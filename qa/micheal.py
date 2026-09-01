# -*- coding: utf-8 -*-
"""The self-healing microphone, proven against the exact failure that
cost him a night: a virtual endpoint whose handle stays open while the
callbacks stop arriving."""
import sys
import threading
import time

sys.path.insert(0, r"D:\Gate LLC")
import lore  # noqa: E402

SAID = []
lore.log = lambda m: SAID.append(m)
lore.load_settings()
lore.SETTINGS["capture_mic"] = True

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


class FakeStream:
    def __init__(self, tag):
        self.tag = tag
        self.stopped = False

    def stop_stream(self):
        self.stopped = True

    def close(self):
        self.stopped = True


class Cap(object):
    """Only the pieces the watchdog touches."""

    def __init__(self):
        self.rings = []
        self._ring_lock = threading.Lock()
        self._streams = []
        self._threads = []
        self._stop = threading.Event()
        self.tmp_dir = "."
        self.tag = ""
        self.mic_wav = None
        self.opened = 0

    def _new_stream(self):
        self.opened += 1
        return FakeStream("s%d" % self.opened)


# borrow the real methods onto our stand-in
for m in ("_mic_ring", "_mic_reopen", "_mic_watch"):
    setattr(Cap, m, getattr(lore.AudioRecorder, m))

cap = Cap()
first = cap._new_stream()
cap._streams.append(first)
ring = {"kind": "mic", "dev": "SteelSeries Sonar - Microphone",
        "cb_at": time.time(), "last_sound": time.time(),
        "t_first": time.time(), "stream": first,
        "reopen": cap._new_stream}
cap.rings.append(ring)
lore._MICWATCH.update({"dev": ring["dev"], "heard": time.time(),
                       "last_sound": time.time(), "quiet": False,
                       "since": time.time(), "said": False,
                       "cb_at": time.time(), "fixes": 0, "state": ""})

print("--- it finds the mic ring ---")
check("the watchdog can see the microphone",
      cap._mic_ring() is ring)

print("\n--- THE FAILURE HE HIT: callbacks stop, handle stays open ---")
SAID[:] = []
ring["cb_at"] = time.time() - 30          # 30s since the last callback
before = cap.opened
healed = cap._mic_reopen(ring, "it stopped sending sound")
check("it reopens the stream in place", healed and cap.opened == before + 1)
check("the dead stream was closed", first.stopped)
check("the new stream is the ring's stream now",
      ring["stream"] is not first and ring["stream"] in cap._streams)
check("the dead one is no longer tracked", first not in cap._streams)
check("it says so, by name, and explains the gap",
      any("Microphone reconnected" in m and "Sonar" in m
          and "silence" in m for m in SAID))
print("      -> " + next(m for m in SAID if "reconnected" in m)[:120])
check("the repair is counted", lore._MICWATCH["fixes"] == 1)

print("\n--- the watchdog does it on its own ---")
SAID[:] = []
ring["cb_at"] = time.time() - 30
before = cap.opened
t = threading.Thread(target=cap._mic_watch, daemon=True)
t.start()
for _ in range(60):
    if cap.opened > before:
        break
    time.sleep(0.2)
cap._stop.set()
t.join(timeout=3)
check("a stalled stream is repaired without anyone asking",
      cap.opened > before)

print("\n--- his NOISE GATE must not be mistaken for a fault ---")
cap2 = Cap()
s0 = cap2._new_stream()
cap2._streams.append(s0)
ring2 = {"kind": "mic", "dev": "Sonar", "cb_at": time.time(),
         "last_sound": time.time() - 200,   # quiet 3 min, gate closed
         "t_first": time.time() - 600, "stream": s0,
         "reopen": cap2._new_stream}
cap2.rings.append(ring2)
before2 = cap2.opened
t2 = threading.Thread(target=cap2._mic_watch, daemon=True)
t2.start()
time.sleep(5)
cap2._stop.set()
t2.join(timeout=3)
check("three minutes of gated silence is left alone",
      cap2.opened == before2)

print("\n--- what the recording line says ---")
lore._MICWATCH.update({"dev": "SteelSeries Sonar - Microphone",
                       "heard": time.time() - 900,
                       "last_sound": time.time() - 400,
                       "cb_at": time.time(), "fixes": 2,
                       "since": time.time() - 900, "said": False})
msg = lore._mic_trouble()
check("a long quiet mentions the reconnects, and blames nobody",
      "quiet" in msg and "reconnected 2" in msg)
print("      -> " + msg)
lore._MICWATCH["cb_at"] = time.time() - 30
msg2 = lore._mic_trouble()
check("a stalled stream says it is reconnecting",
      "reconnecting" in msg2)
print("      -> " + msg2)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
