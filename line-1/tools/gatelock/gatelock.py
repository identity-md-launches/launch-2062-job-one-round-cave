#!/usr/bin/env python3
"""Find a bounded exact plan with both handoff deadlines and shared resources."""
import argparse
from functools import lru_cache
from fractions import Fraction
import itertools
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "plancheck"))
sys.path.insert(0, str(HERE.parent / "gatecheck"))
import plancheck  # noqa: E402
import gatecheck  # noqa: E402
sys.path.insert(0, str(HERE.parent / "lockcheck"))
import lockcheck  # noqa: E402


def integer(value, label, ceiling=10000):
    number = value if isinstance(value, Fraction) else plancheck.number(value, label)
    if number.denominator != 1 or not 0 <= number <= ceiling:
        raise ValueError(f"{label} must be an integer from 0 to {ceiling}")
    return int(number)


def solve(tasks_data, gates_data, limits_data, workers, budget, max_states=100000):
    """Bounded nonpreemptive event search, including intentional worker idle time.

    A regular objective has an active optimum: if any task starts strictly
    between completion events it can move left until time zero, its dependency
    release, or a resource/worker release, without harming a deadline. Enumerate
    every subset of ready tasks that fits the current cumulative capacities.
    Workers are interchangeable and resources are held for the entire task.
    """
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("workers must be an integer from 1 to 4")
    if type(max_states) is not int or not 1 <= max_states <= 500000:
        raise ValueError("max_states must be an integer from 1 to 500000")
    deadline = integer(budget, "budget")
    graph = plancheck.graph(tasks_data)
    if len(graph) > 10:
        raise ValueError("gatelock is limited to 10 tasks")
    gates = gatecheck.validate_gates(gates_data, set(graph))
    capacities, demands = lockcheck.resources(limits_data, set(graph))
    for name, row in demands.items():
        if any(units > capacities[resource] for resource, units in row.items()):
            raise ValueError("task demand exceeds capacity: " + name)
    names = sorted(graph)
    index = {name: i for i, name in enumerate(names)}
    durations = [integer(graph[name][0], "task minutes") for name in names]
    prerequisites = [sum(1 << index[dep] for dep in graph[name][1]) for name in names]
    due = [deadline] * len(names)
    for gate in gates:
        gate_due = integer(gate["due"], "gate due")
        for name in gate["tasks"]:
            due[index[name]] = min(due[index[name]], gate_due)
    all_done = (1 << len(names)) - 1
    examined = 0

    class SearchLimit(Exception):
        pass

    @lru_cache(maxsize=None)
    def search(done, active, now):
        nonlocal examined
        examined += 1
        if examined > max_states:
            raise SearchLimit
        if done == all_done:
            return now, ()
        busy = {task for task, _ in active}
        ready = tuple(i for i in range(len(names)) if
                      not (done >> i) & 1 and i not in busy and
                      prerequisites[i] & ~done == 0)
        capacity = min(workers - len(active), len(ready))
        choices = itertools.chain.from_iterable(
            itertools.combinations(ready, size)
            for size in range(0 if active else 1, capacity + 1))
        best = None
        for chosen in choices:
            reserved = [names[i] for i, _ in active] + [names[i] for i in chosen]
            if any(sum(demands[name].get(resource, 0) for name in reserved) > cap
                   for resource, cap in capacities.items()):
                continue
            running = tuple(sorted(active + tuple((i, durations[i]) for i in chosen)))
            if not running:
                continue
            step = min(remaining for _, remaining in running)
            next_time = now + step
            if next_time > deadline:
                continue
            next_done = done
            next_active = []
            missed = False
            for task, remaining in running:
                if remaining == step:
                    next_done |= 1 << task
                    missed |= next_time > due[task]
                else:
                    next_active.append((task, remaining - step))
            if missed:
                continue
            tail = search(next_done, tuple(next_active), next_time)
            if tail is not None:
                candidate = (tail[0], chosen)
                if best is None or candidate < best:
                    best = candidate
        return best

    try:
        optimum = search(0, (), 0)
    except SearchLimit:
        return {"status": "search_incomplete", "proven": False,
                "reason": "state limit reached; feasibility and optimum not established",
                "states_examined": examined - 1, "state_limit": max_states}
    if optimum is None:
        return {"status": "infeasible", "proven": True,
                "workers": workers, "budget": deadline,
                "states_examined": examined, "state_limit": max_states}

    done, now = 0, 0
    active = []  # task, absolute finish, worker
    rows = []
    while done != all_done:
        state = tuple(sorted((task, finish - now) for task, finish, _ in active))
        _, chosen = search(done, state, now)
        occupied = {worker for _, _, worker in active}
        free = (worker for worker in range(1, workers + 1) if worker not in occupied)
        for task in chosen:
            worker = next(free)
            finish = now + durations[task]
            active.append((task, finish, worker))
            rows.append({"task": names[task], "worker": worker,
                         "start": now, "finish": finish})
        now = min(finish for _, finish, _ in active)
        for task, finish, _ in active:
            if finish == now:
                done |= 1 << task
        active = [item for item in active if item[1] != now]

    plan = {"units": "minutes", "workers": workers, "finish": now,
            "schedule": rows}
    resource_validation = lockcheck.check(tasks_data, plan, limits_data, workers, deadline)
    gate_validation = gatecheck.check(tasks_data, plan, gates_data, workers, deadline)
    if not resource_validation["valid"] or not gate_validation["valid"]:
        raise AssertionError("internal schedule failed independent validation")
    return {"status": "feasible", "proven": True,
            "objective": "shortest finish meeting gates and renewable resource limits",
            "workers": workers, "budget": deadline,
            "states_examined": examined, "state_limit": max_states, "plan": plan,
            "resource_validation": resource_validation, "gate_validation": gate_validation}


def demo():
    # Alphabetical resource planning would start background first and miss review.
    tasks = {"tasks": [{"id": "background", "minutes": 4},
                       {"id": "draft", "minutes": 2},
                       {"id": "review", "minutes": 1, "after": ["draft"]}]}
    gates = {"gates": [{"id": "handoff", "tasks": ["review"], "due": 3}]}
    limits = {"capacities": {"gpu": 1}, "demands": {
        "background": {"gpu": 1}, "draft": {"gpu": 1}, "review": {}}}
    return tasks, gates, limits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--tasks")
    parser.add_argument("--gates")
    parser.add_argument("--limits")
    parser.add_argument("--workers", type=int)
    parser.add_argument("--budget", type=int)
    parser.add_argument("--max-states", type=int, default=100000)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.demo:
            if any(value is not None for value in
                   (args.tasks, args.gates, args.limits, args.workers, args.budget)):
                raise ValueError("--demo cannot be combined with input options")
            tasks, gates, limits = demo()
            workers, budget = 2, 6
        else:
            if any(value is None for value in
                   (args.tasks, args.gates, args.limits, args.workers, args.budget)):
                raise ValueError("--tasks, --gates, --limits, --workers and --budget required")
            tasks = plancheck.read_json(args.tasks)
            gates = plancheck.read_json(args.gates)
            limits = plancheck.read_json(args.limits)
            workers, budget = args.workers, args.budget
        result = solve(tasks, gates, limits, workers, budget, args.max_states)
        if args.plan_only and result["status"] != "feasible":
            raise ValueError("no complete plan: " + result["status"])
        print(json.dumps(result["plan"] if args.plan_only else result, indent=2, allow_nan=False))
        return {"feasible": 0, "infeasible": 2, "search_incomplete": 3}[result["status"]]
    except (ValueError, OSError, OverflowError, RecursionError) as exc:
        print("gatelock: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
