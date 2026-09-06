# -*- coding: utf-8 -*-
"""3.35 drop M - A NIGHT MAY ONLY BE TOLD WITH THE EVIDENCE IT HAS.

Lifts the REAL functions out of lore.py and ai/asr_worker.py by name
(_night_era, _night_mine, _who_law, _dress_line, _aud_who, _aud_dossier,
_title_guard, _mic_claim) into stub namespaces on tempdirs, and holds
them to the two defects measured on his own shelf on 6 Sep:

  M1 THE IDENTITY WAS CLAIMED WITHOUT THE EVIDENCE. 3.34's law taught
     every ask "the recording belongs to <him>" on EVERY night - a 2024
     night with no mic layer at all included. Now each night reads its
     OWN stt sidecar and says which of three eras it belongs to (split /
     mic / mixed), and the law, the dressing, the auditor's labels and
     the title guard all follow it.
  M2 ON A SPLIT NIGHT HIS VOICE WAS NOT ATTRIBUTED AT ALL: 102.6 s of
     mic speech and mic_lines 0, because the 0.9 gate was written for a
     mix where the mic was the only clean layer.

  (1) _night_era on split / mic / mixed sidecars, plus absent and
      corrupt -> "mixed", behind a cache keyed on the stt's mtime;
  (2) _who_law per era: mixed is "" (so the ask is the pre-3.34 one to
      the byte), the nameless split forbids attributing a line to him,
      the mic law forbids Discord, and era=None is HEAD's answer;
  (3) _dress_line per era: a mixed night is the pre-3.34 dressing over
      200 lines, a `micp` line is never dressed, no 'Discord:' off the
      split road;
  (4) _aud_who and the dossier per era;
  (5) the title guard's new re-ask on a night that could not hear him;
  (6) _mic_claim at 0.55 / 0.45 / 0.95 on both roads, and the mix road
      byte-for-byte HEAD's rule;
  (7) the ui's era line;
  (8) the laws this drop must not break - READER 7, no owe cache
      touched, nothing re-owed.

Names here are Wanderer / Faris / Marid - never a real person. Nothing
under D:\\Records is touched; no model, no port, no device.
"""
import ast
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
TREE = ast.parse(SRC)
WSRC = io.open(os.path.join(ROOT, "ai", "asr_worker.py"),
               encoding="utf-8").read()
WTREE = ast.parse(WSRC)

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


def head_of(rel, rev="HEAD"):
    r = subprocess.run(["git", "show", rev + ":" + rel], cwd=ROOT,
                       capture_output=True)
    return r.stdout.decode("utf-8", "replace")


def extract(src, tree, name, ns):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                src.splitlines()[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name + " not found")


def lift_assign(src, tree, name, ns):
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name
                for t in node.targets):
            exec(compile(textwrap.dedent("\n".join(
                src.splitlines()[node.lineno - 1:node.end_lineno])),
                "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name + " not found")


def func_src(name, src=None, tree=None):
    src = SRC if src is None else src
    tree = TREE if tree is None else tree
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(src.splitlines()[node.lineno - 1:node.end_lineno])
    raise AssertionError(name)


TMP = tempfile.mkdtemp(prefix="era335_")

# =======================================================================
print("--- 1: the night says which era it belongs to ---")
SIDE = {}


def sidecar(video_path, kind):
    return os.path.join(TMP, os.path.basename(video_path) + "." + kind
                        + ".json")


nsE = {"os": os, "json": json, "_ai_sidecar": sidecar, "_ERA_CACHE": {}}
_night_era = extract(SRC, TREE, "_night_era", nsE)
_night_mine = extract(SRC, TREE, "_night_mine", nsE)


def write(vid, doc):
    with io.open(sidecar(vid, "stt"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh)


write("split.mp4", {"sources": {"v": 1, "voice": True, "mic_s": 102.6},
                    "segments": [{"a": 0, "t": "yalla"}]})
write("mic.mp4", {"sources": {"v": 1, "voice": False, "mic_s": 45.0},
                  "segments": [{"a": 0, "t": "yalla"}]})
write("mixed.mp4", {"sources": {"v": 1, "voice": False, "mic_s": 0.0},
                    "segments": [{"a": 0, "t": "yalla"}]})
write("old.mp4", {"segments": [{"a": 0, "t": "yalla"}]})
write("tagged.mp4", {"sources": {"v": 1, "voice": False},
                     "segments": [{"a": 0, "t": "yalla", "src": "you"}]})
write("partly.mp4", {"sources": {"v": 1, "voice": False},
                     "segments": [{"a": 0, "t": "yalla", "micp": 0.4}]})
with io.open(sidecar("torn.mp4", "stt"), "w", encoding="utf-8") as fh:
    fh.write('{"sources": {"voice": tr')

check("a Voice tap makes it a SPLIT night", _night_era("split.mp4") == "split")
check("no tap but a mic layer is a MIC night", _night_era("mic.mp4") == "mic")
check("neither is MIXED - one microphone-shaped blur",
      _night_era("mixed.mp4") == "mixed")
check("a sidecar written before the sources block is MIXED too",
      _night_era("old.mp4") == "mixed")
check("a line tagged 'you' is a mic layer even with mic_s missing",
      _night_era("tagged.mp4") == "mic")
check("...and so is a partly-mic line", _night_era("partly.mp4") == "mic")
check("absent and torn sidecars are MIXED, the humblest answer",
      _night_era("gone.mp4") == "mixed" and _night_era("torn.mp4") == "mixed")

# the cache is keyed on the stt's mtime, like every other read
sp = sidecar("split.mp4", "stt")
mt = os.path.getmtime(sp)
write("split.mp4", {"sources": {"v": 1, "voice": False, "mic_s": 0.0},
                    "segments": []})
os.utime(sp, (mt, mt))
check("the same mtime is the same answer - one read, not one a beat",
      _night_era("split.mp4") == "split")
os.utime(sp, (mt + 20, mt + 20))
check("a moved clock is read again", _night_era("split.mp4") == "mixed")
check("_night_mine counts only the lines the mic itself claimed",
      _night_mine([{"src": "you"}, {"micp": 0.6}, {}, {"src": "you"},
                   {"src": "media"}]) == 2
      and _night_mine([]) == 0 and _night_mine(None) == 0)

# =======================================================================
print("\n--- 2: the law each era can afford ---")
SET = {"my_name": ""}
nsW = {"re": re, "SETTINGS": SET, "_my_name": lambda: SET["my_name"]}
law = extract(SRC, TREE, "_who_law", nsW)
HSRC = head_of("lore.py")
HTREE = ast.parse(HSRC)
nsH = {"re": re, "SETTINGS": SET, "_my_name": lambda: SET["my_name"]}
hlaw = extract(HSRC, HTREE, "_who_law", nsH)

check("era=None is 3.34's law to the byte, on every combination it had",
      all(law(v, n) == hlaw(v, n)
          for v in (False, True)
          for n in ("", "Wanderer", None)))

MIXED = law(True, "Wanderer", "mixed", 9)
check("a MIXED night teaches nothing - the ask is the pre-3.34 one",
      MIXED == "" and law(False, "", "mixed", 0) == ""
      and law(False, "Wanderer", "mixed", 0) == "")
# ...and that is the whole ask, not just this law. THE TAUTOLOGY LAW
# (3.24): a check that adds MIXED to a prompt and compares it to THAT
# SAME PROMPT demands nothing the assertion above did not already
# guarantee - `a + "" == a` holds for any string alive - and it never
# reads a pre-3.34 commit at all, so a drop that rewrites _DESC_SYSTEM
# would keep it green while the parity it advertises is gone. The three
# prompts are lifted from BEFORE the law existed (9cfe020, 3.34 drop H)
# and the working tree's ask is compared to that one, ask against ask.
PRE = head_of("lore.py", "9cfe020")
PRETREE = ast.parse(PRE)
nsP = {}
for nm in ("_DESC_SYSTEM", "_AUD_SYSTEM", "_TITLE_SYS"):
    lift_assign(SRC, TREE, nm, nsW)
    lift_assign(PRE, PRETREE, nm, nsP)
check("the three prompts were really read out of 9cfe020",
      all(len(nsP[nm]) > 150
          for nm in ("_DESC_SYSTEM", "_AUD_SYSTEM", "_TITLE_SYS")))
check("the describer's, the auditor's and the title's asks are all "
      "byte-identical to the PRE-3.34 ask on a mixed night - each "
      "compared to 9cfe020's own copy, never to itself",
      all(nsW[nm] + MIXED == nsP[nm]
          for nm in ("_DESC_SYSTEM", "_AUD_SYSTEM", "_TITLE_SYS")))

S1 = law(True, "Wanderer", "split", 3)
check("a SPLIT night with lines of his own is 3.34's law, unchanged",
      S1 == hlaw(True, "Wanderer")
      and "The recording belongs to Wanderer" in S1
      and "Lines marked 'Discord:' are Wanderer's friends" in S1)

S0 = law(True, "Wanderer", "split", 0)
check("a SPLIT night with NO line of his loses every sentence that says "
      "the night is his",
      "The recording belongs to" not in S0
      and "(lines marked 'Wanderer:' are theirs)" not in S0)
check("...and says so outright: he may not be given a line or a deed",
      "Nobody in this recording has been identified as Wanderer" in S0
      and "never attribute a line or an action to him by name" in S0)
check("...while the label the transcript still carries is still explained",
      "Lines marked 'Discord:' are the friends on the voice call" in S0
      and "NEVER write 'Discord' as if it were a person's name" in S0)
# A LAW THAT ONLY CLOSES DOORS SENDS THE MODEL THROUGH THE WRONG ONE.
# This branch forbids his name; 3.34's tail forbade 'the player'; the
# only people-words left in the whole law are the FRIENDS on the call,
# so the nearest legal noun for the man holding the controller was one
# of them. A wrong name would have become a wrong person.
check("...and it hands over a word to USE, not only words to avoid",
      "write 'the one recording'" in S0
      and "never 'the player'" in S0 and "never 'the players'" in S0
      and "never one of the friends' names" in S0
      and not S0.endswith(" Never 'the player' or 'the players'.")
      and "write 'the one recording'" in law(True, "", "split", 0))
S0n = law(True, "", "split", 0)
check("a nameless night with no typed name says the same thing without "
      "inventing a name to forbid",
      "the person recording's own voice" in S0n and "Wanderer" not in S0n)

M1 = law(False, "Wanderer", "mic", 12)
check("a MIC night names him and nobody else",
      "The recording belongs to Wanderer" in M1
      and "someone in the room whose name this recording cannot know" in M1
      and "never guess one" in M1)
check("...and forbids the word Discord outright - there was no call",
      "never call anyone Discord" in M1
      and "Lines marked 'Discord:'" not in M1)
# ...but it may not forbid a name the TRANSCRIPT itself carries: a
# voiceprint he named himself is still dressed onto a mic night's
# line, exactly as it was at HEAD, and a law that called that name a
# guess would throw away the work of naming a voice.
check("...while a name he typed against a voice is the exception the "
      "mic night's own transcript needs",
      "a line that carries a name is the exception" in M1)
check("a MIC night with no typed name teaches nothing: 'YOU:' says it",
      law(False, "", "mic", 12) == "")
check("the three asks are handed the era and the count",
      "+ _who_law(bool(_stt_src.get(" in SRC
      and '"voice")), None, _ins_era,' in SRC
      and "t_sys = _TITLE_SYS + _who_law(" in SRC
      and SRC.count("src.get(\"era\"), src.get(\"mine\"))") == 2
      and "_ins_era = _night_era(video_path)" in SRC
      and "_ins_mine = _night_mine(segs)" in SRC)

# =======================================================================
print("\n--- 3: the transcript the model reads, per era ---")
VOICE = {}
nsD = {"re": re, "SETTINGS": SET,
       "_aud_voice": lambda sns, a, b: VOICE.get("who", ""),
       "_my_name": lambda: SET["my_name"], "_DRESS_SRC": {}}
extract(SRC, TREE, "_seg_layer", nsD)
_dress = extract(SRC, TREE, "_dress_line", nsD)
DS = nsD["_DRESS_SRC"]
SET["my_name"] = "Wanderer"

YOU = {"a": 61000, "b": 63000, "t": "yalla", "src": "you"}
FRIEND = {"a": 61000, "b": 63000, "t": "wait for me"}
PART = {"a": 61000, "b": 63000, "t": "half of this is mine", "micp": 0.45}

DS.clear()
DS.update({"voice": True, "era": "split"})
check("split: his mic line wears his name, an unnamed room line is a "
      "friend on the call",
      _dress(YOU, 3, {}) == "[#3 1:01] Wanderer: yalla"
      and _dress(FRIEND, 4, {}) == "[#4 1:01] Discord: wait for me")
check("split: a partly-mic line is dressed by NEITHER - the mic's own "
      "admission that it had only part of the utterance",
      _dress(PART, 5, {}) == "[#5 1:01] half of this is mine")
VOICE["who"] = "you"
check("...and a voiceprint that calls a partly-mic line his does not "
      "put his name on it either",
      _dress(PART, 5, {}) == "[#5 1:01] half of this is mine")
VOICE["who"] = "Faris"
check("a typed voice name still wins on a partly-mic line - a name he "
      "gave is his own evidence",
      _dress(PART, 5, {}) == "[#5 1:01] Faris: half of this is mine")
VOICE.pop("who")

# A NAMELESS SPLIT NIGHT: THE COUNT AND THE DRESSING MUST AGREE.
# _aud_voice can hand back a voiceprint cluster he once typed 'you',
# and the dressing promoted that to his NAME - while _night_mine,
# which counts only src == "you", still reported 0 and armed the law
# that says nobody in this recording has been identified as him. Same
# night, same ask, two opposite claims. The dressing gives up the one
# the count cannot see - and does NOT hand the line to a friend
# instead, because the print says it is not one of theirs.
DS.clear()
DS.update({"voice": True, "era": "split", "mine": 0})
VOICE["who"] = "you"
check("nameless split: a voiceprint's 'you' writes neither his name "
      "nor 'Discord:' over a line the law says was never identified",
      _dress(FRIEND, 4, {}) == "[#4 1:01] wait for me")
check("...while the line the MIC itself claimed still wears his name - "
      "that is the evidence the count is made of",
      _dress(YOU, 3, {}) == "[#3 1:01] Wanderer: yalla")
DS.update({"mine": 2})
check("...and on a split night that DID hear him the voiceprint road "
      "is untouched (the road eye334test pins)",
      _dress(FRIEND, 4, {}) == "[#4 1:01] Wanderer: wait for me")
DS.update({"mine": 0})
VOICE["who"] = "Faris"
check("...and a name he TYPED still wins on a nameless split night: "
      "it is his own evidence, not the mic's",
      _dress(FRIEND, 4, {}) == "[#4 1:01] Faris: wait for me")
VOICE.pop("who")
check("the dressing is handed the same count the law is",
      '_DRESS_SRC["mine"] = _ins_mine' in SRC)

DS.clear()
DS.update({"voice": False, "era": "mic"})
check("mic: his name on his line, and nobody is called Discord",
      _dress(YOU, 3, {}) == "[#3 1:01] Wanderer: yalla"
      and _dress(FRIEND, 4, {}) == "[#4 1:01] wait for me")

DS.clear()
DS.update({"voice": False, "era": "mixed"})
check("mixed: neither label may appear",
      _dress(YOU, 3, {}) == "[#3 1:01] YOU: yalla"
      and _dress(FRIEND, 4, {}) == "[#4 1:01] wait for me")
DS.clear()
DS.update({"voice": True, "era": "mixed"})
check("...even if a stale tap flag rides in the same block - the era "
      "decides, not the flag",
      _dress(FRIEND, 4, {}) == "[#4 1:01] wait for me")

# THE 2024 NIGHT, BYTE FOR BYTE. The pre-3.34 dressing is the nested
# _line of the 3.30 describer (a7a461f) - the same base sources331
# holds the room lines to.
HEAD30 = head_of("lore.py", "a7a461f")
H30 = ast.parse(HEAD30)
SNS = {"names": {"0": "Marid", "1": "you"},
       "speakers": [{"a": 10.0, "b": 14.0, "who": "0"},
                    {"a": 30.0, "b": 33.0, "who": "1"},
                    {"a": 50.0, "b": 52.0, "who": "2"}]}
hns = {"os": os, "re": re, "_aud_voice": None, "_sd0": SNS}
extract(SRC, TREE, "_aud_voice", hns)
head_line = extract(HEAD30, H30, "_line", hns)
segs = []
for i in range(200):
    t = i * 1.7
    sg = {"a": int(t * 1000), "b": int((t + 1.2) * 1000),
          "t": "line number %d says a thing" % i}
    if i % 7 == 0:
        sg["g"] = 1
    if i % 11 == 0:
        sg["src"] = "you"
    if i % 17 == 0:
        sg["micp"] = 0.4
    segs.append(sg)
nsD["_aud_voice"] = hns["_aud_voice"]
DS.clear()
DS.update({"era": "mixed"})
check("a MIXED night is the pre-3.34 dressing over 200 lines, with his "
      "name typed and everything - a 2024 night cannot become his",
      all(_dress(sg, i, SNS) == head_line(sg, i)
          for i, sg in enumerate(segs)))
nsD["_aud_voice"] = lambda sns, a, b: VOICE.get("who", "")
check("the era reaches the dressing through the same one cell",
      '_DRESS_SRC["era"] = _ins_era' in SRC
      and SRC.index('_DRESS_SRC["era"] = _ins_era')
      < SRC.index("return _dress_line(sg, i, _sd0)"))

# =======================================================================
print("\n--- 4: the auditor's own labels, per era ---")
nsA = {"_my_name": lambda: SET["my_name"]}
_aud_who = extract(SRC, TREE, "_aud_who", nsA)
SPLIT = {"sources": {"voice": True}, "era": "split"}
MICN = {"sources": {}, "era": "mic"}
MIXN = {"sources": {}, "era": "mixed"}
check("split: his name on his mic, Discord on a friend's line",
      _aud_who(YOU, SPLIT) == "Wanderer: "
      and _aud_who(FRIEND, SPLIT) == "Discord: ")
check("split: a partly-mic line wears no label at all",
      _aud_who(PART, SPLIT) == "")
check("mic: his name on his own line, nothing on anyone else's",
      _aud_who(YOU, MICN) == "Wanderer: "
      and _aud_who(FRIEND, MICN) == "")
check("mixed: no mark is written at all, whatever the setting says",
      _aud_who(YOU, MIXN) == "" and _aud_who(FRIEND, MIXN) == "")
SET["my_name"] = ""
check("a nameless split night still labels both - the law explains a "
      "mark the dossier actually writes",
      _aud_who(YOU, SPLIT) == "YOU: "
      and _aud_who(FRIEND, SPLIT) == "Discord: ")
check("no name and no era to read: 3.34's answer, bare",
      _aud_who(YOU, {"sources": {}}) == ""
      and _aud_who(FRIEND, {"sources": {}}) == "")
SET["my_name"] = "Wanderer"

# the dossier speaks through _aud_who and nothing else
nsDo = {"float": float, "str": str, "abs": abs, "len": len,
        "_aud_who": _aud_who, "_aud_tone": lambda sns, t: "",
        "_aud_ear_note": lambda g: ""}
_doss = extract(SRC, TREE, "_aud_dossier", nsDo)
CONV = [dict(YOU, a=20000, t="Line twenty is mine"),
        dict(FRIEND, a=21000, t="Line twenty-one is a friend")]
G0 = {"t": 20.0, "b": 20.9, "text": CONV[0]["t"], "odd": [], "hints": []}
INS = {"chapters": [{"t": 0, "label": "the queue"}]}
d_sp = _doss(G0, dict(SPLIT, stt=CONV, sns=None, vis=None, ins=INS,
                      laughs=[]), INS)
d_mx = _doss(G0, dict(MIXN, stt=CONV, sns=None, vis=None, ins=INS,
                      laughs=[]), INS)
check("the dossier carries the split night's labels",
      "Wanderer: Line twenty is mine" in d_sp
      and "Discord: Line twenty-one" in d_sp)
check("...and a mixed night's dossier carries neither",
      "Wanderer" not in d_mx and "Discord" not in d_mx
      and "Line twenty is mine" in d_mx)
check("the auditor's own src carries the era and the count",
      '"era": _night_era(video_path),' in SRC
      and '"mine": _night_mine(stt)}' in SRC)

# =======================================================================
print("\n--- 5: a night may not be titled after a person it could "
      "not hear ---")
nsT = {"re": re}
for c in ("_TITLE_SWEAR", "_TITLE_MOOD", "_TITLE_STOP", "_TITLE_FILLER",
          "_TITLE_UNHEARD"):
    lift_assign(SRC, TREE, c, nsT)
guard = extract(SRC, TREE, "_title_guard", nsT)
UNH = nsT["_TITLE_UNHEARD"]
check("his name in a title on a night that could not hear him is caught",
      guard("Wanderer takes the last round", [], "Wanderer") == UNH)
check("...and the guard is unarmed on every other night: two arguments "
      "is 3.34's arithmetic exactly",
      guard("Wanderer takes the last round", []) == ""
      and guard("Wanderer takes the last round", [], "") == "")
check("a title that never names him passes on a nameless night",
      guard("The last round goes long", [], "Wanderer") == "")
check("the old guards still fire first and unchanged",
      guard("Rocket League: Boost and Victory", [], "Wanderer") == "a colon"
      and guard("Discord scores in the last second", [], "Wanderer")
      == "Discord as a name"
      and guard("Late Game Chaos", [], "Wanderer")
      == "a mood word, not an event")
check("the re-ask restates the law rather than only naming the crime, "
      "and the guard's own re-check is held to it too",
      "_TITLE_NAME_LAW" in SRC and "+ (_TITLE_NAME_LAW" in SRC
      and "if _why == _TITLE_UNHEARD else \"\")" in SRC
      and "_title_guard(cand, _said, _bare)" in SRC
      and "Do not put his name in the title" in SRC)
check("only a mixed or nameless-split night arms it",
      '_ins_era == "mixed"' in SRC
      and '(_ins_era == "split" and _ins_mine <= 0)' in SRC)

# =======================================================================
print("\n--- 6: his voice on a split night (ai/asr_worker.py) ---")
nsM = {}
_mic_claim = extract(WSRC, WTREE, "_mic_claim", nsM)
check("split: a group the mic carried the louder half of is HIS - "
      "0.55 with a friend's tap open at the same time",
      _mic_claim(0.55, True) == "you" and _mic_claim(0.5, True) == "you"
      and _mic_claim(0.95, True) == "you")
check("split: under half stays a fraction, never a binary",
      _mic_claim(0.45, True) == "micp" and _mic_claim(0.01, True) == "micp")
check("no mic at all is nobody's line, on either road",
      _mic_claim(0.0, True) == "" and _mic_claim(0.0, False) == "")
check("the MIX road is untouched: 0.9 or it is a fraction",
      _mic_claim(0.9, False) == "you" and _mic_claim(0.89, False) == "micp"
      and _mic_claim(0.55, False) == "micp"
      and _mic_claim(0.95, False) == "you")
HW = head_of("ai/asr_worker.py")
check("...and that is HEAD's own rule, read out of HEAD's loop",
      "if mfrac >= 0.9:" in HW and "if mfrac >= 0.9:" not in WSRC)
STEPS = [i / 100.0 for i in range(0, 101)]
check("the mix road agrees with HEAD's rule on every hundredth",
      all(_mic_claim(m, False)
          == ("you" if m >= 0.9 else ("micp" if m > 0 else ""))
          for m in STEPS))
check("the split road claims 40 more of those hundredths for him",
      sum(1 for m in STEPS if _mic_claim(m, True) == "you")
      - sum(1 for m in STEPS if _mic_claim(m, False) == "you") == 40)

# the real loop, driven on a synthetic split night's groups
LOOP = func_src("main", WSRC, WTREE)
check("the loop asks _mic_claim for the night it is on, not a constant",
      "_claim = _mic_claim(mfrac, has_voice)" in LOOP
      and 'if _claim == "you":' in LOOP
      and 'elif _claim == "micp":' in LOOP)
# THE NIGHT ITSELF, THROUGH THE APP'S OWN ROUTINES. Hand-written
# groups ({"mic": 55, "len": 100}) are a shape the routing cannot
# produce: _span_audio was an all-or-nothing 0.9 vote per span, so a
# span a friend shared contributed ZERO mic samples and every group
# on his 6 Sep night scored mfrac 0.0 - the 0.5 gate could never fire
# on the one night it was written for. A fixture that skipped the
# numerator could not say that, and said the opposite. So the groups
# are built by _span_audio + _group_spans and the tagging branch is
# lifted VERBATIM out of main() rather than retyped.
WK = {}
for _n2 in ast.walk(WTREE):
    if isinstance(_n2, ast.Assign):
        for _t2 in _n2.targets:
            if getattr(_t2, "id", "") in ("GROUP_GAP_S", "CHUNK_S"):
                WK[_t2.id] = ast.literal_eval(_n2.value)
SR = 16000
# 17 utterances of his, 6 s each = 102 s of mic speech, his 6 Sep
# night to the second - and every one of them inside a mix span a
# friend's tap opened a second early and closed a second late. His
# mic covers 0.75 of each: under _span_audio's own routing test, which
# is the entire point of the shape.
MM = [(int(12 * k * SR), int((12 * k + 6) * SR)) for k in range(17)]
SPANS = [{"start": int(max(0, 12 * k - 1) * SR),
          "end": int((12 * k + 7) * SR)} for k in range(17)]
MIC_S = sum(y - x for x, y in MM) / float(SR)
_N = int(12 * 17 * SR)
_room = np.zeros(_N, dtype="float32")
_mixa = np.zeros(_N, dtype="float32")
_mica = np.zeros(_N, dtype="float32")


def span_audio(src, tree, has_voice):
    """the app's own router, on this night's arrays"""
    return extract(src, tree, "_span_audio",
                   {"np": np, "a": _room, "mixa": _mixa, "ma": _mica,
                    "mm": MM, "has_voice": has_voice})


def loop_body(src):
    """the tagging branch, VERBATIM out of main() - a suite that
    retypes it is testing its own copy, not the app's"""
    i = src.index('mfrac = g.get("mic", 0) / float(max(1, g["len"]))')
    i = src.rindex("\n", 0, i) + 1
    j = src.index('sg_new["micp"] = round(mfrac, 2)', i)
    return textwrap.dedent(src[i:src.index("\n", j)])


def run_tag(src, tree, groups, has_voice):
    body = compile(loop_body(src), "<main loop>", "exec")
    ns = {}
    try:
        extract(src, tree, "_mic_claim", ns)
    except AssertionError:
        pass       # HEAD keeps the gate inline; that is what M moved
    outs, st = [], {"mic_lines": 0}
    for g in groups:
        sg_new = {}
        loc = dict(ns)
        loc.update({"g": g, "sg_new": sg_new, "stats": st,
                    "has_voice": has_voice})
        exec(body, loc, loc)
        outs.append(sg_new)
    return outs, st


HWTREE = ast.parse(HW)
nsG = {"GROUP_GAP_S": WK["GROUP_GAP_S"], "CHUNK_S": WK["CHUNK_S"]}
group_spans = extract(WSRC, WTREE, "_group_spans", nsG)
G_SPLIT = group_spans(SPANS, span_audio(WSRC, WTREE, True), SR, "room")
G_MIX = group_spans(SPANS, span_audio(WSRC, WTREE, False), SR, "room")
G_HEAD = group_spans(SPANS, extract(
    HW, HWTREE, "_span_audio",
    {"np": np, "a": _room, "mixa": _mixa, "ma": _mica, "mm": MM}),
    SR, "room")
F_SPLIT = [g["mic"] / float(max(1, g["len"])) for g in G_SPLIT]
check("the fixture is the app's own routing, not a shape by hand: "
      "%d groups over %.0f s of his voice" % (len(G_SPLIT), MIC_S),
      len(G_SPLIT) == 17 and 100 < MIC_S < 105
      and all(0.5 <= f < 0.9 for f in F_SPLIT))
O_SPLIT, S_SPLIT = run_tag(WSRC, WTREE, G_SPLIT, True)
O_HEAD, S_HEAD = run_tag(HW, HWTREE, G_HEAD, True)
check("HIS 6 SEP NIGHT: HEAD filed every one of those lines as "
      "nobody's (mic_lines %d); the mic now claims them (%d)"
      % (S_HEAD["mic_lines"], S_SPLIT["mic_lines"]),
      S_HEAD["mic_lines"] == 0
      and S_SPLIT["mic_lines"] == len(G_SPLIT)
      and all(sg.get("src") == "you" for sg in O_SPLIT))
# the numerator learned to COUNT; it did not learn to route. The
# audio handed to the model is still the room's wherever a friend
# may be in the span - swapping it would erase whoever talked over
# him, and TAGGED, NEVER FILTERED is older than this drop.
_sa = span_audio(WSRC, WTREE, True)
_sh, _mn = _sa({"start": 0, "end": int(7 * SR)})
_sc, _mc = _sa({"start": 0, "end": int(6 * SR)})
check("a shared span still hands back the ROOM's audio - only its "
      "mic COUNT changed, from a vote to a measurement",
      np.shares_memory(_sh, _room) and _mn == int(6 * SR)
      and np.shares_memory(_sc, _mica) and _mc == int(6 * SR))
check("the MIX road counts sample for sample what HEAD counted, so "
      "an unsplit night reads exactly as it did",
      [g["mic"] for g in G_MIX] == [g["mic"] for g in G_HEAD]
      and run_tag(WSRC, WTREE, G_MIX, False)[1]
      == run_tag(HW, HWTREE, G_HEAD, False)[1])
check("the mic-VAD fallback is still the non-split road's alone",
      "if mic and os.path.isfile(mic) and ma is None:" in WSRC)
check("NOTHING IS RE-OWED: the reader is untouched on both sides",
      re.search(r"^READER = 7\b", WSRC, re.M)
      and "_STT_READER = 7" in SRC
      and "READER stays 7" in func_src("_mic_claim", WSRC, WTREE))
check("the note the app journals is unchanged in shape",
      '" line(s) read from the clean mic itself")' in WSRC)

# =======================================================================
print("\n--- 7: the panel says which era the night is ---")
USRC = io.open(os.path.join(ROOT, "ui.html"), encoding="utf-8").read()
check("one quiet line, one style, no new panel",
      "function saidEraLine(era){" in USRC
      and "#vsaid .sera{" in USRC
      and USRC.count("saidEraPaint(") == 3)
check("it names the three eras in his own words",
      "Recorded with the sources told apart" in USRC
      and "Recorded before the sources were split" in USRC
      and "the tome can tell your mic from the room, but not one friend "
          "from another" in USRC
      and "Recorded on one mixed track" in USRC
      and "the tome cannot tell who is speaking" in USRC)
check("it is painted after the lines are up, cleared when the panel is, "
      "and never fatal",
      "saidEraPaint('');   /* 3.35 M" in USRC
      and "if(api&&api.night_era)_era=(await api.night_era(v.path))||''"
      in USRC
      and "body.before(el('div','sera',s))" in USRC)
check("the app answers it, and the mock does too",
      "def night_era(self, path):" in SRC
      and "return _night_era(p)" in SRC
      and "night_era:async()=>(location.hash.includes('mixed')" in USRC)
# M4's second half: the panel is the one place he can SEE whether the
# identity work landed, and on a split night his friends' lines were
# carrying no label at all while the model-facing side wrote 'Discord:'
# into the same night's transcript. One branch, on the split era only.
check("an unnamed voice reads Discord on a SPLIT night and on no "
      "other - and 'Voice N' / 'a voice' stay gone",
      "if(n&&_said&&_said.era==='split')return 'Discord';" in USRC
      and "if(named)return named;" in USRC
      and "'Voice '+n" not in USRC and "return 'a voice'" not in USRC)
check("...and the era reaches the chips through the said state, "
      "painted in on the beat the answer arrives",
      "_said.era=_era;" in USRC
      and "if(_era==='split'&&_said.lines.length)saidRender(null);"
      in USRC)

# =======================================================================
print("\n--- 8: the laws this drop must not break ---")
check("the era cache is a READ cache - no owe cache is keyed on it",
      "_ERA_CACHE = {}" in SRC
      and "_ERA_CACHE" not in func_src("_aud_owing_swept")
      and "_ERA_CACHE" not in func_src("_aud_src"))
check("no owing cache changed shape for this drop",
      "eye_agrees" not in func_src("_aud_src")
      and func_src("_aud_src") == func_src("_aud_src", HSRC, HTREE))
check("_AUD_V and the describer generation are untouched",
      "_AUD_V = 7" in SRC
      and re.search(r"^_INS_GENERATION\s*=\s*(\d+)", SRC, re.M).group(1)
      == re.search(r"^_INS_GENERATION\s*=\s*(\d+)", HSRC, re.M).group(1))
check("_night_era never writes: it reads a sidecar and a cache, nothing "
      "else",
      "open(" in func_src("_night_era")
      and ', "w"' not in func_src("_night_era")
      and "_atomic_write_json" not in func_src("_night_era"))
for nm in ("Wanderer", "Faris", "Marid"):
    # lore.py and the worker only: ui.html's preview mock has carried a
    # stand-in roster since 2.93, and it is a fixture, not the app
    check("no test name leaks into the app (%s)" % nm,
          nm not in SRC and nm not in WSRC)
check("the roster runs this suite",
      "era335test" in io.open(os.path.join(ROOT, "qa", "run_all.bat"),
                              encoding="utf-8").read())

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
