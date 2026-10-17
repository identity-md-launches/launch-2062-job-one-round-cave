#!/usr/bin/env python3
"""Check every classic ZIP byte has a structural place before bounded extraction."""
import argparse
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import sys
import time
import zipfile
import zlib

from .safezip import Rejected, local_path
from .zipgate import directory_gate, positive, process as gate_process


def _extra(data, start, length):
    end = start + length
    while start < end:
        if start + 4 > end:
            raise Rejected('truncated local extra field')
        tag, size = struct.unpack_from('<HH', data, start)
        start += 4
        if tag == 1:
            raise Rejected('ZIP64 local extra field not supported')
        if start + size > end:
            raise Rejected('local extra field crosses its boundary')
        start += size


def layout(data, *, entries=1000, directory_bytes=2097152,
           checkpoint=lambda: None):
    """Require exact, nonoverlapping local records from byte zero to the directory.

    This is a structural gate. ZipGate/SafeZip still validate paths, file types,
    decompressed bytes, CRCs and resource limits before publication.
    """
    gate = directory_gate(data, entries=entries, directory_bytes=directory_bytes,
                          checkpoint=checkpoint)
    end = data.rfind(b'PK\x05\x06', max(0, len(data) - 65557))
    _, _, _, _, count, size, cd_start, comment = struct.unpack_from('<4s4H2IH', data, end)
    cursor = cd_start
    records = []
    for _ in range(count):
        checkpoint()
        fields = struct.unpack_from('<4s6H3I5H2I', data, cursor)
        flags, method, crc, compressed, uncompressed = (fields[3], fields[4],
                                                          fields[7], fields[8], fields[9])
        name_len, extra_len, comment_len, local_at = (fields[10], fields[11],
                                                       fields[12], fields[16])
        name = data[cursor+46:cursor+46+name_len]
        records.append((local_at, flags, method, crc, compressed, uncompressed, name))
        cursor += 46 + name_len + extra_len + comment_len
    if cursor != end or cd_start + size != end or end + 22 + comment != len(data):
        raise Rejected('central directory or end record has unclaimed bytes')

    records.sort(key=lambda record: record[0])
    next_start = 0
    header_bytes = payload_bytes = descriptor_bytes = 0
    for index, (start, flags, method, crc, compressed, uncompressed, name) in enumerate(records):
        checkpoint()
        if start != next_start:
            raise Rejected('gap or overlap among local ZIP records')
        if start + 30 > cd_start or data[start:start+4] != b'PK\x03\x04':
            raise Rejected('missing or truncated local file header')
        local = struct.unpack_from('<4s5H3I2H', data, start)
        local_flags, local_method = local[2:4]
        local_crc, local_compressed, local_uncompressed = local[6:9]
        local_name_len, local_extra_len = local[9:11]
        payload_at = start + 30 + local_name_len + local_extra_len
        payload_end = payload_at + compressed
        following = records[index+1][0] if index+1 < len(records) else cd_start
        if following <= start:
            raise Rejected('gap or overlap among local ZIP records')
        if payload_end > following or payload_at > cd_start:
            raise Rejected('local payload crosses next record or directory')
        if (local_flags != flags or local_method != method
                or local_name_len != len(name)
                or data[start+30:start+30+local_name_len] != name):
            raise Rejected('local and central ZIP headers disagree')
        _extra(data, start+30+local_name_len, local_extra_len)
        if flags & 8:
            if (local_crc not in (0, crc) or local_compressed not in (0, compressed)
                    or local_uncompressed not in (0, uncompressed)):
                raise Rejected('local data-descriptor placeholders disagree')
            descriptor_len = following - payload_end
            if descriptor_len not in (12, 16):
                raise Rejected('missing or extra data-descriptor bytes')
            descriptor_at = payload_end
            if descriptor_len == 16:
                if data[descriptor_at:descriptor_at+4] != b'PK\x07\x08':
                    raise Rejected('data-descriptor signature mismatch')
                descriptor_at += 4
            if struct.unpack_from('<III', data, descriptor_at) != (crc, compressed, uncompressed):
                raise Rejected('data descriptor disagrees with central directory')
        else:
            if (local_crc, local_compressed, local_uncompressed) != (crc, compressed, uncompressed):
                raise Rejected('local sizes or CRC disagree with central directory')
            descriptor_len = 0
            if payload_end != following:
                raise Rejected('unclaimed bytes after local payload')
        header_bytes += payload_at - start
        payload_bytes += compressed
        descriptor_bytes += descriptor_len
        next_start = following
    if next_start != cd_start:
        raise Rejected('unclaimed bytes before central directory')
    gate.update({'local_records': len(records), 'local_header_bytes': header_bytes,
                 'compressed_payload_bytes': payload_bytes,
                 'descriptor_bytes': descriptor_bytes, 'end_record_bytes': len(data)-end})
    return gate


def process(archive_path, output=None, *, entries=1000, directory_bytes=2097152,
            archive_bytes=33554432, nodes=32000, file_bytes=16777216,
            total_bytes=67108864, ratio=200, expected_sha256=None,
            seconds=None, cancelled=None):
    for name, value in [('entries', entries), ('directory_bytes', directory_bytes),
                        ('archive_bytes', archive_bytes), ('nodes', nodes),
                        ('file_bytes', file_bytes), ('total_bytes', total_bytes),
                        ('ratio', ratio)]:
        positive(name, value)
    if expected_sha256 is not None and (not isinstance(expected_sha256, str)
            or re.fullmatch(r'[0-9a-fA-F]{64}', expected_sha256) is None):
        raise Rejected('expected SHA-256 must be exactly 64 hexadecimal characters')
    if seconds is not None and (isinstance(seconds, bool) or not isinstance(seconds, (int, float))
                                or not math.isfinite(seconds) or seconds <= 0):
        raise Rejected('seconds must be a finite positive number')
    if cancelled is not None and not callable(cancelled):
        raise Rejected('cancelled must be callable')
    started = time.monotonic()

    def checkpoint():
        if cancelled is not None and cancelled():
            raise Rejected('operation cancelled')
        if seconds is not None and time.monotonic() - started >= seconds:
            raise Rejected('operation time budget exceeded')
        return False

    checkpoint()
    source = local_path(archive_path)
    if not source.is_file() or source.stat().st_size > archive_bytes:
        raise Rejected('archive missing, nonregular, or over archive byte limit')
    if output is not None:
        target = local_path(output)
        if target.exists() or target.is_symlink() or not target.parent.is_dir():
            raise Rejected('output exists or its parent is missing')
    data = bytearray()
    digest = hashlib.sha256()
    with source.open('rb') as reader:
        if not stat.S_ISREG(os.fstat(reader.fileno()).st_mode):
            raise Rejected('archive must be regular')
        while True:
            checkpoint()
            chunk = reader.read(min(65536, archive_bytes-len(data)+1))
            if not chunk:
                break
            if len(data)+len(chunk) > archive_bytes:
                raise Rejected('archive byte limit exceeded while reading')
            data.extend(chunk)
            digest.update(chunk)
    approved = digest.hexdigest()
    if expected_sha256 is not None and not hmac.compare_digest(approved, expected_sha256.lower()):
        raise Rejected('archive SHA-256 differs from approved digest')
    checked_layout = layout(data, entries=entries, directory_bytes=directory_bytes,
                            checkpoint=checkpoint)
    checked_layout['archive_bytes'] = len(data)
    del data
    checkpoint()
    report = gate_process(source, output, entries=entries,
                          directory_bytes=directory_bytes, archive_bytes=archive_bytes,
                          nodes=nodes, file_bytes=file_bytes, total_bytes=total_bytes,
                          ratio=ratio, expected_sha256=approved, cancelled=checkpoint)
    report['layout'] = checked_layout
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('inspect', 'extract'))
    parser.add_argument('archive')
    parser.add_argument('output', nargs='?')
    parser.add_argument('--sha256', dest='expected_sha256')
    for flag, default in [('entries', 1000), ('directory-bytes', 2097152),
                          ('archive-bytes', 33554432), ('nodes', 32000),
                          ('file-bytes', 16777216), ('total-bytes', 67108864),
                          ('ratio', 200)]:
        parser.add_argument('--'+flag, type=int, default=default)
    parser.add_argument('--seconds', type=float)
    args = vars(parser.parse_args())
    command, archive, output = args.pop('command'), args.pop('archive'), args.pop('output')
    if (command == 'extract') != (output is not None):
        parser.error('extract requires output; inspect takes no output')
    try:
        report = process(archive, output, **args)
    except (ValueError, OSError, zipfile.BadZipFile, NotImplementedError,
            RuntimeError, EOFError, zlib.error) as error:
        print(json.dumps({'ok': False, 'error': str(error)}))
        return 2
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
