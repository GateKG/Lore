# -*- coding: utf-8 -*-
"""3.31 THE HYPE CURVE BY SOURCE - the bar, the retone, the tone, the
worker's window prep, the ribbon's export.

Lifts the REAL functions by name: _hype_bar, _ins_retone, _aud_tone and
_JsApi._hype_room out of lore.py; _read_ctl and _hype_prep out of
ai/senses_worker.py (numpy only, no torch). Holds them to:
  (a) _hype_bar: a night of chatter (70 % gated zeros, spoken 0.35 +-
      0.02) is FLAT; three windows at 0.55 make it rise and exactly
      those clear the bar;
  (b) _ins_retone on a room-fed curve retones the funny moment at a
      0.55 window to 'excited' and blanks the one at 0.36 (kind0 kept);
      the same moments under an old (mix) sidecar follow the p85 rule
      to the letter (a hand-computed p85), and a flat room night
      retones nothing;
  (c) _aud_tone on the room: a gated window is 'quiet', a flat night
      'calm' wherever anyone spoke, a rise 'excited' / 'at a peak';
      the mix path is today's;
  (d) _hype_prep: 60 s at 16 k (20 s of noise at -20 dBFS, 40 s of
      zeros): on the room the zero windows yield None and every kept
      window is zero-mean / unit-variance; on the mix every window is
      the raw slice; _read_ctl of a missing file is {};
  (e) _JsApi._hype_room: the deviation from calm with the floor, peaks
      only where the ears named a cause, no quota, flat -> baseline;
  (f) HYPE_GATE_DB (the worker) equals HL_VOICE_GATE_DB (lore.py).
No devices, nothing under D:\\Records, nothing under %LOCALAPPDATA%."""
import ast
import io
import json
import os
import re
import sys
import tempfile
import textwrap
import types

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
WSRC = io.open(os.path.join(ROOT, "ai", "senses_worker.py"),
               encoding="utf-8").read()

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


_TREES = {}


def extract(src, name, ns):
    t = _TREES.get(id(src))
    if t is None:
        t = _TREES[id(src)] = ast.parse(src)
    for node in ast.walk(t):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                src.splitlines()[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name + " not found")


def const(src, name):
    m = re.search(r"^%s\s*=\s*(-?[0-9.]+)" % re.escape(name), src, re.M)
    return float(m.group(1))


TMP = tempfile.mkdtemp(prefix="lore_hype331_")
SIDE = {}
ns = {"os": os, "json": json, "np": np,
      "HYPE_MIN_RISE": const(SRC, "HYPE_MIN_RISE"),
      "_ai_sidecar": lambda p, k: SIDE.get((p, k), os.path.join(TMP, "none"))}
for nm in ("_hype_bar", "_ins_retone", "_aud_tone", "_hype_room"):
    extract(SRC, nm, ns)
_hype_bar = ns["_hype_bar"]
_ins_retone = ns["_ins_retone"]
_aud_tone = ns["_aud_tone"]
_hype_room = ns["_hype_room"]

print("--- (a) _hype_bar ---")
rng = np.random.default_rng(3)
N = 400
v = [0.0] * N
spoken_ix = [i for i in range(N) if i % 10 < 3]          # 30 % spoken
for i in spoken_ix:
    v[i] = round(float(0.35 + rng.uniform(-0.02, 0.02)), 3)
bar0, flat0 = _hype_bar([x for x in v if x > 0])
check("70 % zeros + chatter at 0.35 +- 0.02 is FLAT (bar over its max)",
      flat0 and bar0 > max(v))
hot = [12, 191, 302]
v2 = list(v)
for i in hot:
    v2[i] = 0.55
bar1, flat1 = _hype_bar([x for x in v2 if x > 0])
check("three windows at 0.55 make it rise, and exactly those clear the bar",
      not flat1 and [i for i in range(N) if v2[i] >= bar1] == hot)
check("the bar is at least the floor over the median",
      bar1 >= sorted(x for x in v2 if x > 0)[len(spoken_ix) // 2]
      + ns["HYPE_MIN_RISE"] - 1e-9)
check("under eight readings: bar 1.0, flat", _hype_bar([0.3] * 5) == (1.0, True))

print("\n--- (b) _ins_retone: the room's rule, and the p85 rule for the mix ---")
hop = 3.0


def moments():
    return [{"t": hot[0] * hop + 1.0, "kind": "funny", "why": "a"},
            {"t": 26 * hop + 1.0, "kind": "funny", "why": "b"},
            {"t": 22 * hop + 1.0, "kind": "scary", "why": "c"},
            {"t": 100.0, "kind": "big", "why": "d"}]


v3 = list(v2)
v3[26] = 0.36
v3[22] = 0.0                         # nobody spoke there
sns_room = {"hype": {"hop": hop, "v": v3, "src": "room"}}
ms = moments()
n = _ins_retone(ms, sns_room, {"events": []})
check("room: the funny moment in a 0.55 window becomes 'excited'",
      n == 3 and ms[0]["kind"] == "excited" and ms[0]["kind0"] == "funny")
check("...the one at 0.36 is blanked, kind0 kept",
      ms[1]["kind"] == "" and ms[1]["kind0"] == "funny")
check("...a scary moment in a gated window (0) is never hot",
      ms[2]["kind"] == "" and ms[2]["kind0"] == "scary")
check("...'big' is not the retone's to touch", ms[3]["kind"] == "big"
      and "kind0" not in ms[3])
ms = moments()
n = _ins_retone(ms, sns_room, {"events": [{"t": 40.0, "kind": "laugh"}]})
check("...a laugh within ten seconds lets the funny moment stand",
      ms[0]["kind"] == "funny" and "kind0" not in ms[0] and n == 2)
sns_mix = {"hype": {"hop": hop, "v": v3}}
sv = sorted(v3)
p85 = sv[int(len(sv) * 0.85)]
ms = moments()
n = _ins_retone(ms, sns_mix, {"events": []})
check("mix (src absent): the p85 rule to the letter (p85 = %.3f)" % p85,
      n == 3
      and ms[0]["kind"] == ("excited" if v3[hot[0]] >= p85 else "")
      and ms[1]["kind"] == ("excited" if v3[26] >= p85 else "")
      and ms[2]["kind"] == ("excited" if v3[22] >= p85 else ""))
check("...which promotes the 0.36 window on this fixture (p85 sits under it "
      "because the zeros count) - the very cost the room rule removes",
      ms[1]["kind"] == "excited")
ms = moments()
check("a flat room night retones nothing",
      _ins_retone(ms, {"hype": {"hop": hop, "v": v, "src": "room"}}, {}) == 0
      and ms[0]["kind"] == "funny")
ms = moments()
check("a room night with under twenty spoken windows retones nothing",
      _ins_retone(ms, {"hype": {"hop": hop, "v": [0.0] * 30 + [0.5] * 10,
                                "src": "room"}}, {}) == 0)

print("\n--- (c) _aud_tone ---")
check("room: a gated window is 'quiet'", _aud_tone(sns_room, 22 * hop + 1) == "quiet")
check("room: the 0.55 window is 'at a peak of excitement'",
      _aud_tone(sns_room, hot[1] * hop + 1) == "at a peak of excitement")
check("room: ordinary chatter is 'calm' or 'lively', never 'excited'",
      all(_aud_tone(sns_room, i * hop + 1) in ("calm", "lively")
          for i in spoken_ix if v3[i] < bar1 and v3[i] > 0))
flat_sns = {"hype": {"hop": hop, "v": v, "src": "room"}}
check("room: a flat night is 'calm' wherever anyone spoke",
      all(_aud_tone(flat_sns, i * hop + 1) == "calm" for i in spoken_ix))
mix_tone = _aud_tone(sns_mix, hot[1] * hop + 1)
check("mix: today's p90 words - and a 0 reads 'lively' there, because the "
      "zeros drag the median to 0 (the room rule says 'quiet')",
      mix_tone == "at a peak of excitement"
      and _aud_tone(sns_mix, 22 * hop + 1) == "lively")

print("\n--- (d) the worker's window prep and control file ---")
wns = {"os": os, "json": json, "np": np,
       "HYPE_HOP": const(WSRC, "HYPE_HOP"), "HYPE_WIN": const(WSRC, "HYPE_WIN"),
       "HYPE_GATE_DB": const(WSRC, "HYPE_GATE_DB")}
extract(WSRC, "_read_ctl", wns)
extract(WSRC, "_hype_prep", wns)
_read_ctl = wns["_read_ctl"]
_hype_prep = wns["_hype_prep"]
a16 = np.zeros(60 * 16000, dtype=np.float32)
a16[:20 * 16000] = (rng.normal(0, 0.1, 20 * 16000)).astype(np.float32)  # -20 dBFS
room = list(_hype_prep(np, a16, "room"))
mix = list(_hype_prep(np, a16, "mix"))
hopn, winn = int(3.0 * 16000), int(6.0 * 16000)
check("the same windows on both paths (%d)" % len(mix),
      len(room) == len(mix) == len(range(0, len(a16) - 16000 + 1, hopn))
      and [p for p, _ in room] == [p for p, _ in mix])
check("room: every window past 20 s of zeros yields None (no model call)",
      all(seg is None for p, seg in room if p >= 20 * 16000)
      and all(seg is not None for p, seg in room if p + winn <= 20 * 16000))
kept = [seg for _, seg in room if seg is not None]
check("...and every kept window is zero-mean, unit-variance",
      kept and all(abs(float(seg.mean())) < 1e-3 and abs(float(seg.std()) - 1)
                   < 1e-2 for seg in kept))
check("mix: no None, and every window equals the raw slice",
      all(seg is not None for _, seg in mix)
      and all(np.array_equal(seg, a16[p:p + winn]) for p, seg in mix))
check("_read_ctl of a missing file is {}",
      _read_ctl(os.path.join(TMP, "nope.wav")) == {})
cp = os.path.join(TMP, "x.wav")
io.open(cp + ".ctl", "w", encoding="utf-8").write(
    json.dumps({"src": "room", "game_wav": "g.wav", "mic": None, "threads": 3}))
check("...and of a real one is its dict",
      _read_ctl(cp) == {"src": "room", "game_wav": "g.wav", "mic": None,
                        "threads": 3})
io.open(cp + ".ctl", "w", encoding="utf-8").write("[1, 2]")
check("...a non-dict is {}", _read_ctl(cp) == {})

print("\n--- (e) the ribbon's export for the room ---")
P = os.path.join(TMP, "night.mp4")
hl_p = os.path.join(TMP, "night.hl.json")
SIDE[(P, "hl")] = hl_p
io.open(hl_p, "w", encoding="utf-8").write(json.dumps({"events": [
    {"t": hot[0] * hop + 2, "kind": "laugh", "src": "room"},
    {"t": hot[1] * hop - 3, "kind": "", "src": "room"},
    {"t": hot[2] * hop + 1, "kind": "game", "src": "game"}]}))
self = types.SimpleNamespace()
r = _hype_room(self, P, v2, hop, 1, [round(x, 3) for x in v2])
check("ok, src 'room', the bar and flat False, quiet = the gated share",
      r["ok"] and r["src"] == "room" and r["bar"] == bar1
      and r["flat"] is False and abs(r["quiet"] - 0.7) < 0.01)
check("the deviation is 0 in a gated window, 1.0 at the bar, above 1 past it",
      len(r["dev"]) == N and r["dev"][5] == 0.0
      and all(r["dev"][i] > 1.0 for i in hot)
      and all(0 <= r["dev"][i] < 1.0 for i in spoken_ix if i not in hot))
check("peaks carry a cause: laughter at the first, a shout at the second",
      [p["why"] for p in r["peaks"]]
      == ["laughter", "a shout in the room"]
      and [round(p["t"] / hop) for p in r["peaks"]] == hot[:2])
check("...the third rise has only a game burst near it - no dot",
      not any(abs(p["t"] - hot[2] * hop) < 5 for p in r["peaks"]))
r2 = _hype_room(self, P, v, hop, 1, [round(x, 3) for x in v])
check("a flat night: flat True, no peaks, every deviation 0",
      r2["ok"] and r2["flat"] and r2["peaks"] == []
      and not any(r2["dev"]))
r3 = _hype_room(self, P, [0.0] * 40 + [0.5] * 5, hop, 1, [])
check("under eight spoken windows: not ok, the honest why",
      r3 == {"ok": False, "why": "nobody spoke long enough to have a flow"})
check("_JsApi.hype routes a room curve there and stamps the mix with bar p90",
      'if src == "room":\n            return self._hype_room(p, v, hop, step, vd)'
      in SRC and '"src": "mix", "bar": round(p90, 3), "flat": False' in SRC)

print("\n--- (f) one gate ---")
check("HYPE_GATE_DB (the worker) == HL_VOICE_GATE_DB (lore.py) == -60",
      const(WSRC, "HYPE_GATE_DB") == const(SRC, "HL_VOICE_GATE_DB") == -60.0)
check("the worker's comment names the measurement",
      "qa/sns331time.py" in WSRC)

import shutil
shutil.rmtree(TMP, ignore_errors=True)
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
