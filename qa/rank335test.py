# -*- coding: utf-8 -*-
"""3.35 drop L - THE GAME DECIDES ITS PLACE IN THE QUEUE.

Lifts the REAL pieces out of lore.py (DEFAULTS, _sanitize_settings,
_parse_clip_name, _display_name, _cap_game_key, _game_sources_key,
_game_rank, _force_owes, and the two ordering bands themselves) into
stub namespaces on a tempdir, and holds them to:
  (1) the setting: game_rank defaults to {}, and the clamp keeps only
      short string keys with one of the four words, at most two hundred
      of them - a settings file is untrusted input;
  (2) _game_rank: unknown is "normal", its key is the SHELF'S key (a
      real path driven through both helpers), and the path->key cache
      never outlives a change of rank;
  (3) the order: rank band first, recency inside the band, a "never"
      game absent altogether, and - with no ranks set - a list
      identical to the plain recency sort this replaces;
  (4) the walk and its read-only twin _ai_next_sweep carry the SAME
      band, so the Working page's "next" cannot disagree with the walk;
  (5) a direct ask is never refused: _force_owes does not know the rank
      exists, a "never" night still owes, and the forced road in
      _ai_tick stands ahead of the walk it does not belong to;
  (6) the panel: four states on the chapter's own row, the tip that
      says a night asked for by name always runs, the settings road it
      saves through, the held-back word on the Working page, and the
      MOCK that carries game_rank so the preview page works.
Nothing under the real shelf is touched: no video, no model, no port.
"""
import ast
import io
import os
import re
import sys
import tempfile
import textwrap

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


TMP = tempfile.mkdtemp(prefix="rank335_")

# =======================================================================
print("--- 1: the setting, and the clamp that distrusts the file ---")
DEF = lift_assign("DEFAULTS", {"_default_output_dir": lambda: TMP})
check("DEFAULTS carries game_rank, and it starts empty",
      DEF.get("game_rank") == {} and isinstance(DEF["game_rank"], dict))
check("the four words live next to the clamp, and 'never' is NOT an "
      "ordering position - it is filtered out, never sorted",
      '_GAME_RANKS = ("first", "normal", "later", "never")' in SRC
      and '_RANK_ORDER = {"first": 0, "normal": 1, "later": 2}' in SRC)

nsS = {"re": re, "os": os, "DEFAULTS": DEF}
lift_assign("_GAME_RANKS", nsS)
extract("_room_names_clamp", nsS)
san = extract("_sanitize_settings", nsS)


def clamped(v):
    d = dict(DEF)
    d["game_rank"] = v
    san(d)
    return d["game_rank"]


check("a good dict survives, lower-cased and stripped",
      clamped({"Elden Ring": "LATER", " rocket league ": "first"})
      == {"elden ring": "later", "rocket league": "first"})
check("a word that is not one of the four is dropped",
      clamped({"a": "sometimes", "b": "never"}) == {"b": "never"})
check("a key over eighty characters is dropped; an empty key too",
      clamped({"k" * 81: "later", "  ": "first", "ok": "normal"})
      == {"ok": "normal"})
check("a non-string key or value is dropped",
      clamped({"a": 5, "b": ["later"], "c": "first"}) == {"c": "first"})
check("a non-dict collapses to the default, not to a crash",
      clamped("first") == {} and clamped(None) == {} and clamped([1, 2]) == {})
big = clamped(dict(("g%03d" % i, "later") for i in range(300)))
check("three hundred games are trimmed to two hundred", len(big) == 200)
d = dict(DEF)
d.pop("game_rank")
san(d)
check("a settings file without it falls back to {}", d["game_rank"] == {})

# =======================================================================
print("\n--- 2: _game_rank - the shelf's own key, read live ---")
NS = {"os": os, "re": re, "SETTINGS": {}}
lift_assign("_GAME_NAMES", NS)
lift_assign("_GAME_RANKS", NS)
lift_assign("_RANK_ORDER", NS)
lift_assign("_GAME_RANK_KEY", NS)
NS["_auto_name_for_raw"] = lambda s: None
NS["_apply_user_name"] = lambda s: s
extract("_parse_clip_name", NS)
extract("_display_name", NS)
extract("_cap_game_key", NS)
extract("_game_sources_key", NS)
_game_rank = extract("_game_rank", NS)
SET = NS["SETTINGS"]

SHELF = os.path.join(TMP, "shelf")
P_ALPHA_A = os.path.join(SHELF, "Alpha", "Videos", "Alpha_20260901_120000.mp4")
P_ALPHA_B = os.path.join(SHELF, "Alpha", "Videos", "Alpha_20260902_120000.mp4")
P_BETA_A = os.path.join(SHELF, "Beta", "Videos", "Beta_20260903_120000.mp4")
P_BETA_B = os.path.join(SHELF, "Beta", "Clips", "Beta_clip_20260904_120000.mp4")
P_GAMMA = os.path.join(SHELF, "Gamma", "Videos", "Gamma_20260905_120000.mp4")
P_DELTA = os.path.join(SHELF, "Delta", "Videos", "Delta_20260906_120000.mp4")

check("an unknown game is 'normal' - a shelf with no ranks behaves "
      "exactly as it always did",
      _game_rank(P_ALPHA_A) == "normal" and _game_rank(P_DELTA) == "normal")
check("the key is the SHELF'S key: a real path through _game_rank's own "
      "cache and through the grouping helper agree",
      NS["_GAME_RANK_KEY"][P_ALPHA_A]
      == NS["_game_sources_key"](os.path.basename(P_ALPHA_A))
      == "alpha")
check("a clip and a session of the same game share one key - one chapter, "
      "one rank", NS["_cap_game_key"](P_BETA_A) == NS["_cap_game_key"](P_BETA_B))

SET["game_rank"] = {"alpha": "first", "gamma": "later", "delta": "never"}
check("the cache holds the KEY, never the rank: a press in the panel "
      "lands on the very next call, with no restart",
      _game_rank(P_ALPHA_A) == "first" and _game_rank(P_GAMMA) == "later"
      and _game_rank(P_DELTA) == "never" and _game_rank(P_BETA_A) == "normal")
SET["game_rank"] = {"alpha": "later"}
check("...and again when he changes his mind",
      _game_rank(P_ALPHA_A) == "later" and _game_rank(P_DELTA) == "normal")
SET["game_rank"] = {"alpha": "sideways"}
check("a word the clamp would have refused still answers 'normal' here",
      _game_rank(P_ALPHA_A) == "normal")
SET.pop("game_rank")
check("no setting at all is 'normal', not a crash",
      _game_rank(P_ALPHA_A) == "normal")

# =======================================================================
print("\n--- 3: the order - rank band, then recency ---")
# ONE ASK PER PATH (review 335). SETTINGS is re-bound by
# load_settings() on the pywebview thread, so a filter pass and a
# sort pass that each asked _game_rank could read two different
# answers for one path - and _RANK_ORDER has no 'never' key.
BAND_TICK = (
    '        rk = {pm[0]: _game_rank(pm[0]) for pm in vids}\n'
    '        vids = [pm for pm in vids if rk[pm[0]] != "never"]\n'
    '        vids.sort(key=lambda pm: (_RANK_ORDER[rk[pm[0]]], -pm[1]))\n')
BAND_NEXT = (
    '            rk = {pm[0]: _game_rank(pm[0]) for pm in vids}\n'
    '            vids = [pm for pm in vids if rk[pm[0]] != "never"]\n'
    '            vids.sort(key=lambda pm: (_RANK_ORDER[rk[pm[0]]], -pm[1]))\n')
# the band this replaces, kept so the fix can be MEASURED against
# the fault it was written for - not merely asserted.
BAND_TWO_ASKS = (
    '        vids = [pm for pm in vids if _game_rank(pm[0]) != "never"]\n'
    '        vids.sort(key=lambda pm: (_RANK_ORDER[_game_rank(pm[0])],\n'
    '                                  -pm[1]))\n')
TICK = func_src("_ai_tick")
NEXT = func_src("_ai_next_sweep")
check("the walk carries the band exactly once", TICK.count(BAND_TICK) == 1)
check("the read-only twin carries it exactly once too",
      NEXT.count(BAND_NEXT) == 1)
check("and the two are the SAME band to the byte, indent aside - the "
      "Working page's 'next' can never disagree with the walk",
      textwrap.dedent(BAND_TICK) == textwrap.dedent(BAND_NEXT))
check("the old bare recency sort is gone from both",
      "vids.sort(key=lambda pm: -pm[1])" not in TICK
      and "vids.sort(key=lambda pm: -pm[1])" not in NEXT)


def run_band(band, vids):
    ns = {"_game_rank": _game_rank, "_RANK_ORDER": NS["_RANK_ORDER"],
          "vids": list(vids)}
    exec(compile(textwrap.dedent(band), "<band>", "exec"), ns)
    return ns["vids"]


VIDS = [(P_ALPHA_A, 100), (P_ALPHA_B, 500), (P_BETA_A, 900),
        (P_BETA_B, 200), (P_GAMMA, 1000), (P_DELTA, 1100)]
SET["game_rank"] = {"alpha": "first", "gamma": "later", "delta": "never"}
got = run_band(BAND_TICK, VIDS)
check("first by recency, then normal by recency, then later - and the "
      "'never' game is not in the list at all",
      [p for p, _m in got] == [P_ALPHA_B, P_ALPHA_A, P_BETA_A, P_BETA_B,
                               P_GAMMA])
check("the twin's band gives the identical answer on the identical shelf",
      run_band(BAND_NEXT, VIDS) == got)

SET["game_rank"] = {}
check("PARITY: with no ranks at all the list is byte-identical to the "
      "plain recency sort this replaces",
      run_band(BAND_TICK, VIDS)
      == sorted(VIDS, key=lambda pm: -pm[1])
      == run_band(BAND_NEXT, VIDS))
SET["game_rank"] = {"alpha": "never", "beta": "never", "gamma": "never",
                    "delta": "never"}
check("a shelf ranked 'never' end to end sweeps nothing - and still does "
      "not crash", run_band(BAND_TICK, VIDS) == [])

# =======================================================================
print("\n--- 4: the tail passes ride the same list ---")
tail = TICK[TICK.index("if do_hl and not playing:"):]
check("the screen reader / librarian tail walks `vids` itself, so it "
      "inherits the order and the 'never' filter for free",
      "for p in vids:" in tail
      and "_game_rank" not in tail.split("for p in vids:")[1])
check("the walk itself walks the same list", "\n    for p in vids:\n" in TICK)
# THE THIRD READER. "Why is this waiting?" counts a place off its own
# scan of the shelf - before drop L that scan was the bare recency
# sort, so the plate would have reported a number the sweep was never
# going to honour, and a "never" night a place it does not have.
WHY = None
for _n in ast.parse(SRC).body:
    if isinstance(_n, ast.ClassDef) and _n.name == "_JsApi":
        for _m in _n.body:
            if isinstance(_m, ast.FunctionDef) and _m.name == "ai_whynot":
                WHY = "\n".join(
                    SRC.splitlines()[_m.lineno - 1:_m.end_lineno])
_WB = re.search(r"[ ]*rk = \{pm.*?-pm\[1\]\)\)\n", WHY or "", re.S)
check("ai_whynot exists and carries the SAME band, indent aside",
      WHY is not None and _WB is not None
      and textwrap.dedent(_WB.group(0)) == textwrap.dedent(BAND_TICK)
      and "vids.sort(key=lambda pm: -pm[1])" not in WHY)
check("...and hands the plate the word, so the number and the reason "
      "arrive together", '"rank": _game_rank(p)}' in WHY)
check("the plate spends the word beside the place, and says the plain "
      "thing when there is no place at all",
      "+(rankWord(a.rank)?' \\u2014 '+esc(rankWord(a.rank))"
      ":' (newest first)')));" in USRC
      and "else if(a.rank==='never')b.append(el('div','wngate'," in USRC
      and "queue:14,total:1757,asked:null,rank:'later'," in USRC)
check("_game_rank is asked in _ai_tick ONCE, in the band - not by the "
      "walk, not by the forced road, not by the tail, and not twice "
      "over the same candidate",
      TICK.count("_game_rank") == 1)

# =======================================================================
print("\n--- 5: a direct ask is never refused ---")
nsF = {"os": os, "SETTINGS": {"ai_highlights": True, "ai_transcribe": True},
       "_ai_sidecar_fresh": lambda p, k: False,
       "_lvl_coarse_cached": lambda p: True,
       "_reader_paths": lambda: ("reader",),
       "_stt_stale_reader": lambda p: False,
       "_describer_paths": lambda: None,
       "_ins_owing": lambda p: False, "_sns_owing": lambda p: False,
       "_vis_owing": lambda p: False, "_aud_owing": lambda p: False,
       "_ins_done_honest": lambda p: True}
_force_owes = extract("_force_owes", nsF)
SET["game_rank"] = {"delta": "never"}
check("the night's game is ranked 'never on its own'",
      _game_rank(P_DELTA) == "never")
check("...and a forced ask on it still owes both passes",
      _force_owes(P_DELTA, "all") == {"listening", "hearing"})
check("_force_owes has never heard of the rank - the rank orders the "
      "sweep, it is not a veto",
      "_game_rank" not in func_src("_force_owes")
      and "game_rank" not in func_src("_force_owes"))
check("the forced road stands AHEAD of the walk, and is not inside it",
      TICK.index('fp = _AI.get("force")') < TICK.index("\n    for p in vids:\n"))
check("the code says so in its own words, in all three places a "
      "reader would look",
      "IT IS NEVER A REFUSAL" in func_src("_game_rank")
      and "a direct ask still runs, rank or no" in TICK
      and "asking for a night by name always works" in USRC)
check("the waiting line carries the word, so an asked-for night on a "
      "held-back game explains itself",
      '"rank": _game_rank(it[0]),' in SRC
      and '"rank": _game_rank(p)}' in SRC)

# =======================================================================
print("\n--- 6: the panel, read from ui.html ---")
check("the chip exists on the chapter's own row, drawn before the arrow",
      "function rankChip(g){" in USRC
      and "const rc=rankChip(g); if(rc)r.append(rc);" in USRC
      and USRC.index("const rc=rankChip(g)")
      < USRC.index("    if(has)r.addEventListener('click',"))
check("four states, in the tome's voice",
      "const RANKS=['first','normal','later','never'];" in USRC
      and "first:'ahead of the rest'" in USRC
      and "normal:'in its turn'" in USRC
      and "later:'when the rest are done'" in USRC
      and "never:'never on its own'" in USRC)
check("a click CYCLES the four, and 'normal' is the absence of a rank so "
      "the two-hundred clamp is never filled with defaults",
      "RANKS[(RANKS.indexOf(rankOf(g.key))+1)%RANKS.length]" in USRC
      and "if(r==='normal')delete next[g.key];else next[g.key]=r;" in USRC)
check("the tip explains the state AND says a direct ask always works",
      "asking for a night by name always works" in USRC
      and "the tome never picks this game on its own" in USRC)
check("the press does not open the chapter underneath it",
      "ev.stopPropagation();" in USRC[USRC.index("function rankChip(g){"):
                                      USRC.index("function renderContents(")])
check("it saves through the EXISTING settings road, so it survives a "
      "restart", "queueSave({game_rank:next});" in USRC)
check("...and it is only drawn when the AI suite is on",
      "function aiSuiteOn(){" in USRC
      and "if(!aiSuiteOn())return null;" in USRC)
check("the chip has its own type in the shelf's hand, all four states",
      ".grow .grank{" in USRC and ".grow .grank.r-first{" in USRC
      and ".grow .grank.r-later{" in USRC and ".grow .grank.r-never{" in USRC)
check("the Working page's next pick names the state it is being held at",
      "function rankWord(r){" in USRC
      and "+(rankWord(nx.rank)?'  \\u00b7  '+esc(rankWord(nx.rank)):'')));"
      in USRC
      and "+(rankWord(it.rank)?'  \\u00b7  '+esc(rankWord(it.rank)):'')));"
      in USRC)
check("...and the repaint signature moves when the rank does, or the "
      "word would never appear", "nx&&nx.rank,sd]);" in USRC
      and "x.wait||'',x.rank||'']" in USRC)
check("MOCK carries game_rank in both settings and state, and a ranked "
      "next pick, so the preview page draws it",
      "second_ear:true,room_names:'',my_name:'',game_rank:{}," in USRC
      and "my_name:'',game_rank:{},version:'3.36'" in USRC
      and "next:{name:'mock night.mp4',kind:'listening',rank:'later'}" in USRC)

# =======================================================================
print("\n--- 7: review 335 - the consistency window, and the number "
      "that cannot reach zero ---")


def flipping_rank(after):
    """A rank that answers 'normal' for the first `after` asks and
    'never' from then on - a chip pressed mid-band, exactly."""
    box = [0]

    def rank(_p):
        box[0] += 1
        return "normal" if box[0] <= after else "never"
    return rank


def run_with(band, vids, rank):
    ns = {"_game_rank": rank, "_RANK_ORDER": NS["_RANK_ORDER"],
          "vids": list(vids)}
    exec(compile(textwrap.dedent(band), "<band>", "exec"), ns)
    return ns["vids"]


raised = None
try:
    run_with(BAND_TWO_ASKS, VIDS, flipping_rank(len(VIDS)))
except KeyError:
    raised = "KeyError"
except Exception as e:
    raised = type(e).__name__
check("THE FAULT IS REAL: the two-ask band, driven by a rank that changes "
      "between the filter and the sort, raises KeyError - a lost beat, "
      "a blank 'next', a missing place-in-the-sweep line",
      raised == "KeyError")
still = None
try:
    still = run_with(BAND_TICK, VIDS, flipping_rank(len(VIDS)))
except Exception as e:
    still = type(e).__name__
check("THE REMEDY MEASURES: the shipped band asks once, so the same driver "
      "gives a whole, plainly-ordered list instead",
      isinstance(still, list) and len(still) == len(VIDS)
      and [p for p, _m in still]
      == [p for p, _m in sorted(VIDS, key=lambda pm: -pm[1])])
check("all three readers ask once and read the same answer twice - one "
      "dict, then a filter and a sort that cannot disagree",
      TICK.count("rk = {pm[0]: _game_rank(pm[0]) for pm in vids}") == 1
      and NEXT.count("rk = {pm[0]: _game_rank(pm[0]) for pm in vids}") == 1
      and (WHY or "").count(
          "rk = {pm[0]: _game_rank(pm[0]) for pm in vids}") == 1
      and "_RANK_ORDER[_game_rank(" not in SRC
      and 'if _game_rank(pm[0]) != "never"' not in SRC)

# ---- the standing tally: the held-back share is counted, not hidden
nsT = {
    "time": __import__("time"), "os": os, "_AI": {},
    "SETTINGS": {"output_dir": TMP},
    "_library_dirs": lambda out: [(SHELF, "video")],
    "_scan_dir_mp4s": lambda d, k: [
        {"path": P_ALPHA_A, "mtime": 1}, {"path": P_BETA_A, "mtime": 2},
        {"path": P_GAMMA, "mtime": 3}, {"path": P_DELTA, "mtime": 4}],
    "_ai_sidecar_fresh": lambda p, s: False,
    "_ins_done_honest": lambda p: False,
    "_ins_owing": lambda p: True,
    "_ai_sidecar": lambda p, s: os.path.join(TMP, "nothing.json"),
    "_secs_no_probe": lambda v: 60.0,
    "_aud_done_current": lambda p: False,
    "_game_rank": _game_rank}
_tally = extract("_ai_tally", nsT)
SET["game_rank"] = {"delta": "never"}
T1 = _tally()
check("the tally counts the held-back share on the walk it already "
      "makes - one night on the shelf is never swept on its own",
      T1.get("held_back") == 1 and T1["total"] == 4)
check("...and it does NOT un-owe that night: a rank may reorder the "
      "walk, it may never make the count lie",
      T1["thinking"]["left"] == 4 and T1["hearing"]["left"] == 4
      and T1["listening"]["left"] == 4)
nsT["_AI"].clear()
SET["game_rank"] = {}
T0 = _tally()
check("no ranks at all, and the share is a plain zero",
      T0.get("held_back") == 0 and T0["thinking"]["left"] == 4)
nsT["_AI"].clear()
SET["game_rank"] = {"alpha": "never", "beta": "never",
                    "gamma": "never", "delta": "never"}
TA = _tally()
check("a shelf held back end to end says so, and still owes every "
      "night of it", TA.get("held_back") == 4
      and TA["thinking"]["left"] == 4
      # 3.36 F2: ...and each lane's held is OF ITS LEFT (4 of 4 here)
      and all(TA[j]["held"] == 4 for j in ("listening", "hearing",
                                            "thinking")))
check("the counter rides the walk the tally already makes - no second "
      "pass over the shelf for a number",
      func_src("_ai_tally").count("_game_rank(p)") == 1
      and func_src("_ai_tally").count("for v in _scan_dir_mp4s") == 1)
check("the status road hands the share to the page - each lane's own "
      "(3.36 F2), never the shelf-wide number",
      '"held": k.get("held", 0),' in SRC
      and '"held": t.get("held_back", 0),' not in SRC)

# ---- 3.36 F2: the held-back share is OF THE LEFT. Two never nights
# fully done on every lane and one normal night owing everything used
# to print '1 left - 2 never on their own' on every row.
_doneN = set()
nsT2 = dict(nsT)
nsT2["_AI"] = {}
nsT2["_ai_sidecar_fresh"] = lambda p, s: p in _doneN
nsT2["_ins_done_honest"] = lambda p: p in _doneN
nsT2["_ins_owing"] = lambda p: p not in _doneN
nsT2["_aud_done_current"] = lambda p: p in _doneN
_tally2 = extract("_ai_tally", nsT2)
SET["game_rank"] = {"alpha": "never", "beta": "never"}
_doneN.update({P_ALPHA_A, P_BETA_A})
TD = _tally2()
check("two never nights done on every lane, two normal nights owing: "
      "held is 0 on every lane (the never nights are not 'left')",
      all(TD[j]["left"] == 2 and TD[j]["held"] == 0
          for j in ("listening", "hearing", "thinking"))
      and TD["auditing"]["left"] == 0 and TD["auditing"]["held"] == 0
      and TD.get("held_back") == 2)
_doneN.discard(P_BETA_A)
nsT2["_AI"].clear()
TD2 = _tally2()
check("...un-do one never night and it is back in left AND in held - "
      "a rank never un-owes a night, and held <= left on every lane",
      TD2["thinking"]["left"] == 3 and TD2["thinking"]["held"] == 1
      and all(TD2[j]["held"] <= TD2[j]["left"]
              for j in ("listening", "hearing", "thinking", "auditing")))
nsT["_AI"].clear()
SET["game_rank"] = {}

# ---- and the Working page spends it
check("the standing tally says the held-back share in words, beside "
      "the number it explains",
      "(k.held?num(k.held)+' never on their own':null)," in USRC
      and USRC.index("num(k.left)+' left'")
      < USRC.index("never on their own':null)"))
check("the line still opens by saying whose numbers these are",
      "const tally=k?('the whole shelf: '+[" in USRC)
check("MOCK carries the share in all three lanes, so the preview page "
      "draws the sentence", USRC.count(",held:214") == 3)

# ---- the auditor's repair road says what a 'never' game costs it
_ASK1 = func_src("_ai_ask_first")
check("the auditor's repair road says in its own words that a "
      "'never' game forgoes the repair until he asks by name - a "
      "silent consequence with a line saying why is not silent",
      'A "NEVER" GAME FORGOES THIS REPAIR' in _ASK1
      and "until he asks for" in _ASK1
      and "_game_rank" not in _ASK1)

# =======================================================================
print("\n--- the laws this drop must not break ---")
check("no owe cache, no reader contract and no _AUD_V were touched - a "
      "rank reorders the walk, it never re-owes or un-owes a night",
      "_AUD_V = 7" in SRC and "_game_rank" not in func_src("_aud_src")
      and "_game_rank" not in func_src("_ins_owing"))
check("the sweep's ONE JOB SLOT is untouched - the band reorders "
      "the walk, it does not let a second job start",
      '_AI.get("busy") is None' in SRC
      and "one job per beat, as always" in TICK
      and "one job per tick" in TICK
      and "_game_rank" not in func_src("_afk_ai_tick"))
check("the finish queue is not ranked", "_game_rank" not in
      func_src("_queued_finish_badge"))
check("the stamps: APP_VERSION 3.36, ui.html x2, version.txt, installer",
      'APP_VERSION = "3.36"' in SRC
      and USRC.count("version:'3.36'") == 2
      and "(3, 36, 0, 0)" in io.open(
          os.path.join(ROOT, "version.txt"), encoding="utf-8").read()
      and "AppVersion=3.36" in io.open(
          os.path.join(ROOT, "installer.iss"), encoding="utf-8",
          errors="replace").read())
# a pin on a string is a proxy; ranktest.js RUNS the chip, so the
# roster has to carry both or half this drop is only asserted
ROSTER = io.open(os.path.join(ROOT, "qa", "run_all.bat"),
                 encoding="utf-8").read()
check("the roster runs both of this drop's suites",
      "rank335test" in ROSTER and 'node "ranktest.js"' in ROSTER)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
