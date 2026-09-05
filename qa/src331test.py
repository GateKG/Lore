# -*- coding: utf-8 -*-
"""3.31 THE READER BY SOURCE - the worker, and what lore.py hands it.

Drives the REAL functions, never a re-implementation:
  T1-T5  the module-level pieces lifted out of ai/asr_worker.py by name
         (_media_spans, _subtract, _cap_seconds, _load_layer, _rms, the
         sources block) on synthetic 16 kHz arrays;
  T6     the source-order laws, by index in the source;
  T7     _plan_sources + _group_spans with a hand-made VAD: kinds, the
         mic routing, the Mix for media, COPIES for the game, the
         dead-Voice guard, the sums;
  T8     the lore.py side - the auditor's skips, the stale-reader skip,
         the media stand-down, and THE PARITY FIXTURE: _transcribe_one
         lifted from the working file AND from `git show HEAD:lore.py`
         (the file before this reader), run against the same old
         night with a spy in place of ffmpeg and the worker - the audio
         asked for and the worker's arguments must not move;
  T9     the whole worker end to end on a fake night - no torch, no
         Silero, no model: fake modules and a canned llama-server on a
         local port - the room, a video and the game filed by source,
         and the old-file path byte-identical to the HEAD worker's.
No devices, nothing under D:\\Records, nothing under %LOCALAPPDATA%."""
import ast
import base64
import http.server
import importlib.util
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import types
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WPATH = os.path.join(ROOT, "ai", "asr_worker.py")
LPATH = os.path.join(ROOT, "lore.py")
WSRC = io.open(WPATH, encoding="utf-8").read()
LSRC = io.open(LPATH, encoding="utf-8").read()


# THE FILE BEFORE THIS READER is stage B (a7a461f), not whatever HEAD
# happens to be: once the reader was committed HEAD carried it too and
# the parity fixture would have compared the reader with itself.
PRE = "a7a461f"


def git_show(rel):
    return subprocess.run(["git", "-C", ROOT, "show", PRE + ":" + rel],
                          capture_output=True, text=True,
                          encoding="utf-8").stdout


HEAD_L = git_show("lore.py")
HEAD_W = git_show("ai/asr_worker.py")

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


_TREES = {}


def tree_of(src):
    """one parse per source text - lore.py is 31k lines and this file
    lifts from it dozens of times"""
    t = _TREES.get(id(src))
    if t is None:
        t = _TREES[id(src)] = ast.parse(src)
    return t


def extract(src, name, ns):
    for node in ast.walk(tree_of(src)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                src.splitlines()[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name + " not found")


def lift_assign(src, name, ns):
    """exec the module-level assignment that binds `name` (a plain name
    or one of a tuple of names)."""
    for node in tree_of(src).body:
        if not isinstance(node, ast.Assign):
            continue
        names = []
        for t in node.targets:
            if isinstance(t, ast.Name):
                names.append(t.id)
            elif isinstance(t, ast.Tuple):
                names += [e.id for e in t.elts if isinstance(e, ast.Name)]
        if name in names:
            code = "\n".join(src.splitlines()[node.lineno - 1:node.end_lineno])
            exec(compile(textwrap.dedent(code), "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name + " not assigned")


SR = 16000
TMP = tempfile.mkdtemp(prefix="lore_src331_")


def tone(secs, hz, amp=0.3):
    t = np.arange(int(secs * SR)) / float(SR)
    return (amp * np.sin(2 * math.pi * hz * t)).astype("float32")


def burst(total_s, at, hz, amp=0.3):
    """total_s of silence with a tone from at[0] to at[1]."""
    a = np.zeros(int(total_s * SR), dtype="float32")
    s, e = int(at[0] * SR), int(at[1] * SR)
    a[s:e] = tone((e - s) / float(SR), hz, amp)
    return a


def wav_write(path, a, sr=SR):
    x = np.clip(np.asarray(a, dtype="float32"), -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def wav_read(path, dtype="float32"):
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        raw = w.readframes(w.getnframes())
    a = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
    if ch > 1:
        a = a.reshape(-1, ch)
    return a, sr


# a stand-in for soundfile over the wave module (16-bit PCM is all the
# worker ever reads or writes)
SF = types.ModuleType("soundfile")
SF.read = wav_read


def _sf_write(buf, audio, sr, format="WAV", subtype="PCM_16"):
    x = np.clip(np.asarray(audio, dtype="float32"), -1, 1)
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype("<i2").tobytes())


SF.write = _sf_write

# --------------------------------------------------------------- the lifts
wns = {"os": os, "math": math, "re": re, "json": json, "np": np}
for nm in ("CHUNK_S", "GROUP_GAP_S", "MEDIA_SECS_MAX", "GAME_GROUPS_MAX",
           "MEDIA_RATIO", "MEDIA_FLOOR", "DEAD_VOICE_DB", "MIC_EXTRA_MAX"):
    lift_assign(WSRC, nm, wns)
for nm in ("_load_layer", "_rms", "_subtract", "_media_spans",
           "_cap_seconds", "_cap_count", "_sources_block", "_plan_sources",
           "_group_spans"):
    extract(WSRC, nm, wns)
_rms = wns["_rms"]
_subtract = wns["_subtract"]
_media_spans = wns["_media_spans"]
_cap_seconds = wns["_cap_seconds"]
_load_layer = wns["_load_layer"]
_sources_block = wns["_sources_block"]
_plan_sources = wns["_plan_sources"]
_group_spans = wns["_group_spans"]


def db(x):
    return 10 ** (x / 20.0)


print("--- T1: media is what neither the room nor the game explains ---")
N = 10 * SR
mix = burst(10, (3, 6), 440, db(-20))
room = np.zeros(N, dtype="float32")
game = np.zeros(N, dtype="float32")
span = [(3 * SR, 6 * SR)]
got, why = _media_spans(mix, room, game, span, SR)
check("a -20 dBFS burst the room and game are silent for is media",
      got == span)
room2 = burst(10, (3, 6), 440, db(-25))
check("the room carrying it at -25 dBFS (ratio 0.56) explains it",
      _media_spans(mix, room2, game, span, SR)[0] == [])
game2 = burst(10, (3, 6), 440, db(-30))
check("the game at -30 dBFS (0.32) explains it",
      _media_spans(mix, room, game2, span, SR)[0] == [])
game3 = burst(10, (3, 6), 440, db(-35))
check("the game at -35 dBFS (0.18) does not - still media",
      _media_spans(mix, room, game3, span, SR)[0] == span)
quiet = burst(10, (3, 6), 440, db(-50))
check("a -50 dBFS mix burst is under the floor: not attributable",
      _media_spans(quiet, room, game, span, SR)[0] == [])
check("no room layer at all counts as silent (0.0)",
      _media_spans(mix, None, None, span, SR)[0] == span)

print("\n--- T2: why names what was consulted ---")
check("no Game track -> 'mix>voice' (could be the game or a video)",
      _media_spans(mix, room, None, span, SR)[1] == "mix>voice")
check("a Game track -> 'mix>voice,game'",
      _media_spans(mix, room, game, span, SR)[1] == "mix>voice,game")

print("\n--- T3: _subtract, the one cut ---")
s10 = [(0, 10 * SR)]
check("a 10 s span with a 2-4 s cover yields (0-2, 4-10)",
      _subtract(s10, [(2 * SR, 4 * SR)], SR)
      == [(0, 2 * SR), (4 * SR, 10 * SR)])
check("a piece under 0.4 s is dropped",
      _subtract(s10, [(int(0.3 * SR), 10 * SR)], SR) == [])
sixty = _subtract([(0, 60 * SR)], [], SR)
check("a 60 s piece splits at CHUNK_S",
      len(sixty) == 3 and sixty[0] == (0, 28 * SR)
      and sixty[1] == (28 * SR, 56 * SR) and sixty[2] == (56 * SR, 60 * SR))
check("two covers cut two holes",
      _subtract(s10, [(1 * SR, 2 * SR), (5 * SR, 6 * SR)], SR)
      == [(0, SR), (2 * SR, 5 * SR), (6 * SR, 10 * SR)])
check("a cover that swallows the span leaves nothing",
      _subtract(s10, [(0, 10 * SR)], SR) == [])
check("output is sorted whatever the input order",
      _subtract([(5 * SR, 6 * SR), (0, SR)], [], SR)
      == [(0, SR), (5 * SR, 6 * SR)])

print("\n--- T4: the wall keeps the longest ---")
sp = [(0, 5 * SR), (10 * SR, 30 * SR), (40 * SR, 41 * SR), (50 * SR, 60 * SR)]
kept, dn, ds = _cap_seconds(sp, SR, 30)
check("30 s of budget keeps the 20 s and the 10 s spans, in time order",
      kept == [(10 * SR, 30 * SR), (50 * SR, 60 * SR)])
check("...and reports 2 dropped, 6 s unread", dn == 2 and abs(ds - 6) < 1e-6)
kept2, dn2, ds2 = _cap_seconds(sp, SR, 3600)
check("a wall nothing hits drops nothing", kept2 == sp and dn2 == 0 and ds2 == 0)

print("\n--- T5: _load_layer refuses the wrong rate, fits the length ---")
notes = []
p48 = os.path.join(TMP, "v48.wav")
wav_write(p48, np.zeros(48000, dtype="float32"), 48000)
check("a 48 kHz wav is refused with a 'rates differ' note",
      _load_layer(p48, SR, SF, np, notes, "voice", 16000) is None
      and any("rates differ" in n for n in notes))
notes = []
pshort = os.path.join(TMP, "vshort.wav")
wav_write(pshort, np.zeros(8 * SR, dtype="float32"))
x = _load_layer(pshort, SR, SF, np, notes, "voice", 10 * SR)
check("a wav 2 s shorter than the mix is padded to the mix's length",
      x is not None and len(x) == 10 * SR)
check("...and says so", any("2.0s shorter" in n for n in notes))
notes = []
plong = os.path.join(TMP, "vlong.wav")
wav_write(plong, np.zeros(11 * SR, dtype="float32"))
x = _load_layer(plong, SR, SF, np, notes, "game", 10 * SR)
check("a longer one is trimmed and noted",
      len(x) == 10 * SR and any("1.0s longer" in n for n in notes))
notes = []
check("a missing path is None with no note",
      _load_layer("", SR, SF, np, notes, "voice") is None
      and _load_layer(os.path.join(TMP, "nope.wav"), SR, SF, np, notes,
                      "voice") is None and notes == [])
check("half a second of drift is fitted silently",
      (_load_layer(pshort, SR, SF, np, notes, "voice", 8 * SR + 4000)
       is not None) and notes == [])

print("\n--- T6: the source-order laws ---")
i_laugh = WSRC.index('stats["laugh_won"] += 1')
i_media = WSRC.index("THE SECOND AND THIRD PASSES")
i_legacy = WSRC.index("THE MIC LAYER (2.81+): the mic track's own speech")
check("the media pass sits AFTER the laughter second reading",
      i_laugh < i_media)
check("...and BEFORE the legacy mic tagging", i_media < i_legacy)
i_set = WSRC.index("cur_ctx[0] = cctx")
i_back = WSRC.index("cur_ctx[0] = ctx\n")
check("the pass context is set before the passes and put back after",
      i_media < i_set < i_back < i_legacy)
i_loop = WSRC.index("for sg in out:\n                if sg.get(\"src\") in "
                    "(\"media\", \"game\"):\n                    continue")
check("the legacy 0.4-overlap loop skips media/game lines",
      i_legacy < i_loop)
i_dump = WSRC.index('with open(dst + ".tmp", "w", encoding="utf-8") as fh:')
seg_i = WSRC.index('"segments": out', i_dump)
src_i = WSRC.index('"sources": _sources_block', i_dump)
check("'sources' precedes 'segments' in the final dump",
      src_i < seg_i)
_wr = re.search(r"^READER = (\d+)", WSRC, re.M)
_ar = re.search(r"^_STT_READER = (\d+)", LSRC, re.M)
check("READER == 6 in the worker and _STT_READER == 6 in lore.py",
      _wr and _ar and _wr.group(1) == "6" and _ar.group(1) == "6")
check("ask() reads the context through the cell, never the name",
      'if cur_ctx[0] and use_ctx:' in WSRC
      and 'prompt=(cur_ctx[0] if use_ctx else None)' in WSRC
      and 'if ctx and use_ctx' not in WSRC)
check("_last is saved around the passes and restored",
      "_last_room = last" in WSRC and "last = _last_room" in WSRC)
check("the house walls are gated on walls=True",
      "if walls and txt and lang != \"arabic\"" in WSRC
      and "if walls and txt and stats[\"enwall\"]" in WSRC)
check("the room loop reads with walls, the passes without",
      "_read(audio, True, len(audio) / float(sr))" in WSRC
      and "_read(audio, False, len(audio) / float(sr))" in WSRC)
check("the env contract is the reader's",
      all(k in WSRC for k in ("LORE_ASR_VOICE", "LORE_ASR_GAME\"",
                              "LORE_ASR_CONTEXT_MEDIA",
                              "LORE_ASR_CONTEXT_GAME", "LORE_ASR_MEDIA\"",
                              "LORE_ASR_GAME_LINES"))
      and "LORE_ASR_LAYERS" not in WSRC and "LORE_ASR_LAYERS" not in LSRC)
check("the sidecar's transcript src values are only you/media/game",
      sorted(set(re.findall(r'"src": (\S+?)[,}]', WSRC))) == ['kind']
      and 'sg_new["src"] = "you"' in WSRC and 'sg["src"] = "you"' in WSRC
      and '("media", groups_media' in WSRC and '("game", groups_game' in WSRC
      and "'discord'" not in WSRC.replace("\"discord\")", ""))

print("\n--- T7: _plan_sources and _group_spans on a hand-made night ---")


def vad_of(arr):
    """A VAD that reads the truth off the array: 0.5 s frames over a
    -40 dBFS floor, merged into spans, split at CHUNK_S."""
    n = len(arr)
    f = SR // 2
    on = [float(np.sqrt(np.mean(arr[i:i + f] ** 2))) > 0.01
          for i in range(0, n, f)]
    out, s = [], None
    for k, v in enumerate(on + [False]):
        if v and s is None:
            s = k
        elif not v and s is not None:
            a0, b0 = s * f, min(n, k * f)
            while b0 - a0 > 28 * SR:
                out.append((a0, a0 + 28 * SR))
                a0 += 28 * SR
            out.append((a0, b0))
            s = None
    return out


T = 60
mixa = (burst(T, (2, 5), 440) + burst(T, (10, 13), 440)
        + burst(T, (20, 25), 880) + burst(T, (30, 33), 220))
va = burst(T, (2, 5), 440)
ma = burst(T, (10, 13), 440)
ga = burst(T, (30, 33), 220)
ra = va + ma
mm = vad_of(ma)
spans = [{"start": s, "end": e} for s, e in vad_of(ra)]
stats = {"media_dropped": 0, "game_dropped": 0, "media_off": 0}
notes = []
spans2, media, game_read, meta = _plan_sources(
    ra, mixa, ga, spans, SR, vad_of, stats, notes, True, -20.0, True, True)
check("the room's spans come back untouched",
      spans2 is spans and len(spans2) == 2)
check("the 20-25 s video burst is the one media span",
      media == [(20 * SR, 25 * SR)] and meta["why"] == "mix>voice,game")
check("the 30-33 s game burst is the one game span",
      game_read == [(30 * SR, 33 * SR)])
check("the sums: room 6 s, game 3 s, media 5 s, all read",
      abs(meta["room_s"] - 6) < 0.01 and abs(meta["game_s"] - 3) < 0.01
      and abs(meta["media_s"] - 5) < 0.01
      and abs(meta["media_read_s"] - 5) < 0.01
      and abs(meta["game_read_s"] - 3) < 0.01 and meta["media_ran"])
check("the notes say what the layers found",
      any(n.startswith("the video layer found 1 span(s), 5s") for n in notes)
      and any(n.startswith("the game spoke for 3s in 1 span(s)")
              for n in notes))
check("nothing dropped, the guard did not fire",
      stats == {"media_dropped": 0, "game_dropped": 0, "media_off": 0})


def span_audio(s):
    s0, e0 = s["start"], s["end"]
    if s.get("mix"):
        return mixa[s0:e0], 0
    ov = 0
    for x0, y0 in mm:
        if x0 >= e0:
            break
        ov += max(0, min(e0, y0) - max(s0, x0))
    if ov >= 0.9 * max(1, e0 - s0):
        return ma[s0:e0], e0 - s0
    return ra[s0:e0], 0


groups = _group_spans(spans2, span_audio, SR, "room")
gm = _group_spans([{"start": s, "end": e} for s, e in media],
                  lambda s: (mixa[s["start"]:s["end"]], 0), SR, "media")
gg = _group_spans([{"start": s, "end": e} for s, e in game_read],
                  lambda s: (np.array(ga[s["start"]:s["end"]]), 0), SR,
                  "game")
check("room groups carry kind 'room'; his 10-13 s span routed to the mic",
      [g["kind"] for g in groups] == ["room", "room"]
      and groups[0]["mic"] == 0 and groups[1]["mic"] == 3 * SR)
check("media groups slice the MIX (a view on it)",
      gm[0]["kind"] == "media" and gm[0]["parts"][0].base is mixa)
check("game groups are COPIES (the layer can be released)",
      gg[0]["kind"] == "game" and gg[0]["parts"][0].base is None
      and np.array_equal(gg[0]["parts"][0], ga[30 * SR:33 * SR]))
# the dead-Voice night: a silent tap while the Mix carries 70 s of speech
T2 = 90
mix_d = burst(T2, (5, 75), 880)
va_d = np.zeros(T2 * SR, dtype="float32")
stats = {"media_dropped": 0, "game_dropped": 0, "media_off": 0}
notes = []
sp_d, med_d, game_d, meta_d = _plan_sources(
    va_d, mix_d, None, [], SR, vad_of, stats, notes, True, -120.0, True, True)
check("dead Voice + 70 s unexplained: media detection stands down",
      stats["media_off"] == 1 and med_d == [] and not meta_d["media_ran"])
check("...the unexplained spans joined the room, routed to the mix",
      len(sp_d) == 3 and all(s.get("mix") for s in sp_d)
      and sp_d[0]["start"] == 5 * SR)
check("...and the note says it plainly",
      any("silent for the whole night while the mix carries 70s" in n
          for n in notes))
gd = _group_spans(sp_d, lambda s: ((mix_d if s.get("mix") else va_d)
                                   [s["start"]:s["end"]], 0), SR, "room")
check("...and those groups read the MIX", gd[0]["parts"][0].base is mix_d)
# a dead Voice with under 60 s unexplained is trusted (a quiet night)
stats = {"media_dropped": 0, "game_dropped": 0, "media_off": 0}
mix_q = burst(T2, (5, 35), 880)
sp_q, med_q, _g, meta_q = _plan_sources(
    va_d, mix_q, None, [], SR, vad_of, stats, notes, True, -120.0, True, True)
check("a silent tap with under 60 s unexplained is trusted: media",
      stats["media_off"] == 0 and len(med_q) == 2 and meta_q["media_ran"])
# an old file: no layers -> nothing runs
stats = {"media_dropped": 0, "game_dropped": 0, "media_off": 0}
notes = []
sp_o, med_o, game_o, meta_o = _plan_sources(
    mixa, mixa, None, spans, SR, vad_of, stats, notes, False, -120.0, True,
    True)
check("an old file: the spans it was given, no media, no game, no notes",
      sp_o is spans and med_o == [] and game_o == [] and notes == []
      and not meta_o["media_ran"] and meta_o["why"] == "")
# media off by env / game lines counted but not read
stats = {"media_dropped": 0, "game_dropped": 0, "media_off": 0}
notes = []
_s, med_x, game_x, meta_x = _plan_sources(
    ra, mixa, ga, spans, SR, vad_of, stats, notes, True, -20.0, False, False)
check("LORE_ASR_MEDIA=0: no media; GAME_LINES=0: game counted, not read",
      med_x == [] and not meta_x["media_ran"] and game_x == []
      and abs(meta_x["game_s"] - 3) < 0.01
      and any("counted, not read" in n for n in notes))
# the media wall
stats = {"media_dropped": 0, "game_dropped": 0, "media_off": 0}
notes = []
wns["MEDIA_SECS_MAX"] = 3
_s, med_w, _g, meta_w = _plan_sources(
    ra, mixa, ga, spans, SR, vad_of, stats, notes, True, -20.0, True, True)
wns["MEDIA_SECS_MAX"] = 1800
check("a 3 s media wall against a 5 s video: 0 read, 1 dropped, 5 s counted",
      med_w == [] and stats["media_dropped"] == 1
      and abs(meta_w["media_s"] - 5) < 0.01 and meta_w["media_read_s"] == 0
      and any("went unread" in n for n in notes))
blk = _sources_block(True, False, True, 12.25, 3.0, 15.0, 0.0, 5.0, 5.0,
                     0.0, {"media_dropped": 1, "game_dropped": 0,
                           "media_off": 0})
check("the sources block: game_s is None without a Game track, keys whole",
      blk["game_s"] is None and blk["voice_s"] == 12.2
      and blk["media_dropped"] == 1 and blk["media"] is True
      and list(blk) == ["v", "voice", "game", "media", "voice_s", "mic_s",
                        "room_s", "game_s", "media_s", "media_read_s",
                        "game_read_s", "media_dropped", "game_dropped",
                        "media_off"])

# =========================================================================
print("\n--- T8: the lore.py side ---")
LIB = os.path.join(TMP, "Records")
TH = os.path.join(LIB, ".lore_thumbs")
os.makedirs(TH)
LOGS = []


def side(p, kind):
    return os.path.join(TH, os.path.splitext(os.path.basename(p))[0]
                        + "." + kind + ".json")


def wjson(p, d):
    io.open(p, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False))


lns = {"os": os, "json": json, "re": re, "time": time, "log": LOGS.append,
       "SETTINGS": {"output_dir": LIB, "ffmpeg_path": "FF"},
       "_ai_sidecar": side, "_AI": {}}
for nm in ("_AUD_WORDS", "_AUD_SOUND", "_AUD_EYE", "_AUD_LAYERS"):
    lift_assign(LSRC, nm, lns)
for nm in ("_aud_voice", "_aud_says", "_aud_garble", "_aud_dossier",
           "_speech_times", "_src_media_possible", "_asr_context_media",
           "_asr_context_game", "_seg_layer"):
    extract(LSRC, nm, lns)
lns["_aud_tone"] = lambda sns, t: ""
lns["_REACTION_WORDS"] = ("no way",)
lns["_display_name"] = lambda x: x
extract(LSRC, "_parse_clip_name", lns)

STT = [{"a": 1000, "b": 3000, "t": "this is the video talking now",
        "src": "media"},
       {"a": 9000, "b": 11000, "t": "we are going in", },
       {"a": 30000, "b": 32000, "t": "The enemy has slain your ally",
        "src": "game"}]
lay, det = lns["_aud_says"](2.0, {"stt": STT, "sns": {}})
check("_aud_says: a media line within 4 s is no 'words' witness",
      "words" not in lay)
lay, det = lns["_aud_says"](10.0, {"stt": STT, "sns": {}})
check("...a room line is", "words" in lay and "going in" in det["words"])
lay, det = lns["_aud_says"](31.0, {"stt": STT, "sns": {}})
check("...a game line is not either", "words" not in lay)
freq = {w: 50 for w in "we are going in".split()}
zh = [{"a": 1000, "b": 2000, "t": "\u4f60\u597d\u4e16\u754c", "src": "media"},
      {"a": 5000, "b": 6000, "t": "\u4f60\u597d\u4e16\u754c"}]
g_out = lns["_aud_garble"](zh, freq)
check("_aud_garble: a Chinese-alphabet MEDIA line is not struck",
      not any(abs(float(x.get("t") or 0) - 1.0) < 0.5 for x in g_out))
check("...and one without src still is",
      any(abs(float(x.get("t") or 0) - 5.0) < 0.5 for x in g_out))
dos = lns["_aud_dossier"]({"t": 10.0}, {"stt": STT, "sns": {}}, {})
check("_aud_dossier: the video's line is left out and a note stands in",
      "video talking" not in dos and "a video was playing in the "
      "background here" in dos and "going in" in dos)
# _aud_vocab over a scratch shelf
vns = dict(lns)
vns["_AUD_VOCAB"] = {"freq": None, "low": None, "at": 0}
vns["_AUD_VOCAB_LOCK"] = threading.Lock()
vns["_thumb_dir"] = lambda out: TH
extract(LSRC, "_aud_vocab", vns)
wjson(os.path.join(TH, "v1.stt.json"), {"segments": [
    {"a": 0, "b": 1, "t": "Quilboar build is dead", "src": "media"},
    {"a": 2, "b": 3, "t": "we push now"},
    {"a": 4, "b": 5, "t": "Announcer voice", "src": "game"}]})
freq, low = vns["_aud_vocab"]()
check("_aud_vocab: a word only a video said counts 0; the room's count",
      freq.get("quilboar", 0) == 0 and freq.get("push", 0) == 1
      and freq.get("announcer", 0) == 0)
# _speech_times (stage A) still skips
vp = os.path.join(LIB, "Bazaar", "Videos", "Bazaar_20260901_120000.mp4")
os.makedirs(os.path.dirname(vp))
io.open(vp, "wb").write(b"\0" * 200000)
wjson(side(vp, "stt"), {"segments": STT})
said, hot = lns["_speech_times"](vp)
check("_speech_times: only the room's second", said == [9.0])
# the media stand-down reads .src.json
check("no .src.json: media detection is possible",
      lns["_src_media_possible"](vp, 1000) is True)
wjson(side(vp, "src"), {"layers": {"media": False}, "runs": []})
check("layers.media false -> stood down",
      lns["_src_media_possible"](vp, 1000) is False)
wjson(side(vp, "src"), {"layers": {"media": True}, "runs": [
    {"sources": {"voice": {"state": "dead", "gap_s": 3.0}}}]})
check("a voice tap that died -> stood down",
      lns["_src_media_possible"](vp, 1000) is False)
wjson(side(vp, "src"), {"layers": {"media": True}, "runs": [
    {"sources": {"voice": {"state": "live", "gap_s": 90.0}}},
    {"sources": {"voice": {"state": "live", "gap_s": 30.0}}}]})
check("120 s of gap over a 1000 s night (>10%) -> stood down",
      lns["_src_media_possible"](vp, 1000) is False)
check("...but not over a 2000 s night",
      lns["_src_media_possible"](vp, 2000) is True)
wjson(side(vp, "src"), {"layers": {"media": True}, "runs": [
    {"sources": {"voice": {"state": "gone", "gap_s": 5.0}}}]})
check("a tap that went (Discord closed) is honest",
      lns["_src_media_possible"](vp, 1000) is True)
check("the contexts are built in lore.py, the game one names the shelf",
      lns["_asr_context_media"]().startswith("Narration or dialogue")
      and lns["_asr_context_game"](vp)
      == "In-game dialogue, announcer and voice lines from Bazaar.")
# the stale-reader skip
sns_ = {"os": os, "re": re, "_STT_RD_CACHE": {}, "_STT_TRK_CACHE": {},
        "_ai_sidecar": side}
for nm in ("_STT_READER", "_STT_READER_TRACKS"):
    lift_assign(LSRC, nm, sns_)
PROBES = []


def names_of(p):
    PROBES.append(p)
    return NAMES.get(os.path.basename(p), [])


sns_["_audio_track_names"] = names_of
for nm in ("_stt_reader_of", "_stt_has_layers", "_stt_stale_reader"):
    extract(LSRC, nm, sns_)
NAMES = {}
old_v = os.path.join(LIB, "Bazaar", "Videos", "Bazaar_20260101_120000.mp4")
io.open(old_v, "wb").write(b"\0" * 200000)
NAMES[os.path.basename(old_v)] = ["mix", "system", "mic"]
io.open(side(old_v, "stt"), "w", encoding="utf-8").write(
    '{"v": 3, "model": "m", "engine": "qwen3-asr", "counters": {}, '
    '"reader": 5, "segments": []}')
check("a reader-5 transcript of a Mix/System/Mic night is NOT stale",
      sns_["_stt_stale_reader"](old_v) is False and len(PROBES) == 1)
sns_["_stt_stale_reader"](old_v)
check("...and the probe ran once (cached on the file's clock)",
      len(PROBES) == 1)
NAMES[os.path.basename(old_v)] = ["mix", "voice", "game", "mic"]
sns_["_STT_TRK_CACHE"].clear()
check("the same transcript of a Voice/Game night IS stale",
      sns_["_stt_stale_reader"](old_v) is True)
io.open(side(old_v, "stt"), "w", encoding="utf-8").write(
    '{"v": 3, "reader": 4, "segments": []}')
NAMES[os.path.basename(old_v)] = ["mix", "system", "mic"]
sns_["_STT_RD_CACHE"].clear()
sns_["_STT_TRK_CACHE"].clear()
check("a reader-4 transcript is stale whatever the tracks (5 changed words)",
      sns_["_stt_stale_reader"](old_v) is True)
check("reread_old stays off: no DEFAULTS entry, only ever read with .get",
      re.search(r'"reread_old":\s*True', LSRC) is None
      and LSRC.count('SETTINGS.get("reread_old")') >= 2)
i_g = LSRC.index("for sg in sd2.get(\"segments\") or []:")
check("the g-flag loop skips media/game lines first",
      LSRC.index('if sg.get("src") in ("media", "game"):', i_g)
      < LSRC.index("mid = ((sg.get(\"a\") or 0)", i_g))
check("ask_video prefixes (video) / (game)",
      "pre = (\"(video) \" if sg.get(\"src\") == \"media\"" in LSRC)

print("\n--- T8b: THE PARITY FIXTURE - _transcribe_one against HEAD ---")
WORK = os.path.join(TMP, "work")
os.makedirs(WORK)


def make_ns(src_text, calls, worker_doc, first_rc=None):
    ns = {"os": os, "json": json, "re": re, "time": time, "threading":
          threading, "subprocess": subprocess, "collections":
          __import__("collections"), "log": calls["log"].append,
          "SETTINGS": {"ffmpeg_path": "FF", "output_dir": LIB,
                       "read_game_lines": True, "audio_mode": "separate"},
          "_AI": {"abort": False, "failed": {}, "index": None,
                  "soft_fail": False, "job_secs": 0.0, "prog_file": None},
          "_reader_paths": lambda: ("PY", "WORK"),
          "_worker_reader_gen": lambda: 0,
          "_work_dir": lambda: WORK,
          "_source_busy_add": lambda p: None,
          "_source_busy_done": lambda p: None,
          "_audio_track_names": lambda p: NAMES.get(os.path.basename(p),
                                                    []),
          "_probe_duration": lambda p: 1000.0,
          "_models_dir": lambda: TMP,
          "_write_reader_budget": lambda c: 4,
          "_reader_threads": lambda: 4,
          "_asr_gguf_paths": lambda: None,
          "_game_has_focus": lambda: False,
          "_ai_sidecar": side, "_bank_sidecar": lambda p, k: None,
          "_atomic_write_json": wjson, "_STT_V": 3,
          "_STT_ENGINE": "qwen3-asr",
          "_repick_moments": lambda p: None,
          "_game_sources_note": lambda p, s: calls["note"].append(s),
          "_display_name": lambda x: x}
    for nm in ("_TRK_MIX", "_LAYERS", "_Layer", "_STT_READER"):
        try:
            lift_assign(src_text, nm, ns)
        except AssertionError:
            pass
    for nm in ("_track_for", "_mic_track", "_voice_track", "_game_track",
               "_mix_audio_args", "_fan_args", "_layer_args",
               "_extract_layers", "_asr_context_for", "_asr_context_media",
               "_asr_context_game", "_src_media_possible", "_parse_clip_name",
               "_transcribe_one"):
        try:
            extract(src_text, nm, ns)
        except AssertionError:
            pass
    state = {"n": 0}

    def spy_run(cmd, timeout, flags, env=None):
        calls["run"].append((list(cmd), dict(env) if env else None))
        state["n"] += 1
        if cmd[0] == "FF":
            for x in cmd:
                if x.endswith(".wav"):
                    wav_write(x, np.zeros(SR, dtype="float32"))
            if first_rc is not None and state["n"] == 1:
                return first_rc, b"", b""
            return 0, b"", b""
        outj = cmd[3]
        wjson(outj, worker_doc)
        return 0, b"", b""
    ns["_ai_run"] = spy_run
    return ns


DOC_OLD = {"segments": [{"a": 1000, "b": 2000, "t": "we are going in"}],
           "model": "m", "engine": "qwen3-asr", "reader": 5,
           "counters": {"leash": 1}, "notes": []}


def run_one(src_text, vpath, doc=DOC_OLD, first_rc=None):
    calls = {"run": [], "log": [], "note": []}
    ns = make_ns(src_text, calls, doc, first_rc)
    got = ns["_transcribe_one"](vpath)
    return got, calls


def out_blocks(cmd):
    """an ffmpeg command's per-output argument blocks, after '-i path'
    (a hoisted global -filter_complex, the resolver's spelling for a
    graph shared by outputs, is left out of the blocks)"""
    tail = cmd[cmd.index("-i") + 2:]
    if tail and tail[0] == "-filter_complex":
        tail = tail[2:]
    blocks, cur = [], []
    for x in tail:
        cur.append(x)
        if x.endswith(".wav"):
            blocks.append(cur)
            cur = []
    return blocks


def wenv(calls):
    """the worker call's argv and its LORE_* env"""
    for cmd, env in calls["run"]:
        if cmd[0] == "PY":
            return cmd, {k: v for k, v in (env or {}).items()
                         if k.startswith("LORE_") or k.startswith("HF_")}
    return None, None


for names, label in ((["mix", "system", "mic"], "a Mix/System/Mic night"),
                     ([], "a one-track night"),
                     (["mix"], "a one-track 'mix' night"),
                     (["system", "mic"], "a System/Mic night")):
    NAMES[os.path.basename(old_v)] = names
    ok_h, c_h = run_one(HEAD_L, old_v)
    ok_n, c_n = run_one(LSRC, old_v)
    ff_h = [c for c, e in c_h["run"] if c[0] == "FF"]
    ff_n = [c for c, e in c_n["run"] if c[0] == "FF"]
    check("%s: both readers succeed" % label, ok_h and ok_n)
    check("%s: ONE ffmpeg read where HEAD made %d" % (label, len(ff_h)),
          len(ff_n) == 1)
    head_blocks = sum((out_blocks(c) for c in ff_h), [])
    new_blocks = out_blocks(ff_n[0])
    if names == ["system", "mic"]:
        # NO MIX TITLE (a shape the 2.81+ recorder never writes): the
        # resolver hoists the same amix graph before the outputs and
        # labels its pad [G0] instead of [a] - the same two inputs summed
        # the same way, spelled once for two consumers
        gh = ff_h[0][ff_h[0].index("-filter_complex") + 1]
        gn = ff_n[0][ff_n[0].index("-filter_complex") + 1]
        check("%s: the same amix graph, hoisted and relabelled" % label,
              gh.replace("[a]", "") == gn.replace("[G0]", "")
              and new_blocks[0][:3] == ["-vn", "-map", "[G0]"]
              and head_blocks[0][-7:] == new_blocks[0][-7:]
              and head_blocks[1] == [x for x in new_blocks[1] if x != "-vn"])
    else:
        # HEAD's mic command carried no '-vn' (an audio-only output
        # anyway); every other token of every output is identical
        same = (len(head_blocks) == len(new_blocks) and all(
            (hb == nb) or (hb == [x for x in nb if x != "-vn"]
                           and nb[0] == "-vn")
            for hb, nb in zip(head_blocks, new_blocks)))
        check("%s: the audio asked for is HEAD's, output for output" % label,
              same and ff_n[0][:6] == ff_h[0][:6])
        check("%s: the MIX block is byte-identical to HEAD's whole command"
              % label, ff_n[0][:6] + new_blocks[0] == ff_h[0])
    a_h, e_h = wenv(c_h)
    a_n, e_n = wenv(c_n)
    check("%s: the worker's argv is byte-identical" % label, a_h == a_n)
    check("%s: ...and its environment (no new keys)" % label,
          e_h == e_n and "LORE_ASR_VOICE" not in e_n)
    sc = json.load(io.open(side(old_v, "stt"), encoding="utf-8"))
    check("%s: the sidecar gains 'sources' between run and segments, "
          "all-false from a reader-5 doc" % label,
          list(sc)[-3:] == ["run", "sources", "segments"]
          and sc["sources"] == {"voice": False, "game": False,
                                "media": False})
    check("%s: the log counts the room; the ledger is handed nothing to "
          "vote on" % label,
          any(l == "Transcribed %s: 1 lines." % os.path.basename(old_v)
              for l in c_n["log"])
          and all(not (n.get("voice") or n.get("game"))
                  for n in c_n["note"]))

NAMES[os.path.basename(old_v)] = ["mix", "voice", "game", "mic"]
DOC_NEW = {"segments": [{"a": 1000, "b": 2000, "t": "we are going in"},
                        {"a": 5000, "b": 7000, "t": "a video line",
                         "src": "media", "why": "mix>voice,game"},
                        {"a": 9000, "b": 9500, "t": "Announcer",
                         "src": "game", "why": "game tap"}],
           "model": "m", "engine": "qwen3-asr-gguf", "reader": 6,
           "counters": {"media_lines": 1, "game_lines": 1, "media_off": 0},
           "notes": ["the video layer found 1 span(s), 2s of speech"],
           "sources": {"v": 1, "voice": True, "game": True, "media": True,
                       "voice_s": 130.0, "mic_s": 10.0, "room_s": 140.0,
                       "game_s": 0.5, "media_s": 2.0, "media_read_s": 2.0,
                       "game_read_s": 0.5, "media_dropped": 0,
                       "game_dropped": 0, "media_off": 0}}
try:
    os.remove(side(old_v, "src"))
except OSError:
    pass
ok_n, c_n = run_one(LSRC, old_v, DOC_NEW)
ff_n = [c for c, e in c_n["run"] if c[0] == "FF"]
a_n, e_n = wenv(c_n)
wav0 = [x for x in ff_n[0] if x.endswith(".wav")][0]
check("a Voice/Game night: one ffmpeg read, four outputs, no graph",
      ok_n and len(ff_n) == 1 and len(out_blocks(ff_n[0])) == 4
      and "-filter_complex" not in ff_n[0])
check("...the Mix at the wav, Mic/Voice/Game beside it, by TITLE",
      [b[-1] for b in out_blocks(ff_n[0])]
      == [wav0, wav0 + ".mic.wav", wav0 + ".voice.wav", wav0 + ".game.wav"]
      and out_blocks(ff_n[0])[2][2] == "0:a:1"
      and out_blocks(ff_n[0])[3][2] == "0:a:2")
check("...argv stays [py, work, wav, outj, micwav]",
      a_n == ["PY", "WORK", wav0, wav0 + ".json", wav0 + ".mic.wav"])
check("...env carries the reader's keys",
      e_n.get("LORE_ASR_VOICE") == wav0 + ".voice.wav"
      and e_n.get("LORE_ASR_GAME") == wav0 + ".game.wav"
      and e_n.get("LORE_ASR_CONTEXT_MEDIA", "").startswith("Narration")
      and e_n.get("LORE_ASR_CONTEXT_GAME") == "In-game dialogue, announcer "
      "and voice lines from Bazaar." and e_n.get("LORE_ASR_GAME_LINES") == "1"
      and "LORE_ASR_MEDIA" not in e_n
      and e_n.get("LORE_ASR_CONTEXT", "").startswith("Gaming session of "
                                                     "Bazaar."))
sc = json.load(io.open(side(old_v, "stt"), encoding="utf-8"))
check("...the sidecar carries the worker's sources block before segments",
      list(sc)[-3:] == ["run", "sources", "segments"]
      and sc["sources"]["voice_s"] == 130.0)
check("...the log counts by source and the guards line names them",
      any(l == "Transcribed %s: 1 lines, 1 from a video, 1 from the game."
          % os.path.basename(old_v) for l in c_n["log"])
      and any("1 line(s) filed to a video, 1 to the game." in l
              for l in c_n["log"]))
check("...the ledger is told", c_n["note"] == [DOC_NEW["sources"]])
check("...and the scratch layers are cleaned up",
      not os.path.exists(wav0 + ".voice.wav")
      and not os.path.exists(wav0 + ".game.wav")
      and not os.path.exists(wav0 + ".mic.wav") and not os.path.exists(wav0))
wjson(side(old_v, "src"), {"layers": {"media": True}, "runs": [
    {"sources": {"voice": {"state": "dead", "gap_s": 3.0}}}]})
DOC_DEAD = dict(DOC_NEW)
DOC_DEAD["counters"] = {"media_lines": 0, "game_lines": 0, "media_off": 1,
                        "leash": 1}
ok_n, c_n = run_one(LSRC, old_v, DOC_DEAD)
a_n, e_n = wenv(c_n)
check("a night whose voice tap died: LORE_ASR_MEDIA=0 and the log says why",
      e_n.get("LORE_ASR_MEDIA") == "0"
      and any(l.endswith("media detection stood down (no loopback layer / "
                         "the voice tap was lost mid-night).")
              for l in c_n["log"]))
check("...and the guards line owns up to the stand-down",
      any(l.endswith("0 line(s) filed to a video, 0 to the game (the Voice "
                     "layer was not trusted - media detection stood down).")
          for l in c_n["log"]))
os.remove(side(old_v, "src"))
ok_n, c_n = run_one(LSRC, old_v, DOC_OLD, first_rc=1)
ff_n = [c for c, e in c_n["run"] if c[0] == "FF"]
a_n, e_n = wenv(c_n)
check("the failure ladder: rc=1 on the layered read -> one plain retry",
      ok_n and len(ff_n) == 2 and len(out_blocks(ff_n[0])) == 4
      and len(out_blocks(ff_n[1])) == 2)
check("...logged as the mux's line, and the worker hears the mix",
      any(l == "The Voice layer of %s would not extract (ffmpeg rc=1); "
          "the reader hears the mix instead." % os.path.basename(old_v)
          for l in c_n["log"])
      and "LORE_ASR_VOICE" not in e_n and "LORE_ASR_GAME" not in e_n)
NAMES[os.path.basename(old_v)] = ["mix", "voice", "mic"]
ok_n, c_n = run_one(LSRC, old_v, DOC_NEW)
ff_n = [c for c, e in c_n["run"] if c[0] == "FF"]
a_n, e_n = wenv(c_n)
check("a Voice-only night: 'game' falls to the mix and is NOT handed over",
      len(out_blocks(ff_n[0])) == 3 and "LORE_ASR_GAME" not in e_n
      and e_n.get("LORE_ASR_VOICE", "").endswith(".voice.wav"))
NAMES[os.path.basename(old_v)] = ["mix", "game", "mic"]
ok_n, c_n = run_one(LSRC, old_v, DOC_NEW)
a_n, e_n = wenv(c_n)
check("a Game-only night (the voice app closed): GAME handed over, no VOICE",
      e_n.get("LORE_ASR_GAME", "").endswith(".game.wav")
      and "LORE_ASR_VOICE" not in e_n)

# =========================================================================
print("\n--- T9: the whole worker on a fake night (no torch, no model) ---")


def fake_vad(arr, model, sampling_rate=16000, min_silence_duration_ms=300,
             max_speech_duration_s=None, speech_pad_ms=0, **kw):
    """Silero's shape over an energy detector: 20 ms frames, -40 dBFS."""
    sr = sampling_rate
    f = sr // 50
    n = len(arr)
    on = [float(np.sqrt(np.mean(arr[i:i + f] ** 2))) > 0.01
          for i in range(0, n, f)]
    runs, s = [], None
    for k, v in enumerate(on + [False]):
        if v and s is None:
            s = k
        elif not v and s is not None:
            runs.append([s * f, min(n, k * f)])
            s = None
    gap = int(min_silence_duration_ms / 1000.0 * sr)
    merged = []
    for a0, b0 in runs:
        if merged and a0 - merged[-1][1] < gap:
            merged[-1][1] = b0
        else:
            merged.append([a0, b0])
    pad = int(speech_pad_ms / 1000.0 * sr)
    out = []
    for a0, b0 in merged:
        a0, b0 = max(0, a0 - pad), min(n, b0 + pad)
        if max_speech_duration_s:
            mx = int(max_speech_duration_s * sr)
            while b0 - a0 > mx:
                out.append({"start": a0, "end": a0 + mx})
                a0 += mx
        out.append({"start": a0, "end": b0})
    return out


TORCH = types.ModuleType("torch")
TORCH.from_numpy = lambda a: a
TORCH.set_num_threads = lambda n: None


class _NoGrad:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


TORCH.no_grad = _NoGrad
SIL = types.ModuleType("silero_vad")
SIL.load_silero_vad = lambda: None
SIL.get_speech_timestamps = fake_vad

ASKED = []


class Canned(http.server.BaseHTTPRequestHandler):
    """A llama-server that answers from the audio's pitch: 220 Hz is the
    game's announcer, 440 Hz the room, 880 Hz a video."""

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        b64 = ""
        pinned = None
        for m in body.get("messages") or []:
            c = m.get("content")
            if isinstance(c, list):
                for part in c:
                    if part.get("type") == "input_audio":
                        b64 = part["input_audio"]["data"]
            elif m.get("role") == "assistant":
                pinned = str(c)
        raw = base64.b64decode(b64)
        with wave.open(io.BytesIO(raw), "rb") as w:
            sr = w.getframerate()
            x = np.frombuffer(w.readframes(w.getnframes()),
                              dtype="<i2").astype("float32")
        zc = int(np.sum(np.abs(np.diff(np.sign(x))) > 0))
        hz = zc / 2.0 / (len(x) / float(sr))
        ASKED.append(round(hz))
        if hz < 330:
            txt = "The enemy has slain your ally."
        elif hz < 660:
            txt = "We are going in now."
        else:
            txt = "This video is about Hearthstone."
        content = ("language English<asr_text>" + txt if not pinned
                   else txt)
        out = {"choices": [{"message": {"content": content},
                            "finish_reason": "stop"}]}
        data = json.dumps(out).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Canned)
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["LORE_ASR_GGUF"] = "1"
os.environ["LORE_ASR_SERVER"] = "http://127.0.0.1:%d" % PORT
os.environ["LORE_ASR_CONTEXT"] = ("Gaming session of Bazaar. Friends on "
                                  "Discord playing together; casual gaming "
                                  "chat, callouts, jokes.")
for k in ("LORE_ASR_VOICE", "LORE_ASR_GAME", "LORE_ASR_MEDIA",
          "LORE_ASR_GAME_LINES", "LORE_ASR_THREADS"):
    os.environ.pop(k, None)
sys.modules["soundfile"] = SF
sys.modules["torch"] = TORCH
sys.modules["silero_vad"] = SIL


def load_worker(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


W_NEW = load_worker(WPATH, "asr331_new")
HEADW = os.path.join(TMP, "asr_worker_head.py")
io.open(HEADW, "w", encoding="utf-8", newline="").write(HEAD_W)
W_OLD = load_worker(HEADW, "asr331_head")
check("the HEAD worker is reader 5, the working one reader 6",
      W_OLD.READER == 5 and W_NEW.READER == 6)

NIGHT = os.path.join(TMP, "night")
os.makedirs(NIGHT)
T = 60
p_mix = os.path.join(NIGHT, "stt_mix.wav")
p_mic = os.path.join(NIGHT, "stt_mix.wav.mic.wav")
p_voice = os.path.join(NIGHT, "stt_mix.wav.voice.wav")
p_game = os.path.join(NIGHT, "stt_mix.wav.game.wav")
p_out = os.path.join(NIGHT, "out.json")
wav_write(p_voice, burst(T, (2, 5), 440))
wav_write(p_mic, burst(T, (10, 13), 440))
wav_write(p_game, burst(T, (30, 33), 220))
wav_write(p_mix, burst(T, (2, 5), 440) + burst(T, (10, 13), 440)
          + burst(T, (20, 25), 880) + burst(T, (30, 33), 220))


def run_worker(mod, env, mic=p_mic, out=p_out):
    for k in ("LORE_ASR_VOICE", "LORE_ASR_GAME", "LORE_ASR_MEDIA",
              "LORE_ASR_GAME_LINES"):
        os.environ.pop(k, None)
    os.environ.update(env)
    try:
        os.remove(out)
    except OSError:
        pass
    del ASKED[:]
    rc = mod.main(p_mix, out, mic)
    doc = json.load(io.open(out, encoding="utf-8"))
    raw = io.open(out, encoding="utf-8").read()
    prog = json.load(io.open(p_mix + ".prog", encoding="utf-8"))
    return rc, doc, raw, prog


rc, doc, raw, prog = run_worker(W_NEW, {"LORE_ASR_VOICE": p_voice,
                                        "LORE_ASR_GAME": p_game})
segs = doc["segments"]
check("the by-source night runs to the end", rc == 0 and len(segs) == 4)
by = {}
for sg in segs:
    by.setdefault(sg.get("src", ""), []).append(sg)
check("the friend's line (Voice tap) is the room, src absent",
      len(by.get("", [])) == 1 and by[""][0]["t"] == "We are going in now."
      and 1500 <= by[""][0]["a"] <= 2100)
check("his line (the mic) is src 'you'",
      len(by.get("you", [])) == 1 and 9500 <= by["you"][0]["a"] <= 10100)
check("the video is src 'media' with why 'mix>voice,game'",
      len(by.get("media", [])) == 1
      and by["media"][0]["t"] == "This video is about Hearthstone."
      and by["media"][0]["why"] == "mix>voice,game"
      and 19500 <= by["media"][0]["a"] <= 20100)
check("the game's announcer is src 'game', why 'game tap'",
      len(by.get("game", [])) == 1
      and by["game"][0]["t"] == "The enemy has slain your ally."
      and by["game"][0]["why"] == "game tap")
check("the lines are in time order", [s["a"] for s in segs]
      == sorted(s["a"] for s in segs))
src = doc["sources"]
check("the sources block: voice/game/media true, the seconds",
      src["voice"] and src["game"] and src["media"] and src["v"] == 1
      and abs(src["voice_s"] - 3.4) < 0.3 and abs(src["mic_s"] - 3.2) < 0.3
      and abs(src["room_s"] - 6.8) < 0.5 and abs(src["game_s"] - 3.4) < 0.3
      and abs(src["media_s"] - 5.4) < 0.3
      and src["media_read_s"] == src["media_s"]
      and src["game_read_s"] == src["game_s"] and src["media_off"] == 0)
check("the counters: one media line, one game line",
      doc["counters"]["media_lines"] == 1 and doc["counters"]["game_lines"] == 1
      and doc["counters"]["mic_lines"] == 1)
check("'sources' is written before 'segments'",
      raw.index('"sources"') < raw.index('"segments"'))
check("the notes: the video layer, the game, the mic",
      any(n.startswith("the video layer found 1 span(s), 5s") for n in doc["notes"])
      and any(n.startswith("the game spoke for 3s in 1 span(s)")
              for n in doc["notes"])
      and any(n == "1 of 2 line(s) read from the clean mic itself"
              for n in doc["notes"]))
check(".prog carries room_s and audio_total = room + media + game",
      abs(prog["room_s"] - src["room_s"]) < 0.05
      and abs(prog["audio_total"] - (src["room_s"] + src["media_read_s"]
                                     + src["game_read_s"])) < 0.2)
check("the reader stamp is 6", doc["reader"] == 6)
check("four asks, none re-asked (no wall fired on a video)",
      len(ASKED) == 4 and doc["counters"]["echo"] == 0
      and doc["counters"]["leash"] == 0)

# media off / game lines off
rc, doc, raw, prog = run_worker(W_NEW, {"LORE_ASR_VOICE": p_voice,
                                        "LORE_ASR_GAME": p_game,
                                        "LORE_ASR_MEDIA": "0",
                                        "LORE_ASR_GAME_LINES": "0"})
check("LORE_ASR_MEDIA=0 / GAME_LINES=0: the room only, the game counted",
      [s.get("src", "") for s in doc["segments"]] == ["", "you"]
      and doc["sources"]["media"] is False
      and abs(doc["sources"]["game_s"] - 3.4) < 0.3
      and doc["sources"]["game_read_s"] == 0 and len(ASKED) == 2)

# the Game-only night: the room is his mic alone
rc, doc, raw, prog = run_worker(W_NEW, {"LORE_ASR_GAME": p_game})
check("a Game tap without a Voice tap: the room is the mic; the friend's "
      "Mix-only span and the video are media (why 'mix>voice,game')",
      doc["sources"]["voice"] is False and doc["sources"]["game"]
      and [s.get("src", "") for s in doc["segments"]]
      == ["media", "you", "media", "game"]
      and doc["segments"][0]["why"] == "mix>voice,game")

# the dead-Voice night
T2 = 90
p_mix2 = os.path.join(NIGHT, "dead_mix.wav")
p_voice2 = os.path.join(NIGHT, "dead_voice.wav")
p_mic2 = os.path.join(NIGHT, "dead_mic.wav")
p_out2 = os.path.join(NIGHT, "dead.json")
wav_write(p_mix2, burst(T2, (5, 75), 440))
wav_write(p_voice2, np.zeros(T2 * SR, dtype="float32"))
wav_write(p_mic2, np.zeros(T2 * SR, dtype="float32"))
for k in ("LORE_ASR_GAME", "LORE_ASR_MEDIA", "LORE_ASR_GAME_LINES"):
    os.environ.pop(k, None)
os.environ["LORE_ASR_VOICE"] = p_voice2
del ASKED[:]
rc = W_NEW.main(p_mix2, p_out2, p_mic2)
dd = json.load(io.open(p_out2, encoding="utf-8"))
check("a dead Voice tap over 70 s of Mix speech: media stands down",
      rc == 0 and dd["counters"]["media_off"] == 1
      and dd["sources"]["media"] is False and dd["sources"]["voice"] is True)
check("...the friends are read from the Mix as the room, never 'media'",
      len(dd["segments"]) >= 3
      and all(s.get("src", "") == "" for s in dd["segments"])
      and all(s["t"] == "We are going in now." for s in dd["segments"]))
check("...and the note is the honesty line",
      any("not trusting it; those spans are read as the room" in n
          for n in dd["notes"]))
check("...the guards line in lore.py appends the stand-down",
      "the Voice layer was not trusted - media detection " in LSRC
      and '"stood down)" if cnt.get("media_off") else ""' in LSRC)

# 3.31 stage D: a Voice layer the app NAMED but that would not load
# (a corrupt .voice.wav) on a Voice+Game night - media detection stands
# down, the mix is the room, nobody is filed as "a video"
p_bad = os.path.join(NIGHT, "corrupt.voice.wav")
io.open(p_bad, "wb").write(b"RIFF" + bytes(4) + b"garbage-not-a-wav")
rc, doc, raw, prog = run_worker(W_NEW, {"LORE_ASR_VOICE": p_bad,
                                        "LORE_ASR_GAME": p_game})
check("a corrupt Voice layer beside a Game tap: media detection stood down",
      rc == 0 and doc["sources"]["media"] is False
      and doc["sources"]["voice"] is False and doc["sources"]["game"] is True
      and any(n == "the Voice layer could not be loaded - media detection "
                   "stood down" for n in doc["notes"])
      and any(n.startswith("voice layer skipped: ") for n in doc["notes"]))
check("...the mix is the room, as on an old night: the friend's line, the "
      "video AND the game's announcer are the room, his line off the mic - "
      "nobody is filed as a video; the game tap has nothing the room (the "
      "mix) does not cover",
      [s.get("src", "") for s in doc["segments"]] == ["", "you", "", ""]
      and doc["counters"]["media_lines"] == 0
      and doc["counters"]["game_lines"] == 0
      and doc["sources"]["game_s"] == 0.0)

# THE OLD-FILE PATH, byte-identical to the HEAD worker
p_out_h = os.path.join(NIGHT, "head.json")
p_out_n = os.path.join(NIGHT, "new.json")
rc_h, doc_h, raw_h, prog_h = run_worker(W_OLD, {}, out=p_out_h)
rc_n, doc_n, raw_n, prog_n = run_worker(W_NEW, {}, out=p_out_n)
check("an old night (no env): the HEAD worker and this one write the "
      "same lines", rc_h == rc_n == 0 and doc_h["segments"] == doc_n["segments"]
      and len(doc_n["segments"]) == 4)
check("...the same notes and the same counters but the five new zeros",
      doc_h["notes"] == doc_n["notes"]
      and {k: v for k, v in doc_n["counters"].items()
           if k not in ("media_lines", "game_lines", "media_dropped",
                        "game_dropped", "media_off")} == doc_h["counters"]
      and all(doc_n["counters"][k] == 0 for k in
              ("media_lines", "game_lines", "media_dropped", "game_dropped",
               "media_off")))
check("...the only new top-level key is 'sources', all flags false",
      set(doc_n) - set(doc_h) == {"sources"}
      and doc_n["sources"]["voice"] is False
      and doc_n["sources"]["game"] is False
      and doc_n["sources"]["media"] is False
      and doc_n["sources"]["game_s"] is None
      and doc_n["reader"] == 6 and doc_h["reader"] == 5)
check("...the same audio_total in .prog (room_s beside it)",
      prog_h["audio_total"] == prog_n["audio_total"]
      and "room_s" in prog_n and "room_s" not in prog_h)
# no mic, no layers, nothing at all: the early return, with the block
p_sil = os.path.join(NIGHT, "silent.wav")
p_sil_o = os.path.join(NIGHT, "silent.json")
wav_write(p_sil, np.zeros(10 * SR, dtype="float32"))
for k in ("LORE_ASR_VOICE", "LORE_ASR_GAME"):
    os.environ.pop(k, None)
rc = W_NEW.main(p_sil, p_sil_o, None)
sd = json.load(io.open(p_sil_o, encoding="utf-8"))
raw_s = io.open(p_sil_o, encoding="utf-8").read()
check("a silent night with no layers: the early return carries the block",
      rc == 0 and sd["segments"] == [] and sd["sources"]["voice"] is False
      and raw_s.index('"sources"') < raw_s.index('"segments"'))
srv.shutdown()

shutil.rmtree(TMP, ignore_errors=True)
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
