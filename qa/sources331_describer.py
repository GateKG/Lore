# -*- coding: utf-8 -*-
"""3.31 THE DESCRIBER'S VIEW BY SOURCE - dressing, window rule, moments.

Lifts the REAL module-level functions out of lore.py by name
(_seg_layer, _room_words, _dress_line, _window_parts, _aud_voice) and
holds them to:
  (a) OLD-NIGHT PARITY: over 200 synthetic room lines (with and without
      g, 'you', a named voice overlapping) _dress_line's text equals the
      3.30 nested _line lifted out of `git show HEAD:lore.py` - so no
      review on the shelf is re-owed by this change;
  (b) a media line is dressed '(a video playing in the background, not
      the room)' BEFORE the text and never gets a name;
  (c) a game line is dressed "(the game's own voice)";
  (d)-(f) _window_parts: media thinned to <= 8 per window, >= 60 s
      apart, room never thinned, time order; a room-silent window is
      'what was being watched'; under three lines files silent;
  (g) _room_words ignores media and game words;
  (h) the moments post-check - the REAL loop lines lifted out of
      _insights_one and run with a fake answer: a moment on a video's
      line is dropped and counted;
  plus the wiring, read from the source (_line is the wrapper, the
  words verdict, the head prefix, the two _DESC_SYSTEM rules)."""
import ast
import io
import os
import re
import subprocess
import sys
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
# the 3.30 nested _line lives in the file BEFORE the reader (stage B,
# a7a461f) - HEAD carries the reader itself once it is committed
HEAD = subprocess.run(["git", "-C", ROOT, "show", "a7a461f:lore.py"],
                      capture_output=True, text=True,
                      encoding="utf-8").stdout

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


TREE = ast.parse(SRC)
HTREE = ast.parse(HEAD)


def extract(tree, src, name, ns):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                src.splitlines()[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name + " not found")


ns = {"os": os, "re": re}
for nm in ("_aud_voice", "_seg_layer", "_room_words", "_dress_line",
           "_window_parts"):
    extract(TREE, SRC, nm, ns)
_seg_layer = ns["_seg_layer"]
_room_words = ns["_room_words"]
_dress_line = ns["_dress_line"]
_window_parts = ns["_window_parts"]

# the 3.30 body: the nested _line of HEAD's _insights_one, lifted as it
# was, closing over _sd0 and _aud_voice
hns = {"os": os, "re": re, "_aud_voice": ns["_aud_voice"]}
head_line = extract(HTREE, HEAD, "_line", hns)

print("--- (a) old-night parity: 200 room lines, byte for byte ---")
SNS = {"names": {"0": "Marid", "1": "you"},
       "speakers": [{"a": 10.0, "b": 14.0, "who": "0"},
                    {"a": 30.0, "b": 33.0, "who": "1"},
                    {"a": 50.0, "b": 52.0, "who": "2"}]}
segs = []
for i in range(200):
    t = i * 1.7
    sg = {"a": int(t * 1000), "b": int((t + 1.2) * 1000),
          "t": "line number %d says a thing" % i}
    if i % 7 == 0:
        sg["g"] = 1
    if i % 11 == 0:
        sg["src"] = "you"
    if i % 13 == 0:
        sg["t"] = "  padded  "
    segs.append(sg)
hns["_sd0"] = SNS
same = all(_dress_line(sg, i, SNS) == head_line(sg, i)
           for i, sg in enumerate(segs))
check("_dress_line equals the 3.30 _line on every room line (names sns)",
      same)
hns["_sd0"] = {}
check("...and with no senses sidecar at all",
      all(_dress_line(sg, i, {}) == head_line(sg, i)
          for i, sg in enumerate(segs)))
check("a named overlap still names (Marid at 10-14 s)",
      _dress_line({"a": 11000, "b": 12000, "t": "hi"}, 3, SNS)
      == "[#3 0:11] Marid: hi")
check("a 'you' overlap from the sns becomes YOU:",
      _dress_line({"a": 31000, "b": 32000, "t": "hi"}, 4, SNS)
      == "[#4 0:31] YOU: hi")
check("the g flag keeps today's tail and no name",
      _dress_line({"a": 11000, "b": 12000, "t": "music", "g": 1}, 5, SNS)
      == "[#5 0:11] music (probably the game's own audio)")

print("\n--- (b) (c) media and game dressing ---")
m = _dress_line({"a": 11000, "b": 12000, "t": "the Quilboar build is dead",
                 "src": "media", "why": "mix>voice"}, 6, SNS)
check("a media line is told what it is BEFORE the text",
      m == "[#6 0:11] (a video playing in the background, not the room) "
           "the Quilboar build is dead")
check("...and never a name, even under Marid's overlap", "Marid" not in m)
mg = _dress_line({"a": 11000, "b": 12000, "t": "the Quilboar build is dead",
                  "src": "media", "g": 1}, 6, SNS)
check("a media line that is also g is still media",
      mg.startswith("[#6 0:11] (a video playing") and "probably" not in mg)
g = _dress_line({"a": 11000, "b": 12000, "t": "The enemy has slain your ally.",
                 "src": "game", "why": "game tap"}, 7, SNS)
check("a game line is the game's own voice",
      g == "[#7 0:11] (the game's own voice) The enemy has slain your ally.")
check("_seg_layer: media / game / room (you, absent, g, junk)",
      _seg_layer({"src": "media"}) == "media"
      and _seg_layer({"src": "game"}) == "game"
      and _seg_layer({"src": "you"}) == "room"
      and _seg_layer({}) == "room" and _seg_layer({"g": 1}) == "room"
      and _seg_layer({"src": "MEDIA"}) == "media" and _seg_layer(None) == "room")

print("\n--- (d)-(f) the window rule ---")


def mk(t, src=None, txt="x"):
    d = {"a": int(t * 1000), "b": int(t * 1000 + 900), "t": txt}
    if src:
        d["src"] = src
    return d


room = [mk(10 + 170 * i) for i in range(10)]              # 10 over 30 min
media = [mk(5 + 45 * i, "media") for i in range(40)]      # 40, every 45 s
part, mo = _window_parts(room + media)
kept_m = [sg for sg in part if sg.get("src") == "media"]
check("10 room + 40 media: at most 8 media kept, >= 60 s apart",
      len(kept_m) == 8
      and all((kept_m[i + 1]["a"] - kept_m[i]["a"]) >= 60000
              for i in range(len(kept_m) - 1)))
check("...every room line kept, time-ordered, media_only False",
      [sg for sg in part if not sg.get("src")] == sorted(
          room, key=lambda s: s["a"])
      and [sg["a"] for sg in part] == sorted(sg["a"] for sg in part)
      and mo is False)
part, mo = _window_parts(media[:5])
check("0 room + 5 media: all 5 kept, media_only True",
      len(part) == 5 and mo is True)
part, mo = _window_parts(room[:2] + media[:2])
check("2 room + 2 media: the room's 2 lines back, media_only False (the "
      "caller files the window silent; a video does not make it a chapter)",
      part == room[:2] and mo is False)
part, mo = _window_parts(room[:2] + media[:3] + [mk(7, "game")])
check("2 room + 3 media + a game line: the watched window carries the game "
      "line too, not the room's two", len(part) == 4 and mo is True
      and not any(sg.get("src") is None for sg in part))
game = [mk(20 + 100 * i, "game") for i in range(3)]
part, mo = _window_parts(room + game)
check("an old night (room + game, no media): the same lines in time order",
      part == sorted(room + game, key=lambda s: s["a"]) and mo is False)
part, mo = _window_parts(room[:1])
check("one lone line: files silent", part == room[:1] and mo is False)

print("\n--- (g) the words the room said ---")
check("_room_words ignores media and game words",
      _room_words([mk(1, None, "one two three"), mk(2, "media", "a b c d e"),
                   mk(3, "game", "f g"), mk(4, "you", "four")]) == 4
      and _room_words([]) == 0)

print("\n--- (h) the moments post-check, the real loop ---")
i0 = SRC.index('                for mm in ((got or {}).get("moments") or [])[:4]:')
i1 = SRC.index("                # WHAT IT LEFT COMES BACK.", i0)
block = textwrap.dedent(SRC[i0:i1])
use = [mk(10, None, "we laugh"), mk(20, "media", "video line"),
       mk(30, "game", "announcer"), mk(40, None, "shout")]
lns = {"_seg_layer": _seg_layer, "use": use, "wmoments": [],
       "_mdrop": [0], "str": str,
       "_lt": lambda v, fb: use[max(0, min(len(use) - 1, int(v)))],
       "_m_qcheck": lambda mm, why, u: why,
       "_devoice": lambda x: x, "_descrub": lambda x: x,
       "got": {"moments": [{"line": 1, "why": "the video shouts", "kind": "funny"},
                           {"line": 0, "why": "everyone laughs", "kind": "funny"},
                           {"line": 2, "why": "the announcer", "kind": "big"},
                           {"line": 3, "why": "a shout", "kind": "big"}]}}
exec(compile(block, "<moments>", "exec"), lns)
check("a moment on a video's line OR the game's is dropped and counted "
      "(3.31 stage D: the game's own voice is never the room either)",
      lns["_mdrop"][0] == 2
      and [m["why"] for m in lns["wmoments"]]
      == ["everyone laughs", "a shout"])
check("...the kept moments sit on their lines' clocks",
      all(abs(m["t"] - t0) < 0.06 for m, t0 in
          zip(lns["wmoments"], (10.45, 40.45))))

print("\n--- the wiring ---")
check("_line is the one-line wrapper over _dress_line",
      "    def _line(sg, i):\n        return _dress_line(sg, i, _sd0)" in SRC)
check("the 'nothing was said' verdict counts the room, and a video-only "
      "night carries on",
      "words = _room_words(segs)" in SRC
      and "if words < 12 and mwords < 12:" in SRC)
check("the window asks _window_parts and files < 3 lines silent",
      "part, media_only = _window_parts(wpart)" in SRC
      and SRC.index("part, media_only = _window_parts(wpart)")
      < SRC.index("if len(part) < 3:\n                windows[str(int(lo))] = []"))
check("a media-only window's head says what to write",
      "NOBODY IN THE ROOM SPOKE in this window." in SRC
      and "if media_only else \"\")" in SRC)
i_sys = SRC.index("_DESC_SYSTEM = ")
i_end = SRC.index('"""', SRC.index("RULES:", i_sys))
rules = SRC[i_sys:i_end]
check("_DESC_SYSTEM carries the video rule, quoting the prefix form",
      '(a video playing in the background, not the room)' in rules
      and "never build a moment on it" in rules)
check("...and the game's-own-voice rule",
      "(the game's own voice)" in rules and "it is never who laughed" in rules)
check("...before the final 'Write Arabic' rule",
      rules.index("(the game's own voice)")
      < rules.index("- Write Arabic in Arabic letters"))
check("the dropped-moments log line names both",
      "moment(s) pointed " in SRC
      and "at a video's or the game's line and were dropped - " in SRC
      and 'neither is the room.")' in SRC)

print("\n--- (i) 3.31 stage D: the game's lines are thinned like a video's ---")
room3 = [mk(5, None, "one"), mk(6, None, "two"), mk(7, None, "three")]
gl = [mk(10 + 10 * i, "game", "line %d" % i) for i in range(100)]
part, mo = _window_parts(room3 + gl)
gk = [sg for sg in part if _seg_layer(sg) == "game"]
check("with three room lines, 100 game lines 10 s apart thin to 8, >= 60 s "
      "apart, the room untouched",
      not mo and len(gk) == 8
      and all(b["a"] - a["a"] >= 60000 for a, b in zip(gk, gk[1:]))
      and [sg for sg in part if _seg_layer(sg) == "room"] == room3
      and [sg["a"] for sg in part] == sorted(sg["a"] for sg in part))
ml = [mk(11 + 10 * i, "media", "video %d" % i) for i in range(5)]
part, mo = _window_parts(ml + gl)
check("a room-silent window keeps every media line and thins the game's",
      mo and len([sg for sg in part if _seg_layer(sg) == "media"]) == 5
      and len([sg for sg in part if _seg_layer(sg) == "game"]) == 8)
part, mo = _window_parts(gl[:2] + [mk(3, None, "hi")])
check("under three lines of either kind the game's lines pass through "
      "unthinned (the caller files the window silent)",
      not mo and len(part) == 3)
check("the describer generation was NOT bumped for this (no re-owed reviews)",
      re.search(r"^_INS_GEN\s*=\s*(\d+)", SRC, re.M).group(1)
      == re.search(r"^_INS_GEN\s*=\s*(\d+)", HEAD, re.M).group(1)
      if re.search(r"^_INS_GEN\s*=", SRC, re.M) else True)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
