#!/usr/bin/env python3
"""Review roster, weight, routing and share changes between exact ZTO allocations."""
import argparse
import importlib.util
from pathlib import Path
import sys

SPEC = importlib.util.spec_from_file_location(
    'rewardreceipt', Path(__file__).resolve().parents[1] / 'rewardreceipt' / 'rewardreceipt.py')
rr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rr)
rs = rr.rs


def review(before_request, before_report, after_request, after_report, metadata):
    """Verify both complete reports before deriving any changes, keyed by exact ID."""
    before_receipt = rr.verify(before_request, before_report, metadata)
    after_receipt = rr.verify(after_request, after_report, metadata)
    before = {row['id']: row for row in before_report['allocations']}
    after = {row['id']: row for row in after_report['allocations']}
    changes = []
    for identifier in sorted(before.keys() | after.keys()):
        old, new = before.get(identifier), after.get(identifier)
        old_units = int(old['units']) if old is not None else 0
        new_units = int(new['units']) if new is not None else 0
        reasons = []
        if old is None:
            reasons.append('added')
        elif new is None:
            reasons.append('removed')
        else:
            if old['weight_fraction'] != new['weight_fraction']:
                reasons.append('weight_changed')
            if old.get('address') != new.get('address'):
                reasons.append('address_changed')
        if old_units != new_units:
            reasons.append('share_changed')
        # Null means absence; it is distinct from a present zero-unit row.
        changes.append({'id': identifier, 'reasons': reasons,
                        'before': None if old is None else {
                            'units': old['units'], 'weight_fraction': old['weight_fraction'],
                            'address': old.get('address')},
                        'after': None if new is None else {
                            'units': new['units'], 'weight_fraction': new['weight_fraction'],
                            'address': new.get('address')},
                        'delta_units': str(new_units - old_units)})
    budget_delta = int(after_report['budget_units']) - int(before_report['budget_units'])
    delta_sum = sum(int(row['delta_units']) for row in changes)
    rs.require(delta_sum == budget_delta, 'revision deltas do not conserve the budget change')
    return {
        'schema': 'rewardrevision-v1', 'token': before_report['token'],
        'before_budget_units': before_report['budget_units'],
        'after_budget_units': after_report['budget_units'],
        'budget_delta_units': str(budget_delta), 'delta_sum_units': str(delta_sum),
        'changed_ids': [row['id'] for row in changes if row['reasons']],
        'review_required': bool(budget_delta or any(row['reasons'] for row in changes)),
        'allocations': changes, 'before_receipt': before_receipt, 'after_receipt': after_receipt,
        'scope': 'Unsigned comparison of complete alternative allocations using one token capture. '
                 'Deltas are not payments, debts, refunds or settlement instructions. '
                 'IDs are caller labels, not proof of identity. No work, ownership, balance or payment verified.'}


def verify(saved, before_request, before_report, after_request, after_report, metadata):
    expected = review(before_request, before_report, after_request, after_report, metadata)
    rs.require(rr.canonical_bytes(saved) == rr.canonical_bytes(expected),
               'saved revision differs from full source recomputation')
    return {'schema': 'rewardrevision-verification-v1', 'result': 'verified',
            'revision_sha256': rr.digest(expected),
            'review_required': expected['review_required'], 'scope': expected['scope']}


def demo():
    metadata = rs.read_json(rr.ROOT / 'zto-mainnet.json')
    # Illustrative roles only, using real captured ZTO decimals; no payees invented.
    before = {'budget': '1', 'contributors': [
        {'id': 'build', 'weight': '2'}, {'id': 'review', 'weight': '1'}]}
    after = {'budget': '1', 'contributors': [
        {'id': 'build', 'weight': '1'}, {'id': 'test', 'weight': '1'}]}
    return review(before, rs.allocate(before, metadata), after, rs.allocate(after, metadata), metadata)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('demo', help='offline review of an address-free ZTO roster revision')
    for name in ('review', 'verify'):
        cmd = commands.add_parser(name)
        for side in ('before', 'after'):
            cmd.add_argument('--' + side + '-request', required=True)
            cmd.add_argument('--' + side + '-report', required=True)
        cmd.add_argument('--metadata', default=str(rr.ROOT / 'zto-mainnet.json'))
        cmd.add_argument('--output', help='new workspace JSON file; never overwrite')
        if name == 'verify':
            cmd.add_argument('--revision', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'demo':
            result = demo()
        else:
            sources = [rs.read_json(path) for path in (
                args.before_request, args.before_report, args.after_request,
                args.after_report, args.metadata)]
            result = (verify(rs.read_json(args.revision), *sources)
                      if args.command == 'verify' else review(*sources))
        rs.write_json(result, getattr(args, 'output', None))
        return 1 if result['review_required'] else 0
    except (rs.Invalid, OSError, ValueError, OverflowError, RecursionError) as exc:
        print('rewardrevision: ' + (str(exc) if isinstance(exc, rs.Invalid)
                                   else type(exc).__name__), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
