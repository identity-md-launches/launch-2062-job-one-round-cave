# Gatelock — meet handoffs while sharing tools

Build a shortest complete offline work plan that respects dependencies, worker
slots, renewable resource capacities, intermediate handoff deadlines and a final
budget together. This fills the gap between Gateplan (handoffs) and Lockplan
(shared resources). It executes no tasks and reserves no actual hardware.

From the repository root, Python 3.10+ and only the standard library:

```sh
python3 -B line-1/tools/gatelock/gatelock.py --demo
```

Observed: draft uses the GPU during minutes 0–2. Background then uses it during
2–6, while review runs on the second worker during 2–3. The handoff meets minute
3 exactly; all work finishes at minute 6. Both the independent resource and gate
checks pass. Starting background first would miss that handoff.

## Use your own work

```sh
python3 -B line-1/tools/gatelock/gatelock.py --tasks line-1/tools/gatelock/tasks.json --gates line-1/tools/gatelock/gates.json --limits line-1/tools/gatelock/limits.json --workers 2 --budget 6
```

The three supplied JSON files are editable input examples, with these contracts:

- Tasks: `{"tasks":[{"id":"draft","minutes":2,"after":[]}]}`. Unique nonempty
  task names, positive whole-minute durations, known distinct prerequisites,
  and no cycles. `after` may be omitted. No command fields are accepted.
- Gates: `{"gates":[{"id":"handoff","tasks":["draft"],"due":3}]}`. Each named
  gate requires every listed task to finish by its inclusive due minute. Groups
  may overlap. A gate's prerequisites are enforced by the task graph.
- Limits: `{"capacities":{"gpu":1},"demands":{"draft":{"gpu":1}}}`. Declare
  every task exactly once; use `{}` for a task needing no resources. Demands
  and capacities are positive integer units. Zero demand is expressed by
  omission of the resource. Reservations cover the full half-open task interval
  `[start, finish)`, so a completion releases capacity for starts at that minute.

Limits: 1–10 tasks, 1–4 interchangeable workers, 1–64 resource types, 1–500 gates.
Durations, final budget and gate due times must be whole minutes no greater
than 10,000; budget and due times may be zero. Each demand must fit its resource
capacity. Gates are required; for a final-only problem, name all tasks in one
gate with due equal to budget. File inputs must be ordinary workspace files
under 100 KB, without duplicate keys. Unknown schema fields are rejected.

The result is one of:

- `feasible`: a shortest plan meeting every supplied constraint, with independent
  Lockcheck (including Plancheck) and Gatecheck reports. Add `--plan-only` to
  emit a reusable full schedule for the other line tools.
- `infeasible`: complete search found no plan under these assumptions.
- `search_incomplete`: the state bound was reached; no feasibility or optimality
  proof is claimed and no partial plan is emitted.

CLI exits: 0 feasible, 2 infeasible, 3 incomplete, 1 invalid input or a requested
plan-only output that cannot be produced. `--max-states` defaults to 100,000
and accepts 1–500,000. Demo input options cannot be mixed with file options.

## Method and checks

The bounded search enumerates every resource-feasible subset of ready tasks at
completion events. It includes intentional idle worker slots, since starting
available work immediately can make a better future handoff impossible. States
cache completed tasks, active tasks' remaining durations and current time.
With no external releases, a regular objective has an active optimum: a task
starting between completion events can shift left until a release or time zero
without making any task later. Every start subset at those events is considered.
Worker identities are interchangeable during search and assigned on reconstruction.

```sh
python3 -B line-1/tools/gatelock/selftest.py
```

Observed: nine tests pass, including 180 seeded small cases compared with an
independent exhaustive start-time placement oracle on a minute grid. Coverage
includes simultaneous release/start boundaries, two resources, multi-unit
capacity, intentional waiting, impossible handoffs/budgets, state-limit refusal,
invalid inputs, CLI exit codes and duplicate-key file rejection.

This is exact only for the declared model and completed bounded searches.
Estimates and capacity claims are caller assumptions. No live availability,
resource calendars, preemption, running tasks, worker skills or actual runtime
prediction is modeled. Worst-case search is exponential; use Lockplan for larger
heuristic plans. Keep sibling `plancheck/`, `gatecheck/` and `lockcheck/` folders:
Gatelock imports their unchanged validators. Gateplan supplied the search design;
it is not a runtime dependency. No installation or network is needed.
