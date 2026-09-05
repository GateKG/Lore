# -*- coding: utf-8 -*-
"""3.31 THE SENSES BY SOURCE - the pass, the fold, the worker.

  1. _senses_one lifted out of lore.py by name, ffmpeg and the worker
     replaced by a spy: on a Mix/System/Voice/Game/Mic night ONE ffmpeg
     writes the room (0:a:2 + 0:a:4 at parity) to <wav>, the Mic to
     .mic.wav and the Game to .game.wav; the .ctl beside the wav says
     src 'room' and names the game wav; a worker answer without 'src'
     is stamped mix and logged 'predates 3.31'; the g-flag block leaves
     a layered night's transcript alone; the scratch is cleaned up. On
     an old Mix/System/Mic night the ffmpeg argv and the worker argv are
     BYTE-IDENTICAL to the 3.30 pass's (HEAD's _senses_one, lifted out
     of `git show HEAD:lore.py` and run against the same spy), and the
     g-flag block runs as it always did.
  2. _merge_sns_into_hl with sns.src.clap = 'game': a cheer beside a
     room shout is its own mark (src game); beside an untagged old mark
     it borrows the seat as today.
  3. the whole worker end to end with fake torch / transformers /
     soundfile (no model): an old night (no .ctl) writes the same
     events, hype values, counters, speakers and embeddings as the HEAD
     worker; a room night gates the silent windows, normalises the
     spoken ones, reads the game wav for CLAP, stamps its sources, and
     honours the .ctl threads; an unreadable game wav fails that pass
     alone with src.clap null.
No devices, nothing under D:\\Records, nothing under %LOCALAPPDATA%."""
import ast
import collections
import importlib.util
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import types
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
WPATH = os.path.join(ROOT, "ai", "senses_worker.py")
WSRC = io.open(WPATH, encoding="utf-8").read()


# THE FILES BEFORE STAGE D are the reader's commit (5e38f9b), not
# whatever HEAD happens to be once this stage is committed too
PRE = "5e38f9b"


def git_show(rel):
    return subprocess.run(["git", "-C", ROOT, "show", PRE + ":" + rel],
                          capture_output=True, text=True,
                          encoding="utf-8").stdout


HEAD = git_show("lore.py")
HEAD_W = git_show("ai/senses_worker.py")

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


_TREES = {}


def tree_of(src):
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
            return
    raise AssertionError(name + " not assigned")


TMP = tempfile.mkdtemp(prefix="lore_sns331_")
SHELF = os.path.join(TMP, "Records")
TH = os.path.join(SHELF, ".lore_thumbs")
os.makedirs(os.path.join(SHELF, "Bazaar", "Videos"))
os.makedirs(TH)
FF = r"C:\fake\ffmpeg.exe"
PY, WORK = r"C:\fake\python.exe", r"C:\fake\senses_worker.py"
VID = os.path.join(SHELF, "Bazaar", "Videos", "Bazaar_20260905_120000.mp4")
io.open(VID, "wb").write(b"\0" * 1000)


def side(kind):
    return os.path.join(TH, "Bazaar_20260905_120000." + kind + ".json")


CMDS, CTL, LOG = [], [], []
CANNED = {"v": 1, "events": [{"t": 100.0, "kind": "cheer", "p": 0.3}],
          "hype": {"hop": 3.0, "v": [0.3] * 40}, "speakers": [],
          "emb": [], "counters": {}, "music": []}


def fake_ai_run(cmd, timeout, flags, env=None):
    CMDS.append(list(cmd))
    if cmd[0] == FF:
        for i, a in enumerate(cmd):
            if a.endswith(".wav") and i > 0 and cmd[i - 1] == "pcm_s16le":
                io.open(a, "wb").write(b"RIFF")
        return 0, b"", b""
    if cmd[0] == PY:
        wav = cmd[2]
        try:
            CTL.append(json.load(io.open(wav + ".ctl", encoding="utf-8")))
        except Exception:
            CTL.append(None)
        io.open(cmd[3], "w", encoding="utf-8").write(json.dumps(CANNED))
        return 0, b"", b""
    return 1, b"", b"?"


def make_ns(src, names):
    ns = {"os": os, "json": json, "subprocess": subprocess,
          "threading": threading, "collections": collections,
          "SETTINGS": {"ffmpeg_path": FF, "output_dir": SHELF},
          "_AI": {"abort": False, "proc": None, "soft_fail": False,
                  "job_secs": 60, "index": None, "done_rev": 0},
          "log": LOG.append, "_ai_run": fake_ai_run,
          "_work_dir": lambda: TMP, "_senses_paths": lambda: (PY, WORK),
          "_audio_track_names": lambda p: list(names),
          "_display_name": lambda x: "Bazaar", "_parse_clip_name": lambda x: x,
          "_reader_threads": lambda: 2, "_probe_duration": lambda p: 60.0,
          "_sns_carry_names": lambda old, new: ({}, ""),
          "_here": lambda: TMP, "_HUD_STEP": 60.0,
          "_merge_sns_into_hl": lambda p, sns=None: (0, None),
          "_bank_sidecar": lambda p, k: None,
          "_source_busy_add": lambda p: None,
          "_source_busy_done": lambda p: None}
    for nm in ("_TRK_MIX", "_Layer"):
        try:
            lift_assign(src, nm, ns)
        except AssertionError:
            pass
    if "_LAYERS" in src:
        lift_assign(src, "_LAYERS", ns)
    for nm in ("_thumb_dir", "_ai_sidecar", "_atomic_write_json", "_track_for",
               "_mic_track", "_voice_track", "_game_track", "_mix_audio_args",
               "_fan_args", "_layer_args", "_extract_layers", "_senses_one"):
        try:
            extract(src, nm, ns)
        except AssertionError:
            if nm in ("_thumb_dir", "_ai_sidecar", "_atomic_write_json",
                      "_mic_track", "_mix_audio_args", "_senses_one"):
                raise
    return ns


def reset(stt_g=True):
    for k in ("sns", "stt", "hl"):
        try:
            os.remove(side(k))
        except OSError:
            pass
    io.open(side("stt"), "w", encoding="utf-8").write(json.dumps(
        {"segments": [{"a": 1000, "b": 2000, "t": "hello", "g": 1}]}))
    os.utime(side("stt"), (1700000000, 1700000000))
    del CMDS[:]
    del CTL[:]
    del LOG[:]


print("--- 1. _senses_one on a layered night ---")
LAY = ["mix", "system", "voice", "game", "mic"]
ns = make_ns(SRC, LAY)
reset()
r = ns["_senses_one"](VID)
check("the pass runs", r is True)
ff = [c for c in CMDS if c[0] == FF]
wk = [c for c in CMDS if c[0] == PY]
wav = wk[0][2] if wk else ""
check("ONE ffmpeg for every layer, ONE worker call",
      len(ff) == 1 and len(wk) == 1 and wav.endswith(".wav"))
c = ff[0] if ff else []
gi = c.index("-filter_complex") if "-filter_complex" in c else -1
check("the room = Voice (0:a:2) + Mic (0:a:4) at parity -> <wav>",
      gi > 0 and c[gi + 1]
      == "[0:a:2][0:a:4]amix=inputs=2:duration=longest:normalize=0[G0]"
      and c[c.index("[G0]") + 1:c.index("[G0]") + 7]
      == ["-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le"]
      and c[c.index("[G0]") + 7] == wav)
check("the Mic (0:a:4) -> .mic.wav, the Game (0:a:3) -> .game.wav",
      "0:a:4" in c and c[c.index("0:a:4") + 7] == wav + ".mic.wav"
      and "0:a:3" in c and c[c.index("0:a:3") + 7] == wav + ".game.wav")
check("the worker argv is today's: [py, work, wav, out, game, mic]",
      wk[0] == [PY, WORK, wav, wav + ".json", "Bazaar", wav + ".mic.wav"])
check("the .ctl said src room, the game wav (src game), the mic, the threads",
      CTL and CTL[0] == {"src": "room", "game_wav": wav + ".game.wav",
                         "game_src": "game", "mic": wav + ".mic.wav",
                         "threads": 2})
sns = json.load(io.open(side("sns"), encoding="utf-8"))
check("a worker answer without 'src' is stamped mix throughout and logged",
      sns.get("src") == {"clap": "mix", "hype": "mix", "who": "mix"}
      and any("senses_worker.py on disk predates 3.31" in m for m in LOG))
stt = json.load(io.open(side("stt"), encoding="utf-8"))
check("the g-flag block left the layered night's transcript alone",
      stt["segments"][0].get("g") == 1
      and os.path.getmtime(side("stt")) == 1700000000
      and not any("flagged as probably" in m for m in LOG))
check("the summary log names the feeders",
      any("Fed by mix (hype, voices) and mix (sounds)." in m for m in LOG))
check("the scratch is cleaned up: wav, mic, game, ctl, out",
      not any(os.path.exists(p) for p in
              (wav, wav + ".mic.wav", wav + ".game.wav", wav + ".ctl",
               wav + ".json")))

print("\n--- 1b. a Voice night with no Game track: the sounds hear the mix ---")
ns2 = make_ns(SRC, ["mix", "voice", "mic"])
reset()
ns2["_senses_one"](VID)
c = [x for x in CMDS if x[0] == FF][0]
check("the game layer falls to the mix (0:a:0) -> .game.wav, src 'mix'",
      "0:a:0" in c and c[c.index("0:a:0") + 7].endswith(".game.wav")
      and "[0:a:1][0:a:2]amix" in c[c.index("-filter_complex") + 1]
      and CTL[0]["src"] == "room" and CTL[0]["game_src"] == "mix")

print("\n--- 1c. an old night: byte-identical to 3.30's pass ---")
OLD = ["mix", "system", "mic"]
ns3 = make_ns(SRC, OLD)
reset()
ns3["_senses_one"](VID)
new_cmds = [list(x) for x in CMDS]
new_ctl = list(CTL)
new_stt = json.load(io.open(side("stt"), encoding="utf-8"))
new_log = list(LOG)
hns = make_ns(HEAD, OLD)
reset()
hns["_senses_one"](VID)
old_cmds = [list(x) for x in CMDS]
old_stt = json.load(io.open(side("stt"), encoding="utf-8"))
old_log = list(LOG)
check("the ffmpeg argvs are 3.30's, one by one (two commands)",
      [x for x in new_cmds if x[0] == FF] == [x for x in old_cmds if x[0] == FF]
      and len([x for x in new_cmds if x[0] == FF]) == 2)
check("...the first is today's literal mix extract",
      [x for x in new_cmds if x[0] == FF][0]
      == [FF, "-y", "-loglevel", "error", "-i", VID, "-vn", "-map", "0:a:0",
          "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", wav]
      and [x for x in new_cmds if x[0] == FF][1]
      == [FF, "-y", "-loglevel", "error", "-i", VID, "-map", "0:a:2", "-ac",
          "1", "-ar", "48000", "-c:a", "pcm_s16le", wav + ".mic.wav"])
check("the worker argv is identical",
      [x for x in new_cmds if x[0] == PY] == [x for x in old_cmds if x[0] == PY])
check("the .ctl on an old night says mix, no game wav",
      new_ctl[0] == {"src": "mix", "game_wav": None, "game_src": None,
                     "mic": wav + ".mic.wav", "threads": 0})   # 0 = the worker's own count on an old night
check("the g-flag block ran as it always did (the flag came off, both)",
      "g" not in new_stt["segments"][0] and "g" not in old_stt["segments"][0]
      and any("1 unflagged" in m for m in new_log)
      and any("1 unflagged" in m for m in old_log))
check("the only new log lines are the stamp and the feeders",
      [m for m in new_log if "predates" not in m and "Fed by" not in m]
      == [m for m in old_log if "Fed by" not in m]
      or [m.split(" Fed by")[0] for m in new_log if "predates" not in m]
      == [m for m in old_log])

print("\n--- 2. the fold's source gate ---")
mns = {"os": os, "json": json, "_AI": {"done_rev": 0}, "log": LOG.append}
extract(SRC, "_thumb_dir", mns)
mns["SETTINGS"] = {"output_dir": SHELF}
extract(SRC, "_ai_sidecar", mns)
extract(SRC, "_atomic_write_json", mns)
extract(SRC, "_merge_sns_into_hl", mns)
merge = mns["_merge_sns_into_hl"]


def hl_write(events):
    io.open(side("hl"), "w", encoding="utf-8").write(
        json.dumps({"v": 2, "events": events, "src": {"loud": "room"}}))


hl_write([{"t": 103.0, "z": 20.0, "src": "room"}])
sns_g = {"events": [{"t": 100.0, "kind": "cheer", "p": 0.3}],
         "src": {"clap": "game", "hype": "room", "who": "room"}, "music": []}
added, err = merge(VID, sns_g)
hl = json.load(io.open(side("hl"), encoding="utf-8"))
check("a game cheer beside a room shout is its OWN mark, src game",
      added == 1 and err is None and len(hl["events"]) == 2
      and [e for e in hl["events"] if e["t"] == 100.0][0]["src"] == "game"
      and [e for e in hl["events"] if e["t"] == 100.0][0]["kind"] == "cheer"
      and "kind" not in [e for e in hl["events"] if e["t"] == 103.0][0])
check("...and the hl's own src doc survives the write",
      hl.get("src") == {"loud": "room"})
hl_write([{"t": 103.0, "z": 20.0}])
added, err = merge(VID, sns_g)
hl = json.load(io.open(side("hl"), encoding="utf-8"))
check("beside an untagged old mark it borrows the seat, as today",
      added == 0 and len(hl["events"]) == 1 and hl["events"][0]["kind"] == "cheer")
hl_write([{"t": 103.0, "z": 20.0, "src": "room"}])
added, err = merge(VID, {"events": [{"t": 100.0, "kind": "cheer", "p": 0.3}],
                         "music": []})
hl = json.load(io.open(side("hl"), encoding="utf-8"))
check("an old worker's answer (no src) is the mix and may sit on a room mark",
      added == 0 and hl["events"][0]["kind"] == "cheer")
hl_write([{"t": 103.0, "z": 20.0, "src": "room"}])
added, err = merge(VID, {"events": [], "ocr": [{"t": 300.0, "kind": "victory"}],
                         "music": []})
hl = json.load(io.open(side("hl"), encoding="utf-8"))
check("a HUD read lands with src 'screen'",
      added == 1 and [e for e in hl["events"] if e["t"] == 300.0][0]["src"]
      == "screen")

print("\n--- 3. the whole worker, fake torch (no model) ---")
SR = 48000


def wav_write(path, a, sr=SR):
    x = np.clip(np.asarray(a, dtype="float32"), -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype("<i2").tobytes())


READS = []


def wav_read(path, dtype="float32"):
    READS.append(path)
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0, sr


SF = types.ModuleType("soundfile")
SF.read = wav_read
THREADS = []


class _NoGrad:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Module:
    def __init__(self, *a, **k):
        pass

    def __call__(self, *a, **k):
        return self.forward(*a, **k)

    def eval(self):
        return self

    def load_state_dict(self, d, strict=True):
        return None


class _Identity(_Module):
    def forward(self, x):
        return x


NN = types.ModuleType("torch.nn")
NN.Module, NN.Linear, NN.Dropout = _Module, _Identity, _Identity
TORCH = types.ModuleType("torch")
TORCH.nn = NN
TORCH.from_numpy = lambda a: a
TORCH.no_grad = _NoGrad
TORCH.tanh = np.tanh
TORCH.load = lambda *a, **k: {}
TORCH.is_tensor = lambda x: False
TORCH.set_num_threads = THREADS.append


class _LHS:
    def __init__(self, x):
        self.x = np.asarray(x)[0]

    def mean(self, dim=1):
        x = self.x
        return np.array([[float(np.sqrt(np.mean(x * x))), float(x.mean()),
                          float(x.std())]])


class _Body(_Module):
    @staticmethod
    def from_pretrained(*a, **k):
        return _Body()

    def forward(self, x):
        return types.SimpleNamespace(last_hidden_state=_LHS(x))


class _Cfg:
    @staticmethod
    def from_pretrained(*a, **k):
        return types.SimpleNamespace(hidden_size=8, final_dropout=0.1)


TR = types.ModuleType("transformers")
TR.Wav2Vec2Model, TR.Wav2Vec2Config = _Body, _Cfg
sys.modules["soundfile"] = SF
sys.modules["torch"] = TORCH
sys.modules["torch.nn"] = NN
sys.modules["transformers"] = TR


def load_worker(text, name):
    d = os.path.join(TMP, name)
    os.makedirs(os.path.join(d, "models", "hype"))
    p = os.path.join(d, "senses_worker.py")
    io.open(p, "w", encoding="utf-8", newline="").write(text)
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


W_NEW = load_worker(WSRC, "sns331_new")
W_OLD = load_worker(HEAD_W, "sns331_head")
rng = np.random.default_rng(5)
room = np.zeros(60 * SR, dtype="float32")
room[:20 * SR] = rng.normal(0, 0.1, 20 * SR)
game = 0.3 * np.sin(2 * np.pi * 440 * np.arange(60 * SR) / SR)
p_room = os.path.join(TMP, "sns.wav")
p_game = os.path.join(TMP, "sns.wav.game.wav")
wav_write(p_room, room)
wav_write(p_game, game)


def run(mod, ctl, name):
    out = os.path.join(TMP, name + ".json")
    try:
        os.remove(p_room + ".ctl")
    except OSError:
        pass
    if ctl is not None:
        io.open(p_room + ".ctl", "w", encoding="utf-8").write(json.dumps(ctl))
    del READS[:]
    del THREADS[:]
    rc = mod.main(p_room, out, "Bazaar")
    return rc, json.load(io.open(out, encoding="utf-8"))


rc_h, d_h = run(W_OLD, None, "head")
rc_n, d_n = run(W_NEW, None, "new")
check("an old night (no .ctl): both workers run to the end",
      rc_h == 0 and rc_n == 0)
check("...the same events, speakers, embeddings, music",
      d_h["events"] == d_n["events"] and d_h["speakers"] == d_n["speakers"]
      and d_h["emb"] == d_n["emb"] and d_h.get("music") == d_n.get("music"))
check("...the same hype values and hop (%d windows)" % len(d_h["hype"]["v"]),
      d_h["hype"]["v"] == d_n["hype"]["v"]
      and d_h["hype"]["hop"] == d_n["hype"]["hop"]
      and len(d_h["hype"]["v"]) == 20)
check("...the same counters", d_h["counters"] == d_n["counters"])
check("...the only new keys: src (mix throughout) and the hype block's "
      "src/norm/gate_db/quiet/windows",
      set(d_n) - set(d_h) == {"src"}
      and d_n["src"] == {"clap": "mix", "hype": "mix", "who": "mix"}
      and set(d_n["hype"]) - set(d_h["hype"])
      == {"src", "norm", "gate_db", "quiet", "windows"}
      and d_n["hype"]["src"] == "mix" and d_n["hype"]["norm"] == 0
      and d_n["hype"]["gate_db"] is None and d_n["hype"]["quiet"] == 0
      and d_n["hype"]["windows"] == 20)
check("...no window was gated on the mix (quiet 0 - the zeros got a "
      "reading of their own, as today)",
      d_n["hype"]["quiet"] == 0 and len(d_n["hype"]["v"]) == 20)
check("...the room wav was the only file read, once, by both",
      READS == [p_room])

rc, d = run(W_NEW, {"src": "room", "game_wav": p_game, "game_src": "game",
                    "mic": None, "threads": 3}, "room")
check("a room night runs", rc == 0)
check("...src: clap game, hype room, who room",
      d["src"] == {"clap": "game", "hype": "room", "who": "room"})
check("...the game wav was read for the sound vocabulary, after the room",
      READS == [p_room, p_game])
hv = d["hype"]["v"]
spoken = [x for x in hv if x > 0]
check("...the windows past the 20 s of talk are 0 (no model call), the "
      "spoken ones are the normalised reading (tanh 1 = %.3f)"
      % round(math.tanh(1.0), 3),
      len(hv) == 20 and all(x == 0.0 for x in hv[7:])
      and all(abs(x - round(math.tanh(1.0), 3)) <= 0.002 for x in hv[:5]))
check("...quiet counts the gated windows, norm 1, gate -60, windows 19",
      d["hype"]["quiet"] == hv.count(0.0) and d["hype"]["norm"] == 1
      and d["hype"]["gate_db"] == -60.0 and d["hype"]["windows"] == 20
      and d["hype"]["src"] == "room")
check("...the .ctl threads are honoured", THREADS == [3])
check("...the mix path used the default thread count",
      run(W_NEW, None, "again")[0] == 0 and THREADS
      and THREADS[0] == max(2, (os.cpu_count() or 8) - 4))
rc, d = run(W_NEW, {"src": "room", "game_wav": os.path.join(TMP, "nope.wav"),
                    "game_src": "game", "mic": None}, "badgame")
check("an unreadable game wav: clap fails alone, src.clap null, hype still "
      "the room",
      rc == 0 and d["counters"]["clap_failed"].startswith("game wav unreadable")
      and d["src"]["clap"] is None and d["src"]["hype"] == "room"
      and d["hype"]["src"] == "room")
rc, d = run(W_NEW, {"src": "room", "game_wav": p_game, "game_src": "mix"},
            "gamemix")
check("a game wav that is the mix (no Game track) is stamped clap 'mix'",
      d["src"]["clap"] == "mix")
check("the worker's usage line names the mic argument",
      "senses_worker.py <in.wav> <out.json> [game] [mic]" in WSRC)

shutil.rmtree(TMP, ignore_errors=True)
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
