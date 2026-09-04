# -*- coding: utf-8 -*-
"""3.30: the echo migration, driven for real on a scratch shelf.

Lifts _fab_gates / _asr_context_for / _echo_key / _echo_strike_migration
out of lore.py by AST, points the library helpers at a temp shelf, and
proves THE LAW line by line: physics strikes, a prompt echo said twice
strikes, a prompt-shaped line said ONCE stays, pins stay, readers that
ran the gates themselves are left alone, nothing is written that did
not change, and the second pass changes nothing.
"""
import ast
import io
import json
import os
import re
import sys
import tempfile
import textwrap
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_P = os.path.join(ROOT, "lore.py")
WORKER = os.path.join(ROOT, "ai", "asr_worker.py")
SRC = io.open(SRC_P, encoding="utf-8").read()

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


def extract(name, ns):
    tree = ast.parse(SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                SRC.splitlines()[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<x>", "exec"), ns)
            return ns[name]
    raise AssertionError(name + " not found")


tmp = tempfile.mkdtemp(prefix="lore_echo_")
LIB = os.path.join(tmp, "Records")
TH = os.path.join(LIB, ".lore_thumbs")
os.makedirs(TH)


def vid(game, stamp):
    d = os.path.join(LIB, game, "Videos")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "%s_%s.mp4" % (game, stamp))
    io.open(p, "wb").write(b"\0" * 200000)
    return p


def side(p, kind="stt"):
    return os.path.join(TH, os.path.splitext(os.path.basename(p))[0]
                        + "." + kind + ".json")


def put(p, doc, kind="stt", mt=None):
    io.open(side(p, kind), "w", encoding="utf-8").write(
        json.dumps(doc, ensure_ascii=False))
    if mt is not None:
        os.utime(side(p, kind), (mt, mt))


def load(p, kind="stt"):
    return json.load(io.open(side(p, kind), encoding="utf-8"))


def scan(d, kind):
    out = []
    for f in sorted(os.listdir(d)):
        if f.endswith(".mp4"):
            fp = os.path.join(d, f)
            out.append({"path": fp, "file": f, "kind": kind,
                        "mtime": os.path.getmtime(fp), "size": 200000})
    return out


def libdirs(out):
    res = []
    for g in sorted(os.listdir(LIB)):
        d = os.path.join(LIB, g, "Videos")
        if os.path.isdir(d):
            res.append((d, "session"))
    return res


calls = {"bank": [], "retell": [], "first": [], "log": []}
ns = {"os": os, "json": json, "re": re, "time": time,
      "SETTINGS": {"output_dir": LIB},
      "_AI": {}, "_MIG_SKIPPED": [0], "_MIG_BANKED": set(),
      "_reader_paths": lambda: ("python", WORKER),
      "_library_dirs": libdirs, "_scan_dir_mp4s": scan,
      "_ai_sidecar": lambda p, k: side(p, k),
      "_mig_bank": lambda p, k: calls["bank"].append((p, k)),
      "_aud_retell": lambda p, ts, refill=True:
          calls["retell"].append((p, list(ts), refill)) or len(ts),
      "_ai_ask_first": lambda p, w, why="": calls["first"].append(p),
      "_atomic_write_json": lambda p, d: io.open(
          p, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False)),
      "_aud_clip": lambda s, n=600: str(s)[:n],
      "_display_name": lambda x: x, "_parse_clip_name": lambda x: "Recording",
      "log": lambda m: calls["log"].append(m),
      "_FAB_GATES": {"mt": None, "fn": None}}
for name in ("_fab_gates", "_asr_context_for", "_echo_key",
             "_echo_strike_migration"):
    extract(name, ns)
# the module constant the migration reads
ns["_ECHO_MIG_READER"] = int(re.search(r"^_ECHO_MIG_READER\s*=\s*(\d+)",
                                       SRC, re.M).group(1))
mig = ns["_echo_strike_migration"]
gates = ns["_fab_gates"]()

print("--- the gates come out of the worker itself ---")
check("both gates lifted from ai/asr_worker.py", gates is not None)
ctx_echo, impossible = gates
check("the same object comes back on the second ask (cached on mtime)",
      ns["_fab_gates"]() is gates)
check("the context builder names the shelf's game",
      ns["_asr_context_for"](os.path.join(LIB, "Megabonk", "Videos",
                                          "x.mp4"))
      .startswith("Gaming session of Megabonk. Friends on Discord"))

PROMPT = ("Megabonk's gaming session with friends in the Discord server. "
          "Casual chatting about games they play, making fun of each "
          "other while playing together.")
FAST = "x" * 300                                  # 300 chars in 1s = 300 cps
REAL = "Calling down a sentry! Sentry or fucking rocket launcher? Uh."
ONCE = ("Megabonk's gaming session with friends in the Discord server is "
        "a fun time to spend, we're playing together tonight.")

# night A: reader 2, physics x3 + a real line + a pinned impossible line
A = vid("Megabonk", "20250923_211102")
put(A, {"v": 3, "reader": 2, "segments": [
    {"a": 1000, "b": 2000, "t": FAST},
    {"a": 3000, "b": 4000, "t": FAST},
    {"a": 5000, "b": 6000, "t": FAST},
    {"a": 7000, "b": 12000, "t": "yalla we are going in, watch the left"},
    {"a": 13000, "b": 14000, "t": FAST, "pin": 1},
]}, mt=1000100.0)
# night B and C: the prompt said verbatim on two different nights (slow
# enough to pass physics) + in C a one-off prompt-shaped REAL line and a
# prompt-shaped line said only once on the whole shelf
B = vid("Megabonk", "20250922_193612")
put(B, {"v": 3, "reader": 2, "segments": [
    {"a": 1000, "b": 20000, "t": PROMPT},
    {"a": 21000, "b": 23000, "t": "ok"},
]}, mt=1000200.0)
C = vid("Megabonk", "20250923_174056")
put(C, {"v": 3, "reader": 1, "segments": [
    {"a": 1000, "b": 20000, "t": PROMPT},
    {"a": 21000, "b": 28000, "t": REAL},
    {"a": 30000, "b": 45000, "t": ONCE},
]}, mt=1000300.0)
# night D: reader 4 wrote an impossible line - its own gates already
# re-asked it, so it is the re-ask's answer and stays
D = vid("Megabonk", "20260901_100000")
put(D, {"v": 3, "reader": 4, "segments": [
    {"a": 1000, "b": 2000, "t": FAST},
]}, mt=1000400.0)
# night E: the bare-title short arm, three times in one night
E = vid("FlyKnight", "20250706_002943")
put(E, {"v": 3, "reader": 2, "segments": [
    {"a": 1000, "b": 1700, "t": "Fly Knight."},
    {"a": 5000, "b": 6400, "t": "Fly Knight."},
    {"a": 9000, "b": 9700, "t": "Fly Knight."},
    {"a": 12000, "b": 15000, "t": "bro this boss is insane"},
]}, mt=1000500.0)
# night F: nothing to strike
F = vid("Celeste", "20250901_190600")
put(F, {"v": 3, "reader": 2, "segments": [
    {"a": 1000, "b": 4000, "t": "okay jump now"},
    {"a": 5000, "b": 8000, "t": "no no no"},
]}, mt=1000600.0)
# night G: one echo of the prompt among twenty real lines - struck, but
# not worth a re-telling of the chapters (the earned-retell rule)
G = vid("Megabonk", "20250924_201000")
put(G, {"v": 3, "reader": 2, "segments":
        [{"a": 1000 + i * 3000, "b": 3500 + i * 3000,
          "t": "line number %d about the run" % i} for i in range(20)]
        + [{"a": 70000, "b": 90000, "t": PROMPT}]}, mt=1000700.0)

mig()

print("\n--- night A: physics ---")
a = load(A)
segs = a["segments"]
check("three impossible lines struck", sum(1 for s in segs if s.get("nn")) == 3)
check("the real line stands", segs[3]["t"].startswith("yalla") and not segs[3].get("nn"))
check("the pinned impossible line is untouched",
      segs[4]["t"] == FAST and not segs[4].get("nn"))
check("each struck line keeps its original under `was`",
      all(s.get("was") == FAST for s in segs[:3]))
check("...reads [unintelligible] with a why naming the physics gate",
      all(s["t"] == "[unintelligible]" and "physics" in s.get("fxw", "")
          for s in segs[:3]))
check("the transcript is stamped eg=1", a.get("eg") == 1)
check("banked once, before the write",
      calls["bank"].count((A, "stt")) == 1)
rt = [r for r in calls["retell"] if r[0] == A]
check("the three struck seconds were sent for re-describe, refill=False",
      len(rt) == 1 and sorted(rt[0][1]) == [1.0, 3.0, 5.0] and rt[0][2] is False)

print("\n--- nights B and C: the echo law ---")
b, c = load(B), load(C)
check("the prompt said verbatim on two nights is struck on both",
      b["segments"][0].get("nn") == 1 and c["segments"][0].get("nn") == 1)
check("...with a why that counts the repeats",
      "3 times" in c["segments"][0].get("fxw", ""))
check("the prompt-shaped REAL line (sentry/sentence) said once STAYS",
      c["segments"][1]["t"] == REAL and not c["segments"][1].get("nn"))
check("a prompt-shaped line said only once on the whole shelf stays",
      c["segments"][2]["t"] == ONCE and not c["segments"][2].get("nn"))
check("'ok' stands", b["segments"][1]["t"] == "ok")

print("\n--- night D: a reader that had the gates is left alone ---")
d = load(D)
check("reader-4 impossible line untouched", d["segments"][0]["t"] == FAST)
check("...and its file was not rewritten (clock stands)",
      abs(os.path.getmtime(side(D)) - 1000400.0) < 1)
check("...and not stamped", "eg" not in d)

print("\n--- night E: the bare title, three times ---")
e = load(E)
check("all three bare-title lines struck",
      sum(1 for s in e["segments"] if s.get("nn")) == 3)
check("the real shout stands", e["segments"][3]["t"] == "bro this boss is insane")

print("\n--- night F: nothing to strike, nothing written ---")
check("Celeste's clock did not move",
      abs(os.path.getmtime(side(F)) - 1000600.0) < 1)
check("...and it is not stamped", "eg" not in load(F))
check("...and was never banked", (F, "stt") not in calls["bank"])

print("\n--- the tail ---")
check("one head-of-queue ask, for the newest touched night",
      len(calls["first"]) == 1)
check("_mig_quiet is back off", ns["_AI"].get("_mig_quiet") is False)
check("the log counts 3 + 1 + 1 + 3 + 1 = 9 strikes across 5 transcripts",
      any("struck 9 fabricated line(s) across 5 transcript(s)" in m
          for m in calls["log"]))
check("no file was skipped", ns["_MIG_SKIPPED"][0] == 0)

print("\n--- night G: struck, not re-told ---")
g = load(G)
check("the echoed prompt is struck among the twenty real lines",
      sum(1 for x in g["segments"] if x.get("nn")) == 1
      and g["segments"][-1].get("nn") == 1
      and all(not x.get("nn") for x in g["segments"][:20]))
check("...banked and stamped like any other",
      g.get("eg") == 1 and calls["bank"].count((G, "stt")) == 1)
check("...but ONE line in twenty-one earns no re-describe",
      not [r for r in calls["retell"] if r[0] == G])
check("...and the head-of-queue ask names a RE-TOLD night, never G",
      calls["first"] and calls["first"][0] != G
      and calls["first"][0] in (A, B, C, E))
check("the poisoned nights ARE re-told (A 3 of 5, B 1 of 2, C 1 of 3, "
      "E 3 of 4)",
      all([r for r in calls["retell"] if r[0] == p] for p in (A, B, C, E)))
check("the log counts the strikes and the nights re-told apart",
      any("struck 9 fabricated" in m and "on 4 night(s)" in m
          for m in calls["log"]))

print("\n--- the second pass ---")
before = {p: os.path.getmtime(side(p)) for p in (A, B, C, D, E, F, G)}
n_bank, n_ret = len(calls["bank"]), len(calls["retell"])
time.sleep(0.05)
mig()
check("nothing is banked or retold again",
      len(calls["bank"]) == n_bank and len(calls["retell"]) == n_ret)
check("no clock moved",
      all(abs(os.path.getmtime(side(p)) - before[p]) < 1
          for p in (A, B, C, D, E, F, G)))

print("\n--- the walk is registered ---")
check("'echo' is in _MIG_WALKS",
      re.search(r'^_MIG_WALKS\s*=\s*\(.*"echo".*\)', SRC, re.M) is not None)
check("...and wired into _shelf_migrations after the strike walk",
      re.search(r'\("strike", _aud_strike_migration,[^)]*\),\s*'
                r'\("echo", _echo_strike_migration,', SRC) is not None)
check("_transcribe_one builds its context through _asr_context_for",
      'env["LORE_ASR_CONTEXT"] = _asr_context_for(video_path)' in SRC)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
