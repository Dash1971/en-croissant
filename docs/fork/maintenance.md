# Maintained fork: review contract

This is the proposed maintenance contract for the Maia-oriented En Croissant
distribution in `Dash1971/en-croissant`. The existing application and upstream
credits are retained. Product renaming and new features are separate decisions.

## Source of truth

- `master` is an untouched, fast-forward-only mirror of upstream `master`.
- `main` is the proposed maintained application branch. It initially points to
  unchanged upstream as a review anchor. The baseline PR collects the complete
  previously installed application; it does not install an app.
- The default branch remains `master` during review. Changing it to `main`,
  configuring branch protections, merging this stack and publishing a release
  are later owner-approved steps, not side effects of opening the PRs.
- Preserve published history. Merge selected upstream revisions through reviewed
  PRs; never rebase or force-push released maintained history. Unmerged review
  branches may be updated normally. Urgent upstream fixes use `cherry-pick -x`.
- Offer general bug fixes upstream on independent branches based on upstream.
  Fork maintenance and shipping do not depend on upstream PR acceptance.

The complete existing application baseline is commit
`86c9edcca5144688479a8fc9d9f12175f9a49d03`, based on upstream
`c8473936129bb6f1a919882e45527daa4d3a1e34`. Its local installed-build evidence is
recorded in [the historical receipt](releases/2026-11-21.json). Do not interpret
that receipt as validation of later maintenance commits.

## Register the upstream delta

[changes.json](changes.json) records the five existing change areas, their paths,
purpose, upstream PR, verification and retirement condition. Keep it current in
the same PR that changes the delta or upstream base. Shared paths may appear in
more than one area. Separate maintenance paths are explicitly listed.

Keep fork additions in focused modules where practical and upstream edits small.
Extract code when actual coupling or merge conflicts justify it; this contract
does not require a speculative framework or application rewrite. When upstream
provides equivalent behavior, test parity and retire the redundant fork change.

## Upstream updates

Review drift weekly, then consider stable upstream releases and urgent fixes.
The report is read-only: it must identify its source revisions and errors rather
than claim zero changes/conflicts after a failed fetch or comparison. It must
not merge, push, install, or rewrite source automatically.

An upstream integration PR records the selected old/new bases, conflicts and
decisions for each registered departure. Review data-format changes separately.
Run frontend and native checks and the applicable copied-data/manual tests.
Only update the register's upstream base after resolving and reviewing the merge.

## Candidate and release gates

The release workflow and updater policy are separate stacked review PRs. Until
they are approved, this document is a contract, not evidence that automation or
a custom update feed is active.

A candidate must identify the exact fork commit/tree and upstream base, lockfile
hashes, tool versions, architecture, test receipts, signing status and output
hashes. Build from reviewed clean source. Generated output is not permission to
ignore arbitrary source changes. CI artifacts are candidates, not published
releases or proof of manual validation. Do not promise byte-identical binaries
across different macOS SDK/toolchain/signing environments.

Before a future release or installation:

1. Pass lint, frontend tests, native Rust tests (including engine lifecycle),
   native build and candidate/evidence verification for the exact revision.
2. Test applicable migrations, metadata, autosave and puzzle discovery against
   disposable copies. Preserve originals and compare their hashes. An extension
   rename is not a database conversion.
3. Verify real-engine cold startup, rapid navigation, engine choices, background
   analysis and close/quit cleanup. Check arrows and post-puzzle review when
   affected. Personal engines/models/databases are not CI fixtures or uploads.
4. Obtain owner approval to merge and separately to publish/install. Keep the
   prior app and data-format-compatible originals available for rollback.

## Distribution and data policy

The proposed fork channel uses manual installation from reviewed fork releases.
An official updater must not replace a fork candidate. A signed automatic fork
feed, signing/notarization credentials and release publishing are later work.
The fork-update PR must guard both startup and manual checks and retain official
behavior for ordinary upstream builds.

This pass does not change the application identifier, user directory settings,
database formats or installed app. Future distribution-identity changes need an
explicit migration plan. Runtime preferences, iCloud paths, private data and
model weights stay outside source/release evidence.

## Review order

1. Existing application baseline, register and this contract.
2. Custom distribution/manual update policy, based on the baseline branch.
3. Native CI, candidate build receipts and read-only drift checks, based on the
   distribution branch.

All three PRs remain unmerged until reviewed and approved. After each approved
merge, retarget the next PR and verify its exact head/checks. No tag, release,
installed build or default-branch switch is authorized by this review stack.
