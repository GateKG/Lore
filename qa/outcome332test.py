# -*- coding: utf-8 -*-
"""3.32 THE SCREEN DECIDED - outcomes read off the frames, and every hand
that touches them.

Drives the REAL functions lifted out of lore.py and ai/ocr_worker.py by
name: the pack line grammar (the typed head split before the
twelve-letter cut; outcome kinds never events), the dense windows and
the real RapidOCR over a synthetic clip drawn with ffmpeg (WINNER +
ORANGE + a podium tag, a kickoff clock, "5th Place / Rating 4782 -11"),
the candidates off a synthetic grid (the clock row, overtime, a rating
that moved, the cap), the fold (runs, frames, whose win from the podium
against the in-game name, 'win?' without one, the score, the placement),
the tally and the line, the owe gate (cached, never a spawn, never on a
black night, never without a pack) and the top-up (the sidecar's own
clock, hl untouched), the describer's OUTCOMES block and the planted
moment, the title's THE SCREEN DECIDED line (absent byte-for-byte on an
old night), the auditor's sixth layer (a witness, never standing; the
unshown/contradicted rows, never a strike; the tautology check), the
bridge payloads, and the UI read from its source. Scratch dirs live in
tempfile; nothing under D:\\Records is touched."""
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
WSRC = io.open(os.path.join(ROOT, "ai", "ocr_worker.py"),
               encoding="utf-8").read()
USRC = io.open(os.path.join(ROOT, "ui.html"), encoding="utf-8").read()
TREE = ast.parse(SRC)
try:
    HSRC = subprocess.run(["git", "show", "HEAD:lore.py"], cwd=ROOT,
                          capture_output=True, timeout=60).stdout \
        .decode("utf-8", "replace").replace("\r\n", "\n")
except Exception:
    HSRC = ""
FFMPEG = r"C:\Program Files\Lore\ffmpeg\bin\ffmpeg.exe"
VENV_PY = os.path.join(ROOT, "ai", "venv", "Scripts", "python.exe")

ok = bad = 0


def check(what, cond):
    global ok, bad
    if cond:
        ok += 1
        print("  OK  ", what)
    else:
        bad += 1
        print("  FAIL", what)


def extract(src, name, ns, tree=None):
    """A module-level function, lifted as written."""
    tree = tree or ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                src.splitlines()[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name)


def fsrc(src, name, tree=None):
    tree = tree or ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(src.splitlines()[node.lineno - 1:node.end_lineno])
    raise AssertionError(name)


def assign(src, name, ns, tree=None):
    """A module-level assignment, executed as written."""
    tree = tree or ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name
                for t in node.targets):
            code = "\n".join(src.splitlines()[node.lineno - 1:node.end_lineno])
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name)


def mmss(t):
    t = int(t)
    return "%d:%02d" % (t // 60, t % 60)


# =========================================================================
print("--- the worker: the pack line grammar ---")
sys.path.insert(0, os.path.join(ROOT, "ai"))
import ocr_worker as W  # noqa: E402  (the real module; RapidOCR loads in main only)

pl = W.pack_line
k, rx, oc = pl("outcome.placement: \\b(?P<n>[1-8])\\s?(?:st|nd|rd|th)\\s?Place\\b")
check("a typed head is split BEFORE the twelve-letter cut",
      k == "placement" and oc is True and rx.search("5th Place"))
check("...so outcome.clock is 'clock', never 'outcome.cloc'",
      pl("outcome.clock: (?P<m>\\d):(?P<s>\\d\\d)")[0] == "clock")
check("a plain line is a sense, twelve letters kept, not an outcome",
      pl("kill: \\bTRIPLE KILL\\b")[0] == "kill"
      and pl("kill: x")[2] is False
      and pl("boss_health_bar_reading: x")[0] == "boss_health_")
check("comments, blanks, headless lines and bad regexes are skipped",
      pl("# a comment") is None and pl("") is None and pl("no colon") is None
      and pl("win: (unclosed") is None and pl("outcome.: x") is None)
check("a regex with its own colons keeps them (the first colon is the head)",
      pl("outcome.clock: (?<![\\d:+])(?P<m>[0-5]):(?P<s>[0-5]\\d)")[1]
      .search("clock 0:31").group("s") == "31")

tmpw = tempfile.mkdtemp(prefix="lore_out332w_")
os.makedirs(os.path.join(tmpw, "packs"))
io.open(os.path.join(tmpw, "packs", "testgame.ocr.txt"), "w",
        encoding="utf-8").write(
    "# a pack\nbanner: \\bFLAWLESS\\b\noutcome.win: \\bYOU WON\\b\n"
    "outcome.placement: (?P<n>\\d)(st|nd|rd|th) Place\n")
_wf = W.__file__
W.__file__ = os.path.join(tmpw, "ocr_worker.py")
pats = W.load_pack("Test Game")
W.__file__ = _wf
kinds = [(k2, o2) for k2, _r, o2 in pats]
check("load_pack: the built-ins are senses, the pack's typed lines are outcomes",
      ("victory", False) in kinds and ("banner", False) in kinds
      and ("win", True) in kinds and ("placement", True) in kinds)
check("...and load_pack returns three-tuples throughout",
      all(len(p) == 3 for p in pats))
hits = W.outcome_hits(pats, "FLAWLESS YOU WON 3rd Place")
check("outcome_hits returns only the typed kinds, with named groups",
      [h["kind"] for h in hits] == ["win", "placement"]
      and hits[1]["groups"] == {"n": "3"} and hits[1]["text"] == "3rd Place")
check("...finditer: a podium prints every tag on one frame",
      len(W.outcome_hits(W.load_pack("Rocket League"),
                         "WINNER BLUE [ZZR] Nashmi [ZZR] Qais [KHM] Saif"
                         )) == 4)
check("mark() skips outcome kinds, so they never reach doc['events']",
      "        for kind, rx, outc in pats:\n            if outc:\n"
      "                continue" in WSRC)

print("\n--- the worker: the pattern fix ---")
vic = [r for k2, r, _o in pats if k2 == "victory"][0]
check("'S5 TOURNAMENT WINNER' is a player title, not a victory",
      not vic.search("S5 TOURNAMENT WINNER"))
check("'WINNER ORANGE' is still a victory", bool(vic.search("WINNER ORANGE")))
check("'# reef-tank' off an alt-tab is nothing (the old '#\\s*1' is gone)",
      not vic.search("# reef-tank") and not vic.search("#1 fan")
      and '|#\\s*1\\b"' not in WSRC
      and '(?<!TOURNAMENT )\\bWINNER\\b' in WSRC)

print("\n--- the worker: the dense windows ---")
check("'a-b[:step],...' parses, junk skipped, a step defaults to 2 s",
      W.parse_dense("652-712:2,1100-1160, x, 5-3, 7-9:0.1")
      == [(652.0, 712.0, 2.0), (1100.0, 1160.0, 2.0)])
check("the seconds are each once, in order, capped",
      W.dense_seconds([(0, 10, 2), (6, 14, 2)]) == [0, 2, 4, 6, 8, 10, 12, 14]
      and len(W.dense_seconds([(0, 1000, 2)], cap=300)) == 300
      and W.dense_seconds([], 300) == [])
check("the worker's main takes the dense spec and the cap",
      "def main(video, ffmpeg, dst, seconds, game=\"\", step=0.0, dur=0.0,\n"
      "         dense=None, cap=300)" in WSRC
      and "sys.argv[8] if len(sys.argv) > 8 else None" in WSRC
      and "int(sys.argv[9]) if len(sys.argv) > 9 else 300" in WSRC)
check("a dense frame is read through the centre crop, then wide on a hit",
      'got = read(t, _MID, "d")' in WSRC
      and 'got2 = read(t, "scale=1920:-2", "w")' in WSRC
      and WSRC.index('read(t, _MID, "d")') < WSRC.index('"scale=1920:-2", "w"'))
check("the dense rows land beside the hud, an empty list when asked",
      '    if dense:\n        # asked and answered' in WSRC
      and 'doc["dense"] = dense_rows' in WSRC)
check("the grid's strings and the dense strings share one filter",
      "strs = frame_strings(got)" in WSRC and "frame_strings(got, 40)" in WSRC
      and W.frame_strings([[0, "ab", 0.9], [0, "abc", 0.9], [0, "abcd", 0.3],
                           [0, "abc", 0.9]]) == ["abc"])

# =========================================================================
print("\n--- the worker on a synthetic clip (real RapidOCR) ---")
tmpv = tempfile.mkdtemp(prefix="lore_out332v_")
CLIP = os.path.join(tmpv, "synth.mp4")
FONT = "C\\:/Windows/Fonts/arialbd.ttf"


def dt(text, size, y, enable, color="white"):
    return ("drawtext=fontfile='%s':text='%s':fontsize=%d:fontcolor=%s:"
            "x=(w-tw)/2:y=%d:enable='%s'" % (FONT, text, size, color, y,
                                              enable))


vf = ",".join([
    dt("WINNER", 120, 150, "lt(t\\,10)"),
    dt("ORANGE", 110, 300, "lt(t\\,10)", "orange"),
    dt("[ZZR] NASHMI", 64, 470, "between(t\\,2\\,10)"),
    dt("5\\:00", 90, 60, "between(t\\,10\\,14)"),
    dt("5th Place", 110, 200, "between(t\\,14\\,24)"),
    dt("Rating 4782 -11", 80, 400, "between(t\\,14\\,24)")])
have_tools = os.path.isfile(FFMPEG) and os.path.isfile(VENV_PY)
check("the installed ffmpeg and the reader's venv are on this machine",
      have_tools)
BN = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
if have_tools:
    r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", "color=c=0x203040:s=1280x720:r=2:d=30", "-vf",
                        vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", CLIP],
                       capture_output=True, timeout=120, creationflags=BN)
    check("ffmpeg drew the clip", r.returncode == 0 and os.path.isfile(CLIP))


def run_worker(game, dense, step="0", out="w.json"):
    oj = os.path.join(tmpv, out)
    t0 = time.time()
    r = subprocess.run([VENV_PY, os.path.join(ROOT, "ai", "ocr_worker.py"),
                        CLIP, FFMPEG, oj, "", game, step, "30", dense, "300"],
                       capture_output=True, timeout=600, creationflags=BN)
    d = json.load(io.open(oj, encoding="utf-8")) if os.path.isfile(oj) else {}
    return r.returncode, d, time.time() - t0


if have_tools and os.path.isfile(CLIP):
    rc, d, secs = run_worker("Rocket League", "0-29:2", step="10")
    dense = d.get("dense") or []
    byt = {r[0]: r for r in dense}
    wins = [r for r in dense if any(h["kind"] == "win" for h in r[2])]
    check("the RL run returned dense rows (rc 0, %d frames in %.0f s)"
          % (len(dense), secs), rc == 0 and len(dense) >= 14)
    check("WINNER + ORANGE hit 'win' with team ORANGE on the banner frames "
          "(>= 3)", len(wins) >= 3 and all(
              any(h["kind"] == "win" and h["groups"].get("team") == "ORANGE"
                  for h in r[2]) for r in wins)
          and all(r[0] < 10 for r in wins))
    check("the podium tag was read with its club and name on some frame",
          any(h["kind"] == "podium" and h["groups"].get("club") == "ZZR"
              and h["groups"].get("name", "").upper().startswith("NASHM")
              for r in dense for h in r[2]))
    check("the kickoff clock hit 'clock' m=5 s=00 (a trigger, never an event)",
          any(h["kind"] == "clock" and h["groups"] == {"m": "5", "s": "00"}
              for r in dense for h in r[2])
          and not any(e["kind"] in ("clock", "win", "podium")
                      for e in d.get("events") or []))
    check("the grid rode the same run and the victory sense event stands",
          len((d.get("hud") or {}).get("rows") or []) >= 2
          and any(e["kind"] == "victory" for e in d.get("events") or []))
    check("frames past the banner carry no win hit",
          not any(h["kind"] == "win" for r in dense if r[0] >= 12
                  for h in r[2]))
    rc, d2, secs = run_worker("Hearthstone", "12-29:2", out="h.json")
    dense2 = d2.get("dense") or []
    pl_rows = [r for r in dense2 if any(h["kind"] == "placement"
                                        for h in r[2])]
    check("the Hearthstone run read '5th Place' as placement n=5 "
          "(%d frames in %.0f s)" % (len(pl_rows), secs),
          rc == 0 and len(pl_rows) >= 3
          and all(any(h["groups"].get("n") == "5" for h in r[2]
                      if h["kind"] == "placement") for r in pl_rows)
          and all(14 <= r[0] <= 24 for r in pl_rows))
    check("...and 'Rating 4782 -11' as rating r=4782 d=-11",
          any(h["kind"] == "rating" and h["groups"].get("r") == "4782"
              and h["groups"].get("d", "").replace(" ", "") == "-11"
              for r in dense2 for h in r[2]))
    check("no grid was asked for, none came back",
          "hud" not in d2 and d2.get("events") == [])
    SYNTH_DENSE_RL, SYNTH_DENSE_HS = dense, dense2
else:
    SYNTH_DENSE_RL = SYNTH_DENSE_HS = None

# =========================================================================
print("\n--- the candidates off the grid ---")
ns = {"os": os, "re": re, "json": json, "time": time,
      "subprocess": subprocess, "threading": __import__("threading"),
      "_here": lambda: ROOT}
for c in ("_OUT_STEP", "_OUT_CAP", "_OUT_FRAMES", "_OUT_OWE_CACHE",
          "_PACK_CACHE", "_OUT_VERDICT", "_OUT_RANK", "_HUD_STEP",
          "_HUD_OWE_CACHE", "_OUT_OLD_READER", "_OUT_OLD"):
    assign(SRC, c, ns, TREE)
for f in ("_pack_path", "_pack_outcomes", "_hype_cliffs",
          "_outcome_candidates", "_out_norm", "_ordinal", "_outcome_fold",
          "_outcome_line", "_outcome_tally", "_outcome_block",
          "_outcome_plant", "_outcome_owing", "_outcome_windows_arg",
          "_outcome_read", "_outcome_topup_one", "_hud_paths",
          "_hud_owing"):
    extract(SRC, f, ns, TREE)
_pack_outcomes = ns["_pack_outcomes"]
_outcome_candidates = ns["_outcome_candidates"]
check("the shipped packs resolve through the display name's key",
      [k2 for k2, _r in _pack_outcomes("Rocket League")]
      == ["win", "clock", "overtime", "score", "podium"]
      and [k2 for k2, _r in _pack_outcomes("Hearthstone")]
      == ["placement", "rating", "spectator", "lobby"]
      and _pack_outcomes("Elden Ring") == [])
check("...and the pack is cached on its clock",
      ns["_PACK_CACHE"].get(ns["_pack_path"]("Rocket League")) is not None)


def rl_rows():
    """49 rows a minute apart: a clock counting down over five matches."""
    rows = []
    clocks = {}
    for i in range(49):
        t = 5.0 + 60 * i
        strs = ["[ZZR] Nashmi", "BOOST 47"]
        # matches end after rows 11, 18, 25, 31 (a clock under a minute one
        # row before) and an overtime at row 40
        if i in (11, 18, 25, 31):
            strs.append({11: "0:03", 18: "0:31", 25: "0:25",
                         31: "0:37"}[i])
        elif i == 40:
            strs.append("+0:08")
        elif i in (20, 32):
            strs.append("S5TOURNAMENTWINNER")
            strs.append("3:12")
        else:
            # never "1:00" itself: the boundary is a real end (<= 60 s)
            strs.append("%d:%02d" % (2 + (i * 7) % 4, (i * 13) % 60))
        rows.append([t, strs])
    return rows


sns = {"hud": {"step": 60.0, "rows": rl_rows()}, "events": [], "hype": None}
wins = _outcome_candidates(sns, {"events": []}, None, "Rocket League", 2895)
whys = [w[2] for w in wins]
check("the clock rows under a minute open a window around each end",
      whys.count("clock") == 4
      and any(abs(a - (5 + 60 * 11 + 3 - 15)) < 0.2
              and abs(b - (5 + 60 * 11 + 3 + 45)) < 0.2
              for a, b, w in wins if w == "clock"))
check("the overtime row opens a two-minute window",
      any(w == "overtime" and abs(b - a - 120) < 0.2 for a, b, w in wins))
check("a clock over a minute opens nothing", len(wins) == 5)
check("the windows come back in time order, clipped to the night",
      wins == sorted(wins) and all(0 <= a < b <= 2895 for a, b, _w in wins))
sns["events"] = [{"t": 30.0 + 90 * i, "kind": "cheer", "p": 0.5}
                 for i in range(30)]
hl = {"events": [{"t": 1536.7, "kind": "laugh", "also": ["victory"]},
                 {"t": 2500.0, "kind": "game"}]}
wins2 = _outcome_candidates(sns, hl, None, "Rocket League", 2895)
check("the ears, the borrowed victory and the game burst are candidates "
      "too, the grid's own first, capped at twelve",
      len(wins2) == 12 and all(w in ("clock", "overtime")
                              for w in [x[2] for x in wins2
                                        if x[2] in ("clock", "overtime")])
      and sum(1 for w in wins2 if w[2] in ("clock", "overtime")) == 5
      and any(w[2] == "ears" for w in wins2))
check("overlapping windows merge and the stronger why wins the seat",
      all(wins2[i][1] < wins2[i + 1][0] for i in range(len(wins2) - 1)))
hype = {"hop": 3.0, "v": [0.1] * 20 + [0.9] * 8 + [0.05] * 20 + [0.3] * 10}
cl = ns["_hype_cliffs"](hype)
check("a loud stretch of 24 s that goes dead for 60 s is a cliff",
      cl == [(60.0, 84.0)])
check("...and it opens a 'quiet' window around the hush",
      any(w[2] == "quiet" and abs(w[0] - 64) < 0.2
          for w in _outcome_candidates({"hud": {"rows": []}, "hype": hype},
                                       {}, None, "Rocket League", 600)))
check("a game with no outcome pack has no candidates at all",
      _outcome_candidates(sns, hl, None, "Elden Ring", 2895) == [])
hs = {"hud": {"step": 60.0, "rows": [
    [5.0, ["Welcome to Battlegrounds Duos!", "Rating", "3083"]],
    [65.0, ["Tavern", "Rating 3083"]],
    [125.0, ["a fight"]],
    [185.0, ["@ Spectator Mode"]], [245.0, ["@ Spectator Mode"]],
    [305.0, ["a fight"]], [365.0, ["a fight"]],
    [425.0, ["Welcome to Battlegrounds Duos!", "Rating", "3071"]]]}}
hw = _outcome_candidates(hs, {}, None, "Hearthstone", 500)
check("Battlegrounds: one 'rating' window per rating change (the lobby's "
      "return folds into it), one 'spectator' window when spectating "
      "begins, the first lobby's own",
      sorted(w[2] for w in hw) == ["lobby", "rating", "spectator"])
check("...the rating window ends after the row that moved and reaches "
      "two minutes back", any(w[2] == "rating" and abs(w[1] - 435) < 0.2
                              and abs(w[0] - 305) < 0.2 for w in hw))
check("...and a still-spectating row opens no second window",
      sum(1 for w in hw if w[2] == "spectator") == 1)

# =========================================================================
print("\n--- the fold ---")
_outcome_fold = ns["_outcome_fold"]
_outcome_line = ns["_outcome_line"]
_outcome_tally = ns["_outcome_tally"]
RLP = _pack_outcomes("Rocket League")
HSP = _pack_outcomes("Hearthstone")


def hitsof(pats, text):
    out = []
    for k2, rx2 in pats:
        for m in rx2.finditer(text):
            out.append({"kind": k2, "text": m.group(0)[:40].strip(),
                        "groups": {a: b for a, b in m.groupdict().items()
                                   if b}})
    return out


def frame(t, *strs, pats=RLP):
    return [t, list(strs), hitsof(pats, " ".join(strs))]


dense = []
for t in range(672, 702, 2):
    if 676 <= t <= 680:
        dense.append(frame(t, "Microsoft Edge", "# reef-tank"))   # alt-tab
    elif t < 686:
        dense.append(frame(t, "WINNER", "ORANGE", "[ZZR] Nashmi",
                           "[ZZR] Qais"))
    else:
        dense.append(frame(t, "MY ACCOLADES", "WINNER", "ORANGE"))
dense.append(frame(706, "3 BLUE", "SCORE", "GOALS", "2 ORANGE"))
dense.append(frame(710, "5:00"))
for t in range(1118, 1134, 2):
    dense.append(frame(t, "WIN", "WINNER", "BLUE", "MVP", "[ZZR] Qais",
                       "[KHM] Saif"))
for t in range(2410, 2428, 2):
    dense.append(frame(t, "WINNER", "ORANGE"))
dense.append(frame(2600, "S5 TOURNAMENT WINNER", "ORANGE"))   # one frame
W_RL = [(657, 717, "clock"), (1100, 1160, "clock"), (2400, 2460, "ears")]
outs = _outcome_fold(dense, "Rocket League", 2.0, you=None, wins=W_RL)
check("three matches fold from the frames (the WINNER header through MY "
      "ACCOLADES is one run; the alt-tab gap does not split it)",
      len(outs) == 3 and [o["t"] for o in outs] == [672.0, 1118.0, 2410.0])
check("...with the frames they stood on: 12 / 8 / 9",
      [o["frames"] for o in outs] == [12, 8, 9])
check("...and the span ends a step past the last frame",
      outs[0]["b"] == 702.0 and outs[1]["b"] == 1134.0)
check("without an in-game name every side is 'win?' - the fact, not the "
      "verdict", all(o["side"] == "win?" for o in outs)
      and all(o["kind"] == "win" for o in outs))
check("the team colour and the screen's words ride along",
      outs[0]["team"] == "ORANGE" and outs[1]["team"] == "BLUE"
      and outs[0]["text"] == "WINNER ORANGE")
check("the score from the wide read within 30 s of the banner",
      outs[0].get("score") == {"b": 3, "o": 2} and "score" not in outs[1])
check("the why is the candidate window's own",
      [o["why"] for o in outs] == ["clock", "clock", "ears"])
check("a one-frame WINNER is a title on a replay, never a match",
      not any(o["t"] == 2600 for o in outs))
outs_y = _outcome_fold(dense, "Rocket League", 2.0, you="[ZZR] Nashmi",
                       wins=W_RL)
check("with his name: on the podium = WON, a podium without him = LOST, "
      "no podium read = 'win?'",
      [o["side"] for o in outs_y] == ["win", "loss", "win?"]
      and outs_y[0]["you"] == "[ZZR] Nashmi")
check("the club tag is optional in the name, and the match is letter-blind",
      [o["side"] for o in _outcome_fold(dense, "Rocket League", 2.0,
                                        you="nashmi", wins=W_RL)]
      == ["win", "loss", "win?"])
check("a wrong club flips nothing to a win",
      _outcome_fold(dense, "Rocket League", 2.0, you="[KHM] Nashmi",
                    wins=W_RL)[0]["side"] == "loss")
check("the line: WON as ORANGE with the score and the podium; LOST as BLUE; "
      "match ended - WINNER ORANGE",
      _outcome_line(outs_y[0]) == "WON as ORANGE 3-2 ([ZZR] Nashmi on the "
                                  "podium)"
      and _outcome_line(outs_y[1]) == "LOST as BLUE"
      and _outcome_line(outs_y[2]) == "match ended - WINNER ORANGE"
      and _outcome_line(outs_y[2], clock=True).startswith("40:10 "))
check("...and each outcome carries its line", outs_y[1]["line"] == "LOST as BLUE")
hsd = [frame(1323, "5thPlace", "Rating", "4782", "-11", pats=HSP),
       frame(1325, "5th Place", "Rating 4782 -11", pats=HSP),
       frame(1327, "5th Place", pats=HSP)]
hso = _outcome_fold(hsd, "Hearthstone", 2.0, you="", wins=[(1319, 1329,
                                                            "placement")])
check("Battlegrounds: one placement, 5th, three frames, the rating and "
      "its change, a bottom-half place is a loss",
      len(hso) == 1 and hso[0]["kind"] == "placement" and hso[0]["place"] == 5
      and hso[0]["frames"] == 3 and hso[0]["rating"] == 4782
      and hso[0]["delta"] == -11 and hso[0]["side"] == "loss")
check("...and its line", _outcome_line(hso[0]) == "finished 5th (rating 4782 -11)")
check("a single placement frame is enough (the screen is clicked away)",
      _outcome_fold([frame(50, "2nd Place", pats=HSP)], "Hearthstone", 2.0)
      [0]["place"] == 2
      and _outcome_fold([frame(50, "2nd Place", pats=HSP)], "Hearthstone",
                        2.0)[0]["side"] == "win")
check("junk rows fail open",
      _outcome_fold([None, [1], ["x", [], [{"kind": "win"}]], [5, [], "z"]],
                    "Rocket League") == [] and _outcome_fold(None, "x") == [])
if SYNTH_DENSE_RL:
    so = _outcome_fold(SYNTH_DENSE_RL, "Rocket League", 2.0,
                       you="[ZZR] Nashmi")
    check("the synthetic clip's real read folds to one WON as ORANGE",
          len(so) == 1 and so[0]["side"] == "win" and so[0]["team"] == "ORANGE"
          and so[0]["frames"] >= 3)
    sh = _outcome_fold(SYNTH_DENSE_HS, "Hearthstone", 2.0)
    check("...and one 5th place with rating 4782 -11",
          len(sh) == 1 and sh[0]["place"] == 5 and sh[0]["rating"] == 4782
          and sh[0]["delta"] == -11)
PROBE = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp", "claude",
                     "C--Users-gkg92-OneDrive-Desktop-Random-Files-Claude-"
                     "Sessions", "54d5c52b-8d2b-47a9-b0fa-1e4f4a8593a6",
                     "scratchpad", "spec332",
                     "rocketleague_20260904_233625.probe.json")
if os.path.isfile(PROBE):
    pr = json.load(io.open(PROBE, encoding="utf-8"))
    pd = [[r["t"], [s[0] for s in r["s"]],
           hitsof(RLP, " ".join(s[0] for s in r["s"]))] for r in pr["rows"]]
    po = _outcome_fold(pd, "Rocket League", 2.0, you=None)
    # WINNER + the colour on the SAME frame is the rule (a title on a
    # replay must never count), so the frames are fewer than the banner's
    # 15/8/9 WINNER-alone spans the probe measured: 7/4/5 on this night
    check("the measured RL night's probe rows fold to exactly 3 ends, "
          "4+ frames each, all 'win?' with no name set",
          len(po) == 3 and all(o["frames"] >= 4 for o in po)
          and all(o["side"] == "win?" for o in po)
          and [int(o["t"]) for o in po] == [672, 1118, 2410])

print("\n--- the tally ---")
tl = _outcome_tally(outs_y)
check("won 1 of 3 (1 unknown)",
      tl["line"] == "won 1 of 3 matches (1 unknown)" and tl["won"] == 1
      and tl["lost"] == 1 and tl["unknown"] == 1 and tl["matches"] == 3)
check("three wins of three: 'won 3 of 3 matches'",
      _outcome_tally([dict(o, side="win") for o in outs])["line"]
      == "won 3 of 3 matches")
check("no name: 'won?' - honest, never a guess",
      _outcome_tally(outs)["line"] == "won? - 3 matches ended, the winner "
                                     "unread"
      and "won?" in _outcome_tally(outs[:1])["line"])
check("places: 'finished 5th'; several: best named",
      _outcome_tally(hso)["line"] == "finished 5th"
      and _outcome_tally([{"kind": "placement", "place": 5, "side": "loss"},
                          {"kind": "placement", "place": 3, "side": "win"},
                          {"kind": "placement", "place": 1, "side": "win"}])
      == {"matches": 3, "won": 0, "lost": 0, "unknown": 0, "best_place": 1,
          "places": [5, 3, 1],
          "line": "finished 5th, 3rd and 1st - best 1st"})
check("nothing: '' (never a line for zero outcomes)",
      _outcome_tally([]) == {"matches": 0, "won": 0, "lost": 0, "unknown": 0,
                             "best_place": None, "places": [], "line": ""}
      and _outcome_tally(None)["line"] == "")
check("ordinals", [ns["_ordinal"](n) for n in (1, 2, 3, 4, 11, 12, 21)]
      == ["1st", "2nd", "3rd", "4th", "11th", "12th", "21st"])

# =========================================================================
print("\n--- the owe gate and the top-up ---")
tmp = tempfile.mkdtemp(prefix="lore_out332_")
LIB = os.path.join(tmp, "Records")
TH = os.path.join(LIB, ".lore_thumbs")
os.makedirs(os.path.join(LIB, "RocketLeague", "Videos"))
os.makedirs(TH)
V = os.path.join(LIB, "RocketLeague", "Videos", "RocketLeague_20260904_233625.mp4")
io.open(V, "wb").write(b"\0" * 200000)
os.utime(V, (1000000.0, 1000000.0))


def side(p, k2):
    return os.path.join(TH, os.path.splitext(os.path.basename(p))[0]
                        + "." + k2 + ".json")


def put(p, k2, doc, mt):
    io.open(side(p, k2), "w", encoding="utf-8").write(
        json.dumps(doc, ensure_ascii=False))
    os.utime(side(p, k2), (mt, mt))


runs, logs = [], []
FAKE_DENSE = [frame(t, "WINNER", "ORANGE", "[ZZR] Nashmi")
              for t in range(672, 700, 2)] + [frame(710, "5:00")]


def fake_run(cmd, timeout, flags):
    runs.append(list(cmd))
    io.open(cmd[4], "w", encoding="utf-8").write(json.dumps(
        {"v": 3, "events": [], "dense": FAKE_DENSE}))
    if ns.get("_meanwhile"):
        ns["_meanwhile"]()
    return 0, b"", b""


GAME = ["Rocket League"]
BLACK = [False]
ns.update({
    "SETTINGS": {"output_dir": LIB, "ffmpeg_path": "ffmpeg", "handle": ""},
    "_AI": {"abort": False, "job_secs": 0.0},
    "_senses_paths": lambda: ("python", "senses_worker.py"),
    "_ai_sidecar": side,
    "_probe_duration": lambda p: 2895.0,
    "_display_name": lambda x: GAME[0],
    "_parse_clip_name": lambda x: "RocketLeague",
    "_pic_black": lambda p: BLACK[0],
    "_work_dir": lambda: tmp,
    "_source_busy_add": lambda p: None, "_source_busy_done": lambda p: None,
    "_ai_run": fake_run,
    "_atomic_write_json": lambda p, d: io.open(
        p, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False)),
    "log": lambda m: logs.append(m),
})
_outcome_owing, _outcome_topup_one = ns["_outcome_owing"], ns["_outcome_topup_one"]
_hud_owing = ns["_hud_owing"]
GRID = {"step": 60.0, "rows": rl_rows()}
check("no senses yet: nothing owed", _outcome_owing(V) is False)
put(V, "sns", {"v": 1, "events": [], "names": {"1": "Faris"}}, mt=1000500.0)
check("a senses sidecar without the grid is the grid's debt, not this one's",
      _outcome_owing(V) is False and _hud_owing(V) is True)
put(V, "sns", {"v": 1, "events": [], "hud": GRID, "screen": []}, mt=1000500.0)
check("a grid without outcomes on a packed game owes the dense pass "
      "(and the grid no longer)", _outcome_owing(V) is True
      and _hud_owing(V) is False)
check("...and the owe gate spawned nothing and opened no video",
      runs == [])
put(V, "sns", {"v": 1, "events": [], "hud": GRID, "screen": [],
               "outcomes": []}, mt=1000500.0)
check("outcomes [] is 'looked, found nothing' - settled", _outcome_owing(V)
      is False)
put(V, "sns", {"v": 1, "events": [], "hud": GRID, "screen": []}, mt=1000500.0)
check("the cache follows the file's size, not just its clock",
      _outcome_owing(V) is True)
put(V, "sns", {"v": 1, "events": [], "hud": {"step": 60.0, "rows": [],
                                              "black": True},
               "screen": []}, mt=1000500.0)
check("a black hud is never owed", _outcome_owing(V) is False)
put(V, "sns", {"v": 1, "events": [], "hud": GRID, "screen": []}, mt=1000500.0)
BLACK[0] = True
ns["_OUT_OWE_CACHE"].clear()
check("pic.json says black: never owed (read only)", _outcome_owing(V) is False)
BLACK[0] = False
GAME[0] = "Elden Ring"
ns["_OUT_OWE_CACHE"].clear()
check("a game with no outcome pack is never owed", _outcome_owing(V) is False)
GAME[0] = "Rocket League"
ns["_OUT_OWE_CACHE"].clear()
put(V, "sns", {"v": 1, "failed": True, "tries": 1, "hud": GRID}, mt=1000500.0)
check("a failed senses sidecar is the senses' debt", _outcome_owing(V) is False)
put(V, "sns", {"v": 1, "events": [], "hud": GRID, "screen": [],
               "names": {"1": "Faris"}}, mt=1000500.0)
put(V, "hl", {"events": [{"t": 1536.7, "z": 40, "kind": "laugh"}]},
    mt=1000400.0)
check("owed again", _outcome_owing(V) is True)
st0 = os.stat(side(V, "sns"))
hl0 = os.stat(side(V, "hl"))
ns["SETTINGS"]["handle"] = "[ZZR] Nashmi"
got = _outcome_topup_one(V)
d = json.load(io.open(side(V, "sns"), encoding="utf-8"))
st1 = os.stat(side(V, "sns"))
hl1 = os.stat(side(V, "hl"))
check("the top-up ran the reader once: no targeted seconds, no grid, the "
      "dense windows and the cap",
      got is True and len(runs) == 1 and runs[0][5] == "" and runs[0][7] == "0"
      and runs[0][8] == "2895.0" and re.match(r"^\d+\.\d-\d+\.\d:2(,|$)",
                                              runs[0][9])
      and runs[0][10] == "300" and runs[0][9].count(",") == 4)
check("the outcomes landed on the sidecar with the tally",
      len(d.get("outcomes") or []) == 1 and d["outcomes"][0]["side"] == "win"
      and d["tally"]["line"] == "won 1 of 1 match")
check("the voices' names and the grid are untouched",
      d.get("names") == {"1": "Faris"} and d.get("hud") == GRID)
check("THE CLOCK STAYS: the sidecar wears the mtime it had",
      abs(st1.st_mtime - st0.st_mtime) < 0.01)
check("hl IS NEVER WRITTEN: same clock, same bytes (seam 1)",
      hl1.st_mtime == hl0.st_mtime and hl1.st_size == hl0.st_size
      and json.load(io.open(side(V, "hl"), encoding="utf-8"))["events"]
      == [{"t": 1536.7, "z": 40, "kind": "laugh"}])
check("nothing owed any more", _outcome_owing(V) is False
      and _hud_owing(V) is False)
check("the log says what the screen decided",
      any("The screen decided on" in m and "won 1 of 1" in m for m in logs))
check("a second visit is a no-op that reads nothing",
      _outcome_topup_one(V) is True and len(runs) == 1)
check("no scratch file left behind",
      not [f for f in os.listdir(tmp) if f.startswith("out_")])
check("the top-up never merges into hl (by its own source)",
      "_merge_sns_into_hl" not in fsrc(SRC, "_outcome_topup_one", TREE)
      and '_atomic_write_json(_ai_sidecar(video_path, "hl")'
      not in fsrc(SRC, "_outcome_topup_one", TREE))

# the race: a senses pass rewrites the sidecar while the ends are read
put(V, "sns", {"v": 1, "events": [], "hud": GRID, "screen": []}, mt=1000500.0)
ns["_OUT_OWE_CACHE"].clear()


def meanwhile():
    put(V, "sns", {"v": 1, "events": [{"t": 3}], "hud": GRID, "screen": [],
                   "outcomes": [], "tally": _outcome_tally([])}, mt=1000900.0)


ns["_meanwhile"] = meanwhile
got = _outcome_topup_one(V)
d = json.load(io.open(side(V, "sns"), encoding="utf-8"))
check("a sidecar rewritten meanwhile is left exactly as the new pass wrote "
      "it", got is True and d.get("events") == [{"t": 3}]
      and d.get("outcomes") == [])
ns["_meanwhile"] = None

# a reader that falls over is written down, not asked again every beat
put(V, "sns", {"v": 1, "events": [], "hud": GRID, "screen": []}, mt=1000500.0)
ns["_OUT_OWE_CACHE"].clear()
ns["_ai_run"] = lambda cmd, timeout, flags: (1, b"", b"OCR_WORKER_FAILED boom")
st0 = os.stat(side(V, "sns"))
got = _outcome_topup_one(V)
d = json.load(io.open(side(V, "sns"), encoding="utf-8"))
check("a failed read is written as no outcomes with its why, clock kept",
      got is True and d.get("outcomes") == [] and "boom" in d.get(
          "outcomes_failed", "") and d["tally"]["line"] == ""
      and abs(os.stat(side(V, "sns")).st_mtime - st0.st_mtime) < 0.01)
check("...so it is not owed again", _outcome_owing(V) is False)

# INSTALL DRIFT: a reader on disk that predates 3.32 takes argv[8] in
# silence and answers v 2 with no 'dense' key - that night is left
# OWED (no outcomes key, no outcomes_failed), the notice is said once
# per process, and the same old file is not spawned again
put(V, "sns", {"v": 1, "events": [], "hud": GRID, "screen": []}, mt=1000500.0)
ns["_OUT_OWE_CACHE"].clear()
ns["_OUT_OLD"]["mt"] = None
ns["_OUT_OLD"]["said"] = False
runs.clear()
logs.clear()


def old_run(cmd, timeout, flags):
    runs.append(list(cmd))
    io.open(cmd[4], "w", encoding="utf-8").write(json.dumps(
        {"v": 2, "events": [], "hud": {"step": 60.0, "rows": []}}))
    return 0, b"", b""


ns["_ai_run"] = old_run
raw0 = io.open(side(V, "sns"), "rb").read()
got = _outcome_topup_one(V)
d = json.load(io.open(side(V, "sns"), encoding="utf-8"))
check("a reader that predates 3.32 (v 2, no dense) writes NO outcomes key: "
      "the sidecar is byte-identical and the night stays owed",
      got is True and "outcomes" not in d and "outcomes_failed" not in d
      and io.open(side(V, "sns"), "rb").read() == raw0
      and _outcome_owing(V) is True and len(runs) == 1)
check("...and the notice is logged once, in those words",
      [m for m in logs if "predates 3.32" in m]
      == ["The screen's reader on disk predates 3.32 - outcomes wait for "
          "the drop to land."])
got = _outcome_topup_one(V)
check("...a second visit spawns nothing and says nothing more (the old "
      "file's clock is remembered)", got is True and len(runs) == 1
      and sum("predates 3.32" in m for m in logs) == 1
      and ns["_OUT_OLD"]["mt"] == os.stat(ns["_hud_paths"]()).st_mtime)
# the three roads of _outcome_read itself, on the same window
_rw = [(660.0, 700.0, "clock")]
_ro = os.path.join(tmp, "out_roads.json")
ns["_OUT_OLD"]["mt"] = None
ns["_OUT_OLD"]["said"] = False
logs.clear()
ns["_ai_run"] = fake_run
r3 = ns["_outcome_read"](V, "Rocket League", _rw, 2895.0, "python",
                         ns["_hud_paths"](), _ro, 0)
ns["_ai_run"] = lambda cmd, timeout, flags: (1, b"", b"OCR_WORKER_FAILED boom")
rf = ns["_outcome_read"](V, "Rocket League", _rw, 2895.0, "python",
                         ns["_hud_paths"](), _ro, 0)
ns["_ai_run"] = old_run
r2 = ns["_outcome_read"](V, "Rocket League", _rw, 2895.0, "python",
                         ns["_hud_paths"](), _ro, 0)
check("_outcome_read: v 3 with dense = the rows; rc != 0 = (None, the "
      "stderr); v 2 without dense = (None, the old-reader word)",
      r3 == (FAKE_DENSE, "") and rf == (None, "OCR_WORKER_FAILED boom")
      and r2 == (None, ns["_OUT_OLD_READER"])
      and ns["_OUT_OLD_READER"] == "the screen's reader on disk predates 3.32"
      and sum("predates 3.32" in m for m in logs) == 1)
try:
    os.remove(_ro)
except OSError:
    pass
ns["_OUT_OLD"]["mt"] = None
ns["_OUT_OLD"]["said"] = False

# no candidates: written as looked-and-found-nothing without a run
ns["_ai_run"] = fake_run
runs.clear()
put(V, "sns", {"v": 1, "events": [], "hud": {"step": 60.0, "rows": [
    [5.0 + 60 * i, ["4:22"]] for i in range(20)]}, "screen": []},
    mt=1000500.0)
ns["_OUT_OWE_CACHE"].clear()
got = _outcome_topup_one(V)
d = json.load(io.open(side(V, "sns"), encoding="utf-8"))
check("a night with no predicted end writes outcomes [] and runs nothing",
      got is True and runs == [] and d.get("outcomes") == []
      and any("decided nothing" in m for m in logs))
check("the black night inside the senses pass writes [] beside its black "
      "hud", 'sns["hud"] = {"step": _HUD_STEP, "rows": [], "black": True}\n'
      '                sns["screen"] = []\n'
      '                # ...and nothing to decide off it - written, so the\n'
      '                # outcome top-up never owes a black night either\n'
      '                sns["outcomes"] = []\n' in SRC)
_s1 = fsrc(SRC, "_senses_one", TREE)
check("the dense pass rides the senses pass under the same black gate, "
      "after the grid, on packed games only, never into hl",
      "_outcome_read(" in _s1 and "_outcome_fold(" in _s1
      and _s1.index("if _pic_black(video_path):") < _s1.index("_outcome_read(")
      and 'and _pack_outcomes(game):' in _s1
      and _s1.index('sns["screen"] = _hud_names(_hg)') < _s1.index(
          "_outcome_read(") < _s1.index("_merge_sns_into_hl(video_path, sns)")
      and '"kind": "outcome"' not in fsrc(SRC, "_merge_sns_into_hl", TREE))
check("...and the senses pass, too, leaves an old reader's night owed: no "
      "outcomes key, no outcomes_failed, the tally unwritten",
      "old = why2 == _OUT_OLD_READER" in _s1
      and "                                if not old:\n"
          "                                    sns[\"outcomes_failed\"] = why2\n"
      in _s1
      and "                        if not old:\n"
          "                            sns[\"outcomes\"] = outs\n"
          "                            sns[\"tally\"] = _outcome_tally(outs)\n"
      in _s1
      and _s1.index("_outcome_read(") < _s1.index("old = why2 == _OUT_OLD_READER")
      < _s1.index('sns["outcomes"] = outs'))

# =========================================================================
print("\n--- the describer: the block and the planted moment ---")
_outcome_block, _outcome_plant = ns["_outcome_block"], ns["_outcome_plant"]
blk = _outcome_block(outs_y, 600, 1800)
check("a window spanning the ends gets the OUTCOMES block, verdicts with "
      "their clocks",
      blk.startswith("OUTCOMES the screen showed in these minutes")
      and "11:12 WON as ORANGE 3-2" in blk and "18:38 LOST as BLUE" in blk
      and "40:10" not in blk)
check("...and the one rule sentence",
      "A stretch that spans one of these is named by it" in blk
      and blk.endswith("\n"))
check("a window with no outcome has no block", _outcome_block(outs_y, 0, 600)
      == "" and _outcome_block([], 0, 9999) == "")
wm = [{"t": 1000.0, "why": "a laugh", "kind": "laugh"}]
n = _outcome_plant(wm, outs_y, 600, 1800)
check("the outcomes inside the window are planted as code-only moments, "
      "kind 'outcome', line -1",
      n == 2 and [m for m in wm if m["kind"] == "outcome"]
      == [{"t": 672.0, "why": "WON as ORANGE 3-2 ([ZZR] Nashmi on the podium)",
           "kind": "outcome", "line": -1},
          {"t": 1118.0, "why": "LOST as BLUE", "kind": "outcome", "line": -1}])
check("planting twice plants nothing more (the 8 s rule)",
      _outcome_plant(wm, outs_y, 600, 1800) == 0 and len(wm) == 3)
wm2 = [{"t": 675.0, "why": "they scream", "kind": "scream"}]
check("a moment already within 8 s keeps its seat; no plant beside it",
      _outcome_plant(wm2, outs_y, 600, 700) == 0)
_ins = fsrc(SRC, "_insights_one", TREE)
check("_insights_one reads the outcomes off the senses sidecar",
      '_outs = [o for o in (_sd0.get("outcomes") or [])' in _ins
      and "_outs = []" in _ins)
check("the head's order: frames -> ears -> voices -> SCREEN names -> "
      "OUTCOMES -> eyes",
      _ins.index("The SCREEN itself printed these names")
      < _ins.index("ears += _outcome_block(_outs, lo, hi)")
      < _ins.index("saw_here = [(t0, s0) for t0, s0 in _seen"))
check("the plant happens after the window is told, before it is written",
      _ins.index("_outcome_plant(wmoments, _outs, lo, hi)")
      < _ins.index('windows[str(int(lo))] = {"segments": mapped,'))
check("the schema's moment kinds are untouched (outcome is code-only)",
      '"outcome"' not in "\n".join(SRC.splitlines()[
          [n2 for n2 in TREE.body if isinstance(n2, ast.Assign)
           and any(isinstance(t2, ast.Name) and t2.id == "_DESC_SCHEMA"
                   for t2 in n2.targets)][0].lineno - 1:
          [n2 for n2 in TREE.body if isinstance(n2, ast.Assign)
           and any(isinstance(t2, ast.Name) and t2.id == "_DESC_SCHEMA"
                   for t2 in n2.targets)][0].end_lineno]))

# =========================================================================
print("\n--- the title: THE SCREEN DECIDED ---")
tns = {"re": re}
assign(SRC, "_TITLE_WRITE", tns, TREE)
assign(SRC, "_TITLE_TALLY_RULE", tns, TREE)
tns["_outcome_line"] = _outcome_line
tns["_ordinal"] = ns["_ordinal"]
_title_evidence = extract(SRC, "_title_evidence", tns, TREE)
EV = {"game": "Rocket League", "dur": 2895, "lines": 400, "names": ["Faris"],
      "ranked": [{"a": 0, "b": 600, "n": "The warm-up", "w": "a slow start",
                  "q": "let's go", "gk": {"laugh": 2}}],
      "moments": [{"t": 12, "kind": "laugh", "why": "a joke"}],
      "kinds": {"laugh": 3}, "ocr": [(1534.7, "victory", "WINNER")],
      "screen": [{"n": "BOOST", "a": 5, "b": 65}], "places": [], "creatures": []}
body = _title_evidence(dict(EV, tally=_outcome_tally(outs_y), outcomes=outs_y))
check("the tally is printed as THE SCREEN DECIDED, with each end's clock, "
      "before THE SCREEN printed",
      "THE SCREEN DECIDED: won 1 of 3 matches (1 unknown) (11:12 WON as "
      "ORANGE 3-2 ([ZZR] Nashmi on the podium); 18:38 LOST as BLUE; "
      "40:10 match ended - WINNER ORANGE).\n" in body
      and body.index("THE SCREEN DECIDED") < body.index("THE SCREEN printed"))
check("...and the one rule line rides right under it, once, and nowhere "
      "in the ask", body.count(tns["_TITLE_TALLY_RULE"]) == 1
      and body.index("THE SCREEN DECIDED") < body.index(
          tns["_TITLE_TALLY_RULE"]) < body.index("THE SCREEN printed")
      and "the title may say so in those words" in tns["_TITLE_TALLY_RULE"]
      and "carries the tally" in tns["_TITLE_TALLY_RULE"]
      and "tally" not in tns["_TITLE_WRITE"]
      and "screen decided" not in tns["_TITLE_WRITE"].lower())
check("'won 3 of 5 matches' reaches the ask verbatim",
      "THE SCREEN DECIDED: won 3 of 5 matches" in _title_evidence(
          dict(EV, tally={"line": "won 3 of 5 matches"})))
if HSRC:
    hns = {"re": re}
    assign(HSRC, "_TITLE_WRITE", hns)
    h_title_evidence = extract(HSRC, "_title_evidence", hns)
    # five nights the screen decided nothing on: no key, None, an
    # empty line, an empty dict, and the barest evidence there is
    _fx = [EV, dict(EV, tally=None), dict(EV, tally={"line": ""}),
           dict(EV, tally={}, outcomes=[]), {"game": "X"}]
    check("OLD-NIGHT PARITY: the ask on a night with no tally is HEAD's, "
          "byte for byte, on five no-tally fixtures",
          all(_title_evidence(f) == h_title_evidence(f) for f in _fx)
          and not any("THE SCREEN DECIDED" in _title_evidence(f)
                      for f in _fx))
    check("...and _TITLE_WRITE itself is HEAD's text",
          tns["_TITLE_WRITE"] == hns["_TITLE_WRITE"])
check("the title ask carries the tally and the outcomes",
      '"tally": _sd0.get("tally"),' in _ins and '"outcomes": _outs,' in _ins)

# =========================================================================
print("\n--- the auditor: the sixth layer ---")
ans = {"re": re, "os": os, "json": json}
for c in ("_AUD_V", "_AUD_WORDS", "_AUD_SOUND", "_AUD_EYE", "_AUD_REVIEW",
          "_AUD_CHAPTER", "_AUD_LAUGH", "_AUD_SCREEN", "_AUD_OUT_WIN",
          "_AUD_LIVE", "_AUD_LAYERS", "_AUD_SAY", "_AUD_SILENT",
          "_AUD_OUT_WORDS"):
    assign(SRC, c, ans, TREE)
ans["_aud_voice"] = lambda sns, a, b: ""
ans["_outcome_line"] = _outcome_line
ans["_ordinal"] = ns["_ordinal"]
for f in ("_aud_says", "_aud_live", "_aud_silence", "_aud_out_match",
          "_aud_out_seat", "_aud_out_opposite", "_aud_outcomes",
          "_aud_public"):
    extract(SRC, f, ans, TREE)
check("_AUD_V stays 7 - no shelf-wide re-audit for a witness",
      ans["_AUD_V"] == 7 and "_AUD_V = 7" in SRC)
check("the vocabulary is six, the screen between the eye and the review, "
      "with its say and its silence",
      ans["_AUD_LAYERS"] == ("words", "sound", "eye", "screen", "review",
                             "laugh")
      and ans["_AUD_SAY"]["screen"] == "the screen: "
      and ans["_AUD_SILENT"]["screen"] == "nothing the screen printed")
SNS_A = {"events": [{"t": 1536.7, "kind": "laugh"}],
         "ocr": [{"t": 1534.7, "kind": "victory", "text": "WINNER"}],
         "outcomes": outs_y}
src_a = {"stt": [], "sns": SNS_A, "vis": {}, "ins": {}, "laughs": []}
lay, det = ans["_aud_says"](1118.0, src_a)
check("an outcome within 20 s is the screen's witness: 'WON/LOST as BLUE'",
      "screen" in lay and det["screen"] == "LOST as BLUE")
lay2, det2 = ans["_aud_says"](271.6, src_a)
check("a second with no end near it has no screen witness",
      "screen" not in lay2 and "screen" not in det2)
lay3, det3 = ans["_aud_says"](1535.0, src_a)
check("the banner read (sns.ocr) rides the screen slot now, not the sound's",
      "screen" in lay3 and det3["screen"] == "on screen: WINNER"
      and det3.get("sound") == "laugh" and lay3 == ["sound", "screen"])
check("the answer keeps the fixed order",
      ans["_aud_says"](1118.0, dict(src_a, laughs=[(1119.0, "laugh")]))[0]
      == ["screen", "laugh"])
live = ans["_aud_live"]({"words": 50, "screen": 90, "eye": 40}, 100)
check("the screen never earns standing - a positive counts, silence never "
      "condemns", "screen" not in live and live == {"words", "eye"})
check("...so its silence is never named against a claim",
      "screen" not in ans["_aud_silence"](live, "")
      and ans["_aud_silence"](live, "") == "no line spoken within four "
                                             "seconds and nothing the eye saw")
if HSRC:
    hns2 = {"re": re, "os": os, "json": json}
    for c in ("_AUD_WORDS", "_AUD_SOUND", "_AUD_EYE", "_AUD_REVIEW",
              "_AUD_CHAPTER", "_AUD_LAUGH", "_AUD_LAYERS"):
        assign(HSRC, c, hns2)
    hns2["_aud_voice"] = lambda sns, a, b: ""
    h_says = extract(HSRC, "_aud_says", hns2)
    old_src = {"stt": [{"a": 1117000, "b": 1119500, "t": "what a save"}],
               "sns": {"events": [{"t": 1120.0, "kind": "cheer"}]},
               "vis": {"looks": [{"t": 1121, "place": "the pitch"}]},
               "ins": {"moments": [{"t": 1118.2, "why": "a save"}],
                       "chapters": [{"t": 1110, "label": "The save"}]},
               "laughs": [(1119.0, "laugh")]}
    check("OLD-NIGHT PARITY: a night with no outcomes and no banner read "
          "answers exactly as HEAD's auditor did",
          ans["_aud_says"](1118.0, old_src) == h_says(1118.0, old_src)
          and ans["_aud_says"](50.0, old_src) == h_says(50.0, old_src))

print("\n--- the auditor: what the story claims ---")
_aud_outcomes = ans["_aud_outcomes"]
INS = {"title": "Three wins and a phone call",
       "summary": "Rocket League, a slow start, then the wins came.",
       "chapters": [
           {"t": 271.6, "label": "Boosts and Teammates",
            "what": "a scramble that ends culminating in a win"},
           {"t": 420.0, "label": "The lull", "what": "nobody says much"},
           {"t": 1000.0, "label": "Losing streak",
            "what": "they discuss losing"},
           {"t": 1300.0, "label": "The comeback",
            "what": "they won it at the death"},
           {"t": 2360.0, "label": "Overtime", "what": "they celebrate overtime"}],
       "moments": [{"t": 2000.0, "why": "we lost that game", "kind": "laugh"},
                   {"t": 672.0, "why": "WON as ORANGE", "kind": "outcome"},
                   {"t": 1125.0, "why": "\"we won\" - a cheer", "kind": ""},
                   {"t": 2500.0, "why": "he lost the ball again", "kind": ""},
                   {"t": 2600.0, "why": "they got lost in the menus",
                    "kind": ""}]}
rows, warn = _aud_outcomes(INS, {"outcomes": outs}, 2895.0)
byw = {(r["where"], r["t"]): r for r in rows}
check("a chapter naming a win WITH an end within 180 s is NOT flagged",
      byw[("chapter", 1300.0)]["verdict"] == "shown")
check("a chapter naming a win with NO end within 180 s IS flagged 'unshown', "
      "the nearest named",
      byw[("chapter", 271.6)]["verdict"] == "unshown"
      and byw[("chapter", 271.6)]["nearest"] == "11:12"
      and any("\"Boosts and Teammates\" says \"win\"" in w
              and "did not show that" in w and "11:12" in w for w in warn))
check("the title and the summary look at the whole night: shown",
      byw[("title", 0.0)]["verdict"] == "shown"
      and byw[("summary", 0.0)]["verdict"] == "shown")
check("'won?' cannot dispute a loss: the losing chapter is shown",
      byw[("chapter", 1000.0)]["verdict"] == "shown")
check("a chapter with no outcome word is not a claim",
      ("chapter", 420.0) not in byw and ("chapter", 2360.0) not in byw)
check("a moment claiming a loss with nothing near it is unshown; the "
      "planted outcome moment claims nothing",
      byw[("moment", 1992.0)]["verdict"] == "unshown"
      and byw[("moment", 1992.0)]["claim"] == "lost that game"
      and ("moment", 664.0) not in byw
      and byw[("moment", 1117.0)]["verdict"] == "shown")
_lrx = [r2 for k2, r2 in ans["_AUD_OUT_WORDS"] if k2 == "loss"][0]
check("'lost the ball' and 'got lost' claim no loss (bare 'lost' is gone)",
      ("moment", 2492.0) not in byw and ("moment", 2592.0) not in byw
      and not _lrx.search("he lost the ball again")
      and not _lrx.search("we got lost on the way")
      and not _lrx.search("lost"))
check("'we lost that game', 'lost the match', 'we lost.' and 'we lost' "
      "at the end claim one; 'we lost the ball' does not",
      _lrx.search("we lost that game") and _lrx.search("they lost the match")
      and _lrx.search("and then we lost.") and _lrx.search("honestly we lost")
      and _lrx.search("we lost, again") and not _lrx.search("we lost the ball")
      and _lrx.search("a losing streak") and _lrx.search("the defeat"))
check("NEVER A STRIKE: rows carry verdicts only, no drop, no rewrite",
      all(set(r) == {"where", "t", "claim", "kind", "verdict", "nearest"}
          for r in rows) and not any("drop" in w.lower() for w in warn))
INS2 = {"chapters": [{"t": 1000.0, "label": "The comeback",
                      "what": "they won it at the death"},
                     {"t": 1300.0, "label": "The lull", "what": "quiet"}]}
rows_y, warn_y = _aud_outcomes(INS2, {"outcomes": outs_y}, 2895.0)
byy = {(r["where"], r["t"]): r for r in rows_y}
check("TAUTOLOGY CHECK: nearness is not agreement - a chapter saying "
      "'won' over a LOST end (the podium named him on the other side) is "
      "contradicted, kind against kind",
      byy[("chapter", 1000.0)]["verdict"] == "contradicted"
      and any("\"The comeback\" says \"won\" and the screen showed the "
              "opposite - 18:38 LOST as BLUE" in w for w in warn_y))
check("...and the same claim over a 'win?' end is shown - an unread "
      "winner never accuses",
      _aud_outcomes(INS2, {"outcomes": outs}, 2895.0)[0][0]["verdict"]
      == "shown")
check("...while the same second IS a screen witness for a MARK (the "
      "witness demands more than the fold guaranteed: a kind, a place)",
      "screen" in ans["_aud_says"](1118.0, {"sns": {"outcomes": outs_y}})[0]
      and ans["_aud_out_match"]("placement", 3, {"kind": "placement",
                                                 "place": 5}) is False
      and ans["_aud_out_match"]("placement", 5, {"kind": "placement",
                                                 "place": 5}) is True
      and ans["_aud_out_match"]("placement", None, {"kind": "placement",
                                                    "place": 5}) is False
      and ans["_aud_out_opposite"]("win", None, {"side": "loss"}) is True
      and ans["_aud_out_opposite"]("win", None, {"side": "win?"}) is False)
check("a night never asked (no 'outcomes' key) answers ([], []) - silence, "
      "never an accusation",
      _aud_outcomes(INS, {}, 2895.0) == ([], [])
      and _aud_outcomes(INS, None, 0) == ([], []))
r0, w0 = _aud_outcomes(INS, {"outcomes": []}, 2895.0)
check("looked and found nothing: a claim is unshown with 'no match ended "
      "near it'", any(r["verdict"] == "unshown" for r in r0)
      and all("no match ended near it" in w for w in w0))
ra, wa = _aud_outcomes({"chapters": [{"t": 100, "label": "\u0627\u0644\u0646\u0647\u0627\u064a\u0629",
                                       "what": "\u0641\u0632\u0646\u0627 \u0627\u0644\u0644\u064a\u0644\u0629"}]},
                       {"outcomes": []}, 900)
check("the Arabic list is small and warns only (the 3.25 law)",
      len(ra) == 1 and ra[0]["kind"] == "win" and ra[0]["verdict"] == "unshown"
      and len(wa) == 1
      and len(ans["_AUD_OUT_WORDS"]) == 6)
check("a placement claim naming no seat is shown by NO placement (and "
      "contradicted by none): the Arabic word warns, never accuses",
      ans["_aud_out_match"]("placement", None, {"kind": "placement",
                                                 "place": 1}) is False
      and ans["_aud_out_opposite"]("placement", None, {"kind": "placement",
                                                        "place": 1}) is False
      and _aud_outcomes({"chapters": [{"t": 1300, "label": "x",
                                       "what": "\u0627\u0644\u0645\u0631\u0643\u0632 "
                                               "\u0627\u0644\u062e\u0627\u0645\u0633"}]},
                        {"outcomes": hso}, 1400)[0][0]["verdict"] == "unshown")
check("'first place' is seat 1: shown by a 1st, contradicted by the 5th",
      _aud_outcomes({"chapters": [{"t": 1300, "label": "x",
                                   "what": "first place at last"}]},
                    {"outcomes": [dict(hso[0], place=1)]}, 1400)[0][0]["verdict"]
      == "shown"
      and _aud_outcomes({"chapters": [{"t": 1300, "label": "x",
                                       "what": "first place at last"}]},
                        {"outcomes": hso}, 1400)[0][0]["verdict"]
      == "contradicted")
check("'top 4' / 'top four' is a range: a 3rd shows it, a 4th shows it, "
      "the 5th contradicts it",
      _aud_outcomes({"chapters": [{"t": 1300, "label": "x",
                                   "what": "top 4 finish"}]},
                    {"outcomes": [dict(hso[0], place=3)]}, 1400)[0][0]["verdict"]
      == "shown"
      and _aud_outcomes({"chapters": [{"t": 1300, "label": "x",
                                       "what": "a top four finish"}]},
                        {"outcomes": [dict(hso[0], place=4)]}, 1400)[0][0]
      ["verdict"] == "shown"
      and _aud_outcomes({"chapters": [{"t": 1300, "label": "x",
                                       "what": "top 4 finish"}]},
                        {"outcomes": hso}, 1400)[0][0]["verdict"]
      == "contradicted"
      and ans["_aud_out_match"]("placement", ("top", 4),
                                {"kind": "placement", "place": None}) is False
      and ans["_aud_out_match"]("placement", 3, {"side": "win"}) is False)
check("placements: 'finished 5th' shown by a 5th place, '3rd place' "
      "contradicted by it",
      _aud_outcomes({"chapters": [{"t": 1300, "label": "x",
                                   "what": "finished 5th"}]},
                    {"outcomes": hso}, 1400)[0][0]["verdict"] == "shown"
      and _aud_outcomes({"chapters": [{"t": 1300, "label": "x",
                                       "what": "3rd place at last"}]},
                        {"outcomes": hso}, 1400)[0][0]["verdict"]
      == "contradicted")
_a1 = fsrc(SRC, "_audit_one", TREE)
check("_audit_one runs the check beside the names, warns, writes the rows "
      "and the count", "outrows, owarn = _aud_outcomes(ins, sns, dur)" in _a1
      and "warn.extend(owarn[:4])" in _a1 and '"outcomes": outrows,' in _a1
      and '"unshown": len([r for r in outrows' in _a1
      and _a1.index("_aud_names(video_path, ins, stt, _low)")
      < _a1.index("_aud_outcomes(ins, sns, dur)"))
pub = ans["_aud_public"]({
    "v": 7, "complete": True,
    "thread": [{"t": 1118.0, "what": "x", "agrees": ["words", "screen"],
                "say": {"words": "\"nice\"", "screen": "LOST as BLUE"}}],
    "outcomes": rows_y})
check("the bridge forwards only the rows that question a claim, and keeps "
      "'screen' in agrees and say",
      [r["verdict"] for r in pub["outcomes"]] and all(
          r["verdict"] != "shown" for r in pub["outcomes"])
      and len(pub["outcomes"]) == len([r for r in rows_y
                                       if r["verdict"] != "shown"])
      and pub["thread"][0]["agrees"] == ["words", "screen"]
      and pub["thread"][0]["say"]["screen"] == "LOST as BLUE")
check("the dossier tells the thinker what the screen said within 45 s",
      '"the screen said: " + _outcome_line(o)[:60]' in fsrc(SRC, "_aud_dossier",
                                                             TREE))

# =========================================================================
print("\n--- the bridge, the settings, the hygiene ---")
check("api.senses carries the outcomes and the tally",
      '"outcomes": [o for o in (d.get("outcomes") or [])' in SRC
      and '"tally": d.get("tally") or None}' in SRC)
check("api.visions attaches the outcomes on every shape",
      '"black": True, "outcomes": []}' in SRC
      and '"black": False, "outcomes": outcomes}' in SRC
      and '"outcomes": outcomes,\n                "eye": True, "screen": screen, "black": black}' in SRC
      and 'if screen or outcomes:' in SRC)
check("SETTINGS: 'handle', default '', coerced to a short string",
      '    "handle":            "",\n' in SRC
      and 'd["handle"] = str(d.get("handle", DEFAULTS["handle"]) or "")[:40].strip()' in SRC)
check("the fold reads the handle from SETTINGS on both paths",
      SRC.count('you=SETTINGS.get("handle") or ""') == 2)
check("the tail: one key, grid OR outcomes, the screen visit",
      'if (_hud_owing(p) or _outcome_owing(p)) \\\n'
      '                    and _ai_sidecar_fresh(p, "hl"):\n'
      '                _AI["tail"] = ("screen", p)' in SRC
      and 'screen_only = (tail == "screen")' in SRC
      and '"index": "the librarian"}.get(tail, tail)' in SRC
      and "hud_only" not in SRC)
check("the sidecar-forget tuples take pic, src and emb with the file "
      "(delete, trim, edit)",
      SRC.count('"vis", "aud", "pic", "src", "emb"):') == 1
      and SRC.count('"aud", "pic", "src", "emb"):') == 2
      and SRC.count('"vis", "aud", "pic",\n                                     "src", "emb"):') == 1
      and SRC.count('"pic", "src"):') == 0)
check("pic/emb/outcomes stay outside the attic",
      '_ATTIC_OF = {"listening": ("hl", "lvl"),\n             "hearing": ("stt",),\n'
      '             "thinking": ("ins", "sns", "vis"),' in SRC
      and '"pic"' not in SRC.split("_ATTIC_OF = {")[1].split("}")[0])
check("the blind black latency is quoted as 20-25 s",
      SRC.count("20-25 s") >= 2)
check("the OUTCOMES block, the plant, the tally and the witness are all "
      "one wording", SRC.count("def _outcome_line(") == 1
      and "_outcome_line(o, clock=True)" in fsrc(SRC, "_outcome_block", TREE)
      and "_outcome_line(o)[:140]" in fsrc(SRC, "_outcome_plant", TREE)
      and "_outcome_line(o)[:90]" in fsrc(SRC, "_aud_says", TREE))

# =========================================================================
print("\n--- the UI, read from its source ---")
rhm = USRC[USRC.index("async function renderHlMarks"):]
rhm = rhm[:rhm.index("const clusterPass=")]
check("the bar folds _sns.outcomes FIRST, before the review's moments, "
      "z 1e6, kind 'outcome', the text on the tick",
      "((_sns&&_sns.outcomes)||[]).forEach(o=>{" in rhm
      and rhm.index("_sns.outcomes") < rhm.index("((_ins&&_ins.moments)||[])")
      and "evs.push({t:o.t,z:1e6,kind:'outcome',text:text})" in rhm)
check("...and a mark within 8 s is retagged so the win WINS the seat, "
      "keeping its own kind in also",
      "near.also=[near.kind].concat(near.also||[])" in rhm
      and "near.kind='outcome'; near.text=text;" in rhm)
check("stamp(): outcome is tested BEFORE said; heard = the text",
      "const fk=ev.kind==='outcome'?'outcome':said?'told'" in rhm
      and "const heard=ev.kind==='outcome'?(ev.text||'the screen decided')" in rhm
      and "k==='outcome'?'outcome'" in rhm)
check("the chip 'outcome' joins MARKS, the saved keys, gsig and NAME",
      "outcome:true}" in USRC and "'game','outcome'].forEach" in USRC
      and "['loud','laugh','scream','told','sense','game','outcome'].map" in USRC
      and "game:'game',outcome:'outcome'}" in USRC
      and 'data-m="outcome"' in USRC)
check("the tick wears the brightest gold, outlined",
      '.hlmark[data-fk="outcome"]{background:var(--gold-hi);' in USRC)
check("...and keeps it when told: the outcome+told rule sits BELOW .told, "
      "which ties it on specificity",
      '.hlmark[data-fk="outcome"].told{background:var(--gold-hi)}' in USRC
      and USRC.index(".hlmark.told{") < USRC.index(
          '.hlmark[data-fk="outcome"].told{'))
check("the api.audit contract comment names the six layers, screen among "
      "them", "sound / words / eye / screen /" in USRC
      and "laugh / review (THR_LAYERS, in that order)" in USRC
      and "words / sound / eye / review / laugh." not in USRC)
check("the hover names the screen's verdict",
      "why=ev.kind==='outcome'?('\\u2694 the screen: '+(ev.text||'decided'))" in USRC)
check("the Wins/Losses line under the title, from the senses' tally, "
      "cleared on open, hidden when empty",
      '<div id="vtally" hidden></div>' in USRC
      and "vt.textContent=ln?('The screen decided: '+ln):''; vt.hidden=!ln;" in USRC
      and "const vt=$('#vtally'); if(vt){vt.textContent='';vt.hidden=true;}" in USRC
      and "H('#vtally')" in USRC and "'#vtitle','#vtally'" in USRC)
check("the senses landing redraws the bar so the ticks appear",
      "if(_sns&&(_sns.outcomes||[]).length)renderHlMarks(vid,req);" in USRC)
ps = USRC[USRC.index("function paintSeen"):]
ps = ps[:ps.index("const vd=$('#vvideo'), now=")]
check("the Eye panel: 'The screen decided' rows first, in any and in the "
      "signature",
      "const outs=(vis.outcomes||[])" in ps and "||outs.length);" in ps
      and "outs.map(o=>(o.line||o.text||'')+'@'+o.t)" in ps
      and "'The screen decided'" in ps
      and ps.index("'The screen decided'") < ps.index("'Places'")
      and "'ehead'+(outs.length?'':' first'),'Places'" in ps)
check("LAYNAME, the say order and the help row know 'screen'",
      "LAYNAME={words:'words',sound:'sound',eye:'eye',screen:'screen'," in USRC
      and "['words','sound','eye','screen','review','laugh'].forEach" in USRC
      and "['screen','\\u25a3','the screen']" in USRC)
check("the Thread panel lists what the screen never showed, never a drop",
      "thrArr(o.outcomes)" in USRC and "r.verdict!=='shown'" in USRC
      and "'What the screen never showed \\u00b7 '" in USRC
      and "||outcomes.length)};" in USRC
      and "+lone_names.length+outq.length" in USRC)
check("the Settings row: the in-game name under 'The screen'",
      "divider(R,'The screen');" in USRC and "ctlText('handle',false,'[CLUB] Name')" in USRC
      and USRC.index("divider(R,'The screen')") < USRC.index("divider(R,'Compatibility')"))
check("the MOCK: settings handle, a senses night with outcomes, visions "
      "outcomes, an audit with an unshown row",
      "black_guard:true,handle:''" in USRC
      and "location.hash.includes('outcome')" in USRC
      and "creatures:[],screen:[],outcomes:[]}" in USRC
      and "outcomes:[{where:'chapter',t:271.6,claim:'a win',kind:'win'," in USRC)
check("ONE script block: no new inline string ends it early",
      USRC.lower().count("</script") == 1 and USRC.lower().count("<script") == 1)

print("\n--- the packs ---")
check("both packs and the README ship",
      os.path.isfile(os.path.join(ROOT, "ai", "packs", "rocketleague.ocr.txt"))
      and os.path.isfile(os.path.join(ROOT, "ai", "packs", "hearthstone.ocr.txt"))
      and os.path.isfile(os.path.join(ROOT, "ai", "packs", "README.md")))
rd = io.open(os.path.join(ROOT, "ai", "packs", "README.md"),
             encoding="utf-8").read()
check("the README explains the line grammar",
      "outcome.kind: regex with named groups" in rd and "never deduped" in rd
      and "twelve-letter cut" in rd)
check("no real club tag or name rides in the packs or the worker - the "
      "only bracketed tag is the grammar's placeholder",
      set(re.findall(r"\[([A-Z0-9]{2,6})\]", io.open(os.path.join(
          ROOT, "ai", "packs", "rocketleague.ocr.txt"), encoding="utf-8")
          .read() + WSRC + rd)) <= {"CLUB"})

import shutil
for dd in (tmp, tmpv, tmpw):
    shutil.rmtree(dd, ignore_errors=True)
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
