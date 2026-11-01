"""Rebuild the first real BMX snapshot with quality rules, without fetching."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import page
import sports
from ci.build_preview import build as build_site, mark_preview
from previews.publish import publish
from previews.shreddeals import SOURCE
from report import build_report_html
from sports.bmx.audit import classify

FIXTURES = SOURCE/'tests/fixtures/bmx'


def build(output):
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to(SOURCE):
        raise ValueError('Use a new preview directory outside the checkout')
    provenance = json.loads((FIXTURES/'provenance.json').read_text())
    values = {}
    for name in ('previous_data.json','price_history.json','report_inputs.json'):
        raw = (FIXTURES/('albes-'+name)).read_bytes()
        if hashlib.sha256(raw).hexdigest() != provenance['sha256'][name]:
            raise ValueError('Saved snapshot does not match its recorded provenance')
        values[name] = json.loads(raw)
    selected, audit = classify(values['previous_data.json'], values['price_history.json'])
    selected_urls = {i['url'] for items in selected.values() for i in items}
    inputs = values['report_inputs.json']
    changes = {key:[change for change in changes if (change.get('item') or {}).get('url') in selected_urls]
               for key,changes in inputs['changes'].items()}
    output.mkdir(parents=True)
    site = output/'site'
    # Empty external data root avoids loading another task's catalog. The
    # existing builder renders safe Skate, then the original sport renderer
    # renders this classified snapshot. No engine, state or delivery execution.
    with tempfile.TemporaryDirectory() as empty_data, patch.object(page,'ALERTS_UI_CONFIG',{}):
        build_site(site, 'BMX quality review', data_root=empty_data)
        html = build_report_html(selected, changes, values['price_history.json'],
                                 generated_at=inputs['generated_at'], sport=sports.BMX)
        policy = '<meta http-equiv="Content-Security-Policy" content="connect-src &apos;self&apos;; form-action &apos;none&apos;; frame-src &apos;none&apos;">'
        html = html.replace('</head>',policy+'</head>',1)
        target = site/sports.BMX.page_path
        target.parent.mkdir(parents=True,exist_ok=True)
        labeled = mark_preview(html,'BMX quality review')
        # Review-only banner must not cover the original sticky nav on scroll.
        labeled = labeled.replace('</head>', '<style>#previewBanner{position:static!important;top:auto!important;z-index:auto!important}</style></head>', 1)
        page.write_page(labeled,str(target))
        publish(site,catalogs={'bmx':sports.BMX.page_path})
        home=site/'index.html'
        home.write_text(mark_preview(home.read_text(),'BMX quality review'))
    audit['source']=provenance
    audit['scan_timestamp']=inputs['generated_at']
    (output/'quality-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    (output/'README.txt').write_text('Review only. Serve site/ with python -m http.server --directory site. Open the served index.html?sport=bmx. No scrape or delivery. quality-audit.json is an internal review report outside site/.\n')
    return site/'index.html'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    print('Preview HTML:',build(args.output_dir))
    print('Open the served index.html?sport=bmx; scan time is preserved.')


if __name__=='__main__':main()
