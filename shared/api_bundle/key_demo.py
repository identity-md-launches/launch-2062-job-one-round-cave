#!/usr/bin/env python3
"""Inspect key-policy changes in strictly accounted, approved ZIP snapshots."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import zipfile

import api_bundle


def documents():
    capture = Path(__file__).with_name('imd-openapi.json').read_bytes()
    old = json.loads(capture)
    old['openapi'] = '3.1.0'
    old.setdefault('components', {}).setdefault('schemas', {})['HandoffKeys'] = {
        'enum': ['pending', 'done']}
    old['paths']['/requests/quote']['post']['responses'] = {
        '200': {'description': 'Illustrative key policy', 'content': {
            'application/json': {'schema': {'type': 'object', 'propertyNames': {
                '$ref': '#/components/schemas/HandoffKeys'}}}}}}
    new = copy.deepcopy(old)
    new['components']['schemas']['HandoffKeys']['enum'].append('retry')
    return capture, old, new


def insert_gap(raw):
    end = raw.rfind(b'PK\x05\x06')
    directory = struct.unpack_from('<I', raw, end + 16)[0]
    gap = b'UNCLAIMED'
    result = bytearray(raw[:directory] + gap + raw[directory:])
    struct.pack_into('<I', result, end + len(gap) + 16, directory + len(gap))
    return bytes(result)


def demo():
    capture, old, new = documents()
    scratch = Path('test/scratch')
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='key-bundle-', dir=scratch) as temporary:
        area = Path(temporary)
        paths, hashes = [], []
        for name, document in (('old', old), ('new', new)):
            path = area / (name + '.zip')
            with zipfile.ZipFile(path, 'w') as writer:
                writer.writestr(zipfile.ZipInfo('docs/openapi.json'), json.dumps(document))
            paths.append(path)
            hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
        options = dict(member='docs/openapi.json', old_sha256=hashes[0],
                       new_sha256=hashes[1], strict_layout=True)
        earlier = api_bundle.compare(*paths, maps=True, **options)
        changed = api_bundle.compare(*paths, keys=True, **options)
        unchanged = api_bundle.compare(paths[0], paths[0], keys=True,
            **{**options, 'new_sha256': hashes[0]})
        assert earlier['status'] == 'review_required'
        assert changed['status'] == 'breaking'
        assert any(f['code'] == 'property_names_incompatible' for f in changed['findings'])
        assert unchanged['status'] == 'no_detected_breakage'
        bad = area / 'gap.zip'
        bad.write_bytes(insert_gap(paths[0].read_bytes()))
        digest = hashlib.sha256(bad.read_bytes()).hexdigest()
        # Approval binds bytes; structural accounting is a separate check.
        api_bundle.compare(bad, bad, keys=True, member=options['member'],
                           old_sha256=digest, new_sha256=digest)
        try:
            api_bundle.compare(bad, bad, keys=True, strict_layout=True,
                member=options['member'], old_sha256=digest, new_sha256=digest)
        except ValueError as error:
            refusal = str(error)
        else:
            raise AssertionError('unclaimed ZIP gap was accepted')
        assert len(list(area.iterdir())) == 3
        return dict(baseline_source='https://api.imd.fun/openapi.json',
            capture_sha256=hashlib.sha256(capture).hexdigest(),
            trial='Hypothetical OpenAPI 3.1 response key enum expands behind an unchanged local reference.',
            network_used=False, extracted_files=0,
            previous_mode=earlier['status'], unchanged=unchanged['status'],
            approved_gap_refused=refusal, changed=changed)


if __name__ == '__main__':
    print(json.dumps(demo(), indent=2))
