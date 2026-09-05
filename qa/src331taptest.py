# -*- coding: utf-8 -*-
"""3.31 SOURCES - the tap ring on the REAL methods.

Borrows AudioRecorder._open_process_tap / _spawn_tap / _tap_commit /
_tap_failed / finalize / signal_stop / sources_manifest /
first_sample_wallclock onto a stand-in (the micheal.py way), under a
fake `proctap` module (a ProcessAudioCapture with start/stop/close, a
scripted _backend._native.is_process_specific() and a feed(float32)
hook), a controllable clock and a fake liveness gate, and proves:

  1  anchor=t0 -> the ring's t_first IS t0 and the first chunk fed 2 s
     later is preceded by exactly that much silence, to the frame;
  2  a 130 s feed gap is filled to the frame;
  3  float32 -> int16, stereo frame_bytes 4;
  4  is_process_specific False -> ring removed, WAV deleted, ONE
     'would only give a system-wide tap' line;
  5  a dead pid is refused BEFORE construction (the ctor never runs)
     with the 'is gone - looking for it again' line;
  6  wait=0 returns in < 50 ms while the ctor sleeps 3 s; the ring turns
     'live' later and the writer thread starts only then;
  7  the legacy 2-arg call: kind 'system', synchronous, the old log line;
  8  the run ends before a tap is live -> finalize deletes the WAV and
     voice_wav is None; sources_manifest carries gap_s.
No devices, no proctap, nothing under D:\\Records."""
import ast
import io
import os
import struct
import sys
import tempfile
import textwrap
import threading
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
    """exec the REAL method `name` of class `cls_name` into ns."""
    for node in TREE.body:
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for f in node.body:
                if isinstance(f, ast.FunctionDef) and f.name == name:
                    code = textwrap.dedent("\n".join(
                        SRC.splitlines()[f.lineno - 1:f.end_lineno]))
                    exec(compile(code, "<%s.%s>" % (cls_name, name), "exec"), ns)
                    return ns[name]
    raise AssertionError("%s.%s not found" % (cls_name, name))


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
    ctor_sleep = 0.0
    ctor_raise = None

    def __init__(self, pid, on_data=None):
        if FakeTap.ctor_sleep:
            _real_time.sleep(FakeTap.ctor_sleep)
        if FakeTap.ctor_raise is not None:
            raise FakeTap.ctor_raise
        FakeTap.made.append(self)
        self.pid = pid
        self.on_data = on_data
        self.started = self.stopped = self.closed = False
        self._backend = types.SimpleNamespace(_native=types.SimpleNamespace(
            is_process_specific=lambda: FakeTap.specific))

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def close(self):
        self.closed = True

    def feed(self, pcm):
        self.on_data(pcm, len(pcm) // 8)


fake_mod = types.ModuleType("proctap")
fake_mod.ProcessAudioCapture = FakeTap
sys.modules["proctap"] = fake_mod

ALIVE = {"pids": set(), "other": set()}    # 'other': alive under another exe
SAID = []
ns = {"os": os, "wave": wave, "threading": threading, "time": FakeTime,
      "log": SAID.append,
      "SETTINGS": {"capture_by_source": True, "capture_system": True,
                   "game_audio_only": False, "capture_mic": True},
      "_pid_wears": lambda pid, exe: (pid in ALIVE["pids"]
                                      and pid not in ALIVE["other"]),
      "_pid_alive": lambda pid: pid in ALIVE["pids"],
      "_pa_close": lambda pa: None, "_PA_SETTLE": 0.0}
lift_assign("_TAPWATCH", ns)
lift_assign("_PROCTAP", ns)


class Cap(object):
    def __init__(self, tmp):
        self.rings = []
        self._ring_lock = threading.Lock()
        self._streams = []
        self._threads = []
        self._stop = threading.Event()
        self.tmp_dir = tmp
        self.tag = "00"
        self.system_wav = self.mic_wav = self.voice_wav = self.game_wav = None
        self._taps = {}
        self._said = set()
        self._manifest = {"t0": None, "voice": None, "game": None, "media": "none"}
        self._replay_seconds = 65
        self.sources = {}
        self.t0 = None
        self._pa = None


for m in ("_open_process_tap", "_spawn_tap", "_tap_commit", "_tap_failed",
          "finalize", "signal_stop", "sources_manifest",
          "first_sample_wallclock", "_tap_reopen"):
    setattr(Cap, m, method("AudioRecorder", m, ns))

RATE = 48000


def pcm(nfr, val=0.5):
    return struct.pack("<%df" % (nfr * 2), *([val] * (nfr * 2)))


def wait_for(cond, secs=6.0):
    t = _real_time.time()
    while _real_time.time() - t < secs:
        if cond():
            return True
        _real_time.sleep(0.01)
    return cond()


TD = tempfile.mkdtemp(prefix="tap331_")

# ---------------------------------------------------------------- 1+2+3 --
print("--- 1: the shared anchor ---")
cap = Cap(TD)
cap.t0 = CLOCK[0]
ALIVE["pids"] = {100}
del FakeTap.made[:]
vw = os.path.join(TD, "voice_00.wav")
ring = cap._open_process_tap(100, vw, kind="voice", label="voice",
                             exe="discord.exe", anchor=cap.t0, wait=0)
check("async: the ring comes back at once, state 'opening'",
      isinstance(ring, dict) and ring["state"] == "opening")
check("t_first IS the run's t0, frames start at 0",
      ring["t_first"] == cap.t0 and ring["frames"] == 0)
check("the tap thread proves it and the ring turns live",
      wait_for(lambda: ring["state"] == "live") and cap._taps["voice"] is ring
      and ns["_TAPWATCH"]["voice"]["state"] == "live")
CLOCK[0] = cap.t0 + 2.0
FakeTap.made[-1].feed(pcm(480))
zeros = sum(len(c) for c in list(ring["chunks"])[:-1]) // 4
check("the first chunk fed 2.0 s later is preceded by 2.0 s of silence, to the frame",
      zeros == int(2.0 * RATE) - 480 and ring["frames"] == int(2.0 * RATE))
check("...and its last sample lands at now (first_sample_wallclock = t0)",
      cap.first_sample_wallclock("voice") == cap.t0)

print("\n--- 2: a 130 s gap is filled to the frame ---")
CLOCK[0] = cap.t0 + 132.0
FakeTap.made[-1].feed(pcm(480))
check("frames == (now - t0) * 48000 exactly",
      ring["frames"] == int(132.0 * RATE))
check("last_sound stamped by a non-silent chunk (deaf-backstop parity)",
      ring["last_sound"] == CLOCK[0] and ring["cb_at"] == CLOCK[0])

print("\n--- 3: the sample format ---")
last = list(ring["chunks"])[-1]
check("float32 0.5 -> int16 16383, stereo frame_bytes 4",
      ring["frame_bytes"] == 4 and struct.unpack("<h", last[:2])[0] == 16383
      and len(last) == 480 * 4)
check("the success line names the layer and the exe",
      any("Sources: capturing the voice layer from discord.exe (pid 100)" in m
          for m in SAID))
check("sources_manifest reports the layer with its anchor and no gap",
      cap.sources_manifest()["voice"]["anchor"] == cap.t0
      and cap.sources_manifest()["voice"]["gap_s"] == 0.0
      and cap.sources_manifest()["media"] == "none")
cap.signal_stop()
cap.finalize()
check("a live layer survives finalize with its WAV on disk",
      os.path.isfile(vw) and cap._taps.get("voice") is ring)

# ---------------------------------------------------------------- 4 --
print("\n--- 4: the honesty check ---")
SAID[:] = []
cap = Cap(TD)
cap.t0 = CLOCK[0]
FakeTap.specific = False
gw = os.path.join(TD, "game_00.wav")
r = cap._open_process_tap(100, gw, kind="game", label="game", exe="game.exe",
                          anchor=cap.t0, wait=0)
check("...ring removed, WAV deleted, layer forgotten",
      wait_for(lambda: r["state"] == "failed") and r not in cap.rings
      and not os.path.isfile(gw) and "game" not in cap._taps
      and ns["_TAPWATCH"]["game"]["state"] == "failed")
check("...exactly one 'would only give a system-wide tap' line",
      sum(1 for m in SAID if "would only give a system-wide tap for game.exe (pid 100)" in m) == 1
      and "the game layer is off for this run; the Mix is unaffected" in SAID[-1])
FakeTap.specific = True

# ---------------------------------------------------------------- 5 --
print("\n--- 5: the liveness gate ---")
SAID[:] = []
del FakeTap.made[:]
ALIVE["pids"] = set()
r = cap._open_process_tap(777, gw, kind="game", label="game", exe="game.exe",
                          anchor=cap.t0, wait=0)
check("a dead pid is refused before construction: False, no ctor, no file",
      r is False and FakeTap.made == [] and not os.path.isfile(gw))
check("...with the 'is gone - looking for it again' line",
      SAID == ["Sources: game.exe pid 777 is gone - looking for it again."])
check("...and the row carries the reason (the gao fallback line reads it)",
      ns["_TAPWATCH"]["game"]["err"] == "pid 777 is gone")
SAID[:] = []
ALIVE["pids"] = {778}
ALIVE["other"] = {778}
r = cap._open_process_tap(778, gw, kind="game", label="game", exe="game.exe",
                          anchor=cap.t0, wait=0)
check("a pid alive under another name is refused too, saying 'is not game.exe'",
      r is False and FakeTap.made == [] and not os.path.isfile(gw)
      and SAID == ["Sources: pid 778 is not game.exe - looking for it again."]
      and ns["_TAPWATCH"]["game"]["err"] == "pid 778 does not wear game.exe")
ALIVE["other"] = set()

# ---------------------------------------------------------------- 6 --
print("\n--- 6: async never blocks start() ---")
SAID[:] = []
cap = Cap(TD)
cap.t0 = CLOCK[0]
ALIVE["pids"] = {100}
FakeTap.ctor_sleep = 3.0
t = _real_time.time()
ring = cap._open_process_tap(100, vw, kind="voice", label="voice",
                             exe="discord.exe", anchor=cap.t0, wait=0)
took = _real_time.time() - t
n_thr = len(cap._threads)
check("wait=0 returns in < 50 ms while the ctor sleeps 3 s (%.0f ms)" % (took * 1000),
      took < 0.05 and ring["state"] == "opening")
check("no writer thread yet (one tap thread only)", n_thr == 1)
check("...the ring turns live about 3 s later and the writer starts only then",
      wait_for(lambda: ring["state"] == "live", 8.0) and len(cap._threads) == 2
      and ring["live_at"] is not None)
FakeTap.ctor_sleep = 0.0
cap.signal_stop()
cap.finalize()

# ---------------------------------------------------------------- 7 --
print("\n--- 7: the legacy call ---")
SAID[:] = []
cap = Cap(TD)
sw = os.path.join(TD, "system_00.wav")
r = cap._open_process_tap(100, sw)
ring = cap.rings[0]
check("2-arg call: True, kind 'system', synchronous (live on return), first-sample anchor",
      r is True and ring["kind"] == "system" and ring["state"] == "live"
      and ring["t_first"] is None)
check("...the old log line, and no Sources line",
      SAID == ["Audio: capturing the GAME's own sound only (pid 100)."])
check("...not a layer: absent from _taps, the manifest sees no loopback",
      cap._taps == {} and cap.sources_manifest()["voice"] is None
      and cap.sources_manifest()["media"] == "none")
FakeTap.made[-1].feed(pcm(480))
check("first-sample anchoring as today: t_first = now - nfr/rate",
      abs(ring["t_first"] - (CLOCK[0] - 480 / RATE)) < 1e-6)
cap.signal_stop()
cap.finalize()
SAID[:] = []
cap = Cap(TD)
FakeTap.specific = False
r = cap._open_process_tap(100, sw)
check("legacy failure: False, the old 'using system audio' line, WAV gone",
      r is False and not os.path.isfile(sw)
      and SAID == ["Game-audio tap failed to start (tap fell back to "
                   "system-wide capture); using system audio."])
FakeTap.specific = True

# ---------------------------------------------------------------- 8 --
print("\n--- 8: the run ends before the tap is live ---")
SAID[:] = []
cap = Cap(TD)
cap.t0 = CLOCK[0]
FakeTap.ctor_sleep = 1.0
cap.voice_wav = vw
ring = cap._open_process_tap(100, vw, kind="voice", label="voice",
                             exe="discord.exe", anchor=cap.t0, wait=0)
cap.signal_stop()
cap.finalize()
check("finalize deletes the header-only WAV and voice_wav is None",
      not os.path.isfile(vw) and cap.voice_wav is None and "voice" not in cap._taps
      and ring["state"] == "failed")
check("...said ONCE, by finalize - the post-stop commit is silent",
      sum(1 for m in SAID if "the voice tap never came up in time" in m) == 1
      and not any("the run ended first" in m for m in SAID))
FakeTap.ctor_sleep = 0.0
check("the run dict would see no layer (first_sample_wallclock None)",
      cap.first_sample_wallclock("voice") is None)

print("\n--- the stall clock starts at commit ---")
cap = Cap(TD)
cap.t0 = CLOCK[0]
built_at = CLOCK[0]
FakeTap.ctor_sleep = 0.3
ring = cap._open_process_tap(100, vw, kind="voice", label="voice",
                             exe="discord.exe", anchor=cap.t0, wait=0)
CLOCK[0] += 5.0                          # activation took 5 s
check("cb_at is stamped at commit, not construction",
      wait_for(lambda: ring["state"] == "live")
      and ring["cb_at"] == ring["live_at"] == built_at + 5.0)
FakeTap.ctor_sleep = 0.0
cap.signal_stop()
cap.finalize()

print("\n--- gap_s: the seconds a layer spent not live ---")
cap = Cap(TD)
cap.t0 = CLOCK[0]
ring = cap._open_process_tap(100, vw, kind="voice", label="voice",
                             exe="discord.exe", anchor=cap.t0, wait=0)
wait_for(lambda: ring["state"] == "live")
ring["down_at"] = CLOCK[0] - 30.0
ring["gap_s"] = 12.0
check("sources_manifest sums the closed gaps and the open one",
      cap.sources_manifest()["voice"]["gap_s"] == 42.0)
cap.signal_stop()
cap.finalize()

import shutil
shutil.rmtree(TD, ignore_errors=True)
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
