"""Bounded, read-only BMX source research. No catalog/state/notification writes.

Reads robots.txt first, then (only when allowed) the homepage and up to two
linked terms pages. Product feeds are deliberately left for after reviewing
access terms and choosing an adapter. Outputs evidence outside the checkout.
"""
import argparse
from datetime import datetime, timezone
from html import unescape
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
from urllib import robotparser
from urllib.parse import urljoin, urlsplit

from audit.store_probe import USER_AGENT, _Links, platform_of, sale_links

CANDIDATES = (
    {'id': 'danscomp', 'name': "Dan's Comp", 'url': 'https://www.danscomp.com/'},
    {'id': 'sourcebmx', 'name': 'Source BMX', 'url': 'https://www.sourcebmx.com/'},
)
SOURCE = Path(__file__).resolve().parents[1]
MAX_BYTES = 2_000_000


class NoRedirect(urllib.request.HTTPRedirectHandler):
    # A new host/path needs its own policy review, not an implicit follow.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,text/plain'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                return {'status': 'response_too_large', 'body': ''}
            return {'status': response.status, 'body': raw.decode('utf-8', 'replace')}
    except urllib.error.HTTPError as exc:
        return {'status': exc.code, 'body': '', 'redirect': exc.headers.get('Location', '')}
    except urllib.error.URLError as exc:
        reason = str(exc.reason)
        return {'status': 'environment_proxy_denied' if 'Tunnel connection failed: 403' in reason else 'network_error',
                'body': '', 'error': reason}


def research(store, get=fetch, sleep=time.sleep):
    """Return evidence, explicitly distinguishing blocked from empty/successful."""
    report = {'retailer': store['name'], 'base': store['url'], 'requests': [],
              'status': 'unverified', 'platform': [], 'sale_links': [], 'terms': [],
              'products_observed': None, 'catalog_scan': False, 'approved_source': False}
    evidence = {}
    delay = 3.0

    def read(url, filename):
        if report['requests']:
            sleep(delay)
        result = get(url)
        report['requests'].append({'url': url, **{k: v for k, v in result.items() if k != 'body'}})
        if result.get('status') == 200:
            evidence[filename] = result.get('body', '')
        return result

    robots_url = urljoin(store['url'], '/robots.txt')
    result = read(robots_url, 'robots.txt')
    if result.get('status') != 200:
        report['status'] = 'access_unverified'
        report['blocker'] = 'robots.txt could not be verified; no retailer page or feed was requested'
        return report, evidence
    robots = robotparser.RobotFileParser()
    robots.parse(result.get('body', '').splitlines())
    delay = max(delay, robots.crawl_delay(USER_AGENT) or 0)
    rate = robots.request_rate(USER_AGENT)
    if rate and rate.requests:
        delay = max(delay, rate.seconds / rate.requests)
    report['minimum_request_delay_seconds'] = delay
    if not robots.can_fetch(USER_AGENT, store['url']):
        report['status'] = 'robots_disallowed'
        report['blocker'] = 'robots.txt disallows the homepage for the research user agent'
        return report, evidence
    home = read(store['url'], 'home.html')
    if home.get('status') != 200:
        report['status'] = 'homepage_unavailable'
        report['blocker'] = 'Homepage unavailable or redirected; review destination before requesting more'
        return report, evidence
    report['platform'] = platform_of(home.get('body', ''))
    report['sale_links'] = sale_links(home.get('body', ''), store['url'])
    links = _Links()
    links.feed(home.get('body', ''))
    seen = set()
    for href, label in links.links:
        if not re.search(r'\bterms\b', unescape(label) + ' ' + str(href).replace('-', ' '), re.I):
            continue
        url = urljoin(store['url'], href)
        if urlsplit(url).netloc != urlsplit(store['url']).netloc or url in seen or urlsplit(url).scheme != 'https':
            continue
        seen.add(url)
        if not robots.can_fetch(USER_AGENT, url):
            report['terms'].append({'url': url, 'status': 'robots_disallowed'})
            continue
        terms = read(url, 'terms-' + str(len(report['terms']) + 1) + '.html')
        report['terms'].append({'url': url, 'status': terms.get('status')})
        if len(report['terms']) >= 2:
            break
    report['status'] = 'terms_review_required'
    report['blocker'] = 'Review captured terms and permitted feed paths before requesting product data or approving an adapter'
    return report, evidence


def run(output, get=fetch, sleep=time.sleep):
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to(SOURCE):
        raise ValueError('Use a new evidence directory outside the checkout')
    output.mkdir(parents=True)
    reports = []
    for store in CANDIDATES:
        report, evidence = research(store, get, sleep)
        reports.append(report)
        target = output / store['id']
        target.mkdir()
        for name, body in evidence.items():
            (target / name).write_text(body)
    result = {'observed_at': datetime.now(timezone.utc).isoformat(), 'production_scan': False, 'retailers': reports}
    (output / 'readiness.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir), indent=2))


if __name__ == '__main__':
    main()
