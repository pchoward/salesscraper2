"""Generate the public ShredDeals homepage/assets without scraping or delivery."""
import argparse
from pathlib import Path
import shutil

from previews.shreddeals import HERE, SOURCE, load_config, render_shell, skate_query_keys


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
    (output/'index.html').write_text(render_shell(config,asset_prefix='navigation/'))
    return output/'index.html'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=SOURCE)
    args=parser.parse_args(argv)
    print('Public homepage:',publish(args.output_dir))
    return 0


if __name__=='__main__':raise SystemExit(main())
