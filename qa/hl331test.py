# -*- coding: utf-8 -*-
"""3.31 THE SHOUT PICKER, THE GAME'S BURSTS, THE CURVES - by name.

Lifts the REAL functions out of lore.py (_rms_env_pcm16, _pick_moments,
_pick_shouts, _thin_moments, _thin_game, _lvl_curve, _hype_bar and the
three measured constants) into a stub namespace and holds them to:
  (a) a two-hour synthetic ROOM envelope (a -100 dB gated floor, 30 %
      coverage of -30 dB talk, three +9 dB shouts): _pick_shouts finds
      exactly the three, and _pick_moments on the same envelope marks
      speech instead - the trap its docstring names;
  (b) a flat night marks nothing; (c) a silent night marks nothing;
  (d) _thin_game: half the room's budget, never inside 8 s of a room
      mark, kind and src 'game', in time order;
  (e) _rms_env_pcm16 equals the 3.30 inline loop (lifted out of
      `git show HEAD:lore.py`) to 1e-6 on a pcm buffer;
  (f) _lvl_curve gives the same length for curves that differ by a few
      samples (the room and the game ride the mix's grid);
  (g) the constants carry the measured values and their provenance.
No devices, nothing under D:\\Records, nothing under %LOCALAPPDATA%."""
import ast
import io
import os
import re
import subprocess
import sys
import textwrap

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
# the file BEFORE stage D (the reader, 5e38f9b): the old inline loop
HEAD = subprocess.run(["git", "-C", ROOT, "show", "5e38f9b:lore.py"],
                      capture_output=True, text=True,
                      encoding="utf-8").stdout

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


TREE = ast.parse(SRC)


def extract(name, ns):
    for node in ast.walk(TREE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                SRC.splitlines()[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name + " not found")


def const(name):
    m = re.search(r"^%s\s*=\s*(-?[0-9.]+)" % re.escape(name), SRC, re.M)
    return float(m.group(1))


ns = {"os": os, "np": np}
for nm in ("HL_VOICE_GATE_DB", "HL_SHOUT_RISE_DB", "HYPE_MIN_RISE"):
    ns[nm] = const(nm)
for nm in ("_rms_env_pcm16", "_pick_moments", "_pick_shouts", "_thin_moments",
           "_thin_game", "_lvl_curve", "_hype_bar"):
    extract(nm, ns)
_rms_env_pcm16 = ns["_rms_env_pcm16"]
_pick_moments = ns["_pick_moments"]
_pick_shouts = ns["_pick_shouts"]
_thin_moments = ns["_thin_moments"]
_thin_game = ns["_thin_game"]
_lvl_curve = ns["_lvl_curve"]
_hype_bar = ns["_hype_bar"]

HOP = 0.025


def room_env(hours=2.0, talk_db=-30.0, jitter=2.0, shouts=(), seed=7,
             duty=0.3):
    """A room envelope at 25 ms: a gated floor, talk segments 3-20 s long
    at `duty` coverage, and shouts of +9 dB for 1.2 s."""
    rng = np.random.default_rng(seed)
    n = int(hours * 3600 / HOP)
    e = np.full(n, -100.0, dtype=np.float32)
    t = 0.0
    while t < hours * 3600:
        L = rng.uniform(3, 20)
        i0, i1 = int(t / HOP), min(n, int((t + L) / HOP))
        e[i0:i1] = talk_db + rng.uniform(-jitter, jitter, i1 - i0)
        t += L + L * (1.0 - duty) / duty
    for st in shouts:
        i0, i1 = int(st / HOP), int((st + 1.2) / HOP)
        e[i0:i1] = talk_db + 9.0 + rng.uniform(-0.5, 0.5, i1 - i0)
    return e


print("--- (a) a two-hour room: three shouts, and the trap ---")
SH = (1200.0, 3300.0, 5400.0)
ev = room_env(shouts=SH)
k = np.ones(20, dtype=np.float32) / 20.0
esv = np.convolve(ev, k, mode="same")
got = _pick_shouts(esv, HOP, ())
top = sorted(got, key=lambda e: -e["z"])[:3]
check("_pick_shouts finds the three shouts within a second, as its top three",
      len(got) >= 3 and sorted(round(e["t"]) for e in top)
      == [1200, 3300, 5400]
      and all(min(abs(e["t"] - s) for s in SH) <= 1.0 for e in top))
check("...and nothing else rises 6 dB above the talk",
      all(min(abs(e["t"] - s) for s in SH) <= 2.0 for e in got
          if e["p"] >= 6.0)
      and len(got) == 3)
check("...every mark carries src 'room' and a rise near +9 dB",
      all(e.get("src") == "room" for e in got)
      and all(7.5 <= e["p"] <= 10.5 for e in top))
check("...a hot line beside a shout scores it +6",
      _pick_shouts(esv, HOP, (1200.5,))[0]["z"]
      >= [e for e in got if abs(e["t"] - 1200) < 2][0]["z"] + 5.9)
pm = _pick_moments(esv, HOP)
check("CONTRAST: _pick_moments on the same room envelope marks speech "
      "(> 40 candidates) - the trap the docstring names", len(pm) > 40)
check("...and the docstring names it",
      "Do NOT run it on the\n    room envelope" in SRC
      or "Do NOT run it on the room envelope" in SRC.replace("\n    ", " "))

print("\n--- (b) a flat night, (c) a silent night ---")
flat = np.convolve(room_env(jitter=1.0), k, mode="same")
check("a flat night (talk at -30 +-1 dB, no shouts) marks nothing",
      _pick_shouts(flat, HOP, ()) == [])
silent = np.full(int(7200 / HOP), -100.0, dtype=np.float32)
check("a silent night marks nothing", _pick_shouts(silent, HOP, ()) == [])
check("a night under twenty seconds long marks nothing",
      _pick_shouts(esv[:int(15 / HOP)], HOP, ()) == [])
quiet = room_env(talk_db=-70.0, shouts=(1200.0,))
check("talk under the gate (-70 dB) is nobody talking: nothing to rank",
      _pick_shouts(np.convolve(quiet, k, mode="same"), HOP, ()) == [])

print("\n--- (d) the game's bursts as secondary marks ---")
dur = 3600.0
# six triplets of bursts (three per ten minutes, 50 s apart - exactly
# what the ten-minute promise lets through) of equal score, so
# _thin_moments keeps all 18 and the HALF cap (12) is what bites
gev = [{"t": 600.0 * k2 + 50.0 + 50.0 * j2, "z": 20.0, "p": 8.0}
       for k2 in range(6) for j2 in range(3)]
keep_n = int(min(60, max(8, round(dur / 150.0))))
cap = max(4, keep_n // 2)
room_marks = [{"t": 107.0, "z": 30, "src": "room"},
              {"t": 650.0, "z": 30, "src": "room"},
              {"t": 1307.0, "z": 30, "src": "room"}]
thin = _thin_moments(gev, dur)
cut = sorted(thin, key=lambda e: -e["z"])[:cap]
expect = sorted([e["t"] for e in cut
                 if not any(abs(e["t"] - r["t"]) <= 8.0
                            for r in room_marks)])
out = _thin_game(gev, dur, room_marks)
check("cap = half of _thin_moments' budget (%d of %d)" % (cap, keep_n),
      len(out) <= cap and len(thin) > cap)
check("the three inside 8 s of a room mark are dropped, the rest stand",
      [e["t"] for e in out] == expect
      and len(expect) == len(cut) - sum(
          1 for e in cut if any(abs(e["t"] - r["t"]) <= 8.0
                                for r in room_marks))
      and len(out) == cap - 3
      and any(abs(e["t"] - 107.0) <= 8.0 for e in cut))
check("every survivor is kind 'game', src 'game', in time order",
      all(e["kind"] == "game" and e["src"] == "game" for e in out)
      and [e["t"] for e in out] == sorted(e["t"] for e in out))
check("the inputs are not mutated", all("kind" not in e for e in gev))
check("no bursts, no marks", _thin_game([], dur, room_marks) == [])

print("\n--- (e) _rms_env_pcm16 equals the 3.30 inline loop ---")
i0 = HEAD.index("        env = []\n        carry = np.zeros(0, dtype=np.float32)")
i1 = HEAD.index("        proc.wait(timeout=30)", i0)
old = textwrap.dedent(HEAD[i0:i1])
rng = np.random.default_rng(1)
pcm = (rng.uniform(-0.4, 0.4, 8000 * 95) * 32767).astype("<i2").tobytes()


class _Pipe:
    def __init__(self, b):
        self.b, self.i = b, 0

    def read(self, n):
        c = self.b[self.i:self.i + n]
        self.i += n
        return c


lns = {"np": np, "SR": 8000, "FRAME": 400, "HOP": 200,
       "proc": type("P", (), {"stdout": _Pipe(pcm)})()}
exec(compile(old, "<old-loop>", "exec"), lns)
e_old = np.concatenate(lns["env"])
e_new = _rms_env_pcm16(_Pipe(pcm).read, 8000, 400, 200)
check("the lifted function and the old loop agree to 1e-6 (%d frames)"
      % len(e_old), len(e_old) == len(e_new)
      and float(np.abs(e_old - e_new).max()) < 1e-6)
check("an empty read gives an empty envelope",
      len(_rms_env_pcm16(_Pipe(b"").read)) == 0)
check("a raw file's read and a pipe's read are the same numbers",
      float(np.abs(_rms_env_pcm16(io.BytesIO(pcm).read) - e_new).max())
      < 1e-9)

print("\n--- (f) _lvl_curve on the same grid ---")
n0 = 100000
pts = 1800
c1 = _lvl_curve(np.asarray(esv[:n0]), pts)
c2 = _lvl_curve(np.asarray(esv[:n0 - 3]), pts)
c3 = _lvl_curve(np.asarray(esv[:n0 + 2]), pts)
check("three curves of lengths n, n-3, n+2 give equal lengths",
      len(c1) == len(c2) == len(c3) == pts)
check("the values are the peak of each bucket, as ints",
      all(isinstance(x, int) for x in c1)
      and c1[0] == int(round(float(esv[:max(1, n0 // pts)].max()))))
check("an empty curve is []", _lvl_curve(np.zeros(0), pts) == [])

print("\n--- (g) the constants and their provenance ---")
check("HL_VOICE_GATE_DB = -60 (measured: the lowest five-dB step eight dB "
      "over the median night's floor)", ns["HL_VOICE_GATE_DB"] == -60.0)
check("HL_SHOUT_RISE_DB = 6 (90 % of the words' own shouts clear it)",
      ns["HL_SHOUT_RISE_DB"] == 6.0)
check("HYPE_MIN_RISE = 0.11 (the calm nights' p75)",
      ns["HYPE_MIN_RISE"] == 0.11)
blk = SRC[SRC.index("# 3.31 EXCITEMENT BY SOURCE"):SRC.index("HYPE_MIN_RISE = ")]
check("the comment names the measurement script and the numbers behind them",
      "qa/sns331time.py" in blk and "1.4 %" in blk and "n=1,492" in blk
      and "0.107" in blk)
check("_pick_shouts defaults its gate to the constant and smooths energy",
      "def _pick_shouts(ev, hop_s, hot_said=(), gate_db=HL_VOICE_GATE_DB):"
      in SRC and "10.0 ** (np.asarray(ev, dtype=np.float64) / 10.0)" in SRC)
check("_hype_bar sits before _ins_retone and uses the floor",
      SRC.index("def _hype_bar(") < SRC.index("def _ins_retone(")
      and "med + max(HYPE_MIN_RISE, 3.0 * mad)" in SRC)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
