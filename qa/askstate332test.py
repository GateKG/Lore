# -*- coding: utf-8 -*-
"""3.32 drop D - THE FINISHED ASK THAT CAME BACK FROM THE GRAVE.

ai_state.json is written only when _AI['_qdirty'] is set; a finished
ask's force_ran grew in RAM alone, so the file kept the head row with
ran=[] and the next boot redid the whole night from scratch, archiving
the finished review into the attic (measured 5 Sep 2026). Drives the
REAL _ai_state_save / _ai_state_load lifted out of lore.py by name, on
a scratch data dir: the head row carries force_ran; force None writes
the bare queue; a row for a file that is gone falls out on load; ran
comes back as a list of str; the round trip a finished ask now
survives. Then the source: the three dirt marks at their anchors
(regex on the exact lines), the worker-finally mark within three lines
of the force_ran add, and the two writers that spend the dirt. Nothing
under D:\\Records is touched; no sidecar is written."""
import ast
import io
import json
import os
import re
import shutil
import sys
import tempfile
import textwrap
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
TREE = ast.parse(SRC)

ok = bad = 0


def check(what, cond):
    global ok, bad
    if cond:
        ok += 1
        print("  OK  ", what)
    else:
        bad += 1
        print("  FAIL", what)


def extract(name, ns):
    for node in TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                SRC.splitlines()[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name)


def body_of(name):
    for node in TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(SRC.splitlines()[node.lineno - 1:node.end_lineno])
    raise AssertionError(name)


tmp = tempfile.mkdtemp(prefix="lore_askstate_")
LOGS = []
ns = {"os": os, "json": json, "time": time, "threading": threading,
      "_data_dir": lambda: tmp, "_AI_FORCE_LOCK": threading.RLock(),
      "_AFKAI": {}, "_AI": {}, "log": lambda m: LOGS.append(m),
      "_afk_ai_true_held": lambda: {}}
_ai_state_path = extract("_ai_state_path", ns)
_ai_state_save = extract("_ai_state_save", ns)
_ai_state_load = extract("_ai_state_load", ns)
AI = ns["_AI"]


def read():
    return json.load(io.open(_ai_state_path(), encoding="utf-8"))


try:
    vid = os.path.join(tmp, "hearthstone_20260905_195941.mp4")
    other = os.path.join(tmp, "rocketleague_20260904_233625.mp4")
    for v in (vid, other):
        io.open(v, "wb").write(b"\0" * 64)
    gone = os.path.join(tmp, "gone_20260101_000000.mp4")

    # -----------------------------------------------------------------
    print("--- the writer ---")
    AI.clear()
    AI.update({"force": vid, "force_want": "all", "force_redo": True,
               "force_ran": {"listening", "hearing"},
               "force_queue": [(other, "sound", False, [])]})
    _ai_state_save()
    d = read()
    check("the head row is the ask in hand, with what already ran",
          d["queue"][0] == [vid, "all", True, ["hearing", "listening"]])
    check("...the line follows it, ran empty as it was",
          d["queue"][1] == [other, "sound", False, []]
          and len(d["queue"]) == 2 and d["held"] == {})
    AI["force_ran"].add("thinking")
    _ai_state_save()
    check("a kind that lands later is in the file at the next write",
          read()["queue"][0][3] == ["hearing", "listening", "thinking"])
    AI.update({"force": None, "force_want": None, "force_redo": False,
               "force_ran": set(), "force_queue": []})
    _ai_state_save()
    check("force None and nothing queued: queue []", read()["queue"] == [])
    AI["force_ran"] = None
    AI["force"] = other
    _ai_state_save()
    check("force_ran None (never set) writes as an empty list",
          read()["queue"] == [[other, "all", False, []]])

    # -----------------------------------------------------------------
    print("\n--- the reader ---")
    io.open(_ai_state_path(), "w", encoding="utf-8").write(json.dumps(
        {"queue": [[gone, "all", True, ["listening"]],
                   [vid, "all", True, ["hearing", 7]],
                   [other]],
         "held": {"thinking": True}}))
    AI.clear()
    AI["force_queue"] = [("stale", "all", False, [])]
    del LOGS[:]
    _ai_state_load()
    q = AI["force_queue"]
    check("a row for a file that is gone falls out; the rest come back "
          "in order", [r[0] for r in q] == [vid, other])
    check("ran comes back as a list of str, redo as a bool",
          q[0][3] == ["hearing", "7"] and q[0][2] is True
          and all(isinstance(x, str) for x in q[0][3]))
    check("a bare row defaults: want 'all', redo False, ran []",
          q[1] == (other, "all", False, []))
    check("the line announces itself; a hold does not come back (it dies "
          "with the tome) but says so",
          any("came back with 2 item(s)" in m for m in LOGS)
          and AI["held"]["thinking"] is False
          and any("awake again" in m for m in LOGS))
    io.open(_ai_state_path(), "w", encoding="utf-8").write("{not json")
    AI["force_queue"] = [("kept", "all", False, [])]
    _ai_state_load()
    check("an unreadable file leaves the live line alone",
          AI["force_queue"] == [("kept", "all", False, [])])

    # -----------------------------------------------------------------
    print("\n--- the round trip a finished ask now survives ---")
    AI.clear()
    AI.update({"force": vid, "force_want": "all", "force_redo": True,
               "force_ran": set(), "force_queue": []})
    _ai_state_save()                        # the pickup's write: ran=[]
    for kind in ("listening", "hearing", "thinking"):
        AI["force_ran"].add(kind)
        AI["_qdirty"] = True                # the worker's finally (drop D)
        if AI.pop("_qdirty", None):         # the next spawn / beat end
            _ai_state_save()
    check("after the last kind lands the file's head row carries all "
          "three - the boot's first beat sees a satisfied ask, not a redo",
          read()["queue"] == [[vid, "all", True,
                               ["hearing", "listening", "thinking"]]])
    AI.clear()
    _ai_state_load()
    check("...and the reader hands the line back with that memory",
          AI["force_queue"] == [(vid, "all", True,
                                 ["hearing", "listening", "thinking"])])
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ---------------------------------------------------------------------------
print("\n--- the source: the dirt marks ---")
lines = SRC.splitlines()
i_add = [i for i, ln in enumerate(lines)
         if 'force_ran", set()).add(kind)' in ln]
check("the worker's finally adds the kind to force_ran once",
      len(i_add) == 1)
i_add = i_add[0] if i_add else 0
check("...and marks the line dirty within three lines of it",
      any('_AI["_qdirty"] = True' in ln
          for ln in lines[i_add + 1:i_add + 4]))
check("the satisfied branch marks dirt before it takes the next item",
      re.search(r'^            _AI\["force"\] = None            # satisfied, '
                r'or gone\n            _AI\["force_want"\] = None\n'
                r'            _AI\["force_redo"\] = False\n'
                r'            _AI\["_qdirty"\] = True[^\n]*\n'
                r'            continue', SRC, re.M) is not None)
check("the refused branch marks dirt before it takes the next item",
      re.search(r'^            _AI\["force"\] = None            # it refused '
                r'this exact file before\n'
                r'            _AI\["force_want"\] = None\n'
                r'            _AI\["force_redo"\] = False\n'
                r'            _AI\["_qdirty"\] = True[^\n]*\n'
                r'            log\(f"Cannot read', SRC, re.M) is not None)
check("the held requeue marks dirt before it breaks for Resume",
      re.search(r'^                    _AI\["force_queue"\] = \(\[\(fp, want, '
                r'redo, sorted\(ran\)\)\]\n(?:.*\n){5}'
                r'                _AI\["_qdirty"\] = True[^\n]*\n'
                r'                break$', SRC, re.M) is not None)
check("the dirt is spent by a writer at the next spawn and at the beat's "
      "end (the held requeue's break lands on the second)",
      SRC.count('if _AI.pop("_qdirty", None):\n            _ai_state_save()') >= 1
      and SRC.count('if _AI.pop("_qdirty", None):\n        _ai_state_save()') >= 1)
sv = body_of("_ai_state_save")
check("the writer takes force_ran into the head row, sorted",
      'sorted(_AI.get("force_ran") or set())' in sv)
check("the reader is untouched by this drop: a restored row whose ran "
      "covers what it owes is satisfied on its first beat",
      "force_ran" not in body_of("_ai_state_load")
      and '[str(x) for x in it[3]] if len(it) > 3 else []' in body_of("_ai_state_load"))
check("no sidecar leaves this drop: the marks touch _AI only",
      SRC.count('_AI["_qdirty"] = True') >= 7
      and "_atomic_write_json" not in sv and "_ai_sidecar" not in sv)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
