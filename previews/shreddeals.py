"""Build an isolated ShredDeals prototype from the existing public Skate page."""
import argparse
import ast
import hashlib
import inspect
import json
from pathlib import Path
import re
import shutil

SOURCE = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent


def load_config(path):
    config = json.loads(Path(path).read_text())
    ids = []
    for sport in config['sports']:
        sid = sport['id']
        if not re.fullmatch(r'[a-z]+', sid) or sid in ids:
            raise ValueError('Sport IDs must be unique lowercase tokens')
        ids.append(sid)
        if sid != 'skate' and sport.get('catalog'):
            raise ValueError('This prototype has a Skate catalog only')
        if sid == 'skate' and sport.get('catalog') != 'skate/sale_items_chart.html':
            raise ValueError('Skate must use the copied local catalog')
    if config.get('defaultSport') not in ids or 'skate' not in ids:
        raise ValueError('Unknown default sport or missing Skate')
    return config


def skate_query_keys():
    """Reuse the production decoder's key contract instead of maintaining a fork."""
    import query_state
    tree = ast.parse(inspect.getsource(query_state.decode_query))
    keys = set(query_state.RETIRED_VISIT_PARAMS)
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == 'key':
            keys.update(value.value for value in node.comparators if isinstance(value, ast.Constant) and isinstance(value.value, str))
    return sorted(keys)


def build(output, source=SOURCE, config_path=HERE/'sports.json'):
    source = Path(source).resolve()
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('Use a new output directory; existing paths are not overwritten')
    output = output.resolve()
    if output.is_relative_to(SOURCE) or output.is_relative_to(source):
        raise ValueError('Preview output must be outside the checkout/input directory')
    config = load_config(config_path)
    config['skateQueryKeys'] = skate_query_keys()
    page = source/'sale_items_chart.html'
    history = source/'history.json'
    html = page.read_text()
    if '<body>' not in html or not history.is_file():
        raise ValueError('Saved public page and history.json are required')
    # All current app/search/style code is inline. Fail rather than silently lose
    # future local dependencies if production changes its generated-page format.
    local_scripts = re.findall(r'<script[^>]+src=["\'](?!https?://)([^"\']+)', html, re.I)
    local_links = re.findall(r'<link[^>]+href=["\'](?!https?://|data:|#)([^"\']+)', html, re.I)
    if local_scripts or any(link.split('?', 1)[0] != 'history.json' for link in local_links):
        raise ValueError('New local asset dependencies need review before copying')
    output.mkdir(parents=True)
    (output/'skate').mkdir()
    policy = '<meta http-equiv="Content-Security-Policy" content="connect-src &apos;self&apos;; form-action &apos;none&apos;; frame-src &apos;none&apos;; script-src &apos;self&apos; &apos;unsafe-inline&apos;">'
    html = re.sub(r'<script\b[^>]*src=["\']https://static\.cloudflareinsights\.com/[^>]*>\s*</script>', '', html, flags=re.I)
    html = html.replace('<head>', '<head>'+policy+'<script src="../skate-bridge.js"></script>', 1)
    (output/'skate/sale_items_chart.html').write_text(html)
    shutil.copyfile(history, output/'skate/history.json')
    for name in ('navigation.js','navigation.css','skate-bridge.js'):
        shutil.copyfile(HERE/name, output/name)
    template = (HERE/'shell.html').read_text()
    payload = json.dumps(config).replace('<','\\u003c')
    (output/'index.html').write_text(template.replace('__CONFIG__',payload))
    manifest = {'development_only':True, 'source_page_sha256':hashlib.sha256(page.read_bytes()).hexdigest(),
                'source_history_sha256':hashlib.sha256(history.read_bytes()).hexdigest(),
                'catalogs':{'skate':'saved public catalog','bmx':None,'ski':None,'mtb':None},
                'note':'No production rendering, scraping, state updates, or delivery; only local preview files.'}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return output/'index.html'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--source-dir',type=Path,default=SOURCE)
    parser.add_argument('--config',type=Path,default=HERE/'sports.json')
    args=parser.parse_args(argv)
    try:
        preview=build(args.output_dir,args.source_dir,args.config)
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    print(f'Preview HTML: {preview}')
    print('Serve this output directory with a static HTTP server for working charts and shared URL history.')
    return 0


if __name__=='__main__':raise SystemExit(main())
