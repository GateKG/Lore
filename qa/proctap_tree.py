# -*- coding: utf-8 -*-
"""Does a tap on a process ROOT hear its CHILDREN? (INCLUDE_TARGET_PROCESS_TREE)

Discord and every Chromium app render sound in a child process, so the
whole capture-by-source design rests on this. A parent python spawns a
child python that plays a tone; the tap sits on the PARENT's pid. If the
tone shows up, the tree is followed. A second tap on the child alone is
the control. CPU only, nothing under the library touched.

    python qa/proctap_tree.py [out_dir]
"""
import math
import os
import struct
import subprocess
import sys
import time
import wave

sys.path.insert(0, r"C:\Program Files\Lore\_internal")
from proctap import ProcessAudioCapture  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TEMP", ".")
TONE = os.path.join(OUT, "probe_tone2.wav")
with wave.open(TONE, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000)
    frames = bytearray()
    for i in range(48000 * 6):
        v = int(0.4 * 32767 * math.sin(2 * math.pi * 660 * i / 48000.0))
        frames += struct.pack("<hh", v, v)
    w.writeframes(bytes(frames))

# the PARENT: sleeps, after spawning a CHILD that plays the tone
parent_code = (
    "import subprocess,sys,time;"
    "c=subprocess.Popen([sys.executable,'-c',"
    "'import winsound,sys;winsound.PlaySound(sys.argv[1],winsound.SND_FILENAME)',sys.argv[1]]);"
    "print(c.pid,flush=True);c.wait()")
parent = subprocess.Popen([sys.executable, "-c", parent_code, TONE],
                          stdout=subprocess.PIPE, text=True,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
child_pid = int(parent.stdout.readline().strip())
time.sleep(0.6)
targets = {"parent(root)": parent.pid, "child(player)": child_pid}
print("tapping:", targets)
bufs = {k: [] for k in targets}
taps = {k: ProcessAudioCapture(pid, on_data=(lambda kk: (lambda pcm, n: bufs[kk].append(pcm)))(k))
        for k, pid in targets.items()}
for t in taps.values():
    t.start()
time.sleep(4.0)
for t in taps.values():
    t.stop()
try:
    parent.wait(timeout=6)
except Exception:
    parent.kill()

import array  # noqa: E402
print("\n%-14s %-8s %-6s %-8s %s" % ("tap", "specific", "secs", "peak dB", "RMS dBFS per second"))
verdict = {}
for name, t in taps.items():
    a = array.array("f"); pcm = b"".join(bufs[name]); a.frombytes(pcm[: (len(pcm) // 8) * 8])
    spec = t._backend._native.is_process_specific()
    secs, peak = [], 0.0
    for i in range(0, len(a), 96000):
        c = a[i:i + 96000]
        if not c:
            continue
        peak = max(peak, max(abs(x) for x in c))
        secs.append(20 * math.log10(math.sqrt(sum(x * x for x in c) / len(c)) + 1e-9))
    verdict[name] = max(secs) if secs else -180
    print("%-14s %-8s %-6.1f %-8.1f %s" % (name, spec, len(a) / 96000.0, 20 * math.log10(peak + 1e-9),
                                        " ".join("%.0f" % v for v in secs)))
print("\nVERDICT:", "the ROOT tap hears its child's sound - the tree is followed"
      if verdict.get("parent(root)", -180) > -40 else
      "the ROOT tap is SILENT while the child plays - a tree tap does NOT reach children here")
