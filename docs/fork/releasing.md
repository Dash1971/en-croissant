# Candidate evidence and release gates

This review stack creates unpublished candidates only. It neither publishes a
GitHub release nor changes the default branch, installs an app, merges source,
uses signing credentials, or creates an updater feed. The inherited publishing
workflow is explicitly restricted to the upstream repository. The maintained
fork uses [the manual-update distribution contract](updates.md).

## Inputs and clean source

Use a dedicated checkout at the exact reviewed commit. Fetch full history so the
registered upstream base is available. Candidate creation refuses tracked,
staged, and non-ignored untracked changes, both before and after validation. It
never resets, stashes or deletes source. The only new ignored workspace is
`scripts/fork/out/` (plus this tool's Python bytecode); normal existing dependency
and build directories retain their existing ignores. Do not hide source changes
with local ignore rules or reuse a checkout containing private data.

[`scripts/fork/inputs.json`](../../scripts/fork/inputs.json) pins Rust **1.99.1**,
Node **24.22.3**, pnpm **12.15.0**, and the exact arm64 AIX extension release asset,
size and SHA-256. Existing extension files must match; mismatches fail without
overwriting them. The tool never downloads `latest`. `package.json` must agree on
pnpm. Install the specified tools separately; the candidate script checks them
and does not change globally installed tools.

The build requires native Apple Silicon macOS and a matching Rust host. It uses
native Cargo output, avoiding a second cross-target build cache, and checks the
actual executable with `lipo`. It rebuilds the frontend with the maintained flag,
passes `maintained-fork` to Rust tests and the build, and passes the maintained
Tauri overlay. Conflicting distribution or signing environments are rejected.
The overlay must have the fork version, no updater endpoints or updater
artifacts, the existing identifier, and only ad-hoc signing.

## Commands

From the clean repository root:

```sh
python3 -m unittest discover -s scripts/fork -p 'test_*.py'
python3 scripts/fork/manage.py register-check
python3 scripts/fork/manage.py candidate
python3 scripts/fork/manage.py verify scripts/fork/out/candidate-COMMIT-TIME/receipt.json
```

Candidate creation runs frozen pnpm installation, register and evidence tests,
frontend lint/tests and a frontend build, all native Rust tests in release mode
(two test threads), and the native app build with locked
Cargo dependencies. It requires log evidence that all lifecycle tests passed
(at least the ten current regressions). Cargo concurrency is capped at two.
It does not start the application or load a model/database.

By default dependency downloads go into ignored workspace caches and Cargo uses
`src-tauri/target`. An explicitly provided `CARGO_HOME` or `CARGO_TARGET_DIR` can
reuse an owned cache; do not point concurrent builds at the same target directory.
A shared `node_modules` symlink is rejected: dependency installation must not
mutate another checkout. A cache is not validation evidence; the exact source,
inputs, successful checks and produced app are checked again. `CARGO_BUILD_TARGET`
is rejected for this native recipe. Before bundling, an existing app at the
expected native output path is moved to `previous-build.app` inside the ignored
candidate directory. The build must produce a new app there; a layered Cargo
configuration redirecting output cannot silently reuse the prior app. The prior
bundle is preserved locally and is not uploaded as a candidate artifact.

The native GitHub workflow uses `macos-15` arm64 with a 90-minute limit, pinned
tools, two Cargo jobs and a Rust cache keyed by the input pins. It runs on matching
PR changes and on manual dispatch. PR runs check out the actual PR head; receipts
do not mislabel a synthetic merge commit. The ordinary frontend workflow also
runs the Python fixtures and register check. All fork jobs use read-only contents
permissions; candidate artifacts expire after 14 days.

## What a receipt proves

The receipt identifies the exact fork commit and Git tree, registered upstream
commit, both dependency-lock hashes, pinned external AIX input, tool versions,
macOS, selected developer directory and SDK, Xcode query status/output, executed
commands with exit statuses and log hashes, executable
hash, app contents/modes/symlink manifest hash, archive hash, and ad-hoc signing.
Full Xcode is not required solely for evidence: with Command Line Tools selected,
the receipt retains the failed `xcodebuild -version` status and diagnostic while
recording the selected developer directory and the SDK reported by `xcrun`.
The receipt itself is not included in its own digest. It records the inputs used;
it does not promise byte-identical builds across SDKs or machines.

Verification requires the receipt's exact clean source revision. It requires the exact ordered command recipe (including maintained feature and
overlay), rejects missing/duplicate/altered steps, hashes the logs and archive,
checks archive paths, extracts into a temporary directory,
checks bundle identity/version and arm64 architecture, verifies the code signature,
and compares the extracted file contents, executable permissions and executable
hash. If the unpacked candidate app is also present it must match. Changed logs,
archive, source, lockfiles or app contents fail verification. A receipt and hashes
are review evidence, not a cryptographic attestation from a trusted publisher.

The verifier expects the full prerelease string `0.16.1-fork.1` in the bundle.
The pinned [Tauri macOS bundler](https://github.com/tauri-apps/tauri/blob/tauri-cli-v2.12.4/crates/tauri-bundler/src/bundle/macos/app.rs#L223)
writes `settings.version_string()` directly, and its
[settings implementation](https://github.com/tauri-apps/tauri/blob/tauri-cli-v2.12.4/crates/tauri-bundler/src/bundle/settings.rs#L1170)
returns the package version without stripping prerelease text.

A successful candidate **always** leaves real-engine testing, copied-database
testing and owner release approval marked `pending`. Do not edit a candidate
receipt to turn these into passed gates. Record later manual evidence separately
against the candidate commit and archive hash. Use an isolated test profile,
disposable copies and the [maintenance checklist](maintenance.md); private paths,
models, database files and credentials must not enter CI artifacts. A successful
CI run is not permission to install or publish. Ad-hoc signatures are not Apple
Developer ID signatures or notarization.

## Read-only upstream drift

```sh
python3 scripts/fork/manage.py drift
# Offline comparison against an already fetched revision:
python3 scripts/fork/manage.py drift --upstream-ref UPSTREAM_SHA
```

The report records the maintained HEAD, registered base, exact advertised/fetched
upstream SHA, merge base, `git merge-tree --write-tree` status/output and changed
upstream paths. It does not touch the worktree or branches, push, merge, or rebase.
Fetching and merge-tree may add local Git objects. A real merge conflict is
reported as `conflicts`; fetch/revision/comparison failures are recorded as
`error` and fail the command. Errors are never presented as an empty conflict
list. The workflow retains reports, including error diagnostics, for 30 days.

The weekly schedule is gated on this repository's default branch being `main`.
It remains inactive during the unmerged review stack and while `master` is the
default. Enabling it requires the separately approved merge/default-branch change;
manual dispatch can review drift earlier. No scheduled Codex task is created.

The register checker requires every committed path differing from the recorded
upstream base to match an existing change area or an explicit maintenance path.
A path match is a coverage check, not proof that its rationale or retirement
condition is still correct; review those during each upstream integration.
