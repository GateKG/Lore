# -*- coding: utf-8 -*-
"""3.34 drop H - THE THIN VOCABULARY, THE MARK'S LANDING, THE EYE'S SENTENCE.

Lifts the REAL functions out of lore.py (_aud_vocab,
_aud_garble, _aud_unstrike_seg, _thin_mig_done, _thin_strike_migration,
_speech_times, _eye_norm and their helpers, _moment_of as a witness) into a stub
namespace on tempdirs and holds them to:
  (a) _aud_vocab reads the shelf AND the top level of every dated folder
      under .lore_archive (never its .attic), with the same skip rules,
      logs the two counts once, and keeps the hour cache;
  (b) _AUD_VOCAB_MIN = 5000: _aud_thin says so, the audit's call site
      holds the shortlist under it (_aud_garble itself stays HEAD's -
      pinned byte for byte), logs the thin vocabulary once per night and
      writes vocab_n beside "when";
  (c) _aud_unstrike_seg is the swap Put-it-back does, shared;
  (d) _thin_strike_migration on a scratch shelf: struck lines put back
      (t <- was, markers off), the pinned line untouched, the partial
      strike untouched, the transcript banked, the aud.json moved to
      the attic, the owing cache popped, a night WITH vocab_n untouched
      byte for byte, a night without an aud.json untouched, the marker
      written keyed to the library, the second run a no-op;
  (e) the walk rides _shelf_migrations behind its own marker;
  (f) _eye_norm keeps a 240-character sentence; the eye's clips are
      240 (doing) and 120 (place);
  (g) no struck line is anybody's "closest said": _speech_times,
      _aud_says, the describer's moments (_moment_of stays HEAD's);
  (h) ui.html: the jump reads $('#vvideo') at click time and holds the
      landing once; tipWordsAt skips nn; the said panel folds struck
      lines (saidVisible stays 3.30's, saidFold runs under node); the
      Eye rows wrap;
  (i) the 3.34 stamps everywhere they live, and the roster lists this.
No devices, nothing under D:\\Records, nothing under %LOCALAPPDATA%."""
import ast
import datetime
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
USRC = io.open(os.path.join(ROOT, "ui.html"), encoding="utf-8").read()
TREE = ast.parse(SRC)

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


def extract(name, ns):
    for node in TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                SRC.splitlines()[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name + " not found")


def lift_assign(name, ns):
    for node in TREE.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name
                for t in node.targets):
            code = "\n".join(SRC.splitlines()[node.lineno - 1:node.end_lineno])
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name + " not assigned")


def func_src(name):
    for node in TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(SRC.splitlines()[node.lineno - 1:node.end_lineno])
    raise AssertionError(name + " not found")


def wr(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2)


def rd(path):
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


TMP = tempfile.mkdtemp(prefix="h334_")
LOGS = []


def _mkdata():
    # the real _data_dir() creates its folder before answering
    d = os.path.join(TMP, "data")
    os.makedirs(d, exist_ok=True)
    return d


ns = {"os": os, "re": re, "json": json, "time": time, "shutil": shutil,
      "_dt": datetime, "threading": threading,
      "log": lambda m: LOGS.append(str(m)),
      "SETTINGS": {"output_dir": TMP},
      "_thumb_dir": lambda o: os.path.join(TMP, ".lore_thumbs"),
      "_data_dir": lambda: _mkdata()}
for nm in ("_AUD_VOCAB", "_AUD_VOCAB_LOCK", "_AUD_VOCAB_MIN", "_MIG_SKIPPED",
           "_MIG_BANKED", "_AUD_OWE_CACHE", "_EYE_NULLS", "_REACTION_WORDS"):
    lift_assign(nm, ns)
for nm in ("_aud_vocab", "_aud_garble", "_aud_thin",
           "_aud_unstrike_seg",
           "_thin_mig_mark", "_thin_mig_done", "_thin_strike_migration",
           "_library_dirs", "_scan_dir_mp4s", "_ai_sidecar", "_attic_dir",
           "_bank_sidecar", "_mig_bank", "_atomic_write_json",
           "_speech_times", "_moment_of", "_eye_norm"):
    extract(nm, ns)
THUMBS = os.path.join(TMP, ".lore_thumbs")
os.makedirs(THUMBS)

# =========================================================================
print("--- (a) the vocabulary reads the archive too ---")
wr(os.path.join(THUMBS, "shelfnight.stt.json"),
   {"segments": [{"a": 1000, "b": 2000, "t": "alpha beta"},
                 {"a": 3000, "b": 4000, "t": "gamma"}]})
ARC = os.path.join(TMP, ".lore_archive", "2026-09-06")
wr(os.path.join(ARC, "old.stt.json"),
   {"segments": [{"a": 1000, "b": 2000, "t": "delta epsilon"},
                 {"a": 3000, "b": 4000, "t": "mediaword", "src": "media"},
                 {"a": 5000, "b": 6000, "t": "[unintelligible]", "nn": 1,
                  "was": "struckword"},
                 {"a": 7000, "b": 8000, "t": "fixedword", "fx": 1,
                  "was": "origword"},
                 {"a": 9000, "b": 9500, "t": "\u0634\u0643\u0631\u0627"}]})
wr(os.path.join(ARC, ".attic", "gone.stt.json"),
   {"segments": [{"a": 1000, "b": 2000, "t": "atticword"}]})
wr(os.path.join(TMP, ".lore_archive", ".hidden", "x.stt.json"),
   {"segments": [{"a": 1000, "b": 2000, "t": "hiddenword"}]})
freq, low = ns["_aud_vocab"]()
check("the shelf's words are counted",
      freq.get("alpha") == 1 and freq.get("beta") == 1 and freq.get("gamma") == 1)
check("the archive's words are counted too (his own, read-only)",
      freq.get("delta") == 1 and freq.get("epsilon") == 1)
check("...a corrected line counts its ORIGINAL, as on the shelf",
      freq.get("origword") == 1 and "fixedword" not in freq)
check("...and the archive's Arabic counts",
      freq.get("\u0634\u0643\u0631\u0627") == 1)
check("the same skip rules: a media line and a struck line feed nothing",
      "mediaword" not in freq and "struckword" not in freq)
check("the archive's .attic and a dot-folder are never walked",
      "atticword" not in freq and "hiddenword" not in freq)
check("logged once: N words from the shelf and M from the archive",
      LOGS == ["The auditor's vocabulary: 3 words from the shelf and 4 "
               "from the archive."])
wr(os.path.join(THUMBS, "later.stt.json"),
   {"segments": [{"a": 1000, "b": 2000, "t": "laterword"}]})
f2, _ = ns["_aud_vocab"]()
check("the hour cache holds (a transcript that lands later waits its hour)",
      f2 is freq and "laterword" not in f2 and len(LOGS) == 1)
ns["_AUD_VOCAB"]["at"] = 0.0
f3, _ = ns["_aud_vocab"]()
check("...and a cold cache re-reads (the new word is there, logged again)",
      "laterword" in f3 and len(LOGS) == 2)
wr(os.path.join(THUMBS, "badrow.stt.json"),
   {"segments": ["a str where a row goes", 7, None,
                 {"a": 1000, "b": 2000, "t": "goodword"}]})
wr(os.path.join(THUMBS, "zlast.stt.json"),
   {"segments": [{"a": 1000, "b": 2000, "t": "zlastword"}]})
wr(os.path.join(ARC, "zarc.stt.json"),
   {"segments": [{"a": 1000, "b": 2000, "t": "zarcword"}]})
ns["_AUD_VOCAB"]["at"] = 0.0
f4, _ = ns["_aud_vocab"]()
check("review fix: a malformed row skips ONE row - the rest of that "
      "transcript, the shelf after it and the whole archive still count",
      "goodword" in f4 and "zlastword" in f4 and "zarcword" in f4
      and "laterword" in f4 and len(LOGS) == 3)
check("_aud_vocab derives the archive from _thumb_dir's parent (a penned-in "
      "test shelf never reaches the real archive) and stays self-contained "
      "(src331test lifts it alone with _thumb_dir stubbed)",
      "os.path.dirname(os.path.abspath(td))" in func_src("_aud_vocab")
      and '".lore_archive"' in func_src("_aud_vocab")
      and "_aud_vocab_files" not in SRC)

# =========================================================================
print("\n--- (b) the thin guard ---")
check("_AUD_VOCAB_MIN is 5000", ns["_AUD_VOCAB_MIN"] == 5000)
STT_G = [{"a": 10000, "b": 12000, "t": "Vontrelle almond zami shukran"},
         {"a": 20000, "b": 22000, "t": "\u4f60\u597d\u4e16\u754c"}]
thin = {"w%d" % i: 3 for i in range(4999)}
fat = {"w%d" % i: 3 for i in range(5000)}
check("_aud_thin: 4999 distinct words is thin, 5000 is not, nothing is thin",
      ns["_aud_thin"](thin) is True and ns["_aud_thin"](fat) is False
      and ns["_aud_thin"]({}) is True and ns["_aud_thin"](None) is True)
g = ns["_aud_garble"](STT_G, fat)
check("_aud_garble itself is HEAD's: the line is shortlisted and the "
      "foreign one struck on any non-empty vocabulary",
      len(g) == 2 and g[0].get("verdict") == "noise"
      and g[1].get("odd") == ["Vontrelle", "almond", "zami", "shukran"]
      and len(ns["_aud_garble"](STT_G, thin)) == 2
      and "_AUD_VOCAB_MIN" not in func_src("_aud_garble"))
check("an empty vocabulary still answers []", ns["_aud_garble"](STT_G, {}) == [])
i0 = SRC.index("garble = _aud_garble(stt, _freq)")
tail = SRC[i0:i0 + 1200]
check("the audit's call site holds the shortlist under the floor and logs "
      "it once per night, before the ear-gap witness (no vocabulary needed)",
      "if _aud_thin(_freq):" in tail
      and "garble = []" in tail
      and "the library's vocabulary is thin (" in tail
      and "holds its strikes on " in tail
      and tail.index("if _aud_thin(_freq):") < tail.index("garble = []")
      < tail.index("holds its strikes") < tail.index("_aud_ear_union"))
check("ears333audit's pin on the call line still holds",
      SRC.count("garble = _aud_garble(stt, _freq)") == 1)
doc_i = SRC.index('doc = {"v": _AUD_V, "complete": done,')
doc_s = SRC[doc_i:doc_i + 400]
check("the audit's own aud.json carries vocab_n beside its clock",
      '"when": int(time.time()),' in doc_s
      and '"vocab_n": len(_freq or {}),' in doc_s
      and doc_s.index('"when"') < doc_s.index('"vocab_n"')
      < doc_s.index('"thread": beats'))
check("the failed-audit stub carries no vocab_n (it judged nothing)",
      '"failed": True, "complete": False,\n              "tries": prior + 1, '
      '"when": int(time.time()),\n              "thread": []' in SRC)

# =========================================================================
print("\n--- (c) the swap, shared ---")
sg = {"a": 1000, "b": 2000, "t": "[unintelligible]", "nn": 1, "fx": 1,
      "was": "You gotta own it, bro.", "fxw": "why", "fxo": ["gotta"],
      "d": "you got to own it bro", "src": ""}
out = ns["_aud_unstrike_seg"](sg)
check("t <- was, and nn/fx/fxw/fxo/was come off; the rest stays",
      out is sg and sg == {"a": 1000, "b": 2000, "t": "You gotta own it, bro.",
                           "d": "you got to own it bro", "src": ""})
sg2 = {"t": "kept", "pn": 1, "fx": 1, "was": "kept static"}
ns["_aud_unstrike_seg"](sg2)
check("a partial strike swaps the same way (pn off too)",
      sg2 == {"t": "kept static"})
uf = SRC[SRC.index("def aud_unfix(self, path, t, heard=None):"):]
uf = uf[:uf.index("def ", 10)]
check("Put-it-back uses the shared swap, then pins",
      "_aud_unstrike_seg(hit)" in uf and 'hit["pin"] = 1' in uf
      and uf.index("_aud_unstrike_seg(hit)") < uf.index('hit["pin"] = 1')
      and 'hit["t"] = hit.pop("was")' not in uf)

# =========================================================================
print("\n--- (d) the thin-strike walk on a scratch shelf ---")
VIDS = os.path.join(TMP, "Rocket League", "Videos")
os.makedirs(VIDS)
for nm in ("night1", "night2", "night3", "night5"):
    with io.open(os.path.join(VIDS, nm + ".mp4"), "wb") as fh:
        fh.write(b"\0" * 100_001)
P1 = os.path.join(VIDS, "night1.mp4")
P2 = os.path.join(VIDS, "night2.mp4")
P3 = os.path.join(VIDS, "night3.mp4")
S1 = ns["_ai_sidecar"](P1, "stt")
A1 = ns["_ai_sidecar"](P1, "aud")
S2 = ns["_ai_sidecar"](P2, "stt")
A2 = ns["_ai_sidecar"](P2, "aud")
S3 = ns["_ai_sidecar"](P3, "stt")
check("the sidecars resolve into the scratch shelf, not D:\\Records",
      S1.startswith(THUMBS) and A2.startswith(THUMBS))
STT1 = {"reader": 7, "segments": [
    {"a": 1000, "b": 2000, "t": "Right, we are going in."},
    {"a": 5000, "b": 7000, "t": "[unintelligible]", "nn": 1, "fx": 1,
     "was": "You gotta own it, bro.", "fxw": "two ears heard noise",
     "fxo": ["gotta"]},
    {"a": 9000, "b": 10000, "t": "[unintelligible]", "nn": 1, "fx": 1,
     "was": "So yeah.", "fxw": "noise"},
    {"a": 12000, "b": 13000, "t": "[unintelligible]", "nn": 1, "fx": 1,
     "was": "he pinned this", "pin": 1, "fxw": "his"},
    {"a": 15000, "b": 17000, "t": "kept sentence.", "pn": 1, "fx": 1,
     "was": "kept sentence. zzzt krrr", "fxw": "partial"},
    {"a": 19000, "b": 20000, "t": "[unintelligible]", "nn": 1,
     "fxw": "no original kept"},
]}
AUD1 = {"v": 7, "complete": True, "tries": 0, "when": 1, "garble": [{"t": 5.0}],
        "saw": {"struck": 2}}
STT2 = {"reader": 7, "segments": [
    {"a": 1000, "b": 2000, "t": "[unintelligible]", "nn": 1, "fx": 1,
     "was": "judged with the real vocabulary", "fxw": "noise"}]}
AUD2 = {"v": 7, "complete": True, "tries": 0, "when": 2, "vocab_n": 31337,
        "garble": [{"t": 1.0}], "saw": {"struck": 1}}
STT3 = {"reader": 7, "segments": [
    {"a": 1000, "b": 2000, "t": "[unintelligible]", "nn": 1, "fx": 1,
     "was": "never audited", "fxw": "echo"}]}
# the 3.33 auditor's own failed stub: complete False, tries counted, no
# vocab_n - it struck nothing, and its tries are the sweep's ledger
P5 = os.path.join(VIDS, "night5.mp4")
S5 = ns["_ai_sidecar"](P5, "stt")
A5 = ns["_ai_sidecar"](P5, "aud")
STT5 = {"reader": 7, "segments": [
    {"a": 1000, "b": 2000, "t": "[unintelligible]", "nn": 1, "fx": 1,
     "was": "struck before the sweep gave up", "fxw": "echo"}]}
AUD5 = {"v": 7, "failed": True, "complete": False, "tries": 3, "when": 3,
        "thread": []}
wr(S1, STT1)
wr(A1, AUD1)
wr(S2, STT2)
wr(A2, AUD2)
wr(S3, STT3)
wr(S5, STT5)
wr(A5, AUD5)
raw1 = io.open(S1, "rb").read()
rawa1 = io.open(A1, "rb").read()
raw2 = io.open(S2, "rb").read()
rawa2 = io.open(A2, "rb").read()
raw3 = io.open(S3, "rb").read()
raw5 = io.open(S5, "rb").read()
rawa5 = io.open(A5, "rb").read()
old = time.time() - 86400 * 3
for p in (S1, A1, S2, A2, S3, S5, A5):
    os.utime(p, (old, old))
m2 = os.path.getmtime(S2), os.path.getmtime(A2), os.path.getmtime(S3)
m5 = os.path.getmtime(S5), os.path.getmtime(A5)
key1 = os.path.normcase(os.path.abspath(P1))
key2 = os.path.normcase(os.path.abspath(P2))
ns["_AUD_OWE_CACHE"][key1] = ("sig", False)
ns["_AUD_OWE_CACHE"][key2] = ("sig", False)
lib = os.path.normcase(os.path.abspath(TMP))
check("no marker yet: the walk is owed", ns["_thin_mig_done"](lib) is False)
del LOGS[:]
got = ns["_thin_strike_migration"]()
check("returns (lines put back, nights) = (2, 1)", got == (2, 1))
d1 = rd(S1)
segs = d1["segments"]
check("the two struck lines are back: t <- was, the markers off",
      segs[1] == {"a": 5000, "b": 7000, "t": "You gotta own it, bro."}
      and segs[2] == {"a": 9000, "b": 10000, "t": "So yeah."})
check("the pinned line is untouched", segs[3] == STT1["segments"][3])
check("the partial strike (pn) is untouched", segs[4] == STT1["segments"][4])
check("a struck line with no original kept stays struck (nothing to put "
      "back)", segs[5] == STT1["segments"][5])
check("the room's own line is untouched", segs[0] == STT1["segments"][0])
check("the transcript was banked first (.v1 holds the bytes as they stood)",
      os.path.isfile(S1 + ".v1") and io.open(S1 + ".v1", "rb").read() == raw1)
att = os.listdir(os.path.join(THUMBS, ".attic"))
check("the aud.json MOVED to the attic (night1.aud.<stamp>.json), not copied",
      not os.path.isfile(A1) and len(att) == 1
      and re.match(r"^night1\.aud\.\d{8}-\d{6}\.json$", att[0]) is not None
      and io.open(os.path.join(THUMBS, ".attic", att[0]), "rb").read() == rawa1)
check("the owing cache forgot night1 - and only night1",
      key1 not in ns["_AUD_OWE_CACHE"] and key2 in ns["_AUD_OWE_CACHE"])
check("a night whose audit carries vocab_n is untouched, byte for byte and "
      "clock for clock",
      io.open(S2, "rb").read() == raw2 and io.open(A2, "rb").read() == rawa2
      and (os.path.getmtime(S2), os.path.getmtime(A2)) == m2[:2])
check("a night with no audit at all is untouched (its strike was never the "
      "thin auditor's)",
      io.open(S3, "rb").read() == raw3 and os.path.getmtime(S3) == m2[2]
      and not os.path.isfile(S3 + ".v1"))
check("review fix: a failed-audit STUB (complete False, tries 3, no vocab_n) "
      "is not a candidate - transcript and stub untouched, clock for clock, "
      "not atticked (atticking it would hand a given-up night three more "
      "model runs)",
      io.open(S5, "rb").read() == raw5 and io.open(A5, "rb").read() == rawa5
      and (os.path.getmtime(S5), os.path.getmtime(A5)) == m5
      and not os.path.isfile(S5 + ".v1"))
check("the log says so", LOGS == [
    "Put back 2 struck line(s) on 1 night(s) audited under the thin "
    "vocabulary; their audits will run again."])
MARK = os.path.join(TMP, "data", "strikes.mig")
check("the marker is written to <data dir>\\strikes.mig, keyed to the library",
      os.path.isfile(MARK) and rd(MARK).get("lib") == lib
      and rd(MARK).get("put_back") == 2 and rd(MARK).get("nights") == 1)
check("_thin_mig_done: this library yes, another library no",
      ns["_thin_mig_done"](lib) is True
      and ns["_thin_mig_done"](lib + "x") is False)
del LOGS[:]
snap = {p: (io.open(p, "rb").read(), os.path.getmtime(p))
        for p in (S1, S2, A2, S3, S5, A5)}
got2 = ns["_thin_strike_migration"]()
check("the second run is a no-op: (0, 0), nothing written, nothing logged, "
      "no second attic file",
      got2 == (0, 0) and LOGS == []
      and all((io.open(p, "rb").read(), os.path.getmtime(p)) == v
              for p, v in snap.items())
      and len(os.listdir(os.path.join(THUMBS, ".attic"))) == 1)
os.remove(MARK)
ns["_MIG_BANKED"].clear()
got3 = ns["_thin_strike_migration"]()
check("...and without the marker it is STILL a no-op (the atticked audit is "
      "gone; the vocab_n night is never a candidate)",
      got3 == (0, 0) and os.path.isfile(MARK))
# an unreadable audit is skipped and the walk is NOT retired
os.remove(MARK)
with io.open(A1, "w", encoding="utf-8") as fh:
    fh.write("{not json")
os.utime(A1, (old, old))
ns["_MIG_SKIPPED"][0] = 0
got4 = ns["_thin_strike_migration"]()
check("an unreadable aud.json is counted skipped and the marker is NOT "
      "written (it runs again rather than be written off)",
      got4 == (0, 0) and ns["_MIG_SKIPPED"][0] == 1 and not os.path.isfile(MARK))
ns["_MIG_SKIPPED"][0] = 0
os.remove(A1)

# =========================================================================
print("\n--- (e) wired into the shelf walks, behind its own marker ---")
sm = func_src("_shelf_migrations")
check("_shelf_migrations asks strikes.mig, not shelf.mig, for the thin walk",
      "thin = not _thin_mig_done(lib)" in sm
      # 3.36 N4 added the stale-.new sweep to the same early return,
      # so the clause is quoted, not the whole line
      and "if not todo and not thin" in sm)
check("...runs it LAST inside work(), after the five, and reports a walk "
      "that could not read the shelf",
      "_thin_strike_migration()" in sm
      and sm.index("_thin_strike_migration()") > sm.index('"black-picture"')
      and "The thin-strike walk stumbled" in sm
      and "The thin-strike walk could not read" in sm)
check("_MIG_WALKS is still the five (black332test's pin; the thin walk is "
      "not a sixth name in shelf.mig)",
      re.search(r'_MIG_WALKS = \("refold", "eye", "strike", "echo", "black"\)',
                SRC) is not None)
check("the walk only ever considers a COMPLETE aud.json WITHOUT vocab_n "
      "(review fix: a failed stub is skipped)",
      'if not isinstance(ad, dict) or "vocab_n" in ad or not ad.get("complete"):'
      in func_src("_thin_strike_migration"))
check("_aud_vocab: the isinstance guard heads the segments loop",
      'if not isinstance(sg, dict):\n                        continue'
      in func_src("_aud_vocab"))

# =========================================================================
print("\n--- (f) the eye keeps its sentence ---")
sent = ("the player has just scored and the words 'PIXEL SCORED!' are "
        "displayed on the screen while the ball resets to the centre "
        "of the pitch and both cars boost back to their halves, the "
        "scoreboard now reading two to one with a minute left")
check("a 200+ character sentence survives the 240 clip",
      len(sent) > 200 and ns["_eye_norm"](sent, 240) == sent)
check("...and 90 cut it to ninety characters, mid-sentence (the defect)",
      len(ns["_eye_norm"](sent, 90)) == 90
      and sent.startswith(ns["_eye_norm"](sent, 90)))
check("the eye clips doing at 240 and place at 120",
      '_eye_norm(r.get("doing"), 240)' in SRC
      and '_eye_norm(r.get("place"), 120)' in SRC
      and '_eye_norm(r.get("doing"), 90)' not in SRC)
check("the default cap is unchanged (creatures)",
      "def _eye_norm(v, cap=70):" in SRC)

# =========================================================================
print("\n--- (g) no struck line is anybody's closest said ---")
P4 = os.path.join(VIDS, "night4.mp4")
S4 = ns["_ai_sidecar"](P4, "stt")
wr(S4, {"segments": [
    {"a": 10000, "b": 12000, "t": "[unintelligible]", "nn": 1,
     "was": "Vontrelle scored again, what the"},
    {"a": 20000, "b": 22000, "t": "Vontrelle scored again, what the!"},
    {"a": 30000, "b": 31000, "t": "quiet chatter about nothing"}]})
said, hot = ns["_speech_times"](P4)
check("_speech_times: the struck second is not a said second (the re-pick "
      "cannot seat a gold mark on it)", said == [20.0, 30.0] and hot == [20.0])
# _moment_of is the ASK BOX's road (a quote back to its clock), not a
# mark's closest-said; ask332test pins it byte-identical to 2b59d37 (the
# dormant-without-the-model law), so drop H leaves it as it stands - a
# struck line's only word is "unintelligible", which no quote carries.
check("_moment_of is left as HEAD's (the ask's road, pinned by ask332test)",
      'if sg.get("nn"):' not in func_src("_moment_of")
      and ns["_moment_of"](P4, "Vontrelle scored again", "") == 20000)
says = func_src("_aud_says")
check("_aud_says: a struck line is not a witness to the second",
      'or sg.get("g") or sg.get("nn")' in says)
ins = func_src("_insights_one")
check("the describer's moments: a moment on a struck line is dropped with "
      "the media/game ones (_mdrop), never given a clock",
      'if m_sg.get("nn"):' in ins
      and ins.index('if m_sg.get("nn"):') > ins.index(
          'if _seg_layer(m_sg) in ("media", "game"):')
      and ins.index('if m_sg.get("nn"):') < ins.index("why = _m_qcheck(mm, why, use)"))

# =========================================================================
print("\n--- (h) the UI, read from its source and run under node ---")
j0 = USRC.index("const jump=e=>{")
jump = USRC[j0:USRC.index("m.addEventListener('pointerdown',jump);")]
check("the jump reads $('#vvideo') AT CLICK TIME and seeks on it",
      "const v=$('#vvideo')||vd;" in jump and "v.currentTime=to;" in jump
      and "vd.currentTime=to;" not in jump)
check("...and holds the landing once: a seeking/seeked guard, 300 ms, "
      "one-shot, put back only if the playhead moved off `to`",
      "v.addEventListener('seeking',guard)" in jump
      and "v.addEventListener('seeked',guard)" in jump
      and "setTimeout(off,300)" in jump
      and "Math.abs((v.currentTime||0)-to)>0.5" in jump
      and "let armed=true" in jump)
check("review fix: the jump's request guard - a stale mark (the last "
      "recording's, standing until the next render) never seeks this video; "
      "the press is swallowed, not handed to the bar",
      "if(req!==_viewerReq)return;" in jump
      and jump.index("e.preventDefault(); e.stopPropagation();")
      < jump.index("if(req!==_viewerReq)return;")
      < jump.index("const cur=m._ev||ev"))
check("review fix: the jump stamps V.userSeekReq with its open before it seeks",
      "V.userSeekReq=req;" in jump
      and jump.index("V.userSeekReq=req;") < jump.index("v.currentTime=to;"))
r0 = USRC.index("const rp=resPoint(vid.path);")
r_end = "vd.addEventListener('loadedmetadata',once,{once:true});\n    }"
RES = USRC[r0:USRC.index(r_end, r0) + len(r_end)]
check("review fix: the resume's loadedmetadata seek yields when V.userSeekReq "
      "carries THIS open (source)",
      "if(V.userSeekReq===req)return;" in RES
      and RES.index("if(V.userSeekReq===req)return;") < RES.index("const d=vd.duration;"))
JS_RES = """
const whispers=[]; const whisper=s=>whispers.push(s); const fmtT=t=>String(t);
function mk(userReq){
  const req=7, _viewerReq=7, V={userSeekReq:userReq}, vid={path:'p'};
  const resPoint=()=>({t:407,d:1000});
  const vd={duration:1000,currentTime:391.2,h:null,addEventListener(k,f){this.h=f;}};
""" + RES + """
  vd.h(); return vd.currentTime;
}
console.log(JSON.stringify({yield:mk(7), resume:mk(3), fresh:mk(undefined), w:whispers}));
"""
res = subprocess.run(["node", "-e", JS_RES], capture_output=True, text=True,
                     encoding="utf-8")
try:
    jr = json.loads(res.stdout.strip().splitlines()[-1])
except Exception:
    jr = {}
    print("  node said: " + (res.stderr or res.stdout)[:300])
check("review fix (node): a seek he made on this open keeps the playhead "
      "(391.2 stays, no whisper); an older open's stamp, or none, resumes "
      "at the saved place as before",
      jr.get("yield") == 391.2 and jr.get("resume") == 407 and jr.get("fresh") == 407
      and jr.get("w") == ["resumed at 407", "resumed at 407"])
STAMP = "V.userSeekReq=_viewerReq;   /* 3.34 his seek outranks the resume */"
check("review fix: the said row, the Eye row, your mark, the moment chip, "
      "the chapter row, the moment row and the ask hit all stamp "
      "V.userSeekReq before they seek (7 - the chapter notch was retired "
      "on 6 Sep, the split IS the chapter)",
      USRC.count(STAMP) == 7
      and "    const vd=$('#vvideo');\n    " + STAMP + "\n    try{vd.currentTime=ln.t;}catch(e2){}" in USRC)
check("...and the notch that carried the eighth is gone with its builder",
      "m.className='chnotch'" not in USRC and "ch=[];" in USRC)
tw = USRC[USRC.index("function tipWordsAt(t){"):USRC.index("function markCardShow(m){")]
check("tipWordsAt skips a struck line - the next nearest unstruck line, "
      "else none", "if(s.nn)continue;" in tw
      and tw.index("if(s.nn)continue;") < tw.index("if(t>=a-0.2&&t<=b+0.2)"))
check("the said panel: SAID_STRUCK remembered in localStorage, folded by "
      "default", "let SAID_STRUCK=false;" in USRC
      and "localStorage.getItem('lore.said.struck')==='1'" in USRC
      and "localStorage.setItem('lore.said.struck',SAID_STRUCK?'1':'0')" in USRC)
check("...saidFilter passes it and keeps the gaps; saidRender draws the "
      "fold row mid-list and at the tail; the fold row toggles",
      "const {vis,pos}=saidVisible(_said.lines,_said.low||[],q,SAID_MEDIA);" in USRC
      and "const gaps=saidFold(vis,pos,_said.lines,SAID_STRUCK);" in USRC
      and "_said.gaps=gaps;" in USRC
      and "if(gaps[vi])frag.append(saidGapRow(gaps[vi]));" in USRC
      and "if(w1===vis.length&&gaps[vis.length])frag.append(saidGapRow(gaps[vis.length]));" in USRC
      and "saidStruckToggle(an&&an.dataset.i!=null?+an.dataset.i:null); return; }" in USRC
      and "const an=sl(gap.nextElementSibling)||sl(gap.previousElementSibling);" in USRC)
check("the Eye rows wrap: white-space normal, nothing clipped",
      "#vseen .etx,#vseen .etx div,#vseen .esub{white-space:normal;overflow:visible;" in USRC
      and "text-overflow:clip;overflow-wrap:break-word}" in USRC)


def lift_js(name):
    i = USRC.index("function " + name + "(")
    d = 0
    started = False
    for k in range(i, len(USRC)):
        if USRC[k] == "{":
            d += 1
            started = True
        elif USRC[k] == "}":
            d -= 1
            if started and d == 0:
                return USRC[i:k + 1]
    raise AssertionError(name)


HEAD_U = subprocess.run(["git", "show", "HEAD:ui.html"], cwd=ROOT,
                        capture_output=True).stdout.decode("utf-8", "replace")


def lift_from(src, name):
    i = src.index("function " + name + "(")
    d = 0
    started = False
    for k in range(i, len(src)):
        if src[k] == "{":
            d += 1
            started = True
        elif src[k] == "}":
            d -= 1
            if started and d == 0:
                return src[i:k + 1]
    raise AssertionError(name)


JS_TOG = lift_js("saidStruckToggle") + """
let SAID_STRUCK=false; const calls=[]; const localStorage={setItem(){}}; const $=()=>null;
const whisper=()=>{}; const _said={pos:[]};
function saidFilter(){ _said.pos=[0,-1,-1,1,-1,-1]; calls.push('filter'); }
function saidRender(c){ calls.push(c); }
saidStruckToggle(1); saidStruckToggle(4); saidStruckToggle();
console.log(JSON.stringify(calls));
"""
res = subprocess.run(["node", "-e", JS_TOG], capture_output=True, text=True,
                     encoding="utf-8")
try:
    jt = json.loads(res.stdout.strip().splitlines()[-1])
except Exception:
    jt = None
    print("  node said: " + (res.stderr or res.stdout)[:300])
check("review fix (node): the fold row keeps the reader's place - after the "
      "re-filter the panel is re-centred on the nearest visible line from "
      "the anchor forward (mid-list) or backward (the tail fold); no anchor, "
      "no re-centre",
      jt == ["filter", 1, "filter", 1, "filter"])
check("saidVisible is byte-identical to HEAD's (sources331_panel pins it "
      "to the 3.30 loop) - the fold is a post-pass",
      lift_js("saidVisible") == lift_from(HEAD_U, "saidVisible"))
JS = lift_js("saidVisible") + "\n" + lift_js("saidFold") + """
const L=[{t:'alpha'},{t:'[unintelligible]',nn:1},{t:'[unintelligible]',nn:1},{t:'bravo'},
         {t:'[unintelligible]',nn:1},{t:'m',src:'media'}];
const low=L.map(l=>l.t.toLowerCase());
const run=(q,m,s)=>{const r=saidVisible(L,low,q,m); const gaps=saidFold(r.vis,r.pos,L,s);
  return {vis:r.vis,pos:r.pos,gaps};};
const h=run('',false,false), s=run('',false,true), q=run('bravo',false,false), q2=run('unint',false,false);
console.log(JSON.stringify({h,s,q,q2}));
"""
res = subprocess.run(["node", "-e", JS], capture_output=True, text=True,
                     encoding="utf-8")
try:
    jv = json.loads(res.stdout.strip().splitlines()[-1])
except Exception:
    jv = {}
    print("  node said: " + (res.stderr or res.stdout)[:300])
check("saidFold (node): folded, the struck lines are out of vis, pos -1, "
      "and one gap counts each run - mid-list and at the tail",
      jv.get("h") == {"vis": [0, 3], "pos": [0, -1, -1, 1, -1, -1],
                      "gaps": {"1": {"n": 2, "shown": False},
                               "2": {"n": 1, "shown": False}}})
check("saidFold (node): shown, they are in vis with today's rendering and "
      "the same rows head each run to fold them again",
      jv.get("s") == {"vis": [0, 1, 2, 3, 4], "pos": [0, 1, 2, 3, 4, -1],
                      "gaps": {"1": {"n": 2, "shown": True},
                               "4": {"n": 1, "shown": True}}})
check("saidFold (node): a query still filters; struck rows a query "
      "matches fold into the gap row rather than vanish",
      jv.get("q") == {"vis": [3], "pos": [-1, -1, -1, 0, -1, -1], "gaps": {}}
      and jv.get("q2") == {"vis": [], "pos": [-1] * 6,
                           "gaps": {"0": {"n": 3, "shown": False}}})

# =========================================================================
print("\n--- (i) the stamps ---")
VT = io.open(os.path.join(ROOT, "version.txt"), encoding="utf-8").read()
ISS = io.open(os.path.join(ROOT, "installer.iss"), encoding="utf-8").read()
BAT = io.open(os.path.join(ROOT, "qa", "run_all.bat"), encoding="utf-8").read()
check("lore.py APP_VERSION 3.35", 'APP_VERSION = "3.35"' in SRC)
check("ui.html version:'3.35' x2, no 3.34 stamp left",
      USRC.count("version:'3.35'") == 2 and "version:'3.34'" not in USRC)
check("version.txt 3.35", "filevers=(3, 35, 0, 0)" in VT
      and "prodvers=(3, 35, 0, 0)" in VT and VT.count("'3.35.0.0'") == 2
      and "3, 33" not in VT and "3.33" not in VT)
check("installer.iss 3.35", "AppVersion=3.35\n" in ISS.replace("\r\n", "\n")
      and "VersionInfoVersion=3.35.0\n" in ISS.replace("\r\n", "\n"))
check("the roster lists hotfix334test", "hotfix334test" in BAT)
added = "\n".join(
    ln[1:] for ln in subprocess.run(
        ["git", "diff", "-U0", "HEAD", "--", "lore.py", "ui.html"], cwd=ROOT,
        capture_output=True).stdout.decode("utf-8", "replace").splitlines()
    if ln.startswith("+") and not ln.startswith("+++"))
check("no test name (Wanderer / Faris / Marid) and no real name in the lines "
      "this drop adds", not re.search(r"Wanderer|Faris|Marid", added))

shutil.rmtree(TMP, ignore_errors=True)
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
