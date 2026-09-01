# qa/ — the deterministic regression roster

This is the suite the pre-ship checks run — committed so an external
review can replay the numbers instead of taking the briefing's word
for them (a fair complaint from the v3.23 review).

## What these are

Development-only. Nothing here ships, nothing here touches the
production UI, and nothing here asks the user to do anything — the
product stays hands-off; QA is where human judgment lives.

- `codex32*test.py` — the evidence guards (title/summary name guard,
  Ask verification tiers, describer quote checks, the wallet, the
  auditor's ear gates).
- `asr322test.py` — the transcriber's physics gate, short-echo arm,
  script-derived language (AST-extracts the nested guards from
  `ai/asr_worker.py` and drives them as written).
- `afk*.py` — AFK detection and the AFK catch-up override (including
  a 120-round concurrency storm).
- `fresh319test.py`, `fleet319test.py`, `sched*`, `freeze*`, `aud30*`,
  `silvertest.py`, `pairtest.py`, `gatetest295.py` — the scheduler,
  queue, attic, audit and marks contracts.
- `mic*`, `audiotest.py`, `midchange.py`, `rectests/` — recorder and
  audio-path scenarios.
- `paneltest.js` + `checkui.js` — the UI panels driven under node
  against `ui.html`'s own script (mock `api`).

## How to run

Everything assumes this machine's layout (`D:\Gate LLC`, `D:\Records`
read-only). Python suites: `python <suite>.py` — each prints
`N ok, M failed` and exits nonzero on failure. JS: `node paneltest.js`.

Run the lot:

```bat
qa\run_all.bat
```

## Rules the suites encode (do not "fix" a test to pass)

- Stubs must have the same shape as what they replace (`*args, **k`) —
  a zero-arg stub once hid a TypeError that made a whole feature dead
  on arrival.
- Tests assert OUTCOMES on real functions (AST-extraction for nested
  ones), never re-implementations.
- A test that asserts a snapshot of the library's state (rather than
  an invariant) is a bug; fix the test, not the shelf.
- `D:\Records` is read-only, always. Never send requests to ports
  8906–8912 (live model servers).
