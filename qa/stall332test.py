# -*- coding: utf-8 -*-
"""3.32 drop D - THE ENCODER HEARTBEAT (_stall_track) and the black
guard's honesty under a stuck ticker.

Drives the REAL _stall_track lifted out of lore.py by name against a
fake session, feed and vproc: frames advancing beat after beat (never
a kill), a count stuck short of the patience (nothing yet), a count
stuck for the patience (one kill, one log line, 'killed'), the beat
after the kill (the process is dead: the death branch's business, no
second kill), every stand-down (suspended, win_paused, _rotating, no
feed on the ddagrab path, no first frame yet, frames_out 0, no vproc),
a frozen game (frames_in stuck while the ticker re-sends: not a stall),
a dead ticker under a live ffmpeg (the same condition, the same kill);
then the REAL _black_track with every witness injected, answering None
under a stuck ticker even with a thirty-second black clock, and its
verdict as before once the ticker moves. Source pins: the call site sits
before the black guard in the watcher's healthy branch and continues on
the very next beat; _stop_run never waits on a dead encoder; the
heartbeat writes no sidecar (the mtime law). Nothing on disk is touched."""
import ast
import io
import os
import re
import sys
import textwrap
import threading
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
TREE = ast.parse(SRC)

ok = bad = 0


def check(what, cond):
    global ok, bad
    if cond:
        ok += 1
        print("  OK  ", what)
    else:
        bad += 1
        print("  FAIL", what)


def extract(name, ns):
    for node in TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                SRC.splitlines()[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name)


def body_of(name):
    for node in TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(SRC.splitlines()[node.lineno - 1:node.end_lineno])
    raise AssertionError(name)


def method_src(cls_name, name):
    for node in TREE.body:
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for f in node.body:
                if isinstance(f, ast.FunctionDef) and f.name == name:
                    return "\n".join(
                        SRC.splitlines()[f.lineno - 1:f.end_lineno])
    raise AssertionError(cls_name + "." + name)


def const(name):
    m = re.search(r"^%s\s*=\s*([0-9.]+)" % re.escape(name), SRC, re.M)
    return float(m.group(1))


# ---------------------------------------------------------------------------
print("--- the heartbeat ---")
ns = {"time": time}
LOGS = []
ns["log"] = lambda m: LOGS.append(m)
ns["_STALL_PATIENCE"] = const("_STALL_PATIENCE")
_stall_track = extract("_stall_track", ns)
PATIENCE = ns["_STALL_PATIENCE"]
check("the patience is ten seconds - two beats at the five-second poll",
      PATIENCE == 10.0)


class Proc:
    """A stand-in for the ffmpeg Popen: alive until killed."""

    def __init__(self):
        self.rc = None
        self.kills = 0

    def poll(self):
        return self.rc

    def kill(self):
        self.kills += 1
        self.rc = -9


class Feed:
    def __init__(self, first=True, frames_out=300, frames_in=300,
                 dead=False):
        self._first = threading.Event()
        if first:
            self._first.set()
        self.frames_out = frames_out
        self.frames_in = frames_in
        self.dead = dead
        self.black_since = None
        self.stalled_since = None


class Ctl:
    def __init__(self):
        self.toasts = []
        self._black_toasted = set()

    def notify(self, title, msg, force=False):
        self.toasts.append((title, msg, force))


def sess(feed=None, proc=None, **kw):
    s = types.SimpleNamespace()
    s._wgc = feed if feed is not None else Feed()
    s.vproc = proc if proc is not None else Proc()
    s.suspended = False
    s.win_paused = False
    s._rotating = False
    s.game = "hearthstone.exe"
    s.win = {"hwnd": 77, "mon": 0, "x": 0, "y": 0, "w": 2536, "h": 1312}
    s.cap_wh = (2536, 1312)
    s.audio = None
    s.tmp = ""
    for k, v in kw.items():
        setattr(s, k, v)
    return s


ctl = Ctl()

# frames advancing: never a kill, the mark follows the count
s = sess()
outs = []
for beat, n in ((0.0, 300), (5.0, 600), (10.0, 900), (15.0, 1200)):
    s._wgc.frames_out = n
    outs.append(_stall_track(ctl, s, now=1000.0 + beat))
check("frames advancing beat after beat: None every beat, no kill",
      outs == [None] * 4 and s.vproc.kills == 0 and LOGS == [])
check("...and the mark follows the count (frames_out, wall)",
      s._stall_seen == (1200, 1015.0))

# stuck: nothing until the patience, then one kill
s = sess()
s._wgc.frames_out = 300
r0 = _stall_track(ctl, s, now=1000.0)
r1 = _stall_track(ctl, s, now=1005.0)
r2 = _stall_track(ctl, s, now=1009.9)
check("a count that has not moved: None at 0, 5 and 9.9 s (patience is 10)",
      (r0, r1, r2) == (None, None, None) and s.vproc.kills == 0
      and LOGS == [] and s._stall_seen == (300, 1000.0))
r3 = _stall_track(ctl, s, now=1010.0)
check("stuck for 10 s: 'killed', exactly one kill, one log line",
      r3 == "killed" and s.vproc.kills == 1 and len(LOGS) == 1)
check("...the line says what happened and what comes next",
      "stopped taking frames" in LOGS[0] and "10 s" in LOGS[0]
      and "same recording" in LOGS[0])
check("...the process is dead for the death branch's beat",
      s.vproc.poll() is not None)
check("...and no toast: a silent recovery, log only", ctl.toasts == [])
r4 = _stall_track(ctl, s, now=1015.0)
check("the beat after the kill: None, no second kill, no second line "
      "(vproc is dead - the death branch's business now)",
      r4 is None and s.vproc.kills == 1 and len(LOGS) == 1)
check("...and the mark was dropped with the kill (a new run starts clean)",
      s._stall_seen is None)
del LOGS[:]

# a count that moves after a short stall resets the clock
s = sess()
s._wgc.frames_out = 300
_stall_track(ctl, s, now=1000.0)
_stall_track(ctl, s, now=1008.0)
s._wgc.frames_out = 301
check("one frame through after 8 s: the clock restarts from that beat",
      _stall_track(ctl, s, now=1009.0) is None
      and s._stall_seen == (301, 1009.0))
check("...so a 9 s stall after that is still nothing",
      _stall_track(ctl, s, now=1018.0) is None and s.vproc.kills == 0)


def stuck_session(**kw):
    """A session whose count has been stuck for 30 s - a kill unless
    something stands the heartbeat down."""
    s = sess(**kw)
    s._wgc.frames_out = 300
    s._stall_seen = (300, 970.0)
    return s


check("(the fixture kills when nothing stands it down)",
      _stall_track(ctl, stuck_session(), now=1000.0) == "killed")
del LOGS[:]
for flag in ("suspended", "win_paused", "_rotating"):
    s = stuck_session(**{flag: True})
    check("%s: None and no kill, however long the count sat" % flag,
          _stall_track(ctl, s, now=1000.0) is None and s.vproc.kills == 0)
s = sess(_wgc=None)
s._wgc = None
s._stall_seen = (300, 970.0)
check("no feed (the ddagrab path captures inside ffmpeg): None, ever",
      _stall_track(ctl, s, now=1000.0) is None and s.vproc.kills == 0)
s = stuck_session()
s._wgc._first.clear()
check("the first frame not yet: None (begin()'s timeout owns the start)",
      _stall_track(ctl, s, now=1000.0) is None and s.vproc.kills == 0)
s = stuck_session()
s._wgc.frames_out = 0
s._stall_seen = None
check("frames_out 0 on a fresh run: the mark is seeded, no kill yet",
      _stall_track(ctl, s, now=1000.0) is None and s.vproc.kills == 0
      and s._stall_seen == (0, 1000.0))
s = stuck_session()
s.vproc = None
check("no vproc (a failed resume): None - the death branch enters recovery",
      _stall_track(ctl, s, now=1000.0) is None)
s = stuck_session()
s.vproc.rc = 1
check("vproc already dead: None, never a kill on a corpse",
      _stall_track(ctl, s, now=1000.0) is None and s.vproc.kills == 0)
check("...and none of those wrote a line", LOGS == [])

# a frozen game is not a stall: the ticker re-sends, frames_out advances
s = sess()
s._wgc.frames_in = 40
outs = []
for beat, n in ((0.0, 300), (5.0, 600), (10.0, 900), (15.0, 1200)):
    s._wgc.frames_out = n
    outs.append(_stall_track(ctl, s, now=1000.0 + beat))
check("a frozen game (frames_in stuck, frames_out advancing): None, no kill",
      outs == [None] * 4 and s.vproc.kills == 0)

# a dead ticker under a live ffmpeg is the same condition
s = sess()
s._wgc.dead = True
s._wgc.frames_out = 300
r = [_stall_track(ctl, s, now=1000.0), _stall_track(ctl, s, now=1005.0),
     _stall_track(ctl, s, now=1010.0)]
check("a dead ticker (stdin closed) with ffmpeg still alive after 10 s: "
      "the same kill", r == [None, None, "killed"] and s.vproc.kills == 1)
check("kill() raising never escapes the beat",
      (lambda s: (setattr(s.vproc, "kill",
                          lambda: (_ for _ in ()).throw(OSError("x")))
                  or _stall_track(ctl, s, now=1000.0) == "killed"))(
          stuck_session()))
del LOGS[:]

# ---------------------------------------------------------------------------
print("\n--- the black guard is honest about a stuck ticker ---")
tns = {"time": time, "SETTINGS": {"black_guard": True,
                                  "min_keep_seconds": 45}}
BLOGS = []
tns["log"] = lambda m: BLOGS.append(m)
tns["_BLACK_PATIENCE"] = const("_BLACK_PATIENCE")
tns["_BLACK_PATIENCE_BLIND"] = const("_BLACK_PATIENCE_BLIND")
tns["_STALL_PATIENCE"] = PATIENCE
tns["_WGC_BLACK"] = {}
W = {"rect": {"hwnd": 77, "mon": 0, "x": 0, "y": 0, "w": 2536, "h": 1312},
     "fg": 77, "screen": 120.0, "idle": 300.0, "loud": False,
     "captured": 60}
tns["_game_window_rect"] = lambda p, hwnd=None: W["rect"]
tns["_foreground_root"] = lambda: W["fg"]
tns["_root_hwnd"] = lambda h: h
tns["_screen_probe"] = lambda r: W["screen"]
tns["_afk_idle_recent"] = lambda *a: W["idle"]
tns["_ring_loud"] = lambda aud, within=10.0: W["loud"]
tns["_captured_seconds"] = lambda s: W["captured"]
_black_track = extract("_black_track", tns)

NOW = 5000.0
s = sess()
s._wgc.black_since = NOW - 30.0
s._wgc.frames_out = 300
s._stall_seen = (300, NOW - 30.0)
check("black for 30 s, in front, screen lit - but the ticker stuck 30 s: "
      "None (a black clock that stopped ticking is not evidence)",
      _black_track(ctl, s, "hearthstone.exe", now=NOW) is None
      and BLOGS == [] and tns["_WGC_BLACK"] == {})
s._stall_seen = (300, NOW - 9.0)
check("...the ticker stuck only 9 s: the guard judges as before ('rotate' "
      "at the same size)",
      _black_track(ctl, s, "hearthstone.exe", now=NOW) == "rotate")
tns["_WGC_BLACK"].clear()
s._stall_seen = (299, NOW - 30.0)
s._black_probe_t = 0.0
check("...a stale mark for a count that has since moved does not gag it",
      _black_track(ctl, s, "hearthstone.exe", now=NOW) == "rotate")
s2 = sess()
s2._wgc.black_since = NOW - 30.0
s2._black_probe_t = 0.0
tns["_WGC_BLACK"].clear()
check("...and a session with no mark at all (drop A's own fixtures) is "
      "judged exactly as before",
      _black_track(ctl, s2, "hearthstone.exe", now=NOW) == "rotate")

# ---------------------------------------------------------------------------
print("\n--- the source ---")
call = "if _stall_track(ctl, session):"
check("the call site sits in the watcher's healthy branch, before the "
      "black guard", SRC.count(call) == 1
      and SRC.index(call) < SRC.index("bv = _black_track(ctl, session, current)")
      and SRC.index("_afk_track(ctl, session, current)") < SRC.index(call))
check("...and a kill continues on the very next beat (the death branch's)",
      "if _stall_track(ctl, session):\n"
      "                        _interruptible_sleep(ctl, 0.3)\n"
      "                        continue\n" in SRC)
sb = body_of("_stall_track")
check("the heartbeat kills only a live process it can see, and returns "
      "'killed' from that one path",
      "vproc.kill()" in sb and sb.count("return \"killed\"") == 1
      and "if vproc is None or vproc.poll() is not None:" in sb)
check("the heartbeat writes nothing to disk (the mtime law: no sidecar "
      "leaves this drop)",
      "open(" not in sb and "_atomic_write_json" not in sb
      and "_ai_sidecar" not in sb and "os." not in sb)
check("the heartbeat is a few attribute reads a beat (no window rect, no "
      "screen probe, no segment walk)",
      "_game_window_rect" not in sb and "_screen_probe" not in sb
      and "_list_segments" not in sb and "getmtime" not in sb)
stop = method_src("_RecordSession", "_stop_run") \
    if any(isinstance(n, ast.ClassDef) and n.name == "_RecordSession"
           for n in TREE.body) else ""
if not stop:
    for node in TREE.body:
        if isinstance(node, ast.ClassDef) and any(
                isinstance(f, ast.FunctionDef) and f.name == "_stop_run"
                for f in node.body):
            stop = method_src(node.name, "_stop_run")
            break
check("_stop_run after the kill never waits on the corpse: the 20 s wait "
      "is gated on a live poll(), and the feed's stop() joins a ticker "
      "whose write the broken pipe has already ended",
      "if self.vproc and self.vproc.poll() is None:\n"
      "            try:\n"
      "                self.vproc.wait(timeout=20)" in stop
      and "self._ticker_t.join(timeout=3)" in SRC
      and "except Exception:\n                self.dead = True"
      "                  # encoder went away" in SRC)
bt = body_of("_black_track")
check("the black guard reads the heartbeat's mark and stands down on a "
      "stuck ticker, before its own patience",
      "_stall_seen" in bt and "_STALL_PATIENCE" in bt
      and bt.index("_STALL_PATIENCE") < bt.index("if dark < _BLACK_PATIENCE:"))
check("no second constant: the guard and the heartbeat share one patience",
      SRC.count("_STALL_PATIENCE = ") == 1)


# ---------------------------------------------------------------------------
print("--- the wedge at birth, and a fresh run's clean slate ---")
LOGS[:] = []
f0 = Feed(first=True, frames_out=0, frames_in=40)
p0 = Proc()
s0 = sess(feed=f0, proc=p0)
check("frames_out 0 with the first frame in hand seeds the mark, no kill",
      _stall_track(Ctl(), s0, now=1000.0) is None and p0.kills == 0
      and getattr(s0, "_stall_seen", None) == (0, 1000.0))
check("...still quiet inside the patience",
      _stall_track(Ctl(), s0, now=1000.0 + PATIENCE - 0.5) is None and p0.kills == 0)
check("...and the encoder that never took a frame is killed at the patience",
      _stall_track(Ctl(), s0, now=1000.0 + PATIENCE) == "killed" and p0.kills == 1
      and any("stopped taking frames" in m for m in LOGS))
f1 = Feed(first=True, frames_out=0, frames_in=40)
p1 = Proc()
s1 = sess(feed=f1, proc=p1)
_stall_track(Ctl(), s1, now=2000.0)
f1.frames_out = 120
check("a slow start that begins taking frames is never killed",
      _stall_track(Ctl(), s1, now=2000.0 + PATIENCE + 5) is None and p1.kills == 0)
check("every run starts with no stall mark (_start_run clears it beside _wgc)",
      re.search(r"self\._wgc = None\r?\n\s+self\._stall_seen = None", SRC) is not None)
check("the librarian's stand-down also answers a question at once (no 60 s wait)",
      re.search(r"def _emb_srv[\s\S]{0,900}down_t[\s\S]{0,200}_EMB_STANDDOWN[\s\S]{0,120}return None", SRC) is not None)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
