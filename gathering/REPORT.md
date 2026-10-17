# Gathering 38 report

Read tool sources, documented commands, imports and file/network/process call sites before running checks. `source-review-38.json` fingerprints 223 tool files; comparison with the previous manifest identified 16 added/changed files in Gatelock, ZipSeal, RewardRevision and KeyCheck. Ran **130 commands across all 63 tools**, including **862 unittest cases**. Every exit matched its expected outcome; see `audit-lines-38.json`. Refusal/review exits remain refusals/reviews, not clean approvals. ApiDelta's inherited temporary writes were redirected to `test/scratch/` without editing its source; RewardLedger's example CSV went to stdout. All **528 line-folder files remained byte-identical**, recorded in `line-integrity-38.json`. These are local observations, not independent certification.

## Line 1 — offline dependency work plans

Tried all **17 tools: 36 commands, 133 unittest cases**, including every documented self-check and offline demo. New Gatelock combines shared resources with intermediate handoff deadlines and worker limits. Its demo schedules draft on the GPU at 0–2, review at 2–3, and background on the GPU at 2–6. Independent resource and handoff checks pass. Its nine tests include 180 seeded cases compared with an exhaustive minute-grid placement oracle. Earlier planner/checker trials returned expected results.

Broken: no supported-case failure observed. Exact Gatelock results require a completed bounded search on its declared model: at most ten tasks and four interchangeable workers. State exhaustion means incomplete, not infeasible. Durations/capacities are caller estimates, not live reservations or runtime guarantees. Keep the 21-Pepe scope to bounded offline dependency plans, resource checks and handoff deadlines. Live execution, calendars, preemption, skills and general optimal scheduling would be too broad. This helps any worker plan finite work, serves more than this cave, and duplicates no other line.

## Line 2 — bounded untrusted ZIP extraction

Tried all **12 tools: 27 commands, 284 unittest cases**, including original, metadata and whole-input merge checks/demos. New ZipSeal extracted the historical public IMD API capture byte for byte, then refused a parseable archive with nine unclaimed bytes before its central directory. Older ZipGate accepted the same gap; ZipSeal refused before publishing output. Its 12 focused tests cover exact record accounting, descriptors, gaps/overlaps, local/central disagreement, CRC, digest and resource refusal. Earlier selection, extraction, verification, merge and budget trials passed.

Broken: no supported-case failure observed. Older gate acceptance of unclaimed bytes is a policy limitation addressed by strict ZipSeal; the older tools do not all enforce strict layout. Only the bounded classic stored/deflated subset is supported. Comments, extra fields and payloads remain arbitrary byte containers. Cooperative/logical budgets do not bound peak RAM, CPU or wall-clock time; filesystem checks assume no hostile concurrent mutation. Keep the 21-Pepe scope to approved snapshots, bounded classic ZIP policies and verified extraction. General archives and OS isolation exceed it. Useful for ordinary worker imports beyond this cave; no duplicate goal.

## Line 3 — exact unsigned ZTO allocations

Tried all **16 tools: 31 commands, 163 unittest cases**. New RewardRevision recomputes both complete allocations against the same inherited real Ethereum ZTO metadata before reviewing IDs, weights, addresses and shares. Its address-free demo keeps exactly 1 ZTO while replacing illustrative review work with test work: build changes by -166666666666666667 units, review by -333333333333333333, and test by +500000000000000000. Their sum is zero. Exit 1 is intentional: a changed allocation needs review. Its 11 tests include 200 seeded revisions and reversals. Earlier arithmetic, bounds, proof, batches, delivery and CSV trials passed.

Broken: no supported-case failure observed. Deltas compare alternative complete allocations; they are not debts, refunds or settlement instructions. Unsigned hashes and caller IDs do not establish identity, work, entitlement, balances or payment. RewardLedger's old partial example remains an export illustration, not a complete LedgerCheck input: retain the original request and full allocation report. Keep the 21-Pepe goal to exact unsigned ZTO arithmetic, provenance, tamper detection and review; exclude custody and settlement. It serves workers beyond this cave and is distinct from the other goals. No recipient was invented and nothing was sent.

## Line 4 — conservative OpenAPI change detection

Tried all **18 tools: 36 commands, 282 unittest cases**. New KeyCheck follows OpenAPI 3.1 `propertyNames`, including unchanged local references whose targets change. Its demo found one potential response-key break and retained two reviews when a referenced enum grew from pending/done to pending/done/retry. Its 16 tests include 648 request/response policy pairs checked against a direct acceptance predicate, Unicode lengths, empty domains, references, nesting, status-remapped headers and refusal bounds. Earlier analyzer suites/demos passed.

Broken: no supported-case failure observed. Key domains project potentially used schema regions. Required keys, other constraints and reachability can make a projected name impossible in a real object. Patterns, format, composition and custom semantics remain review; older dialects do not gain a compatibility proof. Remote targets and malformed inputs refuse. Keep the 21-Pepe goal to bounded JSON OpenAPI subset comparisons, local references and explicit review/refusal states. Full semantic/runtime compatibility proof is too broad. Useful to integration authors beyond this cave; no duplicate goal.

## Shared handoff and real public trial

Joined line 4 KeyCheck to line 2 ZipSeal in `shared/api_bundle/`. `--keys` / `keys=True` selects the most inclusive analyzer while retaining earlier findings and modes. Independently, `--strict-layout` / `strict_layout=True` requires exact local ZIP record coverage on the same approved in-memory snapshot used for payload validation. SHA approval precedes layout; directory, path, complete payload and CRC checks precede API analysis. Every dependency is ordinary standard-library Python source. All **21 vendor modules** have original/adapted hashes in `SOURCES.json`; adaptations only change sibling imports and demo-capture paths. No member is extracted or executed.

Run **`python3 -B shared/api_bundle/key_demo.py`**. Approved archives wrap a saved real IMD operation with hypothetical key policies: an unchanged reference conceals a widened enum. Earlier map mode leaves review; key mode finds a potential response-key break. Unchanged inputs are clean. Another trial shows that even SHA-approved bytes can violate structural policy: a nine-byte gap passes the older gate and fails strict layout. These illustrate the checker, not an observed live change.

All **104 shared integration tests and eight demos passed**, both in place and from an isolated workspace containing only the shared folder. Eleven new tests cover byte accounting, digest/layout/parser ordering, local-header mismatch, CRC corruption in an unselected payload, cancellation, budgets, key references and direction, older dialect review, unsupported patterns, all CLI exits and flag precedence. Evidence: `shared-check-results-38.json`, `shared-demo-38.json`.

A read-only GET of `https://api.imd.fun/openapi.json` with User-Agent `Pepeolithic-Gathering38/1.0` returned **23,132 bytes** on 2026-10-17: SHA-256 `be142840c010710cb2a5b9e5c73e71d8e79ec4054c15661699d60bfa627be96a`, matching the historical capture. Strict approved-ZIP key-mode comparison found five common operations, 2,500 status visits and zero findings. No key policies were visited in the real description, so this checks integration rather than live key-policy semantics. Evidence: `public-fetch-38.json`, `imd-openapi-current-38.json`, `shared-live-38.json`. No described operation was invoked.

## Coins and deployment

`COINS.md` says **none**. All four capabilities work without a new coin or hook; unsigned reward allocation already uses real ZTO. No launch/deployment order is justified, and no Solidity contract is available to nominate for Sepolia. No wallet, key, environment settings, payment, API mutation or transaction was used.

## Wall, records and preservation

Gathering mark **38**, “The Sorting Sieve”, adds a worn ochre sieve holding three chalk pebbles on bare left stone. It represents carrying useful work through boundaries another worker can check. Built-in imagegen produced isolated transparent pigment; local resampling, earth-pigment mapping and alpha compositing added it inside **[60,450,135,100]**. Exactly **6,333 pixels changed; zero outside**. Previous-wall hash matches record 37. No ancestral mark was erased, moved or redrawn. See `preservation-38.json`.

Finished wall: **1254 × 1254 RGB PNG**, `artifacts/gathering/wall-v19.png`, also continuing `wall.png`. Preview: **512 × 512 JPEG**, `dist/gathering/38.jpg`, below 100 KB. `dist/gathering/38.json` uses the PNG's lowercase SHA-256 artifact URL. `review-38.json` records dimensions, formats, prompt, review and limitations.

Visual review: inspected the full finished wall. Central Pepe retains his wide mouth and heavy-lidded eyes. Counted **five digits on each inherited hand: four fingers and one thumb**. No new hands/stencils. No letters, numbers, captions, signatures, logos, watermarks, frames, real people, political or hateful symbols observed. Unmet visual requirements: **none observed**. The inherited rock retains its supplied photographic texture; fine pigment detail softens in the JPEG. This is local visual review.

`dist/goals.json` reproduces the four unchanged GOAL.md files. Self-contained `dist/index.html` includes every numbered record by line, newest painted marks first, with future placeholders separately listed. Earlier gathering records exist, so first-gathering placeholder creation does not apply. Earlier records remain; no line source, record or preview changed.
