"""Bounded public affiliate-source research, never affiliate-link transformation.

GET only, fixed sources, no credentials, no forms, no registration, no products.
Readable excerpts and discovered program links require human review; retrieval
never grants merchant approval or enables tracking. Output stays outside source.
"""
import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib import robotparser
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT/'docs/affiliates/bmx-programs.json'
AGENT = 'ShredDealsResearch/1.0 (+https://github.com/pchoward/salesscraper2; public affiliate terms review)'
MAX_BYTES = 2_000_000
MAX_FOLLOW = 2
MAX_PAGES = 24
SOURCE_HOSTS = frozenset({"www.danscomp.com","www.flexoffers.com","bmxunion.com","www.avantlink.com",
                          "www.albes.com","www.circuitbmx.com","www.powersbmx.com","us.sourcebmx.com"})
WORDS = re.compile(r'affiliat|commission|cookie|attribution|data.?feed|deep.?link|publisher|comparison|coupon|deal.?site|reward|referral|terms', re.I)


def public_url(url, hosts):
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == 'https' and parsed.hostname in hosts and not parsed.username
                and not parsed.password and parsed.port in (None,443)
                and not re.match(r'^/(?:products?|collections?|cart|checkout)(?:/|\.|$)',parsed.path,re.I)
                and not any(re.fullmatch(r'(?:aff(?:iliate)?(?:_?id)?|ref(?:erral|id)?|clickid|tag|publisher|pub_?id|rid)', key, re.I)
                            for key in parse_qs(parsed.query)))
    except ValueError:
        return False


def validate(matrix):
    """This issue's pre-approval packet cannot enable a runtime integration."""
    if matrix.get('runtime_integration') is not False or matrix.get('registration_authorized') is not False or matrix.get('rollout_authorized') is not False:
        raise ValueError('Research packet must remain pre-approval and disabled')
    ids = [r['id'] for r in matrix['retailers']]
    if len(ids)!=len(set(ids)) or set(ids)!={'albes','circuit','powers','source_us','danscomp'}:
        raise ValueError('Expected all five requested retailers exactly once')
    source_ids = {s['id'] for s in matrix['sources']}
    if len(source_ids)!=len(matrix['sources']) or any(not public_url(s['url'],SOURCE_HOSTS) for s in matrix['sources']):
        raise ValueError('Sources must be unique, approved public HTTPS locations')
    for retailer in matrix['retailers']:
        if retailer.get('enabled') is not False or retailer.get('approval')!='not_requested':
            raise ValueError('No program can be activated by this research packet')
        for key in ('application_url','network','commission','cookie_days','us_eligibility','deal_coupon_policy',
                    'deep_link_access','affiliate_data_feed_access','restrictions','confidence','verified_on','attempted_on'):
            if key not in retailer:
                raise ValueError('Missing matrix field: '+key)
        if not set(retailer['sources']) <= source_ids:
            raise ValueError('Unknown evidence source')
        if retailer.get('verified_on') is None and any(retailer[k] is not None for k in ('network','commission','cookie_days')):
            raise ValueError('Unverified commercial terms must stay unknown, not promoted from leads')
        for lead in retailer['lead_claims']:
            if lead.get('verified') is not False or lead['source'] not in source_ids:
                raise ValueError('A lead cannot silently become verified terms')
    return matrix


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url):
    request = Request(url, headers={'User-Agent':AGENT,'Accept':'text/html,text/plain'})
    try:
        with build_opener(NoRedirect()).open(request,timeout=20) as response:
            data=response.read(MAX_BYTES+1)
            if len(data)>MAX_BYTES:
                return {'status':'response_too_large','body':''}
            return {'status':response.status,'body':data.decode('utf-8','replace')}
    except HTTPError as exc:
        return {'status':exc.code,'body':'','location':exc.headers.get('Location','')}
    except URLError as exc:
        reason=str(exc.reason)
        return {'status':'environment_proxy_denied' if 'Tunnel connection failed: 403' in reason else 'network_error',
                'body':'','error':reason}


class Extract(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fragments=[]
        self.links=[]
        self.ignore=0
        self.href=None
        self.label=[]

    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.ignore+=1
        if tag=='a':
            self.href=dict(attrs).get('href')
            self.label=[]

    def handle_endtag(self,tag):
        if tag in ('script','style'):self.ignore=max(0,self.ignore-1)
        if tag=='a' and self.href:
            self.links.append((self.href,' '.join(self.label)))
            self.href=None

    def handle_data(self,data):
        if self.ignore:return
        value=' '.join(data.split())
        if value:
            self.fragments.append(value)
            if self.href:self.label.append(value)


def collect(matrix, get=fetch, sleep=time.sleep):
    validate(matrix)
    hosts={urlsplit(s['url']).hostname for s in matrix['sources']}
    # Only seeds and links on these explicitly declared hosts may be fetched.
    policies={}
    last={}
    requests=[]
    results=[]
    seen=set()
    queue=[(s["url"],s["id"],0) for s in matrix["sources"]]

    def read(url,delay=3):
        host=urlsplit(url).hostname
        elapsed=time.monotonic()-last.get(host,0)
        if elapsed<delay:sleep(delay-elapsed)
        result=get(url)
        last[host]=time.monotonic()
        requests.append({'url':url,**{k:v for k,v in result.items() if k!='body'}})
        return result

    def allowed(url):
        if not public_url(url,hosts):return False,'unapproved_host_or_url'
        parts=urlsplit(url)
        host=parts.hostname
        if host not in policies:
            response=read(urljoin(url,'/robots.txt'))
            if response['status'] not in (200,404):
                policies[host]=(None,3,'robots_unavailable')
            else:
                parser=robotparser.RobotFileParser()
                parser.parse(response.get('body','').splitlines() if response['status']==200 else [])
                delay=max(3,parser.crawl_delay(AGENT) or 0)
                rate=parser.request_rate(AGENT)
                if rate and rate.requests:delay=max(delay,rate.seconds/rate.requests)
                policies[host]=(parser,delay,'ready')
        parser,delay,state=policies[host]
        if parser is None:return False,state
        if delay>60:return False,'long_crawl_delay_requires_separate_scheduling'
        return parser.can_fetch(AGENT,url), 'robots_allowed' if parser.can_fetch(AGENT,url) else 'robots_disallowed'

    def page(url,source,follow=0):
        if url in seen or len(results)>=MAX_PAGES:return
        seen.add(url)
        permit,reason=allowed(url)
        result={'source':source,'url':url,'access':reason,'status':'not_fetched','review_required':True}
        results.append(result)
        if not permit:return
        host=urlsplit(url).hostname
        response=read(url,policies[host][1])
        result['status']=response['status']
        if response.get('location'):
            destination=urljoin(url,response['location'])
            result['redirect']=destination
            # Redirects cannot take credentials/requests to a new host or skip
            # robots rules. Public canonical redirects are bounded like links.
            if follow<MAX_FOLLOW and public_url(destination,hosts):queue.append((destination,source,follow+1))
        if response['status']!=200:return
        parsed=Extract()
        parsed.feed(response.get('body',''))
        result['excerpts']=[' '.join(parsed.fragments[max(0,i-1):i+3])[:1200]
                            for i,x in enumerate(parsed.fragments) if WORDS.search(x)][:25]
        links=[]
        for href,label in parsed.links:
            target=urljoin(url,href)
            if urlsplit(target).scheme=='https' and WORDS.search(label+' '+target):
                links.append({'label':label[:200],'url':target})
        result['links']=links[:25]
        # Follow a small number of actual program links (including Dan's
        # official affiliate destination), not broad terms/footer crawling.
        if follow<MAX_FOLLOW:
            candidates=[link for link in links if re.search(r'affiliat',link['label']+' '+link['url'],re.I)]
            for link in candidates[:2]:
                if public_url(link['url'],hosts):queue.append((link['url'],source,follow+1))

    # Visit every seed before spending the follow-up budget on any one host.
    while queue and len(results)<MAX_PAGES:
        page(*queue.pop(0))
    return {'observed_at_utc':datetime.now(timezone.utc).isoformat(),'purpose':'public-source research only',
            'program_approval':False,'tracking_enabled':False,'review_required':True,
            'sources':results,'requests':requests}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args(argv)
    output=args.output_dir.absolute()
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to(ROOT):
        parser.error('Use a new research directory outside the checkout')
    matrix=validate(json.loads(MATRIX.read_text()))
    result=collect(matrix)
    output.mkdir(parents=True)
    (output/'evidence.json').write_text(json.dumps(result,indent=2)+'\n')
    fetched=sum(s['status']==200 for s in result['sources'])
    summary=(f'# BMX affiliate source research\n\n{fetched} public pages retrieved. '
             'Retrieval is not program approval; merchant terms and publisher eligibility require human review.\n\n'
             'No registration, contact messages, tracking IDs, product scrape, catalog/state writes or deployment.\n\n'
             '| Source | Retrieval | Access |\n|---|---|---|\n'+''.join(
                 f"| {s['source']} | {s['status']} | {s['access']} |\n" for s in result['sources']))
    (output/'summary.md').write_text(summary)
    print(summary)
    return 0 if fetched else 2


if __name__=='__main__':raise SystemExit(main())
