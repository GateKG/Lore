# -*- coding: utf-8 -*-
"""The machine facts the 3.31 sources design rests on, as one script.

Folds the scratch probes (tap_lifecycle_probe2.py, tap_walk_probe3.py)
into the roster: through the proctap that ships inside the installed
LORE it taps a SILENT child python and proves, on this machine:

  - a silent target still delivers a continuous stream (zeros) at the
    full rate, so a layer WAV grows at ~384 KB/s float32 whatever plays;
  - a target killed mid-tap keeps delivering zeros with is_running True
    and is_process_specific True - the stream gives NO signal, which is
    why _tap_watch checks the pid, not the audio;
  - a tap on a DEAD pid constructs fine, starts, and reports
    process-specific - why _pid_wears must run BEFORE construction;
  - the first ProcessAudioCapture of a process costs seconds (scipy
    inside proctap's converter) and later ones milliseconds - why
    _prewarm_proctap runs at boot;
  - one tap's steady CPU is a small slice of one core.
Prints the numbers; asserts only the invariants. Plays a quiet tone from
a second child so the render engine is busy (an idle engine can starve a
process loopback, which is the wall-clock fill's job, not this test's).
CPU only, no GPU, nothing under the library touched. Not part of
run_all.bat's deterministic roster - run it by hand:

    python qa/proctap_lifecycle.py
"""
import math
import os
import struct
import subprocess
import sys
import tempfile
import time
import wave

sys.path.insert(0, r"C:\Program Files\Lore\_internal")
import psutil  # noqa: E402

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


TD = tempfile.mkdtemp(prefix="taplife_")
TONE = os.path.join(TD, "quiet_tone.wav")
with wave.open(TONE, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(48000)
    fr = bytearray()
    for i in range(48000 * 25):
        v = int(0.03 * 32767 * math.sin(2 * math.pi * 330 * i / 48000.0))
        fr += struct.pack("<hh", v, v)
    w.writeframes(bytes(fr))

FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)
player = subprocess.Popen([sys.executable, "-c",
                           "import winsound,sys; winsound.PlaySound(sys.argv[1], winsound.SND_FILENAME)",
                           TONE], creationflags=FLAGS)
silent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                          creationflags=FLAGS)
time.sleep(0.8)

print("--- the first tap of a process pays the import ---")
t = time.perf_counter()
from proctap import ProcessAudioCapture  # noqa: E402
import_s = time.perf_counter() - t
bufs = []
t = time.perf_counter()
tap = ProcessAudioCapture(silent.pid, on_data=lambda pcm, n: bufs.append((time.time(), len(pcm))))
first_s = time.perf_counter() - t
print("  import %.2f s, first ctor %.3f s" % (import_s, first_s))
t = time.perf_counter()
tap2 = ProcessAudioCapture(silent.pid, on_data=lambda pcm, n: None)
later_s = time.perf_counter() - t
tap2.close()
print("  a later ctor %.1f ms" % (later_s * 1000))
check("the first (import + ctor) costs far more than a later ctor",
      (import_s + first_s) > 10 * later_s and later_s < 0.5)

print("\n--- a silent target delivers a continuous stream ---")
tap.start()
base = psutil.Process().cpu_times()
t0 = time.time()
time.sleep(4.0)
used = psutil.Process().cpu_times()
secs = time.time() - t0
got = sum(n for _t, n in bufs)
spec = tap._backend._native.is_process_specific()
cpu = ((used.user - base.user) + (used.system - base.system)) / secs * 100
print("  %.0f KB/s over %.1f s, specific=%s, whole-process CPU %.1f%% of one core"
      % (got / secs / 1024, secs, spec, cpu))
check("delivery is continuous for a SILENT target", got / secs > 50 * 1024)
check("the tap is process-specific", spec is True)
check("one tap's steady CPU is a small slice of one core (< 15%%: %.1f%%)" % cpu,
      cpu < 15)
gaps = [b[0] - a[0] for a, b in zip(bufs, bufs[1:])]
check("no gap over a second between chunks", gaps and max(gaps) < 1.0)

print("\n--- the target dies: zeros keep flowing, nothing says so ---")
n_before = len(bufs)
silent.kill()
silent.wait(timeout=5)
time.sleep(3.0)
after = bufs[n_before:]
running = getattr(tap, "is_running", None)
running = running() if callable(running) else running
print("  %d chunks in the 3 s after the kill, is_running=%r, specific=%s"
      % (len(after), running, tap._backend._native.is_process_specific()))
check("chunks keep arriving after the kill", len(after) > 50)
check("is_running stays True (or is not reported)", running in (True, None))
check("is_process_specific stays True", tap._backend._native.is_process_specific() is True)
tap.stop()
tap.close()

print("\n--- a tap on a DEAD pid is granted and specific ---")
dead = silent.pid
t = time.perf_counter()
try:
    dt = ProcessAudioCapture(dead, on_data=lambda pcm, n: None)
    dt.start()
    ctor_ok = True
    dspec = dt._backend._native.is_process_specific()
    time.sleep(0.5)
    dt.stop()
    dt.close()
except Exception as e:
    ctor_ok, dspec = False, repr(e)
print("  ctor+start %.1f ms, specific=%r" % ((time.perf_counter() - t) * 1000, dspec))
check("construction and start succeed on a dead pid", ctor_ok)
check("...and the honesty check would pass it (why the liveness gate exists)",
      dspec is True)

try:
    player.kill()
except Exception:
    pass
import shutil
shutil.rmtree(TD, ignore_errors=True)
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
