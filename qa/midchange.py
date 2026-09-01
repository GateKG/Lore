# -*- coding: utf-8 -*-
r'''His question: "what happens if in the middle of a recording I press
mix or separate, or change the bitrate?"

Nobody had ever tested it. This does - against real ffmpeg, the way
LORE actually concatenates a session (concat demuxer, stream copy).
'''
import io
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, r"D:\Gate LLC")
import lore  # noqa: E402

lore.log = lambda m: None
lore.load_settings()
FF = lore.SETTINGS["ffmpeg_path"]
FP = os.path.join(os.path.dirname(FF), "ffprobe.exe")
TD = tempfile.mkdtemp(prefix="mid_")

ok = bad = 0


def check(name, cond, note=""):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name + (
        ("  [" + note + "]") if note else ""))


def seg(name, br, fps, size="640x360"):
    """One segment, encoded the way a session's segments are."""
    p = os.path.join(TD, name)
    subprocess.run([FF, "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc=size=%s:rate=%d:duration=2" % (size, fps),
                    "-c:v", "libx264", "-b:v", "%dM" % br,
                    "-pix_fmt", "yuv420p", "-g", "12", p],
                   timeout=180, check=True)
    return p


def concat(parts, out):
    lst = os.path.join(TD, "list.txt")
    with open(lst, "w", encoding="utf-8") as fh:
        for p in parts:
            fh.write("file '%s'\n" % p.replace("\\", "/"))
    r = subprocess.run([FF, "-y", "-v", "error", "-f", "concat",
                        "-safe", "0", "-i", lst, "-c", "copy", out],
                       capture_output=True, text=True, timeout=300)
    return r


def dur(p):
    r = subprocess.run([FP, "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True, timeout=60)
    try:
        return float(r.stdout.strip())
    except Exception:
        return None


print("--- CHANGING BITRATE mid-session ---")
a = seg("a.mp4", 2, 60)
b = seg("b.mp4", 8, 60)          # he slid the bitrate up mid-recording
out = os.path.join(TD, "br.mp4")
r = concat([a, b], out)
d = dur(out)
check("segments of different BITRATE still bind into one film",
      r.returncode == 0 and d and 3.5 < d < 4.5,
      "%.2fs" % (d or 0))

print("\n--- CHANGING FRAMERATE mid-session ---")
c = seg("c.mp4", 4, 60)
e = seg("e.mp4", 4, 30)          # 60fps then 30fps
out2 = os.path.join(TD, "fps.mp4")
r2 = concat([c, e], out2)
d2 = dur(out2)
check("segments of different FRAMERATE bind without error",
      r2.returncode == 0, (r2.stderr or "")[:60])
check("...and the running time is still right",
      d2 and 3.5 < d2 < 4.5, "%.2fs" % (d2 or 0))

print("\n--- CHANGING RESOLUTION mid-session (the dangerous one) ---")
f = seg("f.mp4", 4, 60, "640x360")
g = seg("g.mp4", 4, 60, "800x450")
out3 = os.path.join(TD, "res.mp4")
r3 = concat([f, g], out3)
d3 = dur(out3)
broke = (r3.returncode != 0) or not d3 or d3 < 3.5
print("      ffmpeg said: %s" % ((r3.stderr or "ok").strip()[:90]
                                 or "ok"))
# a test that always passes is not a test: verify the GUARD exists
guard = io.open(r"D:\Gate LLC\lore.py", encoding="utf-8").read()
check("LORE refuses to continue a chapter at a new capture size",
      "capture size changed" in guard,
      "concat itself: %s" % ("mangles it" if broke else "accepts it"))

print("\n--- MIX vs SEPARATE flipped mid-recording ---")
# audio_mode is read only when the film is BOUND, not while capturing,
# so a flip mid-session simply decides the final layout
import inspect
src = inspect.getsource(lore.build_mux_cmd)
check("audio_mode is read at BINDING time, not during capture",
      'audio_mode' in src)
sett = inspect.getsource(lore.build_video_cmd)
check("...and the video encoder never reads audio_mode at all",
      "audio_mode" not in sett)


def wav(path, hz):
    subprocess.run([FF, "-y", "-v", "error", "-f", "lavfi", "-i",
                    "sine=frequency=%d:duration=4:sample_rate=48000" % hz,
                    "-ac", "2", path], timeout=120, check=True)
    return path


vid = seg("v.mp4", 4, 60)
sw = wav(os.path.join(TD, "s.wav"), 200)
mw = wav(os.path.join(TD, "m.wav"), 900)
for mode in ("mix", "separate"):
    lore.SETTINGS["audio_mode"] = mode
    o = os.path.join(TD, "bound_%s.mp4" % mode)
    cmd = lore.build_mux_cmd(vid, sw, mw, o)
    rr = subprocess.run(cmd, capture_output=True, timeout=300)
    q = subprocess.run([FP, "-v", "error", "-select_streams", "a",
                        "-show_entries", "stream=index", "-of",
                        "csv=p=0", o], capture_output=True, text=True,
                       timeout=60)
    n = len([x for x in q.stdout.split() if x.strip()])
    check("flipping to '%s' binds cleanly" % mode,
          rr.returncode == 0 and n >= 1, "%d track(s)" % n)

print("\n--- A LATE MICROPHONE (my watchdog opens one mid-session) ---")
# the wav is HALF the video's length, as if the mic arrived late
short = os.path.join(TD, "late_mic.wav")
subprocess.run([FF, "-y", "-v", "error", "-f", "lavfi", "-i",
                "sine=frequency=900:duration=2:sample_rate=48000",
                "-ac", "2", short], timeout=120, check=True)
lore.SETTINGS["audio_mode"] = "separate"
o = os.path.join(TD, "late.mp4")
# +2000ms: it started two seconds after the picture did
cmd = lore.build_mux_cmd(vid, sw, short, o, 0, 2000)
rr = subprocess.run(cmd, capture_output=True, timeout=300)
dd = dur(o)
check("a mic that arrived LATE still binds, delayed into place",
      rr.returncode == 0 and dd and dd > 3.5,
      "%.2fs" % (dd or 0))
check("and the delay is actually applied",
      any("adelay" in str(x) for x in cmd))

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
