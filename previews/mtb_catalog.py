"""Rebuild an isolated MTB review site from saved state, never live scraping."""
import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import page
import sports
from ci.build_preview import build as build_site
from previews.shreddeals import SOURCE
from rebuild_page import load_report_inputs, save_report_inputs


def build(output,data_root=None,fixture=False):
    output=Path(output).absolute()
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to(SOURCE):
        raise ValueError('Use a new preview directory outside the checkout')
    if not fixture and data_root is None:raise ValueError('Provide saved sport state with --data-root; real inventory is never invented')
    with (tempfile.TemporaryDirectory() if fixture else nullcontext(None)) as temporary:
        if fixture:
            from sports.mtb.stores import scrapers
            root=Path(temporary)
            products=json.loads((SOURCE/'tests/fixtures/mtb/shopify-synthetic.json').read_text())['products']
            with sports.MTB.active():data={s.name+'_'+s.part:s.products_from(products) for s in scrapers()}
            folder=root/'catalogs/mtb';folder.mkdir(parents=True)
            data_path=folder/'previous_data.json';data_path.write_text(json.dumps(data))
            history_path=folder/'price_history.json';history_path.write_text('{}')
            save_report_inputs({},None,[], '2026-11-02T00:00:00+00:00',True,
                path=folder/'report_inputs.json',data_path=data_path,history_path=history_path)
            label='SYNTHETIC MTB FIXTURE — NOT LIVE INVENTORY'
        else:
            root=Path(data_root).resolve()
            folder=root/'catalogs/mtb'
            load_report_inputs(folder/'report_inputs.json',folder/'previous_data.json',folder/'price_history.json')
            data=json.loads((folder/'previous_data.json').read_text())
            if not any(data.values()):raise ValueError('No saved MTB deals: inspect retailer failures rather than manufacturing a catalog')
            label='MTB saved-catalog review'
        with patch.object(page,'ALERTS_UI_CONFIG',{}):build_site(output,label,data_root=root)
    # Preview-only banner cannot cover the existing mobile filter drawer.
    for target in output.rglob('sale_items_chart.html'):
        html=target.read_text()
        if fixture:html=html.replace('</body>','<aside role="note" style="position:fixed;bottom:0;right:0;z-index:2000;background:#92400e;color:white;padding:4px;font:12px system-ui">SYNTHETIC FIXTURE — NOT LIVE INVENTORY</aside></body>',1)
        html=html.replace('</head>','<style>#previewBanner{position:static!important;z-index:auto!important}</style></head>',1)
        html=html.replace('</head>','<meta http-equiv="Content-Security-Policy" content="connect-src &apos;self&apos;; form-action &apos;none&apos;; frame-src &apos;none&apos;"></head>',1)
        target.write_text(html)
    (output/'review-manifest.json').write_text(json.dumps({'synthetic':fixture,'scraping':False,'delivery':False,
        'mtb_listings':sum(len(v) for v in data.values()),'note':'Saved timestamps retained; no source state modified.'},indent=2)+'\n')
    return output/'index.html'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--data-root',type=Path)
    parser.add_argument('--fixture',action='store_true',help='Explicitly synthetic UI QA only, not a real catalog preview')
    args=parser.parse_args()
    print('Preview HTML:',build(args.output_dir,args.data_root,args.fixture))
    print('Serve the directory; open index.html?sport=mtb or mtb/sale_items_chart.html.')


if __name__=='__main__':main()
