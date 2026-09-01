# -*- coding: utf-8 -*-
"""3.23: the Codex-triage ship set, proven.

Functional wherever the function is reachable; AST-extraction for the
nested describer helpers; source-order assertions only where a call
would need the model."""
import ast
import io
import sys
import textwrap
import re as _re

sys.path.insert(0, r"D:\Gate LLC")
import lore  # noqa: E402

SAID = []
lore.log = lambda m: SAID.append(m)
lore.load_settings()

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


SRC = io.open(r"D:\Gate LLC\lore.py", encoding="utf-8").read()

print("--- A1: the wallet fails CLOSED ---")
_orig = lore.SETTINGS.get("ai_budget_cents")
try:
    for raw, want in ((0, 0.0), (0.0, 0.0), ("abc", 500.0), (-5, 500.0),
                      (None, 500.0), (True, 500.0), (250, 250.0)):
        lore.SETTINGS["ai_budget_cents"] = raw
        SAID[:] = []
        got = lore._ai_budget()
        check("budget %r -> %s" % (raw, want), got == want)
    lore._AI.pop("_budget_said", None)
    lore.SETTINGS["ai_budget_cents"] = "abc"
    SAID[:] = []
    lore._ai_budget()
    check("a broken hand-edit says so out loud",
          any("not a usable ceiling" in m for m in SAID))
    lore.SETTINGS["ai_budget_cents"] = 0
    ok0, why0 = lore._ai_spend_room("fast")
    check("budget 0 REFUSES (used to mean unlimited)", ok0 is False)
    check("...and the reason names the real setting",
          "ai_budget_cents" in why0)
    lore.SETTINGS["ai_budget_cents"] = 500
    _sp = lore.SETTINGS.get("ai_spent_cents")
    lore.SETTINGS["ai_spent_cents"] = 499.9
    ok1, why1 = lore._ai_spend_room("fast")
    check("over the ceiling still refuses", ok1 is False)
    lore.SETTINGS["ai_spent_cents"] = 0.0
    ok2, _ = lore._ai_spend_room("fast")
    check("room under the ceiling still allows", ok2 is True)
    lore.SETTINGS["ai_spent_cents"] = _sp
    lore._AI.pop("_budget_said", None)
    for raw in (float("inf"), "1e999", float("nan")):
        lore.SETTINGS["ai_budget_cents"] = raw
        check("budget %r is not a ceiling (finite only)" % raw,
              lore._ai_budget() == 500.0)
    lore._AI.pop("_budget_said", None)
    lore.SETTINGS["ai_budget_cents"] = "abc"
    SAID[:] = []
    lore._ai_budget()
    lore._ai_budget()
    lore._ai_budget()
    check("a bad value is announced ONCE, not per poll",
          sum(1 for m in SAID if "not a usable ceiling" in m) == 1)
    lore._AI.pop("_budget_said", None)
finally:
    lore.SETTINGS["ai_budget_cents"] = _orig

check("the dead 'deep' key lookup is gone",
      'CLAUDE_MODELS.get("deep")' not in SRC)
check("cost kind is classified by the actual model",
      'if (model or _claude_model()) == CLAUDE_MODELS["fast"]' in SRC)

print("\n--- A5: grounded time beats invented time ---")
_blk = SRC.rsplit('for h in (data.get("hits") or [])[:20]:', 1)[1][:2200]
check("ask_library grounds in the transcript, and ONLY there",
      "_moment_of(path, why, q)" in _blk
      and 'h.get("t")' not in _blk)
check("...and an ungrounded hit opens WITHOUT seeking - the model's "
      "invented number is never kept",
      "if ms < 0:" in _blk and "ms = 0" in _blk)
check("a genuine hit on the OPENING line is not mistaken for not-found",
      "return -1" in SRC.split("def _moment_of")[1][:2400])

print("\n--- A4: the guard speaks Arabic (the Big Walk sister) ---")
BW_TITLE = ("\u0623\u0628\u0648 \u062e\u0627\u0644\u062f \u0648 "
            "\u0634\u0642\u064a\u0642\u062a\u0647 \u0648 "
            "\u0623\u0635\u062f\u0642\u0627\u0626\u0647\u0645 "
            "\u0641\u064a Big Walk")
bad4 = lore._title_unheard(BW_TITLE, "\u062e\u0627\u0644\u062f abu talk",
                           "Big Walk")
check("the invented sister is flagged",
      any("\u0634\u0642\u064a\u0642" in w for w in bad4))
bad4b = lore._title_unheard(
    BW_TITLE, "\u0634\u0642\u064a\u0642\u062a\u0647 "
              "\u062e\u0627\u0644\u062f", "Big Walk")
check("...and vouched when it was actually heard",
      not any("\u0634\u0642\u064a\u0642" in w for w in bad4b))
abstract = ("\u0627\u0644\u0645\u063a\u0627\u0645\u0631\u0629 "
            "\u0627\u0644\u0643\u0628\u0631\u0649 \u0641\u064a Grunn")
check("abstract Arabic in an honest title is never touched",
      not lore._title_unheard(abstract, "", "Grunn"))

print("\n--- A6: a possessive is not a new person ---")
check("\"Otak's\" is vouched by Otak in the transcript",
      "Otak's" not in lore._title_unheard(
          "Otak's Revenge", "we saw otak again", "Grunn"))
check("a plural is vouched by its base",
      "Molotovs" not in lore._title_unheard(
          "Molotovs and Mayhem", "throw the molotov now", "PEAK"))
check("a genuinely unheard possessive still flags",
      "Zorblax's" in lore._title_unheard(
          "Zorblax's Party", "nothing relevant here", "PEAK"))
check("the rstrip trap is dead (boss != bo)",
      "Boss" not in lore._title_unheard(
          "The Boss Fight", "the boss would not die", "Devour"))

print("\n--- A7 + A9: the summary is guarded; laundering is logged ---")
check("the gate covers the summary", "if title or summary:" in SRC)
check("both fields are checked as a union",
      "_title_unheard(summary, heard, game)" in SRC)
check("a re-ask must bring BOTH back clean",
      "_title_unheard(\n                                        cs, heard, game)"
      in SRC or "not _title_unheard(\n                                        cs" in SRC)
check("substitution repairs the summary too",
      "summary = re.sub(_pat, _rep, summary)" in SRC)
check("an Arabic invention is replaced in Arabic",
      "\u0623\u062d\u062f " in SRC or '"\\u0623\\u062d\\u062f "' in SRC)
check("laundering by chapter names is logged, never blocking",
      "laundering watch" in SRC)

print("\n--- A3: the lines carry their voice ---")
_ln = SRC.split("def _line(sg, i):")[1][:2200]
check("_line asks the overlap-only voice, never the nearest guess",
      "_aud_voice(_sd0" in _ln)
check("game audio is never given a voice",
      'not sg.get("g")' in _ln)
check("there is NO 'speaker N:' arm",
      "speaker " not in _ln.lower() or "speaker n" not in _ln.lower())
check("_sd0 exists even when the senses cannot be read",
      "_sd0 = {}          # _line() closes over this" in SRC)
check("the auto-you cluster maps onto the existing YOU: token",
      '== "you"' in _ln)

print("\n--- A8: a quote must exist in the lines it cites ---")


def extract(name):
    tree = ast.parse(SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                SRC.splitlines()[node.lineno - 1:node.end_lineno]))
            return code
    raise AssertionError(name)


ns = {"re": _re, "str": str, "_qf": [0]}
exec(compile(extract("_qnorm"), "<q>", "exec"), ns)
exec(compile(extract("_q_check"), "<q>", "exec"), ns)
exec(compile(extract("_m_qcheck"), "<q>", "exec"), ns)
_q_check, _m_qcheck = ns["_q_check"], ns["_m_qcheck"]

seq = [{"t": "Get the sniper now"}, {"t": "He is behind the door!"},
       {"t": "\u064a\u0644\u0627 \u0634\u0628\u0627\u0628"}]
sg1 = {"from_line": 0, "to_line": 1, "quote": "behind the door"}
_q_check(sg1, seq)
check("a real quote survives", sg1["quote"] == "behind the door")
sg2 = {"from_line": 0, "to_line": 1, "quote": "we conquered the castle"}
_q_check(sg2, seq)
check("an invented quote is blanked", sg2["quote"] == "")
check("...and banked, never silently dropped",
      sg2.get("quote_was") == "we conquered the castle")
sg3 = {"from_line": 0, "to_line": 1,
       "quote": "\u201cHE IS BEHIND THE DOOR!\u201d"}
_q_check(sg3, seq)
check("curly quotes, case and punctuation never fail a true quote",
      sg3["quote"] != "")
n0 = ns["_qf"][0]
mm1 = {"line": 1}
w1 = _m_qcheck(mm1, "'He is behind the door!' - panic sets in.", seq)
check("a moment's TRUE leading quote is untouched",
      w1.startswith("'He is behind the door!'"))
mm2 = {"line": 1}
w2 = _m_qcheck(mm2, "'Victory is ours!' - the final push succeeds.", seq)
check("a FALSE leading quote is cut, the explanation kept",
      w2 == "the final push succeeds." and ns["_qf"][0] > n0)
check("the guards log announces blanked quotes",
      "quote(s) not found in their cited lines" in SRC)

print("\n--- A2: ask_video verifies, localises, or honestly drops ---")
import json as _json
import os as _os
import tempfile as _tf
api = lore._JsApi.__new__(lore._JsApi)
api._safe_path = lambda p: p
_tmp = _tf.mkdtemp(prefix="ask323_")
_vid = _os.path.join(_tmp, "x.mp4")
io.open(_vid, "w").write("x")
lore._thumb_dir = lambda o: _tmp
_segs = [{"a": 5000, "b": 8000, "t": "Get the sniper now"},
         {"a": 60000, "b": 64000, "t": "He is behind the door!"},
         {"a": 120000, "b": 125000, "t": "The boss finally went down"}]
io.open(lore._ai_sidecar(_vid, "stt"), "w", encoding="utf-8").write(
    _json.dumps({"segments": _segs}))
_canned = {"answer": "They fought a boss.",
           "hits": [
               {"t": 999.0, "quote": "behind the door"},
               {"t": 3.0, "quote": "the boss went down at last"},
               {"t": 50.0, "quote": "we bought a castle in France"},
               {"t": 2.0, "quote": "Sniper!"},
               {"t": 1.0, "quote": ""}]}
_real_llm = lore._ask_llm
lore._ask_llm = lambda *a, **k: (_canned, "")
try:
    r = api.ask_video(_vid, "what happened?")
finally:
    lore._ask_llm = _real_llm
check("the answer prose stands", r["ok"] and "boss" in r["answer"])
check("a VERIFIED quote snaps to the real segment's clock",
      any(h["t_ms"] == 60000 and h["text"] == "behind the door"
          for h in r["hits"]))
check("...the model's invented 999s is discarded",
      not any(h["t_ms"] == 999000 for h in r["hits"]))
check("an overlapping paraphrase is LOCALISED and speaks the real line",
      any(h["t_ms"] == 120000
          and h["text"] == "The boss finally went down"
          for h in r["hits"]))
check("a pure invention is dropped",
      not any("castle" in h["text"] for h in r["hits"]))
check("...and the answer says so honestly",
      "left out" in r["answer"] and "1 quoted" in r["answer"])
check("a one-word quote with changed punctuation still verifies",
      any(h["t_ms"] == 5000 for h in r["hits"]))
check("an empty-quote hit is discarded without being counted",
      len(r["hits"]) == 3)

print("\n--- A10: the docs tell the truth ---")
RD = io.open(r"D:\Gate LLC\README.md", encoding="utf-8").read()
check("'fully offline' is gone", "ully offline" not in RD)
check("the three network modes are named",
      "model downloads" in RD and "cloud naming" in RD
      and "Discord sharing" in RD)
BR = io.open(r"D:\Gate LLC\tools\build_report.py",
             encoding="utf-8").read()
check("the report counts what build.bat copies, models excepted",
      "scripts + vendored libs + venv" in BR
      and '("Workers", "ai")' not in BR
      and "models install separately" in BR)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
