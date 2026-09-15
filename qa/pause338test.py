# -*- coding: utf-8 -*-
"""3.38 drop P - what he saw on 15 Sep, each proved on a lifted twin.

P2  A PAUSED RECORDING IS NOT "PLAYING". Hearthstone sat minimised from
    01:43; the catch-up armed at 01:53 and ran until 16:44 - 254
    transcripts and 255 sound passes on old nights and not one
    description or audit, because the describer's and the audit's gate
    read `ctl.session is not None` and a SUSPENDED session counted as a
    game on the card. "it keeps looping". Fix: one helper _session_live
    (a session that is not suspended); the five gates read it.
P3  A RECORDING PAUSED FOR HOURS IS SAVED, NOT KEPT OPEN. The AFK pause
    and the window pause kept the session for ever; his Hearthstone
    recording resumed after fifteen hours the moment he restored the
    window and was finalised in front of him. "it's saving after I
    didn't touch the thing for like 16 hours". Fix: pause_close_minutes
    (30; 0 = never) - a session paused by AFK or by a lost/minimised
    window that long, WITH footage, is finalised by the watcher through
    the Stop & Save road; the game is suppressed until real input.
P4  THE RING. flagsWatch (3.36 UI-W1) re-asks only the paths a ring of
    recent landings names - and the backend had no ring, so every
    landing it could not explain was a blanket. Fix: _ai_landed(path)
    at every landing site, a 16-entry ring, ai_status carries it. (The
    page's half - the map that is never emptied - is pausetest.js.)

Everything is AST-lifted out of lore.py's SOURCE TEXT (the tree, then
the PARITY_BASE commit) into stub namespaces on tempdirs with a hand
clock. No model, no port, no device, no process, and nothing under
D:\\Records or %LOCALAPPDATA%\\Lore is read or written; lore.py is never
imported. The words in the fixtures are game words, never a person.
"""
import ast
import datetime as _dt
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time as _real_time
import types

ROOT = r"D:\Gate LLC"

# THE PARITY BASE IS A COMMIT, NOT HEAD. 747f76a is 3.37, the tree he was
# running on 15 Sep; HEAD would make every "before" witness vanish the
# moment this drop lands.
PARITY_BASE = "747f76a"

ok = bad = 0


def check(name, cond, extra=""):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  ok    " if cond else "  FAIL  ") + name
          + ("   [" + extra + "]" if extra else ""))


SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
BASE = subprocess.run(["git", "show", PARITY_BASE + ":lore.py"],
                      cwd=ROOT, capture_output=True).stdout.decode("utf-8")
assert "def _ai_tick" in BASE, "git show of the parity base failed"
USRC = io.open(os.path.join(ROOT, "ui.html"), encoding="utf-8").read()

_TREES = {}


def tree_of(src):
    t = _TREES.get(id(src))
    if t is None:
        t = _TREES[id(src)] = ast.parse(src)
    return t


def lift(src, name, ns):
    """a top-level function or assignment, exec'd into ns"""
    lines = src.splitlines()
    for node in tree_of(src).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                lines[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name
                for t in node.targets):
            code = "\n".join(lines[node.lineno - 1:node.end_lineno])
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name + " not found at top level")


def fsrc(src, name):
    lines = src.splitlines()
    for node in tree_of(src).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) \
                and node.name == name:
            return "\n".join(lines[node.lineno - 1:node.end_lineno])
    raise AssertionError(name)


def msrc(src, cls, name):
    lines = src.splitlines()
    for node in tree_of(src).body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for f in node.body:
                if isinstance(f, ast.FunctionDef) and f.name == name:
                    return "\n".join(lines[f.lineno - 1:f.end_lineno])
    raise AssertionError(cls + "." + name)


def lift_method(src, cls, name, ns):
    """a method, exec'd into ns as a plain function taking self"""
    exec(compile(textwrap.dedent(msrc(src, cls, name)),
                 "<" + cls + "." + name + ">", "exec"), ns)
    return ns[name]


CLOCK = [_real_time.time()]


class QTime(object):
    @staticmethod
    def time():
        return CLOCK[0]

    @staticmethod
    def sleep(s):
        CLOCK[0] += float(s)


class QThread(object):
    """the worker runs INSIDE start(): a beat and its job are one call"""
    def __init__(self, target=None, daemon=None, name=None, args=()):
        self._t, self._a = target, args

    def start(self):
        if self._t:
            self._t(*self._a)

    def join(self, *a):
        pass


class QThreading(object):
    RLock = staticmethod(threading.RLock)
    Lock = staticmethod(threading.Lock)
    Thread = QThread
    local = staticmethod(threading.local)
    get_ident = staticmethod(threading.get_ident)


class Sess(object):
    """a recording as the gates and the close road see it"""
    def __init__(self, suspended=False, afk=False, win=False,
                 paused_min=None, game="somegame.exe", tmp=""):
        self.suspended = suspended
        self.afk_paused = afk
        self.win_paused = win
        self.paused_at = ((CLOCK[0] - paused_min * 60)
                          if paused_min is not None else None)
        self.game = game
        self.tmp = tmp


class Ctl(object):
    def __init__(self, session=None):
        self.session = session
        self.saving = 0
        self.status = ""
        self.lock = threading.Lock()
        self.force_record = threading.Event()
        self.watching = threading.Event()
        self.suppressed_game = None
        self.unsuppress_on_input = False
        self.toasts = []

    def set_status(self, s):
        self.status = s

    def notify(self, *a, **k):
        self.toasts.append(a)


# =========================================================================
print("=== P2: a paused recording is not 'playing' ===")
print("--- the two small gates and the reader's budget ---")


def gate_ns(src, ctl, focus):
    ns = {"os": os, "json": json, "_AI": {"ctl": ctl},
          "_game_has_focus": lambda: focus[0]}
    if "def _session_live" in src:
        lift(src, "_session_live", ns)
    for nm in ("_reader_playing", "_reader_threads", "_aud_playing"):
        lift(src, nm, ns)
    return ns


NCPU = os.cpu_count() or 8
IDLE_THREADS = max(2, NCPU - 4)
PLAY_THREADS = max(2, NCPU // 4)

focus = [False]
ns = gate_ns(SRC, Ctl(Sess(suspended=True, afk=True, paused_min=5)), focus)
check("P2 a suspended session and no game in front: the reader's question "
      "says not playing", ns["_reader_playing"]() is False)
check("P2 ...the audit's question says the same",
      ns["_aud_playing"]() is False)
check("P2 ...and the reader's thread budget is the idle count",
      ns["_reader_threads"]() == IDLE_THREADS
      and ns["_reader_threads"](False) == IDLE_THREADS)
check("P2 _session_live is the one question: not None, not suspended",
      ns["_session_live"](None) is False
      and ns["_session_live"](Ctl(None)) is False
      and ns["_session_live"](Ctl(Sess(suspended=True))) is False
      and ns["_session_live"](Ctl(Sess(suspended=False))) is True)

ns = gate_ns(SRC, Ctl(Sess(suspended=False)), focus)
check("P2 a live, unsuspended recording still gates every one of them: "
      "playing, and the budget is a quarter of the machine",
      ns["_reader_playing"]() is True and ns["_aud_playing"]() is True
      and ns["_reader_threads"]() == PLAY_THREADS)
focus = [True]
ns = gate_ns(SRC, Ctl(None), focus)
check("P2 no recording but a game in front: still playing (unchanged)",
      ns["_reader_playing"]() is True and ns["_aud_playing"]() is True
      and ns["_reader_threads"]() == PLAY_THREADS)
focus = [False]
nsb = gate_ns(BASE, Ctl(Sess(suspended=True, afk=True, paused_min=5)), focus)
check("P2 [before, %s] the same suspended session counted as playing "
      "for the reader's budget and the audit - the card was free and "
      "both were told a game had it" % PARITY_BASE,
      nsb["_reader_playing"]() is True and nsb["_aud_playing"]() is True
      and nsb["_reader_threads"]() == PLAY_THREADS
      and "def _session_live" not in BASE)

# ------------------------------------------------------------ the twin
print("--- _ai_next_sweep names the description under a paused "
      "recording ---")


def sweep_ns(src, ctl, focus, night, fresh, owe_ins, owe_aud):
    ns = {"os": os, "time": QTime, "_AI": {"held": {}, "failed": {},
                                            "focus": None, "ctl": ctl},
          "SETTINGS": {"ai_transcribe": True, "ai_highlights": True,
                       "insights_auto": True, "output_dir": "x",
                       "reread_old": False, "bg_shutdown": False},
          "_bg_work_allowed": lambda: True,
          "_library_dirs": lambda out: [("d", "videos")],
          "_scan_dir_mp4s": lambda d, k: [{"path": night, "mtime": 5}],
          "_game_rank": lambda p: "normal",
          "_queued_finish_badge": lambda p: False,
          "_ai_skipped_recently": lambda p: False,
          "_ai_sidecar_fresh": lambda p, k: fresh.get(k, False),
          "_reader_paths": lambda: "reader",
          "_describer_paths": lambda: "describer",
          "_stt_stale_reader": lambda p: False,
          "_ins_owing": lambda p: owe_ins,
          "_sns_owing": lambda p: False,
          "_aud_owing_swept": lambda p: owe_aud,
          "_game_has_focus": lambda: focus[0]}
    lift(src, "_RANK_ORDER", ns)
    if "def _session_live" in src:
        lift(src, "_session_live", ns)
    lift(src, "_ai_next_sweep", ns)
    return ns


NIGHT = os.path.join("d", "somegame_20260914_235700.mp4")
DONE3 = {"hl": True, "lvl": True, "stt": True}
paused = Ctl(Sess(suspended=True, win=True, paused_min=20))
nx = sweep_ns(SRC, paused, focus, NIGHT, DONE3, True, False)
check("P2 the read-only twin names the description as next under a "
      "paused recording",
      (nx["_ai_next_sweep"]() or {}).get("kind") == "thinking")
nx = sweep_ns(SRC, paused, focus, NIGHT, dict(DONE3, ins=True), False, True)
check("P2 ...and the audit, when that is what the night owes",
      (nx["_ai_next_sweep"]() or {}).get("kind") == "auditing")
nx = sweep_ns(SRC, Ctl(Sess(suspended=False)), focus, NIGHT, DONE3, True,
              False)
check("P2 a live recording: the twin names nothing heavy (unchanged)",
      nx["_ai_next_sweep"]() is None)
nxb = sweep_ns(BASE, paused, focus, NIGHT, DONE3, True, False)
check("P2 [before, %s] the twin named nothing under the same paused "
      "recording - the plate said the same as the walk: waiting" % PARITY_BASE,
      nxb["_ai_next_sweep"]() is None)

# ------------------------------------------------------------ the walk
print("--- one sweep beat of the REAL _ai_tick under a paused recording ---")


def tick_ns(src, out, data, logs):
    """loops336test's q_ns shape: the real beat and every helper it
    walks with, over a scratch shelf; the writers are stubs that
    record"""
    ns = {"os": os, "json": json, "re": re, "io": io, "time": QTime,
          "threading": QThreading, "_dt": _dt,
          "log": lambda m: logs.append(str(m)),
          "SETTINGS": {"output_dir": out, "ai_transcribe": True,
                       "ai_highlights": True, "insights_auto": True,
                       "always_read": False, "reread_old": False,
                       "game_rank": {}, "sdr_finish": True,
                       "bg_shutdown": False, "afk_ai": True},
          "_data_dir": lambda: data,
          "_SLATE_BUSY": [0], "_MIG_BUSY": [False],
          "_FINISHING": {"busy": False}, "_TRIM_BUSY": [0],
          "_EMB": {"down_t": 0.0}, "_EMB_STANDDOWN": 600.0,
          "_GAME_RANK_KEY": {},
          "_queued_finish_paths": lambda: []}
    for nm in ("_AI", "AI_KINDS", "AI_LABEL", "_AFKAI", "_AUD_ASK",
               "_GAME_RANKS", "_RANK_ORDER", "_ATTIC_OF"):
        lift(src, nm, ns)
    ns["_AI_FORCE_LOCK"] = threading.RLock()
    ns["_AFKAI_LOCK"] = threading.Lock()
    ns["_AI"].setdefault("failed", {})
    for fn in ("_bg_work_allowed", "_ai_want_lanes", "_ai_lanes_free",
               "_ai_effective_lane", "_ai_skipped_recently", "_ai_sidecar",
               "_ai_sidecar_fresh", "_queued_finish_badge",
               "_ins_done_honest", "_library_dirs", "_scan_dir_mp4s",
               "_thumb_dir", "_game_rank", "_force_owes", "_ai_state_path",
               "_afk_ai_true_held", "_ai_state_save", "_attic_dir",
               "_ai_attic", "_sns_owing", "_vis_owing",
               "_atomic_write_json", "_ai_tick"):
        lift(src, fn, ns)
    for fn in ("_session_live", "_ai_landed"):
        if "def " + fn in src:
            lift(src, fn, ns)
    for fn in ("_ask_idle_tick", "_emb_idle_tick", "_desc_keep_tick",
               "_aud_keep_tick", "_self_check_daily", "_game_sources_daily",
               "_shelf_migrations", "_ask_srv_drop", "_desc_keep_drop",
               "_aud_keep_drop", "_ai_note_rate", "_ai_note_speech",
               "_audit_one"):
        ns[fn] = lambda *a, **k: None
    ns["_afk_ai_tick"] = lambda *a: False
    ns["_reader_paths"] = lambda: "reader"
    ns["_describer_paths"] = lambda: "describer"
    ns["_senses_paths"] = lambda: ("py", "work")
    ns["_desc_mmproj"] = lambda: "mmproj"
    ns["_emb_paths"] = lambda: None
    ns["_game_has_focus"] = lambda: False
    ns["_stt_stale_reader"] = lambda p: False
    ns["_lvl_coarse_cached"] = lambda p: False
    ns["_video_duration"] = lambda p: 60.0
    ns["_secs_no_probe"] = lambda item: 1.0
    ns["_hud_owing"] = lambda p: False
    ns["_outcome_owing"] = lambda p: False
    ns["_emb_owing"] = lambda p: False
    ns["_aud_owing"] = lambda p: False
    ns["_aud_owing_swept"] = lambda p: False
    ns["_audit_ask"] = lambda p, **k: False
    ns["_audit_why"] = lambda p, **k: ""
    ns["_ins_owing"] = lambda p: not ns["_ai_sidecar_fresh"](p, "ins")
    ns["_highlights_one"] = lambda p: True
    ns["_transcribe_one"] = lambda p: True
    ns["_senses_one"] = lambda p: True
    ns["_eyes_one"] = lambda p: True
    ns["_insights_one"] = lambda p, forced=False, fresh=False: True
    ns["_hud_topup_one"] = lambda p: True
    ns["_outcome_topup_one"] = lambda p: True
    ns["_emb_one"] = lambda p: True

    def _ai_abort(force_too=True):
        ns["_AI"]["abort"] = True
        ns["_AI"]["wind"] = False
        ns["_AI"]["wind_src"] = None
    ns["_ai_abort"] = _ai_abort
    return ns


def tick_shelf(tag):
    tmp = tempfile.mkdtemp(prefix="pause338_" + tag + "_")
    out = os.path.join(tmp, "out")
    data = os.path.join(tmp, "data")
    os.makedirs(os.path.join(out, ".lore_thumbs"))
    os.makedirs(data)
    return tmp, out, data


def tick_night(out, game, stamp, age_s):
    d = os.path.join(out, game, "Videos")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, game + "_" + stamp + ".mp4")
    with io.open(p, "wb") as fh:
        fh.truncate(120000)
    t = CLOCK[0] - age_s
    os.utime(p, (t, t))
    return p


def tick_reset(ns):
    AI = ns["_AI"]
    for k in ("force", "force_want", "busy", "busy_path", "focus"):
        AI[k] = None
    AI["force_redo"] = False
    AI["force_ran"] = set()
    AI["force_queue"] = []
    AI["abort"] = False
    AI["wind"] = False
    AI["t_last"] = 0
    AI["failed"] = {}
    AI["soft_n"] = {}
    AI["ran_sig"] = {}
    AI["held"] = {"listening": False, "hearing": False,
                  "thinking": False, "auditing": False}
    AI["_sg2"] = True
    AI["rate"] = {"listening": [], "hearing": [], "thinking": []}
    AI.pop("next_pick", None)
    ns["_AUD_ASK"].update({"path": None, "named": False, "claim": None})
    ns["_GAME_RANK_KEY"].clear()


def tick_case(src, ctl, owes, focus_on=False):
    """one night that owes only what `owes` says ('ins' or 'aud'), the
    catch-up armed (as it was at 01:53), one beat"""
    tmp, out, data = tick_shelf(owes)
    logs, calls = [], []
    ns = tick_ns(src, out, data, logs)
    A = tick_night(out, "somegame", "20260910_210000", 3600)
    fresh = {(A, "hl"): True, (A, "lvl"): True, (A, "stt"): True,
             (A, "ins"): owes != "ins"}
    ns["_library_dirs"] = lambda o: [(os.path.dirname(A), "videos")]
    ns["_scan_dir_mp4s"] = lambda d, k: [
        {"path": A, "mtime": os.path.getmtime(A)}]
    ns["_ai_sidecar_fresh"] = lambda p, k: fresh.get((p, k), False)
    ns["_ai_sidecar"] = lambda p, k: p + "." + k + ".json"   # never exists
    ns["_ai_attic"] = lambda *a, **k: []
    ns["_ins_done_honest"] = lambda p: fresh.get((p, "ins"), False)
    ns["_ins_owing"] = lambda p: not fresh.get((p, "ins"), False)
    ns["_sns_owing"] = lambda p: False
    ns["_vis_owing"] = lambda p: False
    ns["_aud_owing_swept"] = lambda p: owes == "aud"
    ns["_game_has_focus"] = lambda: focus_on
    ns["_INS_SAID"] = threading.local()
    ns["_DRESS_SRC"] = {}
    ns["_insights_wanted"] = lambda: True
    ns["traceback"] = __import__("traceback")

    FR = fresh

    def _ins(p, forced=False, fresh=False):
        calls.append(("thinking", p))
        FR[(p, "ins")] = True
        return True

    def _aud(p, **k):
        calls.append(("auditing", p))
        return True
    ns["_insights_one"] = _ins
    ns["_audit_ask"] = _aud
    tick_reset(ns)
    ns["_AFKAI"]["on"] = True          # the catch-up armed at 01:53
    CLOCK[0] += 6
    ns["_AI"]["t_last"] = 0
    ns["_ai_tick"](ctl)
    shutil.rmtree(tmp, ignore_errors=True)
    return calls, logs, A


calls, logs, A = tick_case(SRC, Ctl(Sess(suspended=True, win=True,
                                        paused_min=20)), "ins")
check("P2 a suspended session, no game in front, a night owing only its "
      "description: one beat spawns the describer",
      calls == [("thinking", A)])
calls, logs, A = tick_case(SRC, Ctl(Sess(suspended=True, afk=True,
                                        paused_min=20)), "aud")
check("P2 ...the audit road likewise", calls == [("auditing", A)])
calls, logs, A = tick_case(SRC, Ctl(Sess(suspended=False)), "ins")
check("P2 a live, unsuspended recording still gates the beat: nothing "
      "spawns", calls == [])
calls, logs, A = tick_case(SRC, Ctl(None), "ins", focus_on=True)
check("P2 no recording but a game in front: the describer still waits "
      "(unchanged)", calls == [])
calls, logs, A = tick_case(BASE, Ctl(Sess(suspended=True, win=True,
                                         paused_min=20)), "ins")
callsb2, _l, _a = tick_case(BASE, Ctl(Sess(suspended=True, afk=True,
                                           paused_min=20)), "aud")
check("P2 [before, %s] the same beat under the same paused recording "
      "spawned neither the describer nor the audit - fifteen hours of "
      "'it keeps looping'" % PARITY_BASE,
      calls == [] and callsb2 == [])

# ------------------------------------------------------------ the pins
print("--- the five gates read the one question ---")
TICK = fsrc(SRC, "_ai_tick")
NEXT = fsrc(SRC, "_ai_next_sweep")
WHY = msrc(SRC, "_JsApi", "ai_whynot")
check("P2 _ai_tick's playing gate reads _session_live(ctl) or focus",
      TICK.count("playing = (_session_live(ctl) or _game_has_focus())") == 1
      and "ctl.session is not None or _game_has_focus()" not in TICK)
check("P2 _ai_next_sweep's does too",
      "playing = bool(_session_live(_AI.get(\"ctl\"))" in NEXT
      and "getattr(_c, \"session\", None) is not None" not in NEXT)
check("P2 _aud_playing and _reader_playing ask it",
      "_session_live(_AI.get(\"ctl\"))" in fsrc(SRC, "_aud_playing")
      and "_session_live(_AI.get(\"ctl\"))" in fsrc(SRC, "_reader_playing"))
check("P2 the whynot text: 'waits while a game has the screen' is gated "
      "on the same question",
      "elif _session_live(ctl) or _game_has_focus():" in WHY
      and "elif ctl.session is not None or _game_has_focus():" not in WHY)
check("P2 the sweep's own live gate stands as loops336test asserts it "
      "(nothing else changes)",
      TICK.count('_live = _sess is not None and not getattr(_sess, '
                 '"suspended", False)') == 1)

# =========================================================================
print("\n=== P3: a recording paused for hours is saved, not kept open ===")


def close_ns(src, segs):
    fin, logs, disc, asked = [], [], [], []
    ns = {"os": os, "time": QTime, "_AI": {},
          "SETTINGS": {"pause_close_minutes": 30, "min_keep_seconds": 45},
          "log": lambda m: logs.append(str(m)),
          "_list_segments": lambda d: list(segs),
          "_finalize_async": lambda c, s: fin.append(s),
          # the worth-keeping mark, as the game-gone road has it: the
          # test flips WORTH; the (session, manual) it was asked with
          # is recorded
          "WORTH": False, "DISCARD": disc, "ASKED": asked,
          "_not_worth_keeping": lambda s, m: (asked.append((s, m)),
                                              ns["WORTH"])[1],
          "_captured_seconds": lambda s: 4 * len(segs),
          "_fmt_secs": lambda n: "%d seconds" % int(n),
          "_discard_soon": lambda s: disc.append(s)}
    lift(src, "_pause_close_tick", ns)
    return ns, fin, logs


def closed(ns, ctl, s):
    return ns["_pause_close_tick"](ctl, s, s.game)


ns, fin, logs = close_ns(SRC, ["seg_000000.mp4"])
s = Sess(suspended=True, afk=True, paused_min=31)
c = Ctl(s)
c.force_record.set()
r = closed(ns, c, s)
check("P3 an AFK pause 31 min old with footage is finalised on the beat",
      r is True and fin == [s] and c.session is None)
check("P3 ...through the Stop & Save road: the 'Saving your video' "
      "toast, force_record cleared, watching set",
      any("Saving your video" in str(t) for t in c.toasts)
      and not c.force_record.is_set() and c.watching.is_set())
check("P3 ...the game is suppressed AND the one-shot flag is set",
      c.suppressed_game == s.game and c.unsuppress_on_input is True)
check("P3 ...said once, in his words: paused for N min, saved what was "
      "recorded, a fresh recording starts when he is back",
      len(logs) == 1 and "was paused for 31 min" in logs[0]
      and "saved what was recorded" in logs[0]
      and "fresh recording starts when you are back" in logs[0])
check("P3 ...and the input poll can find the controller",
      ns["_AI"].get("ctl") is c)

ns, fin, logs = close_ns(SRC, ["seg_000000.mp4", "seg_000001.mp4"])
s = Sess(suspended=True, win=True, paused_min=45)
c = Ctl(s)
check("P3 a minimised/lost-window pause 45 min old with footage: the same",
      closed(ns, c, s) is True and fin == [s] and c.session is None
      and c.unsuppress_on_input is True and len(logs) == 1)

ns, fin, logs = close_ns(SRC, [])
s = Sess(suspended=True, afk=True, paused_min=31)
c = Ctl(s)
check("P3 the same pause with NO footage (born paused) is left alone",
      closed(ns, c, s) is False and fin == [] and c.session is s
      and c.suppressed_game is None and not c.unsuppress_on_input
      and logs == [])

ns, fin, logs = close_ns(SRC, ["seg_000000.mp4"])
s = Sess(suspended=True, afk=False, win=False, paused_min=180)
c = Ctl(s)
check("P3 a MANUAL pause (his own hotkey, neither flag) three hours old "
      "is never closed by this",
      closed(ns, c, s) is False and fin == [] and c.session is s
      and logs == [])

ns, fin, logs = close_ns(SRC, ["seg_000000.mp4"])
s = Sess(suspended=True, afk=True, paused_min=29)
c = Ctl(s)
check("P3 29 minutes is under the 30-minute cap: it waits",
      closed(ns, c, s) is False and fin == [] and c.session is s)

ns, fin, logs = close_ns(SRC, ["seg_000000.mp4"])
ns["SETTINGS"]["pause_close_minutes"] = 0
s = Sess(suspended=True, afk=True, paused_min=180)
c = Ctl(s)
check("P3 cap 0 = never: a three-hour AFK pause with footage stays open",
      closed(ns, c, s) is False and fin == [] and c.session is s)

ns, fin, logs = close_ns(SRC, ["seg_000000.mp4"])
s = Sess(suspended=True, afk=True, paused_min=None)
c = Ctl(s)
check("P3 no paused_at (a session that never ran suspend()) is not closed",
      closed(ns, c, s) is False and fin == [] and c.session is s)

ns, fin, logs = close_ns(SRC, ["seg_000000.mp4"])
s = Sess(suspended=False, afk=True, paused_min=60)
c = Ctl(s)
check("P3 a session that is rolling again is not closed, whatever the "
      "flags say", closed(ns, c, s) is False and fin == [])

# ---------------------------------------------- the review's two lows
print("--- the worth-keeping mark, and once per handle ---")
ns, fin, logs = close_ns(SRC, ["seg_000000.mp4"])
s = Sess(suspended=True, afk=True, paused_min=31)
c = Ctl(s)
r1 = closed(ns, c, s)
r2 = closed(ns, c, s)
check("P3 twice on the same handle: the second call returns False and "
      "files nothing (the flags are cleared with the close)",
      r1 is True and r2 is False and fin == [s]
      and s.afk_paused is False and s.win_paused is False
      and len(logs) == 1 and len(c.toasts) == 1)
check("P3 the mark was asked about an AUTOMATIC end (manual=False), "
      "once, on the session being closed",
      ns["ASKED"] == [(s, False)])

# a launcher that flashed the game's window for one segment and then
# sat minimised for half an hour
ns, fin, logs = close_ns(SRC, ["seg_000000.mp4"])
ns["WORTH"] = True
s = Sess(suspended=True, win=True, paused_min=31)
c = Ctl(s)
c.force_record.set()
r = closed(ns, c, s)
check("P3 under the worth-keeping mark: closed (True), NOT filed - "
      "discarded, no finalise, the 'Not kept' toast, as the game-gone "
      "road does",
      r is True and fin == [] and ns["DISCARD"] == [s]
      and c.session is None
      and any(t and t[0] == "Not kept" and "too short to file" in t[1]
              for t in c.toasts)
      and not any("Saving your video" in str(t) for t in c.toasts))
check("P3 ...the suppression is exactly as on the kept road: game "
      "suppressed, one-shot flag set, force_record cleared, watching set",
      c.suppressed_game == s.game and c.unsuppress_on_input is True
      and not c.force_record.is_set() and c.watching.is_set())
check("P3 ...said once: paused N min, under the mark, not saved, a "
      "fresh recording when he is back",
      len(logs) == 1 and "was paused for 31 min" in logs[0]
      and "worth-keeping mark" in logs[0] and "not saved" in logs[0]
      and "fresh recording starts when you are back" in logs[0])
check("P3 the source: the close road applies the mark with the game-gone "
      "road's three lines (log, 'Not kept', _discard_soon) and clears "
      "the flags after the close",
      "_not_worth_keeping(session, False)" in fsrc(SRC, "_pause_close_tick")
      and "_discard_soon(session)" in fsrc(SRC, "_pause_close_tick")
      and "session.afk_paused = session.win_paused = False"
      in fsrc(SRC, "_pause_close_tick"))

# ------------------------------------------------------------ the input
print("--- real input lifts the suppression; nothing else does ---")


def idle_ns(src, ctl, idle_ms):
    logs = []
    ns = {"time": QTime, "_AI": {"ctl": ctl},
          "log": lambda m: logs.append(str(m)),
          "_pad_check": lambda: None,
          "_kbms_idle_ms": lambda: idle_ms[0],
          "_PAD": {"active_t": 0.0},
          "_AFK_CLK": {"prev": 0.0, "said": 0.0, "pos": (0, 0)},
          "_AFK_SEEN": {"t": 0.0, "v": 0.0},
          "_MICWATCH": {"last_sound": None},
          "CUR": [(0, 0)]}
    ns["_cursor_pos"] = lambda: ns["CUR"][0]
    lift(src, "_afk_idle_seconds", ns)
    return ns, logs


c = Ctl(None)
c.suppressed_game = "somegame.exe"
c.unsuppress_on_input = True
idle = [900000]
ns, logs = idle_ns(SRC, c, idle)
got = ns["_afk_idle_seconds"]()
check("P3 fifteen quiet minutes: the game stays suppressed (the game "
      "merely being seen never lifts it)",
      got == 900.0 and c.suppressed_game == "somegame.exe"
      and c.unsuppress_on_input is True and logs == [])
idle[0] = 1200
ns["CUR"][0] = (40, 12)                    # ...and the cursor travelled
got = ns["_afk_idle_seconds"]()
BACK = [l for l in logs if "watching for the game again" in l]
check("P3 real input (1.2 s ago): the suppression and the flag both "
      "clear on that poll, said once (beside the countdown-reset line "
      "that road always wrote)",
      got == 1.2 and c.suppressed_game is None
      and c.unsuppress_on_input is False and len(BACK) == 1
      and any("AFK countdown reset" in l for l in logs))
got = ns["_afk_idle_seconds"]()
check("P3 ...and the next poll says nothing more",
      len([l for l in logs if "watching for the game again" in l]) == 1)
c2 = Ctl(None)
c2.suppressed_game = "somegame.exe"       # a Stop & Save by hand
ns, logs = idle_ns(SRC, c2, [500])
ns["_afk_idle_seconds"]()
check("P3 a game he stopped by hand (no flag) keeps its old rule: input "
      "does not touch it", c2.suppressed_game == "somegame.exe"
      and logs == [])
ns, logs = idle_ns(SRC, None, [500])
check("P3 no controller yet: the poll still answers",
      ns["_afk_idle_seconds"]() == 0.5)

# ------------------------------------- the phantom tick (review, low)
print("--- one phantom input tick is not a person ---")


def phantom():
    """closed and suppressed at 31 min, fifteen quiet minutes since"""
    c = Ctl(None)
    c.suppressed_game = "somegame.exe"
    c.unsuppress_on_input = True
    idle = [900000]
    ns, logs = idle_ns(SRC, c, idle)
    ns["_afk_idle_seconds"]()
    return c, idle, ns, logs


def still(c):
    return c.suppressed_game == "somegame.exe" and c.unsuppress_on_input


c, idle, ns, logs = phantom()
idle[0] = 1000                             # a device claims he was here
got = ns["_afk_idle_seconds"]()
check("P3 ONE phantom input tick (idle 1 s, no cursor travel, no pad, no "
      "mic): the suppression stands - the clock alone is not a person",
      got == 1.0 and still(c)
      and not any("watching for the game again" in l for l in logs))
check("P3 ...the countdown-reset line still names what it saw: the "
      "cursor travelled 0 px",
      any("AFK countdown reset" in l and "travelled 0 px" in l
          for l in logs))
idle[0] = 2000
ns["_afk_idle_seconds"]()
check("P3 ...and the next poll on the same lie keeps it", still(c))
ns["CUR"][0] = (3, 0)
idle[0] = 300
ns["_afk_idle_seconds"]()
check("P3 the cursor travelled 3 px since the last poll: lifted",
      c.suppressed_game is None and c.unsuppress_on_input is False
      and len([l for l in logs if "watching for the game again" in l])
      == 1)

c, idle, ns, logs = phantom()
idle[0] = 1000
ns["_PAD"]["active_t"] = CLOCK[0] - 1.0    # a real controller press
ns["_afk_idle_seconds"]()
check("P3 the controller pressed a second ago: lifted (no cursor travel "
      "needed)", c.suppressed_game is None
      and c.unsuppress_on_input is False)

c, idle, ns, logs = phantom()
idle[0] = 1000
ns["_MICWATCH"]["last_sound"] = CLOCK[0] - 20   # the mic heard him
ns["_afk_idle_seconds"]()
check("P3 the mic heard him 20 s ago: lifted", c.suppressed_game is None
      and c.unsuppress_on_input is False)

c, idle, ns, logs = phantom()
idle[0] = 1000
ns["_MICWATCH"]["last_sound"] = CLOCK[0] - 300  # ...five minutes ago
ns["_afk_idle_seconds"]()
check("P3 a mic five minutes quiet is no witness: the suppression stands",
      still(c))

c, idle, ns, logs = phantom()
idle[0] = 1000
ns["CUR"][0] = None                        # a cursor that cannot be read
ns["_afk_idle_seconds"]()
check("P3 a cursor that cannot be read at all falls back to the clock "
      "(not this box)", c.suppressed_game is None)
check("P3 the source: the lift asks for a person (pad, cursor travel or "
      "the mic), and the AFK fold pins of loops336 still hold - the mic "
      "read is in the input poll, not in _afk_track",
      "person = pad_ago < 5 or moved != 0" in fsrc(SRC, "_afk_idle_seconds")
      and "_MICWATCH" in fsrc(SRC, "_afk_idle_seconds")
      and "_MICWATCH" not in fsrc(SRC, "_afk_track"))
check("P3 [before, %s] the poll had no lift road at all - and no "
      "question about a person" % PARITY_BASE,
      "unsuppress_on_input" not in fsrc(BASE, "_afk_idle_seconds")
      and "person" not in fsrc(BASE, "_afk_idle_seconds"))

# ------------------------------------------------------------ the session
print("--- Session.suspend() stamps paused_at; resume() clears it ---")


class Runs(object):
    def __init__(self):
        self.suspended = False
        self.paused_at = None
        self.calls = []

    def _stop_run(self):
        self.calls.append("stop")

    def _start_run(self):
        self.calls.append("start")


slogs = []
sns_ = {"time": QTime, "log": lambda m: slogs.append(str(m))}
lift_method(SRC, "Session", "suspend", sns_)
lift_method(SRC, "Session", "resume", sns_)
r = Runs()
r.suspend = types.MethodType(sns_["suspend"], r)
r.resume = types.MethodType(sns_["resume"], r)
r.suspend()
check("P3 suspend() stamps paused_at with the clock",
      r.suspended and r.paused_at == CLOCK[0] and r.calls == ["stop"])
CLOCK[0] += 600
r.suspend()
check("P3 a second suspend() is the no-op it always was (the stamp keeps "
      "the FIRST pause)", r.paused_at == CLOCK[0] - 600
      and r.calls == ["stop"])
r.resume()
check("P3 resume() clears it", not r.suspended and r.paused_at is None
      and r.calls == ["stop", "start"])
INIT = msrc(SRC, "Session", "__init__")
check("P3 Session.__init__ starts it at None",
      "self.paused_at = None" in INIT)
check("P3 the controller carries unsuppress_on_input = False from birth",
      "self.unsuppress_on_input = False" in msrc(SRC, "_Ctl", "__init__"))

# ------------------------------------------------------------ the wiring
print("--- the watcher's road, the setting, the page ---")
WATCH = SRC[SRC.index("                    _afk_track(ctl, session, current)"
                      "   # resumes an AFK pause"):]
WATCH = WATCH[:WATCH.index("if not session.win_paused and not "
                           "session.afk_paused:")]
check("P3 the watcher's suspended beat takes the close road right after "
      "_afk_track, drops its handle and goes round again",
      "if _pause_close_tick(ctl, session, current):" in WATCH
      and "session = current = None" in WATCH
      and "manual = False" in WATCH and "continue" in WATCH)
check("P3 the watcher never forgets that suppression on its own - only "
      "input does",
      re.search(r'if ctl\.suppressed_game and ctl\.suppressed_game != g \\\n'
                r'\s+and not ctl\.unsuppress_on_input:\n'
                r'\s+ctl\.suppressed_game = None', SRC) is not None)
check("P3 ...and keeps the input poll read while the flag stands",
      re.search(r'if ctl\.unsuppress_on_input:\n\s+try:\n\s+'
                r'_afk_idle_recent\(\)', SRC) is not None)
check("P3 the setting: default 30, bounded 0..1440",
      re.search(r'^    "pause_close_minutes": 0,', SRC, re.M) is not None
      and '"pause_close_minutes": (0, 1440)' in fsrc(SRC,
                                                      "_sanitize_settings"))
check("P3 the Settings row sits beside the AFK rows and the mock carries "
      "the default",
      USRC.index("ctlNum('afk_minutes',1,120)")
      < USRC.index("ctlNum('pause_close_minutes',0,1440)")
      < USRC.index("ctlNum('afk_minutes',1,120)") + 900
      and "pause_close_minutes:0," in USRC)
check("P3 _afk_track itself is byte-identical to %s (the close road is "
      "the watcher's, not the AFK detector's)" % PARITY_BASE,
      fsrc(SRC, "_afk_track") == fsrc(BASE, "_afk_track"))
check("P3 [before, %s] there was no road at all: no cap, no stamp, no "
      "flag - a pause waited for ever" % PARITY_BASE,
      "def _pause_close_tick" not in BASE
      and "pause_close_minutes" not in BASE
      and "paused_at" not in msrc(BASE, "Session", "suspend")
      and "unsuppress_on_input" not in BASE)

# =========================================================================
print("\n=== P4: the ring ===")
rn = {"_AI": {}, "_AI_FORCE_LOCK": threading.RLock()}
lift(SRC, "_ai_landed", rn)
landed = rn["_ai_landed"]
r1 = landed("D:/R/a.mp4")
r2 = landed("D:/R/b.mp4")
r3 = landed("D:/R/b.mp4")
AI = rn["_AI"]
check("P4 _ai_landed bumps done_rev, records done_path and appends "
      "{rev, path} to the ring",
      (r1, r2, r3) == (1, 2, 3) and AI["done_rev"] == 3
      and AI["done_path"] == "D:/R/b.mp4"
      and AI["done_paths"] == [{"rev": 1, "path": "D:/R/a.mp4"},
                               {"rev": 2, "path": "D:/R/b.mp4"},
                               {"rev": 3, "path": "D:/R/b.mp4"}])
for i in range(30):
    landed("D:/R/n%d.mp4" % i)
check("P4 the ring holds the last 16 landings, oldest out first",
      len(AI["done_paths"]) == 16 and AI["done_rev"] == 33
      and [e["rev"] for e in AI["done_paths"]] == list(range(18, 34))
      and AI["done_paths"][-1]["path"] == "D:/R/n29.mp4"
      and all(set(e) == {"rev", "path"} for e in AI["done_paths"]))
rn2 = {"_AI": {"done_rev": 40, "done_paths": None},
       "_AI_FORCE_LOCK": threading.RLock()}
lift(SRC, "_ai_landed", rn2)
check("P4 a state with no ring yet (an older ai_state) starts one",
      rn2["_ai_landed"]("x") == 41
      and rn2["_AI"]["done_paths"] == [{"rev": 41, "path": "x"}])

BARE = '_AI["done_rev"] = int(_AI.get("done_rev") or 0) + 1'
check("P4 no bare bump remains: every landing site goes through the "
      "helper (the base had six)",
      SRC.count(BARE) == 0 and BASE.count(BARE) == 6)


def landing_sites(src):
    """(innermost function name, the path argument) for every call of
    _ai_landed - a nested function (the auditor's _put, its worker's
    work) is its own site, not its parent's twice"""
    out = []

    def calls_in(node, top, owner):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                calls_in(ch, top or ch.name, ch.name)
                continue
            if isinstance(ch, ast.Call) and isinstance(ch.func, ast.Name) \
                    and ch.func.id == "_ai_landed":
                out.append((top, owner, ast.unparse(ch.args[0])
                            if ch.args else None))
            calls_in(ch, top, owner)
    calls_in(tree_of(src), None, "<module>")
    return out


sites = landing_sites(SRC)
by_top = {}
for top, owner, arg in sites:
    by_top.setdefault(top, []).append((owner, arg))
check("P4 the six landing sites each name a path: the two ears' folds "
      "(which bumped without one), the auditor's write and its worker's "
      "finally, the sweep's worker, and a version switched by hand",
      len(sites) == 6 and all(a for _t, _o, a in sites)
      and by_top == {"_merge_sns_into_hl": [("_merge_sns_into_hl",
                                              "video_path")],
                     "_merge_vis_into_hl": [("_merge_vis_into_hl",
                                              "video_path")],
                     "_audit_one": [("_put", "video_path")],
                     "_audit_ask": [("work", "video_path")],
                     "_ai_tick": [("work", "path")],
                     "ai_version_use": [("ai_version_use", "p")]})
check("P4 ...and the auditor's two (its _put and its worker's finally) "
      "sit inside _audit_one and _audit_ask",
      "_ai_landed(video_path)" in fsrc(SRC, "_audit_one")
      and "_ai_landed(video_path)" in fsrc(SRC, "_audit_ask"))
STATUS = msrc(SRC, "_JsApi", "ai_status")
check("P4 ai_status returns done_paths beside done_rev and done_path",
      '"done_paths": list(_AI.get("done_paths") or [])' in STATUS
      and STATUS.index('"done_rev"') < STATUS.index('"done_path"')
      < STATUS.index('"done_paths"'))
check("P4 [before, %s] no helper, no ring, nothing in ai_status - every "
      "unexplained bump was a blanket on the page" % PARITY_BASE,
      "def _ai_landed" not in BASE
      and "done_paths" not in msrc(BASE, "_JsApi", "ai_status"))

# --------------------------------------- the landing under the lock
print("--- five threads land at once: no rev lost, no ring entry lost ---")


class YDict(dict):
    """a state whose get() yields the GIL between the read and the write
    - the review's way of widening the unlocked window"""
    def get(self, k, d=None):
        v = dict.get(self, k, d)
        _real_time.sleep(0.0002)
        return v


def storm(fn_src, label):
    ns = {"_AI": YDict(), "_AI_FORCE_LOCK": threading.RLock()}
    exec(compile(fn_src, "<" + label + ">", "exec"), ns)
    land = ns["_ai_landed"]

    def run(k):
        for i in range(300):
            land("D:/R/t%d_%d.mp4" % (k, i))
    ts = [threading.Thread(target=run, args=(k,)) for k in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    ring = list(ns["_AI"]["done_paths"])
    return int(ns["_AI"]["done_rev"]), [e["rev"] for e in ring]


LANDED = textwrap.dedent(fsrc(SRC, "_ai_landed"))
check("P4 the source: _ai_landed takes _AI_FORCE_LOCK (the RLock the "
      "auditor's worker already holds)",
      "    with _AI_FORCE_LOCK:" in LANDED
      and "_AI_FORCE_LOCK = threading.RLock()" in SRC)
rev, revs = storm(LANDED, "landed")
check("P4 8 threads x 300 landings under the lock: done_rev is 2400 and "
      "the ring holds the last 16 revs, contiguous, none dropped",
      rev == 2400 and revs == list(range(2385, 2401)), "rev=%d" % rev)
# the witness: the same helper with its lock line made a no-op - the
# shape the reviewers ran against drop P as it stood (the parity base
# has no helper at all, so this is the only "before" there is)
UNLOCKED = LANDED.replace("    with _AI_FORCE_LOCK:", "    if True:")
assert UNLOCKED != LANDED
lost = 0
for _try in range(3):
    rev, revs = storm(UNLOCKED, "unlocked")
    lost = max(lost, 2400 - rev + (len(revs) - len(set(revs))))
    if lost:
        break
check("P4 [before, drop P as reviewed] the same storm without the lock "
      "lost revs or ring entries (the page then saw no gap and never "
      "re-asked that night)", lost > 0, "lost=%d" % lost)

# the ears' fold, run: it lands and names the night
print("--- the ears' fold names the night it landed ---")
tmp = tempfile.mkdtemp(prefix="pause338_fold_")
VID = os.path.join(tmp, "somegame_20260914_235700.mp4")
io.open(VID, "wb").write(b"\0" * 100)
flogs = []
fns = {"os": os, "json": json, "_AI": {},
       "_AI_FORCE_LOCK": threading.RLock(),
       "log": lambda m: flogs.append(str(m)),
       "_ai_sidecar": lambda p, k: p[:-4] + "." + k + ".json"}
lift(SRC, "_atomic_write_json", fns)
lift(SRC, "_ai_landed", fns)
lift(SRC, "_merge_sns_into_hl", fns)
io.open(VID[:-4] + ".hl.json", "w", encoding="utf-8").write(
    json.dumps({"v": 2, "events": [{"t": 103.0, "z": 20.0, "src": "room"}]}))
added, err = fns["_merge_sns_into_hl"](
    VID, {"events": [{"t": 100.0, "kind": "cheer", "p": 0.3}],
          "src": {"clap": "game"}, "music": []})
check("P4 a sound mark folded into the gold: the ring names that night",
      added == 1 and err is None and fns["_AI"]["done_rev"] == 1
      and fns["_AI"]["done_path"] == VID
      and fns["_AI"]["done_paths"] == [{"rev": 1, "path": VID}])
added, err = fns["_merge_sns_into_hl"](
    VID, {"events": [{"t": 100.0, "kind": "cheer", "p": 0.3}],
          "src": {"clap": "game"}, "music": []})
check("P4 the same fold again adds nothing and does not bump (no loop)",
      added == 0 and err is None and fns["_AI"]["done_rev"] == 1)
shutil.rmtree(tmp, ignore_errors=True)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
