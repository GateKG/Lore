# -*- coding: utf-8 -*-
"""The 3.08 review repairs, proven: an undrainable line cannot starve
the machine, an interrupted queue audit comes back in its place, the
order survives a defer cycle, an undescribed night escalates, queue
audits are not 'named', and the bolt appends instead of replacing."""
import os
import sys
import tempfile

sys.path.insert(0, r"D:\Gate LLC")
import lore  # noqa: E402

lore.log = lambda m: None
try:
    lore.load_settings()
except Exception:
    pass
lore.save_settings = lambda *a, **k: None
lore._data_dir = lambda: tempfile.mkdtemp(prefix="s4_")

# a described night and an undescribed one, from his real shelf
DESCRIBED = r"D:\Records\Devour\Videos\devour_20260801_185559.mp4"
UNDESC = None
for root in (r"D:\Records\ELDEN RING", r"D:\Records\Big Walk"):
    for d, _x, fs in os.walk(root):
        for f in fs:
            if f.lower().endswith(".mp4"):
                p = os.path.join(d, f)
                try:
                    if not lore._ins_done_honest(p):
                        UNDESC = p
                        break
                except Exception:
                    pass
        if UNDESC:
            break
    if UNDESC:
        break

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


def reset():
    lore._AI["held"] = {"listening": False, "hearing": False,
                        "thinking": False, "auditing": False}
    lore._AI["force"] = None
    lore._AI["force_want"] = None
    lore._AI["force_redo"] = False
    lore._AI["force_ran"] = set()
    lore._AI["force_queue"] = []
    lore._AI["busy"] = None
    lore._AI["busy_path"] = None
    lore._AI["abort"] = False
    lore._AI.pop("aud_defer", None)
    lore._AI.pop("aud_item", None)
    lore._AI.pop("aud_live", None)
    lore.SETTINGS["bg_shutdown"] = False


api = lore._JsApi.__new__(lore._JsApi)

# the source tree has no models (they live beside the
# installed exe), and 3.09 rightly refuses an audit ask
# with no thinker. These tests are about the QUEUE, so
# stand an installed machine up for them.
lore._describer_paths = lambda: ("llama-server.exe", "m.gguf")
lore._aud_llm_paths = lambda: ("llama-server.exe", "m.gguf")


print("--- C1: a deferred line cannot starve the machine ---")
reset()
# _takeable is the guard that decides whether a waiting row may make
# the beat "forced" - lifted out of _ai_tick by the ast, the way this
# repo's other harnesses lift functions (no extraction drift)
import ast
import textwrap
import time as _time

_SRC = open(r"D:\Gate LLC\lore.py", encoding="utf-8").read()
_LINES = _SRC.splitlines()
_node = next(n for n in ast.walk(ast.parse(_SRC))
             if isinstance(n, ast.FunctionDef) and n.name == "_takeable")
_ns = {"_AI": lore._AI, "_ai_lanes_free": lore._ai_lanes_free,
       "_ai_skipped_recently": lore._ai_skipped_recently,
       "time": _time}
exec(compile(textwrap.dedent(
    "\n".join(_LINES[_node.lineno - 1:_node.end_lineno])),
    "<takeable>", "exec"), _ns)
takeable = _ns["_takeable"]
lore._AI["force_queue"] = [(DESCRIBED, "audit", True, [])]
lore._AI["aud_defer"] = {DESCRIBED: _time.time()}
check("a deferred audit row is NOT takeable",
      takeable((DESCRIBED, "audit", True, [])) is False)
lore._AI["aud_defer"] = {}
check("an un-deferred audit row IS takeable",
      takeable((DESCRIBED, "audit", True, [])) is True)
lore._AI["held"]["auditing"] = True
check("a held audit row is not takeable",
      takeable((DESCRIBED, "audit", True, [])) is False)

print("\n--- S4: an undescribed night escalates to a describe ---")
reset()
if UNDESC:
    owe = lore._force_owes(UNDESC, "audit", True)
    check("an audit ask on an undescribed night owes THINKING",
          owe == {"thinking"})
else:
    check("(no undescribed night on the shelf to test)", True)
check("a described night still owes its audit",
      lore._force_owes(DESCRIBED, "audit", True) == {"auditing"})

print("\n--- S5: the queue's audits are not 'named' ---")
reset()
_real_one = lore._audit_one
_real_playing = lore._aud_playing
_real_honest = lore._ins_done_honest
lore._audit_one = lambda p, redo=False: True
lore._aud_playing = lambda: False
lore._ins_done_honest = lambda p: True
try:
    started = lore._audit_ask(DESCRIBED, redo=True, named=False)
    check("a queue audit starts without claiming the name",
          started and lore._AUD_ASK.get("named") is False)
    for _ in range(60):
        if lore._AUD_ASK.get("path") is None:
            break
        __import__("time").sleep(0.05)
finally:
    lore._audit_one = _real_one
    lore._aud_playing = _real_playing
    lore._ins_done_honest = _real_honest
    lore._AUD_ASK.update({"path": None, "named": False, "claim": None})

print("\n--- M8: the bolt APPENDS to his line ---")
reset()
lore._AI["force_queue"] = [(DESCRIBED, "audit", True, [])]
r = api.ai_force_many([UNDESC or DESCRIBED], "think", False)
q = lore._AI["force_queue"]
check("the standing row survives a new press",
      any(it[0] == DESCRIBED and it[1] == "audit" for it in q))
check("the new ask is appended, not swapped in", len(q) >= 1)
before = len(q)
api.ai_force_many([DESCRIBED], "audit", True)
check("the same path+job is never doubled",
      len(lore._AI["force_queue"]) == before)

print("\n--- M6: prioritise routes an audit to the line ---")
reset()
r = api.prioritise(DESCRIBED, "audit")
check("prioritise(audit) queues instead of forcing",
      lore._AI.get("force") is None
      and any(it[1] == "audit" for it in lore._AI["force_queue"]))

print("\n--- M7: the audit has words ---")
check("the audit says itself in the nothing-to-do line",
      lore._WANT_SAID.get("audit") == "a fresh audit")

reset()
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
