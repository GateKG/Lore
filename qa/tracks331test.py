# -*- coding: utf-8 -*-
"""3.31 THE TRACK CONTRACT - the one resolver, driven on real files.

Lifts the REAL functions out of lore.py by name (the track-title helpers,
_mix_audio_args, _fan_args, _layer_args, _voice_audio_args,
_extract_layers, build_mux_cmd) into a stub namespace and proves, with
the installed ffmpeg on a scratch shelf:

  T1  OLD-FILE PARITY IS SACRED - _mix_audio_args, _mic_track and
      build_mux_cmd give byte-for-byte the 3.30 answers (frozen here as
      literal fixtures captured from the committed 3.30 file BEFORE the
      resolver landed);
  T7  the fallback table, by TITLE never by position, on real renders:
      a Mix/System/Mic night, a one-track 'mix' night, a plain mp4 the
      tome did not record, and a Mix/Voice/Game/Mic night - with an FFT
      proving each layer carries only its own tones;
  T9  _extract_layers: ONE ffmpeg call per pass, aliases decoded once,
      the single-source command identical to today's, rc propagated.
No models, no devices, nothing under D:\\Records."""
import ast
import collections
import io
import json
import math
import os
import re
import struct
import subprocess
import sys
import tempfile
import textwrap
import time
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
FFDIR = r"C:\Program Files\Lore\ffmpeg\bin"
FF = os.path.join(FFDIR, "ffmpeg.exe")

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
    """exec the module-level assignment that binds `name` (a plain name
    or one of a tuple of names)."""
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
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name + " not assigned at module level")


SAID = []
ns = {"os": os, "json": json, "subprocess": subprocess, "time": time,
      "collections": collections,
      "SETTINGS": {"ffmpeg_path": FF, "audio_mode": "separate"},
      "_AI": {"proc": None, "abort": False}, "_popen": subprocess.Popen,
      "log": SAID.append}
for nm in ("_TRK_MIX", "_LAYERS", "_Layer", "_MUX_SAID"):
    lift_assign(nm, ns)
for nm in ("_audio_track_names", "_track_for", "_mic_track", "_voice_track",
           "_game_track", "_mix_audio_args", "_fan_args", "_layer_args",
           "_voice_audio_args", "_ai_run", "_extract_layers",
           "build_mux_cmd"):
    extract(nm, ns)
names_of = ns["_audio_track_names"]
mix_args = ns["_mix_audio_args"]
mic_track = ns["_mic_track"]
track_for = ns["_track_for"]
layer_args = ns["_layer_args"]
voice_args = ns["_voice_audio_args"]
extract_layers = ns["_extract_layers"]
build_mux_cmd = ns["build_mux_cmd"]

# ---------------------------------------------------------------------------
# THE 3.30 FIXTURES. Captured from the committed 3.30 lore.py (git HEAD
# 76a64d8) before the resolver landed. If any of these ever has to change,
# ~400 nights on the shelf re-owe their reviews - so they are literals.
OLD_MIX_ARGS = {
    ("mix", "system", "mic"): ["-vn", "-map", "0:a:0"],
    ("system", "mic"): ["-vn", "-filter_complex",
                        "[0:a:0][0:a:1]amix=inputs=2:duration=longest"
                        ":normalize=0[a]", "-map", "[a]"],
    ("",): ["-vn"],
    ("mix",): ["-vn", "-map", "0:a:0"],
    ("", ""): ["-vn"],
    (): ["-vn"],
}
OLD_MIC = {("mix", "system", "mic"): 2, ("system", "mic"): 1, ("",): None,
           ("mix",): None, ("", ""): None, (): None}
OLD_MUX = {
    "separate": ["FF", "-y", "-hide_banner", "-loglevel", "warning", "-i",
                 "VID", "-i", "SYS", "-i", "MIC", "-filter_complex",
                 "[1:a]aresample=48000,aformat=channel_layouts=stereo[a0];"
                 "[2:a]aresample=48000,aformat=channel_layouts=stereo[a1];"
                 "[a0]asplit=2[s0][t0];[a1]asplit=2[s1][t1];"
                 "[s0][s1]amix=inputs=2:duration=longest:normalize=0[a]",
                 "-map", "0:v", "-map", "[a]", "-map", "[t0]", "-map", "[t1]",
                 "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                 "-metadata:s:a:0", "title=Mix", "-metadata:s:a:1",
                 "title=System", "-metadata:s:a:2", "title=Mic", "OUT"],
    "mix": ["FF", "-y", "-hide_banner", "-loglevel", "warning", "-i", "VID",
            "-i", "SYS", "-i", "MIC", "-filter_complex",
            "[1:a]aresample=48000,aformat=channel_layouts=stereo[a0];"
            "[2:a]aresample=48000,aformat=channel_layouts=stereo[a1];"
            "[a0][a1]amix=inputs=2:duration=longest:normalize=0[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
            "-b:a", "192k", "-metadata:s:a:0", "title=Mix", "OUT"],
}

print("--- T1: old-file parity, byte for byte ---")
for names, want in OLD_MIX_ARGS.items():
    check("_mix_audio_args%r == 3.30" % (names,),
          mix_args("x", list(names)) == want)
    check("_mic_track%r == 3.30" % (names,),
          mic_track("x", list(names)) == OLD_MIC[names])

TD = tempfile.mkdtemp(prefix="trk331_")
SYSW = os.path.join(TD, "sys.wav")
MICW = os.path.join(TD, "mic.wav")
open(SYSW, "wb").write(b"x")
open(MICW, "wb").write(b"x")
for mode in ("separate", "mix"):
    ns["SETTINGS"]["audio_mode"] = mode
    c = build_mux_cmd("VID", SYSW, MICW, "OUT")
    c = ["FF" if x == FF else "SYS" if x == SYSW else "MIC" if x == MICW
         else x for x in c]
    check("build_mux_cmd(%s) is the 3.30 command token for token" % mode,
          c == OLD_MUX[mode])
ns["SETTINGS"]["audio_mode"] = "separate"

print("\n--- T2: by title, never by position ---")
BS = ["mix", "voice", "game", "mic"]
check("a 3.31 file: mix 0, voice 1, game 2, mic 3, no system",
      [track_for("x", k, BS) for k in ("mix", "voice", "game", "mic",
                                        "system")] == [0, 1, 2, 3, None])
check("an old file: mix 0, system 1, mic 2, no voice/game",
      [track_for("x", k, ["mix", "system", "mic"])
       for k in ("mix", "system", "mic", "voice", "game")]
      == [0, 1, 2, None, None])
check("a file with the mic FIRST still finds it by its title",
      track_for("x", "mic", ["mic", "mix"]) == 0
      and track_for("x", "mix", ["mic", "mix"]) == 1)
check("the wrappers are the one implementation",
      ns["_mic_track"]("x", BS) == 3 and ns["_voice_track"]("x", BS) == 1
      and ns["_game_track"]("x", BS) == 2
      and ns["_voice_track"]("x", ["mix", "system", "mic"]) is None
      and ns["_game_track"]("x", []) is None)
check("an unknown layer name is None, not a crash",
      track_for("x", "bogus", BS) is None)
check("the constants spell the titles",
      (ns["_TRK_MIX"], ns["_TRK_VOICE"], ns["_TRK_GAME"], ns["_TRK_MIC"],
       ns["_TRK_SYSTEM"]) == ("Mix", "Voice", "Game", "Mic", "System"))

print("\n--- T3: _mix_audio_args' honest fallback ---")
check("no Mix title + Voice/Game riding: sum only system and mic",
      mix_args("x", ["system", "mic", "voice", "game"])
      == ["-vn", "-filter_complex",
          "[0:a:0][0:a:1]amix=inputs=2:duration=longest:normalize=0[a]",
          "-map", "[a]"])
check("no Mix title, one playable layer beside the mic: that one, no amix",
      mix_args("x", ["voice", "mic"]) == ["-vn", "-map", "0:a:1"])

print("\n--- T4: the layer table on names alone ---")
OLD = ["mix", "system", "mic"]


def LA(layer, names, fan=1):
    return layer_args("x", layer, names, fan)


check("old separate: room == today's mix args, how 'mix'",
      LA("room", OLD) == (["-vn"], [["-map", "0:a:0"]], "mix"))
check("old separate: voice is None (no Voice track alone)",
      LA("voice", OLD) == (["-vn"], [], None))
check("old separate: game -> System, how 'system'",
      LA("game", OLD) == (["-vn"], [["-map", "0:a:1"]], "system"))
check("old separate: mic -> 0:a:2", LA("mic", OLD) == (["-vn"], [["-map", "0:a:2"]], "mic"))
check("old separate: media is None (nothing to subtract against)",
      LA("media", OLD) == (["-vn"], [], None))
pre, maps, how = LA("room", ["system", "mic"])
check("pre-3.10 separate (no Mix title): room = the sum, byte-identical",
      pre + maps[0] == OLD_MIX_ARGS[("system", "mic")] and how == "sum")
check("one-track 'mix' night: room/game/media/mic",
      LA("room", ["mix"]) == (["-vn"], [["-map", "0:a:0"]], "mix")
      and LA("game", ["mix"]) == (["-vn"], [["-map", "0:a:0"]], "mix")
      and LA("mic", ["mix"]) == (["-vn"], [], None)
      and LA("media", ["mix"]) == (["-vn"], [], None))
check("a plain untitled file: the default pick, no -map at all",
      LA("room", [""]) == (["-vn"], [[]], "default")
      and LA("mix", []) == (["-vn"], [[]], "default"))
check("3.31 night: room = Voice+Mic amix normalize=0",
      LA("room", BS) == (["-vn", "-filter_complex",
                          "[0:a:1][0:a:3]amix=inputs=2:duration=longest"
                          ":normalize=0[L]"], [["-map", "[L]"]], "voice+mic"))
check("3.31 night: voice / game / mic / media / mix",
      LA("voice", BS) == (["-vn"], [["-map", "0:a:1"]], "voice")
      and LA("game", BS) == (["-vn"], [["-map", "0:a:2"]], "game")
      and LA("mic", BS) == (["-vn"], [["-map", "0:a:3"]], "mic")
      and LA("media", BS) == (["-vn"], [["-map", "0:a:0"]], "mix")
      and LA("mix", BS) == (["-vn"], [["-map", "0:a:0"]], "mix"))
check("Discord closed on a by-source night (Mix/Game/Mic): room = the mic alone",
      LA("room", ["mix", "game", "mic"]) == (["-vn"], [["-map", "0:a:2"]], "mic")
      and LA("voice", ["mix", "game", "mic"]) == (["-vn"], [], None)
      and LA("media", ["mix", "game", "mic"])[2] == "mix")
check("a Voice track with no Mic: room = the voice alone",
      LA("room", ["mix", "voice"]) == (["-vn"], [["-map", "0:a:1"]], "voice"))
try:
    LA("bogus", BS)
    check("an unknown layer raises", False)
except ValueError:
    check("an unknown layer raises", True)

print("\n--- T5: _voice_audio_args, the adapter ---")
check("old night -> None (callers take the mix as they always did)",
      voice_args("x", OLD) is None and voice_args("x", ["mix"]) is None
      and voice_args("x", [""]) is None)
check("3.31 night -> the room graph",
      voice_args("x", BS) == ["-vn", "-filter_complex",
                              "[0:a:1][0:a:3]amix=inputs=2:duration=longest"
                              ":normalize=0[L]", "-map", "[L]"])
check("Discord closed -> the mic alone",
      voice_args("x", ["mix", "game", "mic"]) == ["-vn", "-map", "0:a:2"])

print("\n--- T6: fan=2 shapes ---")
pre, maps, how = LA("room", BS, fan=2)
check("a graph fans through asplit",
      pre[2].endswith(",asplit=2[L0][L1]") and "amix=inputs=2" in pre[2]
      and maps == [["-map", "[L0]"], ["-map", "[L1]"]] and how == "voice+mic")
pre, maps, how = LA("mic", BS, fan=2)
check("a raw stream is mapped twice, as two distinct lists",
      maps == [["-map", "0:a:3"], ["-map", "0:a:3"]]
      and maps[0] is not maps[1] and pre == ["-vn"])
pre, maps, how = LA("room", [""], fan=2)
check("the default pick fans through [0:a]",
      pre == ["-vn", "-filter_complex", "[0:a]asplit=2[L0][L1]"]
      and maps == [["-map", "[L0]"], ["-map", "[L1]"]] and how == "default")

# ---------------------------------------------------------------------------
print("\n--- T7: real files ---")


def tone(path, hz, secs=2.0):
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(48000)
        n = int(48000 * secs)
        w.writeframes(b"".join(struct.pack(
            "<hh", *((int(9000 * math.sin(2 * math.pi * hz * i / 48000)),) * 2))
            for i in range(n)))
    return path


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, timeout=120,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    return r.returncode


SYS_ = tone(os.path.join(TD, "sys200.wav"), 200)
MIC_ = tone(os.path.join(TD, "mic900.wav"), 900)
VOI_ = tone(os.path.join(TD, "voice1500.wav"), 1500)
GAM_ = tone(os.path.join(TD, "game3000.wav"), 3000)
VID = os.path.join(TD, "v.mp4")
rc = run([FF, "-y", "-v", "error", "-f", "lavfi", "-i",
          "color=black:size=160x90:rate=10", "-t", "2", "-c:v", "libx264",
          "-pix_fmt", "yuv420p", VID])
check("a 2 s black video renders", rc == 0 and os.path.getsize(VID) > 0)

F_OLD = os.path.join(TD, "old_sep.mp4")
rc = run(build_mux_cmd(VID, SYS_, MIC_, F_OLD))
check("a Mix/System/Mic night binds (today's command)",
      rc == 0 and names_of(F_OLD) == ["mix", "system", "mic"])
ns["SETTINGS"]["audio_mode"] = "mix"
F_ONE = os.path.join(TD, "old_mix.mp4")
rc = run(build_mux_cmd(VID, SYS_, MIC_, F_ONE))
ns["SETTINGS"]["audio_mode"] = "separate"
check("a one-track 'mix' night binds", rc == 0 and names_of(F_ONE) == ["mix"])
F_PLAIN = os.path.join(TD, "plain.mp4")
rc = run([FF, "-y", "-v", "error", "-i", VID, "-i", SYS_, "-map", "0:v",
          "-map", "1:a", "-c:v", "copy", "-c:a", "aac", F_PLAIN])
check("a plain mp4 the tome did not record: one untitled track",
      rc == 0 and names_of(F_PLAIN) == [""])
F_PRE = os.path.join(TD, "pre310.mp4")
rc = run([FF, "-y", "-v", "error", "-i", VID, "-i", SYS_, "-i", MIC_,
          "-map", "0:v", "-map", "1:a", "-map", "2:a", "-c:v", "copy",
          "-c:a", "aac", "-metadata:s:a:0", "title=System",
          "-metadata:s:a:1", "title=Mic", F_PRE])
check("a pre-3.10 separate file (System/Mic, no Mix)",
      rc == 0 and names_of(F_PRE) == ["system", "mic"])
# the 3.31 layout, bound by the REAL build_mux_cmd(taps=) (stage B):
# Mix = System + Mic at parity, then Voice, Game, Mic as their own tracks
F_NEW = os.path.join(TD, "new.mp4")
TAPS2 = [{"label": "Voice", "path": VOI_, "off": 0, "secs": None},
         {"label": "Game", "path": GAM_, "off": 0, "secs": None}]
rc = run(build_mux_cmd(VID, SYS_, MIC_, F_NEW, taps=TAPS2))
check("a Mix/Voice/Game/Mic night binds through build_mux_cmd(taps=)",
      rc == 0 and names_of(F_NEW) == ["mix", "voice", "game", "mic"])

nm_old = names_of(F_OLD)
pre, maps, how = layer_args(F_OLD, "room", nm_old)
check("old night on disk: room == _mix_audio_args, how 'mix'",
      pre + maps[0] == mix_args(F_OLD, nm_old) == OLD_MIX_ARGS[("mix", "system", "mic")]
      and how == "mix")
check("old night on disk: game -> System, mic -> 0:a:2, media None, voice None",
      layer_args(F_OLD, "game", nm_old) == (["-vn"], [["-map", "0:a:1"]], "system")
      and layer_args(F_OLD, "mic", nm_old) == (["-vn"], [["-map", "0:a:2"]], "mic")
      and layer_args(F_OLD, "media", nm_old)[2] is None
      and layer_args(F_OLD, "voice", nm_old)[2] is None)
check("one-track night on disk: room -> 0:a:0 how 'mix'",
      layer_args(F_ONE, "room") == (["-vn"], [["-map", "0:a:0"]], "mix"))
check("plain mp4 on disk: default pick, no -map, _mic_track None",
      layer_args(F_PLAIN, "room") == (["-vn"], [[]], "default")
      and mic_track(F_PLAIN) is None)
pre, maps, how = layer_args(F_PRE, "room")
check("pre-3.10 file on disk: the sum graph, byte-identical to 3.30",
      pre + maps[0] == OLD_MIX_ARGS[("system", "mic")] and how == "sum")


def spectrum(path, layer, fan_maps=None):
    """Decode one layer to 16 kHz mono through the resolver's own
    arguments and return {hz: dB over the floor} for the four tones."""
    import numpy as np
    pre, maps, how = layer_args(path, layer)
    cmd = [FF, "-y", "-loglevel", "error", "-i", path] + pre + maps[0] + [
        "-ac", "1", "-ar", "16000", "-f", "s16le", "pipe:1"]
    r = subprocess.run(cmd, capture_output=True, timeout=120,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    a = np.frombuffer(r.stdout, np.int16).astype(np.float32)
    if len(a) < 16000:
        return {}
    a = a[:16000 * 2] if len(a) >= 32000 else a
    mag = np.abs(np.fft.rfft(a * np.hanning(len(a))))
    freqs = np.fft.rfftfreq(len(a), 1.0 / 16000)
    floor = float(np.median(mag)) + 1e-9
    out = {}
    for hz in (200, 900, 1500, 3000):
        i = int(np.argmin(np.abs(freqs - hz)))
        out[hz] = 20 * math.log10(max(mag[i - 2:i + 3].max(), 1e-9) / floor)
    return out


def carries(sp, yes, no, db=30, gap=40):
    """The tones in `yes` stand at least `db` over the floor; every tone
    in `no` sits at least `gap` dB below the loudest of them (a pure
    tone's median floor is near zero, so an AAC harmonic 110 dB down
    still reads 'over the floor' - absence is judged against the peak)."""
    if not sp or not all(sp[h] > db for h in yes):
        return False
    top = max(sp[h] for h in yes)
    return all(top - sp[h] > gap for h in no)


sp = spectrum(F_NEW, "voice")
check("3.31 night: the voice layer is Discord alone (1500)",
      carries(sp, (1500,), (200, 900, 3000)))
sp = spectrum(F_NEW, "room")
check("3.31 night: the room is Discord + the mic (1500 + 900), no game, no playback",
      carries(sp, (1500, 900), (200, 3000)))
sp = spectrum(F_NEW, "game")
check("3.31 night: the game layer is the game alone (3000)",
      carries(sp, (3000,), (200, 900, 1500)))
sp = spectrum(F_NEW, "mic")
check("3.31 night: the mic layer is the mic alone (900)",
      carries(sp, (900,), (200, 1500, 3000)))
sp = spectrum(F_NEW, "mix")
check("3.31 night: the mix is the playback + the mic (200 + 900)",
      carries(sp, (200, 900), (1500, 3000)))
sp = spectrum(F_OLD, "room")
check("old night: the room falls to the mix (200 + 900)",
      carries(sp, (200, 900), (1500, 3000)))
sp = spectrum(F_OLD, "game")
check("old night: the game falls to System (200 alone)",
      carries(sp, (200,), (900, 1500, 3000)))
sp = spectrum(F_PRE, "room")
check("pre-3.10 night: the room is the sum (200 + 900)",
      carries(sp, (200, 900), (1500, 3000)))

print("\n--- T8: fan=2 on a real file ---")


def frames_of(path):
    try:
        with wave.open(path, "rb") as w:
            return w.getnframes()
    except Exception:
        return -1


pre, maps, how = layer_args(F_NEW, "room", fan=2)
A = os.path.join(TD, "fan_a.wav")
B = os.path.join(TD, "fan_b.wav")
rc = run([FF, "-y", "-loglevel", "error", "-i", F_NEW] + pre + maps[0]
         + ["-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", A]
         + ["-vn"] + maps[1] + ["-ac", "1", "-ar", "32000", "-c:a", "pcm_s16le", B])
check("asplit feeds two outputs of the room; ffmpeg accepts, lengths agree",
      rc == 0 and frames_of(A) > 16000 * 1.9
      and abs(frames_of(A) * 2 - frames_of(B)) <= 64)
pre, maps, how = layer_args(F_NEW, "mic", fan=2)
rc = run([FF, "-y", "-loglevel", "error", "-i", F_NEW] + pre + maps[0]
         + ["-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", A]
         + ["-vn"] + maps[1] + ["-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", B])
check("a raw stream mapped twice is accepted", rc == 0 and frames_of(A) == frames_of(B) > 0)

print("\n--- T9: _extract_layers, one read per pass ---")
CALLS = []
real_run = ns["_ai_run"]


def spy_run(cmd, timeout, flags):
    CALLS.append(list(cmd))
    return real_run(cmd, timeout, flags)


ns["_ai_run"] = spy_run
FL = subprocess.CREATE_NO_WINDOW


def near2s(path, rate):
    n = frames_of(path)
    return abs(n - 2 * rate) < rate * 0.15


base = os.path.join(TD, "stt_a.wav")
del CALLS[:]
lay = extract_layers(F_NEW, names_of(F_NEW), base,
                     ("mix", "mic", "voice", "game"), 16000, 300, FL)
check("3.31 night, the reader's want: ONE ffmpeg call", len(CALLS) == 1 and lay["rc"] == 0)
check("...mix lands at the base wav, the rest beside it",
      lay["mix"].path == base and lay["mic"].path == base + ".mic.wav"
      and lay["voice"].path == base + ".voice.wav"
      and lay["game"].path == base + ".game.wav")
check("...every layer says how it was fed",
      [lay[k].how for k in ("mix", "mic", "voice", "game")]
      == ["mix", "mic", "voice", "game"])
check("...four 2 s files at 16 kHz",
      all(near2s(lay[k].path, 16000) for k in ("mix", "mic", "voice", "game")))
check("...no graph on a night whose layers are plain tracks",
      "-filter_complex" not in CALLS[0]
      and CALLS[0].count("-vn") == 4 and CALLS[0].count("-map") == 4)

base = os.path.join(TD, "sns_a.wav")
del CALLS[:]
lay = extract_layers(F_NEW, names_of(F_NEW), base, ("room", "mic", "game"),
                     48000, 300, FL)
c = CALLS[0]
check("3.31 night, the senses' want: one call, the room graph renamed and mapped",
      len(CALLS) == 1 and lay["rc"] == 0 and "-filter_complex" in c
      and c[c.index("-filter_complex") + 1].endswith("[G0]")
      and "amix=inputs=2" in c[c.index("-filter_complex") + 1]
      and c[c.index("-map") + 1] == "[G0]")
check("...room at the base wav (how voice+mic), mic and game beside it",
      lay["room"] == (base, "voice+mic")
      and lay["mic"] == (base + ".mic.wav", "mic")
      and lay["game"] == (base + ".game.wav", "game")
      and all(near2s(p, 48000) for p in (base, base + ".mic.wav", base + ".game.wav")))
import numpy as np
with wave.open(base, "rb") as w:
    a = np.frombuffer(w.readframes(48000), np.int16).astype(np.float32)
mag = np.abs(np.fft.rfft(a * np.hanning(len(a))))
fr = np.fft.rfftfreq(len(a), 1.0 / 48000)
floor = float(np.median(mag)) + 1e-9


def db(hz):
    i = int(np.argmin(np.abs(fr - hz)))
    return 20 * math.log10(max(mag[i - 2:i + 3].max(), 1e-9) / floor)


check("...the room file written through the graph carries 1500 + 900 and no 3000/200",
      db(1500) > 30 and db(900) > 30 and db(3000) < 30 and db(200) < 30)

base = os.path.join(TD, "sns_old.wav")
del CALLS[:]
lay = extract_layers(F_OLD, names_of(F_OLD), base, ("room", "mic", "game"),
                     48000, 300, FL)
check("old night, the senses' want: room = the mix (how 'mix'), game from System",
      len(CALLS) == 1 and lay["rc"] == 0
      and lay["room"] == (base, "mix") and lay["mic"] == (base + ".mic.wav", "mic")
      and lay["game"] == (base + ".game.wav", "system")
      and "-filter_complex" not in CALLS[0])

base = os.path.join(TD, "one.wav")
del CALLS[:]
lay = extract_layers(F_ONE, names_of(F_ONE), base, ("room", "game", "mic"),
                     16000, 300, FL)
check("one-track night: room and game ALIAS to one file, decoded once; mic absent",
      len(CALLS) == 1 and lay["rc"] == 0
      and lay["room"].path == lay["game"].path == base
      and lay["room"].how == lay["game"].how == "mix"
      and lay["mic"] == ("", None)
      and CALLS[0].count("pcm_s16le") == 1 and near2s(base, 16000))

base = os.path.join(TD, "today.wav")
del CALLS[:]
lay = extract_layers(F_OLD, names_of(F_OLD), base, ("mix",), 16000, 300, FL)
check("old night, one layer: EXACTLY today's reader command",
      CALLS[0] == [FF, "-y", "-loglevel", "error", "-i", F_OLD]
      + OLD_MIX_ARGS[("mix", "system", "mic")]
      + ["-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", base]
      and lay["mix"] == (base, "mix"))
base = os.path.join(TD, "today_pre.wav")
del CALLS[:]
lay = extract_layers(F_PRE, names_of(F_PRE), base, ("room",), 48000, 300, FL)
check("pre-3.10 night, one layer: EXACTLY today's senses command (the sum graph)",
      CALLS[0] == [FF, "-y", "-loglevel", "error", "-i", F_PRE]
      + OLD_MIX_ARGS[("system", "mic")]
      + ["-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", base]
      and lay["room"] == (base, "sum") and near2s(base, 48000))
base = os.path.join(TD, "plain.wav")
del CALLS[:]
lay = extract_layers(F_PLAIN, names_of(F_PLAIN), base, ("mix", "mic"), 16000, 300, FL)
check("plain mp4: the default pick with no -map, mic absent, one output",
      CALLS[0] == [FF, "-y", "-loglevel", "error", "-i", F_PLAIN, "-vn",
                   "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", base]
      and lay["mix"] == (base, "default") and lay["mic"] == ("", None)
      and near2s(base, 16000))

base = os.path.join(TD, "gone.wav")
del CALLS[:]
lay = extract_layers(os.path.join(TD, "nope.mp4"), ["mix", "voice", "game", "mic"],
                     base, ("mix", "voice"), 16000, 300, FL)
check("a file that will not read: rc propagated, every path ''",
      lay["rc"] != 0 and lay["mix"].path == "" and lay["voice"].path == ""
      and lay["voice"].how == "voice")
del CALLS[:]
lay = extract_layers(F_OLD, names_of(F_OLD), base, ("voice", "media"), 16000, 300, FL)
check("nothing to extract: no ffmpeg call, rc 0, both layers absent",
      CALLS == [] and lay["rc"] == 0 and lay["voice"] == ("", None)
      and lay["media"] == ("", None))
ns["_ai_run"] = real_run

def _title_maps_probe(names):
    ns2 = dict(ns)
    ns2["_audio_track_names"] = lambda p: names
    for k in ("_TRK_MIX", "_TRK_VOICE", "_TRK_GAME", "_TRK_MIC", "_TRK_SYSTEM"):
        ns2[k] = ns.get(k) or {"_TRK_MIX": "Mix", "_TRK_VOICE": "Voice",
                               "_TRK_GAME": "Game", "_TRK_MIC": "Mic",
                               "_TRK_SYSTEM": "System"}[k]
    extract("_title_maps", ns2)
    return ns2["_title_maps"]("x.mp4")

print("\n--- the remuxers keep every track (source) ---")
check("the SDR finisher maps 0:v:0 and the OPTIONAL 0:a? and restates the titles",
      '"-map", "0:v:0", "-map", "0:a?", *_title_maps(path),' in SRC
      and SRC.index('"-map", "0:v:0", "-map", "0:a?", *_title_maps(path),')
      < SRC.index('"-c:a", "copy", tmp_out]'))
check("Save&Replace maps the same way and a share cut stays one-track",
      '(["-map", "0:v:0", "-map", "0:a?"] + _title_maps(p))' in SRC
      and "if replace else []" in SRC)
check("_title_maps restates every known title by index and skips the rest",
      _title_maps_probe(["mix", "voice", "", "mic"]) ==
      ["-metadata:s:a:0", "title=Mix", "-metadata:s:a:1", "title=Voice",
       "-metadata:s:a:3", "title=Mic"]
      and _title_maps_probe([]) == [])

# ---------------------------------------------------------------------------
# THE MUX WITH SOURCES (stage B) - numbered by the mux spec's tests
print("\n--- M2: the taps graph ---")


def maps_of(c):
    return [c[i + 1] for i in range(len(c) - 1) if c[i] == "-map"]


def titles_of(c):
    return [c[i + 1].split("=", 1)[1] for i in range(len(c) - 1)
            if c[i].startswith("-metadata:s:a:")]


def graph_of(c):
    return c[c.index("-filter_complex") + 1]


SAID[:] = []
c = build_mux_cmd("VID", SYSW, MICW, "OUT", taps=TAPS2)
g = graph_of(c)
check("inputs in the fixed order System, Voice, Game, Mic",
      [c[i + 1] for i in range(len(c) - 1) if c[i] == "-i"]
      == ["VID", SYSW, VOI_, GAM_, MICW])
check("maps: video, the Mix, Voice and Game direct, the Mic split",
      maps_of(c) == ["0:v", "[a]", "[a1]", "[a2]", "[t3]"])
check("titles in order Mix, Voice, Game, Mic - NO System track",
      titles_of(c) == ["Mix", "Voice", "Game", "Mic"])
check("exactly one amix, of System + Mic (the taps are NOT summed into the Mix)",
      g.count("amix=") == 1 and "[a0][s3]amix=inputs=2:duration=longest:normalize=0[a]" in g
      and "[a3]asplit=2[s3][t3]" in g and "[a0]asplit" not in g)
check("each tap carries its own offset",
      "[2:a]aresample=48000,aformat=channel_layouts=stereo,adelay=delays=150:all=1[a1]"
      in graph_of(build_mux_cmd("VID", SYSW, MICW, "OUT", taps=[
          {"label": "Voice", "path": VOI_, "off": 150, "secs": None}]))
      and ",atrim=start=0.200,asetpts=PTS-STARTPTS[a1]" in graph_of(
          build_mux_cmd("VID", SYSW, MICW, "OUT", taps=[
              {"label": "Game", "path": GAM_, "off": -200, "secs": None}])))
check("a lone tap takes the layered route: Mix + its own titled track",
      titles_of(build_mux_cmd("VID", SYSW, None, "OUT", taps=[TAPS2[0]]))
      == ["Mix", "Voice"])
check("no 'one track' line in 'separate' mode", SAID == [])
check("taps=[] and taps=None are today's command, token for token",
      build_mux_cmd("VID", SYSW, MICW, "OUT", taps=[])
      == build_mux_cmd("VID", SYSW, MICW, "OUT")
      == [FF if x == "FF" else SYSW if x == "SYS" else MICW if x == "MIC" else x
          for x in OLD_MUX["separate"]])

print("\n--- M3: no loopback ---")
c = build_mux_cmd("VID", None, MICW, "OUT", taps=TAPS2)
g = graph_of(c)
check("Mix = amix of Voice, Game and Mic (the taps join the Mix only without the loopback)",
      "[s0][s1][s2]amix=inputs=3:duration=longest:normalize=0[a]" in g
      and g.count("asplit=2") == 3)
check("titles Mix, Voice, Game, Mic; maps the split halves",
      titles_of(c) == ["Mix", "Voice", "Game", "Mic"]
      and maps_of(c) == ["0:v", "[a]", "[t0]", "[t1]", "[t2]"])
c = build_mux_cmd("VID", None, None, "OUT", taps=[TAPS2[0]])
check("a Voice tap alone: the Mix is that one member (anull), plus the Voice track",
      "[s0]anull[a]" in graph_of(c) and titles_of(c) == ["Mix", "Voice"])

print("\n--- M4: 'one track' set while sources were captured ---")
SAID[:] = []
ns["_MUX_SAID"]["one_track"] = False
ns["SETTINGS"]["audio_mode"] = "mix"
c = build_mux_cmd("VID", SYSW, MICW, "OUT", taps=TAPS2)
c2 = build_mux_cmd("VID", SYSW, MICW, "OUT", taps=TAPS2)
ns["SETTINGS"]["audio_mode"] = "separate"
check("bound layered anyway", titles_of(c) == ["Mix", "Voice", "Game", "Mic"]
      and c == c2)
check("exactly ONE line containing 'bound layered' across two calls of one bind",
      sum(1 for m in SAID if "bound layered" in m) == 1
      and "'one track' is set, but sources were captured" in SAID[0])
ns["SETTINGS"]["audio_mode"] = "mix"
c = build_mux_cmd("VID", SYSW, MICW, "OUT")
ns["SETTINGS"]["audio_mode"] = "separate"
check("...and 'mix' with no taps is still today's one-track command",
      c == [FF if x == "FF" else SYSW if x == "SYS" else MICW if x == "MIC" else x
            for x in OLD_MUX["mix"]])

print("\n--- M5: placeholders ---")
c = build_mux_cmd("VID", SYSW, MICW, "OUT",
                  taps=[{"label": "Voice", "path": None, "off": 0, "secs": 3.0}])
i = c.index("anullsrc=r=48000:cl=stereo")
check("a silent Voice placeholder: '-f lavfi -t 3.000 -i anullsrc', a Voice title",
      c[i - 5:i] == ["-f", "lavfi", "-t", "3.000", "-i"]
      and titles_of(c) == ["Mix", "Voice", "Mic"])
c = build_mux_cmd("VID", SYSW, MICW, "OUT", taps=[
    {"label": "Voice", "path": VOI_, "off": 0, "secs": None},
    {"label": "Voice", "path": GAM_, "off": 0, "secs": None}])
check("two Voice inputs -> one pre-sum amix and a single Voice title",
      "[a1][a2]amix=inputs=2:duration=longest:normalize=0[v1]" in graph_of(c)
      and titles_of(c) == ["Mix", "Voice", "Mic"] and maps_of(c) == ["0:v", "[a]", "[v1]", "[t3]"])
c = build_mux_cmd("VID", SYSW, MICW, "OUT", taps=[
    {"label": "Voice", "path": None, "off": 0, "secs": 3.0},
    {"label": "Voice", "path": VOI_, "off": 0, "secs": None}])
check("a placeholder beside a real Voice is dropped",
      "anullsrc" not in " ".join(c) and titles_of(c) == ["Mix", "Voice", "Mic"])
c = build_mux_cmd("VID", SYSW, MICW, "OUT", taps=[
    {"label": "Voice", "path": None, "off": 0, "secs": None},
    {"label": "Game", "path": os.path.join(TD, "nope.wav"), "off": 0, "secs": None}])
check("a tap with no path and no secs, or a missing file, is skipped (today's command)",
      c == build_mux_cmd("VID", SYSW, MICW, "OUT"))
F_PH = os.path.join(TD, "placeholder.mp4")
rc = run(build_mux_cmd(VID, SYS_, MIC_, F_PH, taps=[
    {"label": "Voice", "path": None, "off": 0, "secs": 4.0},
    {"label": "Game", "path": GAM_, "off": 0, "secs": None}]))
check("a placeholder night really binds: titles Mix, Voice, Game, Mic",
      rc == 0 and names_of(F_PH) == ["mix", "voice", "game", "mic"])
sp = spectrum(F_PH, "voice")
check("...and its Voice track is silence (no tone stands over the floor)",
      sp and all(sp[h] < 30 for h in (200, 900, 1500, 3000)))

# (M6 is T7 above: the real bind of the 2 s Mix/Voice/Game/Mic night through
#  build_mux_cmd(taps=), its titles by ffprobe and each layer's tones by FFT)

print("\n--- M10: _assemble's union layout on real ffmpeg ---")
import types
sys.path.insert(0, ROOT)
import lore  # noqa: E402
LSAID = []
lore.log = LSAID.append
lore.load_settings()
lore.SETTINGS.update({"ffmpeg_path": FF, "audio_mode": "separate",
                      "audio_offset_ms": 0, "segment_seconds": 2})
TD10 = os.path.join(TD, "asm")
os.makedirs(TD10)


def seg(name):
    p = os.path.join(TD10, name)
    run([FF, "-y", "-v", "error", "-f", "lavfi", "-i",
         "testsrc=size=160x90:rate=10:duration=2", "-c:v", "libx264",
         "-pix_fmt", "yuv420p", "-g", "12", p])
    return p


S1, S2 = seg("seg_000000.mp4"), seg("seg_000001.mp4")
EMPTY = os.path.join(TD10, "empty_voice.wav")
open(EMPTY, "wb").close()


def anchors(segp):
    t0 = os.path.getmtime(segp) - 2.0
    return {"sys_t0": t0, "mic_t0": t0, "voice_t0": t0, "game_t0": t0,
            "v_end_wall": t0 + 2.0, "nseg": 1}


fake = types.SimpleNamespace(tmp=TD10, runs=[])
fake._assemble = types.MethodType(lore.Session._assemble, fake)
run1 = dict(anchors(S1), sys=SYS_, mic=MIC_, voice=VOI_, game=None)
run2 = dict(anchors(S2), sys=SYS_, mic=MIC_, voice=None, game=None)
F1, F2 = os.path.join(TD10, "_runf0.mp4"), os.path.join(TD10, "_runf1.mp4")
del LSAID[:]
ok1 = fake._assemble([S1], SYS_, MIC_, F1, run1, want_taps={"Voice"})
ok2 = fake._assemble([S2], SYS_, MIC_, F2, run2, want_taps={"Voice"})
check("both run-finals bind", ok1 and ok2 and os.path.isfile(F1) and os.path.isfile(F2))
check("both carry the SAME four titles: Mix, Voice, Mic (+ nothing else)",
      names_of(F1) == names_of(F2) == ["mix", "voice", "mic"])
check("run 2 says it got a placeholder",
      any("Run had no Voice sound" in m and "a silent Voice track keeps the file's layout" in m
          for m in LSAID))
check("the sync log names the voice offset only where the wav exists",
      any(m.startswith("A/V sync: video t0 anchored;") and ", voice " in m for m in LSAID)
      and any(m.startswith("A/V sync: video t0 anchored;") and ", voice " not in m
              for m in LSAID))
STITCH = os.path.join(TD10, "stitched.mp4")
check("_concat_copy of the two succeeds and the length is the sum",
      lore._concat_copy(FF, [F1, F2], STITCH)
      and abs((ns["_probe_duration"](STITCH) if "_probe_duration" in ns
               else lore._probe_duration(STITCH)) - 4.0) < 0.35)
sp = spectrum(F1, "voice")
check("run 1's Voice track carries Discord (1500) alone",
      carries(sp, (1500,), (200, 900, 3000)))
del LSAID[:]
F3 = os.path.join(TD10, "_runf2.mp4")
run3 = dict(anchors(S1), sys=SYS_, mic=MIC_, voice=EMPTY, game=GAM_)
ok3 = fake._assemble([S1], SYS_, MIC_, F3, run3, want_taps={"Voice", "Game"})
check("an empty voice wav is dropped, said, and the bind still succeeds",
      ok3 and any("the Voice track's audio was empty - bound without it" in m for m in LSAID)
      and names_of(F3) == ["mix", "voice", "game", "mic"])
check("...its Voice track became the placeholder (silent), the Game is real",
      all(v < 30 for v in spectrum(F3, "voice").values())
      and carries(spectrum(F3, "game"), (3000,), (200, 900, 1500)))
del LSAID[:]
F4 = os.path.join(TD10, "_runf3.mp4")
run4 = dict(anchors(S1), sys=SYS_, mic=MIC_, voice=None, game=None)
ok4 = fake._assemble([S1], SYS_, MIC_, F4, run4)
check("a run with no taps and no want binds today's Mix/System/Mic",
      ok4 and names_of(F4) == ["mix", "system", "mic"]
      and not any("empty" in m or "placeholder" in m for m in LSAID))
# the retry rung: a tap path that is a real file but not audio
BAD = os.path.join(TD10, "bad_voice.wav")
open(BAD, "wb").write(b"RIFF" + b"\x00" * 4000)
del LSAID[:]
F5 = os.path.join(TD10, "_runf4.mp4")
real_probe = lore._probe_duration
lore._probe_duration = lambda p: (1.0 if p == BAD else real_probe(p))
run5 = dict(anchors(S1), sys=SYS_, mic=MIC_, voice=BAD, game=None)
ok5 = fake._assemble([S1], SYS_, MIC_, F5, run5)
lore._probe_duration = real_probe
check("a bind that fails WITH the tap tracks is bound again without them",
      ok5 and any("Bind with the Voice/Game tracks failed; binding again without them." in m
                  for m in LSAID) and names_of(F5) == ["mix", "system", "mic"])

print("\n--- M10b: the run-final stitch keeps every titled track (real render) ---")
FFP = os.path.join(FFDIR, "ffprobe.exe")


def vpts(path):
    """The video packets' pts, sorted, by ffprobe -show_packets."""
    r = subprocess.run([FFP, "-v", "error", "-select_streams", "v:0",
                        "-show_packets", "-of", "json", path],
                       capture_output=True, timeout=60,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    pk = json.loads(r.stdout.decode("utf-8", "ignore") or "{}").get("packets", [])
    return sorted(float(p.get("pts_time") or p.get("dts_time") or 0) for p in pk)


CMDS = []
real_popen = lore._popen


def spy_popen(cmd, **kw):
    CMDS.append(list(cmd))
    return real_popen(cmd, **kw)


lore._popen = spy_popen
runA = dict(anchors(S1), sys=SYS_, mic=MIC_, voice=VOI_, game=GAM_)
runB = dict(anchors(S2), sys=SYS_, mic=MIC_, voice=VOI_, game=GAM_)
FA, FB = os.path.join(TD10, "_runfA.mp4"), os.path.join(TD10, "_runfB.mp4")
okA = fake._assemble([S1], SYS_, MIC_, FA, runA, want_taps={"Voice", "Game"})
okB = fake._assemble([S2], SYS_, MIC_, FB, runB, want_taps={"Voice", "Game"})
check("two 2 s Mix/Voice/Game/Mic run-finals bind",
      okA and okB and names_of(FA) == names_of(FB) == ["mix", "voice", "game", "mic"])
ST_OLD = os.path.join(TD10, "stitch_old.mp4")
ST_NEW = os.path.join(TD10, "stitch_new.mp4")
del CMDS[:]
ok_old = lore._concat_copy(FF, [FA, FB], ST_OLD)
cmd_old = list(CMDS[-1])
del CMDS[:]
ok_new = lore._concat_copy(FF, [FA, FB], ST_NEW, keep_tracks=True)
cmd_new = list(CMDS[-1])
check("the bare '-c copy' stitch (every other caller) keeps ONE untitled track - the measured bug",
      ok_old and len(names_of(ST_OLD)) == 1)
check("keep_tracks: the stitched night carries Mix, Voice, Game, Mic in order, titled",
      ok_new and names_of(ST_NEW) == ["mix", "voice", "game", "mic"])
check("...and its length is the sum of the runs",
      abs(lore._probe_duration(ST_NEW) - 4.0) < 0.35)
check("...each layer of the stitch still carries only its own tone",
      carries(spectrum(ST_NEW, "voice"), (1500,), (200, 900, 3000))
      and carries(spectrum(ST_NEW, "game"), (3000,), (200, 900, 1500))
      and carries(spectrum(ST_NEW, "mic"), (900,), (200, 1500, 3000)))
check("the keep_tracks command maps 0:v:0 and 0:a? and restates the four titles",
      cmd_new[cmd_new.index("-i") + 2:cmd_new.index("-c")]
      == ["-map", "0:v:0", "-map", "0:a?",
          "-metadata:s:a:0", "title=Mix", "-metadata:s:a:1", "title=Voice",
          "-metadata:s:a:2", "title=Game", "-metadata:s:a:3", "title=Mic"])
check("...the default command is byte-identical to before (no -map, no titles)",
      "-map" not in cmd_old and not any(a.startswith("-metadata") for a in cmd_old)
      and cmd_old[:cmd_old.index("-i")] == cmd_new[:cmd_new.index("-i")]
      and cmd_old[-3:-1] == cmd_new[-3:-1] == ["-c", "copy"]
      and cmd_old[cmd_old.index("-i") + 2:] == ["-c", "copy", ST_OLD])
check("only the run-final stitch passes keep_tracks (the source)",
      SRC.count("keep_tracks=True") == 1
      and "run_finals, tmp_final,\n                                keep_tracks=True)" in SRC)
# the old three-track night: Mix/System/Mic keeps its three titles too
F4b = os.path.join(TD10, "_runf3b.mp4")
ok4b = fake._assemble([S2], SYS_, MIC_, F4b, dict(anchors(S2), sys=SYS_, mic=MIC_,
                                                   voice=None, game=None))
ST_3 = os.path.join(TD10, "stitch_three.mp4")
check("the old three-track case (Mix/System/Mic x2) keeps its 3 titled streams",
      ok4b and lore._concat_copy(FF, [F4, F4b], ST_3, keep_tracks=True)
      and names_of(ST_3) == ["mix", "system", "mic"]
      and abs(lore._probe_duration(ST_3) - 4.0) < 0.35)

print("\n--- M10c: a placeholder never outlives the picture ---")
# run 1 lacks the Voice (placeholder), run 2 has it: the stitched night's
# 21st frame (run 2's first) must land at run 1's length, not 2 s later
runP = dict(anchors(S1), sys=SYS_, mic=MIC_, voice=None, game=GAM_)
FP = os.path.join(TD10, "_runfP.mp4")
del LSAID[:]
okP = fake._assemble([S1], SYS_, MIC_, FP, runP, want_taps={"Voice", "Game"})
check("run 1 binds with a Voice placeholder",
      okP and names_of(FP) == ["mix", "voice", "game", "mic"]
      and any("Run had no Voice sound" in m for m in LSAID))
dP = lore._probe_duration(FP)
check("...and the placeholder did not stretch it: the file is the picture's 2 s",
      dP is not None and abs(dP - 2.0) < 0.15)
ST_P = os.path.join(TD10, "stitch_ph.mp4")
okS = lore._concat_copy(FF, [FP, FB], ST_P, keep_tracks=True)
pts = vpts(ST_P)
check("stitched: 40 frames, run 2's first frame lands at run 1's length",
      okS and len(pts) == 40 and abs(pts[20] - dP) < 0.15
      and abs(lore._probe_duration(ST_P) - 4.0) < 0.35)
# THE BUG, reproduced with the old 'bind_total + 2.0' placeholder through
# build_mux_cmd directly: a 4 s silence under a 2 s picture, and the next
# run starts 2 s late - a frozen hole in the film
OLDPH = os.path.join(TD10, "_runfOld.mp4")
rc = run(build_mux_cmd(S1, SYS_, MIC_, OLDPH, taps=[
    {"label": "Voice", "path": None, "off": 0, "secs": 4.0},
    {"label": "Game", "path": GAM_, "off": 0, "secs": None}]))
ST_H = os.path.join(TD10, "stitch_hole.mp4")
okH = lore._concat_copy(FF, [OLDPH, FB], ST_H, keep_tracks=True)
pts_h = vpts(ST_H)
check("(the old placeholder, 2 s past the picture: run 2's first frame at 4.0 s - the hole)",
      rc == 0 and okH and len(pts_h) == 40 and abs(pts_h[20] - 4.0) < 0.15)
check("the placeholder's length is the picture's, never past it (the source)",
      '"secs": bind_total + 2.0' not in SRC
      and "ph_secs = float(vdur) if vdur else float(bind_total)" in SRC)
lore._popen = real_popen

print("\n--- M11: the remuxers keep every track on a real render ---")
ns["_title_maps"] = None
extract("_title_maps", ns)
F_FIN = os.path.join(TD, "finished.mp4")
rc = run([FF, "-y", "-v", "error", "-i", F_NEW, "-c:v", "copy",
          "-map", "0:v:0", "-map", "0:a?", *ns["_title_maps"](F_NEW),
          "-c:a", "copy", F_FIN])
check("the finisher's map arguments keep Mix/Voice/Game/Mic with their titles",
      rc == 0 and names_of(F_FIN) == ["mix", "voice", "game", "mic"])
F_CUT = os.path.join(TD, "cut.mp4")
rc = run([FF, "-y", "-v", "error", "-i", F_NEW, "-c:v", "copy", "-c:a", "aac", F_CUT])
check("...where the default pick (a share cut) keeps one track: the Mix",
      rc == 0 and names_of(F_CUT) == [""] and carries(spectrum(F_CUT, "mix"), (200, 900), (1500, 3000)))

import shutil
shutil.rmtree(TD, ignore_errors=True)
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
