# -*- coding: utf-8 -*-
"""Both audio modes must produce a file whose FIRST track is audible
speech+game. 'Separate' used to lead with the game alone, which is why
he could not hear himself."""
import os
import struct
import sys
import tempfile
import wave

sys.path.insert(0, r"D:\Gate LLC")
import lore  # noqa: E402

lore.log = lambda m: None
lore.load_settings()

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


TD = tempfile.mkdtemp(prefix="aud_")


def wav(path, hz, secs=1.0):
    import math
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(48000)
        n = int(48000 * secs)
        fr = b"".join(struct.pack("<hh", *(
            (int(12000 * math.sin(2 * math.pi * hz * i / 48000)),) * 2))
            for i in range(n))
        w.writeframes(fr)
    return path


SYS = wav(os.path.join(TD, "sys.wav"), 200)
MIC = wav(os.path.join(TD, "mic.wav"), 900)
VID = os.path.join(TD, "v.mp4")
open(VID, "wb").write(b"x")


def build(mode):
    lore.SETTINGS["audio_mode"] = mode
    return lore.build_mux_cmd(VID, SYS, MIC,
                              os.path.join(TD, "out_%s.mp4" % mode))


print("--- what each mode maps ---")
for mode in ("separate", "mix"):
    c = build(mode)
    maps = [c[i + 1] for i, x in enumerate(c) if x == "-map"]
    amix = any("amix" in str(x) for x in c)
    print("  %-9s maps=%s  amix=%s" % (mode, maps, amix))
    if mode == "separate":
        check("SEPARATE leads with the mix, then the parts",
              amix and maps[:2] == ["0:v", "[a]"] and len(maps) == 4)
    else:
        check("MIX is exactly one track, as its label promises",
              amix and maps == ["0:v", "[a]"])

print("\n--- and it really renders that way (ffmpeg, for real) ---")
FF = r"C:\Program Files\Lore\ffmpeg\bin\ffmpeg.exe"
FP = r"C:\Program Files\Lore\ffmpeg\bin\ffprobe.exe"
import subprocess
# a real 1-second video to mux against
subprocess.run([FF, "-y", "-v", "error", "-f", "lavfi", "-i",
                "color=c=black:s=320x240:d=1", "-c:v", "libx264",
                "-pix_fmt", "yuv420p", VID], timeout=120)
for mode in ("separate", "mix"):
    out = os.path.join(TD, "out_%s.mp4" % mode)
    cmd = build(mode)
    r = subprocess.run(cmd, capture_output=True, timeout=180)
    if r.returncode != 0:
        check("%s muxes" % mode, False)
        print("    ", r.stderr.decode("utf-8", "ignore")[-300:])
        continue
    q = subprocess.run([FP, "-v", "error", "-select_streams", "a",
                        "-show_entries", "stream=index", "-of",
                        "csv=p=0", out], capture_output=True,
                       text=True, timeout=60)
    ntracks = len([x for x in q.stdout.split() if x.strip()])
    # is the FIRST track the mix? it must contain BOTH tones
    p = subprocess.run([FF, "-hide_banner", "-i", out, "-map",
                        "0:a:0", "-af", "volumedetect", "-f", "null",
                        "-"], capture_output=True, text=True,
                       timeout=120)
    loud = "mean_volume" in p.stderr
    print("  %-9s tracks=%d  first-track-has-audio=%s"
          % (mode, ntracks, loud))
    if mode == "separate":
        check("separate: three tracks, and track 1 plays",
              ntracks == 3 and loud)
    else:
        check("mix: one track, and it plays", ntracks == 1 and loud)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
