# -*- coding: utf-8 -*-
"""THE ONE PROOF ONLY A REAL CALL CAN GIVE. Run this while you are in a
Discord voice call and a friend is talking (you can stay quiet). It
taps Discord's root process for 15 seconds beside your microphone and
prints, second by second, how loud each was. Expected: the Discord tap
carries your friend's voice (loud seconds around -30 dBFS or louder)
while the mic tap is quiet when you are not speaking - which proves a
tap on Discord's root hears the call audio its child process renders.

Nothing is written under the library; the WAVs land in %TEMP% so you
can listen to them. CPU only, safe while LORE records.

    python qa/proctap_discord_call.py
"""
import math
import os
import struct
import sys
import time
import wave

sys.path.insert(0, r"C:\Program Files\Lore\_internal")
import psutil  # noqa: E402
from proctap import ProcessAudioCapture  # noqa: E402

OUT = os.environ.get("TEMP", ".")
SECS = 15.0


def root(names):
    procs = {p.pid: p for p in psutil.process_iter(["name", "ppid"])}
    for pid, p in procs.items():
        nm = (p.info.get("name") or "").lower()
        if nm not in names:
            continue
        pp = procs.get(p.info.get("ppid"))
        if ((pp.info.get("name") if pp else "") or "").lower() != nm:
            return nm, pid
    return None, None


exe, pid = root({"discord.exe", "discordptb.exe", "discordcanary.exe"})
if not pid:
    print("Discord is not running - start the call first, then run this again.")
    sys.exit(2)
print("tapping %s (root pid %d) for %.0f s - let a friend talk, stay quiet yourself" % (exe, pid, SECS))
buf = []
tap = ProcessAudioCapture(pid, on_data=lambda pcm, n: buf.append(pcm))
tap.start()
for i in range(int(SECS)):
    time.sleep(1.0)
    print("  %2d s" % (i + 1), end="\r", flush=True)
tap.stop()
print()

import array  # noqa: E402
a = array.array("f")
pcm = b"".join(buf)
a.frombytes(pcm[: (len(pcm) // 8) * 8])
spec = tap._backend._native.is_process_specific()
secs, peak = [], 0.0
for i in range(0, len(a), 96000):
    c = a[i:i + 96000]
    if not c:
        continue
    peak = max(peak, max(abs(x) for x in c))
    secs.append(20 * math.log10(math.sqrt(sum(x * x for x in c) / len(c)) + 1e-9))
loud = sum(1 for v in secs if v > -45)
print("process-specific: %s | %.1f s captured | peak %.1f dBFS | loud seconds %d of %d"
      % (spec, len(a) / 96000.0, 20 * math.log10(peak + 1e-9), loud, len(secs)))
print("per second (RMS dBFS):", " ".join("%.0f" % v for v in secs))
wp = os.path.join(OUT, "probe_discord_call.wav")
with wave.open(wp, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(48000)
    w.writeframes(b"".join(struct.pack("<h", max(-32768, min(32767, int(x * 32767)))) for x in a))
print("saved", wp, "- listen to it: it should be the call, and only the call")
print("\nVERDICT:", ("the Discord tap carries the call - capture by source works for your friends' voices"
                    if spec and loud >= 3 else
                    "the Discord tap stayed quiet - tell Claude; the tap may need to sit on Discord's audio child"))
