"""Generate the public ShredDeals homepage/assets without scraping or delivery."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
import re
from pathlib import Path
import shutil

from previews.shreddeals import HERE, SOURCE, load_config, render_shell, skate_query_keys


class CategoryParser(HTMLParser):
    """Read the generated controls, without building a catalog DOM."""
    def __init__(self):
        super().__init__()
        self.categories = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag != 'button' or not all(key in attrs for key in ('data-part', 'data-order', 'data-count')):
            return
        category = attrs['data-part']
        from query_state import TYPE_TO_SLUG
        slug = 'all' if category == 'all' else TYPE_TO_SLUG.get(category) or re.sub(r'[^a-z0-9]+', '-', category.lower().replace('&', ' ')).strip('-')
        self.categories[category] = {'category': category, 'order': int(attrs['data-order']),
                                     'count': int(attrs['data-count']), 'slug': slug}


def publish_categories(output, config):
    for sport in config['sports']:
        if not sport.get('catalog'):
            continue
        # Preview builds have just rendered their catalogs in output. Isolated
        # shell publication uses the saved public catalogs from the checkout.
        source = output / sport['catalog']
        if not source.is_file():
            source = SOURCE / sport['catalog']
        parser = CategoryParser()
        with source.open() as catalog:
            for chunk in iter(lambda: catalog.read(65536), ''):
                parser.feed(chunk)
        entries = sorted(parser.categories.values(), key=lambda entry: entry['order'])
        payload = json.dumps(entries, ensure_ascii=False, separators=(',', ':')) + '\n'
        relative = 'navigation/' + sport['id'] + '-categories.json'
        target = output / relative
        if target.is_symlink():
            raise ValueError('Public assets must not be symlinks')
        target.write_text(payload, encoding='utf-8')
        sport['categoriesURL'] = relative + '?v=' + hashlib.sha256(payload.encode()).hexdigest()[:12]


def publish(output=SOURCE, catalogs=None):
    """``catalogs`` maps other sports to their pages ({'bmx': 'bmx/sale_items_chart.html'}). Without it, the
    sports whose catalog has listings in the repository (sports.published_catalogs) get their tab."""
    if catalogs is None:
        import sports
        catalogs = sports.published_catalogs(SOURCE)
    output=Path(output).resolve()
    config=load_config(HERE/'sports.json')
    config['production']=True
    config['skateQueryKeys']=skate_query_keys()
    for sport in config['sports']:
        if sport['id']=='skate':sport['catalog']='sale_items_chart.html'
        elif (catalogs or {}).get(sport['id']):sport['catalog']=catalogs[sport['id']]
    assets=output/'navigation'
    for path in (output/'index.html',assets):
        if path.is_symlink():raise ValueError('Public output paths must not be symlinks')
    output.mkdir(parents=True,exist_ok=True)
    assets.mkdir(exist_ok=True)
    for name in ('navigation.js','navigation.css','skate-bridge.js'):
        if (assets/name).is_symlink():raise ValueError('Public assets must not be symlinks')
        shutil.copyfile(HERE/name,assets/name)
    publish_categories(output, config)
    if any(sport['id'] == 'mtb' and sport.get('catalog') for sport in config['sports']):
        from explore.public import publish_demo
        config['exploreScopes'] = [publish_demo(output)]
    (output/'index.html').write_text(render_shell(config,asset_prefix='navigation/'))
    return output/'index.html'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=SOURCE)
    args=parser.parse_args(argv)
    print('Public homepage:',publish(args.output_dir))
    return 0


if __name__=='__main__':raise SystemExit(main())
