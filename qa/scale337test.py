# -*- coding: utf-8 -*-
"""3.37 drop O, item O1 - THE SCALE SAYS WHAT IT MEANS.

His word, 13 Sep: "silver should be for old versions of the suite.. like
if silver describe it should mean old version of describe.. same with
audit.. right now its silver describe and when i hover it tells me its
silver because its not audited??? that makes no sense".

Until this drop have_flags set the DESCRIBE pen to silver whenever the
AUDIT was not gold. Now all four marks obey one law: gold = the pass
exists and is current; silver = it exists but an older version made it
or its input changed since (and the why says which, and what happens
next); dark = it does not exist. Never silver because a DIFFERENT pass
is missing.

Proven on the real have_flags over tempdir nights, with the witness
lifted from the PARITY_BASE showing the same no-audit night silver
before. Nothing under D:\\Records is read or written; the names are
game words, never a person.
"""
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

# a suite must pen the library walk (aud302's law)
lore._library_dirs = lambda out: []
lore._scan_dir_mp4s = lambda d, k: []
lore.log = lambda m: None
lore.load_settings()
lore.save_settings = lambda *a, **k: None

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
USRC = io.open(os.path.join(ROOT, "ui.html"), encoding="utf-8").read()

# THE PARITY BASE IS A COMMIT, NOT HEAD. 01f0a49 is 3.36, the tree his
# 13 Sep word was measured on; HEAD would make the witness vanish the
# moment this drop lands.
PARITY_BASE = "01f0a49"


def mount(mod, td, eye):
    """have_flags' doors onto the machine, closed: sidecars on a
    tempdir, the eye mounted or not by a knob, the owing caches cold."""
    mod._ai_sidecar = (lambda p, k, _t=td:
                       os.path.join(_t, os.path.basename(p) + "." + k
                                    + ".json"))
    mod._desc_mmproj = (lambda: r"C:\mock\mmproj.gguf") if eye \
        else (lambda: None)
    mod._library_dirs = lambda out: []
    mod._scan_dir_mp4s = lambda d, k: []
    mod.log = lambda m: None
    mod._INS_OWE_CACHE.clear()
    if hasattr(mod, "_AUD_OWE_CACHE"):
        mod._AUD_OWE_CACHE.clear()
    api = mod._JsApi.__new__(mod._JsApi)
    api._safe_path = lambda p: p
    return api


def night(mod, td, name, ins=None, aud=None, covers=True, new=None):
    """A video, its review, optionally a staged .new and an audit whose
    src.ins clock matches the review (covers) or predates it."""
    p = os.path.join(td, name + ".mp4")
    with io.open(p, "wb") as fh:
        fh.write(b"x")
    if ins is not None:
        with io.open(mod._ai_sidecar(p, "ins"), "w",
                     encoding="utf-8") as fh:
            fh.write(json.dumps(ins))
    if new is not None:
        with io.open(mod._ai_sidecar(p, "ins") + ".new", "w",
                     encoding="utf-8") as fh:
            fh.write(json.dumps(new))
    if aud is not None:
        aud = dict(aud)
        clock = round(os.path.getmtime(mod._ai_sidecar(p, "ins")), 1)
        aud["src"] = {"ins": clock if covers else clock - 100.0}
        with io.open(mod._ai_sidecar(p, "aud"), "w",
                     encoding="utf-8") as fh:
            fh.write(json.dumps(aud))
    return p


CH = [{"t": 0, "name": "the arena match"}]
G = lore._INS_GENERATION
A = lore._AUD_V


def current(**kw):
    """A whole, counted, titled review by the installed describer -
    nothing the owing judge could want from it."""
    d = {"complete": True, "chapters": CH, "gen": G,
         "cov": {"frac": 1.0}, "tgen": lore._TITLE_GEN}
    d.update(kw)
    return d


# =======================================================================
print("--- 1: the pen with the eye mounted ---")
TD = tempfile.mkdtemp(prefix="scale337_")
api = mount(lore, TD, eye=True)
CALLS = []
_real_owing = lore._ins_owing
lore._ins_owing = lambda p, _r=_real_owing: (CALLS.append(p), _r(p))[1]

n_gold = night(lore, TD, "gold_no_audit", ins=current())
n_old = night(lore, TD, "older_gen", ins=current(gen=G - 1))
n_new = night(lore, TD, "retold", ins=current(),
              new={"windows": {"0": {}}, "complete": False, "tries": 0,
                   "retold": ["0"], "gen": G})
n_fresh = night(lore, TD, "fresh", ins={"complete": True, "chapters": CH,
                                        "gen": G})
n_aud_old = night(lore, TD, "aud_older_auditor", ins=current(),
                  aud={"complete": True, "v": A - 1}, covers=True)
n_aud_pre = night(lore, TD, "aud_predates", ins=current(),
                  aud={"complete": True, "v": A}, covers=False)
n_aud_gold = night(lore, TD, "aud_gold", ins=current(),
                   aud={"complete": True, "v": A}, covers=True)
n_empty = night(lore, TD, "empty", ins={"complete": True, "empty": True,
                                        "chapters": [], "gen": G})
n_gave = night(lore, TD, "gave_up", ins={"failed": True, "tries": 3,
                                         "chapters": [], "windows": {}})
n_none = night(lore, TD, "never")

f = api.have_flags([n_gold, n_old, n_new, n_fresh, n_aud_old, n_aud_pre,
                    n_aud_gold, n_empty, n_gave, n_none])

r = f[n_gold]
check("a current, whole description with NO audit is GOLD - the audit "
      "mark is dark, not the pen silver",
      r["ins_lvl"] == 2 and r["ins"] is True and r["ins_why"] == ""
      and r["aud_lvl"] == 0 and r["aud"] is False and r["aud_why"] == "")
r = f[n_old]
check("described by an older version, eye mounted -> SILVER 'described "
      "by an older version (v%d; v%d is installed) - it will be told "
      "again on its own'" % (G - 1, G),
      r["ins_lvl"] == 1 and r["ins_why"] ==
      "described by an older version (v%d; v%d is installed) - it will "
      "be told again on its own" % (G - 1, G))
r = f[n_new]
check("a live .new with a retold ledger -> SILVER 'the audit corrected "
      "lines inside it - those minutes are being told again'",
      r["ins_lvl"] == 1 and r["ins_why"] ==
      "the audit corrected lines inside it - those minutes are being "
      "told again")
r = f[n_fresh]
check("a review that never counted its coverage (owed, no .new) -> "
      "SILVER 'a fresh telling is owed'",
      r["ins_lvl"] == 1 and r["ins_why"] == "a fresh telling is owed")
r = f[n_aud_old]
check("audited by v%d against this description -> aud SILVER 'audited "
      "by v%d; auditor v%d is installed - it will be audited again', "
      "and the pen stays GOLD" % (A - 1, A - 1, A),
      r["aud_lvl"] == 1 and r["aud_v"] == A - 1 and r["aud_why"] ==
      "audited by v%d; auditor v%d is installed - it will be audited "
      "again" % (A - 1, A) and r["ins_lvl"] == 2)
r = f[n_aud_pre]
check("an audit whose src.ins predates the description -> aud SILVER "
      "'it read an older description - it will be audited again', pen "
      "GOLD",
      r["aud_lvl"] == 1 and r["aud_why"] ==
      "it read an older description - it will be audited again"
      and r["ins_lvl"] == 2)
r = f[n_aud_gold]
check("a current audit over a current description: both GOLD, no why",
      r["aud_lvl"] == 2 and r["ins_lvl"] == 2 and r["aud_why"] == ""
      and r["ins_why"] == "")
r = f[n_empty]
check("honestly empty -> pen DARK 'nothing here to tell', audit dark",
      r["ins_lvl"] == 0 and r["ins_why"] ==
      "described - the tome found nothing here to tell"
      and r["aud_lvl"] == 0)
r = f[n_gave]
check("gave up -> pen DARK 'gave up after three tries ...'",
      r["ins_lvl"] == 0
      and r["ins_why"].startswith("gave up after three tries"))
r = f[n_none]
check("never described -> dark, no reason", r["ins_lvl"] == 0
      and r["ins_why"] == "" and r["aud_lvl"] == 0)
check("_ins_owing was never asked about the night without a review file "
      "nor the honestly-empty one (a batch of 300 stays cheap)",
      n_none not in CALLS and n_empty not in CALLS)
check("...the ONE row without a description it is asked about is the "
      "gave-up night: 3.36's dark-pen branch tells 'gave up' from 'tries "
      "left' by the same judge (the exception, named)",
      n_gave in CALLS)
check("...and was asked about every night that carries a description",
      all(p in CALLS for p in (n_gold, n_old, n_new, n_fresh, n_aud_old,
                               n_aud_pre, n_aud_gold)))
whys = [f[p]["ins_why"] for p in f]
check("no ins_why says 'audit' except the corrected-lines case",
      all("audit" not in w or w.startswith("the audit corrected lines")
          for w in whys)
      and any(w.startswith("the audit corrected lines") for w in whys))
check("'the audit is owed again' and 'no audit has read' are gone from "
      "the pen", not any("no audit has read" in w or "owed again" in w
                         for w in whys))

# =======================================================================
print("--- 2: the pen without the eye ---")
lore._ins_owing = _real_owing
api = mount(lore, TD, eye=False)
r = api.have_flags([n_old, n_gold])
check("an older-version review with no eye mounted is not owed -> "
      "SILVER '... - ask for it by name to bring it up to date'",
      r[n_old]["ins_lvl"] == 1 and r[n_old]["ins_why"] ==
      "described by an older version (v%d; v%d is installed) - ask for "
      "it by name to bring it up to date" % (G - 1, G))
check("the current one stays GOLD", r[n_gold]["ins_lvl"] == 2)
n_old3 = night(lore, TD, "older_refused", ins=current(gen=G - 1),
               new={"windows": {}, "complete": False, "tries": 3,
                    "gen": G})
api = mount(lore, TD, eye=True)
r = api.have_flags([n_old3])[n_old3]
check("the upgrade refused three times (eye mounted): silver, 'ask for "
      "it by name' - the sweep will not bring it up on its own",
      r["ins_lvl"] == 1 and r["ins_why"].endswith(
          "ask for it by name to bring it up to date"))

# =======================================================================
print("--- 2b: a staged .new without the audit's ledger is his own "
      "press ---")
api = mount(lore, TD, eye=True)
n_redo = night(lore, TD, "redo_by_name", ins=current(),
               new={"windows": {"0": {}}, "complete": False, "tries": 0,
                    "gen": G})
n_redo1 = night(lore, TD, "redo_by_name_try1", ins=current(),
                new={"windows": {"0": {}}, "complete": False, "tries": 1,
                     "gen": G})
r = api.have_flags([n_redo, n_redo1, n_new])
check("Describe it pressed on a finished night (a live .new at the "
      "current gen, no 'retold' ledger) -> SILVER 'it is being described "
      "again - asked by name' - never an audit that did not run",
      r[n_redo]["ins_lvl"] == 1 and r[n_redo]["ins_why"] ==
      "it is being described again - asked by name"
      and "audit" not in r[n_redo]["ins_why"])
check("...the same redo with one try spent says the same",
      r[n_redo1]["ins_lvl"] == 1 and r[n_redo1]["ins_why"] ==
      "it is being described again - asked by name")
check("...while the audit's retell (the ledger present) still says 'the "
      "audit corrected lines inside it'",
      r[n_new]["ins_lvl"] == 1
      and r[n_new]["ins_why"].startswith("the audit corrected lines"))

# =======================================================================
print("--- 3: the source ---")
hf_i = SRC.find("    def have_flags(self, paths):")
hf = SRC[hf_i:SRC.find("\n    def ", hf_i + 10)]
check("have_flags no longer says 'no audit has read this description' "
      "and does not read the audit's level into the pen",
      "no audit has read" not in hf
      and 'row["ins_lvl"] = 2 if row["aud_lvl"] == 2 else 1' not in hf
      and "13 Sep" in hf)
check("the 'if not _has_desc: aud_lvl = 0' block stays",
      hf.count('                row["aud_lvl"] = 0\n'
               '                row["aud"] = False\n'
               '                row["aud_why"] = ""\n') == 1)
check("the describe's held-audit line no longer promises a silver pen",
      "stays silver until the audit lane runs" not in SRC
      and SRC.count("audit mark stays dark until the audit lane") == 1)
check("no owe cache, generation or auditor version moved (count-undoing)",
      lore._INS_GENERATION == 3 and lore._AUD_V == 7
      and lore._STT_READER == 7)
check("ui.html's mock carries the new why on its silver pen",
      "ins_why:'described by an older version (v2; v3 is installed) '"
      in USRC and "no audit has read this description yet" not in USRC)
check("ui.html's quick-look never says 'described, audit owed'",
      "described, audit owed" not in USRC
      and "the audit has read this version" not in USRC)

# =======================================================================
print("--- 4: the witness, %s ---" % PARITY_BASE)
BASE_PY = os.path.join(tempfile.mkdtemp(prefix="scale337_base_"),
                       "lore_base.py")
io.open(BASE_PY, "wb").write(subprocess.run(
    ["git", "show", PARITY_BASE + ":lore.py"], cwd=ROOT,
    capture_output=True).stdout)
_spec = importlib.util.spec_from_file_location("lore_base", BASE_PY)
lore_base = importlib.util.module_from_spec(_spec)
sys.modules["lore_base"] = lore_base
lore_base.__dict__["log"] = lambda m: None
_spec.loader.exec_module(lore_base)
lore_base._library_dirs = lambda out: []
lore_base._scan_dir_mp4s = lambda d, k: []
TDB = tempfile.mkdtemp(prefix="scale337_b_")
apib = mount(lore_base, TDB, eye=True)
b_gold = night(lore_base, TDB, "gold_no_audit", ins=current())
b_old = night(lore_base, TDB, "older_gen", ins=current(gen=G - 1),
              aud={"complete": True, "v": A}, covers=True)
fb = apib.have_flags([b_gold, b_old])
check("before: the same current, whole, never-audited description was "
      "SILVER, 'no audit has read this description yet'",
      fb[b_gold]["ins_lvl"] == 1
      and fb[b_gold]["ins_why"] == "no audit has read this description yet")
check("before: an older-version review with a gold audit was GOLD - the "
      "pen never said which version told it",
      fb[b_old]["ins_lvl"] == 2 and fb[b_old]["ins_why"] == "")
b_redo = night(lore_base, TDB, "redo_by_name", ins=current(),
               new={"windows": {"0": {}}, "complete": False, "tries": 0,
                    "gen": G})
fb2 = apib.have_flags([b_redo])
check("before: his own press on a finished night wore 'no audit has read "
      "this description yet' - an audit named that never ran",
      fb2[b_redo]["ins_lvl"] == 1
      and fb2[b_redo]["ins_why"] == "no audit has read this description yet")
del sys.modules["lore_base"]

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
