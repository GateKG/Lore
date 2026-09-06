# -*- coding: utf-8 -*-
"""3.34 drop I + K - THE EYE AS A REAL WITNESS, AND WHO IS TALKING.

Lifts the REAL functions out of lore.py (_eye_norm, _eye_seen,
_eye_lines, _eye_block, _aud_eye_agrees, _aud_says, _aud_condemn,
_aud_live, _aud_silence, _aud_drop, _aud_review, _my_name,
_seed_my_name, _sanitize_settings, _dress_line, _who_law, _title_guard)
into stub namespaces on tempdirs and holds them to:
  (1) the eye's prompt: a place is never the game's name alone, the
      doing is one sentence up to thirty words, and it READS the screen;
      the clips are 120 (place) and 240 (doing);
  (2) _eye_seen keeps the doing on every row, cut at 240 and sorted;
      _eye_lines caps a window at 12 with the nearest to a mark first;
      _eye_block heads them, and a night with no .vis renders nothing;
  (3) _aud_eye_agrees: a shared content word or one event family, and
      nothing either side is never agreement - so a vacuous look is
      near the claim (eye_near) without voting for it;
  (4) the thread's say.eye carries the look's sentence;
  (6) my_name: the default, the clamp, and the one-time seed from
      my_name.txt (the name is never in this file - the tests say
      Wanderer);
  (7) _dress_line labels his mic line with his name and an unnamed
      friend's line on a tap night 'Discord:', a typed voice name wins,
      and with no name and no tap it is HEAD's line to the byte;
  (8) _who_law is "" without a name or a tap (so the prompt is HEAD's),
      teaches the labels when there is one, and never lets 'Discord'
      be a person: the title guard catches it and the re-ask restates
      the law.
Names here are Wanderer / Faris / Marid - never a real person. Nothing
under D:\\Records is touched; no model, no port, no device.
"""
import ast
import io
import json
import os
import re
import sys
import tempfile
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
TREE = ast.parse(SRC)
FLAT = re.sub(r"\s+", " ", SRC)

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


TMP = tempfile.mkdtemp(prefix="eye334_")
LOGS = []

# =======================================================================
print("--- 1: the eye says what a person would say ---")
EYE = lift_assign("_EYE_SYSTEM", {})
FEYE = re.sub(r"\s+", " ", EYE)
check("a place is somewhere INSIDE the game, never the game's name alone",
      "NEVER the game's name alone" in FEYE
      and "a place is somewhere INSIDE it" in FEYE)
check("the doing is one full sentence, up to thirty words",
      "one full sentence, up to thirty words" in FEYE)
check("...and it reads what is legible on the screen - the score, the "
      "scorer, a timer, a banner",
      "the score" in FEYE and "who scored" in FEYE
      and "a timer" in FEYE and "WINNER" in FEYE
      and "text on screen is the best evidence there is" in FEYE)
check("the never-invent law is untouched",
      "Never invent a story between frames" in FEYE)
check("the eye's own clips: 120 for a place, 240 for a sentence",
      '_eye_norm(r.get("place"), 120)' in SRC
      and '_eye_norm(r.get("doing"), 240)' in SRC)
ns1 = {"re": re}
lift_assign("_EYE_NULLS", ns1)
_eye_norm = extract("_eye_norm", ns1)
check("_eye_norm cuts a long sentence at its cap, not at 70",
      len(_eye_norm("a car lands " + ("x" * 400), 240)) == 240
      and _eye_norm("none", 240) == "" and _eye_norm("", 240) == "")

# =======================================================================
print("\n--- 2: the describer gets the eye's sentences ---")
ns2 = {"re": re, "json": json, "os": os,
       "_ai_sidecar": lambda p, k: os.path.join(
           TMP, os.path.basename(p) + "." + k + ".json")}
_eye_seen = extract("_eye_seen", ns2)
_eye_lines = extract("_eye_lines", ns2)
_eye_block = extract("_eye_block", ns2)
VID = os.path.join(TMP, "night.mp4")
LOOKS = [
    {"t": 300.0, "place": "the orange goal end", "creature": "none",
     "doing": "a car is on the ground after a goal was scored, and the "
              "banner reads PIXEL SCORED with the score at 2-1"},
    {"t": 60.0, "place": "a hexagonal arena", "creature": "",
     "doing": "the kickoff countdown reads 3"},
    {"t": 900.0, "place": "the main menu", "creature": "", "doing": ""},
    {"t": "junk", "place": "nowhere", "creature": "", "doing": "x"},
]
with io.open(os.path.join(TMP, "night.mp4.vis.json"), "w",
             encoding="utf-8") as fh:
    json.dump({"looks": LOOKS + [{"t": 1200.0, "place": "the pitch",
                                  "creature": "",
                                  "doing": "y" * 400}]}, fh)
seen = _eye_seen(VID)
check("every look is one row, in time order, a bad clock skipped",
      [round(t) for t, _s in seen] == [60, 300, 900, 1200])
check("the doing is ALWAYS on the row - the sentence that carries the "
      "content is what the describer was missing",
      "PIXEL SCORED" in seen[1][1] and "countdown reads 3" in seen[0][1])
check("a look with no doing still says where it was",
      seen[2][1] == "the main menu")
check("a row is cut at 240, the eye's own sentence cap",
      len(seen[3][1]) == 240)
check("no .vis at all is no rows (and never an exception)",
      _eye_seen(os.path.join(TMP, "absent.mp4")) == [])
with io.open(os.path.join(TMP, "failed.mp4.vis.json"), "w",
             encoding="utf-8") as fh:
    json.dump({"failed": True, "looks": LOOKS}, fh)
check("a failed .vis is no rows", _eye_seen(os.path.join(TMP,
                                                         "failed.mp4")) == [])
MANY = [(float(i * 10), "look %d" % i) for i in range(40)]
win = _eye_lines(MANY, 0.0, 400.0, [305.0, 105.0], 12)
check("a window is capped at 12 looks, in time order",
      len(win) == 12 and win == sorted(win))
check("...with the looks nearest the marked moments taken first",
      (300.0, "look 30") in win and (100.0, "look 10") in win)
check("a window that fits is untouched",
      _eye_lines(MANY, 0.0, 100.0, [], 12) == MANY[:10])
# THE EYE REPEATS ITSELF: eight of one Rocket League night's
# seventeen looks said the same words. Dropping the taken rows by
# VALUE removed every copy, so the even spread stepped by less than
# one and printed a look twice while real looks fell out.
DUPES = ([(10.0, "the pitch")] * 3
         + [(float(20 + i * 10), "look %d" % i) for i in range(10)])
dwin = _eye_lines(DUPES, 0.0, 400.0, [15.0], 12)
check("byte-identical looks do not eat each other: 13 in, 12 out, and "
      "no look printed more often than the eye actually looked",
      len(dwin) == 12 and dwin == sorted(dwin)
      and all(dwin.count(r) <= DUPES.count(r) for r in set(dwin))
      and dwin.count((10.0, "the pitch")) == 3)
check("...and no real look is sacrificed to a repeated one (the "
      "measured trap printed one twice and lost two)",
      len([r for r in dwin if r[1] != "the pitch"]) == 9)
blk = _eye_block(win)
check("the block is headed in the eye's own words, one clock a line",
      blk.startswith("WHAT THE EYE SAW (each look, in its own words):\n")
      and "  5:00  look 30" in blk
      and "what it read off the screen" in blk)
check("no look, no block - a night without an eye renders nothing",
      _eye_block([]) == "" and _eye_block(_eye_lines([], 0, 10)) == "")
check("the window's evidence carries the block, and the title ask gets "
      "the first four lines nearest the moments",
      "_eye_block(_eye_lines(saw_here, lo, hi," in SRC
      and '"seen": _eye_lines(_seen, 0.0, float("inf"),' in SRC
      and 'if isinstance(m, dict)], 4)}' in SRC)

# =======================================================================
print("\n--- 3: the eye's witness needs content ---")
nsA = {"re": re, "os": os, "json": json,
       "_aud_voice": lambda sns, a, b: "",
       "_outcome_line": lambda o, clock=False: str(o.get("k") or "")}
for c in ("_AUD_WORDS", "_AUD_SOUND", "_AUD_SCREEN", "_AUD_EYE",
          "_AUD_REVIEW", "_AUD_CHAPTER", "_AUD_LAUGH", "_AUD_LIVE",
          "_AUD_LAYERS", "_AUD_SILENT", "_AUD_STOP", "_AUD_EYE_FAM"):
    lift_assign(c, nsA)
for f in ("_aud_eye_agrees", "_aud_says", "_aud_condemn", "_aud_live",
          "_aud_silence", "_aud_drop", "_aud_review"):
    extract(f, nsA)
agrees = nsA["_aud_eye_agrees"]
check("a content word in common is agreement",
      agrees("a car after a goal, PIXEL SCORED", "he scored a goal") is True
      and agrees("the tavern, the innkeeper is talking",
                 "they walk into the tavern") is True)
check("...four letters, and never one of the auditor's stop words",
      agrees("what a with that", "what a with that") is False
      and agrees("the boss", "the boss") is True)
check("an event family carries the meaning when no word is shared",
      agrees("a car lands as the banner reads GOAL", "he scored") is True
      and agrees("the WINNER banner is up", "they won that one") is True
      and agrees("the enemy is dead on the floor",
                 "he killed him") is True)
check("no overlap at all is not agreement - the vacuous look that "
      "agreed with every beat of a Rocket League night",
      agrees("rocket League stadium field", "what a save") is False
      and agrees("rocket League stadium field",
                 "the review called this a moment") is False)
check("nothing either side is never agreement",
      agrees("", "he scored a goal") is False
      and agrees("a car after a goal", "") is False
      and agrees("", "") is False)
check("the look may come as the dict itself",
      agrees({"place": "the arena", "doing": "the banner reads GOAL",
              "creature": ""}, "he scored") is True)

SAY = nsA["_aud_says"]
LOOK_FULL = {"t": 300.0, "place": "the orange goal end", "creature": "",
             "doing": "a car is on the ground after a goal was scored, "
                      "the banner reads PIXEL SCORED and the score at the "
                      "top of the screen has gone to 2-1"}
LOOK_VAC = {"t": 300.0, "place": "rocket League stadium field",
            "creature": "", "doing": ""}
MARK = {"stt": [{"a": 299000, "b": 301000, "t": "he scored a goal"}],
        "sns": {}, "ins": {}, "laughs": []}
lay, det = SAY(300.0, dict(MARK, vis={"looks": [LOOK_FULL]}))
check("a look that says what the mark says is an agreeing witness",
      "eye" in lay and det.get("eye_near") is True)
check("...and it travels as the look's SENTENCE, not as a place name "
      "cut at 90 (the thread's say.eye)",
      det["eye"].startswith("a car is on the ground")
      and "PIXEL SCORED" in det["eye"] and len(det["eye"]) > 90)
lay2, det2 = SAY(300.0, dict(MARK, vis={"looks": [LOOK_VAC]}))
check("a look that names only the game is NOT a witness - but the panel "
      "still knows the eye was looking here",
      "eye" not in lay2 and det2.get("eye_near") is True
      and det2["eye"] == "rocket League stadium field")
check("a look with no sentence still falls back to its place",
      SAY(300.0, dict(MARK, vis={"looks": [
          dict(LOOK_VAC, place="the orange goal end")]}))[1]["eye"]
      == "the orange goal end")
check("a look nowhere near the second is no eye at all",
      "eye" not in SAY(30.0, dict(MARK, vis={"looks": [LOOK_FULL]}))[1]
      and "eye_near" not in SAY(30.0, dict(MARK,
                                           vis={"looks": [LOOK_FULL]}))[1])
LIVE = {"words", "eye"}
gone1, ag1, _d1 = nsA["_aud_condemn"](
    300.0, dict(MARK, vis={"looks": [LOOK_FULL]}), LIVE, "")
gone2, ag2, _d2 = nsA["_aud_condemn"](
    300.0, {"stt": [], "sns": {}, "laughs": [],
            "vis": {"looks": [LOOK_VAC]},
            "ins": {"chapters": [{"t": 300.0, "label": "The kickoff"}]}},
    LIVE, "review")
check("a mark the eye backs stands; a chapter whose only witnesses are "
      "itself and a vacuous look falls to the road already there",
      gone1 is False and "eye" in ag1 and gone2 is True and ag2 == [])
rows, drops = nsA["_aud_review"](
    {"stt": [], "sns": {}, "laughs": [], "vis": {"looks": [LOOK_VAC]},
     "ins": {"chapters": [{"t": 300.0, "label": "The kickoff"}]}}, LIVE)
check("...and the drop says so in the words the panel already shows",
      rows == [] and len(drops) == 1
      and drops[0]["what"] == "The kickoff"
      and drops[0]["why"] == ("a chapter starts here and no line spoken "
                              "within four seconds and nothing the eye saw"))
check("no new warning kind was invented for it",
      "eye_vacuous" not in SRC and "the eye agreed with nothing" not in SRC)

# EYE_NEAR IS A FLAG, NOT A WITNESS'S WORD. det keeps one bool among
# strings, and both readers of det stringify what they find: the
# sidecar wrote "eye_near": "True" into every thread row with a look
# near it, and the dossier's sweep took the literal 'True' for a
# name that had been shown to the model. Both are run here, from the
# shipped lines, not read.
ANCH = [{"t": 1.0, "agrees": ["words"],
         "say": dict(det2, words="he scored a goal")}]
nsB = {"anchors": ANCH, "_AUD_LAYERS": nsA["_AUD_LAYERS"]}
exec(compile(textwrap.dedent(re.search(
    r"        beats = \[\{.*?\n(?=        beats\.sort)",
    func_src("_audit_one"), re.S).group(0)), "<beats>", "exec"), nsB)
check("the .aud thread row carries the six layers and nothing else - no "
      "witness in the sidecar ever said \"True\"",
      nsB["beats"][0]["say"] == {"words": "he scored a goal",
                                 "eye": "rocket League stadium field"}
      and "eye_near" not in nsB["beats"][0]["say"])
nsC = {"anchors": ANCH, "places": [], "crs": [],
       "_AUD_LAYERS": nsA["_AUD_LAYERS"],
       "_eye_key": lambda x: str(x).strip().lower()}
exec(compile(textwrap.dedent(re.search(
    r'    shown = \[str\(p\.get.*?\n(?=    tail = "")',
    func_src("_aud_body"), re.S).group(0)), "<shown>", "exec"), nsC)
check("...and the dossier's \"already shown\" sweep never counts it as "
      "a name the model was given",
      "true" not in nsC["shown"]
      and "rocket league stadium field" in nsC["shown"])

# =======================================================================
print("\n--- 6: his name for the tome ---")
DEF = lift_assign("DEFAULTS", {"_default_output_dir": lambda: TMP})
check("the setting exists and is empty until he (or the file) fills it",
      DEF["my_name"] == "")
nsS = {"re": re, "os": os, "DEFAULTS": DEF}
extract("_room_names_clamp", nsS)
san = extract("_sanitize_settings", nsS)
d = dict(DEF, my_name="   " + "W" * 60 + "   ")
san(d)
check("the clamp strips and cuts at forty", d["my_name"] == "W" * 40)
d2 = dict(DEF)
d2.pop("my_name")
san(d2)
check("a settings file without it falls back to empty", d2["my_name"] == "")

DATA = os.path.join(TMP, "data")
os.makedirs(DATA, exist_ok=True)
SET = {"my_name": ""}
SAVED = []
nsN = {"re": re, "os": os, "SETTINGS": SET,
       "_data_dir": lambda: DATA,
       "save_settings": lambda s: SAVED.append(dict(s)),
       "log": lambda m: LOGS.append(m)}
_my_name = extract("_my_name", nsN)
_seed = extract("_seed_my_name", nsN)
check("no my_name.txt, nothing happens", _seed() is False and SAVED == [])
with io.open(os.path.join(DATA, "my_name.txt"), "w",
             encoding="utf-8-sig") as fh:
    fh.write("# the name the tome should use\nWanderer\nignored\n")
check("the file seeds the empty setting ONCE and saves it",
      _seed() is True and SET["my_name"] == "Wanderer"
      and len(SAVED) == 1 and _my_name() == "Wanderer")
check("...and says so without ever printing the name",
      LOGS == ["Your name for the tome was read from my_name.txt."]
      and "Wanderer" not in LOGS[0])
check("a filled setting is never touched", _seed() is False
      and len(SAVED) == 1)
SET["my_name"] = ""
with io.open(os.path.join(DATA, "my_name.txt"), "w",
             encoding="utf-8") as fh:
    fh.write("   " + "W" * 60 + "   \n")
check("the seed wears the same forty-character clamp",
      _seed() is True and SET["my_name"] == "W" * 40)
check("the boot seeds it beside the room's names, and state() carries it",
      "_seed_my_name()               # 3.34 K once, from my_name.txt" in SRC
      and '"my_name": _my_name(),' in SRC)

# =======================================================================
print("\n--- 7: the transcript says who is talking ---")
VOICE = {}
nsD = {"re": re, "SETTINGS": SET,
       "_aud_voice": lambda sns, a, b: VOICE.get("who", ""),
       "_DRESS_SRC": {}}
extract("_seg_layer", nsD)
nsD["_my_name"] = lambda: str(SET.get("my_name") or "")
_dress = extract("_dress_line", nsD)
YOU = {"a": 61000, "b": 63000, "t": "yalla", "src": "you"}
FRIEND = {"a": 61000, "b": 63000, "t": "wait for me"}
SET["my_name"] = ""
nsD["_DRESS_SRC"].clear()
head_you = _dress(YOU, 3, {})
head_fr = _dress(FRIEND, 4, {})
check("no name and no voice tap: HEAD's line, to the byte",
      head_you == "[#3 1:01] YOU: yalla"
      and head_fr == "[#4 1:01] wait for me")
SET["my_name"] = "Wanderer"
check("his mic line carries his name instead of YOU",
      _dress(YOU, 3, {}) == "[#3 1:01] Wanderer: yalla")
check("...and a friend's line on a mix night stays bare - no tap, no "
      "proof of who it was",
      _dress(FRIEND, 4, {}) == "[#4 1:01] wait for me")
nsD["_DRESS_SRC"].update({"voice": True})
check("on a tap night an unnamed room line that is not his is a friend "
      "on the call, by construction",
      _dress(FRIEND, 4, {}) == "[#4 1:01] Discord: wait for me"
      and _dress(YOU, 3, {}) == "[#3 1:01] Wanderer: yalla")
VOICE["who"] = "Faris"
check("a typed voice name wins over the label",
      _dress(FRIEND, 4, {}) == "[#4 1:01] Faris: wait for me")
VOICE["who"] = "you"
check("...and a voice the room's names call his is his name too",
      _dress(FRIEND, 4, {}) == "[#4 1:01] Wanderer: wait for me")
VOICE.pop("who")
check("the game's own audio is never given a friend",
      _dress(dict(FRIEND, g=1), 4, {})
      == "[#4 1:01] wait for me (probably the game's own audio)")
check("a video and the game's own voice are dressed as they always were",
      _dress(dict(FRIEND, src="media"), 4, {}).endswith(
          "(a video playing in the background, not the room) wait for me")
      and _dress(dict(FRIEND, src="game"), 4, {}).endswith(
          "(the game's own voice) wait for me"))
SET["my_name"] = ""
check("a tap night with no name still names the friends, and his line "
      "is still YOU",
      _dress(FRIEND, 4, {}) == "[#4 1:01] Discord: wait for me"
      and _dress(YOU, 3, {}) == "[#3 1:01] YOU: yalla")
check("the night's sources reach the dressing through one cell, set "
      "before a line can be dressed",
      "_DRESS_SRC.clear()" in SRC and "_DRESS_SRC.update(_stt_src)" in SRC
      and SRC.index("_DRESS_SRC.update(_stt_src)")
      < SRC.index("return _dress_line(sg, i, _sd0)"))

# =======================================================================
print("\n--- 8: the prose law, and Discord is not a person ---")
nsW = {"re": re, "SETTINGS": SET, "_my_name": lambda: ""}
law = extract("_who_law", nsW)
check("no name and no tap: nothing to teach, so the prompt is HEAD's",
      law() == "" and law(False, "") == "" and law(voice=False) == "")
L1 = law(False, "Wanderer")
check("with a name the prompt learns whose recording it is",
      "The recording belongs to Wanderer" in L1
      and "lines marked 'Wanderer:' are theirs" in L1
      and "Never 'the player' or 'the players'." in L1
      and "Discord" not in L1)
L2 = law(True, "Wanderer")
check("with a voice tap it learns the label, and that the label is not "
      "a name",
      "Lines marked 'Discord:' are Wanderer's friends on the voice call"
      in L2
      and "NEVER write 'Discord' as if it were a person's name" in L2
      and "a friend on the call" in L2 and "the boys on the call" in L2)
L3 = law(True, "")
check("a tap night with no name still says the room is not 'the player'",
      "the person recording" in L3 and "'YOU:' are theirs" in L3
      and "Discord" in L3)
check("the describer, the title and the auditor all ask under it",
      "txt = srv.ask(_DESC_SYSTEM\n                                  "
      "+ _who_law(bool(_stt_src.get(" in SRC
      and "t_sys = _TITLE_SYS + _who_law(" in SRC
      and "_asys = _AUD_SYSTEM + _who_law(" in SRC
      and SRC.count("asrv.ask(_asys, body,") == 2
      and "txt = srv.ask(_AUD_SYSTEM + _who_law(" in SRC)
check("the auditor is told the night's sources to build it with",
      '"sources": (stt_doc.get("sources")' in SRC)

nsT = {"re": re}
for c in ("_TITLE_SWEAR", "_TITLE_MOOD", "_TITLE_STOP", "_TITLE_FILLER"):
    lift_assign(c, nsT)
guard = extract("_title_guard", nsT)
check("a title that uses the label as a subject is caught",
      guard("Discord scores in the last second", []) == "Discord as a name"
      and guard("Discord and Faris lose the lobby", [])
      == "Discord as a name")
check("...but the place is allowed to be a place",
      guard("A friend on Discord calls it early", []) == ""
      and guard("The whole call goes down at once", []) == "")
check("the old guards are untouched",
      guard("Rocket League: Boost and Victory", []) == "a colon"
      and guard("Late Game Chaos", []) == "a mood word, not an event"
      and guard("The apostle finally goes down", []) == "")
check("the re-ask restates the law instead of only naming the crime",
      "_TITLE_DISCORD_LAW" in SRC
      and '+ (_TITLE_DISCORD_LAW' in SRC
      and 'if _why == "Discord as a name" else ""),' in SRC
      and "'Discord' is not a person." in SRC)

# =======================================================================
print("\n--- the laws this drop must not break ---")
check("the eye's conditional vote is owned where standing is counted "
      "- a night of bare place names has no eye in `live` at all",
      "STANDING IS COUNTED FROM THE SAME VOTES" in SRC
      and '"a sighting whose look is gone" road' in SRC)
check("_who_law owns the one prompt it changes without a name: a tap "
      "night's law is about the LABEL, which the transcript carries",
      "A TAP NIGHT WITH NO NAME STILL GETS THE LAW" in func_src("_who_law")
      and "no longer byte-comparable" in func_src("_who_law"))
check("the auditor's dossier speaks the labels its own law explains",
      "def _aud_who(sg, src):" in SRC
      and "_aud_who(sg, src) + txt[:110]" in func_src("_aud_dossier"))
check("_AUD_V is untouched - old audits are archived, not re-owed",
      "_AUD_V = 7" in SRC)
check("_aud_src and the owing caches are not re-keyed by this drop",
      "def _aud_src(video_path):" in SRC
      and "eye_agrees" not in func_src("_aud_src"))
for nm in ("Wanderer", "Faris", "Marid"):
    check("no test name leaks into lore.py (%s)" % nm, nm not in SRC)
check("the roster runs this suite", "eye334test" in io.open(
    os.path.join(ROOT, "qa", "run_all.bat"), encoding="utf-8").read())

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
