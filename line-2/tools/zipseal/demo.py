#!/usr/bin/env python3
"""Offline real-public-capture replay and unclaimed-byte refusal."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import zipfile

from zipseal import Rejected, gate_process, process


def insert_gap(data, gap=b'UNCLAIMED'):
    """Keep a ZIP parseable while inserting unused bytes before its directory."""
    end = data.rfind(b'PK\x05\x06')
    offset = struct.unpack_from('<I', data, end+16)[0]
    changed = bytearray(data[:offset] + gap + data[offset:])
    struct.pack_into('<I', changed, end+len(gap)+16, offset+len(gap))
    return bytes(changed)


def main():
    root = Path(__file__).resolve().parents[1]
    source = root / 'safezip' / 'imd-openapi.json'
    provenance = json.loads((root / 'safezip' / 'sample-source.json').read_text())
    payload = source.read_bytes()
    assert len(payload) == provenance['bytes']
    assert hashlib.sha256(payload).hexdigest() == provenance['sha256']
    scratch = Path('test/scratch')
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='zipseal-', dir=scratch) as temporary:
        area = Path(temporary)
        archive = area / 'approved.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as writer:
            writer.writestr('docs/imd/openapi.json', payload)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        output = area / 'extracted'
        accepted = process(archive, output, expected_sha256=digest,
                           total_bytes=len(payload), file_bytes=len(payload))
        assert (output / 'docs/imd/openapi.json').read_bytes() == payload
        bad = area / 'hidden.zip'
        bad.write_bytes(insert_gap(archive.read_bytes()))
        inherited_gate_accepted = gate_process(bad)['ok']
        assert inherited_gate_accepted
        refused = False
        try:
            process(bad, area / 'must-not-exist')
        except Rejected as error:
            refused = 'unclaimed bytes' in str(error)
        assert refused and not (area / 'must-not-exist').exists()
    print(json.dumps({'ok': True, 'source_sha256': provenance['sha256'],
                      'source_bytes': len(payload), 'archive_sha256': digest,
                      'extracted_bytes': accepted['total_bytes'],
                      'local_records': accepted['layout']['local_records'],
                      'inherited_gate_accepted_gap': inherited_gate_accepted,
                      'unclaimed_gap_refused': refused,
                      'no_output_on_refusal': True}, indent=2))


if __name__ == '__main__':
    main()
