# -*- coding: utf-8 -*-
"""3.37 drop O, item O2 - THE ANSWER THAT WAS CUT AT THE CAP.

Measured in lore.log since the 3.36 boot (12 Sep 17:52 -> 13 Sep 14:45):
60 describe windows, 22 with zero stretches, and every one of the 22
logged "for up to 1200|1500, and the answer did not parse - 875..2907
char(s) came back: {"segments": [{"from_line": 0, ...". The answer is
grammar-fenced (response_format json_schema), so the only way it fails
json.loads is that max_tokens cut it before its closing brace.

  1  _DescServer.ask records last_finish / last_tokens; the diagnostic
     line says the finish reason, the tokens and the last 80 chars;
  2  the cap is a ceiling: min(4000, 1500 + 150 * want), never above
     8000 on any ask;
  3  an ask after a cut carries twice the ceiling;
  4  _desc_salvage keeps the whole stretches of a cut answer - never a
     partial one, never raises - and the coverage road re-asks the rest.

Proven on the real _insights_one with a fake describer (the idiom of
retell336test), and on _desc_salvage cut at every character position.
No model, no port, no GPU; nothing under D:\\Records is read or written;
the names in the fixtures are game words, never a person.
"""
import ast
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, r"D:\Gate LLC")
import lore  # noqa: E402

lore._library_dirs = lambda out: []
lore._scan_dir_mp4s = lambda d, k: []
LOG = []
lore.log = lambda m: LOG.append(str(m))
lore._here = lambda: r"C:\Program Files\Lore"

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
TREE = ast.parse(SRC)

# THE PARITY BASE IS A COMMIT, NOT HEAD. 01f0a49 is 3.36, the tree the
# 22 cut windows were measured on.
PARITY_BASE = "01f0a49"


def func_src(name, src=None, tree=None):
    src = SRC if src is None else src
    tree = TREE if tree is None else tree
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(src.splitlines()[node.lineno - 1:node.end_lineno])
    raise AssertionError(name + " not found")


# =======================================================================
#  the fixture answer: eight stretches over twelve lines
# =======================================================================
NAMES = ["the first pull", "the ramp climb", "the arena gate",
         "the long volley", "the goal rush", "the reset", "the last pull",
         "the whistle"]


def fixture(n=8):
    return json.dumps({"segments": [
        {"from_line": i, "to_line": i, "name": NAMES[i],
         "what": "the ball is chased across the arena",
         "topics": ["arena", "ball"], "quote": ""} for i in range(n)],
        "moments": [{"line": 2, "kind": "funny",
                     "why": "the ball bounces off the gate"}]})


FULL = fixture()
FULL_SEGS = json.loads(FULL)["segments"]

print("--- 1: _desc_salvage, cut at every character ---")
sal = lore._desc_salvage
never_partial = True
never_raised = True
n_some = n_none = 0
for cut in range(len(FULL) + 1):
    try:
        r = sal(FULL[:cut])
    except Exception:
        never_raised = False
        continue
    if r is None:
        n_none += 1
        continue
    n_some += 1
    got = r.get("segments")
    if not isinstance(got, list) or not got \
            or got != FULL_SEGS[:len(got)]:
        never_partial = False
check("every cut returns exactly the whole prefix stretches or None - "
      "never a partial stretch (%d positions: %d salvaged, %d None)"
      % (len(FULL) + 1, n_some, n_none),
      never_partial and n_some > 0 and n_none > 0)
check("never raises", never_raised)
check("a cut inside the first stretch yields None (nothing whole came "
      "back)", sal(FULL[:FULL.find('"name"') + 12]) is None)
first_end = FULL.find("}") + 1
check("a cut right after the first stretch's brace yields exactly it",
      (sal(FULL[:first_end]) or {}).get("segments") == FULL_SEGS[:1])
check("a cut inside the moments array yields all eight stretches "
      "(moments dropped)",
      (sal(FULL[:FULL.find('"kind"') + 3]) or {}).get("segments")
      == FULL_SEGS and "moments" not in sal(FULL[:FULL.find('"kind"') + 3]))
whole = sal(FULL)
check("PINNED: an untruncated answer returns the FULL doc, moments and "
      "all (json.loads of the whole)",
      whole is not None and whole.get("segments") == FULL_SEGS
      and len(whole.get("moments") or []) == 1)
tricky = json.dumps({"segments": [
    {"from_line": 0, "to_line": 1, "name": "a } brace in the name",
     "what": "quotes \"inside\" and a ] bracket and a { brace",
     "topics": ["x]", "{y"], "quote": "back\\slash \\\" quote"},
    {"from_line": 2, "to_line": 3, "name": "second",
     "what": "plain", "topics": [], "quote": ""}],
    "moments": []})
t_segs = json.loads(tricky)["segments"]
t_ok = True
for cut in range(len(tricky) + 1):
    r = sal(tricky[:cut])
    if r is not None and r["segments"] != t_segs[:len(r["segments"])]:
        t_ok = False
check("braces, brackets and escaped quotes INSIDE strings do not fool "
      "the walk (every cut of a tricky answer)", t_ok)
check("garbage, empty and None yield None, quietly",
      sal("garbage") is None and sal("") is None and sal(None) is None
      and sal('{"moments": [{"line": 1, "kind": "funny", "why":') is None)

# =======================================================================
#  the fixture: one night, a fake describer, the real _insights_one
# =======================================================================
ASKS = []


def make_server(answers):
    class FakeServer(object):
        def __init__(self, port=None):
            self.pr = None
            self.last_finish = None
            self.last_tokens = None

        def start(self, budget=900):
            return True

        def ask(self, system, user, max_tokens=900, schema=None,
                images=None, **kw):
            m = re.search(r"runs from minute (\d+) to minute", user)
            if m:
                key = "w" + m.group(1)
                mn = re.search(r"#numbers \(0 to (\d+)\)", user)
                n = int(mn.group(1)) + 1 if mn else 0
                ASKS.append((key, max_tokens, n))
                a = answers.get(key)
                if callable(a):
                    a = a(n)
                if a is None:
                    self.last_finish, self.last_tokens = None, None
                    return ""
                txt, fin, tok = a
                self.last_finish, self.last_tokens = fin, tok
                return txt
            ASKS.append(("title", max_tokens, 0))
            self.last_finish, self.last_tokens = "stop", 20
            return json.dumps({"title": "the arena match goes long",
                               "summary": "a long night in the arena"})

        def stop(self):
            pass

    return FakeServer


def mount(mod, root, vdur, answers):
    """Every door _insights_one opens onto the machine, closed."""
    mod.log = lambda m: LOG.append(str(m))
    mod._library_dirs = lambda out: []
    mod._scan_dir_mp4s = lambda d, k: []
    try:
        mod.load_settings()
    except Exception:
        pass
    mod.SETTINGS["output_dir"] = root
    mod.SETTINGS["insights_auto"] = True
    mod.SETTINGS["bg_shutdown"] = False
    mod._ai_sidecar = lambda p, k: os.path.join(
        os.path.dirname(p),
        os.path.splitext(os.path.basename(p))[0] + "." + k + ".json")
    mod._describer_paths = lambda: ("exe", "mdl")
    mod._desc_mmproj = lambda: None
    mod._video_duration = lambda p: vdur
    mod._story_seconds = lambda p, d: (vdur, "")
    mod._pic_black = lambda p: False
    mod._grab_frames = lambda p, t, stats=None: []
    mod._eye_seen = lambda p: []
    mod._stt_reader_of = lambda p: 7
    mod._DescServer = make_server(answers)
    mod._DESC_KEEP["srv"] = None
    mod._AI["abort"] = False
    mod._AI["wind"] = False
    return mod


WORDS = ("the ball rolls across the arena and the match runs long "
         "again tonight").split()


def night(root, name, vdur=1800.0):
    """A video and a transcript with a dozen room lines in one window."""
    os.makedirs(root, exist_ok=True)
    vid = os.path.join(root, name + ".mp4")
    io.open(vid, "w").write("x")
    segs = []
    for i in range(12):
        t = int((60 + i * 60) * 1000)
        segs.append({"a": t, "b": t + 3000,
                     "t": " ".join(WORDS[i % len(WORDS):]
                                   + WORDS[:i % len(WORDS)])})
    json.dump({"segments": segs, "sources": {}},
              io.open(os.path.join(root, name + ".stt.json"), "w",
                      encoding="utf-8"))
    return vid


def ins_of(mod, vid):
    p = mod._ai_sidecar(vid, "ins")
    if not os.path.isfile(p):
        return None
    return json.load(io.open(p, encoding="utf-8"))


def rest(n):
    """The answer to a coverage re-ask: one stretch over every row."""
    return (json.dumps({"segments": [
        {"from_line": 0, "to_line": n - 1, "name": "the rest of it",
         "what": "the match plays out", "topics": ["arena"],
         "quote": ""}], "moments": []}), "stop", 60)


CUT = FULL[:int(len(FULL) * 0.6)]
CUT_SEGS = (sal(CUT) or {}).get("segments") or []
CAP3 = min(4000, 1500 + 150 * 3)        # twelve lines: want 3


def cut_then_rest(n):
    # the twelve-line first telling comes back cut; a shorter slice (the
    # coverage re-ask) comes back whole
    return (CUT, "length", CAP3) if n == 12 else rest(n)


# =======================================================================
print("--- 2: the window road - a cut answer is salvaged, the rest "
      "re-asked with the doubled ceiling ---")
check("the fixture cut at 60%% holds %d whole stretches (of 8), and "
      "leaves >= 6 rows untold so the coverage road fires"
      % len(CUT_SEGS), 3 <= len(CUT_SEGS) <= 6)
P1 = tempfile.mkdtemp(prefix="desc337_a_")
v1 = night(P1, "night")
mount(lore, P1, 1800.0, {"w0": cut_then_rest})
ASKS[:] = []
LOG[:] = []
lore._insights_one(v1, forced=True)
d1 = ins_of(lore, v1)
w1 = ((d1 or {}).get("windows") or {}).get("0") or {}
names1 = [s.get("name") for s in (w1.get("segments") or [])]
check("the window banks the salvaged stretches, in order, and the rest",
      names1[:len(CUT_SEGS)] == [s["name"] for s in CUT_SEGS]
      and "the rest of it" in names1)
check("the log says 'salvaged N stretch(es) from an answer cut at the "
      "cap'", any("salvaged %d stretch(es) from an answer cut at the cap"
                  % len(CUT_SEGS) in m for m in LOG))
check("no 'did not parse' line - the cut answer was a word, not a hole",
      not any("did not parse" in m for m in LOG))
wasks = [a for a in ASKS if a[0] == "w0"]
check("two asks of the window: the first telling at the ceiling for "
      "twelve lines (%d), then the coverage re-ask over the untold rows"
      % CAP3,
      len(wasks) == 2 and wasks[0][1] == CAP3 and wasks[0][2] == 12
      and wasks[1][2] == 12 - len(CUT_SEGS))
n2 = wasks[1][2] if len(wasks) == 2 else 0
w2 = max(3, min(12, -(-n2 // 12)))
check("the second ask carries the DOUBLED ceiling (%d)"
      % min(8000, 2 * min(4000, 1500 + 150 * w2)),
      len(wasks) == 2
      and wasks[1][1] == min(8000, 2 * min(4000, 1500 + 150 * w2)))
check("the review is whole: complete, chapters, one window, no parse "
      "retry counted",
      bool((d1 or {}).get("complete")) and bool((d1 or {}).get("chapters"))
      and not any("parse retr" in m and "1 parse" in m for m in LOG))
check("nothing re-owed: no owe cache, generation or version moved",
      lore._INS_GENERATION == 3 and lore._AUD_V == 7)

# =======================================================================
print("--- 3: a cut with nothing whole: the retry itself carries the "
      "doubled ceiling ---")
STUB = FULL[:FULL.find('"name"') + 12]        # inside the first stretch


def stub_then_full(n):
    calls.append(n)
    return (STUB, "length", CAP3) if len(calls) == 1 \
        else (FULL if n == 12 else rest(n)[0], "stop", 400)


calls = []
P2 = tempfile.mkdtemp(prefix="desc337_b_")
v2 = night(P2, "night")
mount(lore, P2, 1800.0, {"w0": stub_then_full})
ASKS[:] = []
LOG[:] = []
lore._insights_one(v2, forced=True)
wasks = [a for a in ASKS if a[0] == "w0"]
d2 = ins_of(lore, v2)
check("the first ask at %d, the retry of the SAME twelve lines at %d"
      % (CAP3, min(8000, 2 * CAP3)),
      len(wasks) >= 2 and wasks[0] == ("w0", CAP3, 12)
      and wasks[1] == ("w0", min(8000, 2 * CAP3), 12))
check("the retry's whole answer is banked: eight stretches",
      len((((d2 or {}).get("windows") or {}).get("0") or {})
          .get("segments") or []) == 8)
check("no 'salvaged' line (nothing whole came back), and no 'did not "
      "parse' (the retry answered)",
      not any("salvaged" in m for m in LOG)
      and not any("did not parse" in m for m in LOG))

# =======================================================================
print("--- 4: garbage with finish 'stop' - today's road, and the "
      "diagnostic says how it ended ---")
GARBAGE = "the ball " * 40 + "END OF THE GARBAGE"
P3 = tempfile.mkdtemp(prefix="desc337_c_")
v3 = night(P3, "night")
mount(lore, P3, 1800.0, {"w0": lambda n: (GARBAGE, "stop", 77)})
ASKS[:] = []
LOG[:] = []
lore._insights_one(v3, forced=True)
wasks = [a for a in ASKS if a[0] == "w0"]
d3 = ins_of(lore, v3)
diag = [m for m in LOG if "did not parse" in m]
check("the parse retry fires once, both asks at the same ceiling (no "
      "doubling without a cut)",
      len(wasks) == 2 and wasks[0][1] == CAP3 and wasks[1][1] == CAP3)
check("the window is unfinished - banked with its spent ask, no "
      "stretch, not complete",
      not (d3 or {}).get("complete")
      and (((d3 or {}).get("windows") or {}).get("0") or {})
      .get("segments") == [])
check("the diagnostic line carries the finish reason, the tokens and "
      "the tail",
      len(diag) == 1 and "for up to %d" % CAP3 in diag[0]
      and "%d char(s) came back (finish stop, 77 token(s)): " % len(GARBAGE)
      in diag[0] and " ... " in diag[0]
      and diag[0].rstrip().endswith("END OF THE GARBAGE")
      and " ".join(GARBAGE[:200].split()) in diag[0])
check("no 'salvaged' on a stop finish - salvage is for a cut only",
      not any("salvaged" in m for m in LOG))

# =======================================================================
print("--- 5: the cap arithmetic ---")
ins = func_src("_insights_one")
line = [ln for ln in ins.splitlines() if "out_cap = min(" in ln]
check("one cap line: out_cap = min(4000, 1500 + 150 * want)",
      len(line) == 1 and line[0].strip()
      == "out_cap = min(4000, 1500 + 150 * want)")
caps = {}
for want in (3, 5, 8, 12):
    caps[want] = eval(line[0].split("=", 1)[1], {}, {"want": want})
check("want 3/5/8/12 -> 1950/2250/2700/3300, doubled 3900/4500/5400/6600",
      caps == {3: 1950, 5: 2250, 8: 2700, 12: 3300}
      and [min(8000, 2 * c) for c in caps.values()]
      == [3900, 4500, 5400, 6600])
check("no ask ever exceeds 8000: the doubled ask is min(8000, ...) and "
      "the ceiling is 4000",
      "_mt = min(8000, 2 * out_cap) if _dbl else out_cap" in ins
      and ins.count("max_tokens=_mt,") == 1
      and max(min(8000, 2 * min(4000, 1500 + 150 * w))
              for w in range(3, 13)) <= 8000)
check("the ask reads the finish off the server (getattr, so a server "
      "without it is a stop)",
      'getattr(srv, "last_finish", None)' in ins
      and 'getattr(srv, "last_tokens", None)' in ins
      and 'if _fin == "length":' in ins)
ask = None
for node in ast.walk(TREE):
    if isinstance(node, ast.ClassDef) and node.name == "_DescServer":
        for f in node.body:
            if isinstance(f, ast.FunctionDef) and f.name == "ask":
                ask = "\n".join(SRC.splitlines()[f.lineno - 1:f.end_lineno])
check("_DescServer.ask records finish_reason and completion_tokens, and "
      "clears them at the top of every ask",
      ask is not None and '.get("finish_reason")' in ask
      and '.get("completion_tokens")' in ask
      and ask.count("self.last_finish = None") == 1
      and ask.count("self.last_tokens = None") == 1)
check("privacy: the diagnostic keeps a 200-char head and an 80-char tail "
      "and nothing goes to disk",
      "str(txt)[:200].split()" in ins and "str(txt)[-80:].split()" in ins
      and "_desc_salvage" in ins
      and "open(" not in func_src("_desc_salvage"))

# =======================================================================
print("--- 5b: an EMPTY answer that finished 'length' (the 3.33 shape: "
      "thinking spent the budget) ---")
calls = []


def empty_then_full(n):
    calls.append(n)
    if len(calls) == 1:
        return ("", "length", 622)
    return (FULL, "stop", 400) if n == 12 else rest(n)


P4 = tempfile.mkdtemp(prefix="desc337_d_")
v4 = night(P4, "night")
mount(lore, P4, 1800.0, {"w0": empty_then_full})
ASKS[:] = []
LOG[:] = []
lore._insights_one(v4, forced=True)
wasks = [a for a in ASKS if a[0] == "w0"]
d4 = ins_of(lore, v4)
check("the first ask at %d came back EMPTY with finish length; the retry "
      "of the same twelve lines carries the DOUBLED ceiling (%d)"
      % (CAP3, min(8000, 2 * CAP3)),
      len(wasks) >= 2 and wasks[0] == ("w0", CAP3, 12)
      and wasks[1] == ("w0", min(8000, 2 * CAP3), 12))
check("the retry's whole answer is banked: eight stretches",
      len((((d4 or {}).get("windows") or {}).get("0") or {})
          .get("segments") or []) == 8)
check("no 'salvaged' line - nothing to salvage from an empty answer",
      not any("salvaged" in m for m in LOG))
P5 = tempfile.mkdtemp(prefix="desc337_e_")
v5 = night(P5, "night")
mount(lore, P5, 1800.0, {"w0": lambda n: ("", "length", 622)})
ASKS[:] = []
LOG[:] = []
lore._insights_one(v5, forced=True)
diag = [m for m in LOG if "did not parse" in m]
check("empty on both asks: the diagnostic's empty branch names the "
      "finish and the tokens - 'nothing came back at all (finish length, "
      "622 token(s)).'",
      len(diag) == 1 and diag[0].rstrip().endswith(
          "nothing came back at all (finish length, 622 token(s)).")
      and "for up to %d" % min(8000, 2 * CAP3) in diag[0])
P6 = tempfile.mkdtemp(prefix="desc337_f_")
v6 = night(P6, "night")
mount(lore, P6, 1800.0, {"w0": lambda n: None})
ASKS[:] = []
LOG[:] = []
lore._insights_one(v6, forced=True)
wasks = [a for a in ASKS if a[0] == "w0"]
diag = [m for m in LOG if "did not parse" in m]
check("a server error (nothing, no finish) reads 'nothing came back at "
      "all (finish ?).' - told from an empty length - and the retry is "
      "NOT doubled",
      len(diag) == 1 and diag[0].rstrip().endswith(
          "nothing came back at all (finish ?).")
      and len(wasks) == 2 and all(a[1] == CAP3 for a in wasks))

# =======================================================================
print("--- 6: the witness, %s ---" % PARITY_BASE)
BASE_PY = os.path.join(tempfile.mkdtemp(prefix="desc337_base_"),
                       "lore_base.py")
io.open(BASE_PY, "wb").write(subprocess.run(
    ["git", "show", PARITY_BASE + ":lore.py"], cwd=ROOT,
    capture_output=True).stdout)
_spec = importlib.util.spec_from_file_location("lore_base", BASE_PY)
lore_base = importlib.util.module_from_spec(_spec)
sys.modules["lore_base"] = lore_base
lore_base.__dict__["log"] = lambda m: None
_spec.loader.exec_module(lore_base)
PB = tempfile.mkdtemp(prefix="desc337_base_n_")
vb = night(PB, "night")
mount(lore_base, PB, 1800.0, {"w0": cut_then_rest})
ASKS[:] = []
LOG[:] = []
lore_base._insights_one(vb, forced=True)
db = ins_of(lore_base, vb)
wb = ((db or {}).get("windows") or {}).get("0") or {}
basks = [a for a in ASKS if a[0] == "w0"]
check("before: the same cut answer was asked for up to %d, twice, and "
      "logged 'did not parse' with nothing banked"
      % min(1500, 900 + 100 * max(0, 3 - 5)),
      len(basks) == 2 and all(a[1] == 900 and a[2] == 12 for a in basks)
      and any("did not parse" in m for m in LOG)
      and wb.get("segments") == [] and not (db or {}).get("complete"))
check("before: no salvage, no finish reason in the log",
      not hasattr(lore_base, "_desc_salvage")
      and not any("finish " in m for m in LOG))
PB2 = tempfile.mkdtemp(prefix="desc337_base_e_")
vb2 = night(PB2, "night")
mount(lore_base, PB2, 1800.0, {"w0": lambda n: ("", "length", 622)})
ASKS[:] = []
LOG[:] = []
lore_base._insights_one(vb2, forced=True)
basks = [a for a in ASKS if a[0] == "w0"]
check("before: an empty 'length' answer was logged 'nothing came back at "
      "all.' with no finish and no tokens, and its retry at the same 900",
      len(basks) == 2 and all(a[1] == 900 for a in basks)
      and any(m.rstrip().endswith("nothing came back at all.") for m in LOG)
      and not any("finish " in m for m in LOG))
del sys.modules["lore_base"]

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
