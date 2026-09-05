# -*- coding: utf-8 -*-
"""3.31 SOURCES - dump_ring with layer rings present.

Borrows the REAL AudioRecorder.dump_ring onto a stand-in (the micheal.py
way) with four fake rings - system, mic, voice, game - each a second of
its own constant sample, under a frozen clock, and proves: the MIC file
is the one returned as the mic (the old else-branch handed back whichever
non-system ring came last, so a clip would have got Discord as its Mic
track); the system file is the system; ends carries all four kinds;
voice_clip.wav / game_clip.wav land at their deterministic names with
their own bytes; trim_tail is honoured per ring; and the old two-ring
shape returns exactly what it always did. Stage C: a tap ring lends a
clip its sound only in state live/reconnected/dead (opening, failed,
gone and '' are skipped), and a ring that has delivered nothing leaves
no header-only <kind>_clip.wav behind."""
import ast
import collections
import io
import os
import shutil
import struct
import sys
import tempfile
import textwrap
import threading
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


def extract(name, ns):
    for node in ast.walk(ast.parse(SRC)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                SRC.splitlines()[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name + " not found")


T = 1_700_000_000.0


class Clock(object):
    @staticmethod
    def time():
        return T


SAID = []
ns = {"os": os, "wave": wave, "time": Clock, "log": SAID.append}
dump_ring = extract("dump_ring", ns)
RATE, CH = 48000, 2


class Cap(object):
    def __init__(self, kinds):
        self.rings = []
        self._ring_lock = threading.Lock()
        for kind, val in kinds:
            chunks = collections.deque()
            chunks.append(struct.pack("<h", val) * (RATE * CH))   # 1 s
            self.rings.append({
                "kind": kind, "rate": RATE, "channels": CH, "chunks": chunks,
                "t_first": T - 1.0, "frames": RATE, "push": chunks.append,
                "frame_bytes": CH * 2, "closed": False,
            })


Cap.dump_ring = dump_ring


def sample_of(path):
    with wave.open(path, "rb") as w:
        n = w.getnframes()
        fr = w.readframes(1)
    return n, struct.unpack("<h", fr[:2])[0]


TD = tempfile.mkdtemp(prefix="dump331_")

print("--- four rings: system, mic, voice, game (the mic is NOT last) ---")
cap = Cap([("system", 1), ("mic", 2), ("voice", 3), ("game", 4)])
sp, mp, ends = cap.dump_ring(TD, 1.0)
check("the mic file is the MIC ring's, not the last non-system ring's",
      mp == os.path.join(TD, "mic_clip.wav") and sample_of(mp) == (RATE, 2))
check("the system file is the system ring's",
      sp == os.path.join(TD, "system_clip.wav") and sample_of(sp) == (RATE, 1))
check("ends carries all four kinds at the ring's last sample",
      sorted(ends) == ["game", "mic", "system", "voice"]
      and all(abs(ends[k] - T) < 1e-6 for k in ends))
vc, gc = os.path.join(TD, "voice_clip.wav"), os.path.join(TD, "game_clip.wav")
check("voice_clip.wav / game_clip.wav land at their deterministic names, own bytes",
      os.path.isfile(vc) and os.path.isfile(gc)
      and sample_of(vc) == (RATE, 3) and sample_of(gc) == (RATE, 4))
check("the return arity is unchanged: (system, mic, ends)",
      isinstance(ends, dict) and mp != sp)

print("\n--- the same rings in another order ---")
TD2 = tempfile.mkdtemp(prefix="dump331_")
cap = Cap([("voice", 3), ("game", 4), ("system", 1), ("mic", 2)])
sp, mp, ends = cap.dump_ring(TD2, 1.0)
check("order does not matter: mic is the mic, system is the system",
      sample_of(mp) == (RATE, 2) and sample_of(sp) == (RATE, 1))

print("\n--- layers without a mic ---")
TD3 = tempfile.mkdtemp(prefix="dump331_")
cap = Cap([("system", 1), ("voice", 3), ("game", 4)])
sp, mp, ends = cap.dump_ring(TD3, 1.0)
check("no mic ring -> mic path None, even with layer rings present",
      mp is None and sample_of(sp) == (RATE, 1)
      and sorted(ends) == ["game", "system", "voice"])

print("\n--- trim_tail, per ring ---")
TD4 = tempfile.mkdtemp(prefix="dump331_")
cap = Cap([("system", 1), ("mic", 2), ("voice", 3), ("game", 4)])
sp, mp, ends = cap.dump_ring(TD4, 1.0, trim_tail=0.25)
check("every ring loses its newest quarter second",
      all(sample_of(os.path.join(TD4, k + "_clip.wav"))[0] == int(RATE * 0.75)
          for k in ("system", "mic", "voice", "game")))
check("...and every end moves back by that quarter second",
      all(abs(ends[k] - (T - 0.25)) < 1e-6 for k in ("system", "mic", "voice", "game")))

print("\n--- tap rings by state ---")
for st, want in (("opening", False), ("failed", False), ("gone", False),
                 ("", False), ("live", True), ("reconnected", True),
                 ("dead", True)):
    TDx = tempfile.mkdtemp(prefix="dump331_")
    cap = Cap([("system", 1), ("mic", 2), ("voice", 3), ("game", 4)])
    for r in cap.rings:
        r["state"] = st                  # every ring: the key alone filters nothing
        if r["kind"] in ("voice", "game"):
            r["is_tap"] = True
    sp, mp, ends = cap.dump_ring(TDx, 1.0)
    have = sorted(f for f in os.listdir(TDx) if f.endswith("_clip.wav"))
    check("tap rings in state %r are %s; the device rings are written whatever the key says"
          % (st, "written" if want else "skipped"),
          sample_of(sp) == (RATE, 1) and sample_of(mp) == (RATE, 2)
          and (have == ["game_clip.wav", "mic_clip.wav", "system_clip.wav", "voice_clip.wav"]
               if want else have == ["mic_clip.wav", "system_clip.wav"])
          and (("voice" in ends and "game" in ends) if want
               else ("voice" not in ends and "game" not in ends)))
    shutil.rmtree(TDx, ignore_errors=True)

print("\n--- no empty clip wav ---")
TD7 = tempfile.mkdtemp(prefix="dump331_")
cap = Cap([("system", 1)])
for kind in ("voice", "mic"):             # two rings that have delivered nothing
    chunks = collections.deque()
    cap.rings.append({"kind": kind, "rate": RATE, "channels": CH, "chunks": chunks,
                      "t_first": None, "frames": 0, "push": chunks.append,
                      "frame_bytes": CH * 2, "closed": False,
                      "is_tap": kind == "voice", "state": "live"})
sp, mp, ends = cap.dump_ring(TD7, 1.0)
check("a live tap ring that delivered nothing leaves no voice_clip.wav and no end",
      not os.path.isfile(os.path.join(TD7, "voice_clip.wav")) and "voice" not in ends)
check("an empty mic ring: no mic_clip.wav, mic path None (the mux never sees a header-only wav)",
      mp is None and not os.path.isfile(os.path.join(TD7, "mic_clip.wav"))
      and sample_of(sp) == (RATE, 1) and sorted(os.listdir(TD7)) == ["system_clip.wav"])
check("nothing was logged for the empty rings", SAID == [])
shutil.rmtree(TD7, ignore_errors=True)

print("\n--- the old shape (system + mic only) is what it always was ---")
TD5 = tempfile.mkdtemp(prefix="dump331_")
cap = Cap([("system", 1), ("mic", 2)])
sp, mp, ends = cap.dump_ring(TD5, 1.0)
check("system and mic, ends for both, nothing else written",
      sample_of(sp) == (RATE, 1) and sample_of(mp) == (RATE, 2)
      and sorted(ends) == ["mic", "system"]
      and sorted(os.listdir(TD5)) == ["mic_clip.wav", "system_clip.wav"])
check("nothing was logged", SAID == [])
check("the docstring names the layer clips and the elif",
      "voice_clip.wav" in dump_ring.__doc__ and "ONLY A RING OF KIND 'mic'" in dump_ring.__doc__)

shutil.rmtree(TD, ignore_errors=True)
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
