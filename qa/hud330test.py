# -*- coding: utf-8 -*-
"""3.30 THE SCREEN READER - what the screen named, and the lane it rides.

Drives the REAL functions lifted out of lore.py and ai/ocr_worker.py by
name: the grid's seconds, the name folding (chrome falls away, spellings
fold, numbers never name), the owe gate and its cache, and the top-up
that puts the sidecar back with its own clock - and leaves it alone
when a senses pass rewrote it meanwhile. Then the wiring, read from the
source: the listening lane carries the grid (never while playing), a
grid-only visit does not evict the warm describer, the senses pass runs
the grid, the describer is told, the eye panel shows it."""
import ast
import io
import json
import os
import re
import sys
import tempfile
import textwrap
import time

ROOT = r"D:\Gate LLC"
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
WSRC = io.open(os.path.join(ROOT, "ai", "ocr_worker.py"),
               encoding="utf-8").read()
USRC = io.open(os.path.join(ROOT, "ui.html"), encoding="utf-8").read()

ok = bad = 0


def check(what, cond):
    global ok, bad
    if cond:
        ok += 1
        print("  OK  ", what)
    else:
        bad += 1
        print("  FAIL", what)


def extract(src, name, ns):
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                src.splitlines()[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name)


def const(src, name):
    m = re.search(r"^%s\s*=\s*([0-9.]+)" % re.escape(name), src, re.M)
    return float(m.group(1))


print("--- the grid's seconds ---")
wns = {}
grid_seconds = extract(WSRC, "grid_seconds", wns)
g = grid_seconds(60, 7920)
check("a 132-minute night at one a minute gives 132 frames, from 5s in",
      len(g) == 132 and g[0] == 5.0 and g[1] == 65.0)
check("no step, no duration, a clip shorter than ten seconds: no grid",
      grid_seconds(0, 100) == [] and grid_seconds(60, 0) == []
      and grid_seconds(60, 8) == [])
check("junk numbers fail open",
      grid_seconds("x", 5) == [] and grid_seconds(None, None) == [])
check("the worker's main takes the step and the duration",
      "def main(video, ffmpeg, dst, seconds, game=\"\", step=0.0, dur=0.0,"
      in WSRC)
check("...and its CLI passes argv[6] and argv[7] through",
      "float(sys.argv[6]) if len(sys.argv) > 6" in WSRC
      and "float(sys.argv[7]) if len(sys.argv) > 7" in WSRC)
check("the grid reads the CENTRE 16:9 of the picture",
      "crop=min(iw\\,ih*16/9)" in WSRC and '_MID, "g"' in WSRC)
check("the grid's frames feed the event patterns too",
      "mark(t, \" \".join(strs))" in WSRC)

print("\n--- what the screen named ---")
ns = {"os": os, "json": json, "re": re, "time": time,
      "_HUD_STOP": eval(re.search(r"^_HUD_STOP = frozenset\((\(.*?\))\)",
                                  SRC, re.M | re.S).group(1))}
_hud_names = extract(SRC, "_hud_names", ns)
STEP = 60.0
rows = []
for i in range(100):
    t = 5.0 + i * STEP
    strs = ["Wanderer", "Flask of Crimson Tears", "12:45", "HP 652"]
    if 40 <= i <= 56:
        strs.append("GODSKINAPOSTLE" if i % 4 == 0 else "Godskin Apostle")
    if i in (10, 11):
        strs.append("Level Up")
    if i == 70:
        strs.append("Rebirth")
    if 20 <= i <= 65:
        strs.append("Host of Fingers")
    rows.append([t, strs])
names = _hud_names({"step": STEP, "rows": rows})
byn = {d["n"]: d for d in names}
check("the boss bar that stood for 17 frames is the first name",
      names and names[0]["n"] == "Godskin Apostle")
check("...spanning its first frame to a step past its last, 17 frames",
      names and names[0]["a"] == int(5 + 40 * STEP)
      and names[0]["b"] == int(5 + 56 * STEP + STEP) and names[0]["k"] == 17)
check("the two spellings folded into the most-read one",
      "GODSKINAPOSTLE" not in byn)
check("a menu open across two frames is a name",
      "Level Up" in byn and byn["Level Up"]["k"] == 2)
check("his own tag on every frame is chrome and falls away",
      "Wanderer" not in byn)
check("the flask slot on every frame is chrome too",
      "Flask of Crimson Tears" not in byn)
check("a string seen on one frame only never names",
      "Rebirth" not in byn)
check("numbers and counters never name",
      not any(d["n"] in ("12:45", "HP 652") for d in names))
check("a label standing on 46%% of a long night is chrome (a third rule)",
      "Host of Fingers" not in byn)
short = [[5.0 + i * STEP, ["Wanderer"] + (["Margit"] if 4 <= i <= 11 else [])]
         for i in range(20)]
sn = _hud_names({"step": STEP, "rows": short})
check("on a short night the chrome line is half, so an 8-of-20 boss stays",
      [d["n"] for d in sn] == ["Margit"])
check("a string that is mostly symbols never names (a misread icon)",
      not [d for d in _hud_names({"step": STEP, "rows": [
          [5.0 + i * STEP, ["Wanderer", "?+@ Hide uI", "Margit"]]
          for i in range(12)]}) if "Hide" in d["n"]])
check("the recorder's own overlay never names",
      [d["n"] for d in _hud_names({"step": STEP, "rows": [
          [5.0 + i * STEP, ["Video capture paused", "AltTabbed"]
           + (["Margit"] if 2 <= i <= 6 else [])]
          for i in range(12)]})] == ["Margit"])
check("a two-word boss over eight frames outranks a one-word label over "
      "eleven", [d["n"] for d in _hud_names({"step": STEP, "rows": [
          [5.0 + i * STEP, ["Wanderer"] + (["Godskin Apostle"] if 2 <= i <= 9
                                        else []) + (["Reset"] if i < 11
                                                    else [])]
          for i in range(40)]})][:2] == ["Godskin Apostle", "Reset"])
check("fewer than three frames: nothing named",
      _hud_names({"step": STEP, "rows": rows[:2]}) == [])
check("junk rows fail open", _hud_names({"rows": [None, 5, ["x"]]}) == []
      and _hud_names(None) == [])
ar = [[5.0 + i * STEP, ["Wanderer", "ملك الرماد" if 3 <= i <= 6 else "x"]]
      for i in range(12)]
check("Arabic names fold on their letters like Latin ones",
      [d["n"] for d in _hud_names({"step": STEP, "rows": ar})]
      == ["ملك الرماد"])

print("\n--- the owe gate and the top-up ---")
tmp = tempfile.mkdtemp(prefix="lore_hud330_")
LIB = os.path.join(tmp, "Records")
TH = os.path.join(LIB, ".lore_thumbs")
os.makedirs(os.path.join(LIB, "EldenRing", "Videos"))
os.makedirs(TH)
V = os.path.join(LIB, "EldenRing", "Videos", "ELDENRING_20260418_165025.mp4")
io.open(V, "wb").write(b"\0" * 200000)
os.utime(V, (1000000.0, 1000000.0))


def side(p, k):
    return os.path.join(TH, os.path.splitext(os.path.basename(p))[0]
                        + "." + k + ".json")


def put(p, k, doc, mt):
    io.open(side(p, k), "w", encoding="utf-8").write(
        json.dumps(doc, ensure_ascii=False))
    os.utime(side(p, k), (mt, mt))


runs = []
logs = []
FAKE_HUD = {"step": 60.0, "rows": [[5.0 + i * 60, ["Wanderer"]
                                    + (["Margit"] if 2 <= i <= 6 else [])]
                                   for i in range(12)]}


def fake_run(cmd, timeout, flags):
    runs.append(list(cmd))
    oj = cmd[4]
    io.open(oj, "w", encoding="utf-8").write(json.dumps(
        {"v": 2, "events": [], "hud": FAKE_HUD}))
    if ns.get("_meanwhile"):
        ns["_meanwhile"]()
    return 0, b"", b""


ns.update({
    "SETTINGS": {"output_dir": LIB, "ffmpeg_path": "ffmpeg"},
    "_AI": {"abort": False, "job_secs": 0.0},
    "_here": lambda: ROOT,
    "_senses_paths": lambda: ("python", "senses_worker.py"),
    "_ai_sidecar": side,
    "_probe_duration": lambda p: 725.0,
    "_display_name": lambda x: x, "_parse_clip_name": lambda x: "Elden Ring",
    "_work_dir": lambda: tmp,
    "_source_busy_add": lambda p: None, "_source_busy_done": lambda p: None,
    "_ai_run": fake_run,
    "_atomic_write_json": lambda p, d: io.open(
        p, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False)),
    "log": lambda m: logs.append(m),
    "_HUD_OWE_CACHE": {},
    "_OUT_OWE_CACHE": {},        # 3.32: the grid top-up pops it too
    "_HUD_STEP": const(SRC, "_HUD_STEP"),
    "subprocess": __import__("subprocess"),
    "threading": __import__("threading"),
})
for name in ("_hud_paths", "_hud_owing", "_hud_topup_one"):
    extract(SRC, name, ns)
_hud_owing, _hud_topup_one = ns["_hud_owing"], ns["_hud_topup_one"]

check("the reader's paths resolve on this machine",
      ns["_hud_paths"]() is not None)
check("no senses yet: nothing owed (the senses pass brings the grid)",
      _hud_owing(V) is False)
put(V, "sns", {"v": 1, "events": [], "names": {"1": "Faris"}}, mt=999000.0)
check("senses older than the video: not owed here (owed whole elsewhere)",
      _hud_owing(V) is False)
put(V, "sns", {"v": 1, "events": [], "names": {"1": "Faris"}}, mt=1000500.0)
check("a finished senses sidecar without the grid owes it",
      _hud_owing(V) is True)
put(V, "sns", {"v": 1, "failed": True, "tries": 1}, mt=1000500.0)
check("a failed senses sidecar is the senses' debt, not the grid's",
      _hud_owing(V) is False)
put(V, "sns", {"v": 1, "events": [], "names": {"1": "Faris"}}, mt=1000500.0)
check("...and the cache follows the file's size, not just its clock",
      _hud_owing(V) is True)

st0 = os.stat(side(V, "sns"))
got = _hud_topup_one(V)
d = json.load(io.open(side(V, "sns"), encoding="utf-8"))
st1 = os.stat(side(V, "sns"))
check("the top-up ran the reader once, grid only (no targeted seconds)",
      len(runs) == 1 and runs[0][5] == "" and runs[0][7] == "60.0"
      and runs[0][8] == "725.0")
check("...and returned True", got is True)
check("the grid landed on the sidecar", d.get("hud") == FAKE_HUD)
check("...with the names folded beside it",
      [x["n"] for x in d.get("screen") or []] == ["Margit"])
check("the voices' names are untouched", d.get("names") == {"1": "Faris"})
check("THE CLOCK STAYS: the sidecar wears the mtime it had",
      abs(st1.st_mtime - st0.st_mtime) < 0.01)
check("nothing owed any more", _hud_owing(V) is False)
check("the log names what the screen named",
      any("screen reader" in m and "Margit" in m for m in logs))
check("a second visit is a no-op that reads nothing", _hud_topup_one(V)
      is True and len(runs) == 1)
check("no scratch file left behind",
      not [f for f in os.listdir(tmp) if f.startswith("hud_")])

# the race: a senses pass rewrites the sidecar while the grid is read
put(V, "sns", {"v": 1, "events": [], "names": {"1": "Faris"}}, mt=1000500.0)
ns["_HUD_OWE_CACHE"].clear()


def meanwhile():
    put(V, "sns", {"v": 1, "events": [{"t": 3}], "names": {"1": "Sultan"},
                   "hud": {"step": 60.0, "rows": []}, "screen": []},
        mt=1000900.0)


ns["_meanwhile"] = meanwhile
got = _hud_topup_one(V)
d = json.load(io.open(side(V, "sns"), encoding="utf-8"))
check("a sidecar rewritten meanwhile is left exactly as the new pass "
      "wrote it", got is True and d.get("names") == {"1": "Sultan"}
      and d.get("screen") == [] and d.get("events") == [{"t": 3}])
ns["_meanwhile"] = None

# a reader that falls over is written down, not asked again every beat
put(V, "sns", {"v": 1, "events": []}, mt=1000500.0)
ns["_HUD_OWE_CACHE"].clear()


def bad_run(cmd, timeout, flags):
    return 1, b"", b"OCR_WORKER_FAILED boom"


ns["_ai_run"] = bad_run
got = _hud_topup_one(V)
d = json.load(io.open(side(V, "sns"), encoding="utf-8"))
check("a failed read is written as an empty grid with its why",
      got is True and d.get("hud", {}).get("rows") == []
      and "boom" in d.get("hud", {}).get("failed", ""))
check("...so it is not owed again", _hud_owing(V) is False)

print("\n--- the wiring ---")
check("the grid is dispatched only after the walk found nothing louder "
      "(one job slot for every lane), never while playing",
      "THE SCREEN READER FILLS THE QUIET" in SRC
      and '_AI["tail"] = ("screen", p)' in SRC
      and SRC.index("THE SCREEN READER FILLS THE QUIET")
      > SRC.index("if _AI.get(\"focus\") == p:\n            try:\n"
                  "                _owes_more = (")
      and "if do_hl and not playing:\n        for p in vids:" in SRC)
check("the focus is never held for a grid",
      "or (not playing and _hud_owing(p))" not in SRC)
check("the tail pass keeps the walk's own skips (skipped, badge, failed, "
      "veto)", SRC.count("if _ai_skipped_recently(p) or "
                         "_queued_finish_badge(p):") == 1)
check("a screen-only visit skips the ears and keeps the describer warm",
      '_tail = _AI.pop("tail", None)' in SRC
      and 'screen_only = (tail == "screen")' in SRC
      and "if not tail:\n                # a tail visit never "
          "touches the card" in SRC)
# 3.32 ONE TAIL, ONE KEY: the screen visit is owed by the grid OR the
# outcomes, and tops the grid up before the ends it predicted
check("the tail owes the screen visit for the grid or the outcomes",
      "if (_hud_owing(p) or _outcome_owing(p)) \\\n"
      "                    and _ai_sidecar_fresh(p, \"hl\"):" in SRC
      and "hud_only" not in SRC)
check("...and the screen visit reads the grid first, then the outcomes",
      0 < SRC.index("ok = _hud_topup_one(path)")
      < SRC.index("if ok and not _AI[\"abort\"] and _outcome_owing(path):\n"
                  "                        ok = _outcome_topup_one(path)"))
check("a redo of the ears tops the grid up when owed",
      "if ok and not _AI[\"abort\"] and _hud_owing(path):\n"
      "                        ok = _hud_topup_one(path)" in SRC)
check("the senses pass runs the grid in the same worker call",
      'f"{_HUD_STEP:.1f}", f"{float(dur or 0):.1f}"]' in SRC
      and 'sns["screen"] = _hud_names(_hg)' in SRC)
check("the describer is told what the screen printed in each window",
      "The SCREEN itself printed these names in this window" in SRC
      and 'x.get("screen") or []' in SRC or "_sd0.get(\"screen\")" in SRC)
check("the eye's bridge carries the screen names",
      '"eye": True, "screen": screen, "black": black}' in SRC
      and '"complete": True, "eye": False, "screen": screen,' in SRC)
check("the eye panel lists them in time order",
      "'The screen named'" in USRC and "vis.eye!==false" in USRC
      and "scr.map(s=>s.n+'@'+s.a+'-'+s.b)" in USRC)
check("_HUD_STEP is one frame a minute", const(SRC, "_HUD_STEP") == 60.0)
check("a grid that stumbles is a soft strike, not a failed night",
      'The screen reader stumbled on' in SRC
      and SRC.index('_AI["soft_fail"] = True\n        log(f"The screen reader '
                    'stumbled') > 0)
check("a screen visit names itself 'the screen' on the Working page",
      '_AI["busy"] = (kind, {"screen": "the screen",' in SRC
      and '+ " \\u00b7 " + os.path.basename(path))' in SRC)
check("a tail visit does not teach the listening lane its pace",
      'if ok and not _AI["abort"] and not tail:' in SRC)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
