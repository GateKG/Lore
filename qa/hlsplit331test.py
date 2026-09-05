# -*- coding: utf-8 -*-
"""3.31 THE SOUND PASS BY SOURCE, on real ffmpeg.

A 60 s night is rendered with five AAC tracks titled Mix / System /
Voice / Game / Mic (the Voice: -35 dBFS noise at 50 % duty with one
+12 dB burst at 25 s; the Game: a -20 dBFS tone with a +15 dB burst at
12 s; the Mic: silence; System = Game; Mix = Voice + Game) and the REAL
_highlights_one is lifted out of lore.py by name with only the outside
stubbed (the laughter ear off, the words empty, the folds and banks
inert, the shelf under tempfile). Holds it to:
  - the pipe stays UNMAPPED and the room and game raws ride the same
    ffmpeg (one disk read): the asplit graph over 0:a:2 + 0:a:4, the
    Game map 0:a:3;
  - hl.src == {loud: room, laugh: none, game: true}; a room mark at the
    25 s shout, a 'game' mark at the 12 s burst, NO room mark near 12 s;
  - the lvl carries room and game curves on the mix's grid, and its
    'db' equals the curve the same function writes for a ONE-track copy
    of the file (the old path, byte-identical arguments to 3.30's);
  - _repick_moments over the room curve keeps the split: a media line
    under the game burst does not turn it into a room mark, hl.src.loud
    stays 'room', a laugh is carried and a stale game mark is not.
Needs the installed LORE ffmpeg; no models, nothing under D:\\Records."""
import ast
import collections
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
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
# the file BEFORE stage D (the reader, 5e38f9b): 3.30's sound command
HEAD = subprocess.run(["git", "-C", ROOT, "show", "5e38f9b:lore.py"],
                      capture_output=True, text=True,
                      encoding="utf-8").stdout
FF = r"C:\Program Files\Lore\ffmpeg\bin\ffmpeg.exe"

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


def lift_assign(name, ns):
    for node in TREE.body:
        if not isinstance(node, ast.Assign):
            continue
        names = []
        for t in node.targets:
            if isinstance(t, ast.Name):
                names.append(t.id)
            elif isinstance(t, ast.Tuple):
                names += [e.id for e in t.elts if isinstance(e, ast.Name)]
        if name in names:
            code = "\n".join(SRC.splitlines()[node.lineno - 1:node.end_lineno])
            exec(compile(textwrap.dedent(code), "<" + name + ">", "exec"), ns)
            return
    raise AssertionError(name + " not assigned")


if not os.path.isfile(FF):
    print("SKIP: the installed LORE ffmpeg is not at " + FF)
    print("\n0 ok, 0 failed")
    sys.exit(0)

TMP = tempfile.mkdtemp(prefix="lore_hlsplit331_")
SHELF = os.path.join(TMP, "Records")
os.makedirs(os.path.join(SHELF, "Bazaar", "Videos"))
SR = 32000
T = 60.0
rng = np.random.default_rng(11)


def wav_write(path, a):
    x = np.clip(np.asarray(a, dtype="float32"), -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())


n = int(T * SR)
tt = np.arange(n) / float(SR)
voice = np.zeros(n, dtype=np.float32)
for s0 in range(0, int(T), 4):                       # 2 s on, 2 s off
    a0, a1 = s0 * SR, min(n, (s0 + 2) * SR)
    voice[a0:a1] = rng.normal(0, 10 ** (-35 / 20.0), a1 - a0)
a0, a1 = int(25.0 * SR), int(26.2 * SR)
voice[a0:a1] = rng.normal(0, 10 ** (-23 / 20.0), a1 - a0)   # +12 dB
game = (10 ** (-20 / 20.0)) * np.sin(2 * np.pi * 440 * tt)
a0, a1 = int(12.0 * SR), int(13.2 * SR)
game[a0:a1] = (10 ** (-5 / 20.0)) * np.sin(2 * np.pi * 440 * tt[a0:a1])
mic = np.zeros(n, dtype=np.float32)
mix = voice + game
P = {}
for nm, arr in (("mix", mix), ("sys", game), ("voice", voice),
                ("game", game), ("mic", mic)):
    P[nm] = os.path.join(TMP, nm + ".wav")
    wav_write(P[nm], arr)
FIVE = os.path.join(SHELF, "Bazaar", "Videos", "Bazaar_20260905_120000.mp4")
ONE = os.path.join(SHELF, "Bazaar", "Videos", "Bazaar_20260905_130000.mp4")
r = subprocess.run([FF, "-y", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=black:s=160x90:r=10", "-i", P["mix"], "-i",
                    P["sys"], "-i", P["voice"], "-i", P["game"], "-i",
                    P["mic"], "-t", str(T), "-map", "0:v", "-map", "1:a",
                    "-map", "2:a", "-map", "3:a", "-map", "4:a", "-map",
                    "5:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a",
                    "aac", "-b:a", "128k",
                    "-metadata:s:a:0", "title=Mix", "-metadata:s:a:1",
                    "title=System", "-metadata:s:a:2", "title=Voice",
                    "-metadata:s:a:3", "title=Game", "-metadata:s:a:4",
                    "title=Mic", FIVE], capture_output=True)
check("the five-track night renders", r.returncode == 0 and os.path.isfile(FIVE))
r = subprocess.run([FF, "-y", "-v", "error", "-i", FIVE, "-map", "0:v",
                    "-map", "0:a:0", "-c", "copy", "-metadata:s:a:0",
                    "title=Mix", ONE], capture_output=True)
check("...and its one-track copy", r.returncode == 0 and os.path.isfile(ONE))

# ------------------------------------------------------------- the lift
LOG = []
CMDS = []
_real_popen = subprocess.Popen


def spy_popen(cmd, *a, **k):
    CMDS.append(list(cmd))
    return _real_popen(cmd, *a, **k)


ns = {"os": os, "json": json, "subprocess": subprocess, "threading": threading,
      "collections": collections, "np": np,
      "SETTINGS": {"ffmpeg_path": FF, "output_dir": SHELF},
      "_AI": {"abort": False, "proc": None, "soft_fail": False, "force": None,
              "force_redo": False, "force_want": "", "done_rev": 0},
      "log": LOG.append, "_popen": spy_popen,
      "_work_dir": lambda: TMP, "_laugh_paths": lambda: None,
      "_speech_times": lambda p: ([], []),
      "_merge_sns_into_hl": lambda p, sns=None: (0, None),
      "_merge_vis_into_hl": lambda p, vis=None: (0, None),
      "_bank_sidecar": lambda p, k: None,
      "_source_busy_add": lambda p: None, "_source_busy_done": lambda p: None,
      "_describer_paths": lambda: None, "_senses_paths": lambda: None,
      "_reader_threads": lambda: 2}
for nm in ("_HL_V", "_LVL_V", "HL_VOICE_GATE_DB", "HL_SHOUT_RISE_DB",
           "HYPE_MIN_RISE", "_TRK_MIX", "_LAYERS", "_Layer", "_REACTION_WORDS"):
    lift_assign(nm, ns)
for nm in ("_thumb_dir", "_ai_sidecar", "_atomic_write_json", "_probe_duration",
           "_audio_track_names", "_track_for", "_mic_track", "_voice_track",
           "_game_track", "_mix_audio_args", "_fan_args", "_layer_args",
           "_ai_run", "_rms_env_pcm16", "_pick_moments", "_pick_shouts",
           "_thin_moments", "_thin_game", "_lvl_curve", "_highlights_one",
           "_repick_moments"):
    extract(nm, ns)
hl_one = ns["_highlights_one"]
side = ns["_ai_sidecar"]

print("\n--- the five-track night ---")
del CMDS[:]
del LOG[:]
ok5 = hl_one(FIVE)
check("the pass runs", ok5 is True)
cmd = CMDS[0] if CMDS else []
ipipe = cmd.index("pipe:1") if "pipe:1" in cmd else -1
check("ONE ffmpeg, the pipe output unmapped (no -map before pipe:1)",
      len(CMDS) == 1 and ipipe > 0 and "-map" not in cmd[:ipipe]
      and cmd[:ipipe] == [FF, "-y", "-loglevel", "error", "-i", FIVE, "-vn",
                          "-ac", "1", "-ar", "8000", "-f", "s16le"])
ifc = cmd.index("-filter_complex") if "-filter_complex" in cmd else -1
check("the room = Voice (0:a:2) + Mic (0:a:4) at parity, mapped to the "
      "room raw",
      ifc > ipipe and cmd[ifc + 1]
      == "[0:a:2][0:a:4]amix=inputs=2:duration=longest:normalize=0[L]"
      and cmd[ifc + 2:ifc + 4] == ["-map", "[L]"]
      and cmd[ifc + 4:ifc + 10] == ["-ac", "1", "-ar", "8000", "-f", "s16le"]
      and cmd[ifc + 10].endswith(".room8.raw"))
check("the Game track (0:a:3) to the game raw, 8 kHz s16le",
      "0:a:3" in cmd and cmd[cmd.index("0:a:3") - 1] == "-map"
      and cmd[cmd.index("0:a:3") + 7].endswith(".game8.raw")
      and cmd[cmd.index("0:a:3") + 1:cmd.index("0:a:3") + 7]
      == ["-ac", "1", "-ar", "8000", "-f", "s16le"])
hl = json.load(io.open(side(FIVE, "hl"), encoding="utf-8"))
lvl = json.load(io.open(side(FIVE, "lvl"), encoding="utf-8"))
ev = hl.get("events") or []
check("hl.src == {loud: room, laugh: none, game: true}",
      hl.get("src") == {"loud": "room", "laugh": "none", "game": True})
room_marks = [e for e in ev if e.get("src") == "room"]
game_marks = [e for e in ev if e.get("kind") == "game"]
check("a room mark within a second of the 25 s shout (%s)"
      % [e["t"] for e in room_marks],
      any(abs(e["t"] - 25.0) <= 1.0 for e in room_marks))
check("a 'game' mark within a second of the 12 s burst, src game (%s)"
      % [e["t"] for e in game_marks],
      any(abs(e["t"] - 12.0) <= 1.0 and e.get("src") == "game"
          for e in game_marks))
check("NO room mark within four seconds of the game burst",
      not any(abs(e["t"] - 12.0) <= 4.0 for e in room_marks))
check("every mark carries a src; the room's rise is over 6 dB",
      all(e.get("src") in ("room", "game") for e in ev)
      and all(e.get("p", 0) >= 6.0 for e in room_marks))
check("the lvl carries room and game curves on the mix's grid, and says "
      "db is the mix",
      "room" in lvl and "game" in lvl
      and len(lvl["room"]) == len(lvl["game"]) == len(lvl["db"])
      and lvl.get("src") == {"db": "mix"})
check("the room curve is silent (-100) between talk and the game's is not",
      min(lvl["room"]) <= -90 and min(lvl["game"]) > -60)
check("the log names the sources",
      any("loud marks from the room" in m and "1 game mark(s)" in m
          for m in LOG))
raws = [p for p in os.listdir(TMP) if p.endswith(".raw")]
check("the raws are cleaned up", raws == [])

print("\n--- the one-track copy: the old path ---")
del CMDS[:]
del LOG[:]
ok1 = hl_one(ONE)
cmd1 = CMDS[0] if CMDS else []
check("the pass runs, ONE ffmpeg, today's exact command",
      ok1 is True and len(CMDS) == 1
      and cmd1 == [FF, "-y", "-loglevel", "error", "-i", ONE, "-vn", "-ac",
                   "1", "-ar", "8000", "-f", "s16le", "pipe:1"])
i0 = HEAD.index('        cmd = [SETTINGS["ffmpeg_path"], "-y", "-loglevel", "error",\n'
                '               "-i", video_path,\n'
                '               "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "pipe:1"]')
check("...which is 3.30's literal (git show HEAD:lore.py)", i0 > 0)
hl1 = json.load(io.open(side(ONE, "hl"), encoding="utf-8"))
lvl1 = json.load(io.open(side(ONE, "lvl"), encoding="utf-8"))
check("the old path stamps loud mix / laugh none / game false, src mix on "
      "every mark",
      hl1.get("src") == {"loud": "mix", "laugh": "none", "game": False}
      and all(e.get("src") == "mix" for e in hl1["events"]))
check("...and its lvl has db + src only (no room, no game)",
      "room" not in lvl1 and "game" not in lvl1
      and lvl1.get("src") == {"db": "mix"})
check("the five-track night's 'db' equals the one-track copy's "
      "(the unmapped pipe is the Mix, untouched by the extra outputs)",
      lvl["db"] == lvl1["db"] and lvl["floor"] == lvl1["floor"]
      and lvl["peak"] == lvl1["peak"] and lvl["dur"] == lvl1["dur"])
check("the log says the mix", any("loud marks from the mix." in m for m in LOG))

print("\n--- the words-known re-pick keeps the split ---")
extract("_speech_times", ns)          # the real one now
stt = {"segments": [{"a": 12000, "b": 13000, "t": "!!!", "src": "media"},
                    {"a": 25000, "b": 26000, "t": "go go go!"}]}
io.open(side(FIVE, "stt"), "w", encoding="utf-8").write(json.dumps(stt))
prior = json.load(io.open(side(FIVE, "hl"), encoding="utf-8"))
prior["events"].append({"t": 40.0, "z": 60.0, "kind": "laugh", "src": "room"})
prior["events"].append({"t": 50.0, "z": 30.0, "kind": "game", "src": "game"})
prior["src"]["laugh"] = "room"
io.open(side(FIVE, "hl"), "w", encoding="utf-8").write(json.dumps(prior))
del LOG[:]
changed = ns["_repick_moments"](FIVE)
hl2 = json.load(io.open(side(FIVE, "hl"), encoding="utf-8"))
ev2 = hl2["events"]
check("the re-pick ran and wrote", changed is True)
check("hl.src.loud stays 'room' and the laugh source rides",
      hl2.get("src", {}).get("loud") == "room"
      and hl2["src"].get("laugh") == "room" and hl2["src"].get("game") is True)
check("the game burst stays a 'game' mark - the media line under it never "
      "made it a room mark",
      any(abs(e["t"] - 12.0) <= 1.0 and e.get("kind") == "game" for e in ev2)
      and not any(abs(e["t"] - 12.0) <= 4.0 and e.get("src") == "room"
                  for e in ev2))
check("the room shout stands, now with its hot line",
      any(abs(e["t"] - 25.0) <= 1.0 and e.get("src") == "room" for e in ev2))
check("the laugh is carried; the stale game mark at 50 s is re-derived away",
      any(e.get("kind") == "laugh" and abs(e["t"] - 40.0) < 0.1 for e in ev2)
      and not any(abs(e["t"] - 50.0) < 0.1 for e in ev2))
check("the log has no 'predates 3.31' tail (no .src.json here)",
      not any("predates 3.31" in m for m in LOG))

shutil.rmtree(TMP, ignore_errors=True)
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
