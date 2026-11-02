"""Policy-checked, single-run shared cache. No retries or anti-bot workarounds."""
import json
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.robotparser import RobotFileParser

USER_AGENT = 'ShredDealsExplore/1.0 (+https://github.com/pchoward/salesscraper2)'
MAX_BYTES = 4 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Redirect requires source review')


class Reader:
    def __init__(self, max_requests=30, max_seconds=120):
        self.opener = build_opener(NoRedirect())
        self.max_requests = max_requests
        self.deadline = time.monotonic() + max_seconds
        self.requests = 0
        self.bytes = 0
        self.cache = {}
        self.policies = {}
        self.last_request = {}

    def get(self, url, delay=1.5):
        if url in self.cache:
            return self.cache[url]
        if self.requests >= self.max_requests or time.monotonic() >= self.deadline:
            raise RuntimeError('Run request/time budget exhausted')
        host = urlsplit(url).netloc
        wait = max(0, self.last_request.get(host, 0) + delay - time.monotonic())
        if time.monotonic() + wait >= self.deadline:
            raise RuntimeError('Run time budget exhausted')
        time.sleep(wait)
        self.requests += 1
        self.last_request[host] = time.monotonic()
        with self.opener.open(Request(url, headers={'User-Agent': USER_AGENT}),
                              timeout=max(.1, min(15, self.deadline - time.monotonic()))) as response:
            body = response.read(MAX_BYTES + 1)
        if time.monotonic() > self.deadline:
            raise RuntimeError('Run time budget exhausted')
        if len(body) > MAX_BYTES:
            raise RuntimeError('Response byte budget exhausted')
        self.bytes += len(body)
        self.cache[url] = body
        return body

    def __call__(self, source, page, limit):
        if not source.get('approved') or not source.get('approval_note'):
            raise RuntimeError('Source awaits retailer policy and eligibility review')
        base = source['base'].rstrip('/')
        url = base + '/collections/' + source['collection'] + '/products.json?' + urlencode({'limit': limit, 'page': page})
        if base not in self.policies:
            policy = RobotFileParser(base + '/robots.txt')
            # Fail closed for missing or unreadable policies as well as 403.
            policy.parse(self.get(base + '/robots.txt').decode('utf-8').splitlines())
            self.policies[base] = policy
        policy = self.policies[base]
        if not policy.can_fetch(USER_AGENT, url):
            raise RuntimeError('Retailer robots policy denies collection feed')
        delay = max(1.5, policy.crawl_delay(USER_AGENT) or 0)
        rate = policy.request_rate(USER_AGENT)
        if rate:
            delay = max(delay, rate.seconds / rate.requests)
        return json.loads(self.get(url, delay))
