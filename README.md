# LORE — a game recorder bound as a book

LORE is a Windows game recorder for one power user, wrapped in a skeuomorphic
leather tome. It watches for games, records them automatically (ffmpeg
desktop-duplication → AMD AV1 hardware encoding, HDR-aware), and shelves the
recordings in a book you leaf through: every game is a chapter, every session a
page, with an in-app player, a multi-piece trim/stitch editor, a replay-clip
hotkey, and an optional clip-to-Discord share.

Created by Gate.

---

## Architecture — deliberately two files

| File | What it is |
|---|---|
| `lore.py` | The entire backend: game detection, the ffmpeg recording engine, HDR→SDR finishing queue, thumbnails, the library scanner, a tokened loopback media server, the tray, global hotkeys, popups, and the JS↔Python bridge (`_JsApi`). |
| `ui.html` | The entire frontend in ONE self-contained file: vanilla JS (a tiny `el()` helper, no framework, no build step), inline CSS, and embedded CC0 textures/fonts as data URIs. |

The UI runs in WebView2 via **pywebview** (frameless window). Every method on
`_JsApi` is callable from JS as `api.<name>()`. A mock bridge near the top of
`ui.html` powers browser-only preview during development.

There is intentionally **no bundler, no npm, no framework** — the point is that
one person can read all of it.

## Things a reviewer might care about

- **Fully offline.** The app makes no network calls of its own. The only
  outbound traffic possible is the user-configured Discord webhook share, and
  `_post_discord_file` refuses any host that is not `discord.com` /
  `discordapp.com`.
- **The in-app player** streams from a loopback-only HTTP server
  (`_start_media_server`) because WebView2 rejects `file://` media. It binds
  `127.0.0.1`, uses a fresh random token per launch, and only serves files that
  live inside the recordings library.
- **The storage cap sweeper and temp-file cleanup only ever touch files LORE
  itself wrote** (its own naming patterns, in its own shelves). Nothing else on
  disk is ever deleted.
- **Recording engine:** ffmpeg `ddagrab` desktop duplication → `av1_amf`
  (hardware) with measured HDR→SDR tone-mapping done later, at idle, at
  below-normal priority, and never while the user is watching or recording.
- **Crash safety:** finished recordings are recovered on restart from any
  shelf; a transient file lock can never delete a recording; edits write to
  temp names and replace atomically.

## Building it

You need (once): Python 3, [Inno Setup 6](https://jrsoftware.org/isdl.php),
and an ffmpeg build — put `ffmpeg.exe` **and** `ffprobe.exe` in `ffmpeg\bin\`
next to `build.bat` (not committed here; grab a build from gyan.dev).

Then double-click **`build.bat`**. It installs the Python deps, bundles the app
with PyInstaller, and compiles `installer.iss` into a single shareable
`installer_output\LoreSetup.exe`.

Friends need nothing installed — the installer carries everything.

## Repo map

```
lore.py            the backend (see the section banners inside)
ui.html            the frontend (data layer → views → player/editor → boot)
build.bat          one-click build → LoreSetup.exe
installer.iss      Inno Setup script
version.txt        version resource stamped into Lore.exe
known_games.txt    baked list of windowed games the watcher recognises
lore.ico           the app icon (drawn in code — see _tome_mark in lore.py)
app_launchers/     tiny optional .bat helpers (autostart, tray commands)
HOW-TO-RUN.txt     drop-in update notes for an already-installed copy
```

## Credits

- Textures: brown leather + dark wood from **Poly Haven**, paper from
  **ambientCG** — all CC0, baked and embedded as data URIs in `ui.html`.
- Everything else: Gate.

## License

Source-visible for review. All rights reserved — ask before reusing pieces of
it.
