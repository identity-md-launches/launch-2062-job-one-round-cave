#!/usr/bin/env python3
"""Compare saved real public descriptions through strict approved ZIP snapshots."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'shared/api_bundle'))
import api_bundle


def main():
    scratch = ROOT / 'test/scratch'
    scratch.mkdir(parents=True, exist_ok=True)
    sources = [ROOT / 'shared/api_bundle/imd-openapi.json',
               ROOT / 'gathering/imd-openapi-current-38.json']
    with tempfile.TemporaryDirectory(prefix='public38-', dir=scratch) as temporary:
        paths, hashes = [], []
        for index, source in enumerate(sources):
            path = Path(temporary) / f'{index}.zip'
            with zipfile.ZipFile(path, 'w') as writer:
                writer.writestr(zipfile.ZipInfo('openapi.json'), source.read_bytes())
            paths.append(path)
            hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
        result = api_bundle.compare(*paths, old_sha256=hashes[0], new_sha256=hashes[1],
                                    keys=True, strict_layout=True, seconds=10)
    (ROOT / 'gathering/shared-live-38.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'operations': result['operations_compared'],
                      'findings': len(result['findings']), 'key_pairs': len(result['key_pairs'])}))


if __name__ == '__main__':
    main()
