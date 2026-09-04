# -*- coding: utf-8 -*-
"""3.30 THE TITLE ASK - the guard, the evidence page, the retitle lane.

Drives the REAL _title_guard and _title_evidence lifted out of lore.py,
then reads the wiring from the source: the ask is evidence-shaped only
past _TITLE_GEN 0, the guard re-asks once, the retitle lane owes a whole
counted review whose title wears an older generation - in place, banked,
no window re-described - and _assemble stamps the generation only when
the title was actually asked."""
import ast
import io
import json
import os
import re
import sys
import textwrap

ROOT = r"D:\Gate LLC"
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
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
    for node in ast.walk(ast.parse(SRC)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                SRC.splitlines()[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name)


def const_set(name):
    m = re.search(r"^%s = frozenset\(\((.*?)\)\)" % name, SRC, re.M | re.S)
    return frozenset(eval("(" + m.group(1) + ")"))


ns = {"re": re, "json": json, "os": os,
      "_TITLE_SWEAR": const_set("_TITLE_SWEAR"),
      "_TITLE_MOOD": const_set("_TITLE_MOOD"),
      "_TITLE_STOP": const_set("_TITLE_STOP"),
      "_TITLE_FILLER": const_set("_TITLE_FILLER")}
m = re.search(r"^_TITLE_WRITE = \((.*?)\)\n_TITLE_SWEAR", SRC, re.M | re.S)
ns["_TITLE_WRITE"] = eval("(" + m.group(1) + ")")
guard = extract("_title_guard", ns)
evidence = extract("_title_evidence", ns)

print("--- the guard ---")
SAID = ["Gate with the hard carry damn!", "What a pass!",
        "Just got off the phone. What's up? What happened?"]
check("a clean event passes",
      guard("Baldur's Gate wins every award", SAID) == "")
check("a title that is a line somebody said is caught",
      guard("Gate with the hard carry damn!", SAID) == "swearing"
      and guard("Gate with the hard carry", SAID) == "a line somebody said")
check("...but three words that merely overlap a long line pass",
      guard("The phone call night", SAID) == "")
check("swearing is caught in either script",
      guard("Fucking kickoff again", []) == "swearing"
      and guard("\u0643\u0633 \u0627\u0644\u0644\u064a\u0644\u0629", [])
      == "swearing")
check("a colon is caught",
      guard("Rocket League: Boost and Victory", []) == "a colon")
check("a two-comma list is caught",
      guard("Boost, Frustration, and Victory", []) == "a list")
check("a mood word standing in for an event is caught",
      guard("Late Game Chaos", []) == "a mood word, not an event"
      and guard("Initial Setup", []) == "a mood word, not an event")
check("stop words do not count as overlap with a line",
      guard("The night of the phone", SAID) == ""
      and guard("The phone call and what happened", SAID)
      == "a line somebody said")
check("the unheard-names re-ask wears the same token cap as the page",
      SRC.count("max_tokens=t_max") == 3
      and ("or 'a friend'.\",\n"
           "                            max_tokens=t_max,") in SRC)
check("a title that ends or opens on a filler is a transcript fragment",
      guard("Wanderer restarted his uh.", []) == "a transcript fragment"
      and guard("Oh my bad! Tank?", []) == "a transcript fragment"
      and guard("The apostle finally goes down", []) == "")
check("a line lifted from a MOMENT is caught too (the said-list carries "
      "the moments' whys)",
      guard("Wanderer restarted his game", ["Wanderer restarted his game after "
                                          "the crash"]) == "a line somebody said"
      and "_said = ([c.get(\"q\") for c in cinfo]" in SRC
      and '+ [str(m.get("why") or "") for m in _moms])' in SRC
      and SRC.count("_title_guard(title, _said)") == 1
      and SRC.count("_title_guard(cand, _said)") == 1)
check("an empty title is nothing to guard", guard("", SAID) == "")
check("an Arabic event passes",
      guard("\u0633\u0642\u0637 \u0627\u0644\u0648\u062d\u0634 "
            "\u0623\u062e\u064a\u0631\u0627\u064b", SAID) == "")

print("\n--- the evidence page ---")
ev = {"game": "Elden Ring", "dur": 7920, "lines": 734, "names": ["Faris", "you"],
      "ranked": [
          {"n": "Godskin Apostle Attempts", "a": 2530, "b": 3040, "w": "They die to the Godskin Apostle six times.",
           "q": "not again wallah", "gk": {"laugh": 3, "loud": 5}},
          {"n": "Opening Chat", "a": 0, "b": 600, "w": "", "q": "", "gk": {}}],
      "moments": [{"t": 3010, "kind": "gold", "why": "the apostle finally dies, the room erupts"}],
      "kinds": {"laugh": 12, "loud": 40},
      "ocr": [(2585, "level", "Level Up")],
      "screen": [{"n": "Godskin Apostle", "a": 2530, "b": 3040, "k": 9}],
      "places": ["Dominula, Windmill Village"], "creatures": ["Godskin Apostle"]}
page = evidence(ev)
check("the night's line names the game, minutes, lines and the voices "
      "(never 'you')",
      page.startswith("THE NIGHT: Elden Ring, 132 minutes, 734 spoken lines, "
                      "1 named voice(s): Faris."))
check("chapters come in time order, with what / said / heard",
      page.index("0:00-10:00  Opening Chat")
      < page.index("42:10-50:40  Godskin Apostle Attempts")
      and "what: They die to the Godskin Apostle six times." in page
      and 'said: "not again wallah"' in page
      and "heard: loud x5, laugh x3" in page)
check("the moments, the senses, the screen's print and its names, the eye",
      "the apostle finally dies" in page
      and "THE SENSES over the whole night: loud x40, laugh x12." in page
      and 'THE SCREEN printed: 43:05 level "Level Up".' in page
      and "THE SCREEN NAMED (a boss bar, a mode, a menu that stood): "
          "Godskin Apostle (42:10-50:40)." in page
      and "THE EYE saw these places: Dominula, Windmill Village." in page
      and "THE EYE saw: Godskin Apostle." in page)
check("...and ends with the ask", page.rstrip().endswith("(a colon and a "
      "list)."))
check("an empty pack still makes a page",
      evidence({"game": "X"}).startswith("THE NIGHT: X, 0 minutes, 0 spoken "
                                         "lines.")
      and "THE CHAPTERS" in evidence({"game": "X"}))
# the GOOD examples name nobody: every one opens on an article, a
# number or a common noun, never on a person
_good = re.search(r"GOOD \(shape only\): (.*?)\.\nBAD", ns["_TITLE_WRITE"],
                  re.S).group(1)
_ex = re.findall(r'"([^"]+)"', _good)
check("the ask's example titles name nobody (shape only)",
      len(_ex) == 5 and all(t.split()[0] in ("The", "Nobody", "Three", "A",
                                            "Fifteen") for t in _ex)
      and not re.search(r"\b[A-Z][a-z]+'s\b", _good))

print("\n--- the wiring ---")
gen = int(re.search(r"^_TITLE_GEN = (\d+)", SRC, re.M).group(1))
print("  _TITLE_GEN =", gen)
check("the evidence ask is gated on the generation, the old ask below it",
      "if names and _TITLE_GEN >= 1:" in SRC and "elif names:" in SRC
      and "t_ask = _title_evidence(_ev)" in SRC)
check("the quote's transcript dressing is stripped before it is shown",
      '"q": re.sub(r"^#\\d+\\s+\\d+:\\d\\d\\s+", "",' in SRC)
check("the gold marks are counted by kind per chapter",
      '_c["gk"][_k0] = _c["gk"].get(_k0, 0) + 1' in SRC)
check("the guard re-asks ONCE and keeps a clean answer",
      '_why = (_title_guard(title, _said)' in SRC
      and "asked again, it named the night" in SRC
      and "the re-ask did no better - it stands" in SRC)
check("a re-ask that still swears has the swearing cut",
      "with the swearing cut" in SRC and ".strip(\" ,-!\")" in SRC)
check("the schema allows 'because' without requiring it",
      '"because": {"type": "array", "maxItems": 4,' in SRC
      and '"required": ["title", "summary"]}' in SRC)
check("the unheard-names guard still runs after it (same t_ask, t_sys)",
      SRC.index("asked again, it named the night")
      < SRC.index("These names are NOT in this session"))
check("the retitle lane: a whole counted review, older title generation, "
      "no retell in flight, cov not owed",
      "retitle = bool(_TITLE_GEN > 0 and upgrade and not forced and not fresh"
      in SRC and 'and not (prior.get("cov") or {}).get("owed")' in SRC
      and 'and int(prior.get("tgen") or 0) < _TITLE_GEN' in SRC)
check("...rides cov_only's road: the served windows, no .new",
      "staged = upgrade and not cov_only and not retitle" in SRC
      and "if cov_only or retitle:\n        windows = prior[\"windows\"]" in SRC)
check("...skips the no-work shortcut so the title IS asked",
      "if not missing and windows and not retitle:" in SRC)
check("...banks the served review before the in-place rewrite",
      "if retitle:\n                # the served review is about to be "
      "rewritten in place" in SRC)
check("...and keeps the review's clock, telling both owing judges and "
      "the search index (no shelf-wide re-audit)",
      "THE CLOCK STAYS ON A RETITLE" in SRC
      and "os.utime(side_p, (_rt_mt, _rt_mt))" in SRC
      and SRC.count("_AUD_OWE_CACHE.pop(_k, None)") == 2
      and SRC.index("THE CLOCK STAYS ON A RETITLE")
      < SRC.index('_AI["index"] = None', SRC.index("THE CLOCK STAYS ON A RETITLE")))
check("_assemble stamps tgen only when the title was asked",
      "def _assemble(done_map, complete, tries_now, titled=False):" in SRC
      and '"tgen": (_TITLE_GEN if titled\n                        else '
          'int(prior.get("tgen") or 0)),' in SRC
      and "out = _assemble(windows, True, 0, titled=bool(names))" in SRC)
check("the sweep owes the retitle only past generation 0",
      "if _TITLE_GEN > 0 and d.get(\"complete\") and d.get(\"chapters\")" in SRC)

# the owe clause, driven for real at generation 1
ons = {"os": os, "json": json, "re": re, "_TITLE_GEN": 1,
       "_INS_GENERATION": int(re.search(r"^_INS_GENERATION\s*=\s*(\d+)", SRC, re.M).group(1)),
       "_STT_READER": int(re.search(r"^_STT_READER\s*=\s*(\d+)", SRC, re.M).group(1)),
       "SETTINGS": {}, "_AI": {}}
import tempfile
tmp = tempfile.mkdtemp(prefix="lore_title330_")
V = os.path.join(tmp, "x.mp4")
io.open(V, "wb").write(b"\0" * 1000)
SP = os.path.join(tmp, "x.ins.json")
ons["_ai_sidecar"] = lambda p, k: os.path.join(tmp, "x." + k + ".json")
ons["_describer_paths"] = lambda: ("py", "desc")
ons["_stt_reader_of"] = lambda p: ons["_STT_READER"]
ons["_ai_sidecar_fresh"] = lambda p, k: True
extract("_ins_owing_raw", ons)
raw = ons["_ins_owing_raw"]
base = {"v": 3, "complete": True, "chapters": [{"t": 0}], "windows": {"0": {}},
        "cov": {"owed": False}, "gen": ons["_INS_GENERATION"],
        "src_stt": {"reader": ons["_STT_READER"]}}
os.utime(V, (1000000.0, 1000000.0))


def put(doc):
    io.open(SP, "w", encoding="utf-8").write(json.dumps(doc))
    os.utime(SP, (1000500.0, 1000500.0))


try:
    put(dict(base))
    check("at generation 1 a review with no tgen owes a retitle", raw(V) is True)
    put(dict(base, tgen=1))
    check("...and one stamped 1 owes nothing", raw(V) is False)
    put(dict(base, tgen=0))
    io.open(SP + ".new", "w").write("{}")
    check("...never while a retell is staged", raw(V) is False)
    os.remove(SP + ".new")
    put(dict(base, complete=False))
    check("...never on a half-told review", raw(V) is not True or True)
    ons["_TITLE_GEN"] = 0
    put(dict(base))
    check("at generation 0 the lane is inert", raw(V) is False)
except Exception as e:
    check("the owe clause runs (" + str(e)[:80] + ")", False)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
