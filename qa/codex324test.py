# -*- coding: utf-8 -*-
"""3.24: the hands-off decision matrix, proven on the real functions.

A mutation lands only when the recording itself supports it; evidence
conflicts preserve automatically; unsupported output is rejected
automatically. No row requires the user."""
import io
import json
import os
import sys
import tempfile

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


# a vocabulary where common words recur and inventions do not
lore._AUD_VOCAB["freq"] = {w: 9 for w in
                           ("door", "sniper", "boss", "behind", "going",
                            "the", "yalla", "shabab", "get", "now")}

print("--- C1: a fix must share ground with the ear ---")


def parse(garble, fixes):
    SAID[:] = []
    return lore._aud_parse({"checked": [], "fixes": fixes}, garble)


g1 = [{"t": 10.0, "text": "gibber jabber xx",
       "ear": "get behind the door now"}]
_, _, _, _, _, fx = parse(g1, [{"n": 0, "heard": "Get behind the door",
                                "why": "clearer"}])
check("a fix the ear AGREES with is applied", len(fx) == 1)

g2 = [{"t": 10.0, "text": "gibber jabber xx",
       "ear": "yalla shabab going now"}]
_, _, _, _, _, fx2 = parse(g2, [{"n": 0, "heard": "The sniper boss door",
                                 "why": "sounds right"}])
check("a fluent fix sharing NO word with the audio is refused",
      len(fx2) == 0)
check("...and the refusal names the ear",
      any("re-listened audio heard none" in m for m in SAID))

g3 = [{"t": 10.0, "text": "gibber jabber xx"}]        # no ear at all
_, _, _, _, _, fx3 = parse(g3, [{"n": 0, "heard": "Get behind the door",
                                 "why": "clear"}])
check("a span the ear never reached keeps the old behaviour",
      len(fx3) == 1)

g4 = [{"t": 10.0, "text": "gibber jabber xx",
       "ear": "zz", "ear_junk": True}]
_, _, _, _, _, fx4 = parse(g4, [{"n": 0, "heard": "Get behind the door",
                                 "why": "clear"}])
check("a junk ear does not gate (it saw nothing)", len(fx4) == 1)

print("\n--- C2: a noise strike needs the recording's testimony ---")


def verdict_of(row, v="noise"):
    garble = [row]
    lore._aud_parse({"checked": [{"n": 0, "verdict": v, "why": "x"}],
                     "fixes": []}, garble)
    return garble[0].get("verdict")


check("noise with a READABLE ear is downgraded - the line survives",
      verdict_of({"t": 5.0, "text": "abc",
                  "ear": "get behind the door"}) == "unclear")
check("noise with a junk ear still strikes",
      verdict_of({"t": 5.0, "text": "abc", "ear": "zz",
                  "ear_junk": True}) == "noise")
check("noise with no ear keeps the old behaviour",
      verdict_of({"t": 5.0, "text": "abc"}) == "noise")
check("noise whose ear is itself gibberish still strikes",
      verdict_of({"t": 5.0, "text": "abc",
                  "ear": "zzq xxv qqz wwx"}) == "noise")
check("the survivor is marked so QA can count these",
      (lambda r: (verdict_of(r), r.get("ear_kept"))[1])(
          {"t": 5.0, "text": "abc", "ear": "behind the door"}) is True)
check("only 'noise' verdicts strike (the downgrade is preservation)",
      'g.get("verdict") == "noise"' in io.open(
          r"D:\Gate LLC\lore.py", encoding="utf-8").read())

print("\n--- C3/C4/C5/C8: the Ask and quote fixes ---")
SRC = io.open(r"D:\Gate LLC\lore.py", encoding="utf-8").read()
api = lore._JsApi.__new__(lore._JsApi)
api._safe_path = lambda p: p
_tmp = tempfile.mkdtemp(prefix="ask324_")
_vid = os.path.join(_tmp, "x.mp4")
io.open(_vid, "w").write("x")
lore._thumb_dir = lambda o: _tmp
_segs = [{"a": 5000, "b": 8000, "t": "I know the way"},
         {"a": 60000, "b": 64000, "t": "Let's go now"}]
io.open(lore._ai_sidecar(_vid, "stt"), "w", encoding="utf-8").write(
    json.dumps({"segments": _segs}))
_real_llm = lore._ask_llm


def ask_with(hits, answer="An answer."):
    lore._ask_llm = lambda *a, **k: ({"answer": answer, "hits": hits}, "")
    try:
        return api.ask_video(_vid, "what?")
    finally:
        lore._ask_llm = _real_llm


r1 = ask_with([{"t": 1.0, "quote": "no"}])
check("'no' can no longer verify inside 'know'", len(r1["hits"]) == 0)
r2 = ask_with([{"t": 1.0, "quote": "Let's go"}])
check("a contiguous token quote still verifies (curly-safe)",
      len(r2["hits"]) == 1 and r2["hits"][0]["t_ms"] == 60000)
r3 = ask_with([{"t": 9.0, "quote": "the treasure is buried at dawn"}],
              "Alice said the treasure is buried at dawn.")
check("prose does not outlive its evidence: zero survivors REPLACES it",
      "could not verify" in r3["answer"]
      and "treasure" not in r3["answer"])
r4 = ask_with([{"t": 9.0, "quote": "the treasure is buried at dawn"},
               {"t": 2.0, "quote": "Let's go"}])
check("with a survivor, the prose stands and the miss is footnoted",
      "could not verify" not in r4["answer"]
      and "left out" in r4["answer"])

check("ask_library NEVER keeps an invented time",
      "ms = 0" in SRC.rsplit(
          'for h in (data.get("hits") or [])[:20]:', 1)[1][:2400]
      and 'ms = int(float(h.get("t")' not in SRC.rsplit(
          'for h in (data.get("hits") or [])[:20]:', 1)[1][:2400])

# proven functionally, not by grepping escapes: an honest quote the
# model copied WITH its Arabic speaker prefix must be recovered
import ast as _ast
import re as _re
import textwrap as _tw


def _extract(name):
    tree = _ast.parse(SRC)
    for node in _ast.walk(tree):
        if isinstance(node, _ast.FunctionDef) and node.name == name:
            return _tw.dedent("\n".join(
                SRC.splitlines()[node.lineno - 1:node.end_lineno]))


_ns = {"re": _re, "_qf": [0]}
exec(compile(_extract("_qnorm"), "<q>", "exec"), _ns)
exec(compile(_extract("_q_check"), "<q>", "exec"), _ns)
_seq = [{"t": "\u064A\u0644\u0627 \u0646\u0631\u0648\u062D "
             "\u0627\u0644\u062D\u064A\u0646"}]
_sg = {"from_line": 0, "to_line": 0,
       "quote": "\u0645\u0631\u064A\u0645: \u064A\u0644\u0627 "
                "\u0646\u0631\u0648\u062D \u0627\u0644\u062D\u064A\u0646"}
_ns["_q_check"](_sg, _seq)
check("an Arabic-prefixed honest quote is recovered, prefix shed",
      _sg["quote"] != "" and "\u0645\u0631\u064A\u0645" not in _sg["quote"])

print("\n--- the W round: the gates earn their keep ---")
# W2: a fix that transcribes what the ear heard, across scripts
g5 = [{"t": 10.0, "text": "gibber",
       "ear": "راستن"}]
_, _, _, _, _, fx5 = parse(g5, [{"n": 0, "heard": "Rastin.",
                                 "why": "the name"}])
check("W2: 'Rastin.' agrees with its Arabic ear by skeleton",
      len(fx5) == 1)
# W3: a refusal leaves a visible, strike-proof verdict
g6 = [{"t": 10.0, "text": "gibber",
       "ear": "yalla shabab going now"}]
parse(g6, [{"n": 0, "heard": "The sniper boss door", "why": "x"}])
check("W3: a refused fix leaves 'unclear' + the reason on the row",
      g6[0].get("verdict") == "unclear"
      and "refused" in (g6[0].get("vwhy") or ""))
# W1: the veto demands a FULLY readable ear
check("W1: an UNRELATED single-token ear does not veto a strike "
      "(one that repeats the line does - codex325test)",
      verdict_of({"t": 5.0, "text": "abc",
                  "ear": "door"}) == "noise")
check("W1: a CJK-static ear does not veto",
      verdict_of({"t": 5.0, "text": "abc",
                  "ear": "أستا ちは総力"}) == "noise")
check("W1: a fully readable ear still vetoes (the line survives)",
      verdict_of({"t": 5.0, "text": "abc",
                  "ear": "get behind the door"}) == "unclear")
# W1b + W4: source contracts
check("W1b: a vetoed strike is never frozen by the carry",
      'not p0.get("ear_kept")' in SRC)
check("W4: a fix beats the ear-kept downgrade in the dedup",
      'g.get("ear_kept")' in SRC.split("fixed_ts = {")[1][:600])
check("W5: Arabic punctuation cannot glue tokens (both sides shed)",
      "u061f" in SRC.split("word-glue")[1][:300])

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
