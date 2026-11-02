"""Build the issue #122 native-page header preview; never modifies the live site."""
import argparse
import hashlib
from html import escape
import json
from pathlib import Path
import re
import shutil

from previews.shreddeals import SOURCE, HERE


def inject_header(html, config):
    """Engine integration seam: inline these assets/config after existing page assets.

    This only enhances existing DOM nodes. It does not render products or bind
    section/alerts actions, and it has no iframe or engine dependency.
    """
    payload = json.dumps(config).replace('<', '\\u003c')
    return html.replace('</head>',
        '<style>' + (HERE / 'unified-header.css').read_text() + '</style>'
        '<script type="application/json" id="shredHeaderConfig">' + payload + '</script>'
        '<script>' + (HERE / 'unified-header.js').read_text() + '</script></head>', 1)


def inert(html):
    """Preview only: preserve the existing alerts panel in its offline state."""
    html = re.sub(r'<script>window\.SKATEDEALS_ALERTS = .*?</script>', '', html, flags=re.S)
    html = re.sub(r'<!-- Cloudflare Web Analytics -->.*?<!-- End Cloudflare Web Analytics -->', '', html, flags=re.S)
    html = re.sub(r'<script\b[^>]*src=["\']https://static\.cloudflareinsights\.com/[^>]*>\s*</script>', '', html, flags=re.I)
    policy = '<meta http-equiv="Content-Security-Policy" content="connect-src &apos;self&apos;; form-action &apos;none&apos;; frame-src &apos;none&apos;; object-src &apos;none&apos;">'
    return html.replace('</head>', policy + '<meta name="robots" content="noindex,nofollow"></head>', 1)


def build(output, source=SOURCE):
    output = Path(output).absolute()
    source = Path(source).resolve()
    if output.exists() or output.is_symlink():
        raise ValueError('Use a new output directory')
    output = output.resolve()
    if output.is_relative_to(SOURCE) or output.is_relative_to(source):
        raise ValueError('Preview output must be outside the checkout/input directory')
    # Read names/order only. Claude owns the sport engine/configuration; this
    # preview does not invent the final output paths or change his configuration.
    source_config = json.loads((HERE / 'sports.json').read_text())
    # Sports with a live catalog (Claude's engine: <id>/sale_items_chart.html
    # with listings) use their real page; the rest get a placeholder.
    import sports as engine
    live = engine.published_catalogs(source)
    sports = []
    for sport in source_config['sports']:
        if not re.fullmatch('[a-z][a-z0-9-]*', sport['id']):
            raise ValueError('Invalid sport ID')
        if sport['id'] != 'skate' and sport.get('catalog'):
            raise ValueError('A new catalog is configured; integrate its engine output explicitly first')
        href = 'index.html' if sport['id'] == 'skate' else live.get(sport['id']) or sport['id'] + '.html'
        sports.append({'id': sport['id'], 'label': sport['label'], 'href': href})
    skate = next(s for s in sports if s['id'] == 'skate')
    skate['aliases'] = ['./', 'sale_items_chart.html']
    html = (source / 'sale_items_chart.html').read_text()
    if 'id="stickyBar"' not in html or 'id="homeReset"' not in html:
        raise ValueError('Saved page needs the existing Skate header')
    output.mkdir(parents=True)

    def config_for(sport):
        """Links relative to this page: a bmx/ page reaches ../index.html."""
        up = '../' * sport['href'].count('/')
        return {'brand': 'ShredDeals', 'currentSport': sport['id'],
                'sports': [dict(other, href=up + other['href'],
                                **({'aliases': [up + alias for alias in other['aliases']]} if other.get('aliases') else {}))
                           for other in sports]}

    for sport in sports:
        config = config_for(sport)
        if sport['id'] == 'skate':
            rendered = inert(html)
        elif sport['id'] in live:
            page = source / sport['href']
            rendered = inert(page.read_text())
            (output / sport['href']).parent.mkdir(parents=True, exist_ok=True)
            history = page.parent / 'history.json'
            if history.is_file():
                shutil.copyfile(history, output / sport['href'].rsplit('/', 1)[0] / 'history.json')
        else:
            label = escape(sport['label'])
            # Reuse the source's base styles, without any catalog or app scripts.
            styles = ''.join(re.findall(r'<style\b[^>]*>.*?</style>', html, flags=re.S))
            rendered = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ShredDeals — {label}</title>{styles}</head>
<body><header id="stickyBar"><div class="topnav"><h1 class="brand"><button class="brand-home" id="homeReset" type="button" onclick="location.href='index.html'">ShredDeals</button></h1>
<div class="topnav-links" role="group" aria-label="Sections"><a class="nav-link" href="#comingSoon">Deals</a><button class="nav-link" disabled title="No catalog yet">Track</button><button class="nav-link" disabled title="No catalog yet">Insights</button><button class="nav-link" disabled title="Subscriptions are not available for this sport">Subscribe</button></div></div></header>
<main id="comingSoon" class="shred-empty"><h1>{label} deals</h1><p>Coming soon / no catalog yet</p><p>We’re adding {label} retailers. There are no {label} products or alerts here yet.</p><a href="index.html">Browse Skate deals</a></main></body></html>'''
            rendered = inert(rendered)
        rendered = inject_header(rendered, config)
        rendered = rendered.replace('</body>', '<p style="position:fixed;bottom:0;right:0;z-index:1000;margin:0;padding:3px 8px;background:#78350f;color:white;font:11px system-ui">HEADER PREVIEW · alerts and analytics off</p></body>', 1)
        (output / sport['href']).write_text(rendered)
    shutil.copyfile(source / 'history.json', output / 'history.json')
    # Native standalone alias tests the same shared header without the old shell.
    alias_config = {'brand': 'ShredDeals', 'currentSport': 'skate', 'sports': sports}
    (output / 'sale_items_chart.html').write_text(inject_header(inert(html), alias_config))
    (output / 'manifest.json').write_text(json.dumps({
        'development_only': True, 'native_pages': True, 'sports': sports,
        'source_page_sha256': hashlib.sha256((source / 'sale_items_chart.html').read_bytes()).hexdigest(),
        'source_history_sha256': hashlib.sha256((source / 'history.json').read_bytes()).hexdigest(),
    }, indent=2) + '\n')
    return output / 'index.html'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--source-dir', type=Path, default=SOURCE)
    args = parser.parse_args(argv)
    print('Preview HTML:', build(args.output_dir, args.source_dir))
    print('Serve its directory with python -m http.server; no scraper or email runs.')


if __name__ == '__main__':
    main()
