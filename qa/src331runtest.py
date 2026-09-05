# -*- coding: utf-8 -*-
"""3.31 SOURCES - Session._stop_run and _write_src_sidecar on a fake
session (rectests style: lore.log captured, _list_segments stubbed), the
REAL methods lifted by name, with a fake audio object exposing
system_wav / mic_wav / voice_wav / game_wav / first_sample_wallclock /
sources_manifest. Proves:

  1  all four files -> the run carries voice/game/voice_t0/game_t0/sources;
  2  no layers -> the run dict equals the stage A fixture KEY FOR KEY plus
     voice=None/game=None/voice_t0=None/game_t0=None/sources=None, and
     NO .src.json is written (capture_by_source off gives the same);
  3  game_audio_only + capture_by_source -> run['sys'] IS the game file
     and sys_t0 == game_t0;
  4  the .src.json shape, at _ai_sidecar(final, 'src');
  5  'src' is not in _ATTIC_OF.
The stage A fixture is frozen here as a literal AND, when git can show
the stage A commit, re-derived from that file's own _stop_run."""
import ast
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
TREE = ast.parse(SRC)
STAGE_A = "af7d571"

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


def method_src(src, tree, cls_name, name):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for f in node.body:
                if isinstance(f, ast.FunctionDef) and f.name == name:
                    return textwrap.dedent("\n".join(
                        src.splitlines()[f.lineno - 1:f.end_lineno]))
    raise AssertionError("%s.%s not found" % (cls_name, name))


def method(cls_name, name, ns, src=SRC, tree=TREE):
    exec(compile(method_src(src, tree, cls_name, name),
                 "<%s.%s>" % (cls_name, name), "exec"), ns)
    return ns[name]


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


T = 1_700_000_000.0


class Clock(object):
    @staticmethod
    def time():
        return T + 100.0


TD = tempfile.mkdtemp(prefix="run331_")
THUMBS = os.path.join(TD, ".lore_thumbs")
SAID = []
SETTINGS = {"capture_by_source": True, "game_audio_only": False,
            "output_dir": TD}
ns = {"os": os, "time": Clock, "json": json, "log": SAID.append,
      "SETTINGS": SETTINGS, "_thumb_dir": lambda out: THUMBS,
      "_list_segments": lambda d: ["seg_%06d.mp4" % i for i in range(3)]}
extract("_ai_sidecar", ns)
extract("_atomic_write_json", ns)
lift_assign("_ATTIC_OF", ns)


class FakeAudio(object):
    def __init__(self, **wavs):
        self.system_wav = wavs.get("system")
        self.mic_wav = wavs.get("mic")
        self.voice_wav = wavs.get("voice")
        self.game_wav = wavs.get("game")
        self.t0 = {"system": T + 1.0, "mic": T + 1.5, "voice": T,
                   "game": T}
        self.calls = []

    def signal_stop(self):
        self.calls.append("signal_stop")

    def finalize(self):
        self.calls.append("finalize")

    def first_sample_wallclock(self, kind):
        return self.t0.get(kind) if getattr(self, kind + "_wav", None) else None

    def sources_manifest(self):
        return {"t0": T, "media": "loopback" if self.system_wav else "none",
                "voice": ({"exe": "discord.exe", "pid": 100, "specific": True,
                           "opened": T + 0.4, "anchor": T, "reopens": 0,
                           "state": "live", "gap_s": 0.0}
                          if self.voice_wav else None),
                "game": ({"exe": "game.exe", "pid": 7, "specific": True,
                          "opened": T + 0.3, "anchor": T, "reopens": 1,
                          "state": "live", "gap_s": 3.5}
                         if self.game_wav else None)}


class FakeSession(object):
    def __init__(self, audio):
        self.audio = audio
        self._wgc = None
        self.vproc = None
        self.tmp = TD
        self._run_vstart = 0
        self.runs = []
        self._seg_start = 0
        self._run_index = 0
        self.final = os.path.join(TD, "Elden Ring_20260905_120000.mp4")


method("Session", "_stop_run", ns)
method("Session", "_write_src_sidecar", ns)
FakeSession._stop_run = ns["_stop_run"]
FakeSession._write_src_sidecar = ns["_write_src_sidecar"]


def wav(name):
    p = os.path.join(TD, name)
    open(p, "wb").write(b"RIFF")
    return p


SYS, MIC, VOI, GAM = wav("system_00.wav"), wav("mic_00.wav"), wav("voice_00.wav"), wav("game_00.wav")

# the run dict stage A wrote for THIS fake (sys/mic present, 3 segments)
STAGE_A_RUN = {"sys": SYS, "mic": MIC, "nseg": 3, "v_end_wall": T + 100.0,
               "sys_t0": T + 1.0, "mic_t0": T + 1.5}

print("--- 1: all four files ---")
au = FakeAudio(system=SYS, mic=MIC, voice=VOI, game=GAM)
sess = FakeSession(au)
sess._stop_run()
run = sess.runs[0]
check("the run carries the layers, their anchors and the manifest",
      run["voice"] == VOI and run["game"] == GAM and run["voice_t0"] == T
      and run["game_t0"] == T and run["sources"]["voice"]["exe"] == "discord.exe"
      and run["sources"]["game"]["gap_s"] == 3.5)
check("...the old keys exactly as before",
      all(run[k] == v for k, v in STAGE_A_RUN.items()))
check("...audio stopped then finalised, once each",
      au.calls == ["signal_stop", "finalize"] and sess.audio is None
      and sess._run_index == 1 and sess._seg_start == 3)

print("\n--- 2: no layers -> stage A's run dict key for key ---")
au = FakeAudio(system=SYS, mic=MIC)
sess = FakeSession(au)
sess._stop_run()
run = sess.runs[0]
NEW_NONE = {"voice": None, "game": None, "voice_t0": None, "game_t0": None}
check("the old keys equal the stage A fixture",
      {k: run[k] for k in STAGE_A_RUN} == STAGE_A_RUN)
check("the new keys are None except the manifest (capture_by_source on)",
      all(run[k] is None for k in NEW_NONE) and isinstance(run["sources"], dict)
      and set(run) == set(STAGE_A_RUN) | set(NEW_NONE) | {"sources"})
sess._write_src_sidecar()
check("NO .src.json for a night with no layer",
      not os.path.exists(ns["_ai_sidecar"](sess.final, "src")))
SETTINGS["capture_by_source"] = False
au = FakeAudio(system=SYS, mic=MIC)
sess = FakeSession(au)
sess._stop_run()
run = sess.runs[0]
check("capture_by_source OFF: the fixture plus every new key None (sources too)",
      {k: run[k] for k in STAGE_A_RUN} == STAGE_A_RUN
      and all(run[k] is None for k in list(NEW_NONE) + ["sources"]))
sess._write_src_sidecar()
check("...and no sidecar", not os.path.exists(ns["_ai_sidecar"](sess.final, "src")))
SETTINGS["capture_by_source"] = True

# the fixture re-derived from stage A's own _stop_run, when git can show it
try:
    old = subprocess.run(["git", "-C", ROOT, "show", STAGE_A + ":lore.py"],
                         capture_output=True, timeout=60).stdout.decode("utf-8")
    old_tree = ast.parse(old)
    ns_old = dict(ns)
    method("Session", "_stop_run", ns_old, src=old, tree=old_tree)
    FakeSessionA = type("FakeSessionA", (FakeSession,), {"_stop_run": ns_old["_stop_run"]})
    sa = FakeSessionA(FakeAudio(system=SYS, mic=MIC))
    sa._stop_run()
    check("stage A's own _stop_run on the same fake writes exactly the frozen fixture",
          sa.runs[0] == STAGE_A_RUN)
except Exception as e:
    print("  (stage A re-derivation skipped: %s)" % str(e)[:80])

print("\n--- 3: 'Keep only the game' + by source ---")
SETTINGS["game_audio_only"] = True
au = FakeAudio(mic=MIC, voice=VOI, game=GAM)      # no loopback was opened
sess = FakeSession(au)
sess._stop_run()
run = sess.runs[0]
check("run['sys'] IS the game file and sys_t0 == game_t0",
      run["sys"] == GAM and run["game"] == GAM and run["sys_t0"] == run["game_t0"] == T)
check("...the manifest says no loopback (media 'none')",
      run["sources"]["media"] == "none")
SETTINGS["game_audio_only"] = False
au = FakeAudio(mic=MIC, voice=VOI, game=GAM)
sess = FakeSession(au)
sess._stop_run()
check("without 'Keep only the game' the game file is NOT the sys",
      sess.runs[0]["sys"] is None and sess.runs[0]["game"] == GAM)

print("\n--- 4: the .src.json ---")
au = FakeAudio(system=SYS, mic=MIC, voice=VOI, game=GAM)
sess = FakeSession(au)
sess._stop_run()
sess.audio = FakeAudio(system=SYS, mic=MIC)       # a second run, Discord gone
sess._stop_run()
sess._write_src_sidecar()
p = ns["_ai_sidecar"](sess.final, "src")
check("written at _ai_sidecar(final, 'src') = <thumbs>/<name>.src.json",
      p == os.path.join(THUMBS, "Elden Ring_20260905_120000.src.json") and os.path.isfile(p))
doc = json.load(io.open(p, encoding="utf-8"))
check("the shape: v, the two switches, layers, exes, runs[]",
      doc["v"] == 1 and doc["capture_by_source"] is True
      and doc["game_audio_only"] is False
      and doc["layers"] == {"voice": True, "game": True, "media": True}
      and doc["voice_exe"] == "discord.exe" and doc["game_exe"] == "game.exe"
      and len(doc["runs"]) == 2)
check("runs[] says which runs were real (the placeholder's honesty)",
      doc["runs"][0]["voice"] is True and doc["runs"][1]["voice"] is False
      and doc["runs"][1]["game"] is False and doc["runs"][0]["voice_t0"] == T
      and doc["runs"][1]["sources"]["voice"] is None
      and doc["runs"][0]["sources"]["game"]["gap_s"] == 3.5)
check("a whole-night gap: sys_t0/mic_t0/v_end_wall ride along per run",
      doc["runs"][0]["sys_t0"] == T + 1.0 and doc["runs"][0]["mic_t0"] == T + 1.5
      and doc["runs"][0]["v_end_wall"] == T + 100.0)

print("\n--- 5: not a lane product ---")
check("'src' is not in _ATTIC_OF",
      all("src" not in v for v in ns["_ATTIC_OF"].values()))

import shutil
shutil.rmtree(TD, ignore_errors=True)
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
