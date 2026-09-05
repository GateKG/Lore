# -*- coding: utf-8 -*-
"""3.32 drop D5 - the story follows the sound.

On 5 Sep 2026 a wedged encoder left 3:04 of picture under 68 minutes of
sound. The describer measured the night by its picture (3 minutes told of
68) and the eye planned looks past the last frame (22 of 24 failed). These
lift the REAL helpers and the eye's planner and prove: the story is the
sound's length when the picture died early, the picture's when the sound
merely drifts past it; the eye never plans a second past the last frame;
the cache answers once per (path, mtime)."""
import ast
import io
import os
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
TREE = ast.parse(SRC)
OK = FAIL = 0


def check(what, cond):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("FAIL:", what)


def extract(name, ns):
    for node in TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = ast.get_source_segment(SRC, node)
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise KeyError(name)


tmp = tempfile.mkdtemp(prefix="lore_pic_")
night = os.path.join(tmp, "hearthstone_20260905_195941.mp4")
io.open(night, "wb").write(b"\0" * 64)

calls = []
ns = {"os": os, "threading": threading, "_PICSEC_CACHE": {}, "_PICSEC_LOCK": threading.Lock(),
      "_PICTURE_DRIFT_S": 60.0, "_EYE_EDGE": 3.0, "_EYE_GAP": 20.0,
      "SETTINGS": {"eye_looks": 24}, "log": lambda m: None}
AV = {"v": (184.0, 4088.6)}
def _av_durations(p):
    calls.append(p)
    return AV["v"]
ns["_av_durations"] = _av_durations
ns["_video_duration"] = lambda p: 4088.6
ns["_read_sidecar"] = lambda p, kind: {"events": [{"t": t, "z": 5 - i} for i, t in enumerate((30.0, 90.0, 150.0, 900.0, 2000.0, 3500.0))]} if kind == "hl" else {}

_picture_seconds = extract("_picture_seconds", ns)
_story_seconds = extract("_story_seconds", ns)
_eye_looks = extract("_eye_looks", ns)

# the picture, cached on (path, mtime)
check("picture seconds read off the video stream", _picture_seconds(night) == 184.0)
n0 = len(calls)
_picture_seconds(night)
check("a second ask costs no probe (cached)", len(calls) == n0)
os.utime(night, (os.path.getmtime(night) + 10, os.path.getmtime(night) + 10))
_picture_seconds(night)
check("a new mtime asks again", len(calls) == n0 + 1)

# the story: the sound's length when the picture died early
secs, note = _story_seconds(night, 4088.6)
check("a picture that died early: the story is the sound's length", abs(secs - 4088.6) < 0.01)
check("...and it says so", note and "picture ends at 3m04s of 68m08s" in note and "follows the sound" in note)

# the story: the picture's length on a drifted recording
AV["v"] = (4080.0, 4088.6)
ns["_PICSEC_CACHE"].clear()
secs, note = _story_seconds(night, 4088.6)
check("a drift of seconds: the story ends with the picture", abs(secs - 4080.0) < 0.01 and note is None)

# the story: a picture longer than the container, or unknown, changes nothing
AV["v"] = (5000.0, 4088.6)
ns["_PICSEC_CACHE"].clear()
check("picture longer than the container: the container", _story_seconds(night, 4088.6) == (4088.6, None))
AV["v"] = None
ns["_PICSEC_CACHE"].clear()
check("unknown picture: the container", _story_seconds(night, 4088.6) == (4088.6, None))
check("a bad dur is 0", _story_seconds(night, "x") == (0.0, None))


# a failed probe is asked again (never a sticky None)
AV["v"] = None
ns["_PICSEC_CACHE"].clear()
calls.clear()
_picture_seconds(night)
_picture_seconds(night)
check("a probe that failed is asked again on the next call", len(calls) == 2)
# the eye never plans a look past the last frame
AV["v"] = (184.0, 4088.6)
ns["_PICSEC_CACHE"].clear()
looks = _eye_looks(night)
check("the eye planned something", len(looks) >= 3)
check("no look past the last frame", all(3.0 <= t <= 184.0 - 3.0 for t in looks))
check("the loud marks inside the picture were kept", any(abs(t - 30.0) < 0.01 for t in looks) and any(abs(t - 150.0) < 0.01 for t in looks))
check("the loud marks past the picture were not", not any(t >= 184.0 for t in looks))

# a healthy night: the eye ranges over the whole recording
AV["v"] = (4088.0, 4088.6)
ns["_PICSEC_CACHE"].clear()
looks = _eye_looks(night)
check("a healthy night keeps the far looks", any(t > 3000.0 for t in looks))

# source pins
check("the describer takes the story's length", "vdur, _story_note = _story_seconds(video_path, dur)" in SRC)
check("the eye caps at the picture", "pic = _picture_seconds(video_path)" in SRC and "if pic and pic < dur:" in SRC)
check("the old min(dur, got[0]) clamp is gone from the describer", "vdur = min(dur, got[0])" not in SRC)
check("the picture cache has its own name (the black-fact cache is _PIC_CACHE)", SRC.count("_PICSEC_CACHE = {}") == 1 and "_PIC_CACHE = {}" in SRC)
check("a failed probe is never cached", "if pic is not None:" in SRC)
check("the frame picker stops at the picture", "_frame_times_for(video_path, lo, _hi_pic)" in SRC and "_pic_s = _picture_seconds(video_path)" in SRC)

import shutil
shutil.rmtree(tmp, ignore_errors=True)
print("%d ok, %d failed" % (OK, FAIL))
sys.exit(1 if FAIL else 0)
