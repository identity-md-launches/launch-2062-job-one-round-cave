"""Offline regression tests and an independent exhaustive minute-grid oracle."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import random
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gatelock as gl


def oracle(tasks, gates, limits, workers, budget):
    # Place tasks in topological order at EVERY integer start, including starts
    # between completion events. Count interval occupancy without worker IDs.
    rows = tasks['tasks']
    by_id = {r['id']: r for r in rows}
    order, remaining = [], set(by_id)
    while remaining:
        name = next(n for n in sorted(remaining)
                    if set(by_id[n].get('after', [])) <= set(order))
        order.append(name)
        remaining.remove(name)
    due = {name: budget for name in order}
    for gate in gates['gates']:
        for name in gate['tasks']:
            due[name] = min(due[name], gate['due'])
    occupancy = [0] * budget
    resources = {r: [0] * budget for r in limits['capacities']}
    ends = {}
    best = None

    def place(index):
        nonlocal best
        if index == len(order):
            finish = max(ends.values())
            best = finish if best is None else min(best, finish)
            return
        name = order[index]
        row = by_id[name]
        duration = row['minutes']
        earliest = max((ends[d] for d in row.get('after', [])), default=0)
        for start in range(earliest, due[name] - duration + 1):
            end = start + duration
            if best is not None and end >= best:
                continue
            interval = range(start, end)
            demand = limits['demands'][name]
            if any(occupancy[t] == workers for t in interval):
                continue
            if any(resources[r][t] + units > limits['capacities'][r]
                   for r, units in demand.items() for t in interval):
                continue
            for t in interval:
                occupancy[t] += 1
                for r, units in demand.items():
                    resources[r][t] += units
            ends[name] = end
            place(index + 1)
            del ends[name]
            for t in interval:
                occupancy[t] -= 1
                for r, units in demand.items():
                    resources[r][t] -= units
    place(0)
    return best


class GatelockTests(unittest.TestCase):
    def test_demo_joint_constraints(self):
        tasks, gates, limits = gl.demo()
        result = gl.solve(tasks, gates, limits, 2, 6)
        self.assertEqual(result['status'], 'feasible')
        self.assertEqual(result['plan']['finish'], 6)
        slots = {r['task']: r for r in result['plan']['schedule']}
        self.assertEqual(slots['draft']['start'], 0)
        self.assertEqual(slots['review']['finish'], 3)
        self.assertTrue(result['resource_validation']['valid'])
        self.assertTrue(result['gate_validation']['valid'])

    def test_infeasible(self):
        tasks, gates, limits = gl.demo()
        self.assertEqual(gl.solve(tasks, gates, limits, 2, 5)['status'], 'infeasible')
        gates['gates'][0]['due'] = 2
        self.assertEqual(gl.solve(tasks, gates, limits, 2, 10)['status'], 'infeasible')

    def test_incomplete_is_not_proof(self):
        result = gl.solve(*gl.demo(), 2, 6, max_states=1)
        self.assertEqual(result['status'], 'search_incomplete')
        self.assertFalse(result['proven'])
        self.assertNotIn('plan', result)
        self.assertEqual(result['states_examined'], 1)

    def test_intentional_idle(self):
        tasks = {'tasks': [{'id': 'prepare', 'minutes': 1},
                          {'id': 'a', 'minutes': 7, 'after': ['prepare']},
                          {'id': 'b', 'minutes': 7, 'after': ['prepare']},
                          {'id': 'join', 'minutes': 8, 'after': ['a', 'b']},
                          {'id': 'background', 'minutes': 6}]}
        gates = {'gates': [{'id': 'join', 'tasks': ['join'], 'due': 16}]}
        limits = {'capacities': {'gpu': 2}, 'demands': {r['id']: {} for r in tasks['tasks']}}
        limits['demands']['a'] = limits['demands']['b'] = {'gpu': 1}
        self.assertEqual(gl.solve(tasks, gates, limits, 2, 16)['plan']['finish'], 16)

    def test_resource_capacity_and_boundary(self):
        tasks = {'tasks': [{'id': n, 'minutes': 2} for n in 'abc']}
        gates = {'gates': [{'id': 'all', 'tasks': list('abc'), 'due': 4}]}
        limits = {'capacities': {'gpu': 2, 'desk': 3},
                  'demands': {n: {'gpu': 1, 'desk': 1} for n in 'abc'}}
        result = gl.solve(tasks, gates, limits, 3, 4)
        self.assertEqual(result['plan']['finish'], 4)
        self.assertEqual(result['resource_validation']['resources'][1]['peak_units'], 2)

    def test_validation_and_no_mutation(self):
        args = gl.demo()
        before = copy.deepcopy(args)
        gl.solve(*args, 2, 6)
        self.assertEqual(args, before)
        for workers, budget, cap in [(True, 6, 1), (0, 6, 1), (5, 6, 1),
                                     (2, -1, 1), (2, Decimal('6.1'), 1), (2, 6, 0)]:
            with self.assertRaises(ValueError):
                gl.solve(*args, workers, budget, max_states=cap)
        tasks, gates, limits = gl.demo()
        limits['demands']['draft'] = {'gpu': 2}
        with self.assertRaises(ValueError):
            gl.solve(tasks, gates, limits, 2, 6)
        tasks, gates, limits = gl.demo()
        tasks['tasks'][0]['minutes'] = Decimal('1.5')
        with self.assertRaises(ValueError):
            gl.solve(tasks, gates, limits, 2, 6)
        tasks, gates, limits = gl.demo()
        gates['gates'][0]['tasks'] = ['missing']
        with self.assertRaises(ValueError):
            gl.solve(tasks, gates, limits, 2, 6)

    def test_seeded_exhaustive_grid(self):
        rng = random.Random(3801)
        for case in range(180):
            n = rng.randint(1, 5)
            names = [str(i) for i in range(n)]
            tasks = {'tasks': [{'id': name, 'minutes': rng.randint(1, 3),
                               'after': [d for d in names[:i] if rng.random() < .3]}
                              for i, name in enumerate(names)]}
            budget, workers = rng.randint(3, 8), rng.randint(1, 3)
            gates = {'gates': [{'id': 'g', 'tasks': rng.sample(names, rng.randint(1, n)),
                                'due': rng.randint(1, budget)}]}
            caps = {'gpu': rng.randint(1, 3), 'desk': rng.randint(1, 3)}
            limits = {'capacities': caps, 'demands': {name: {
                r: rng.randint(1, cap) for r, cap in caps.items() if rng.random() < .6}
                for name in names}}
            expected = oracle(tasks, gates, limits, workers, budget)
            got = gl.solve(tasks, gates, limits, workers, budget)
            with self.subTest(case=case):
                self.assertEqual(got['status'], 'infeasible' if expected is None else 'feasible')
                if expected is not None:
                    self.assertEqual(got['plan']['finish'], expected)

    def test_cli(self):
        cmd = [sys.executable, '-B', str(Path(gl.__file__)), '--demo']
        for extra, code in [([], 0), (['--max-states', '1'], 3),
                            (['--workers', '2'], 1), (['--plan-only'], 0)]:
            result = subprocess.run(cmd + extra, capture_output=True, text=True)
            self.assertEqual(result.returncode, code, result.stderr)

    def test_file_cli(self):
        scratch = Path('test/scratch/gatelock')
        scratch.mkdir(parents=True, exist_ok=True)
        for name, data in zip(('tasks', 'gates', 'limits'), gl.demo()):
            (scratch / (name + '.json')).write_text(json.dumps(data))
        cmd = [sys.executable, '-B', str(Path(gl.__file__)),
               '--tasks', str(scratch / 'tasks.json'),
               '--gates', str(scratch / 'gates.json'),
               '--limits', str(scratch / 'limits.json'), '--workers', '2', '--budget']
        for budget, expected in [('6', 0), ('5', 2), ('-1', 1)]:
            result = subprocess.run(cmd + [budget], capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stderr)
        (scratch / 'limits.json').write_text('{"capacities":{},"capacities":{},"demands":{}}')
        result = subprocess.run(cmd + ['6'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('duplicate JSON key', result.stderr)


if __name__ == '__main__':
    unittest.main()
