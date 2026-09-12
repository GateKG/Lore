# -*- coding: utf-8 -*-
"""3.36 drop N - THE RETELL THAT NEVER FINISHES.

Measured on his own shelf on 8 Sep (lore.log + the sidecars of a
47-minute night described under 3.33):

    01:44:58  Described ...: 17 stretch(es) across 2 window(s)
    01:50:37  The audit corrected lines inside 1 described window(s)
    01:54:43  window 0-30 min -> 0 stretch(es), 3 moment(s)
    01:54:43  ... is unfinished: 1 of 2 window(s) done
    01:57:30  window 0-30 min -> 0 stretch(es), 3 moment(s)

and on disk an ins.json.new holding ONE window, tries=2, cov.frac
0.405. Reproduced here against the real _insights_one: BOTH parse
attempts of the retold window came back unusable, so `got` was None,
and the record at the foot of the window loop (`if mapped or got is
not None`) threw the window away - the spent ask, the moments the
screen's verdicts had planted, everything. Nothing counted down, so
the next beat made the identical ask. The "3 moment(s)" in that log
line were planted by code, never answered by the model.

  N1 the ask that will not parse is banked, says what it asked for,
     and a window that ANSWERED nothing twice (a parsed answer with no
     stretch) is TOLD-EMPTY - while an answer that did not parse is no
     word at all: the window stays owed, the run spends a try, and the
     served telling is never replaced by a hole (the fix-first review
     measured 3 stretches -> 0 when both were settled alike); the
     second ask is a first telling again, not "the REST of a window
     whose start you already described" over an empty evidence block;
  N2 a resume MERGES what is on disk with what this run told; a
     window is re-asked only when it is missing or when the audit's
     own ledger says it was cut;
  N3 the head of the queue is bounded: two empty retells and the
     night is left as it was, said once;
  N4 a .new older than the finished review beside it goes to the
     attic on boot, never deleted - NARROWED from the spec's plain
     clock rule by a tries>=3 gate (measured read-only on the shelf, 8
     Sep: the 7 older .new files were all live retells respelled by
     _aud_apply_names, tries 0), so the one the spec saw "with no
     describe in flight" is not filed by this drop; and never on an
     older-engine review with the eye installed, where the tries-3
     .new IS the marker the owing judge reads;
  N5 the audit that never settles: the backstop - two change-free
     audits inside ten minutes and the night is left alone for the
     session, focus released, said once - and the empty review's write
     keeps its clock when the doc on disk is byte-identical;
  N6 the Working tally's week sentence and the eye's price line, both
     measured off the log the app already writes.

Everything runs on tempdirs with a fake describer. No model, no port,
no device, and nothing under D:\\Records is read or written. The names
in the fixtures are game words, never a person.
"""
import ast
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, r"D:\Gate LLC")
import lore  # noqa: E402

# A SUITE THAT TICKS MUST PEN THE LIBRARY WALK (aud302's law): the boot
# migrations WRITE, and this drop adds one more of them.
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

# THE PARITY BASE IS A COMMIT, NOT HEAD. While a drop is uncommitted
# "HEAD" is the file before it; the moment it lands "HEAD" IS the drop
# and the twin becomes its own subject. 1fc336d is 3.35.
PARITY_BASE = "1fc336d"


def func_src(name, src=None, tree=None):
    src = SRC if src is None else src
    tree = TREE if tree is None else tree
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(src.splitlines()[node.lineno - 1:node.end_lineno])
    raise AssertionError(name + " not found")


# =======================================================================
#  the fixture: one night, a fake describer, the real _insights_one
# =======================================================================
ASKS = []


def make_server(answers):
    import re as _re

    class FakeServer(object):
        def __init__(self, port=None):
            self.pr = None

        def start(self, budget=900):
            return True

        def ask(self, system, user, max_tokens=900, schema=None,
                images=None, **kw):
            m = _re.search(r"runs from minute (\d+) to minute", user)
            if m:
                key = "w" + m.group(1)
                ASKS.append(key)
                a = answers.get(key)
                if callable(a):
                    a = a()
                return a if a is not None else ""
            ASKS.append("title")
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
    # his live master switch is penned like the library walk:
    # a suite must never go red on a preference he changed
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


def night(root, name, edges_n=2, vdur=3000.0):
    """A video and a transcript with a dozen room lines per window."""
    os.makedirs(root, exist_ok=True)
    vid = os.path.join(root, name + ".mp4")
    io.open(vid, "w").write("x")
    segs = []
    for w in range(edges_n):
        for i in range(12):
            t = int((w * 1800 + 60 + i * 60) * 1000)
            segs.append({"a": t, "b": t + 3000,
                         "t": " ".join(WORDS[i % len(WORDS):]
                                       + WORDS[:i % len(WORDS)])})
    json.dump({"segments": segs, "sources": {}},
              io.open(os.path.join(root, name + ".stt.json"), "w",
                      encoding="utf-8"))
    return vid


def told(label, n=12):
    return json.dumps({"segments": [
        {"name": label, "what": "they play out a long match",
         "topics": ["arena"], "from_line": 0, "to_line": n - 1,
         "quote": ""}], "moments": []})


def ins_of(mod, vid, new=False):
    p = mod._ai_sidecar(vid, "ins") + (".new" if new else "")
    if not os.path.isfile(p):
        return None
    return json.load(io.open(p, encoding="utf-8"))


# =======================================================================
print("--- 1: parity - a night with no audit correction is described "
      "exactly as 3.35 described it ---")
BASE_PY = os.path.join(tempfile.mkdtemp(prefix="retell336_base_"),
                       "lore_base.py")
io.open(BASE_PY, "wb").write(subprocess.run(
    ["git", "show", PARITY_BASE + ":lore.py"], cwd=ROOT,
    capture_output=True).stdout)
_spec = importlib.util.spec_from_file_location("lore_base", BASE_PY)
lore_base = importlib.util.module_from_spec(_spec)
sys.modules["lore_base"] = lore_base
lore_base.__dict__["log"] = lambda m: None
_spec.loader.exec_module(lore_base)

ANS = {"w0": told("the first half"), "w30": told("the second half")}
P_NEW = tempfile.mkdtemp(prefix="retell336_a_")
P_OLD = tempfile.mkdtemp(prefix="retell336_b_")
v_new = night(P_NEW, "night")
v_old = night(P_OLD, "night")
mount(lore, P_NEW, 3000.0, ANS)
mount(lore_base, P_OLD, 3000.0, ANS)
ASKS[:] = []
lore._insights_one(v_new, forced=True)
asks_new = list(ASKS)
ASKS[:] = []
lore_base._insights_one(v_old, forced=True)
asks_old = list(ASKS)
d_new, d_old = ins_of(lore, v_new), ins_of(lore_base, v_old)
for d in (d_new, d_old):
    (d or {}).pop("src_stt", None)   # the stt's mtime, one per tempdir
check("the parity base described the fixture at all",
      d_old and d_old.get("complete") and len(d_old["chapters"]) == 2)
check("3.36 asks for exactly the same windows, in the same order",
      asks_new == asks_old and asks_new[:2] == ["w0", "w30"])
check("the whole review is byte-identical to the parity base's",
      json.dumps(d_new, sort_keys=True) == json.dumps(d_old, sort_keys=True))
check("and no cut ledger is written on a night nobody cut",
      "retold" not in (d_new or {}))

# =======================================================================
print("\n--- 2: the resume merges (N2) ---")
P2 = tempfile.mkdtemp(prefix="retell336_c_")
v2 = night(P2, "night")
mount(lore, P2, 3000.0, ANS)
lore._insights_one(v2, forced=True)
d0 = ins_of(lore, v2)
w1_before = json.dumps(d0["windows"]["1800"], sort_keys=True)
ch_before = [c["label"] for c in d0["chapters"]]

# the audit cuts window one and does NOT refill (the card is leaving)
lore._aud_retell(v2, [70.0], refill=False)
nd = ins_of(lore, v2, new=True)
check("the cut is staged, the served review untouched",
      set(nd["windows"]) == {"1800"} and nd["complete"] is False
      and set(ins_of(lore, v2)["windows"]) == {"0", "1800"})
check("and the cut NAMES itself - the ledger the resume reads",
      nd.get("retold") == ["0"])

# now a stale .new is what the retell landed on: it lost window one to
# an interruption. The served review still has it, and the ledger says
# only window zero was cut.
nd.pop("windows")["1800"]
# the staged doc carries the SERVED review's lineage, exactly as
# _aud_retell's copy does - a retell is the same telling, re-asked
json.dump({"v": 3, "windows": {}, "complete": False, "tries": 0,
           "gen": d0.get("gen"), "src_stt": d0.get("src_stt"),
           "retold": ["0"]},
          io.open(lore._ai_sidecar(v2, "ins") + ".new", "w",
                  encoding="utf-8"))
ASKS[:] = []
lore._insights_one(v2, forced=True)
d1 = ins_of(lore, v2)
check("only the CUT window is asked for - the other is carried in",
      [a for a in ASKS if a.startswith("w")] == ["w0"])
check("the review is whole again: 2 of 2, complete",
      d1["complete"] is True and set(d1["windows"]) == {"0", "1800"}
      and ins_of(lore, v2, new=True) is None)
check("the window the audit never touched is byte-identical",
      json.dumps(d1["windows"]["1800"], sort_keys=True) == w1_before)
check("and its chapters still read as they did",
      [c["label"] for c in d1["chapters"]] == ch_before)
check("the finished review carries no ledger forward",
      "retold" not in d1)

print("\n--- 2b: three windows, two of them dirty ---")
P3 = tempfile.mkdtemp(prefix="retell336_d_")
v3 = night(P3, "night", edges_n=3, vdur=5000.0)
ANS3 = {"w0": told("the first"), "w30": told("the second"),
        "w60": told("the third")}
mount(lore, P3, 5000.0, ANS3)
lore._insights_one(v3, forced=True)
d3 = ins_of(lore, v3)
w2_before = json.dumps(d3["windows"]["1800"], sort_keys=True)
check("three windows told", set(d3["windows"]) == {"0", "1800", "3600"})
lore._aud_retell(v3, [70.0, 3700.0], refill=False)
nd3 = ins_of(lore, v3, new=True)
check("both dirty windows are cut and named, the third left alone",
      nd3.get("retold") == ["0", "3600"]
      and set(nd3["windows"]) == {"1800"})
ASKS[:] = []
lore._insights_one(v3, forced=True)
d3b = ins_of(lore, v3)
check("exactly the two dirty windows are re-asked",
      sorted(a for a in ASKS if a.startswith("w")) == ["w0", "w60"])
check("3 of 3, complete, and the untouched window is unchanged",
      d3b["complete"] is True
      and set(d3b["windows"]) == {"0", "1800", "3600"}
      and json.dumps(d3b["windows"]["1800"], sort_keys=True) == w2_before)

# =======================================================================
print("\n--- 2c: a REBUILD is not a retell - the merge stays inside "
      "one lineage ---")
P8 = tempfile.mkdtemp(prefix="retell336_i_")
v8 = night(P8, "night", edges_n=3, vdur=5000.0)
mount(lore, P8, 5000.0, {"w0": told("the old first"),
                         "w30": told("the old second"),
                         "w60": told("the old third")})
lore._insights_one(v8, forced=True)
sp8 = lore._ai_sidecar(v8, "ins")
d8 = json.load(io.open(sp8, encoding="utf-8"))
# the served review is the OLD engine's work, read by an OLD ear
d8["gen"] = 2
d8["src_stt"] = dict(d8.get("src_stt") or {}, reader=5)
json.dump(d8, io.open(sp8, "w", encoding="utf-8"))
# and a rebuild is in flight: window zero re-described at the
# current generation, interrupted - and then an audit landed on that
# staged doc and cut the last window, so the ledger names a window
# the served review still holds in the old engine's words. Merging
# on the ledger alone would carry those words into the rebuild and
# stamp the lot as upgraded; the owing test would never ask again.
w0new = json.loads(json.dumps(d8["windows"]["0"]))
for sg in w0new["segments"]:
    sg["name"] = "the new first"
json.dump({"v": 3, "gen": 3, "src_stt": {"reader": 7},
           "windows": {"0": w0new}, "complete": False, "tries": 0,
           "retold": ["3600"]},
          io.open(sp8 + ".new", "w", encoding="utf-8"))
lore._DescServer = make_server({"w0": told("the new first"),
                                "w30": told("the new second"),
                                "w60": told("the new third")})
lore._DESC_KEEP["srv"] = None
ASKS[:] = []
lore._insights_one(v8, forced=True)
d8b = ins_of(lore, v8)
check("the superseded windows are re-described, never carried in",
      sorted(a for a in ASKS if a.startswith("w")) == ["w30", "w60"])
check("no word of the old telling survives in the upgraded review",
      d8b["complete"] is True and len(d8b["windows"]) == 3
      and not any("old" in c["label"] for c in d8b["chapters"]))
check("so the stamp it wears is honest - every window is this "
      "engine's and this ear's",
      d8b.get("gen") == lore._INS_GENERATION
      and (d8b.get("src_stt") or {}).get("reader") == 7)

# =======================================================================
print("\n--- 3: a retell that will not PARSE (N1 + N3 on one road) ---")
# THE SPEC'S OWN SHAPE: window zero told three real stretches; the
# audit corrects a line in it; the describer's answer for the retold
# window will not parse - twice per ask, exactly as his did. The law:
# an unparsed answer is no word at all, so the served telling is LEFT
# AS IT WAS, the retell spends its two tries, the night says so once,
# and nobody asks a third time. (Settling it as told-empty, the way a
# parsed empty answer is, completed the staged doc and swapped an
# empty window over the three stretches - the fix-first review
# measured chapters 6 -> 3 on this very fixture.)


def three(label, n=12):
    per = n // 3
    return json.dumps({"segments": [
        {"name": "%s %d" % (label, j), "what": "they play the match out",
         "topics": ["arena"], "from_line": j * per,
         "to_line": (n - 1 if j == 2 else (j + 1) * per - 1),
         "quote": ""} for j in range(3)], "moments": []})


ANS3S = {"w0": three("the first half"), "w30": told("the second half")}
P4 = tempfile.mkdtemp(prefix="retell336_e_")
v4 = night(P4, "night")
mount(lore, P4, 3000.0, dict(ANS3S))
lore._insights_one(v4, forced=True)
served0 = ins_of(lore, v4)
n_before = len(served0["windows"]["0"]["segments"])
chap_before = [c["label"] for c in served0["chapters"]]
check("the served review holds three real stretches in window zero",
      n_before == 3 and served0["complete"] is True)
# from here the describer refuses window zero, exactly as his did:
# two attempts, neither parses
lore._DescServer = make_server({"w0": "sorry, I cannot",
                                "w30": ANS["w30"]})
LOG[:] = []
ASKS[:] = []
lore._DESC_KEEP["srv"] = None
lore._AI["focus"] = None
lore._RETELL_QUIT.clear()
lore._aud_retell(v4, [70.0])
run1 = list(LOG)
nd4 = ins_of(lore, v4, new=True)
check("the spent ask is BANKED, not thrown away with the window",
      nd4 is not None and nd4["windows"].get("0") is not None
      and nd4["windows"]["0"]["segments"] == []
      and nd4["windows"]["0"]["asks"] == 1)
check("the window the audit never touched is still in the count",
      set(nd4["windows"]) == {"0", "1800"})
check("the log says what it asked for and what came back",
      any("did not parse" in m and "char(s) came back" in m
          and "token(s) over" in m for m in run1))
check("the unfinished line counts windows TOLD, not keys on disk",
      any("is unfinished: 1 of 2 window(s) done" in m for m in run1))
# one ASK, both of its parse attempts - and no other window touched
check("the refusal did not become a second describe",
      [a for a in ASKS if a.startswith("w")] == ["w0", "w0"])
check("BANKED IS NOT TOLD: the run spent a try (an unparsed answer "
      "is no progress), so the bound is reachable",
      int(nd4.get("tries") or 0) == 1)
check("the first empty retell still goes to the head of the queue",
      lore._AI.get("focus") == v4
      and any("head of the queue" in m for m in run1))
check("the served review is untouched after run one",
      json.dumps(ins_of(lore, v4), sort_keys=True)
      == json.dumps(served0, sort_keys=True))

LOG[:] = []
ASKS[:] = []
lore._DESC_KEEP["srv"] = None
owed_before = lore._ins_owing_raw(v4)
lore._insights_one(v4)              # the sweep's own beat, not forced
run2 = list(LOG)
d4 = ins_of(lore, v4)
nd4b = ins_of(lore, v4, new=True)
check("the second beat asks once more, again as a first telling",
      owed_before is True
      and [a for a in ASKS if a.startswith("w")] == ["w0", "w0"])
check("the staged doc stays UNFINISHED with its second try spent - "
      "never completed over a hole made of unparsed answers",
      nd4b is not None and nd4b.get("complete") is False
      and int(nd4b.get("tries") or 0) == 2
      and nd4b["windows"]["0"]["segments"] == []
      and nd4b["windows"]["0"]["asks"] == 2)
check("the SERVED review keeps its three stretches and its chapters "
      "('it is left as it was')",
      len(d4["windows"]["0"]["segments"]) == n_before
      and [c["label"] for c in d4["chapters"]] == chap_before
      and d4["complete"] is True)
check("no swap happened, so nothing was banked away either",
      not os.path.isfile(lore._ai_sidecar(v4, "ins") + ".v1")
      and not any("Described" in m for m in run2))
check("the N3 sentence is said ON THIS ROAD - the sweep's beat spent "
      "the second try, and nobody hoists after it",
      len([m for m in run2 if "came back empty twice" in m]) == 1
      and any("ask for it by name" in m for m in run2))
check("and the focus is let go with it",
      lore._AI.get("focus") is None)
check("the sweep's judge stops here: the retell bound is two, the "
      "upgrade's three, read off the same tries",
      lore._ins_owing_raw(v4) is False)
ASKS[:] = []
LOG[:] = []
lore._DESC_KEEP["srv"] = None
if lore._ins_owing_raw(v4):
    lore._insights_one(v4)
check("no third ask, by any road", ASKS == [])
lore._retell_head(v4, "the audit re-told part of it")
check("the audit's hoist refuses too, and says nothing twice",
      lore._AI.get("focus") is None and LOG == [])
# THE PRE-FIX WITNESS: 1fc336d on the same shape still owes the night
# after two beats (its bound is three, and every beat re-asks) - the
# circle this section closes.
P4b = tempfile.mkdtemp(prefix="retell336_e0_")
v4b = night(P4b, "night")
mount(lore_base, P4b, 3000.0, dict(ANS3S))
lore_base._insights_one(v4b, forced=True)
lore_base._DescServer = make_server({"w0": "sorry, I cannot",
                                     "w30": ANS["w30"]})
lore_base._DESC_KEEP["srv"] = None
lore_base._AI["focus"] = None
lore_base._aud_retell(v4b, [70.0])
lore_base._DESC_KEEP["srv"] = None
lore_base._insights_one(v4b)
check("(witness) 1fc336d still owes the same night after two empty "
      "retells - the bound was unreachable there",
      lore_base._ins_owing_raw(v4b) is True
      and lore._ins_owing_raw(v4) is False)

print("\n--- 3c: a retell that PARSES empty is told-empty, and the "
      "review completes (N1's law) ---")
P4c = tempfile.mkdtemp(prefix="retell336_e2_")
v4c = night(P4c, "night")
mount(lore, P4c, 3000.0, dict(ANS3S))
lore._insights_one(v4c, forced=True)
lore._DescServer = make_server({"w0": json.dumps({"segments": [],
                                                  "moments": []}),
                                "w30": ANS["w30"]})
LOG[:] = []
ASKS[:] = []
lore._DESC_KEEP["srv"] = None
lore._AI["focus"] = None
lore._aud_retell(v4c, [70.0])
run3 = list(LOG)
d4c = ins_of(lore, v4c)
check("two parsed empty answers settle the window: TOLD-EMPTY, done",
      d4c["complete"] is True and d4c["windows"]["0"]["segments"] == []
      and d4c["windows"]["0"]["asks"] == 2
      and d4c["windows"]["0"]["left"] == 0
      and [a for a in ASKS if a.startswith("w")] == ["w0", "w0"])
check("the review completes and the staged file is swapped in - the "
      "old telling banked first",
      ins_of(lore, v4c, new=True) is None
      and any("Described" in m for m in run3)
      and os.path.isfile(lore._ai_sidecar(v4c, "ins") + ".v1"))
check("the untold minutes are SAID, not hidden - the coverage gap "
      "names them", any(g.get("kind") == "untold"
                        for g in (d4c.get("cov") or {}).get("gaps") or []))
check("and the count SAYS it is short: a window that spent itself "
      "banks no 'left' to say so with, and half a night missing "
      "must not read as a whole telling",
      (d4c.get("cov") or {}).get("short") is True
      and (d4c.get("cov") or {}).get("frac") == 0.5)
check("the re-ask is COUNTED - the guard line no longer reads "
      "'0 coverage re-ask(s)' on the very road this drop is about",
      any("1 coverage re-ask(s)" in m for m in run3))
ASKS[:] = []
lore._DESC_KEEP["srv"] = None
if lore._ins_owing_raw(v4c):
    lore._insights_one(v4c)
check("and the sweep never comes back for a third ask",
      ASKS == [] and lore._ins_owing_raw(v4c) is False)
check("the N3 sentence has no place on a night that finished",
      not any("came back empty twice" in m for m in run3))

print("\n--- 3b: the second ask is a first telling, not 'the REST' ---")
P5 = tempfile.mkdtemp(prefix="retell336_f_")
v5 = night(P5, "night")
HEADS = []


def _spy(answers):
    Base = make_server(answers)

    class Spy(Base):
        def ask(self, system, user, max_tokens=900, schema=None,
                images=None, **kw):
            if "runs from minute 0 to minute" in user:
                HEADS.append(user)
            return Base.ask(self, system, user, max_tokens, schema,
                            images, **kw)
    return Spy


mount(lore, P5, 3000.0, dict(ANS))
lore._insights_one(v5, forced=True)
lore._DescServer = _spy({"w0": "not json at all", "w30": ANS["w30"]})
lore._DESC_KEEP["srv"] = None
HEADS[:] = []
lore._aud_retell(v5, [70.0])
lore._DESC_KEEP["srv"] = None
lore._insights_one(v5)
# two asks, each spending both of its parse attempts
check("both asks for the empty window were made", len(HEADS) == 4)
check("neither was dressed as the REST of a window already described",
      all("REST of a window" not in h for h in HEADS))
check("and both carried the window's evidence head",
      all("The game being played is" in h for h in HEADS))

# =======================================================================
print("\n--- 4: the head of the queue is bounded (N3) ---")
P6 = tempfile.mkdtemp(prefix="retell336_g_")
v6 = night(P6, "night")
mount(lore, P6, 3000.0, ANS)
sp6 = lore._ai_sidecar(v6, "ins")
json.dump({"v": 3, "complete": True, "chapters": [{"t": 0, "label": "x"}],
           "windows": {"0": {}, "1800": {}}},
          io.open(sp6, "w", encoding="utf-8"))


def stage(tries):
    json.dump({"v": 3, "complete": False, "tries": tries,
               "windows": {"1800": {}}, "retold": ["0"]},
              io.open(sp6 + ".new", "w", encoding="utf-8"))


lore._AI["focus"] = None
LOG[:] = []
stage(0)
lore._retell_head(v6, "the audit re-told part of it")
check("a first retell goes to the head of the queue",
      lore._AI.get("focus") == v6
      and any("head of the queue" in m for m in LOG))
lore._AI["focus"] = None
LOG[:] = []
stage(1)
lore._retell_head(v6, "the audit re-told part of it")
check("so does the second", lore._AI.get("focus") == v6)
lore._AI["focus"] = v6                 # parked in the one slot...
LOG[:] = []
stage(2)
lore._retell_head(v6, "the audit re-told part of it")
check("after two empty retells the night is left as it was - and "
      "the focus it held is let go",
      lore._AI.get("focus") is None
      and not any("head of the queue" in m for m in LOG))
check("and it says so - once, in his words",
      len([m for m in LOG if "came back empty twice" in m]) == 1
      and any("ask for it by name" in m for m in LOG))
LOG[:] = []
lore._retell_head(v6, "the audit re-told part of it")
check("the second time it says nothing at all",
      LOG == [] and lore._AI.get("focus") is None)
rt = func_src("_aud_retell")
check("BOTH of the retell's hoists go through the bound",
      rt.count("_retell_head(") == 2 and "_ai_ask_first(" not in rt)

# =======================================================================
print("\n--- 5: a stale .new goes to the attic on boot (N4) ---")
P7 = tempfile.mkdtemp(prefix="retell336_h_")
mount(lore, P7, 3000.0, ANS)
COMPLETE = {"v": 3, "complete": True, "chapters": [{"t": 0, "label": "x"}],
            "windows": {"0": {}}, "segments": []}
PART = {"v": 3, "complete": False, "tries": 0, "windows": {}}
made = {}
# "respelled" is the shape his shelf actually holds: a LIVE staged
# retell (tries 0, windows described) whose served review was
# rewritten in place afterwards by _aud_apply_names, so the .new is
# the older file by the clock and by nothing else. Measured read-only
# on the shelf, 8 Sep: 90 staged files, 7 older than their review,
# and all 3 that passed the old gate were of exactly this kind.
for nm, base, newer, tries in (("stale", COMPLETE, False, 3),
                               ("live", COMPLETE, True, 0),
                               ("respelled", COMPLETE, False, 0),
                               ("midbuild", PART, False, 3)):
    v = night(P7, nm)
    sp = lore._ai_sidecar(v, "ins")
    json.dump(base, io.open(sp, "w", encoding="utf-8"))
    json.dump({"v": 3, "windows": {}, "complete": False,
               "tries": tries},
              io.open(sp + ".new", "w", encoding="utf-8"))
    old = time.time() - 600
    if newer:
        os.utime(sp, (old, old))            # the .new is the newer file
    else:
        os.utime(sp + ".new", (old, old))   # ... and here the older one
    made[nm] = (v, sp)
lore._library_dirs = lambda out: [(P7, "game")]
lore._scan_dir_mp4s = lambda d, k: [{"path": v} for v, _s in made.values()]
served_before = {nm: (io.open(sp, encoding="utf-8").read(),
                      os.path.getmtime(sp)) for nm, (_v, sp) in made.items()}
LOG[:] = []
moved = lore._ins_new_sweep()
check("the stale .new is gone from beside the review",
      moved == 1 and not os.path.isfile(made["stale"][1] + ".new"))
check("it was FILED, never deleted",
      any(f.startswith("stale.ins.new.") for f in
          os.listdir(lore._attic_dir())))
check("a .new newer than its review is a live resume point, left alone",
      os.path.isfile(made["live"][1] + ".new"))
check("a .new beside an unfinished review IS the work in progress",
      os.path.isfile(made["midbuild"][1] + ".new"))
check("a staged retell with tries left is LIVE however old its clock "
      "reads - the served review is rewritten by writers that never "
      "touch the .new",
      os.path.isfile(made["respelled"][1] + ".new"))
check("no served review was touched - not a byte, not a clock",
      all(io.open(sp, encoding="utf-8").read() == served_before[nm][0]
          and os.path.getmtime(sp) == served_before[nm][1]
          for nm, (_v, sp) in made.items()))
check("it says so once", len([m for m in LOG if "stale part-description"
                              in m]) == 1)
LOG[:] = []
check("and a second pass finds nothing to do",
      lore._ins_new_sweep() == 0 and LOG == [])
mig = func_src("_shelf_migrations")
check("the boot walk runs it once per RUN, not once per shelf",
      "_NEW_SWEPT" in mig and "_ins_new_sweep()" in mig
      and "sweep = not _NEW_SWEPT[0]" in mig)
lore._library_dirs = lambda out: []
lore._scan_dir_mp4s = lambda d, k: []

print("\n--- 5b: a refused upgrade keeps its marker ---")
# an older-engine review with the eye installed: the owing judge reads
# a tries-3 .new as "the upgrade refused three times - the old review
# stays". Filing that .new took the marker with it and re-owed a full
# re-describe on the next beat (the fix-first review measured moved=1,
# owed False -> True).
P7b = tempfile.mkdtemp(prefix="retell336_h2_")
mount(lore, P7b, 3000.0, ANS)
lore._desc_mmproj = lambda: "mmproj"        # the eye is installed
v7 = night(P7b, "oldgen")
sp7 = lore._ai_sidecar(v7, "ins")
json.dump({"v": 3, "complete": True, "chapters": [{"t": 0, "label": "x"}],
           "windows": {"0": {}}, "gen": 2, "cov": {"owed": False},
           "src_stt": {"reader": 7}, "tgen": 1},
          io.open(sp7, "w", encoding="utf-8"))
json.dump({"v": 3, "windows": {}, "complete": False, "tries": 3},
          io.open(sp7 + ".new", "w", encoding="utf-8"))
old = time.time() - 600
os.utime(sp7 + ".new", (old, old))
owed_a = lore._ins_owing_raw(v7)
lore._library_dirs = lambda out: [(P7b, "game")]
lore._scan_dir_mp4s = lambda d, k: [{"path": v7}]
LOG[:] = []
mv7 = lore._ins_new_sweep()
owed_b = lore._ins_owing_raw(v7)
lore._library_dirs = lambda out: []
lore._scan_dir_mp4s = lambda d, k: []
check("the sweep leaves the tries-3 .new beside an older-engine review "
      "while the eye is installed - it IS the marker",
      mv7 == 0 and os.path.isfile(sp7 + ".new") and LOG == [])
check("so the owing judge answers the same before and after: not owed",
      owed_a is False and owed_b is False)
lore._desc_mmproj = lambda: None

# =======================================================================
print("\n--- 6: the laws this drop must not break ---")
sw = func_src("_ins_new_sweep")
check("the sweep writes no sidecar and moves no clock",
      "_atomic_write_json" not in sw and "os.utime" not in sw
      and "os.remove" not in sw and "shutil.move" in sw)
check("it undoes no count: no _AUD_V, no reader bump, and the one "
      "cache it pops is the one whose input it changed",
      "_AUD_V" not in sw and "stt.reader" not in sw
      and sw.count("_INS_OWE_CACHE.pop") == 1
      and "_AUD_OWE_CACHE" not in sw)
ins = func_src("_insights_one")
check("N1 banks the ask on the window, not in a second counter",
      "asked > _asked0" in ins and "\"dry\"" not in ins
      and "'dry'" not in ins)
check("N2's merge is gated on the ledger - a .new from before this "
      "drop resumes exactly as it does today",
      'isinstance(wdoc.get("retold"), list)' in ins
      and "not _wiped" in ins)
check("a cut window is never resurrected by the merge",
      "_k5 not in _retold" in ins)
check("the ledger rides the staged doc only while it is unfinished",
      "if _retold and not complete:" in ins)
head = func_src("_retell_head")
check("the bound reads the tries already on disk - no new counter",
      '.get("tries")' in head and "_t < 2" in head)
owe = func_src("_ins_owing_raw")
check("and the sweep's judge stops a RETELL at the same bound (two), "
      "an upgrade at three - one counter, read in two places",
      '(2 if isinstance(nd.get("retold"), list) else 3)' in owe)
check("told-empty is a PARSED answer's verdict, never an unparsed one's",
      "if got is not None and not mapped and asked >= 2:" in ins
      and "if not mapped and asked >= 2:" not in ins)
check("the bound is said where it is reached: the describe that spends "
      "the second try quits the night itself",
      "_retell_quit(video_path)" in ins
      and func_src("_retell_quit").count("_RETELL_QUIT.add") == 1)

check("N2's merge stays inside ONE lineage - a staged rebuild is "
      "never handed the served review's older windows",
      'int(prior.get("gen") or 0)' in ins
      and '>= int(wdoc.get("gen") or 0)' in ins
      and '(wdoc.get("src_stt") or {}).get("reader")' in ins)
check("N4 judges a .new by its spent budget, not by a clock some "
      "other writer can move - and it keeps the clock test too",
      'if int(nd.get("tries") or 0) < 3:' in sw
      and "os.path.getmtime(np0) >= os.path.getmtime(sp)" in sw)
check("the continuation counter counts re-asks, not 'not first'",
      "_cont = asked > 0" in ins and "if not _first:" not in ins)
check("and cov.short believes the gaps a spent window leaves",
      'or any(g.get("kind") == "untold"' in ins)
check("N4 never files the refused-upgrade marker",
      'if int(d.get("gen") or 2) < _INS_GENERATION' in sw
      and "_desc_mmproj() is not None" in sw)

# =======================================================================
print("\n--- 7: the audit that never settles (N5) - the captain shape ---")
# built from that night's own shape: an empty review (stamped, as 1fc336d
# stamps it), three marks, no claims, no names, no strikes - and an
# audit that finds nothing to do, every six seconds, for three hours.
P9 = tempfile.mkdtemp(prefix="retell336_j_")
mount(lore, P9, 300.0, {})
mount(lore_base, P9, 300.0, {})
for _m in (lore, lore_base):
    _m._stt_reader_of = lambda p: 4
v9 = os.path.join(P9, "harbor.mp4")
io.open(v9, "w").write("x")
for k, body in (("hl", {"moments": [{"t": 33.8}, {"t": 51.3}, {"t": 70.0}],
                        "events": [{"t": 33.8}, {"t": 51.3}, {"t": 70.0}]}),
                ("sns", {"v": 1}), ("vis", {"v": 1}), ("lvl", {"v": 1}),
                ("stt", {"reader": 4, "segments": [], "sources": {}})):
    json.dump(body, io.open(lore._ai_sidecar(v9, k), "w", encoding="utf-8"))
ins9 = lore._ai_sidecar(v9, "ins")
aud9 = lore._ai_sidecar(v9, "aud")
LOG[:] = []
lore._insights_one(v9)                      # the empty road: stamped
d9 = json.load(io.open(ins9, encoding="utf-8"))
check("the empty review is stamped with the ear it was built on",
      d9.get("empty") and (d9.get("src_stt") or {}).get("reader") == 4)


def audit_put(mod):
    """A _put-shaped audit: complete, no fixes, no strikes, no names."""
    json.dump({"v": mod._AUD_V, "complete": True, "tries": 0,
               "thread": [{"t": 33.8}, {"t": 51.3}], "dropped": [],
               "merged": [], "names": [], "garble": [], "fixes": [],
               "saw": {"marks": 3, "fixed": 0, "struck": 0},
               "src": mod._aud_src(v9)},
              io.open(aud9, "w", encoding="utf-8"))


audit_put(lore)
check("the audit's own write satisfies the owing judge",
      lore._aud_owing(v9) is False and lore._aud_settled(v9) is False)
# the loop's shape: the review's clock moves (rewritten byte-identical
# by whatever road) and the audit is owed again - on 1fc336d and here
time.sleep(0.6)
os.utime(ins9, None)
check("a moved review clock re-owes the audit on 1fc336d (the loop's "
      "engine) and, before the backstop, here too",
      lore_base._aud_owing(v9) is True and lore._aud_owing(v9) is True)
# two audits inside ten minutes that changed nothing
lore._AI["focus"] = v9
LOG[:] = []
first = lore._aud_settle_note(v9, 0, 0, [], [], 0)
audit_put(lore)
time.sleep(0.6)
os.utime(ins9, None)
second = lore._aud_settle_note(v9, 0, 0, [], [], 0)
check("the first change-free audit is only noted, the second settles",
      first is False and second is True)
check("said once, in his words, and the focus is released",
      len([m for m in LOG if "has nothing left to settle - leaving it"
           in m]) == 1 and lore._AI.get("focus") is None)
check("the third is refused: both judges the sweep and the thinking "
      "worker read answer settled, however the review's clock moves",
      lore._aud_owing(v9) is False and lore._aud_owing_swept(v9) is False)
time.sleep(0.6)
os.utime(ins9, None)
check("... and stays refused while the layers stand (a byte-identical "
      "review with a new clock is not a change)",
      lore._aud_owing(v9) is False)
check("(witness) 1fc336d re-owes the same night on that clock - the "
      "third audit of 1,776",
      lore_base._aud_owing(v9) is True)
LOG[:] = []
check("a third change-free audit says nothing more",
      lore._aud_settle_note(v9, 0, 0, [], [], 0) is True and LOG == [])
# a REAL change (the transcript re-read) makes it a night again
time.sleep(0.6)
json.dump({"reader": 5, "segments": [], "sources": {}},
          io.open(lore._ai_sidecar(v9, "stt"), "w", encoding="utf-8"))
check("a layer that truly moved reopens the night - the set is not "
      "an owe cache, it is a signature of what was left",
      lore._aud_owing(v9) is True and v9 not in lore._AUD_SETTLED)
check("an audit that FIXED something never settles the night",
      lore._aud_settle_note(v9, 1, 0, [], [], 0) is False
      and lore._aud_settle_note(v9, 0, 0, [], [], 0) is False)
ao = func_src("_aud_owing")
check("the judge reads the settled set first, after the honest-review "
      "gate; asking by name never reads this judge",
      "if _aud_settled(video_path):" in ao
      and "_aud_settle_note(" in func_src("_audit_one")
      and "_resp = _aud_apply_names(video_path, names)"
      in func_src("_audit_one"))

print("\n--- 7b: the empty review keeps its clock when nothing changed ---")
for _m in (lore, lore_base):
    _m._stt_reader_of = lambda p: 5          # the re-read ear above
mt_a = os.path.getmtime(ins9)
time.sleep(0.6)
lore._insights_one(v9, forced=True)         # the doc on disk differs
mt_b = os.path.getmtime(ins9)               # (reader 5 now): written
time.sleep(0.6)
lore._insights_one(v9, forced=True)         # byte-identical: left alone
mt_c = os.path.getmtime(ins9)
check("a changed transcript rewrites the empty review (new stamp)",
      mt_b > mt_a and json.load(io.open(ins9, encoding="utf-8"))
      .get("src_stt", {}).get("reader") == 5)
check("a forced re-describe of an unchanged empty review does not "
      "move its clock (the mtime law) - so the audit is not re-owed "
      "by it", mt_c == mt_b)
vb9 = os.path.join(P9, "harbor.mp4")        # the twin on the same files
time.sleep(0.6)
lore_base._insights_one(vb9, forced=True)
check("(witness) 1fc336d rewrites it and moves the clock",
      os.path.getmtime(ins9) > mt_c)

# =======================================================================
print("\n--- 8: the cost, measured (N6) ---")
P10 = tempfile.mkdtemp(prefix="retell336_k_")
lg = os.path.join(P10, "lore.log")
LINES = [
    "[23:40:00] AFK catch-up: no keyboard, mouse or controller for 10 "
    "minutes, so the tome is taking the whole suite - sound, transcripts, "
    "the review and the audit. Anything you had paused is remembered.",
    "[23:50:00] Described arena_a.mp4: 9 stretch(es) across 2 window(s) "
    "- the first night",
    "[00:10:00] The eye on arena_a.mp4: 24 look(s) of 24 wanted, 5 "
    "place(s), 22 sighting(s), 3 retried - 8m24s.",
    "[00:30:00] Described arena_b.mp4: 8 stretch(es) across 2 window(s) "
    "- the second night",
    "[00:50:00] The eye on arena_b.mp4: 24 look(s) of 24 wanted, 1 "
    "place(s), 14 sighting(s) - 8m00s.",
    "[01:20:00] Described arena_a.mp4: 9 stretch(es) across 2 window(s) "
    "- the first night, retold",
    "[01:40:00] AFK countdown reset at 120 min by keyboard/mouse "
    "(cursor travelled 16 px).",
    "[01:40:00] AFK catch-up ended - you are back. Everything is back "
    "exactly as you left it.",
    "[01:41:00] Windows game database: 152 titles recognised.",
]
io.open(lg, "w", encoding="utf-8").write("\n".join(LINES) + "\n")
NOW = time.time()
os.utime(lg, (NOW, NOW))
rows = lore._log_stamped(lg, NOW)
check("every line gets a clock, and midnight is read off the roll-over "
      "(23:50 -> 00:10 is twenty minutes, not minus a day)",
      len(rows) == len(LINES)
      and abs((rows[2][0] - rows[1][0]) - 1200) < 1
      and abs((rows[-1][0] - rows[0][0]) - 7260) < 1)
w = lore._ai_week_rate(paths=[lg], now=NOW)
check("two hours away, two distinct nights finished in them (three "
      "describes - one was a retell), 48 looks timed",
      w["afk_s"] == 7200 and w["nights"] == 2 and w["describes"] == 3
      and w["eye_looks"] == 48 and w["measured"] is True)
check("a look's price is the eye's own lines: (504 + 480) / 48",
      w["per_look_s"] == 20.5)
e = lore._ai_week_eta(10, w)
check("ten remaining nights at two per two hours = ten hours",
      e["eta_s"] == 36000)
check("nothing left = nothing to time", lore._ai_week_eta(0, w)["eta_s"]
      is None)
# under an hour measured: the answer says so instead of guessing
SHORT = [LINES[0].replace("23:40", "23:50"), LINES[1], LINES[7]
         .replace("01:40", "00:10")]
lg2 = os.path.join(P10, "short.log")
io.open(lg2, "w", encoding="utf-8").write("\n".join(SHORT) + "\n")
os.utime(lg2, (NOW, NOW))
w2 = lore._ai_week_rate(paths=[lg2], now=NOW)
check("twenty minutes away is 'not enough measured yet', never a number",
      w2["afk_s"] == 1200 and w2["measured"] is False
      and lore._ai_week_eta(10, w2)["eta_s"] is None)
# a window still open when the log stops earns hours only to the last
# line written, never to now
lg3 = os.path.join(P10, "open.log")
io.open(lg3, "w", encoding="utf-8").write("\n".join(LINES[:2]) + "\n")
import datetime as _dt2
NOW3 = _dt2.datetime.combine(_dt2.date.today(),
                             _dt2.time(23, 55, 0)).timestamp()
os.utime(lg3, (NOW3 - 300, NOW3 - 300))     # last written at 23:50
w3 = lore._ai_week_rate(paths=[lg3], now=NOW3)
check("an open window runs to the log's last write (23:50), not to "
      "now (23:55)", w3["afk_s"] == 600)
# the tally counts the eye's backlog only when there is an eye
P11 = tempfile.mkdtemp(prefix="retell336_l_")
mount(lore, P11, 3000.0, ANS)
va, vb = night(P11, "seen"), night(P11, "unseen")
json.dump({"v": 1, "complete": True, "looks": [1] * 24,
           "counters": {"wanted": 24}},
          io.open(lore._ai_sidecar(va, "vis"), "w", encoding="utf-8"))
lore._library_dirs = lambda out: [(P11, "game")]
lore._scan_dir_mp4s = lambda d, k: [{"path": va, "dur": 3000.0},
                                    {"path": vb, "dur": 3000.0}]
lore._AI["_tally"] = None
check("no eye installed: the backlog is not a number",
      lore._ai_tally().get("eye_left") is None)
lore._desc_mmproj = lambda: "mmproj"
lore._AI["_tally"] = None
check("eye installed: one of the two nights still owes a look",
      lore._ai_tally().get("eye_left") == 1)
lore._library_dirs = lambda out: []
lore._scan_dir_mp4s = lambda d, k: []
# the page's call: the setting, the measured price, the tally's count
import types as _types
_api = lore._JsApi.__new__(lore._JsApi)
_api._ctl = _types.SimpleNamespace(session=None)
_wr = lore._ai_week_rate
lore._ai_week_rate = lambda paths=None, now=None: dict(w)
ec = _api.eye_cost()
lore._ai_week_rate = _wr
lore._desc_mmproj = lambda: None
check("eye_cost hands the page the setting, the measured price and the "
      "backlog it would have to pay for",
      ec["looks"] == int(lore.SETTINGS.get("eye_looks", 24))
      and ec["per_look_s"] == 20.5 and ec["design_s"] == 21
      and ec["owed"] == 1 and ec["eye"] is True)
check("the default is not touched - it is his call",
      lore.DEFAULTS.get("eye_looks") == 24)
st = func_src("ai_status")
check("the Working row carries the week's arithmetic for the describer",
      '"week": (_ai_week_eta(k["left"])' in st)
UI = io.open(os.path.join(ROOT, "ui.html"), encoding="utf-8").read()
check("the tally says the sentence, and says 'not enough measured yet' "
      "under an hour",
      "at the rate of the last seven days (" in UI
      and "not enough measured yet" in UI
      and "would take about '+dur(k.week.eta_s)" in UI)
check("Settings has the eye_looks control with the price line under it",
      "ctlNum('eye_looks',1,60)" in UI and "api.eye_cost" in UI
      and "min per night" in UI
      and "still owed a look would take" in UI)
check("the harness's mock api answers eye_cost too",
      "eye_cost:async()=>" in UI)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
