#!/usr/bin/env python3
"""Offline revision checks, including file handoff and independently derived deltas."""
import contextlib
import copy
import io
from pathlib import Path
import random
import tempfile
import unittest
import rewardrevision as rv


class RevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metadata = rv.rs.read_json(rv.rr.ROOT / 'zto-mainnet.json')
        cls.base = {'budget': '1', 'contributors': [
            {'id': 'build', 'weight': '2'}, {'id': 'review', 'weight': '1'}]}

    def sources(self, before=None, after=None):
        before = copy.deepcopy(self.base if before is None else before)
        after = copy.deepcopy(before if after is None else after)
        return [before, rv.rs.allocate(before, self.metadata),
                after, rv.rs.allocate(after, self.metadata), self.metadata]

    def test_demo_exact_expected_deltas(self):
        result = rv.demo()
        self.assertEqual(result['changed_ids'], ['build', 'review', 'test'])
        self.assertEqual([row['delta_units'] for row in result['allocations']],
                         ['-166666666666666667', '-333333333333333333', '500000000000000000'])
        self.assertEqual(result['delta_sum_units'], '0')
        self.assertTrue(result['review_required'])

    def test_no_change_permutation_and_equivalent_weights(self):
        after = copy.deepcopy(self.base)
        after['contributors'].reverse()
        after['contributors'][0]['weight'] += '.00'
        result = rv.review(*self.sources(after=after))
        self.assertEqual(result['changed_ids'], [])
        self.assertFalse(result['review_required'])
        self.assertNotEqual(result['before_receipt']['request_sha256'],
                            result['after_receipt']['request_sha256'])

    def test_zero_share_added_and_removed(self):
        after = copy.deepcopy(self.base)
        after['contributors'].append({'id': 'zero', 'weight': '0'})
        forward = rv.review(*self.sources(after=after))['allocations'][-1]
        reverse = rv.review(*self.sources(before=after, after=self.base))['allocations'][-1]
        self.assertIsNone(forward['before'])
        self.assertEqual(forward['after']['units'], '0')
        self.assertEqual(forward['reasons'], ['added'])
        self.assertEqual(reverse['reasons'], ['removed'])
        self.assertEqual(forward['delta_units'], '0')

    def test_weight_change_without_share_change(self):
        after = copy.deepcopy(self.base)
        for row in after['contributors']:
            row['weight'] = str(int(row['weight']) * 2)
        result = rv.review(*self.sources(after=after))
        self.assertTrue(result['review_required'])
        self.assertTrue(all(row['reasons'] == ['weight_changed'] for row in result['allocations']))

    def test_address_changes_with_no_share_change(self):
        # Real public token contracts are syntax fixtures, never proposed recipients.
        before = copy.deepcopy(self.base)
        before['contributors'][0]['address'] = rv.rs.TOKENS['zto']
        after = copy.deepcopy(before)
        after['contributors'][0]['address'] = rv.rs.TOKENS['imd']
        row = rv.review(*self.sources(before, after))['allocations'][0]
        self.assertEqual(row['reasons'], ['address_changed'])
        self.assertEqual(row['delta_units'], '0')
        after['contributors'][0].pop('address')
        row = rv.review(*self.sources(before, after))['allocations'][0]
        self.assertIsNone(row['after']['address'])
        self.assertEqual(row['reasons'], ['address_changed'])

    def test_tampered_reports_refused_both_sides(self):
        for index in (1, 3):
            sources = self.sources()
            sources[index]['allocations'][0]['units'] = '1'
            with self.assertRaises(rv.rs.Invalid):
                rv.review(*sources)

    def test_mismatched_metadata_and_payment_claim_refused(self):
        sources = self.sources()
        sources[-1] = dict(self.metadata, block_number=self.metadata['block_number'] + 1)
        with self.assertRaises(rv.rs.Invalid):
            rv.review(*sources)
        sources = self.sources()
        sources[3]['paid'] = True
        with self.assertRaises(rv.rs.Invalid):
            rv.review(*sources)

    def test_saved_review_tampering_and_types(self):
        sources = self.sources()
        result = rv.review(*sources)
        self.assertEqual(rv.verify(result, *sources)['result'], 'verified')
        for field, value in [('review_required', 0), ('delta_sum_units', '1'), ('paid', True)]:
            with self.subTest(field=field), self.assertRaises(rv.rs.Invalid):
                rv.verify(dict(result, **{field: value}), *sources)

    def test_uint256_and_one_unit_budget_delta(self):
        before = dict(self.base, budget=rv.rs.display_units(rv.rs.UINT256_MAX - 1, 18))
        after = dict(self.base, budget=rv.rs.display_units(rv.rs.UINT256_MAX, 18))
        result = rv.review(*self.sources(before, after))
        self.assertEqual(result['delta_sum_units'], '1')
        self.assertEqual(result['budget_delta_units'], '1')

    def test_200_seeded_roster_revisions_and_reversals(self):
        rng = random.Random(73736)
        for _ in range(200):
            def request():
                ids = rng.sample(range(15), rng.randint(1, 15))
                return {'budget': rv.rs.display_units(rng.randint(1, 100000), 18),
                        'contributors': [{'id': 'role-' + str(i), 'weight': str(rng.randint(1, 100))}
                                         for i in ids]}
            sources = self.sources(request(), request())
            forward = rv.review(*sources)
            reverse = rv.review(sources[2], sources[3], sources[0], sources[1], sources[4])
            balances = {}
            for sign, report in ((-1, sources[1]), (1, sources[3])):
                for row in report['allocations']:
                    balances[row['id']] = balances.get(row['id'], 0) + sign * int(row['units'])
            self.assertEqual({row['id']: int(row['delta_units']) for row in forward['allocations']}, balances)
            self.assertEqual([int(row['delta_units']) for row in reverse['allocations']],
                             [-int(row['delta_units']) for row in forward['allocations']])
            self.assertEqual(sum(balances.values()), int(forward['budget_delta_units']))

    def test_cli_handoff_verification_overwrite_and_refusal(self):
        scratch = Path('test/scratch')
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            paths = []
            for index, value in enumerate(self.sources()):
                path = Path(directory) / (str(index) + '.json')
                rv.rs.write_json(value, path)
                paths.append(str(path))
            args = []
            for flag, path in zip(('--before-request', '--before-report', '--after-request',
                                   '--after-report', '--metadata'), paths):
                args.extend((flag, path))
            out = str(Path(directory) / 'revision.json')
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(rv.main(['review', *args, '--output', out]), 0)
                self.assertEqual(rv.main(['verify', *args, '--revision', out]), 0)
                self.assertEqual(rv.main(['review', *args, '--output', out]), 2)
                self.assertEqual(rv.main(['demo']), 1)
                Path(paths[0]).write_text('{"budget":"1","budget":"2"}')
                self.assertEqual(rv.main(['review', *args]), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
