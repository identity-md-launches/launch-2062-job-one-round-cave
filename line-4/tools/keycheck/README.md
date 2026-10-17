# KeyCheck

Find potential breaking changes to **object key names** in OpenAPI 3.1 JSON
schemas, including unchanged local `propertyNames` references whose targets
change. KeyCheck extends MapCheck and retains all earlier line 4 findings.
Python 3.9+ and the standard library are sufficient; keep the sibling tool
folders alongside this one. It reads descriptions without calling their APIs.

From the repository root:

```sh
python3 -B line-4/tools/keycheck/keycheck.py demo
```

Tried successfully: **five operations compared, one potential break and two
reviews**, exit 0. The demo uses an operation in the bundled real public IMD
description, hypothetically sets the description to OpenAPI 3.1, and gives its
response a key-name enum through a local component reference. The enum expands
from `pending, done` to `pending, done, retry` while the reference stays the same.
MapCheck leaves the component change for review; KeyCheck also finds the
potential response-key break. These schemas are an illustration, not an
observed change or promise of the live service.

Compare your own workspace descriptions:

```sh
python3 -B line-4/tools/keycheck/keycheck.py compare old.json new.json
```

Compare prints deterministic JSON and exact input-byte SHA-256 values. Exit
**0** means no detected break within the subset, **1** a potential break,
**2** invalid/unsupported input or resource refusal, **3** unresolved review.
The Python `compare(old_dict, new_dict)` entry point returns the same report
without byte hashes and does not mutate either input. Reports include visited
`key_pairs`, their locations and directions, projected old/new key domains,
and the inherited map/dispatch/status details.

## Supported key domains

The [JSON Schema property-name rule](https://json-schema.org/understanding-json-schema/reference/object#property-names)
applies its schema to each object's key, independently of the value. Keys are
strings. KeyCheck interprets a bounded subset of that schema:

- `true`, omission and `{}` allow all names; `false` allows no names. A no-name
  policy still permits an empty object; it is not an impossible object schema.
- `type` intersects the possible names with strings. Adding `type: string`
  alone does not restrict JSON keys; `type: integer` leaves no allowed names.
- `enum` and `const` intersect their string literals; non-string literals
  cannot name a JSON key. Mixed enums and contradictory enum/const combinations
  are handled without treating booleans as integers.
- `minLength` and `maxLength` bound Unicode **code points**, with inclusive
  endpoints. The checker filters finite sets through these bounds and compares
  unrestricted length intervals. A zero-length interval contains just `""`;
  contradictory intervals contain no names. No long witness string is built.
- Requests must continue to accept the old projected names; responses must
  stay within the old projected names. Violations add a
  `property_names_incompatible` potential break. Existing review findings stay.

These are JSON Schema 2020-12 keywords, used by the
[OpenAPI 3.1 Schema Object](https://spec.openapis.org/oas/v3.1.0.html#schema-object).
OpenAPI 3.0 and cross-version comparisons leave key semantics for explicit
review rather than promoting them to a break.

The extension visits the schema pairs already traversed by MapCheck: common
properties, array items, additional-property values, explicit discriminator
mapping targets, request bodies/parameters and response bodies/headers,
including remapped response status fallbacks. Local references are resolved
independently on each side. Recursive graphs use inherited active-pair guards.

## Review boundaries and refusals

Any other non-annotation keyword in a visited key schema, even when unchanged,
adds `property_name_constraints_unchecked`. Patterns, format, composition,
custom dialects and vocabularies are **not evaluated**. Changes to resolved
key schemas get their own review location, so a changed pattern behind an
unchanged reference cannot silently produce a clean report. Reference URLs
are never fetched; regexes, scripts and described endpoints are never run.

The key-domain projection does not solve whole-object satisfiability or
reachability. Required keys, closed objects, pattern properties, conditional
schemas, non-object parent types and other restrictions can make a projected
name impossible in a real payload. A finding is a potential schema-region
break, not a proof that an accepted object or a generated client breaks.
Arbitrary compositions, unvisited/unused targets, callbacks and webhooks keep
the inherited limitations. A clean report is not runtime compatibility proof.

Refusals include malformed visited policies, invalid length bounds, enums
outside **1..1,024 entries**, invalid type declarations, remote/missing local
references, alias cycles and semantic `$ref` siblings. There are at most
**1,024 visited key pairs**, plus inherited 1,024 map pairs, 512 dispatch pairs,
20,000 schema visits, 2,000 findings, 1 MiB/input, 50,000 nodes, depth 80 and
operation/header/security/server budgets. A refusal returns no partial success
report. This remains a subset analyzer, not complete schema validation.

## What happened when tried

```sh
python3 -B line-4/tools/keycheck/selftest.py
python3 -B line-4/check-38.py
```

The new suite passed **16 tests**, including **648** request/response policy
pairs evaluated by an independent direct acceptance predicate over
representative key names. Regressions cover Unicode lengths, empty-string and
empty domains, mixed literals, unchanged/recursive references, nested maps and
arrays, discriminator targets, remapped headers, request parameters, unsupported
constraints, older dialects, malformed inputs, budget refusals, nonmutation,
retained findings, the historical public capture and all CLI outcomes.

The round check passed **282 tests across 18 suites**, including every inherited
suite, with temporary files confined
to `test/scratch/`. Optional `--live` fetches only the public description using
User-Agent `Pepeolithic-KeyCheck/38.0`, then compares it with the historical
capture. The live trial returned **23,132 bytes**, identical to the bundled capture:
five operations compared, zero findings. It has no visited key-name policies,
so this checks integration rather than live key-policy semantics. Results and
the exact capture hash are in `line-4/check-results-38.json`.
No described operation, wallet, secret, balance, payment or transaction is
needed for this offline integration tool.
