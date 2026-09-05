# -*- coding: utf-8 -*-
"""3.31 SOURCES - the tap watch on the REAL methods.

Borrows AudioRecorder._tap_watch / _tap_reopen / _open_sources /
_open_process_tap / _spawn_tap / _tap_commit / _tap_failed onto a
stand-in with a fake `proctap`, fake _root_pids / _voice_target /
_pid_wears, a controllable clock, and the 4 s beat driven by a stepper
standing in for self._stop, and proves:

  1  Discord absent -> exactly ONE 'is not running' line across 10 beats;
  2  Discord appears at beat 6 -> opened once, with ITS OWN anchor, not t0;
  3  the pid dies -> after the 8 s look a new root reopens into the SAME
     ring (identity, reopens 1, t_first unchanged) and the next chunk
     fills the gap; gap_s is counted;
  4  no new root for 60 s -> ONE 'closed - the voice layer is your
     microphone alone' line and state 'gone';
  5  cb_at stale 9 s with a live pid -> one reopen on the same pid;
  6  voice_apps ['steam.exe','discord.exe'] both running -> Steam chosen
     and the 'more than one voice app' line once (the REAL _voice_target);
  7  capture_by_source flipped off mid-session -> nothing further;
  8  a reopen that fails leaves the ring 'dead' and is retried;
  9  (stage C) a quiet tap is a stall only while the Mix heard sound in
     the last 30 s; the 'stopped sending sound' line comes once per
     kind; a same-pid reopen whose fresh tap goes quiet again backs off
     to one try a minute, and a reopened tap that ran a good minute
     earns the 8 s response back;
 10  (stage C) a 'dead' ring whose pid is ALIVE never turns 'gone' -
     the 'closed - your microphone alone' verdict needs a dead pid.
No devices, no proctap, nothing under D:\\Records."""
import ast
import io
import os
import struct
import sys
import tempfile
import textwrap
import threading as _real_threading
import time as _real_time
import types
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
TREE = ast.parse(SRC)

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


def method(cls_name, name, ns):
    for node in TREE.body:
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for f in node.body:
                if isinstance(f, ast.FunctionDef) and f.name == name:
                    code = textwrap.dedent("\n".join(
                        SRC.splitlines()[f.lineno - 1:f.end_lineno]))
                    exec(compile(code, "<%s.%s>" % (cls_name, name), "exec"), ns)
                    return ns[name]
    raise AssertionError("%s.%s not found" % (cls_name, name))


def extract(name, ns):
    for node in TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = "\n".join(SRC.splitlines()[node.lineno - 1:node.end_lineno])
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name)


def lift_assign(name, ns):
    for node in TREE.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            code = "\n".join(SRC.splitlines()[node.lineno - 1:node.end_lineno])
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name)


# ---------------------------------------------------------------- fakes --
CLOCK = [1_700_000_000.0]


class FakeTime(object):
    @staticmethod
    def time():
        return CLOCK[0]

    @staticmethod
    def sleep(s):
        _real_time.sleep(s)


class FakeTap(object):
    made = []
    specific = True
    ctor_raise = None

    def __init__(self, pid, on_data=None):
        if FakeTap.ctor_raise is not None:
            raise FakeTap.ctor_raise
        FakeTap.made.append(self)
        self.pid = pid
        self.on_data = on_data
        self.stopped = False

    def start(self):
        pass

    def stop(self):
        self.stopped = True

    def close(self):
        pass

    def feed(self, pcm):
        self.on_data(pcm, len(pcm) // 8)

    @property
    def _backend(self):
        return types.SimpleNamespace(_native=types.SimpleNamespace(
            is_process_specific=lambda: FakeTap.specific))


fake_mod = types.ModuleType("proctap")
fake_mod.ProcessAudioCapture = FakeTap
sys.modules["proctap"] = fake_mod


class Beat(object):
    """Stands in for self._stop: the watch's 4 s wait steps the clock and
    counts beats (True ends the loop); a tap thread's 0.5 s wait is a
    real blink that answers is_set."""

    def __init__(self):
        self.n = 0
        self.limit = 0
        self._set = False

    def wait(self, t=None):
        if t == 4.0:
            if self.n >= self.limit:
                return True
            self.n += 1
            CLOCK[0] += 4.0
            return False
        _real_time.sleep(0.005)
        return self._set

    def is_set(self):
        return self._set

    def set(self):
        self._set = True


class ThreadShim(object):
    """Real threads, except the watch itself, which the test drives."""

    def __init__(self, target=None, daemon=None):
        self._t = None
        if getattr(target, "__name__", "") != "_tap_watch":
            self._t = _real_threading.Thread(target=target, daemon=True)

    def start(self):
        if self._t is not None:
            self._t.start()

    def join(self, timeout=None):
        if self._t is not None:
            self._t.join(timeout)

    def is_alive(self):
        return bool(self._t is not None and self._t.is_alive())


fake_threading = types.SimpleNamespace(Thread=ThreadShim,
                                       Event=_real_threading.Event,
                                       Lock=_real_threading.Lock)

WORLD = {"roots": {}, "alive": set()}     # what the machine looks like
SAID = []
SETTINGS = {"capture_by_source": True, "capture_system": True,
            "game_audio_only": False, "capture_mic": True,
            "voice_apps": ["discord.exe", "discordptb.exe", "discordcanary.exe"]}
ns = {"os": os, "wave": wave, "threading": fake_threading, "time": FakeTime,
      "log": SAID.append, "SETTINGS": SETTINGS,
      "_root_pids": lambda names: {n: WORLD["roots"][n] for n in names
                                   if n in WORLD["roots"]},
      "_pid_wears": lambda pid, exe: pid in WORLD["alive"],
      "_pid_alive": lambda pid: pid in WORLD["alive"],
      "_pa_close": lambda pa: None, "_PA_SETTLE": 0.0}
lift_assign("_TAPWATCH", ns)
lift_assign("_PROCTAP", ns)
extract("_voice_target", ns)           # the REAL one, over the fake walk


class Cap(object):
    def __init__(self, tmp, sources=None):
        self.rings = []
        self._ring_lock = _real_threading.Lock()
        self._streams = []
        self._threads = []
        self._stop = Beat()
        self.tmp_dir = tmp
        self.tag = "00"
        self.system_wav = self.mic_wav = self.voice_wav = self.game_wav = None
        self._taps = {}
        self._said = set()
        self._manifest = {"t0": None, "voice": None, "game": None, "media": "none"}
        self._replay_seconds = 65
        self.sources = sources or {"game_exe": "game.exe", "game_pid": None,
                                   "voice_apps": list(SETTINGS["voice_apps"])}
        self.t0 = CLOCK[0]
        self._sys_done = True
        self._pa = None


for m in ("_open_process_tap", "_spawn_tap", "_tap_commit", "_tap_failed",
          "_tap_reopen", "_tap_watch", "_open_sources", "first_sample_wallclock",
          "sources_manifest"):
    setattr(Cap, m, method("AudioRecorder", m, ns))

RATE = 48000


def pcm(nfr, val=0.5):
    return struct.pack("<%df" % (nfr * 2), *([val] * (nfr * 2)))


def wait_for(cond, secs=4.0):
    t = _real_time.time()
    while _real_time.time() - t < secs:
        if cond():
            return True
        _real_time.sleep(0.005)
    return cond()


def beats(cap, n):
    cap._stop.limit = cap._stop.n + n
    cap._tap_watch()


TD = tempfile.mkdtemp(prefix="watch331_")
VW = os.path.join(TD, "voice_00.wav")

# ---------------------------------------------------------------- 1 --
print("--- 1: Discord absent ---")
cap = Cap(TD)
cap._open_sources(None)
beats(cap, 10)
check("exactly ONE 'is not running' line across start + 10 beats",
      sum(1 for m in SAID if "Discord is not running - the voice layer is your "
          "microphone alone until it starts." in m) == 1)
check("no game pid: 'the game layer will start when it appears', once",
      sum(1 for m in SAID if "no live process for game.exe yet" in m) == 1)
check("no tap was opened, no WAV", FakeTap.made == [] and not os.path.isfile(VW)
      and cap._taps == {})

# ---------------------------------------------------------------- 2 --
print("\n--- 2: Discord appears at beat 6 ---")
SAID[:] = []
cap = Cap(TD)
t0 = cap.t0
cap._stop.limit = 5
cap._tap_watch()                        # 5 beats, nobody home (the 20 s look)
WORLD["roots"] = {"discord.exe": 100}
WORLD["alive"] = {100}
beats(cap, 3)                           # beats 6-8: the 20 s look fires
check("opened once, on the root, on a second look",
      len(FakeTap.made) == 1 and FakeTap.made[0].pid == 100
      and sum(1 for m in SAID if "discord.exe found on a second look (pid 100)" in m) == 1
      and cap.voice_wav == VW)
ring = cap._taps.get("voice")
check("...and it turns live", ring is not None
      and wait_for(lambda: ring["state"] == "live"))
check("its anchor is its OWN (no preset t_first, not t0)",
      ring["t_first"] is None)
opened_at = CLOCK[0]
FakeTap.made[-1].feed(pcm(480))
check("the first chunk anchors at now - nfr/rate, hours after t0 count nothing",
      abs(ring["t_first"] - (opened_at - 480 / RATE)) < 1e-6
      and ring["t_first"] > t0 + 20 and ring["frames"] == 480)

# ---------------------------------------------------------------- 3 --
print("\n--- 3: the pid dies, a new root appears ---")
SAID[:] = []
before = ring["t_first"]
WORLD["alive"] = set()                  # Discord died
beats(cap, 1)                           # noticed; first look right away (last_look old)
WORLD["roots"] = {"discord.exe": 200}
WORLD["alive"] = {200}
beats(cap, 3)                           # the 8 s look: beat 2 or 3 after
check("reopened into the SAME ring: identity, reopens 1, t_first unchanged, pid 200",
      cap._taps["voice"] is ring and ring["reopens"] == 1
      and ring["t_first"] == before and ring["pid"] == 200
      and wait_for(lambda: ring["state"] == "live"))
check("the old tap was retired (on its own thread), a new one opened on 200",
      len(FakeTap.made) == 2 and wait_for(lambda: FakeTap.made[0].stopped)
      and FakeTap.made[1].pid == 200)
check("the 'restarted (pid 100 -> 200)' line, once",
      sum(1 for m in SAID if "discord.exe restarted (pid 100 -> 200) - the voice "
          "layer follows the new one" in m) == 1
      and ns["_TAPWATCH"]["voice"]["state"] == "reconnected"
      and ns["_TAPWATCH"]["voice"]["fixes"] == 1)
frames_before = ring["frames"]
FakeTap.made[0].feed(pcm(480))          # a late chunk from the retired tap
check("a late chunk from the retired tap is ignored", ring["frames"] == frames_before)
FakeTap.made[1].feed(pcm(480))
check("the next chunk fills the gap to the wall clock",
      ring["frames"] == int((CLOCK[0] - ring["t_first"]) * RATE))
# the death is noticed on beat 1 (down_at), the 8 s look fires on the next
# beat that clears it - 4 s here, the honest number, not a guess
check("gap_s counts the dead stretch from the beat it was noticed (4 s here)",
      4.0 <= ring["gap_s"] < 20.0 and ring["down_at"] is None
      and cap.sources_manifest()["voice"]["gap_s"] == ring["gap_s"])

# ---------------------------------------------------------------- 4 --
print("\n--- 4: no new root for 60 s ---")
SAID[:] = []
WORLD["alive"] = set()
WORLD["roots"] = {}
beats(cap, 20)                          # 80 s of nothing
check("ONE 'closed - the voice layer is your microphone alone from here' line",
      sum(1 for m in SAID if "discord.exe closed - the voice layer is your "
          "microphone alone from here." in m) == 1)
check("state 'gone' on the ring and the status row, no reopen attempted",
      ring["state"] == "gone" and ns["_TAPWATCH"]["voice"]["state"] == "gone"
      and len(FakeTap.made) == 2)
check("...and the manifest's gap keeps growing while it is gone",
      cap.sources_manifest()["voice"]["gap_s"] > 60)
WORLD["roots"] = {"discord.exe": 300}
WORLD["alive"] = {300}
beats(cap, 3)
check("a root that comes back after 'gone' is followed again",
      ring["pid"] == 300 and wait_for(lambda: ring["state"] == "live")
      and ns["_TAPWATCH"]["voice"]["state"] == "reconnected")

# ---------------------------------------------------------------- 5 --
print("\n--- 5: alive but stalled ---")
SAID[:] = []
n_taps = len(FakeTap.made)
ring["cb_at"] = CLOCK[0]
beats(cap, 1)
check("a fresh cb_at: nothing happens", len(FakeTap.made) == n_taps and SAID == [])
ring["cb_at"] = CLOCK[0] - 9.0
beats(cap, 1)
check("cb_at 9 s stale with a live pid -> ONE reopen on the same pid",
      len(FakeTap.made) == n_taps + 1 and FakeTap.made[-1].pid == 300
      and ring["pid"] == 300
      and sum(1 for m in SAID if "the voice tap stopped sending sound - reopening it." in m) == 1
      and any("the voice tap is back on discord.exe (pid 300)" in m for m in SAID))

# ---------------------------------------------------------------- 8 --
print("\n--- 8: a reopen that fails is 'dead' and retried ---")
SAID[:] = []
n_taps = len(FakeTap.made)
FakeTap.ctor_raise = RuntimeError("activation refused")
CLOCK[0] += 120.0                       # the tap from 5 ran a good two minutes
ring["cb_at"] = CLOCK[0] - 9.0
beats(cap, 1)
check("the failed reopen leaves the ring 'dead', once said, the row 'dead'",
      ring["state"] == "dead" and ns["_TAPWATCH"]["voice"]["state"] == "dead"
      and sum(1 for m in SAID if "the voice tap could not be reopened yet "
              "(activation refused) - trying again shortly." in m) == 1)
beats(cap, 3)
check("...retried on the 8 s look while dead (still failing, said once)",
      ring["state"] == "dead"
      and sum(1 for m in SAID if "could not be reopened yet" in m) == 1)
FakeTap.ctor_raise = None
beats(cap, 3)
check("...and comes back on the same root when the reopen works",
      wait_for(lambda: ring["state"] == "live") and ring["pid"] == 300
      and ns["_TAPWATCH"]["voice"]["state"] == "reconnected")

# ---------------------------------------------------------------- 9 --
print("\n--- 9: the Mix gate and the 60 s cadence ---")
SAID[:] = []
n_taps = len(FakeTap.made)
CLOCK[0] += 120.0
MIX = {"kind": "system", "last_sound": CLOCK[0] - 45.0, "closed": False,
       "t_first": None, "push": None, "frames": 0, "rate": RATE}
cap.rings.append(MIX)


def beats_loud(cap, n, fresh=False):
    """n beats with the Mix hearing sound at every one (and, with
    `fresh`, the tap delivering too)."""
    for _ in range(n):
        MIX["last_sound"] = CLOCK[0]
        if fresh:
            ring["cb_at"] = CLOCK[0]
        beats(cap, 1)


ring["cb_at"] = CLOCK[0] - 9.0
beats(cap, 3)
check("a Mix silent for 45 s starves the taps by design: no line, no reopen",
      len(FakeTap.made) == n_taps and SAID == [] and ring["state"] == "live")
ring["cb_at"] = CLOCK[0] - 9.0
beats_loud(cap, 1)
R = CLOCK[0]
check("the Mix heard sound this beat -> the stall is real: one reopen on the same pid",
      len(FakeTap.made) == n_taps + 1 and FakeTap.made[-1].pid == 300
      and wait_for(lambda: ring["state"] == "live"))
check("...and the 'stopped sending sound - reopening it' line is NOT said again (once per kind, test 5 had it)",
      not any("stopped sending sound - reopening it" in m for m in SAID)
      and any("the voice tap is back on discord.exe (pid 300)" in m for m in SAID))
# the fresh tap delivers nothing (cb_at stays at the reopen): quiet again
# within the minute -> one try a minute from the reopen
beats_loud(cap, 14)
check("quiet again within the minute: no second reopen through 56 s",
      len(FakeTap.made) == n_taps + 1 and CLOCK[0] - R == 56.0)
beats_loud(cap, 1)
check("...the next try lands at 60 s", len(FakeTap.made) == n_taps + 2
      and CLOCK[0] - R == 60.0 and wait_for(lambda: ring["state"] == "live"))
beats_loud(cap, 14)
check("...and again nothing through the next 56 s", len(FakeTap.made) == n_taps + 2)
beats_loud(cap, 1)
R2 = CLOCK[0]
check("...one a minute: the 60 s cadence holds", len(FakeTap.made) == n_taps + 3
      and wait_for(lambda: ring["state"] == "live"))
check("...still only the one 'stopped sending sound' line of the whole night",
      not any("stopped sending sound - reopening it" in m for m in SAID))
beats_loud(cap, 18, fresh=True)         # the reopened tap runs 72 s, delivering
ring["cb_at"] = CLOCK[0] - 9.0
beats_loud(cap, 1)
check("a reopened tap that ran a good minute earns the 8 s response back",
      len(FakeTap.made) == n_taps + 4 and CLOCK[0] - R2 == 76.0
      and wait_for(lambda: ring["state"] == "live"))
check("the cadence rides the ring: stall_at is the last stall reopen, backoff is off again",
      ring["stall_at"] == CLOCK[0] and ring["stall_backoff"] is False)
cap.rings.remove(MIX)

# ---------------------------------------------------------------- 10 --
print("\n--- 10: 'dead' with a live pid is never 'gone' ---")
SAID[:] = []
WORLD["roots"] = {"discord.exe": 500}
WORLD["alive"] = {500}
cap3 = Cap(TD, sources={"game_exe": None, "game_pid": None,
                        "voice_apps": ["discord.exe"]})
cap3._open_sources(None)
ring3 = cap3._taps["voice"]
check("a fresh session's tap is live on pid 500",
      wait_for(lambda: ring3["state"] == "live") and ring3["pid"] == 500)
n_taps = len(FakeTap.made)
FakeTap.ctor_raise = RuntimeError("activation refused")
CLOCK[0] += 120.0
ring3["cb_at"] = CLOCK[0] - 9.0
beats(cap3, 1)
check("its reopen fails: 'dead', the 'could not be reopened yet' line once",
      ring3["state"] == "dead"
      and sum(1 for m in SAID if "the voice tap could not be reopened yet" in m) == 1)
WORLD["roots"] = {}                     # the walk sees no root, the pid lives on
beats(cap3, 25)                         # 100 s
check("100 s later, pid alive: still 'dead' (retried), NOT 'gone', no 'closed' line",
      ring3["state"] == "dead" and ns["_TAPWATCH"]["voice"]["state"] == "dead"
      and not any("closed - the voice layer" in m for m in SAID)
      and sum(1 for m in SAID if "could not be reopened yet" in m) == 1)
WORLD["alive"] = set()                  # now it really dies
beats(cap3, 20)                         # 80 s, one pass of the watch
check("...the pid really dead: the verdict, once, and 'gone'",
      ring3["state"] == "gone" and ns["_TAPWATCH"]["voice"]["state"] == "gone"
      and sum(1 for m in SAID if "discord.exe closed - the voice layer is your "
              "microphone alone from here." in m) == 1)
FakeTap.ctor_raise = None
WORLD["roots"] = {"discord.exe": 600}
WORLD["alive"] = {600}
beats(cap3, 3)
check("...and a new root after 'gone' is followed again",
      ring3["pid"] == 600 and wait_for(lambda: ring3["state"] == "live"))
cap3._stop.set()

# ---------------------------------------------------------------- 6 --
print("\n--- 6: two voice apps ---")
SAID[:] = []
ns["_TAPWATCH"]["said"].clear()
WORLD["roots"] = {"steam.exe": 40, "discord.exe": 50}
WORLD["alive"] = {40, 50}
cap2 = Cap(TD, sources={"game_exe": None, "game_pid": None,
                        "voice_apps": ["steam.exe", "discord.exe"]})
cap2._open_sources(None)
check("Steam chosen (first in the list) and the tap sits on its root",
      cap2._taps["voice"]["pid"] == 40 and cap2._taps["voice"]["exe"] == "steam.exe"
      and wait_for(lambda: cap2._taps["voice"]["state"] == "live"))
check("the 'more than one voice app' line, once",
      sum(1 for m in SAID if "more than one voice app is running; the voice layer "
          "follows steam.exe." in m) == 1)
check("a desktop recording says the game layer is off, once",
      sum(1 for m in SAID if "no game process to follow for a desktop recording" in m) == 1)
beats(cap2, 6)
check("...and the watch does not say it again",
      sum(1 for m in SAID if "more than one voice app" in m) == 1)

# ---------------------------------------------------------------- 7 --
print("\n--- 7: capture_by_source flipped off mid-session ---")
SAID[:] = []
n_taps = len(FakeTap.made)
SETTINGS["capture_by_source"] = False
WORLD["alive"] = set()
ring2 = cap2._taps["voice"]
ring2["cb_at"] = CLOCK[0] - 30.0      # stale AND its pid dead: two reasons to act
reopens_before = ring2["reopens"]
beats(cap2, 20)
check("the watch does nothing further: no reopen, no lines, ring untouched",
      len(FakeTap.made) == n_taps and SAID == [] and ring2["state"] == "live"
      and ring2["reopens"] == reopens_before)
SETTINGS["capture_by_source"] = True

for c in (cap, cap2):
    c._stop.set()
import shutil
shutil.rmtree(TD, ignore_errors=True)
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
