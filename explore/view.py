"""Explore demo/review pages sharing the catalog's compact styles and bridge."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def render(scope, state):
    css = (ROOT / 'page.css').read_text() + '\n' + (Path(__file__).with_name('view.css')).read_text()
    payload = json.dumps({'scope': scope, 'state': state}).replace('<', '\\u003c')
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>ShredDeals · Explore DEMO</title><style>''' + css + '''</style>
<script src="../../navigation/skate-bridge.js" defer></script><script src="../view.js" defer></script></head>
<body><nav class="topnav"><strong>ShredDeals</strong><div class="topnav-links"><button id="navDeals">Deals</button><button id="navExplore" aria-pressed="true">Explore</button></div></nav>
<div class="preview-note">DEMO / SAMPLE PRODUCTS · not real inventory · not available to buy</div>
<main><h1>''' + html.escape(scope['label']) + '''</h1><p id="coverage"></p>
<form id="filters" class="explore-tools"><label>Category<select id="category"></select></label><label>Store<select id="store"></select></label><label>Brand<select id="brand"></select></label>
<label class="search">Search<input id="query" type="search" placeholder="Search inventory…"></label><label>Size<select id="size"></select></label><label>Price type<select id="sale"><option value="">All prices</option><option value="sale">Discounted</option><option value="regular">Regular price</option></select></label>
<label>Sort<select id="sort"><option value="title">Title</option><option value="price">Price: low first</option></select></label><label>View<select id="view"><option value="cards">Cards</option><option value="table">Table</option></select></label><button type="reset">Clear</button></form>
<p id="count" role="status" aria-live="polite"></p><div id="inventory"></div><dialog id="quick"><button id="closeQuick" aria-label="Close quick view">Close</button><div id="quickContent"></div></dialog></main>
<script type="application/json" id="exploreData">''' + payload + '''</script></body></html>'''


def install(out, entries):
    """Called explicitly by review builds, never default publish or live scrape.

    entries: list of (scope config, scoped state). Adds mode routing to an
    existing preview shell, retaining Deals as its default destination.
    """
    out = Path(out)
    import re
    shell = (out / 'index.html').read_text()
    match = re.search(r'(<script[^>]+id="sportConfig"[^>]*>)(.*?)(</script>)', shell, re.S)
    config = json.loads(match.group(2))
    config['exploreScopes'] = []
    folder = out / 'explore'; folder.mkdir(exist_ok=True)
    for name in ('view.js', 'entry.js'):
        (folder / name).write_text(Path(__file__).with_name(name).read_text())
    for scope, state in entries:
        target = folder / scope['id']; target.mkdir(exist_ok=True)
        (target / 'index.html').write_text(render(scope, state))
        config['exploreScopes'].append({'id': scope['id'], 'sport': scope['sport'], 'catalog': 'explore/' + scope['id'] + '/index.html'})
        sport = next(item for item in config['sports'] if item['id'] == scope['sport'])
        catalog = out / sport['catalog']
        content = catalog.read_text()
        if 'explore/entry.js' not in content:
            # sport catalogs are exactly one directory below the site root.
            content = content.replace('</head>', '<script src="../explore/entry.js" defer></script></head>')
            catalog.write_text(content)
    (out / 'index.html').write_text(shell[:match.start(2)] + json.dumps(config).replace('<', '\\u003c') + shell[match.end(2):])
