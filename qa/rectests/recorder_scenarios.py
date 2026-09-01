# -*- coding: utf-8 -*-
"""Recorder decision harness for lore.py - the random-stop scenarios.

Imports lore as a module (boot is __main__-guarded), monkeypatches the
outside world (windows, process walks, sounds, disk finalisers, lore.log)
and drives the REAL decision functions:

    _window_track          alt-tab / minimise / move / resize -> None|split|restart
    _apply_track_act       split=save / restart=discard + direct re-attach
    the watcher gone-block (lines 8131-8235) - replicated verbatim, driven
                           through the real running_process_names /
                           _process_walk_trustworthy / _exe_has_any_window
    _note_restart / _restart_streak_now   60s decay
    _not_worth_keeping     the launch-head test

CPU only. Nothing is recorded, no file outside rectests/_tmp is touched,
lore.log is captured in memory and never written.
"""
import os
import shutil
import sys
import threading
import time
import types

sys.path.insert(0, r"D:\Gate LLC")
import lore  # noqa: E402

# ---------------------------------------------------------------- patches --
LOG = []
lore.log = lambda m: LOG.append(str(m))          # NEVER touch lore.log on disk

lore._play_sound = lambda kind: None             # no audio

CALLS = {"finalize": 0, "discard_soon": 0}
lore._finalize_async = lambda ctl, s: CALLS.__setitem__("finalize", CALLS["finalize"] + 1)
lore._discard_soon = lambda s: CALLS.__setitem__("discard_soon", CALLS["discard_soon"] + 1)

# window rect script: each _game_window_rect call pops the next answer
RECT = {"script": []}
lore._game_window_rect = lambda pname, hwnd=None: (
    RECT["script"].pop(0) if RECT["script"] else None)

WINDOWED = {"val": False}                        # _exe_has_any_window answer
lore._exe_has_any_window = lambda pname: WINDOWED["val"]

# fake psutil so the REAL running_process_names() runs on synthetic processes
PROCS = {"names": []}


class _P:
    def __init__(self, n):
        self.info = {"name": n}


lore.psutil = types.SimpleNamespace(
    process_iter=lambda attrs=None: [_P(n) for n in PROCS["names"]])


class FakeNext:
    """What _apply_track_act re-attaches with (replaces lore.Session)."""
    made = []

    def __init__(self, name):
        self.game = name
        self.suspended = False
        self.win = None
        self.tmp = None
        FakeNext.made.append(name)


lore.Session = FakeNext
lore._safe_start = lambda s, ctl: True

lore.SETTINGS["segment_seconds"] = 4
lore.SETTINGS["min_keep_seconds"] = 45
lore.SETTINGS["notify_on_record"] = False

# ---------------------------------------------------------------- fixtures --
import tempfile
BASE = tempfile.mkdtemp(prefix="rec_")
_N = [0]


def seg_dir(n):
    """A scratch segment folder holding n finished segments."""
    _N[0] += 1
    d = os.path.join(BASE, "segs_%02d" % _N[0])
    os.makedirs(d)
    for i in range(n):
        open(os.path.join(d, "seg_%05d.mp4" % i), "wb").close()
    return d


def rect(w, h, x=0, y=0, mon=0, hwnd=11, iconic=False):
    return {"w": w, "h": h, "x": x, "y": y, "mon": mon,
            "hwnd": hwnd, "iconic": iconic}


class FakeCtl:
    def __init__(self):
        self.lock = threading.Lock()
        self.force_record = threading.Event()
        self.session = None
        self.saving = 0
        self.skip_loop_on = False
        self.skip_loop_off = False
        self.muted_until = 0.0
        self.suppressed_game = None
        self.statuses = []
        self.toasts = []

    def set_status(self, s):
        self.statuses.append(s)

    def notify(self, title, msg, force=False):
        self.toasts.append((title, msg))


class FakeSession:
    def __init__(self, segs, win=None, game="thebazaar.exe"):
        self.tmp = seg_dir(segs)
        self.win = dict(win) if win else None
        self.game = game
        self.suspended = False
        self.win_paused = False
        self.afk_paused = False
        self._win_lost = 0.0
        self._win_pend = None
        self._gone_polls = 0
        self._rotating = False
        self._pause_toasted = False
        self.vproc = None
        self.calls = []

    def suspend(self):
        self.suspended = True
        self.calls.append("suspend")

    def resume(self):
        self.suspended = False
        self.calls.append("resume")

    def discard(self):
        self.calls.append("discard")

    def _stop_run(self):
        self.calls.append("_stop_run")

    def _start_run(self):
        self.calls.append("_start_run")


GAME = "thebazaar.exe"
BIG = ["filler%02d.exe" % i for i in range(24)]    # trustworthy walk (>=20)
SHORT = ["a.exe", "b.exe", "c.exe", "d.exe", "e.exe"]  # refused/cut-off walk


def gone_block_poll(session, current):
    """VERBATIM replica of the watcher's suspended-session gone test,
    lore.py lines 8136-8144 + the >=3 trigger at 8199 - but through the
    real running_process_names / _process_walk_trustworthy /
    _exe_has_any_window. Returns (game_gone, fired)."""
    _names = lore.running_process_names()
    game_gone = (current is not None
                 and lore._process_walk_trustworthy(_names)
                 and current not in _names
                 and not lore._exe_has_any_window(current))
    session._gone_polls = session._gone_polls + 1 if game_gone else 0
    return game_gone, session._gone_polls >= 3


def active_gone_poll(state, current):
    """VERBATIM replica of the ACTIVE-recording gone test, lore.py lines
    8641-8646 (elif current not in running_process_names(): gone += 1;
    if gone >= 2: stop+save) and the else: gone = 0 at 8657-8658."""
    if current is not None and current not in lore.running_process_names():
        state["gone"] += 1
        if state["gone"] >= 2:
            state["gone"] = 0
            return True                      # stop + save + (re-detect next poll)
    else:
        state["gone"] = 0
    return False


ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK      " if cond else "  FAIL    ") + name)


def finding(name, demonstrated):
    """A real-code behavior check: OK means the misbehavior IS demonstrated
    by the real code (the harness is honest); the finding itself is reported
    in prose at the end."""
    global ok, bad
    ok += bool(demonstrated)
    bad += not demonstrated
    print(("  FINDING " if demonstrated else "  FAIL    ") + name)


# =========================================================================
print("--- _window_track: alt-tab and resize decisions ---")

# 1. alt-tab: window vanishes ONE poll then returns at the same size
s = FakeSession(6, win=rect(2560, 1440))
RECT["script"] = [None, rect(2560, 1440)]
r1 = lore._window_track(None, s, GAME)          # grace poll: no ctl use
ctl = FakeCtl()
r2 = lore._window_track(ctl, s, GAME)
check("alt-tab 1-poll blink, same size: no split, never even paused",
      r1 is None and r2 is None and not s.win_paused
      and "suspend" not in s.calls)

# 1b. alt-tab: gone TWO polls (pauses), then back at the same size -> resume
s = FakeSession(6, win=rect(2560, 1440))
ctl = FakeCtl()
RECT["script"] = [None, None, rect(2560, 1440)]
outs = [lore._window_track(ctl, s, GAME) for _ in range(3)]
check("alt-tab long blink: paused then resumed into the SAME file, no split",
      outs == [None, None, None] and "suspend" in s.calls
      and "resume" in s.calls and not s.win_paused and not s.suspended)

# 2. window returns at a NEW size, >=4 segments -> split (after 2-poll settle)
s = FakeSession(6, win=rect(2560, 1440))
ctl = FakeCtl()
RECT["script"] = [None, None, rect(3440, 1440), rect(3440, 1440)]
outs = [lore._window_track(ctl, s, GAME) for _ in range(4)]
check("returns at new size with >=4 segments -> split (chapter saved)",
      outs == [None, None, None, "split"])

# 2b. same but only 2 segments -> restart (seconds-old head, discard)
s = FakeSession(2, win=rect(2560, 1440))
ctl = FakeCtl()
RECT["script"] = [None, None, rect(3440, 1440), rect(3440, 1440)]
outs = [lore._window_track(ctl, s, GAME) for _ in range(4)]
check("returns at new size with <4 segments -> restart (head thrown away)",
      outs == [None, None, None, "restart"])

# 3. resolution change MID-RECORDING (window never vanished), >=4 segments
s = FakeSession(20, win=rect(2560, 1440))       # 20 segs * 4s = 80s of footage
ctl = FakeCtl()
RECT["script"] = [rect(1920, 1080), rect(1920, 1080)]
outs = [lore._window_track(ctl, s, GAME) for _ in range(2)]
check("mid-recording resize, >=4 segments -> split on the 2nd settled poll",
      outs == [None, "split"])

CALLS["finalize"] = CALLS["discard_soon"] = 0
FakeNext.made = []
PROCS["names"] = BIG + ["TheBazaar.exe"]        # game alive, trustworthy walk
nxt = lore._apply_track_act(ctl, s, GAME, "split")
check("...and _apply_track_act SAVES it (finalize, not discard)",
      CALLS["finalize"] == 1 and CALLS["discard_soon"] == 0)
check("...and directly re-attaches a fresh session to the running game",
      isinstance(nxt, FakeNext) and FakeNext.made == [GAME])

# 4. launch-time resolution change: a seconds-old head under the keep mark
s = FakeSession(2, win=rect(2560, 1440))        # 2 segs * 4s = 8s < 45s
ctl = FakeCtl()
CALLS["finalize"] = CALLS["discard_soon"] = 0
LOG[:] = []
PROCS["names"] = SHORT                          # game gone after: no re-attach
nxt = lore._apply_track_act(ctl, s, GAME, "split")
check("launch head (8s < 45s keep mark) on split -> discarded, not filed",
      CALLS["discard_soon"] == 1 and CALLS["finalize"] == 0
      and any("changed shape after" in ln for ln in LOG))
check("_not_worth_keeping: manual recordings are never judged on length",
      lore._not_worth_keeping(s, True) is False
      and lore._not_worth_keeping(s, False) is True)

# =========================================================================
print("\n--- the suspended-session gone test (3 agreeing signals) ---")

# 5. short (untrustworthy) process walk -> never gone, however many polls
s = FakeSession(6, win=rect(2560, 1440))
PROCS["names"] = SHORT                          # 5 procs: walk was refused
WINDOWED["val"] = False
fired = any(gone_block_poll(s, GAME)[1] for _ in range(6))
check("untrustworthy walk (5 procs): 6 polls, never gone, counter stays 0",
      not fired and s._gone_polls == 0)

# 6. trustworthy walk, game missing 2 polls then back -> debounce holds
s = FakeSession(6, win=rect(2560, 1440))
PROCS["names"] = BIG                            # trustworthy, game missing
g1 = gone_block_poll(s, GAME)
g2 = gone_block_poll(s, GAME)
two_polls_held = (not g1[1] and not g2[1] and s._gone_polls == 2)
PROCS["names"] = BIG + [GAME]                   # game back on poll 3
g3 = gone_block_poll(s, GAME)
check("game missing 2 polls only -> not gone (debounce=3), then reset to 0",
      two_polls_held and not g3[0] and s._gone_polls == 0)

# 6b. game missing but it still owns a window (hidden alt-tab) -> not gone
s = FakeSession(6, win=rect(2560, 1440))
PROCS["names"] = BIG
WINDOWED["val"] = True
fired = any(gone_block_poll(s, GAME)[1] for _ in range(4))
WINDOWED["val"] = False
check("process missing but a window still exists -> never gone",
      not fired and s._gone_polls == 0)

# 7. three consecutive gone polls with a trustworthy walk -> gone
s = FakeSession(6, win=rect(2560, 1440))
PROCS["names"] = BIG
outs = [gone_block_poll(s, GAME) for _ in range(3)]
check("3 consecutive trustworthy-gone polls -> the game is gone",
      [o[1] for o in outs] == [False, False, True] and s._gone_polls == 3)

# ...and what the >=3 branch then does to a too-short auto recording
s2 = FakeSession(2)
check("gone game, 8s auto footage -> _not_worth_keeping says drop it",
      lore._not_worth_keeping(s2, False) is True)
s3 = FakeSession(20)
check("gone game, 80s footage -> kept (finalized)",
      lore._not_worth_keeping(s3, False) is False)

# =========================================================================
print("\n--- restart streak decay ---")

s = FakeSession(0)
streaks = [lore._note_restart(s) for _ in range(6)]
check("6 rapid capture restarts -> streak reads 6 (recovery gate closes)",
      streaks == [1, 2, 3, 4, 5, 6] and lore._restart_streak_now(s) == 6)
s._last_restart = time.time() - 61              # a quiet minute passes
check("streak decays after 60s: _restart_streak_now reads 0 again",
      lore._restart_streak_now(s) == 0 and s._restart_streak == 0)
check("...and the next restart counts as a NEW streak of 1",
      lore._note_restart(s) == 1)

# =========================================================================
print("\n--- case-insensitivity of process matching ---")

# 9. psutil reports "TheBazaar.exe"; the tracked name is "thebazaar.exe"
PROCS["names"] = BIG + ["TheBazaar.exe"]
names = lore.running_process_names()
check("running_process_names lowercases: TheBazaar.exe -> thebazaar.exe",
      "thebazaar.exe" in names and "TheBazaar.exe" not in names)
s = FakeSession(6, win=rect(2560, 1440))
g = gone_block_poll(s, GAME)
check("mixed-case process still matches the tracked name: not gone",
      not g[0] and s._gone_polls == 0)
st = {"gone": 0}
check("...and the active-recording check matches it too",
      not active_gone_poll(st, GAME) and st["gone"] == 0)

# =========================================================================
print("\n--- real-code findings: the trust gate exists in ONE of the three "
      "gone checks ---")

# F1. ACTIVE recording (lore.py 8641-8646): raw walk, debounce 2, no trust
# gate, no window check. Two short walks while the game is running stop the
# recording, save it, and the next poll re-detects the game and starts a new
# one: exactly the reported Bazaar mid-game auto-stop/save/restart.
PROCS["names"] = SHORT                          # walk refused mid-game
st = {"gone": 0}
stopped = [active_gone_poll(st, GAME) for _ in range(2)]
finding("ACTIVE gone check (8641): 2 untrustworthy walks STOP a live "
        "recording (suspended path would have refused)",
        stopped == [False, True])

# ...the very same two walks through the fixed suspended-path logic: held.
s = FakeSession(6, win=rect(2560, 1440))
held = not any(gone_block_poll(s, GAME)[1] for _ in range(2))
check("same 2 short walks through the suspended-path logic -> held",
      held)

# F2. _apply_track_act re-attach guard (lore.py 7731): raw walk again. A
# short walk at the moment of a split makes it believe the game closed, so
# it clears force_record and does NOT re-attach - the chapter ends and no
# follow-up recording starts from here.
s = FakeSession(20, win=rect(2560, 1440))
ctl = FakeCtl()
CALLS["finalize"] = CALLS["discard_soon"] = 0
FakeNext.made = []
PROCS["names"] = SHORT                          # game IS running; walk refused
nxt = lore._apply_track_act(ctl, s, GAME, "split")
# FIXED: a short walk no longer presumes the game closed - the split
# re-attaches to the still-running game immediately
finding("_apply_track_act (fixed): untrustworthy walk at split time -> "
        "the game is NOT presumed gone; a fresh session re-attaches",
        CALLS["finalize"] == 1 and FakeNext.made)

# F3. window-scope capture-death recovery (lore.py 8373): game_alive uses a
# raw walk. ffmpeg dying on alt-tab (the common display-mode teardown) plus
# one short walk = game_alive False = the pause-and-wait recovery is skipped
# and the chapter is split/restarted instead of resumed.
PROCS["names"] = SHORT
# FIXED: the real site now asks _looks_gone, which refuses to trust a
# short walk - the game reads alive and the alt-tab recovery proceeds
game_alive = (not lore._looks_gone(GAME))               # the fixed 8373
finding("capture-death recovery (fixed): a short walk cannot read the "
        "game as dead - recovery proceeds",
        game_alive is True)

shutil.rmtree(BASE, ignore_errors=True)
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
