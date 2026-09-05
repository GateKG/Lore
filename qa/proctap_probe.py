# -*- coding: utf-8 -*-
"""Does per-process audio capture actually work on THIS machine?

Taps the Discord tree, a browser tree and (if one is running) the game
for a few seconds each, at the same time, through the proctap that ships
inside the installed LORE. Reports, per tap: whether Windows granted a
PROCESS-SPECIFIC loopback (the native layer silently falls back to
system-wide on failure - that is the whole question), how loud each
source was second by second, and whether the sources are independent
(a browser playing while Discord is silent must show up on one tap and
not the other). Writes nothing under the library; the WAVs land in the
scratch folder given as argv[1] (or %TEMP%). CPU only, no GPU, no LORE
files touched, safe to run while LORE records.

    python qa/proctap_probe.py [out_dir] [seconds]
"""
import io
import os
import struct
import sys
import time
import wave

sys.path.insert(0, r"C:\Program Files\Lore\_internal")
try:
    import psutil
except ImportError:
    psutil = None
from proctap import ProcessAudioCapture  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TEMP", ".")
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 12.0


def roots(names):
    """The root pid of each named process tree: the one whose parent
    does not wear the same name (Discord.exe has six processes; the
    renderer is not the one to tap)."""
    out = {}
    if psutil is None:
        return out
    procs = {p.pid: p for p in psutil.process_iter(["name", "ppid"])}
    for pid, p in procs.items():
        nm = (p.info.get("name") or "").lower()
        if nm not in names:
            continue
        pp = procs.get(p.info.get("ppid"))
        pnm = ((pp.info.get("name") if pp else "") or "").lower()
        if pnm != nm and nm not in out:
            out[nm] = pid
    return out


def game_pid():
    """Whatever the watcher currently sees, if anything."""
    try:
        import json
        beat = json.load(io.open(os.path.join(os.environ["LOCALAPPDATA"], "Lore", "watch.beat")))
        exe = (beat.get("sees") or "").lower()
        if exe and psutil is not None:
            for p in psutil.process_iter(["name"]):
                if (p.info.get("name") or "").lower() == exe:
                    return exe, p.pid
    except Exception:
        pass
    return "", None


targets = roots({"discord.exe", "chrome.exe", "msedge.exe", "firefox.exe", "spotify.exe"})
g, gp = game_pid()
if gp:
    targets[g] = gp
if not targets:
    print("nothing to tap: no Discord, browser or game running")
    sys.exit(2)
print("tapping:", {k: v for k, v in targets.items()})

taps = {}
bufs = {k: [] for k in targets}
for name, pid in targets.items():
    try:
        t = ProcessAudioCapture(pid, on_data=(lambda k: (lambda pcm, n: bufs[k].append(pcm)))(name))
        taps[name] = t
    except Exception as e:
        print("  %-14s pid %6d  could not open: %s" % (name, pid, str(e)[:120]))
t0 = time.time()
for name, t in taps.items():
    try:
        t.start()
    except Exception as e:
        print("  %-14s start failed: %s" % (name, str(e)[:120]))
time.sleep(SECS)
for name, t in taps.items():
    try:
        t.stop()
    except Exception:
        pass
wall = time.time() - t0

print("\n%-14s %-8s %-9s %-10s %s" % ("source", "specific", "seconds", "peak dBFS", "loud seconds (RMS dBFS per second)"))
for name, t in taps.items():
    pcm = b"".join(bufs[name])
    n = len(pcm) // 4
    spec = None
    try:
        spec = t._backend._native.is_process_specific()
    except Exception as e:
        spec = "?" + str(e)[:40]
    # float32 stereo interleaved -> per-second RMS
    import array
    a = array.array("f")
    a.frombytes(pcm[: (n // 2) * 2 * 4])
    secs = []
    step = 48000 * 2
    peak = 0.0
    for i in range(0, len(a), step):
        chunk = a[i:i + step]
        if not chunk:
            continue
        s = sum(x * x for x in chunk) / len(chunk)
        pk = max(abs(x) for x in chunk)
        peak = max(peak, pk)
        import math
        secs.append(20 * math.log10(math.sqrt(s) + 1e-9))
    import math
    print("%-14s %-8s %-9.1f %-10.1f %s" % (
        name, str(spec), n / 96000.0, 20 * math.log10(peak + 1e-9),
        " ".join("%.0f" % v for v in secs)))
    if pcm:
        wp = os.path.join(OUT, "probe_%s.wav" % name.replace(".exe", ""))
        with wave.open(wp, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(48000)
            w.writeframes(b"".join(struct.pack("<h", max(-32768, min(32767, int(x * 32767)))) for x in a))
print("\nwall %.1fs; captured %.1fs expected per tap" % (wall, SECS))
