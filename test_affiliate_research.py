"""Affiliate research cannot approve programs, transform links or mutate state."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import URLError

import yaml

from research.affiliates import (MATRIX, ROOT, SOURCE_HOSTS, collect, fetch, main,
                                 public_url, validate)


def matrix():
    return json.loads(MATRIX.read_text())


class AffiliateMatrixTests(unittest.TestCase):
    def test_all_five_retailers_are_disabled_with_complete_unknown_terms(self):
        data=validate(matrix())
        self.assertEqual(len(data['retailers']),5)
        source=next(r for r in data['retailers'] if r['id']=='source_us')
        self.assertIsNone(source['commission'])
        self.assertIsNone(source['cookie_days'])
        self.assertEqual(source['lead_claims'][0]['commission_percent'],1.6)
        self.assertEqual(source['lead_claims'][0]['cookie_days'],30)
        self.assertFalse(source['lead_claims'][0]['verified'])
        self.assertTrue(all(r['verified_on'] is None and r['application_url'] is None for r in data['retailers']))
        self.assertEqual(next(r for r in data['retailers'] if r['id']=='danscomp')['catalog_status'],'expansion_candidate')

    def test_unverified_leads_cannot_be_promoted_or_enabled(self):
        for field,value in [('enabled',True),('approval','approved'),('commission','1.6%'),('cookie_days',30)]:
            with self.subTest(field=field):
                data=matrix();data['retailers'][0][field]=value
                with self.assertRaises(ValueError):validate(data)
        data=matrix();data['runtime_integration']=True
        with self.assertRaises(ValueError):validate(data)

    def test_unknown_sources_and_local_urls_are_rejected(self):
        data=matrix();data['retailers'][0]['sources']=['invented']
        with self.assertRaises(ValueError):validate(data)
        data=matrix();data['sources'][0]['url']='https://127.0.0.1/metadata'
        with self.assertRaises(ValueError):validate(data)
        for url in ('http://www.albes.com/','https://www.albes.com.evil.test/','https://user:pass@www.albes.com/',
                    'https://www.albes.com:8443/','javascript:alert(1)','file:///etc/passwd',
                    'https://www.albes.com/products/affiliate-swag','https://www.albes.com/collections.json',
                    'https://us.sourcebmx.com/?ref=someone','https://www.albes.com/?affiliate_id=123'):
            self.assertFalse(public_url(url,SOURCE_HOSTS),url)


class AffiliateCollectorTests(unittest.TestCase):
    def test_proxy_denial_is_not_a_retailer_or_program_rejection(self):
        with patch('urllib.request.OpenerDirector.open',side_effect=URLError('Tunnel connection failed: 403 Forbidden')):
            self.assertEqual(fetch('https://www.albes.com/robots.txt')['status'],'environment_proxy_denied')
        get=Mock(return_value={'status':'environment_proxy_denied','body':''})
        report=collect(matrix(),get,sleep=lambda _:None)
        self.assertEqual(get.call_count,8)
        self.assertTrue(all(s['status']=='not_fetched' and s['access']=='robots_unavailable' for s in report['sources']))
        self.assertFalse(report['program_approval'])
        self.assertFalse(report['tracking_enabled'])

    def test_allowed_program_link_is_followed_but_tracking_is_never_enabled(self):
        seen=[]
        def get(url):
            seen.append(url)
            if url.endswith('/robots.txt'):return {'status':200,'body':'User-agent: *\nAllow: /\nCrawl-delay: 3'}
            if 'sponsorship-requests' in url:
                return {'status':200,'body':'<a href="/affiliate-program">Affiliate Program Page</a><a href="https://unapproved.test/apply">Affiliate</a>'}
            if url.endswith('/affiliate-program'):
                return {'status':200,'body':'<p>Commission</p><span>Example 4%</span><p>Deal sites require approval.</p><script>secret-script-value</script>'}
            return {'status':200,'body':'<p>No public terms in this fixture.</p>'}
        before=matrix()
        report=collect(before,get,sleep=lambda _:None)
        self.assertIn('https://www.danscomp.com/affiliate-program',seen)
        self.assertFalse(any('unapproved.test' in url for url in seen))
        program=next(s for s in report['sources'] if s['url'].endswith('/affiliate-program'))
        self.assertIn('Example 4%',str(program['excerpts']))
        self.assertNotIn('secret-script-value',str(program['excerpts']))
        self.assertTrue(report['review_required'])
        self.assertFalse(report['program_approval'])
        self.assertEqual(before,matrix())
        self.assertTrue(all(r['enabled'] is False for r in before['retailers']))

    def test_robots_restrictions_and_cross_host_redirects_stop_requests(self):
        seen=[]
        def get(url):
            seen.append(url)
            if url.endswith('/robots.txt'):
                return {'status':200,'body':'User-agent: *\nDisallow: /'}
            raise AssertionError('No page should be fetched')
        report=collect(matrix(),get,sleep=lambda _:None)
        self.assertTrue(all(s['access']=='robots_disallowed' for s in report['sources']))
        def redirect(url):
            if url.endswith('/robots.txt'):return {'status':404,'body':''}
            return {'status':302,'body':'','location':'https://other.test/program'}
        report=collect(matrix(),redirect,sleep=lambda _:None)
        self.assertTrue(all(r['url'].split('/')[2]!='other.test' for r in report['requests']))
        self.assertFalse(report['tracking_enabled'])

    def test_collection_budget_and_long_crawl_delay_are_enforced(self):
        number=[0]
        def expansive(url):
            if url.endswith('/robots.txt'):return {'status':200,'body':'User-agent: *\nAllow: /'}
            number[0]+=1
            prefix='https://www.danscomp.com/affiliate/'+str(number[0])
            return {'status':200,'body':f'<a href="{prefix}/a">Affiliate</a><a href="{prefix}/b">Affiliate</a>'}
        report=collect(matrix(),expansive,sleep=lambda _:None)
        self.assertLessEqual(len(report['sources']),24)
        self.assertLessEqual(len(report['requests']),32)
        def slow(url):
            self.assertTrue(url.endswith('/robots.txt'))
            return {'status':200,'body':'User-agent: *\nAllow: /\nCrawl-delay: 61'}
        report=collect(matrix(),slow,sleep=lambda _:None)
        self.assertTrue(all(s['access']=='long_crawl_delay_requires_separate_scheduling' for s in report['sources']))

    def test_cli_only_writes_external_research_artifacts_and_returns_blocked(self):
        names=('previous_data.json','price_history.json','scrape_health.json','notification_state.json',
               'sale_items_chart.html','index.html','history.json')
        def hashes():
            return {n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() if (ROOT/n).exists() else None for n in names}
        before=hashes()
        report={'observed_at_utc':'2026-11-01T23:00:00Z','program_approval':False,'tracking_enabled':False,'sources':[], 'requests':[]}
        with tempfile.TemporaryDirectory() as directory,patch('research.affiliates.collect',return_value=report):
            out=Path(directory)/'research'
            self.assertEqual(main(['--output-dir',str(out)]),2)
            self.assertEqual({p.name for p in out.iterdir()},{'summary.md','evidence.json'})
            with self.assertRaises(SystemExit):main(['--output-dir',str(out)])
        self.assertEqual(before,hashes())

    def test_workflow_is_manual_read_only_and_has_no_signup_or_deployment(self):
        text=(ROOT/'.github/workflows/affiliate-research.yml').read_text()
        workflow=yaml.safe_load(text)
        trigger=workflow.get('on',workflow.get(True))
        self.assertEqual(trigger,{'workflow_dispatch':None})
        self.assertEqual(workflow['permissions'],{'contents':'read'})
        checkout=workflow['jobs']['research']['steps'][0]
        self.assertFalse(checkout['with']['persist-credentials'])
        for unwanted in ('secrets.','git push','scraper.py','notification_engine','gh pr merge','deploy','curl -X POST'):
            # Comments may describe that publication does not occur; commands may not.
            commands='\n'.join(s.get('run','') for s in workflow['jobs']['research']['steps'])
            self.assertNotIn(unwanted,commands)

    def test_existing_retailer_links_keep_raw_variant_and_fragment(self):
        from bs4 import BeautifulSoup
        from page import _card_store_link
        url='https://www.albes.com/products/example?variant=20&color=black#details'
        item={'url':url}
        html=_card_store_link(item['url'],'Example',"Albe's BMX")
        link=BeautifulSoup(html,'html.parser').select_one('a')
        self.assertEqual(link['href'],url)
        self.assertEqual(link['target'],'_blank')
        self.assertIn('noopener',link['rel'])
        self.assertEqual(item['url'],url)


if __name__=='__main__':unittest.main()
