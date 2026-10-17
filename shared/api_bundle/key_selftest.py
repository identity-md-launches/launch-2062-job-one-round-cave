#!/usr/bin/env python3
"""Cross-line integration tests for strict ZIP records and object-key checks."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

import api_bundle as bundle
from key_demo import documents, insert_gap


class KeyBundleTests(unittest.TestCase):
    def setUp(self):
        scratch = Path('test/scratch')
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='key-tests-', dir=scratch)
        self.root = Path(self.temp.name)
        _, self.old, self.new = documents()

    def tearDown(self):
        self.temp.cleanup()

    def archive(self, name, doc):
        path = self.root / name
        with zipfile.ZipFile(path, 'w') as writer:
            writer.writestr(zipfile.ZipInfo('docs/openapi.json'), json.dumps(doc))
            writer.writestr(zipfile.ZipInfo('unselected.txt'), b'inert payload')
            writer.comment = b'permitted envelope comment'
        return path

    def pair(self, old=None, new=None):
        a = self.archive('old.zip', self.old if old is None else old)
        b = self.archive('new.zip', self.new if new is None else new)
        return a, b, dict(member='docs/openapi.json', strict_layout=True,
            old_sha256=self.digest(a), new_sha256=self.digest(b))

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_reference_change_retains_previous_findings(self):
        a, b, options = self.pair()
        prior = bundle.compare(a, b, maps=True, **options)
        result = bundle.compare(a, b, keys=True, **options)
        self.assertEqual(prior['status'], 'review_required')
        self.assertEqual(result['status'], 'breaking')
        self.assertEqual(result['key_pairs'][0]['direction'], 'response')
        self.assertTrue(all(f in result['findings'] for f in prior['findings']))
        self.assertIn('property_names_incompatible', {f['code'] for f in result['findings']})
        for side, path in zip(result['bundle_inputs'].values(), (a, b)):
            self.assertTrue(side['strict_layout_checked'])
            self.assertTrue(side['approved_sha256_checked'])
            self.assertTrue(side['all_payloads_crc_checked'])
            layout = side['layout']
            self.assertEqual(sum(layout[k] for k in ('local_header_bytes',
                'compressed_payload_bytes', 'descriptor_bytes', 'directory_bytes',
                'end_record_bytes')), path.stat().st_size)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['new.zip', 'old.zip'])

    def test_unchanged_capture_and_independent_flags(self):
        capture = json.loads(Path(__file__).with_name('imd-openapi.json').read_bytes())
        a, b, options = self.pair(capture, capture)
        result = bundle.compare(a, b, keys=True, **options)
        self.assertEqual(result['status'], 'no_detected_breakage')
        self.assertEqual(result['operations_compared'], 5)
        self.assertEqual(result['key_pairs'], [])
        maps = bundle.compare(a, b, maps=True, **options)
        self.assertTrue(maps['extension'].startswith('mapcheck-v1'))
        loose = bundle.compare(a, b, keys=True, **{**options, 'strict_layout': False})
        self.assertNotIn('layout', loose['bundle_inputs']['old'])
        self.assertEqual(result['findings'], loose['findings'])

    def test_approved_gap_refused_before_zip_parser(self):
        a, b, options = self.pair()
        b.write_bytes(insert_gap(b.read_bytes()))
        options['new_sha256'] = self.digest(b)
        loose = bundle.compare(a, b, keys=True, **{**options, 'strict_layout': False})
        self.assertEqual(loose['status'], 'breaking')
        # The second snapshot is refused before constructing its ZipFile.
        with mock.patch.object(bundle.zipfile, 'ZipFile', wraps=zipfile.ZipFile) as parser:
            with mock.patch.object(bundle.keycheck, 'compare') as analyzer:
                with self.assertRaisesRegex(ValueError, 'unclaimed bytes'):
                    bundle.compare(a, b, keys=True, **options)
                self.assertEqual(parser.call_count, 1)
                analyzer.assert_not_called()

    def test_approval_precedes_layout(self):
        a, b, options = self.pair()
        with mock.patch.object(bundle.zipseal, 'layout') as layout:
            with self.assertRaisesRegex(ValueError, 'approved digest'):
                bundle.compare(a, b, keys=True, **{**options, 'old_sha256': '0' * 64})
            layout.assert_not_called()

    def test_local_header_mismatch_refused(self):
        a, b, options = self.pair()
        raw = bytearray(b.read_bytes())
        raw[30] ^= 1  # Local filename, central directory unchanged.
        b.write_bytes(raw)
        with mock.patch.object(bundle.keycheck, 'compare') as analyzer:
            with self.assertRaisesRegex(ValueError, 'headers disagree'):
                bundle.compare(a, b, keys=True, **{**options, 'new_sha256': self.digest(b)})
            analyzer.assert_not_called()

    def test_crc_of_omitted_payload_checked_before_analysis(self):
        a, b, options = self.pair()
        b.write_bytes(b.read_bytes().replace(b'inert payload', b'INERT PAYLOAD'))
        with mock.patch.object(bundle.keycheck, 'compare') as analyzer:
            with self.assertRaises(zipfile.BadZipFile):
                bundle.compare(a, b, keys=True, **{**options, 'new_sha256': self.digest(b)})
            analyzer.assert_not_called()

    def test_request_direction_and_older_dialect(self):
        old, new = copy.deepcopy(self.new), copy.deepcopy(self.old)
        for doc in (old, new):
            op = doc['paths']['/requests/quote']['post']
            op['requestBody'] = op['responses']['200']
            op['responses'] = {}
            # Isolate the hypothetical operation before changing dialect; the
            # real 3.1 capture has numeric exclusive bounds invalid in 3.0.
            doc['paths'] = {'/requests/quote': {'post': op}}
        a, b, options = self.pair(old, new)
        result = bundle.compare(a, b, keys=True, **options)
        self.assertEqual(result['status'], 'breaking')
        self.assertEqual(result['key_pairs'][0]['direction'], 'request')
        for doc in (old, new):
            doc['openapi'] = '3.0.3'
        a, b, options = self.pair(old, new)
        result = bundle.compare(a, b, keys=True, **options)
        codes = {f['code'] for f in result['findings']}
        self.assertIn('property_names_dialect_unchecked', codes)
        self.assertNotIn('property_names_incompatible', codes)

    def test_unsupported_unchanged_pattern_stays_review(self):
        old = copy.deepcopy(self.old)
        old['components']['schemas']['HandoffKeys'] = {'pattern': '^p'}
        a, b, options = self.pair(old, old)
        result = bundle.compare(a, b, keys=True, **options)
        self.assertEqual(result['status'], 'review_required')
        self.assertIn('property_name_constraints_unchecked', {f['code'] for f in result['findings']})

    def test_remote_policy_and_key_budget_refuse(self):
        old = copy.deepcopy(self.old)
        old['components']['schemas']['HandoffKeys'] = {'$ref': 'https://example.invalid/key'}
        a, b, options = self.pair(old, old)
        with self.assertRaises(ValueError):
            bundle.compare(a, b, keys=True, **options)
        a, b, options = self.pair()
        with mock.patch.object(bundle.keycheck, 'MAX_KEY_PAIRS', 0):
            with self.assertRaisesRegex(ValueError, 'pair limit'):
                bundle.compare(a, b, keys=True, **options)

    def test_cancellation_and_archive_budget_precede_analysis(self):
        a, b, options = self.pair()
        with mock.patch.object(bundle.keycheck, 'compare') as analyzer:
            for extra in ({'cancelled': lambda: True}, {'directory_bytes': 1}, {'nodes': 1}):
                with self.assertRaises(ValueError):
                    bundle.compare(a, b, keys=True, **options, **extra)
            analyzer.assert_not_called()
        for name in ('keys', 'strict_layout'):
            with self.assertRaisesRegex(ValueError, 'booleans'):
                bundle.compare(a, b, **{name: 1})

    def test_cli_exits_and_precedence(self):
        a, _, _ = self.pair(self.old, self.old)
        review = copy.deepcopy(self.old)
        review['components']['schemas']['HandoffKeys']['pattern'] = '^p'
        for document, expected in ((self.old, 0), (self.new, 1), ({}, 2), (review, 3)):
            b = self.archive('new.zip', document)
            command = [sys.executable, '-B', bundle.__file__, str(a), str(b),
                '--member', 'docs/openapi.json', '--keys', '--maps', '--dispatch',
                '--strict-layout', '--old-sha256', self.digest(a), '--new-sha256', self.digest(b)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
            if expected != 2:
                self.assertTrue(json.loads(result.stdout)['extension'].startswith('keycheck-v1'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
