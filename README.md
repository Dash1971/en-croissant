<br />
<div align="center">
  <a href="https://github.com/franciscoBSalgueiro/en-croissant">
    <img width="115" height="115" src="https://github.com/franciscoBSalgueiro/en-croissant/blob/master/src-tauri/icons/icon.png" alt="Logo">
  </a>

<h3 align="center">En Croissant</h3>

  <p align="center">
    The Ultimate Chess Toolkit
    <br />
    <a href="https://www.encroissant.org"><strong>encroissant.org</strong></a>
    <br />
    <br />
    <a href="https://discord.gg/tdYzfDbSSW">Discord Server</a>
    ·
    <a href="https://www.encroissant.org/download">Download</a>
    .
    <a href="https://www.encroissant.org/docs">Explore the docs</a>
  </p>
</div>

En-Croissant is an open-source, cross-platform chess GUI that aims to be powerful, customizable and easy to use.

## About this fork

This is a Maia-oriented fork of [En Croissant](https://github.com/franciscoBSalgueiro/en-croissant), maintained by [Dash1971](https://github.com/Dash1971/en-croissant). It keeps upstream's chess toolkit and adds support for comparing Stockfish and Maia analysis, reviewing puzzles, and preserving data. Upstream retains its existing credits and GPL-3.0 license.

The following additions and fixes are included in our [November 21, 2026 custom Mac build](docs/fork/releases/2026-11-21.json). The linked upstream PRs describe the contributions; inclusion in this fork does not imply upstream acceptance.

| Addition or fix                         | Behavior                                                                                                                                                                                                                                                                                                             | Upstream contribution                                                     |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Multicolor engine agreement arrows      | Shows agreement on displayed candidates, including Stockfish's second and third choices, with two, three, or four agreeing colors. For Stockfish/Maia agreement, the shaft keeps Stockfish's color and the head uses the agreeing Maia colors. Candidate transparency and score-based arrow thickness are preserved. | [PR #946](https://github.com/franciscoBSalgueiro/en-croissant/pull/946)   |
| Engine analysis after puzzles           | Reviews a completed puzzle on the same board, remembers individual engine selections, and returns to training without showing engine help while solving.                                                                                                                                                             | [PR #888](https://github.com/franciscoBSalgueiro/en-croissant/pull/888)   |
| Game metadata and autosave preservation | Preserves ECO codes, extra PGN tags and partial dates through database conversion and editing; serializes autosaves so newer edits are retained.                                                                                                                                                                     | [PR #1103](https://github.com/franciscoBSalgueiro/en-croissant/pull/1103) |
| Legacy puzzle database preservation     | Keeps unsupported legacy SQLite puzzle files during discovery instead of deleting them. This preserves the files; it does not convert them into the current format.                                                                                                                                                  | [PR #1106](https://github.com/franciscoBSalgueiro/en-croissant/pull/1106) |
| Duplicate Maia startup fix              | Prevents duplicate pending engine starts, cancels starts for closed boards, and cleans up owned worker processes. Analysis boards can still run in the background until stopped or closed.                                                                                                                           | [PR #1122](https://github.com/franciscoBSalgueiro/en-croissant/pull/1122) |

### Fork maintenance

The [bounded maintenance pass](https://github.com/Dash1971/en-croissant/issues/1) was approved and merged on November 23, 2026. `main` is the maintained default branch; `master` stays an upstream mirror. The repository includes a documented fork baseline, manual-only fork updates, and unpublished Mac candidates with source/build receipts and read-only upstream drift reports. Merging these changes does not update an installed app or publish a downloadable release. Real-engine and copied-database testing remain separate release gates for future builds.

See the [maintenance contract](docs/fork/maintenance.md) and [change register](docs/fork/changes.json) for scope, validation and the conditions for retiring each fork change. The generic build instructions below describe upstream; maintained candidate builds must follow the [fork distribution contract](docs/fork/updates.md) and [candidate build instructions](docs/fork/releasing.md).

## Features

- Store and analyze your games from [lichess.org](https://lichess.org) and [chess.com](https://chess.com)
- Multi-engine analysis. Supports all UCI engines
- Prepare a repertoire and train it with spaced repetition
- Simple engine and database installation and management
- Absolute or partial position search in the database

<img src="https://github.com/franciscoBSalgueiro/encroisssant-site/blob/master/public/showcase.webp" />

## Building from source

Refer to the [Tauri documentation](https://tauri.app/start/prerequisites/) for the requirements on your platform.

En-Croissant uses pnpm as the package manager for dependencies. Refer to the [pnpm install instructions](https://pnpm.io/installation) for how to install it on your platform.

```bash
git clone https://github.com/franciscoBSalgueiro/en-croissant
cd en-croissant
pnpm install
pnpm build
```

The built app can be found at `src-tauri/target/release`

## Donate

If you wish to support the development of this GUI, you can do so [here](https://encroissant.org/support). All donations are greatly appreciated!

## Contributing

For contributing to this project please refer to the [Contributing guide](./CONTRIBUTING.md).

## License

This software is licensed under GPL-3.0 License.
Some bundled chess piece sets are distributed under separate licenses.
