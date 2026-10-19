"""Opt-in personal watch events. State contains hashes/flags, never email or URLs."""

import copy
import datetime as dt
import fcntl
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import tempfile

from filters import is_meaningful_drop, normalize_url
from history import all_time_low_status
from watchlist import load_watchlist, rule_matches

logger = logging.getLogger('notification_engine')
STATE_PATH = 'notification_state.json'
MAX_RECORDS = 4096
MAX_EVENTS = 1024
MAX_DIGEST_WATCHES = 25
EVENT_DAYS = 30
LABELS = {'match': 'New watch match', 'price': 'Maximum price reached',
          'drop': 'Meaningful price drop', 'low': 'Verified historical low', 'stock': 'Back in stock (verified)'}


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _price(value):
    if isinstance(value, bool):
        return None
    try:
        price = float(value)
        return price if math.isfinite(price) and price >= 0 else None
    except (ValueError, TypeError):
        return None


def empty_state():
    return {'version': 1, 'records': {}, 'events': {}}


def _validate(state):
    if (not isinstance(state, dict) or set(state) != {'version', 'records', 'events'}
            or state.get('version') != 1 or not isinstance(state.get('records'), dict)
            or not isinstance(state.get('events'), dict) or len(state['records']) > MAX_RECORDS
            or len(state['events']) > MAX_EVENTS):
        raise ValueError('Unsupported notification state')
    digest = lambda value: isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value)
    fields = {'rule_id', 'owner_id', 'recipient_id', 'product_id', 'category', 'conditions',
              'sequence', 'last_price', 'stock', 'touched', 'blocked'}
    for key, record in state['records'].items():
        if not digest(key) or not isinstance(record, dict) or set(record) - fields:
            raise ValueError('Malformed notification record')
        if any(not digest(record.get(k)) for k in ['rule_id', 'owner_id', 'recipient_id', 'product_id']):
            raise ValueError('Malformed notification identity')
        if not re.fullmatch(r'[A-Za-z0-9 _-]{1,100}', str(record.get('category', ''))):
            raise ValueError('Invalid notification category')
        conditions = record.get('conditions')
        if not isinstance(conditions, dict) or set(conditions) - {'price', 'low', 'match'} or any(type(v) is not bool for v in conditions.values()):
            raise ValueError('Invalid condition state')
        if type(record.get('sequence')) is not int or record['sequence'] < 0:
            raise ValueError('Invalid event sequence')
        if 'blocked' in record and type(record['blocked']) is not bool:
            raise ValueError('Invalid delivery hold flag')
        if record.get('stock') is not None and type(record['stock']) is not bool:
            raise ValueError('Invalid stock state')
        if record.get('last_price') is not None and _price(record['last_price']) is None:
            raise ValueError('Invalid price state')
        if record.get('touched'):
            dt.date.fromisoformat(record['touched'])
    for key, event in state['events'].items():
        if not digest(key) or not isinstance(event, dict) or set(event) != {'record', 'kind', 'status', 'date', 'price'}:
            raise ValueError('Malformed notification event')
        if event['record'] not in state['records'] or event['kind'] not in LABELS or event['status'] not in {'pending', 'sending', 'delivered', 'uncertain'}:
            raise ValueError('Invalid notification event')
        dt.date.fromisoformat(event['date'])
        if _price(event['price']) is None:
            raise ValueError('Invalid event price')
    return state


def load_state(path, initialize=False):
    path = Path(path)
    if not path.exists():
        if initialize:
            return empty_state()
        raise ValueError('Notification state missing; explicit initialization required (delivery disabled)')
    state = json.loads(path.read_text(encoding='utf-8'))
    return _validate(state)


def save_state(path, state):
    """Atomic private local checkpoint. Cache persistence is handled by Actions."""
    _validate(state)
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=path.name+'.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(state, handle, sort_keys=True, allow_nan=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _alias(value):
    value = str(value)
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value):
        raise ValueError('Owner/recipient IDs must be non-personal aliases, never email addresses')
    return value


def _stock(item, rule):
    if item.get('part') == 'Sneakers' and rule.get('size') not in (None, '') and not isinstance(item.get('shoe_sizes'), list):
        return None
    if 'shoe_sizes' in item and isinstance(item['shoe_sizes'], list):
        target = rule.get('size')
        if target not in (None, ''):
            return any(_price(size) == _price(target) for size in item['shoe_sizes']) if _price(target) is not None else None
        return bool(item['shoe_sizes'])
    return {'in_stock': True, 'out_of_stock': False}.get(item.get('stock'))


def evaluate(state, rules, catalog, history, failed_keys=(), previous=None,
             stock_evidence=None, skip_urls=(), day=None, owner_id='personal', recipient_id='primary'):
    """Pure planning: return bounded state and transient grouped email hits.

    Unknown/missing listings and bad scans never establish a stock transition.
    Definite negative stock or a known above-threshold price can re-arm a watch.
    """
    day = str(day or dt.date.today().isoformat())[:10]
    cutoff = (dt.date.fromisoformat(day) - dt.timedelta(days=EVENT_DAYS)).isoformat()
    state = copy.deepcopy(state)
    records, events = state['records'], state['events']
    failed = set(failed_keys)
    skip = {normalize_url(u) for u in skip_urls}
    owner_id, recipient_id = _alias(owner_id), _alias(recipient_id)
    prior = {normalize_url(i.get('url')): i for rows in (previous or {}).values() for i in rows or [] if isinstance(i, dict)}
    candidates = {}
    known_out = {_hash(normalize_url(url)) for url, status in (stock_evidence or {}).items() if status == 'out_of_stock'}
    # Recover an interrupted send before considering new events for that watch.
    for event_id, event in list(events.items()):
        if event['status'] == 'sending':
            event['status'] = 'uncertain'
            records[event['record']]['blocked'] = True
        if event['date'] < cutoff and event['status'] in {'pending', 'delivered'}:
            if event['status'] == 'pending':
                logger.warning('An undelivered watch event expired after %s days', EVENT_DAYS)
            del events[event_id]
    active_rules = set()
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        owner = _alias(rule.get('owner_id') or 'personal')
        recipient = _alias(rule.get('recipient_id') or 'primary')
        if (owner, recipient) != (owner_id, recipient_id):
            continue  # no implicit routing of another owner's watches
        identity = {k: v for k, v in rule.items() if k != 'note'}
        rule_id = _hash(identity)
        active_rules.add(rule_id)
        for category, items in catalog.items():
            if category in failed or not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                url = normalize_url(item.get('url'))
                if not url or url in skip:
                    continue
                selector = dict(rule)
                if item.get('part') == 'Sneakers':
                    if rule.get('size') not in (None, '') and _price(rule['size']) is None:
                        continue
                    selector.pop('size', None)  # observe reliable negative size stock too
                if not rule_matches(selector, item):
                    continue
                product_id = _hash(url)
                key = _hash([owner, recipient, rule_id, product_id])
                record = records.get(key)
                if record is None:
                    if len(records) >= MAX_RECORDS:
                        logger.warning('Watch state capacity reached; new identities skipped, not evicted')
                        continue
                    record = {'rule_id': rule_id, 'owner_id': _hash(owner), 'recipient_id': _hash(recipient),
                              'product_id': product_id, 'category': category, 'conditions': {}, 'sequence': 0,
                              'last_price': _price((prior.get(url) or {}).get('price_new')), 'stock': None}
                    records[key] = record
                stock = _stock(item, rule)
                if stock is None and (record.get('stock') is False or product_id in known_out
                                      or (item.get('part') == 'Sneakers' and rule.get('size') not in (None, ''))):
                    if record.get('stock') is False or product_id in known_out:
                        record['stock'] = False
                        record['conditions'] = {k: False for k in record['conditions']}
                    continue
                if stock is False:
                    # Never learn another size's price (or an unavailable offer's
                    # price) while the watched variant is definitely out of stock.
                    record.update(stock=False, conditions={k: False for k in ['price', 'low', 'match']}, touched=day)
                    for eid in [eid for eid, event in events.items() if event['record'] == key and event['status'] == 'pending']:
                        del events[eid]
                    continue
                current = _price(item.get('price_new'))
                if item.get('part') == 'Sneakers' and rule.get('size') not in (None, ''):
                    prices = item.get('shoe_prices')
                    if isinstance(prices, dict):
                        current = next((_price(v) for size, v in prices.items() if _price(size) == _price(rule['size'])), current)
                if current is None:
                    continue
                old_stock = record.get('stock')
                if old_stock is None and (stock_evidence or {}).get(url) == 'out_of_stock':
                    old_stock = False
                previous_price = record.get('last_price')
                low = bool(all_time_low_status(item, history).get('flagged'))
                if item.get('part') == 'Sneakers' and rule.get('size') not in (None, ''):
                    low = False  # existing history is listing-level, not size-specific
                threshold = _price(rule.get('max_price'))
                explicit = (any(rule.get(k) is True for k in ['alert_on_drop', 'alert_on_low', 'alert_on_stock'])
                            or any(rule.get(k) not in (None, '') for k in ['max_price', 'back_in_stock_width']))
                conditions = {'price': threshold is not None and current < threshold,
                              'low': low, 'match': True}
                reasons = []
                if stock is not False:
                    if threshold is not None and conditions['price'] and not record['conditions'].get('price'):
                        reasons.append('price')
                    if (rule.get('alert_on_drop') is True or not explicit) and previous_price is not None and is_meaningful_drop(previous_price, current):
                        reasons.append('drop')
                    if rule.get('alert_on_low') is True and low and (not record['conditions'].get('low') or (previous_price is not None and current < previous_price)):
                        reasons.append('low')
                    target = rule.get('back_in_stock_width')
                    width_ok = target in (None, '') or rule_matches(dict(rule, width=target), item)
                    if (rule.get('alert_on_stock') is True or target not in (None, '') or not explicit) and width_ok and stock is True and old_stock is False:
                        reasons.append('stock')
                    if not explicit and not record['conditions'].get('match'):
                        reasons.append('match')
                record.update(conditions=conditions, last_price=current, touched=day)
                if stock is not None:
                    record['stock'] = stock
                selected_item = dict(item, price_new=f'{current:.2f}')
                if item.get('part') == 'Sneakers' and rule.get('size') not in (None, ''):
                    compares = item.get('shoe_compares')
                    if isinstance(compares, dict):
                        original = next((_price(v) for size, v in compares.items() if _price(size) == _price(rule['size'])), None)
                        if original is not None:
                            selected_item['price_old'] = f'{original:.2f}'
                candidates[key] = (rule, selected_item, owner, recipient)
                for kind in reasons:
                    if record.get('blocked'):
                        continue
                    pending = next((e for e in events.values() if e['record'] == key and e['kind'] == kind and e['status'] == 'pending'), None)
                    if pending:
                        pending['price'] = current
                        continue
                    if len(events) >= MAX_EVENTS:
                        logger.warning('Watch event capacity reached; new event skipped')
                        continue
                    record['sequence'] += 1
                    event_id = _hash([key, kind, record['sequence'], day])
                    events[event_id] = {'record': key, 'kind': kind, 'status': 'pending', 'date': day, 'price': current}
    for key, record in list(records.items()):
        if record['rule_id'] not in active_rules:
            # Only remove rules owned by this configured route; other routes stay intact.
            if record['owner_id'] == _hash(owner_id) and record['recipient_id'] == _hash(recipient_id):
                for event_id in [e for e in events if events[e]['record'] == key]:
                    del events[event_id]
                del records[key]
            continue
        if key not in candidates and record['category'] in catalog and record['category'] not in failed:
            # A verified out-of-stock check can re-arm stock; absence alone cannot.
            if record['product_id'] in known_out:
                record['stock'] = False
                record['conditions'] = {k: False for k in record['conditions']}
    grouped = {}
    for event_id, event in list(events.items()):
        key = event['record']
        if event['status'] != 'pending' or key not in candidates or records[key].get('blocked'):
            continue
        rule, item, owner, recipient = candidates[key]
        record = records[key]
        kind = event['kind']
        valid = record.get('stock') is not False
        if kind in ('price', 'low'):
            valid &= bool(record['conditions'].get(kind))
        if kind == 'drop':
            valid &= _price(item['price_new']) <= event['price']
        if kind == 'stock' and _stock(item, rule) is not True:
            continue  # unknown evidence cannot renew a back-in-stock delivery
        if not valid:
            del events[event_id]
            continue
        hit = grouped.setdefault(key, {'rule_id': str(rule.get('id') or ''), 'owner_id': owner,
                                      'recipient_id': recipient, 'note': ' · '.join(filter(None, [str(rule.get('note') or ''), f"Size {rule['size']}" if rule.get('size') not in (None, '') else ''])),
                                      'item': item, 'reasons': [], 'event_ids': []})
        if LABELS[kind] not in hit['reasons']:
            hit['reasons'].append(LABELS[kind])
        hit['event_ids'].append(event_id)
    return state, list(grouped.values())


def send_notifications(digest, catalog, history, failed_keys=(), previous=None,
                       stock_evidence=None, skip_urls=(), dry_run=None, env=None, rules=None,
                       path=None, day=None, sender=None):
    """Opt-in wrapper; failures never stop scraping. Dry runs never change state."""
    from notify import send_digest, deliver_digest_result, load_smtp_config
    env = os.environ if env is None else env
    if str(env.get('NOTIFICATION_ENGINE_ENABLED', '')).lower() not in {'1', 'true'}:
        return send_digest(digest, env=env, dry_run=dry_run)
    path = Path(path or env.get('NOTIFICATION_STATE_PATH') or STATE_PATH)
    preview = load_smtp_config(env).dry_run if dry_run is None else dry_run
    try:
        # Serialize local reruns. Workflow-level concurrency protects Actions cache snapshots.
        with open(str(path)+'.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            state = load_state(path, initialize=preview or env.get('NOTIFICATION_ALLOW_BOOTSTRAP') == '1')
            state, hits = evaluate(state, rules if rules is not None else load_watchlist(), catalog, history,
                                   failed_keys, previous, stock_evidence, skip_urls, day,
                                   env.get('NOTIFICATION_OWNER_ID') or 'personal', env.get('NOTIFICATION_RECIPIENT_ID') or 'primary')
            # Keep watch digests concise; unselected pending events stay queued.
            hits.sort(key=lambda hit: (min(state['events'][eid]['date'] for eid in hit['event_ids']), min(hit['event_ids'])))
            hits = hits[:MAX_DIGEST_WATCHES]
            outgoing = copy.copy(digest)
            outgoing.watch_alerts = hits
            outgoing.watch_hits = hits  # never include another route's quiet matches/notes
            ids = [eid for hit in hits for eid in hit['event_ids']]
            if not preview:
                for eid in ids:
                    state['events'][eid]['status'] = 'sending'
                save_state(path, state)  # abort before SMTP if the journal cannot be written
            result = (sender or deliver_digest_result)(outgoing, env=env, dry_run=preview,
                                                       delivery_id=_hash(sorted(ids)) if ids else None)
            if not preview:
                for eid in ids:
                    event = state['events'][eid]
                    event['status'] = {'sent': 'delivered', 'failed': 'pending', 'skipped': 'pending', 'empty': 'pending'}.get(result, 'uncertain')
                    if event['status'] == 'uncertain':
                        state['records'][event['record']]['blocked'] = True
                save_state(path, state)
            return result in {'sent', 'preview'}
    except Exception as exc:
        logger.error('Notification engine unavailable (%s); delivery skipped', type(exc).__name__)
        return False


def main(argv=None):
    """Local administration and preview only; this CLI never sends email."""
    import argparse
    from report import Digest
    parser = argparse.ArgumentParser(description=main.__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--initialize', action='store_true')
    action.add_argument('--status', action='store_true')
    action.add_argument('--preview', action='store_true')
    action.add_argument('--resolve', metavar='EVENT_ID')
    parser.add_argument('--outcome', choices=['delivered', 'retry'])
    parser.add_argument('--state', type=Path, default=Path(STATE_PATH))
    parser.add_argument('--catalog', type=Path, default=Path('previous_data.json'))
    parser.add_argument('--history', type=Path, default=Path('price_history.json'))
    parser.add_argument('--health', type=Path, default=Path('scrape_health.json'))
    args = parser.parse_args(argv)
    try:
        if args.preview:
            catalog = json.loads(args.catalog.read_text())
            history = json.loads(args.history.read_text())
            health = json.loads(args.health.read_text())
            if not isinstance(catalog, dict) or not isinstance(history, dict) or not isinstance(health, dict):
                raise ValueError('Preview requires catalog/history/health objects')
            runs = health.get('runs') or []
            if not runs:
                raise ValueError('Preview requires observed scrape health, not assumed success')
            latest = max(runs, key=lambda run: run['date'])
            failed = {key for key, result in latest['results'].items() if result.get('failed') or result.get('suspect')}
            env = dict(os.environ, NOTIFICATION_ENGINE_ENABLED='1')
            written = send_notifications(Digest(), catalog, history, failed, previous=catalog,
                                         dry_run=True, env=env, path=args.state)
            print('Preview written to email_preview.html' if written else 'No preview written: no qualifying events or state unavailable')
            return 0 if written else 1
        with open(str(args.state)+'.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if args.initialize:
                if args.state.exists():
                    raise ValueError('State exists; refusing to reset delivery history')
                save_state(args.state, empty_state())
                print('Empty notification state initialized; no email sent')
                return 0
            state = load_state(args.state)
            if args.resolve:
                if not args.outcome:
                    raise ValueError('--resolve requires --outcome after verifying the delivery externally')
                event = state['events'].get(args.resolve)
                if event is None or event['status'] not in {'pending', 'sending', 'uncertain'}:
                    raise ValueError('Only an existing pending or ambiguous event can be resolved')
                if event['status'] == 'pending' and args.outcome != 'delivered':
                    raise ValueError('Pending events are already retryable; only explicit acknowledgement is needed')
                event['status'] = 'pending' if args.outcome == 'retry' else 'delivered'
                key = event['record']
                if not any(e['record'] == key and e['status'] in {'sending', 'uncertain'} for e in state['events'].values()):
                    state['records'][key]['blocked'] = False
                save_state(args.state, state)
                print('Delivery resolution saved; no email sent. Retrying an accepted message can duplicate it.')
            else:
                statuses = {status: sum(e['status'] == status for e in state['events'].values())
                            for status in ['pending', 'sending', 'delivered', 'uncertain']}
                print(json.dumps({'records': len(state['records']), 'events': statuses,
                                  'held_event_ids': [key for key, e in state['events'].items() if e['status'] in {'sending', 'uncertain'}],
                                  'pending_event_ids': [key for key, e in state['events'].items() if e['status'] == 'pending']}, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    raise SystemExit(main())
