"""Publish the explicitly labeled Dirt Jump DEMO as static assets, never source."""
from pathlib import Path

from explore.demo import fixture
from explore.view import render

PUBLIC_FOLDER = 'discover'
DEMO_SCOPE = 'mtb-dirt-jump'


def publish_demo(output):
    output = Path(output)
    targets = [output / PUBLIC_FOLDER, output / PUBLIC_FOLDER / DEMO_SCOPE,
               output / PUBLIC_FOLDER / 'view.js', output / PUBLIC_FOLDER / DEMO_SCOPE / 'index.html']
    if any(path.is_symlink() for path in targets):
        raise ValueError('Public demo output must not contain symlinks')
    folder = output / PUBLIC_FOLDER
    (folder / DEMO_SCOPE).mkdir(parents=True, exist_ok=True)
    scope, state = fixture('mtb')
    scope['id'] = DEMO_SCOPE
    # Clear fixture scan claims: this is a demo, not verified retailer coverage.
    state.update(scope=DEMO_SCOPE, last_success=None, attempted_at=None, history={}, manifest=[], metrics={})
    (folder / 'view.js').write_text(Path(__file__).with_name('view.js').read_text(), encoding='utf-8')
    (folder / DEMO_SCOPE / 'index.html').write_text(render(scope, state), encoding='utf-8')
    return {'id': DEMO_SCOPE, 'sport': 'mtb', 'catalog': PUBLIC_FOLDER + '/' + DEMO_SCOPE + '/index.html', 'demo': True}
