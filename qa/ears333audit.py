# -*- coding: utf-8 -*-
"""3.33 drop F - THE AUDITOR WEIGHS THE TWO EARS, proven.

Drop E left every room line a second reading `d`; this drop makes the
disagreement between the reader and that English-only ear a WITNESS on
the auditor's doubtful shortlist. These lift the REAL functions out of
lore.py by name (and their HEAD twins out of `git show HEAD:lore.py`)
and drive them on scratch fixtures: the overlap arithmetic, the ear-gap
shortlist (room lines only, a pinned / struck / fixed line skipped,
sorted, capped, and NOTHING without `d`), the union with the garble rows
(one row per second, the odd words kept), the dossier's witness lines
and the pack builder keeping them past its 900-character knife, the
sense gate's `extra`, the fix gate inside _aud_parse, the room's first
spelling winning in the name check, the prompt paragraph, the log-line
pin, and the laws: _AUD_V, _aud_src and every owing cache byte-identical
to HEAD's, and a night without `d` taking HEAD's decisions. The fix-first
round added T9-T11: the sense reverter keeps an ear-weighed fix by the
same evidence that admitted it, a "noise" verdict on a pure ear-gap row
weighs as unclear (never a strike), and the ask is budgeted (a dozen ear
rows per ask, a character guard that cuts the tail in place). Names here
are Wanderer / Faris / Marid - never a real person; game words are
duos / MMR / Alt-F4. Nothing under D:\\Records is touched; no model, no
port."""
import ast
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import time
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LSRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
LTREE = ast.parse(LSRC)
OK = FAIL = 0


def check(what, cond):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("FAIL:", what)


def node_of(tree, name, kinds=(ast.FunctionDef, ast.ClassDef)):
    for node in ast.walk(tree):
        if isinstance(node, kinds) and node.name == name:
            return node
    raise KeyError(name)


def seg(src, tree, name):
    return textwrap.dedent(ast.get_source_segment(src, node_of(tree, name)))


def extract(src, tree, name, ns):
    exec(compile(seg(src, tree, name), "<" + name + ">", "exec"), ns)
    return ns[name]


def assign_src(src, tree, name):
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tg in node.targets:
                if isinstance(tg, ast.Name) and tg.id == name:
                    return ast.get_source_segment(src, node)
    raise KeyError(name)


def lift_assign(src, tree, name, ns):
    exec(compile(assign_src(src, tree, name), "<" + name + ">", "exec"), ns)
    return ns[name]


def head_of(rel):
    return subprocess.run(["git", "show", "HEAD:" + rel], cwd=ROOT,
                          capture_output=True).stdout.decode("utf-8")


HSRC = head_of("lore.py")
HTREE = ast.parse(HSRC)
check("HEAD's lore.py could be read for the parity checks",
      len(HSRC) > 100000)

LOGS = []


def build(src, tree, ns=None):
    """A stub namespace holding the auditor's word machinery, lifted
    from ONE source (the tree or HEAD)."""
    ns = ns if ns is not None else {}
    ns.update({"re": re, "os": os, "json": json, "unicodedata": unicodedata,
               "log": lambda m: LOGS.append(m),
               "_AI": {"abort": False},
               "SETTINGS": {"room_names": ""},
               "_outcome_line": lambda o, clock=False: str(o.get("k") or "")})
    for nm in ("_AUD_STOP", "_AUD_AR", "_AUD_VOWEL", "_AUD_SUFFIX",
               "_AUD_WITH", "_AUD_POSS", "_AUD_TELL", "_AUD_LAYERS",
               "_AUD_SAY", "_AUD_VOCAB", "_AUD_SYSTEM", "_AUD_SCHEMA",
               "_AUD_V"):
        lift_assign(src, tree, nm, ns)
    # _AUD_PAIRS is a set filled by a loop right after its assignment
    i0 = src.index("_AUD_PAIRS = set()")
    i1 = src.index("def _aud_lat(t):", i0)
    exec(compile(src[i0:i1], "<_AUD_PAIRS>", "exec"), ns)
    for nm in ("_eye_stamp", "_eye_key", "_aud_lat", "_aud_skel",
               "_aud_phon", "_aud_ed", "_aud_filler", "_aud_clip",
               "_aud_sense", "_aud_garble", "_aud_tone", "_aud_dossier",
               "_aud_shown", "_aud_body", "_aud_parse", "_aud_ear_veto",
               "_aud_ear_agrees", "_aud_prompt_ear", "_aud_people",
               "_aud_gamewords", "_aud_grounded", "_aud_names",
               "_room_names", "_room_aliases_of", "_aud_carry",
               "_aud_hints", "_aud_skel_index"):
        extract(src, tree, nm, ns)
    return ns


NS = build(LSRC, LTREE)
HN = build(HSRC, HTREE)
for nm in ("_aud_ear_toks", "_aud_overlap", "_aud_ear_gap",
           "_aud_ear_union", "_aud_ear_note", "_aud_ear_extra",
           "_room_first_of"):
    extract(LSRC, LTREE, nm, NS)
for nm in ("_AUD_EAR_STOP", "_AUD_EAR_TOK", "_AUD_EAR_CAP", "_AUD_EAR_ASK",
           "_AUD_ASK_CHARS"):
    lift_assign(LSRC, LTREE, nm, NS)

# =========================================================================
print("--- T1: _aud_overlap ---")
ov = NS["_aud_overlap"]
check("identical -> 1.0",
      ov("Push the duos queue now Faris", "Push the duos queue now Faris")
      == 1.0)
check("disjoint -> 0.0", ov("Wanderer take the MMR hit", "married ember") == 0.0)
check("Arabic is ignored for the overlap (the second ear has none)",
      ov("\u064a\u0644\u0627 \u064a\u0644\u0627 Wanderer duos queue",
         "Wanderer duos queue") == 1.0)
check("stop words are ignored: 'the you are our' add nothing",
      ov("the duos are our queue", "duos queue you the") == 1.0)
check("two hearings with nothing Latin score 0, never a ZeroDivision",
      ov("\u064a\u0644\u0627", "") == 0.0 and ov("", "") == 0.0)
check("the sheet's own line: the reader and the ear agree on under half",
      ov("Yalla Wanderer we're about to lose our streak",
         "we're about to lose our freak") < 0.5)
check("case does not count as disagreement",
      ov("MMR Duos Alt-F4", "mmr duos alt-f4") == 1.0)

# =========================================================================
print("--- T2: _aud_ear_gap ---")
STT = [
    {"a": 1000, "b": 3500, "t": "Yalla Wanderer we're about to lose our streak",
     "lang": "english", "d": "we're about to lose our freak"},
    {"a": 5000, "b": 7000, "t": "Push the duos queue now Faris",
     "lang": "english", "d": "Push the duos queue now Faris"},
    {"a": 9000, "b": 11000, "t": "some movie line here tonight",
     "lang": "english", "src": "media", "d": "totally different words"},
    {"a": 13000, "b": 15000, "t": "Alt-F4 the lobby Marid please",
     "lang": "english", "pin": 1, "d": "all the four lobby married please"},
    {"a": 17000, "b": 19000, "t": "fixed line words here tonight",
     "lang": "english", "fx": 1, "was": "fix line word here tonight",
     "d": "nothing alike at all"},
    {"a": 21000, "b": 23000, "t": "MMR is dropping fast tonight",
     "lang": "english", "d": "Ember are dropping fast tonight"},
    {"a": 25000, "b": 27000, "t": "\u064a\u0644\u0627 \u064a\u0644\u0627 "
                                  "\u064a\u0644\u0627 go go",
     "lang": "arabic", "d": "go go go"},
    {"a": 29000, "b": 31000, "t": "Marid take the MMR hit for duos",
     "lang": "english", "src": "you",
     "d": "Married take the ember hit for do us"},
]
gap = NS["_aud_ear_gap"]
rows = gap(STT)
check("only the two disagreeing room lines come back, most different first",
      [r["n"] for r in rows] == [7, 0])
check("the rows carry {n, t, b, text, was, d, gap, odd, kind}",
      rows and all(set(r) >= {"n", "t", "b", "text", "was", "d", "gap",
                              "odd", "kind"} for r in rows)
      and rows[1]["t"] == 1.0 and rows[1]["b"] == 3.5
      and rows[1]["was"] == rows[1]["text"]
      and rows[1]["text"] == STT[0]["t"] and rows[1]["d"] == STT[0]["d"]
      and rows[1]["odd"] == [] and rows[1]["kind"] == "ears")
check("gap is 1 - overlap, rounded",
      rows[1]["gap"] == round(1.0 - ov(STT[0]["t"], STT[0]["d"]), 2)
      and rows[0]["gap"] > rows[1]["gap"])
check("a media line is never a candidate even when it carries d",
      2 not in [r["n"] for r in rows])
check("a pinned line, a fixed line, an agreeing line and an Arabic line "
      "are skipped", not {3, 4, 5, 6} & {r["n"] for r in rows})
nod = [dict((k, v) for k, v in sg.items() if k != "d") for sg in STT]
check("a night without d -> [] (the count-undoing law)", gap(nod) == [])
check("a struck (nn) and a split-struck (pn) line are skipped",
      gap([dict(STT[0], nn=1), dict(STT[7], pn=1)]) == [])
check("a 'you' segment (his clean mic) is a room line", rows[0]["n"] == 7)
check("a game line is not", gap([dict(STT[0], src="game")]) == [])
check("a line with fewer than three Latin content tokens is skipped",
      gap([dict(STT[0], t="Wanderer duos")]) == [])
check("thirty percent Arabic script or more is skipped",
      gap([dict(STT[0], t="\u0645\u0627\u0631\u062f \u064a\u0644\u0627 "
                          "\u062e\u0644\u0627\u0635 lose our streak")])
      == [])
many = [{"a": 1000 * (i + 1), "b": 1000 * (i + 1) + 800,
         "t": "Wanderer duos queue number %d" % i,
         "d": "married do us cue number %d" % i} for i in range(50)]
mrows = gap(many)
check("capped at 40 rows a night", len(mrows) == 40 == NS["_AUD_EAR_CAP"])
check("a bad clock on a segment costs that segment only",
      [r["n"] for r in gap([dict(STT[0], a="x"), STT[7]])] == [1])

# =========================================================================
print("--- T3: the shortlist union ---")
uni = NS["_aud_ear_union"]
garble = [{"t": 1.0, "b": 3.5, "text": STT[0]["t"], "odd": ["Yalla"]}]
ears = gap(STT)
out = uni(garble, ears)
check("a garble row and an ear-gap row at the same second -> ONE row",
      len(out) == 2 and [r["t"] for r in out] == [1.0, 29.0])
check("...that keeps its odd words and its text, gains d and gap, and "
      "stays a garble row (no kind)",
      out[0]["odd"] == ["Yalla"] and out[0]["text"] == STT[0]["t"]
      and out[0]["d"] == STT[0]["d"] and out[0]["gap"] == ears[1]["gap"]
      and "kind" not in out[0] and out[0] is garble[0])
check("the pure ear-gap row is appended after the garble rows, kind=ears",
      out[1]["kind"] == "ears" and out[1]["n"] == 7)
check("no ears -> the very same list object (a 3.32 night: untouched)",
      uni(garble, []) is garble and uni(None, []) is None)
check("a carried foreign-script strike at that second is not duplicated",
      len(uni([{"t": 29.0, "text": "x", "odd": [], "verdict": "noise",
                "carried": True}], ears)) == 2)

# =========================================================================
print("--- T4: the dossier and the pack ---")
CONV = [{"a": 1000 * i, "b": 1000 * i + 900,
         "t": "Line number %d of the room talking about duos and MMR and "
              "the queue tonight" % i, "lang": "english"}
        for i in range(60)]
SRC = {"stt": CONV, "sns": None, "vis": None, "laughs": [],
       "ins": {"chapters": [{"t": 0, "label": "the queue"}]}}
G0 = {"t": 20.0, "b": 20.9, "text": CONV[20]["t"], "odd": [], "hints": []}
G1 = dict(G0, d="we're about to lose our freak", kind="ears", gap=0.6)
dh = HN["_aud_dossier"](G0, SRC, SRC["ins"])
dt = NS["_aud_dossier"](G0, SRC, SRC["ins"])
check("without d the dossier is byte-identical to HEAD's", dh == dt)
d1 = NS["_aud_dossier"](G1, SRC, SRC["ins"])
WIT = '    the second ear (English only) heard: "we\'re about to lose our freak"'
check("with d the witness line appears exactly once, after the conversation",
      d1.count("the second ear (English only) heard") == 1
      and d1 == dh + "\n" + WIT)
NS["SETTINGS"]["room_names"] = "Wanderer, Faris / Fares, Marid"
d2 = NS["_aud_dossier"](G1, SRC, SRC["ins"])
check("with the room's names set, 'people in the room' follows, once",
      d2.count("people in the room") == 1
      and d2.endswith(WIT + "\n    people in the room: Wanderer, Faris, "
                      "Fares, Marid"))
check("...but never on a row without d (byte-identical to HEAD)",
      NS["_aud_dossier"](G0, SRC, SRC["ins"]) == dh)
NS["SETTINGS"]["room_names"] = ""
# the pack builder cuts each dossier at 900 characters; the witness sits
# after a 14-line conversation, past the knife
bh = HN["_aud_body"]([], [], "Fortnite", 600.0, SRC, [], [], [G0])
bt = NS["_aud_body"]([], [], "Fortnite", 600.0, SRC, [], [], [G0])
check("without d the whole ask is byte-identical to HEAD's", bh == bt)
b1 = NS["_aud_body"]([], [], "Fortnite", 600.0, SRC, [], [], [G1])
check("the dossier ran past 900 characters (the knife is live)",
      len(dh) > 900)
check("with d the pack keeps the witness past the knife",
      b1.count(WIT) == 1
      and b1.index(WIT) > b1.index("(0) 0:20 the line:")
      and "\nReturn only fixes." in b1[b1.index(WIT):])
check("...and the conversation, not the witness, met the knife",
      len(b1) - len(bt) <= len("\n" + WIT) + 2)

# =========================================================================
print("--- T5: _aud_sense with extra ---")
freq = dict(("word%d" % i, 5) for i in range(1200))
freq.update({"yalla": 30, "wanderer": 20, "about": 90, "lose": 40,
             "our": 80, "streak": 12, "the": 900})
sense = NS["_aud_sense"]
ok0, bad0 = sense("Alt-F4 duos Drakkari", freq)
check("an 'Alt-F4 duos Drakkari' correction fails a vocabulary that never "
      "heard those words", ok0 is False and bad0 == ["Alt", "duos", "Drakkari"])
ex = NS["_aud_ear_extra"]({"d": "alt-f4 duos Drakkari"})
ok1, bad1 = sense("Alt-F4 duos Drakkari", freq, ex)
check("...and passes WITH extra from the second ear's draft",
      ok1 is True and bad1 == [])
check("extra is the draft's tokens, lower case, stop words kept",
      ex == {"alt", "duos", "drakkari"})
check("a row without d has no extra (None) and a bare call is the old call",
      NS["_aud_ear_extra"]({"text": "x"}) is None
      and NS["_aud_ear_extra"](None) is None)
for s in ("Alt-F4 duos Drakkari", "Yalla Wanderer lose our streak",
          "\u0633\u0643\u0631 \u0644\u064a\u062a", "", "Drakkari",
          "the the streak"):
    check("default path parity with HEAD on %r" % s,
          sense(s, freq) == HN["_aud_sense"](s, freq))
check("extra never vouches for an Arabic token",
      sense("\u0646\u0627\u0641\u0648 \u062a\u0631\u0648\u0646\u0648\u0645",
            freq, {"nafo", "tronom"})[0] is False)
NS["SETTINGS"]["room_names"] = "Wanderer, Faris / Fares, Marid"
ex2 = NS["_aud_ear_extra"]({"d": "go go"},
                           r"D:\scratch\Hearthstone\Videos\Hearthstone_20260905_010203.mp4")
check("extra unions the room's aliases and the game's words off the "
      "filename", ex2 >= {"wanderer", "faris", "fares", "marid",
                          "hearthstone"} and "go" not in ex2)
NS["SETTINGS"]["room_names"] = ""

# =========================================================================
print("--- T6: the fix gate in _aud_parse ---")
NS["_AUD_VOCAB"] = {"at": 1.0, "freq": freq, "low": {}, "filler": None}
ROW0 = {"t": 1.0, "b": 3.5, "text": STT[0]["t"], "odd": []}
GOT = {"fixes": [{"n": 0, "heard": "Yalla Wanderer Alt-F4 duos Drakkari",
                  "why": "the game words, said as the lobby closed"}],
       "checked": []}
del LOGS[:]
r0 = NS["_aud_parse"](json.loads(json.dumps(GOT)), [dict(ROW0)])
check("without d the fix is refused by the sense gate, as at HEAD",
      r0[5] == [] and any("failed the sense test" in m for m in LOGS))
ROW1 = dict(ROW0, d="alt-f4 duos Drakkari", kind="ears", gap=0.8)
r1 = NS["_aud_parse"](json.loads(json.dumps(GOT)), [ROW1],
                      r"D:\scratch\Fortnite\Videos\Fortnite_20260905_010203.mp4")
check("with d the same fix passes: matched by second + was, why kept",
      len(r1[5]) == 1 and r1[5][0]["t"] == 1.0
      and r1[5][0]["was"] == STT[0]["t"]
      and r1[5][0]["heard"] == "Yalla Wanderer Alt-F4 duos Drakkari"
      and r1[5][0]["why"].startswith("the game words"))
check("_aud_parse still answers the old two-argument call",
      NS["_aud_parse"]({"fixes": []}, [])[5] == [])
check("_aud_apply_fixes is byte-identical to HEAD's (item 7)",
      seg(LSRC, LTREE, "_aud_apply_fixes")
      == seg(HSRC, HTREE, "_aud_apply_fixes"))

# =========================================================================
print("--- T7: the room's first spelling in the name check ---")
low = dict(("word%d" % i, 5) for i in range(300))
STT2 = [{"a": 1000, "b": 3000, "t": "yalla Faris come here we are about to "
                                    "lose the streak in duos tonight"},
        {"a": 5000, "b": 7000, "t": "Marit take the MMR hit please"}]
INS = {"title": "Duos night with Fares and Marid", "summary": ""}
VP = r"D:\scratch\Fortnite\Videos\Fortnite_20260905_010203.mp4"
rh, wh = HN["_aud_names"](VP, INS, STT2, low)
rt, wt = NS["_aud_names"](VP, INS, STT2, low)
check("with no room names the name check is HEAD's, row for row",
      (rt, wt) == (rh, wh) and [r["name"] for r in rt] == ["Fares", "Marid"])
check("(the fixture exercises both shapes: Fares said via the skeleton, "
      "Marid spelt Marit by the night)",
      rh[0]["verdict"] == "said" and rh[1]["verdict"] == "spelt"
      and rh[1]["said"] == "Marit")
NS["SETTINGS"]["room_names"] = "Wanderer, Faris / Fares, Marid / Marit"
rt2, wt2 = NS["_aud_names"](VP, INS, STT2, low)
check("a title's 'Fares' folds to the room's first spelling 'Faris'",
      rt2[0]["verdict"] == "spelt" and rt2[0]["said"] == "Faris"
      and "room's names" in rt2[0]["how"])
check("a title already spelt the room's way ('Marid') is not respelt "
      "toward the night's 'Marit'",
      rt2[1]["verdict"] == "said" and rt2[1].get("alias") == "Marit")
check("the spelt warning names the room's spelling",
      any("Fares" in w and "Faris" in w for w in wt2)
      and not any("Marit" in w for w in wt2))
INS3 = {"title": "Duos night with Wanderer", "summary": ""}
rt3, wt3 = NS["_aud_names"](VP, INS3, STT2, low)
check("the setting alone never puts a person in the room: an unsaid "
      "Wanderer stays unsaid",
      rt3[0]["verdict"] == "unsaid" and any("Wanderer" in w for w in wt3))
check("_room_first_of: any spelling -> the first; a stranger -> ''",
      NS["_room_first_of"]("fares") == "Faris"
      and NS["_room_first_of"]("Marit") == "Marid"
      and NS["_room_first_of"]("Wanderer") == "Wanderer"
      and NS["_room_first_of"]("Drakkari") == "" and NS["_room_first_of"]("") == "")
NS["SETTINGS"]["room_names"] = ""
check("_aud_apply_names is byte-identical to HEAD's (the respell writes "
      "whatever 'said' names)",
      seg(LSRC, LTREE, "_aud_apply_names") == seg(HSRC, HTREE, "_aud_apply_names"))

# =========================================================================
print("--- T8: the prompt, the log line, the laws ---")
sysp = re.sub(r"\s+", " ", NS["_AUD_SYSTEM"])
check("the prompt carries the two-ears paragraph",
      "STEP 1c - WEIGH THE TWO EARS." in sysp
      and "an English-only model that knows the game's words and the "
          "room's names but no Arabic" in sysp
      and "keep every Arabic word the first ear wrote" in sysp
      and "write ONE line that a person in that room would have said" in sysp
      and "Never merge two different sentences into one; when you cannot "
          "tell, leave the line alone." in sysp)
check("...placed between STEP 1b and STEP 2",
      sysp.index("STEP 1b") < sysp.index("STEP 1c") < sysp.index("STEP 2 -"))
check("the schema is unchanged", NS["_AUD_SCHEMA"] == HN["_AUD_SCHEMA"])
a1 = seg(LSRC, LTREE, "_audit_one")
check("the log line gains ', weighed the two ears on N line(s)' inside the "
      "summary, only when N > 0",
      '+ (", weighed the two ears on " + str(_eared) + " line(s)"' in a1
      and 'if _eared else "")' in a1
      and a1.index("weighed the two ears") > a1.index('log("The auditor on "')
      and a1.index("weighed the two ears") < a1.index('" name(s) respelt"'))
check("N counts the shortlist rows carrying d that went to the model",
      '_eared = len([g for g in ask_rows if g.get("d")])' in a1)
check("the union sits right after the garble shortlist, before the hints "
      "and the carry",
      a1.index("garble = _aud_garble(stt, _freq)")
      < a1.index("garble = _aud_ear_union(garble, _aud_ear_gap(stt))")
      < a1.index('_g["hints"] = _aud_hints(_g, _freq)')
      < a1.index("carried = _aud_carry(garble, _pg)"))
check("_AUD_V is 7, the value at HEAD",
      NS["_AUD_V"] == 7 == HN["_AUD_V"]
      and assign_src(LSRC, LTREE, "_AUD_V") == "_AUD_V = 7")
for nm in ("_aud_src", "_aud_owing", "_aud_owing_swept", "_aud_covers_now",
           "_aud_corrected", "_aud_garble", "_aud_carry",
           "_aud_apply_strikes", "_aud_relisten",
           "_aud_done_current"):
    check(nm + " is byte-identical to HEAD's (count-undoing / mtime laws)",
          seg(LSRC, LTREE, nm) == seg(HSRC, HTREE, nm))
check("the auditor still writes only its own sidecars: no new "
      "_atomic_write_json in the drop",
      LSRC.count("_atomic_write_json(") == HSRC.count("_atomic_write_json("))
check("_aud_dossier differs from HEAD's ONLY by the appended witness",
      seg(LSRC, LTREE, "_aud_dossier").replace(
          '\n            + "\\n".join(outl)\n'
          '            # 3.33 F the second ear\'s hearing and the room\'s '
          'names, after\n'
          '            # the conversation - the pack builder keeps this '
          'tail past\n'
          '            # its knife\n'
          '            + _aud_ear_note(g))',
          '\n            + "\\n".join(outl))')
      == seg(HSRC, HTREE, "_aud_dossier"))
check("the real _aud_garble never reads d (nothing without d is ever "
      "a candidate anywhere but _aud_ear_gap)",
      '"d"' not in seg(LSRC, LTREE, "_aud_garble"))
RV = seg(LSRC, LTREE, "_aud_revert_nonsense")
RV_HEAD = seg(HSRC, HTREE, "_aud_revert_nonsense")
RV_NEW = ('        ok, bad = _aud_sense(sg.get("t"), freq,\n'
          '                             _aud_ear_extra(sg, video_path))\n')
check("_aud_revert_nonsense differs from HEAD's ONLY by the extra it hands "
      "the sense gate (its comment aside)",
      RV.count(RV_NEW) == 1
      and re.sub(r"(?m)^        # .*\n", "", RV).replace(
          RV_NEW, '        ok, bad = _aud_sense(sg.get("t"), freq)\n')
      == re.sub(r"(?m)^        # .*\n", "", RV_HEAD)
      and "_aud_ear_extra" not in RV_HEAD)
check("the run_all roster lists ears333audit right after ears333test",
      re.search(r"ears333test\s+ears333audit\b",
                io.open(os.path.join(ROOT, "qa", "run_all.bat"),
                        encoding="utf-8").read()) is not None)
# DORMANT PARITY, end to end on the shortlist: a night without d takes
# HEAD's decisions - the garble rows, the hints, the carry
nod2 = [dict((k, v) for k, v in sg.items() if k != "d") for sg in STT]
gh = HN["_aud_garble"](nod2, freq)
gt = NS["_aud_garble"](nod2, freq)
gt = NS["_aud_ear_union"](gt, NS["_aud_ear_gap"](nod2))
check("a night without d: the shortlist is HEAD's, row for row", gh == gt)


# =========================================================================
print("--- T9: the sense reverter keeps an ear-weighed fix ---")
# scratch sidecars under a temp dir - <dir>/<stem>.<kind>.json; the tree
# and HEAD each get their own dir so the two nights never share a file
WRITES = []


def sidecars(ns, tag):
    tmp = tempfile.mkdtemp(prefix="ears333audit_" + tag + "_")

    def _atomic_write_json(p, d):
        WRITES.append(p)
        with io.open(p, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False)
    ns.update({"time": time, "_aud_bank_orig": lambda *a, **k: None,
               "_atomic_write_json": _atomic_write_json,
               "_ai_sidecar": lambda vp, kind: os.path.join(
                   tmp, os.path.splitext(os.path.basename(vp))[0]
                   + "." + kind + ".json")})
    return tmp


TMP_T = sidecars(NS, "tree")
TMP_H = sidecars(HN, "head")
for nm in ("_aud_revert_nonsense", "_aud_apply_fixes", "_aud_apply_strikes",
           "_aud_keep_split", "_aud_word_seen"):
    extract(LSRC, LTREE, nm, NS)
    extract(HSRC, HTREE, nm, HN)
VPF = r"D:\scratch\Fortnite\Videos\Fortnite_20260905_010203.mp4"


def night(ns, segs):
    p = ns["_ai_sidecar"](VPF, "stt")
    with io.open(p, "w", encoding="utf-8") as fh:
        json.dump({"v": 3, "reader": 7, "segments": json.loads(json.dumps(segs))},
                  fh, ensure_ascii=False)
    return p


def doc_of(p):
    return json.load(io.open(p, encoding="utf-8"))


# the night under test: the sheet's line (with the draft that admitted the
# fix) and one agreeing neighbour - STT's own line 4 is a pre-fixed line
# the vocabulary never saw, which HEAD's reverter takes back too
STTD = json.loads(json.dumps(STT[:2]))
STTD[0]["d"] = "we're about to lose our freak alt-f4 duos drakkari"
spT = night(NS, STTD)
check("(setup) the ear-weighed fix from T6 lands on the scratch sidecar",
      NS["_aud_apply_fixes"](VPF, json.loads(json.dumps(r1[5]))) == 1
      and doc_of(spT)["segments"][0]["t"] == "Yalla Wanderer Alt-F4 duos Drakkari"
      and doc_of(spT)["segments"][0]["d"] == STTD[0]["d"])
del LOGS[:]
took = NS["_aud_revert_nonsense"](VPF, freq)
s0 = doc_of(spT)["segments"][0]
check("the next audit's reverter KEEPS it: the segment's own d, the room "
      "and the game are the evidence that admitted the fix",
      took == 0 and s0["t"] == "Yalla Wanderer Alt-F4 duos Drakkari"
      and s0["fx"] == 1 and s0["was"] == STT[0]["t"] and not LOGS)
check("...so the line is no longer an ear-gap candidate (no oscillation)",
      0 not in [r["n"] for r in gap(doc_of(spT)["segments"])])
# the same fix on a segment WITHOUT d: the tree and HEAD take it back alike
NOD = json.loads(json.dumps(doc_of(spT)["segments"]))
NOD[0].pop("d", None)
spT2 = night(NS, NOD)
spH2 = night(HN, NOD)
tookT = NS["_aud_revert_nonsense"](VPF, freq)
tookH = HN["_aud_revert_nonsense"](VPF, freq)
check("a segment without d hands None: the decision is HEAD's (taken back "
      "by both, byte-identical sidecars)",
      tookT == tookH == 1
      and io.open(spT2, encoding="utf-8").read()
      == io.open(spH2, encoding="utf-8").read()
      and doc_of(spT2)["segments"][0]["t"] == STT[0]["t"]
      and "fx" not in doc_of(spT2)["segments"][0])
# extra never vouches for Arabic noise, so an eared fix that IS gibberish
# still goes back
GIB = json.loads(json.dumps(STT[:2]))
GIB[0].update({"t": "\u0646\u0627\u0641\u0648 \u062a\u0631\u0648\u0646\u0648\u0645",
               "was": STT[0]["t"], "fx": 1, "d": "nafo tronom go go"})
spG = night(NS, GIB)
check("an eared fix that is Arabic-lettered noise is still taken back",
      NS["_aud_revert_nonsense"](VPF, freq) == 1
      and doc_of(spG)["segments"][0]["t"] == STT[0]["t"])
check("a pinned eared fix is never re-judged",
      night(NS, [dict(GIB[0], pin=1)]) and NS["_aud_revert_nonsense"](VPF, freq) == 0)
check("every sidecar written sat under the scratch dirs, never the library",
      WRITES and all(p.startswith(TMP_T) or p.startswith(TMP_H) for p in WRITES))
check("_aud_apply_fixes / _aud_apply_strikes still byte-identical to HEAD's",
      seg(LSRC, LTREE, "_aud_apply_fixes") == seg(HSRC, HTREE, "_aud_apply_fixes")
      and seg(LSRC, LTREE, "_aud_apply_strikes")
      == seg(HSRC, HTREE, "_aud_apply_strikes"))

# =========================================================================
print("--- T10: a noise verdict on a pure ear-gap row weighs as unclear ---")
ROWe = dict(ROW1)              # kind=ears, d, no odd words, no relisten ear
GOTn = {"fixes": [], "checked": [{"n": 0, "verdict": "noise",
                                  "why": "could not make sense of it"}]}
NS["_aud_parse"](json.loads(json.dumps(GOTn)), [ROWe], VPF)
check("the thinker's 'noise' on a pure ear row becomes 'unclear', marked "
      "wit_kept, the why kept",
      ROWe["verdict"] == "unclear" and ROWe.get("wit_kept") is True
      and ROWe["vwhy"] == "could not make sense of it")
spN = night(NS, STTD)
del WRITES[:]
check("...and _aud_apply_strikes strikes nothing: the line stays readable",
      NS["_aud_apply_strikes"](VPF, [ROWe], None, freq) == 0
      and doc_of(spN)["segments"][0]["t"] == STT[0]["t"]
      and "nn" not in doc_of(spN)["segments"][0] and not WRITES)
ROWm = dict(ROW0, d=ROW1["d"], gap=0.8, odd=["Yalla"])   # a merged row: no kind
NS["_aud_parse"](json.loads(json.dumps(GOTn)), [ROWm], VPF)
ROWh = dict(ROW0, odd=["Yalla"])                          # HEAD's row, no d
HN["_AUD_VOCAB"] = NS["_AUD_VOCAB"]
HN["_aud_parse"](json.loads(json.dumps(GOTn)), [ROWh])
check("a merged garble+ear row keeps its odd words and stays strikeable, "
      "exactly as HEAD judges the row without d",
      ROWm["verdict"] == "noise" == ROWh["verdict"]
      and "wit_kept" not in ROWm and "wit_kept" not in ROWh)
ROWr = dict(ROW1)
GOTr = {"fixes": [], "checked": [{"n": 0, "verdict": "right", "why": "a real line"}]}
NS["_aud_parse"](json.loads(json.dumps(GOTr)), [ROWr], VPF)
check("'right' and 'unclear' on an ear row pass through untouched",
      ROWr["verdict"] == "right" and "wit_kept" not in ROWr)
ap = seg(LSRC, LTREE, "_aud_parse")
check("the witness clause sits before the ear veto in the checked loop",
      ap.index('row.get("kind") == "ears"') < ap.index("THE VETO MUST DEMAND MORE"))

# =========================================================================
print("--- T11: the ask budget ---")
check("_AUD_EAR_ASK is 12 and _AUD_ASK_CHARS is 32000",
      NS["_AUD_EAR_ASK"] == 12 and NS["_AUD_ASK_CHARS"] == 32000)
extract(LSRC, LTREE, "_aud_ear_budget", NS)
NS["SETTINGS"]["room_names"] = "Wanderer, Faris / Fares, Marid"
LONG = [{"a": 1000 * i, "b": 1000 * i + 900,
         "t": "Line number %d of the room talking about duos and MMR and "
              "the queue and the lobby and the streak tonight" % i,
         "lang": "english"} for i in range(80)]
SRCL = {"stt": LONG, "sns": None, "vis": None, "laughs": [],
        "ins": {"chapters": [{"t": 0, "label": "the queue"}]}}
GARB = [{"t": float(i), "b": i + 0.9, "text": LONG[i]["t"], "odd": ["Yalla"],
         "hints": []} for i in range(0, 60, 6)]                # 10 garble rows
EARS = [{"t": float(i), "b": i + 0.9, "text": LONG[i]["t"], "was": LONG[i]["t"],
         "d": "married do us cue number %d of the room" % i, "odd": [],
         "kind": "ears", "gap": round(1.0 - i / 100.0, 2), "hints": []}
        for i in range(70, 30, -1)]                            # 40 ear rows
rows = GARB + EARS
del LOGS[:]
body0 = NS["_aud_body"]([], [], "Fortnite", 600.0, SRCL, [], [], rows)
check("(fixture) a full shortlist - 10 garble + 40 ear rows - runs past "
      "the budget", len(body0) > NS["_AUD_ASK_CHARS"])
body1 = NS["_aud_ear_budget"](VPF, [], [], "Fortnite", 600.0, SRCL, [], [],
                              rows, body0)
check("the guard cuts the tail until the ask fits, ear rows only, in place",
      len(body1) <= NS["_AUD_ASK_CHARS"] and rows[:10] == GARB
      and len(rows) < 50 and all(r.get("kind") == "ears" for r in rows[10:])
      and rows[10:] == EARS[:len(rows) - 10])
check("...the body returned is the ask over exactly those rows",
      body1 == NS["_aud_body"]([], [], "Fortnite", 600.0, SRCL, [], [], rows)
      and ("(%d) " % (len(rows) - 1)) in body1
      and ("(%d) " % len(rows)) not in body1)
check("...and says so in the log",
      any("ear-gap row(s) off the ask" in m and "Fortnite_20260905_010203" in m
          for m in LOGS))
del LOGS[:]
body2 = NS["_aud_ear_budget"](VPF, [], [], "Fortnite", 600.0, SRCL, [], [],
                              rows, body1)
check("an ask that fits is handed back untouched, nothing logged",
      body2 is body1 and not LOGS)
MANYG = [dict(g, t=float(i), b=i + 0.9, text=LONG[i]["t"])
         for i, g in enumerate([GARB[0]] * 60)]
bodyg = NS["_aud_body"]([], [], "Fortnite", 600.0, SRCL, [], [], MANYG)
keepg = list(MANYG)
check("a night without d (garble rows only, however long) loses no row: "
      "the guard never cuts a garble row",
      len(bodyg) > NS["_AUD_ASK_CHARS"]
      and NS["_aud_ear_budget"](VPF, [], [], "Fortnite", 600.0, SRCL, [], [],
                                MANYG, bodyg) is bodyg
      and MANYG == keepg and not LOGS)
check("an empty table is handed back as it came",
      NS["_aud_ear_budget"](VPF, [], [], "Fortnite", 600.0, SRCL, [], [],
                            [], "x") == "x")
NS["SETTINGS"]["room_names"] = ""
# the count cap: the real loop out of _audit_one, run on a fixture
a1 = seg(LSRC, LTREE, "_audit_one")
i0 = a1.index("        _ears_n = 0\n")
i1 = a1.index("        ask_rows = _kept\n") + len("        ask_rows = _kept\n")
cap_ns = {"_AUD_EAR_ASK": NS["_AUD_EAR_ASK"],
          "ask_rows": [dict(g) for g in GARB[:3]] + [dict(e) for e in EARS]}
exec(compile(textwrap.dedent(a1[i0:i1]), "<cap>", "exec"), cap_ns)
check("the count cap in _audit_one: 3 garble + 40 ear rows -> 3 + 12, the "
      "most-different ear rows, in order",
      len(cap_ns["ask_rows"]) == 15
      and [r["text"] for r in cap_ns["ask_rows"][:3]] == [g["text"] for g in GARB[:3]]
      and [r["d"] for r in cap_ns["ask_rows"][3:]] == [e["d"] for e in EARS[:12]])
cap_ns2 = {"_AUD_EAR_ASK": NS["_AUD_EAR_ASK"],
           "ask_rows": [dict(g) for g in GARB]}
exec(compile(textwrap.dedent(a1[i0:i1]), "<cap>", "exec"), cap_ns2)
check("...and a night without d keeps every row",
      cap_ns2["ask_rows"] == GARB)
check("the cap sits after the carry filter and before the relisten, the "
      "ETA and the ask; the ear count is taken again after the ask",
      a1.index('ask_rows = [g for g in (garble or []) if not g.get("carried")]')
      < a1.index("if _ears_n > _AUD_EAR_ASK:")
      < a1.index('_eared = len([g for g in ask_rows if g.get("d")])')
      < a1.index("_aud_relisten(video_path, ask_rows)")
      < a1.index("ask_eta=60.0 + per * len(ask_rows)")
      < a1.rindex('_eared = len([g for g in ask_rows if g.get("d")])')
      < a1.index("weighed the two ears"))
th = seg(LSRC, LTREE, "_aud_thread")
check("_aud_thread runs the guard right after building the body on BOTH "
      "asks (the thinker's and the describer's)",
      th.count("_aud_ear_budget(video_path, anchors, drops, game, dur, src,") == 2
      and th.count("body = _aud_body(anchors, drops, game, dur, src, places, crs,") == 2
      and th.index("_aud_ear_budget(") > th.index("body = _aud_body(")
      and th.rindex("_aud_ear_budget(") > th.rindex("body = _aud_body(")
      and th.index("_aud_ear_budget(") < th.index("max_tokens=1600 + 80 * len(garble or [])")
      and th.rindex("_aud_ear_budget(") < th.index("max_tokens=900 + (60 * len(garble or []))"))
check("_aud_relisten still re-hears garble[:8] - no extra plays a night",
      "for g in garble[:8]:" in seg(LSRC, LTREE, "_aud_relisten"))

print("%d ok, %d failed" % (OK, FAIL))
sys.exit(1 if FAIL else 0)
