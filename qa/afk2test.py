# -*- coding: utf-8 -*-
"""The AFK regression he hit tonight, proven dead: a resting controller
must not read as a person, and a recording of pure silence must pause
even if some input signal insists he is there."""
import sys
import threading
import time

sys.path.insert(0, r"D:\Gate LLC")
import lore  # noqa: E402

SAID = []
lore.log = lambda m: SAID.append(m)
lore.load_settings()

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


print("--- a controller resting with drift is NOT a person ---")
THRESH = (lambda g, prev: (
    g["b"] != prev[0]
    or abs(g["lt"] - prev[1]) > 30 or abs(g["rt"] - prev[2]) > 30
    or abs(g["lx"] - prev[4]) > 3200 or abs(g["ly"] - prev[5]) > 3200
    or abs(g["rx"] - prev[6]) > 3200 or abs(g["ry"] - prev[7]) > 3200))
rest = {"b": 0, "lt": 0, "rt": 0, "lx": 9000, "ly": 200,
        "rx": -9500, "ry": 0}          # both sticks drifted past dead zone
prev = (0, 0, 0, 1, 9000, 200, -9500, 0)
check("a drifted but motionless pad reads as IDLE",
      THRESH(rest, prev) is False)
played = dict(rest, lx=200)
check("a stick that actually moved reads as ACTIVE",
      THRESH(played, prev) is True)
check("a button press reads as ACTIVE",
      THRESH(dict(rest, b=4096), prev) is True)
check("a trigger pull reads as ACTIVE",
      THRESH(dict(rest, rt=200), prev) is True)
check("tiny jitter under the movement floor stays IDLE",
      THRESH(dict(rest, lx=9000 + 900, ly=200 - 700), prev) is False)

print("\n--- the real code stores the sticks now ---")
src = open(r"D:\Gate LLC\lore.py", encoding="utf-8").read()
check("_pad_check remembers stick positions",
      "g.sThumbLX, g.sThumbLY," in src and "g.sThumbRX, g.sThumbRY)" in src)
check("and compares them to where they WERE, not to the dead zone",
      "abs(g.sThumbLX - prev[4]) > 3200" in src)
check("the absolute dead-zone test is gone",
      "abs(g.sThumbLX) > 7849" not in src)

print("\n--- the silence backstop ---")


class Ring(dict):
    pass


class Aud:
    def __init__(self, last_sound):
        self._ring_lock = threading.Lock()
        self.rings = [{"kind": "mic", "last_sound": last_sound},
                      {"kind": "system", "last_sound": last_sound}]


class Sess:
    suspended = False
    afk_paused = False

    def __init__(self, aud):
        self.audio = aud

    def suspend(self):
        self.suspended = True


class Ctl:
    rec_t0 = time.time() - 7200

    def set_status(self, s):
        pass

    def notify(self, *a):
        pass


now = time.time()
loud = Sess(Aud(now - 5))
quiet = Sess(Aud(now - 3000))          # 50 minutes of nothing heard
ctl = Ctl()
check("a recording that is hearing things reports ~no deaf time",
      lore._afk_deaf_seconds(ctl, loud) < 30)
check("a silent recording reports its full quiet",
      2900 < lore._afk_deaf_seconds(ctl, quiet) < 3100)
check("no audio object at all is not treated as silence",
      lore._afk_deaf_seconds(ctl, Sess(None)) == 0.0)

print("\n--- and it PAUSES, even when the input clock lies ---")
_real_idle = lore._afk_idle_seconds
_real_snd = lore._loop_sound
lore._loop_sound = lambda *a, **k: None
lore.SETTINGS["afk_pause"] = True
lore.SETTINGS["afk_minutes"] = 4
try:
    # the exact shape of tonight's failure: something insists he is
    # here (a drifting pad), while the room has been silent for an hour
    lore._afk_idle_seconds = lambda: 3.0
    SAID[:] = []
    lore._afk_track(ctl, quiet, "rocketleague.exe")
    check("a silent recording is paused despite an 'active' input",
          quiet.afk_paused is True and quiet.suspended is True)
    check("and it says plainly that something claimed he was here",
          any("not a sound on any track" in m for m in SAID))
    print("      -> " + next((m for m in SAID
                              if "not a sound" in m), "")[:110])
    # and a LOUD recording with a live input is left alone
    loud2 = Sess(Aud(time.time() - 2))
    lore._afk_idle_seconds = lambda: 3.0
    lore._afk_track(ctl, loud2, "rocketleague.exe")
    check("a live, audible session is never touched",
          loud2.afk_paused is False and loud2.suspended is False)
finally:
    lore._afk_idle_seconds = _real_idle
    lore._loop_sound = _real_snd

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
