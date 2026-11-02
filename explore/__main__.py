"""Explicit Explore capture; never runs from the sale scraper or scheduler."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile

from explore.engine import capture
from explore.transport import Reader


def save(path, state):
    path = Path(path)
    for _ in range(4):
        state['metrics']['serialized_bytes'] = len(json.dumps(state, sort_keys=True, separators=(',', ':')).encode()) + 1
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False, encoding='utf-8') as stream:
        temporary = Path(stream.name)
        json.dump(state, stream, sort_keys=True, separators=(',', ':'))
        stream.write('\n')
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scope')
    parser.add_argument('--config', type=Path, default=Path(__file__).with_name('scopes.json'))
    parser.add_argument('--state-dir', type=Path, required=True, help='Independent Explore state folder')
    args = parser.parse_args(argv)
    scope = json.loads(args.config.read_text())[args.scope]
    # Fixed filename, not arbitrary paths from scope/config input.
    from explore.engine import validate
    validate(scope)
    target = args.state_dir / (scope['id'] + '.json')
    previous = json.loads(target.read_text()) if target.exists() else None
    reader = Reader()
    state = capture(scope, reader, datetime.now(timezone.utc).isoformat(), previous)
    state['transport'] = {'requests': reader.requests, 'response_bytes': reader.bytes}
    save(target, state)
    print(json.dumps({'scope': scope['id'], 'stale': state['stale'], 'metrics': state['metrics'], 'manifest': state['manifest']}))
    return 1 if state['stale'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
