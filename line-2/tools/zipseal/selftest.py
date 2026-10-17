#!/usr/bin/env python3
"""Adversarial checks for strict ZIP layout plus inherited extraction."""
import hashlib
import io
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

from demo import insert_gap
from zipseal import Rejected, gate_process, layout, process


class NoSeek(io.BytesIO):
    def seek(self, *args):
        raise OSError('nonseekable writer')


class SealTests(unittest.TestCase):
    def setUp(self):
        scratch = Path('test/scratch')
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='zipseal-test-', dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name)

    def archive(self, names=('alpha.txt', 'nested/beta.txt'), compression=zipfile.ZIP_DEFLATED):
        path = self.area / 'archive.zip'
        with zipfile.ZipFile(path, 'w', compression=compression) as writer:
            for name in names:
                writer.writestr(name, (name+'\n').encode())
            writer.comment = b'comment'
        return path

    def refusal(self, data, message):
        path = self.area / 'bad.zip'
        path.write_bytes(data)
        output = self.area / 'output'
        with self.assertRaisesRegex(Rejected, message):
            process(path, output)
        self.assertFalse(output.exists())

    def test_extract_and_account_for_all_bytes(self):
        path = self.archive()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        output = self.area / 'output'
        report = process(path, output, expected_sha256=digest)
        self.assertEqual((output / 'nested/beta.txt').read_bytes(), b'nested/beta.txt\n')
        counts = report['layout']
        self.assertEqual(counts['local_records'], 2)
        self.assertEqual(sum(counts[key] for key in ('local_header_bytes',
            'compressed_payload_bytes', 'descriptor_bytes', 'directory_bytes',
            'end_record_bytes')), path.stat().st_size)

    def test_stored_and_empty_archive(self):
        self.assertEqual(process(self.archive(compression=zipfile.ZIP_STORED))['total_bytes'], 26)
        path = self.area / 'empty.zip'
        with zipfile.ZipFile(path, 'w'):
            pass
        report = process(path)
        self.assertEqual(report['layout']['local_records'], 0)

    def test_unclaimed_gap_with_adjusted_end_offset(self):
        data = insert_gap(self.archive().read_bytes())
        path = self.area / 'gap.zip'
        path.write_bytes(data)
        self.assertTrue(gate_process(path)['ok'])
        self.refusal(data, 'unclaimed bytes')

    def test_prefix(self):
        data = self.archive().read_bytes()
        self.refusal(b'MZ'+data, 'noncontiguous directory|prefix|gap')

    def test_local_name_mismatch(self):
        data = bytearray(self.archive().read_bytes())
        data[30] ^= 1
        self.refusal(data, 'headers disagree')

    def test_local_crc_mismatch(self):
        data = bytearray(self.archive().read_bytes())
        data[14] ^= 1
        self.refusal(data, 'sizes or CRC disagree')

    def test_duplicate_local_offset(self):
        data = bytearray(self.archive().read_bytes())
        cd = struct.unpack_from('<I', data, data.rfind(b'PK\x05\x06')+16)[0]
        name_len, extra_len, comment_len = struct.unpack_from('<HHH', data, cd+28)
        second = cd+46+name_len+extra_len+comment_len
        struct.pack_into('<I', data, second+42, 0)
        self.refusal(data, 'gap or overlap')

    def test_unsigned_data_descriptor(self):
        buffer = NoSeek()
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as writer:
            writer.writestr('payload.txt', b'valid payload')
        data = buffer.getvalue()
        self.assertEqual(layout(data)['descriptor_bytes'], 16)
        path = self.area / 'descriptor.zip'
        path.write_bytes(data)
        self.assertEqual(process(path)['total_bytes'], 13)

    def test_descriptor_without_signature(self):
        buffer = NoSeek()
        with zipfile.ZipFile(buffer, 'w') as writer:
            writer.writestr('one.txt', b'one')
        data = bytearray(buffer.getvalue())
        marker = data.find(b'PK\x07\x08')
        self.assertGreater(marker, 0)
        del data[marker:marker+4]
        end = data.rfind(b'PK\x05\x06')
        struct.pack_into('<I', data, end+16, struct.unpack_from('<I', data, end+16)[0]-4)
        self.assertEqual(layout(data)['descriptor_bytes'], 12)

    def test_payload_corruption_is_still_checked(self):
        data = bytearray(self.archive(compression=zipfile.ZIP_STORED).read_bytes())
        data[39] ^= 1
        path = self.area / 'bad.zip'
        path.write_bytes(data)
        with self.assertRaises((zipfile.BadZipFile, Rejected)):
            process(path, self.area / 'output')
        self.assertFalse((self.area / 'output').exists())

    def test_digest_and_budget(self):
        path = self.archive()
        with self.assertRaisesRegex(Rejected, 'approved digest'):
            process(path, expected_sha256='0'*64)
        with self.assertRaisesRegex(Rejected, 'archive byte limit'):
            process(path, archive_bytes=path.stat().st_size-1)

    def test_cancelled_before_output(self):
        path = self.archive()
        with self.assertRaisesRegex(Rejected, 'cancelled'):
            process(path, self.area / 'output', cancelled=lambda: True)
        self.assertFalse((self.area / 'output').exists())


if __name__ == '__main__':
    unittest.main()
