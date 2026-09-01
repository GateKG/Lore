# -*- coding: utf-8 -*-
"""The review-314 criticals, each proven dead:
  C1 an unstartable row must not freeze the shelf
  C2 an automatic repair must never behave like a by-name ask
  C3 "Audit only" on an undescribed night must queue a DESCRIBE
  C4 the by-name refusal must keep the promise it makes
  S5 focus is let go only when the night owes nothing
  S6 an audit cannot claim to cover a review it tore open
  S7 an empty night's marks stay quiet
"""
import ast
import io
import json
import os
import sys
import tempfile
import textwrap
import time

sys.path.insert(0, r"D:\Gate LLC")
import lore  # noqa: E402

SAID = []
lore.log = lambda m: SAID.append(m)
lore.load_settings()
lore.save_settings = lambda *a, **k: None

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


SRC = io.open(r"D:\Gate LLC\lore.py", encoding="utf-8").read()
TD = tempfile.mkdtemp(prefix="frz_")
lore._ai_sidecar = (lambda p, k, _t=TD:
                    os.path.join(_t, os.path.basename(p) + "." + k
                                 + ".json"))


def night(name, ins=None, aud=None, covers=False):
    p = os.path.join(TD, name + ".mp4")
    with io.open(p, "wb") as fh:
        fh.write(b"x")
    if ins is not None:
        with io.open(lore._ai_sidecar(p, "ins"), "w",
                     encoding="utf-8") as fh:
            fh.write(json.dumps(ins))
    if aud is not None:
        if covers:
            aud = dict(aud)
            aud["src"] = {"ins": round(os.path.getmtime(
                lore._ai_sidecar(p, "ins")), 1)}
        with io.open(lore._ai_sidecar(p, "aud"), "w",
                     encoding="utf-8") as fh:
            fh.write(json.dumps(aud))
    return p


print("--- C1: the sweep asks whether anything can START ---")
node = next(n for n in ast.walk(ast.parse(SRC))
            if isinstance(n, ast.FunctionDef) and n.name == "_takeable")
ns = {"_AI": lore._AI, "_ai_lanes_free": lore._ai_lanes_free,
      "_ai_skipped_recently": lore._ai_skipped_recently,
      "time": time}
exec(compile(textwrap.dedent("\n".join(
    SRC.splitlines()[node.lineno - 1:node.end_lineno])), "<t>", "exec"),
    ns)
takeable = ns["_takeable"]
lore._AI["held"] = {"listening": False, "hearing": False,
                    "thinking": False, "auditing": False}
VID = night("frozen", ins={"complete": False})
lore._AI["aud_defer"] = {VID: time.time()}
check("a deferred audit row is not takeable",
      takeable((VID, "audit", True, [])) is False)
check("and the SWEEP now bails on takeability, not existence",
      'any(\n                _takeable(it) for it in (_AI.get("force_queue")'
      in SRC or "any(\n                _takeable(it)" in SRC)
check("the old existence-only bail is gone",
      'if _AI.get("force") or _AI.get("force_queue"):\n            return'
      not in SRC)

print("\n--- C2: the repair steers the sweep, never the forced line ---")
lore._AI["force_queue"] = []
lore._AI["focus"] = None
lore._AI["failed"] = {VID: 123}
lore._ai_ask_first(VID, "think", "because the audit re-told it")
check("nothing was put on the FORCED line (no gate is jumped)",
      lore._AI["force_queue"] == [])
check("the night is at the head of the sweep's walk instead",
      lore._AI["focus"] == VID)
check("and its give-up memo was cleared", VID not in lore._AI["failed"])
check("it says so plainly",
      any("head of the queue" in m for m in SAID))

print("\n--- C3: Audit-only on undescribed nights becomes a describe ---")
api = lore._JsApi.__new__(lore._JsApi)
api._safe_path = lambda p: p
und = night("undesc", ins={"complete": False, "windows": {"0": {}}})
lore._AI["force_queue"] = []
lore._AI["held"] = {"listening": False, "hearing": False,
                    "thinking": False, "auditing": False}
_rp = lore._describer_paths
_ap = lore._aud_llm_paths
lore._describer_paths = lambda: ("x", "y")
lore._aud_llm_paths = lambda: ("x", "y")
try:
    r = api.ai_force_many([und], "audit", True)
    q = lore._AI.get("force_queue") or []
    check("the ask is accepted", bool(r.get("ok")))
    check("and queued as a DESCRIBE, which is what it owes",
          bool(q) and q[0][1] == "think")
    check("so nothing unstartable is ever put on the line",
          all(it[1] != "audit" for it in q))
finally:
    lore._describer_paths = _rp
    lore._aud_llm_paths = _ap
    lore._AI["force_queue"] = []

print("\n--- C4: the by-name refusal keeps its promise ---")
check("the audit door escalates instead of only refusing",
      'if why and "description must exist first" in why:' in SRC)

print("\n--- S5: focus is let go only when nothing is owed ---")
check("the release now weighs what the night still owes",
      "_owes_more" in SRC and "_aud_owing_swept(p)" in SRC)
check("and no longer fires merely because a job is gated",
      "# NOTHING LEFT THIS WALK CAN START on this night - let it go,"
      not in SRC)

print("\n--- S6: an audit cannot cover a review it tore open ---")
torn = night("torn",
             ins={"complete": False, "chapters": [{"t": 0}],
                  "windows": {"0": {}}},
             aud={"complete": True, "v": lore._AUD_V}, covers=True)
check("clocks match, but the review is in pieces -> NOT covered",
      lore._aud_covers_now(torn) is False)
whole = night("whole",
              ins={"complete": True, "chapters": [{"t": 0}]},
              aud={"complete": True, "v": lore._AUD_V}, covers=True)
check("a whole review with a matching clock IS covered",
      lore._aud_covers_now(whole) is True)

print("\n--- S7: an empty night says nothing, on both marks ---")
empty = night("empty", ins={"complete": True, "empty": True},
              aud={"complete": True, "v": lore._AUD_V}, covers=True)
f = api.have_flags([empty, whole, torn])
check("empty: no description mark", f[empty]["ins_lvl"] == 0)
check("empty: and no audit mark either (they cannot contradict)",
      f[empty]["aud_lvl"] == 0)
check("whole: both GOLD",
      f[whole]["ins_lvl"] == 2 and f[whole]["aud_lvl"] == 2)
check("torn: SILVER, and it says the audit read an older description",
      f[torn]["ins_lvl"] == 1 and f[torn]["aud_lvl"] == 1)

print("\n--- S8: one meaning of 'audited' ---")
check("the tally asks the same question the shelf does",
      "_aud_covers_now(video_path, d)" in SRC)
check("torn night: the tally does NOT call it audited",
      lore._aud_done_current(torn) is False)
check("whole night: it does", lore._aud_done_current(whole) is True)

lore._AI["focus"] = None
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
