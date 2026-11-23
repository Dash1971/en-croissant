# Maintained fork updates

The maintained distribution uses manual releases at
<https://github.com/Dash1971/en-croissant/releases>. Startup performs no update
check. **Check for Updates**, in either the native menu or the in-app menu, opens
that fixed page in the browser. It does not query an updater feed, download an
installer, install an update, or relaunch the app.

This is an opt-in build policy. The default upstream build retains its existing
automatic check and user-approved installation flow. There is no change to the
app name, application identifier, directory preferences, databases, or engines.

## Build contract

Use all three settings together:

1. Cargo feature: `maintained-fork`.
2. Frontend environment: `VITE_EN_CROISSANT_DISTRIBUTION=maintained-fork`.
3. Tauri overlay: `src-tauri/tauri.maintained.conf.json`.

For example, from the repository root, using the package manager pinned in
`package.json`:

```sh
VITE_EN_CROISSANT_DISTRIBUTION=maintained-fork pnpm tauri build \
  --features maintained-fork \
  --config src-tauri/tauri.maintained.conf.json
```

The overlay sets version `0.16.1-fork.1`, clears updater endpoints, and disables
updater artifacts. It inherits the existing `org.encroissant.app` identifier and
product name. Tauri applies the overlay as a JSON merge patch: an empty endpoints
array replaces the upstream array; it does not append to it. The base
`tauri.conf.json` remains unchanged.

The Cargo feature excludes native updater plugin registration. This prevents an
accidental frontend updater invocation from reaching the official updater even
if the frontend flag is omitted. The frontend flag avoids those invocations and
implements the manual release-page action. Empty endpoints are a third defense:
the pinned updater returns `EmptyEndpoints` before attempting a network request,
with no built-in official fallback endpoint.

These defenses do not replace the paired build contract. Do not label or share a
maintained candidate built with only some settings, and do not reuse a `dist`
directory built for another distribution. Candidate tooling must verify all three
settings and rebuild the frontend. An unknown or misspelled frontend value is not
a supported maintained build. No signing key, update manifest, updater signature,
or published release is needed to review this policy.

## Review and validation

`src/utils/updates.test.ts` exercises the functions called by app startup and the
shared menu action. It verifies that maintained startup makes no updater call;
manual checks open only the fork release page, including failure without
fallback; and the default upstream check, consent, installation, relaunch,
no-update feedback and error behavior remain intact.

```sh
pnpm test src/utils/updates.test.ts
pnpm exec tsc --noEmit
```

Before distributing a candidate, validate the merged Tauri configuration and
build the native binary with `maintained-fork`. Native testing should use an
isolated test identifier and copied data; the distribution overlay itself must
retain the production identifier so an eventual approved manual replacement
continues to use the existing settings and directories. Verify startup does not
request the official feed and Check for Updates opens the fork release page.
Reviewing or building a candidate does not authorize installation or publication.

## Manual replacement and retirement

A future approved release is installed manually after reviewing its notes and
compatibility checks. Quit the app, keep a backup of the existing app bundle, and
replace the bundle; keep database and engine directories in place. Database
migrations and data compatibility require their own validation and are not
performed by this update policy.

Retain this policy for as long as maintained fork builds can differ from official
builds. Retire or replace it only after reviewing a trusted fork-specific update
channel and its signing/rollback requirements, or after an explicit decision to
return completely to upstream. Removing a single guard while continuing to ship
fork-only changes is not a retirement plan.
