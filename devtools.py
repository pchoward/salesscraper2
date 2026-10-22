"""Isolated development previews. Never run the production bookkeeping pipeline."""
import argparse
import contextlib
import datetime
import functools
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import smtplib
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parent
SNAPSHOTS = ('previous_data.json', 'price_history.json', 'scrape_health.json',
             'site_sales.json', 'tracked.yaml', 'watchlist.yaml')


def read_json(path):
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f'{path.name} must contain an object')
    return value


def scan_timestamp(health):
    runs = health.get('runs') or []
    if not runs:
        raise ValueError('Saved health has no original scan timestamp/date')
    latest = max(runs, key=lambda run: run.get('date', ''))
    stamp = latest.get('scanned_at') or latest.get('date')
    # Historical health files may only have the original calendar date.
    datetime.datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
    return str(stamp)


def prepare_workspace(source, output=None):
    source = source.resolve()
    if output is None:
        root = Path(tempfile.mkdtemp(prefix='skatedeals-dev-'))
    else:
        root = Path(output).absolute()
        if root.is_symlink() or root.exists():
            raise ValueError('Output must be a new directory, not an existing path or symlink')
        root = root.resolve()
        if any(root.is_relative_to(base) for base in (SOURCE, source)):
            raise ValueError('Output must be outside the source/production checkout')
        root.mkdir(parents=True)
    if any(root.resolve().is_relative_to(base) for base in (SOURCE, source)):
        raise ValueError('Output must be outside the source/production checkout')
    hashes = {}
    for name in SNAPSHOTS:
        origin = source / name
        if not origin.is_file():
            raise ValueError(f'Missing saved input: {name}')
        shutil.copyfile(origin, root / name)
        (root / name).chmod(0o444)
        hashes[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    manifest = {'development_only': True, 'complete_production_scan': False,
                'input_hashes': hashes, 'source_directory': str(source)}
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return root


def sanitized_env(root):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('SMTP_', 'EMAIL_', 'ADMIN_EMAIL_', 'NOTIFICATION_', 'ALERTS_'))}
    env.update(EMAIL_DRY_RUN='1', NOTIFICATION_ENGINE_ENABLED='0', ALERTS_DELIVERY_ENABLED='0',
               TRACKED_PATH=str(root / 'tracked.yaml'), WATCHLIST_PATH=str(root / 'watchlist.yaml'))
    return env


def blocked(*args, **kwargs):
    raise RuntimeError('Development tools prohibit this network/delivery operation')


@contextlib.contextmanager
def safety_guards(rebuild):
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(smtplib, 'SMTP', blocked))
        stack.enter_context(patch.object(smtplib, 'SMTP_SSL', blocked))
        if rebuild:
            stack.enter_context(patch.object(socket.socket, 'connect', blocked))
            stack.enter_context(patch.object(urllib.request, 'urlopen', blocked))
        yield


@contextlib.contextmanager
def request_metrics(metrics):
    """Count application HTTP calls and navigations, not browser subresources."""
    from stores import browser
    original_open = urllib.request.urlopen
    original_chrome = browser.webdriver.Chrome

    def http(*args, **kwargs):
        metrics['http_requests'] += 1
        return original_open(*args, **kwargs)

    def chrome(*args, **kwargs):
        metrics['browser_starts'] += 1
        driver = original_chrome(*args, **kwargs)
        original_get = driver.get

        def navigate(*args, **kwargs):
            metrics['browser_navigations'] += 1
            return original_get(*args, **kwargs)
        driver.get = navigate
        return driver

    with patch.object(urllib.request, 'urlopen', http), patch.object(browser.webdriver, 'Chrome', chrome):
        yield


def select_scraper(retailer, category):
    from stores.registry import build_scrapers
    matches = [scraper for scraper in build_scrapers()
               if scraper.name.casefold() == retailer.casefold() and scraper.part.casefold() == category.casefold()]
    if len(matches) != 1:
        raise ValueError('Unknown or disabled retailer/category; use the names shown in README')
    return matches[0]


def configure_brand(scraper, brand):
    from stores.zumiez import ZumiezSneakersScraper, explicitly_allowed, star_rules, brand_sale_url, fetch_zumiez_robots
    if not brand:
        return 'category'
    if isinstance(scraper, ZumiezSneakersScraper):
        robots = fetch_zumiez_robots()
        if not explicitly_allowed(star_rules(robots), brand_sale_url(brand)):
            raise ValueError('Brand query is not explicitly allowed by live robots.txt; refusing broad fallback')
        scraper.scrape = functools.partial(scraper.scrape, robots_text=robots,
                                          catalog={'sneakers': [{'brand': brand}]})
        return 'brand-query (live facet must still be valid)'
    return 'post-filter only; normal category pages/shared feed are still fetched'


def filter_brand(items, brand):
    if not brand:
        return items
    words = r'\s+'.join(re.escape(word) for word in brand.split())
    pattern = re.compile(r'(?<!\w)' + words + r'(?!\w)', re.I)
    return [item for item in items if pattern.search(f"{item.get('name', '')} {item.get('description', '')}")]


def render_preview(catalog, history, health, sales, timestamp, label):
    from pipeline import decorate_digest
    from report import Digest, build_report_html
    # No inferred daily diff: a current snapshot cannot recover yesterday's digest.
    digest = Digest()
    failed = {key for key, result in max(health['runs'], key=lambda run: run['date']).get('results', {}).items()
              if result.get('failed') or result.get('suspect')}
    decorate_digest(digest, catalog, history, [], previous_data=catalog,
                    today=timestamp[:10], site_sales=sales, scanned_at=timestamp, failed_keys=failed)
    html = build_report_html(catalog, {}, history, failed_keys=failed, generated_at=timestamp, digest=digest)
    from html import escape
    banner = ('<div role="status" style="padding:16px;background:#fff7ed;color:#7c2d12;font:16px sans-serif">'
              f'<strong>DEVELOPMENT PREVIEW — {escape(label)}</strong><br>'
              f'Saved production scan: {escape(timestamp)}. No state updates or notifications. '
              'Daily new/drop events are not reconstructed.</div>')
    # Inline the existing assets and renderer output; the preview needs no server.
    # Prevent the preview's client-side alert UI from contacting any live API,
    # even if a future renderer supplies a configured endpoint.
    policy = '<meta http-equiv="Content-Security-Policy" content="connect-src &apos;none&apos;; form-action &apos;none&apos;; frame-src &apos;none&apos;">'
    return html.replace('<head>', '<head>' + policy, 1).replace('<body>', '<body>' + banner, 1)


def run_worker(root, mode, retailer=None, category=None, brand=None):
    """Runs only in a dedicated child process whose CWD is the isolated workspace."""
    if root.is_symlink():
        raise ValueError('Workspace must not be a symlink')
    root = root.resolve()
    if mode not in ('rebuild', 'scrape'):
        raise ValueError('Unknown development mode')
    if Path.cwd().resolve() != root or root.is_relative_to(SOURCE):
        raise ValueError('Worker must run in an isolated workspace outside the checkout')
    manifest = read_json(root / 'manifest.json')
    if manifest.get('development_only') is not True or manifest.get('complete_production_scan') is not False:
        raise ValueError('Not a development workspace')
    # Reject symlink destinations and verify all snapshots before any scraper runs.
    for name in (*SNAPSHOTS, 'preview.html', 'targeted-result.json', 'manifest.json'):
        if (root / name).is_symlink():
            raise ValueError('Workspace paths must not be symlinks')
    for name in SNAPSHOTS:
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != manifest['input_hashes'][name]:
            raise ValueError('Input snapshot changed')
    catalog = read_json(root / 'previous_data.json')
    history = read_json(root / 'price_history.json')
    health = read_json(root / 'scrape_health.json')
    sales = read_json(root / 'site_sales.json')
    timestamp = scan_timestamp(health)
    metrics = dict(http_requests=0, browser_starts=0, browser_navigations=0)
    start = time.perf_counter()
    ok = True
    with safety_guards(rebuild=mode == 'rebuild'):
        if mode == 'scrape':
            from stores.runner import run_stores
            scraper = select_scraper(retailer, category)
            key = f'{scraper.name}_{scraper.part}'
            failure_reason = None
            try:
                with request_metrics(metrics):
                    strategy = configure_brand(scraper, brand)
                    print(f'Brand strategy: {strategy}', flush=True)
                    results, failed = run_stores([scraper])
            except Exception as exc:
                # For example, unavailable/disallowing robots must not fall back
                # to a slow full-store crawl when a brand was explicitly selected.
                strategy = 'targeting unavailable; no broad fallback'
                failure_reason = type(exc).__name__
                results, failed = {key: None}, {key}
            ok = key not in failed and isinstance(results.get(key), list)
            items = filter_brand(results[key], brand) if ok else []
            result = {'development_only': True, 'complete_production_scan': False,
                      'scope': {'retailer': scraper.name, 'category': scraper.part, 'brand': brand},
                      'status': 'success' if ok else 'failed', 'brand_strategy': strategy,
                      'diagnostics': {'failure_type': failure_reason,
                                      'candidate_count': getattr(scraper, 'candidates', 0),
                                      'raw_kept_count': len(results[key]) if ok else None,
                                      'brand_kept_count': len(items)},
                      'saved_scan_timestamp': timestamp, 'metrics': metrics,
                      'elapsed_seconds': time.perf_counter() - start,
                      'items': items, 'note': 'PARTIAL: no lifecycle, stock confirmation, history, health, or notification updates'}
            (root / 'targeted-result.json').write_text(json.dumps(result, indent=2) + '\n')
            # Display selected results only, never merge them into the saved catalog.
            catalog = {key: items}
            # A partial preview must not infer absence for any omitted listing,
            # even in read-only lifecycle sections of the existing renderer.
            from filters import normalize_url
            visible_urls = {normalize_url(item.get('url') or '') for item in items}
            history = {url: entry for url, entry in history.items() if normalize_url(url) in visible_urls}
            label = f'PARTIAL targeted results: {key}' + (f' / {brand}' if brand else '')
            if not ok:
                label += ' — FETCH FAILED; not an empty production catalog'
        else:
            label = 'REBUILD ONLY from saved data'
        html = render_preview(catalog, history, health, sales, timestamp, label)
        (root / 'preview.html').write_text(html)
    for name in SNAPSHOTS:
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != manifest['input_hashes'][name]:
            raise ValueError('Development input was modified')
    manifest.update(mode=mode, saved_scan_timestamp=timestamp, metrics=metrics,
                    elapsed_seconds=time.perf_counter() - start, status='success' if ok else 'failed')
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Preview HTML: {root / "preview.html"}', flush=True)
    return 0 if ok else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='mode', required=True)
    for mode in ('rebuild', 'scrape'):
        command = commands.add_parser(mode)
        command.add_argument('--source-dir', type=Path, default=SOURCE, help='Saved inputs; read only')
        command.add_argument('--output-dir', type=Path, help='New directory outside checkout (default: fresh /tmp directory)')
        if mode == 'scrape':
            command.add_argument('--retailer', required=True)
            command.add_argument('--category', required=True)
            command.add_argument('--brand', help='Validated Zumiez shoe query; other categories filter after fetching')
    args = parser.parse_args(argv)
    if args.mode == 'scrape' and args.brand is not None and not args.brand.strip():
        parser.error('--brand must not be blank')
    try:
        if args.mode == 'scrape':
            select_scraper(args.retailer, args.category)  # validate before creating workspace or making requests
        root = prepare_workspace(args.source_dir, args.output_dir)
        request = {'mode': args.mode, 'retailer': getattr(args, 'retailer', None),
                   'category': getattr(args, 'category', None), 'brand': getattr(args, 'brand', None)}
        (root / 'request.json').write_text(json.dumps(request))
        print(f'Development workspace: {root}', flush=True)
        return subprocess.run([sys.executable, str(Path(__file__).resolve()), '_worker', str(root)],
                              cwd=root, env=sanitized_env(root)).returncode
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Development preview failed ({type(exc).__name__}): check saved inputs and arguments', file=sys.stderr)
        return 1


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '_worker':
        try:
            workspace = Path(sys.argv[2]).resolve()
            request = read_json(workspace / 'request.json')
            if request.get('mode') not in ('rebuild', 'scrape'):
                raise ValueError('Unknown mode')
            raise SystemExit(run_worker(workspace, **request))
        except Exception as exc:
            print(f'Development worker failed ({type(exc).__name__}); no production updates were run', file=sys.stderr)
            raise SystemExit(1)
    raise SystemExit(main())
