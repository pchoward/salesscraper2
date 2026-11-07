"""Labeled truck UI fixtures in an isolated preview; no stored catalog changes."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import page
from report import build_report_html
from ci.build_preview import mark_preview


def build(output):
    output = Path(output).resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Use a preview outside the checkout')
    items = []
    def item(key, name, **extra):
        items.append({'name':name, 'part':'Trucks', 'store':'TGM',
                      'url':'https://example.test/'+key, 'price_new':50, 'price_old':100, **extra})
    item('variants','Ace AF1 SYNTHETIC variants', spec_offers=[
        {'truck_size':'55','price':50,'compare_at_price':100,'available':True},
        {'truck_size':'66','price':150,'available':True},
        {'truck_size':'66','price':20,'compare_at_price':100,'available':False}])
    item('wide','Ace AF1 80 SYNTHETIC',price_new=100)
    item('stage4','Independent Stage 4 Gonz 166 SYNTHETIC',price_new=90)
    item('legacy','Independent Stage 11 159 (8.75") SYNTHETIC',price_new=70)
    item('unverified','Thunder Team 149 SYNTHETIC',price_new=40)
    item('missing','Ace AF1 SYNTHETIC missing size',price_new=30)
    item('classic','Ace Classic 66 SYNTHETIC',price_new=120)
    item('classic-small','Ace Classic 00 SYNTHETIC',price_new=40)
    page.ALERTS_UI_CONFIG = {}
    html = build_report_html({'TGM_Trucks':items},{},{},set(),generated_at='2026-11-07T10:00:00+00:00')
    (output/'truck-fixtures.html').write_text(mark_preview(html,'SYNTHETIC trucks; not real inventory'))


if __name__ == '__main__':
    build(sys.argv[1])
