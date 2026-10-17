# RewardRevision

Review a proposed replacement of an exact ZTO allocation when contributor IDs, weights, recipient addresses or the budget change. Both complete reports must first match RewardReceipt's recomputation from their original requests and the same token capture. The review lists every ID in ASCII order, original and replacement units/weights/addresses, explicit additions/removals, and signed atomic-unit differences. Their sum must equal the budget difference. Python standard library only, using the existing sibling RewardReceipt and RewardSplit modules; no installation or network required.

Run from the repository root:

```sh
python3 -B line-3/tools/rewardrevision/rewardrevision.py demo
```

The demo **exits 1 intentionally**: a valid revision needs review. Using the inherited real Ethereum ZTO capture, it replaces illustrative `build`/`review` roles with `build`/`test`, keeping exactly 1 ZTO. `build` changes by -166666666666666667 units, `review` by -333333333333333333 and `test` by +500000000000000000. The sum is zero. No recipient addresses are invented. This was tried locally; all 11 tests passed, including 200 seeded roster revisions and reversals, address-only and weight-only changes, zero-unit memberships, uint256 precision, altered inputs and file handoff checks. The inherited eight RewardReceipt tests also passed.

For your own proposed revision, save both original requests and full RewardSplit reports:

```sh
python3 -B line-3/tools/rewardrevision/rewardrevision.py review \
  --before-request BEFORE_REQUEST.json --before-report BEFORE_REPORT.json \
  --after-request AFTER_REQUEST.json --after-report AFTER_REPORT.json \
  --output REVISION.json
```

Use `verify` with those same flags and `--revision REVISION.json` to recompute and check a saved review; choose another `--output` if saving verification. `--metadata PATH` selects the same capture used for both reports (default: the included historical real ZTO mainnet capture). Inputs and outputs must be inside the current workspace. Duplicate JSON keys, inputs over 256 KiB, mismatched reports and existing output files are refused. Oversize output is refused before writing; reduce the roster/ID lengths if a revision cannot fit 256 KiB even in compact JSON. No report is trusted merely because its hash matches a CSV.

Exit 0 means verified and no allocation-setting change; 1 means verified but review is needed; 2 means invalid input or I/O refusal. Equivalent weight notation and input ordering alone do not trigger review, although canonical input receipts still bind those source values. A changed weight triggers review even when shares remain equal. Adding/removing a zero-unit contributor also triggers review. Missing contributors appear as `null`, distinct from present zero shares. Missing addresses remain `null`; changing an address never merges two IDs. Renames appear as removal plus addition. Changed rounding flags without a share or setting change are not separately flagged, but both complete reports remain receipt-bound.

These are alternative complete allocations, not successive payments. **Never use signed differences as payment, debt, refund or recovery instructions.** Contributor IDs are caller labels; matching them does not prove identity or continuity. Address changes are exposed, not authorized. Neither arithmetic nor hashes establish work, ownership, available balances or payment. The historical token capture is a single public RPC observation, not an independent chain proof. RewardRevision does not access wallets or secrets, read environment variables, sign, send, pay, post, or prepare transactions. For budget-only changes and explicit largest-remainder reversal flags, use RewardCompare.

```sh
python3 -B line-3/tools/rewardrevision/selftest.py
```
