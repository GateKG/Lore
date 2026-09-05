# -*- coding: utf-8 -*-
"""Proof of FLOW and ISOLATION for per-process capture on this machine.

Spawns a child python that plays a 440 Hz tone for ~8 s through the
default playback device (winsound), then taps THAT child's pid, the
Discord tree and a browser tree at the same time through the proctap
inside the installed LORE. Expected: the tone tap is loud and the other
two stay silent - audio flows, and a tap hears only its own tree.
CPU only, nothing under the library touched, safe while LORE runs.

    python qa/proctap_flow.py [out_dir]
"""
import math
import os
import struct
import subprocess
import sys
import time
import wave

sys.path.insert(0, r"C:\Program Files\Lore\_internal")
import psutil  # noqa: E402
from proctap import ProcessAudioCapture  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TEMP", ".")
TONE = os.path.join(OUT, "probe_tone.wav")
with wave.open(TONE, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(48000)
    frames = bytearray()
    for i in range(48000 * 8):
        v = int(0.4 * 32767 * math.sin(2 * math.pi * 440 * i / 48000.0))
        frames += struct.pack("<hh", v, v)
    w.writeframes(bytes(frames))

child = subprocess.Popen([sys.executable, "-c",
                          "import winsound,sys; winsound.PlaySound(sys.argv[1], winsound.SND_FILENAME)",
                          TONE], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
time.sleep(0.8)          # let the child open its stream


def root(name):
    procs = {p.pid: p for p in psutil.process_iter(["name", "ppid"])}
    for pid, p in procs.items():
        if (p.info.get("name") or "").lower() != name:
            continue
        pp = procs.get(p.info.get("ppid"))
        if ((pp.info.get("name") if pp else "") or "").lower() != name:
            return pid
    return None


targets = {"tone(child)": child.pid}
for nm in ("discord.exe", "chrome.exe"):
    pid = root(nm)
    if pid:
        targets[nm] = pid
print("tapping:", targets)
bufs = {k: [] for k in targets}
taps = {}
for name, pid in targets.items():
    taps[name] = ProcessAudioCapture(pid, on_data=(lambda k: (lambda pcm, n: bufs[k].append(pcm)))(name))
for t in taps.values():
    t.start()
time.sleep(6.0)
for t in taps.values():
    t.stop()
try:
    child.wait(timeout=5)
except Exception:
    child.kill()

import array  # noqa: E402
print("\n%-12s %-8s %-7s %-9s %s" % ("source", "specific", "secs", "peak dB", "RMS dBFS per second"))
for name, t in taps.items():
    pcm = b"".join(bufs[name])
    a = array.array("f")
    a.frombytes(pcm[: (len(pcm) // 8) * 8])
    spec = t._backend._native.is_process_specific()
    secs, peak = [], 0.0
    for i in range(0, len(a), 96000):
        c = a[i:i + 96000]
        if not c:
            continue
        peak = max(peak, max(abs(x) for x in c))
        secs.append(20 * math.log10(math.sqrt(sum(x * x for x in c) / len(c)) + 1e-9))
    print("%-12s %-8s %-7.1f %-9.1f %s" % (name, spec, len(a) / 96000.0, 20 * math.log10(peak + 1e-9),
                                          " ".join("%.0f" % v for v in secs)))
