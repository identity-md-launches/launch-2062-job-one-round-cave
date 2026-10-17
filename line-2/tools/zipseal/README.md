# ZipSeal — strict classic ZIP layout before extraction

ZipSeal checks that a classic ZIP's local records occupy every byte from the
start of the archive to its central directory, with no gap, overlap or hidden
unreferenced local record. It compares each local filename, method, flags,
sizes and CRC with its central entry and checks data descriptors. Only then
does it call the inherited ZipGate and SafeZip to check paths, special members,
compression, every payload, CRC, digest and extraction limits. It publishes an
output directory only after those checks succeed. Python 3.9+ standard library
only; keep the shipped `../zipgate/` and `../safezip/` folders beside it.

From the repository root, run one command to see it work:

```sh
python3 -B line-2/tools/zipseal/demo.py
```

Tried here: the demo packed the shipped historical public IMD OpenAPI capture
(23,132 bytes, provenance in `../safezip/sample-source.json`), extracted it
byte-identically, then refused an otherwise parseable ZIP with nine unclaimed
bytes inserted between the last payload and central directory. The inherited
ZipGate accepted that archive, showing the added check. ZipSeal left no output.
This is an offline replay of public data, not a fresh
network observation. The demo uses only disposable files in `test/scratch/`.

## Use

First review an archive and its SHA-256. The optional `--sha256` requires an
exact approved digest and binds the strict layout check to the subsequent
ZipGate/SafeZip reads. The archive and destination must be within the current
workspace, with no existing symlink path component. Extraction requires a new
destination whose parent already exists.

```sh
python3 -B line-2/tools/zipseal/zipseal.py inspect incoming.zip --sha256 REVIEWED_SHA256
python3 -B line-2/tools/zipseal/zipseal.py extract incoming.zip extracted --sha256 REVIEWED_SHA256
```

`process(archive_path, output=None, ...)` is the Python API. It returns the
inherited inspection/extraction report with a `layout` section: local record,
header, compressed payload, descriptor, central-directory and end-record byte
counts. `output=None` inspects without extraction. Refusal, corruption and I/O
errors produce a nonzero CLI exit and an `ok: false` JSON error. Untrusted
archive content is never executed.

The defaults are 1,000 entries, 2 MiB central directory, 32 MiB whole archive,
32,000 filesystem nodes, 16 MiB per file, 64 MiB total uncompressed bytes and
200:1 per-file compression ratio. All limits are positive integers. `--seconds`
is a finite positive cooperative deadline shared across layout and payload
checks; the API also accepts a cancellation callback. These are logical and
cooperative bounds, not exact CPU, peak RAM, disk or wall-clock reservations.
The digest-bound inherited pass rereads the archive. A changed source is
refused before publishing output.

This deliberately accepts only the classic single-disk, stored/deflated ZIP
subset accepted by ZipGate. ZIP64, self-extracting prefixes, gaps and some valid
unusual layouts are refused. ZIP comments, extra fields and compressed payloads
remain permitted byte containers; structural accounting does not make their
contents safe or authenticate a publisher. Work in a cooperative workspace:
hostile concurrent filesystem changes can race path checks. Do not execute
extracted files without separate review.

Run the focused adversarial checks with
`python3 -B line-2/tools/zipseal/selftest.py`. All 12 passed here, covering
stored/deflated and empty archives, exact byte accounting, signed and unsigned
data descriptors, gaps, overlaps, prefixes, local/central disagreement, payload
corruption, digest/size refusal and cancellation without output. These are local
observations, not independent certification. No coin, wallet or transaction is
needed for local extraction.
