# -*- coding: utf-8 -*-
"""The race the AFK catch-up's lock exists for.

_afk_ai_tick runs on the watcher thread; afk_ai_set and _afk_ai_forget
run on the pywebview thread. Arming and releasing are both
check-then-act on one dict. A double-arm would snapshot the ALREADY
CLEARED holds as though they were his - which is the whole feature
quietly losing his switches, the exact class of bug he has been hit by
all week. Six threads, 120 storms, he comes back mid-storm every time.
"""
import sys
import threading
import time

sys.path.insert(0, r"D:\Gate LLC")
import lore  # noqa: E402

lore.log = lambda m: None
lore.load_settings()
lore._ai_state_save = lambda: None
lore._ai_abort = lambda *a, **k: None
lore.save_settings = lambda *a, **k: None      # same shape as the real one

HIS = {"listening": True, "hearing": False,
       "thinking": True, "auditing": False}
bad = 0

for trial in range(120):
    lore._AFKAI.update({"on": False, "since": 0.0, "held": None,
                        "shut": None, "set": None})
    lore.SETTINGS["afk_ai"] = True
    lore.SETTINGS["afk_ai_minutes"] = 1
    lore._AI["held"] = dict(HIS)
    lore._AI["busy"] = None
    away = [True]
    lore._afk_idle_recent = lambda m=2.0: (9999.0 if away[0] else 1.0)
    lore._afk_idle_seconds = lambda: (9999.0 if away[0] else 1.0)

    def beat():
        for _ in range(30):
            lore._afk_ai_tick()
            time.sleep(0)

    ts = [threading.Thread(target=beat) for _ in range(6)]
    for t in ts:
        t.start()
    time.sleep(0.004)
    away[0] = False                    # he comes back mid-storm
    for t in ts:
        t.join()
    lore._afk_ai_tick()                # settle
    if lore._AI["held"] != HIS or lore._AFKAI["on"]:
        bad += 1
        if bad < 3:
            print("  trial %d -> %r on=%s"
                  % (trial, lore._AI["held"], lore._AFKAI["on"]))

print("120 concurrent arm/release storms: %d wrong" % bad)
print("PASS - his holds always came back exactly" if not bad
      else "FAIL - a race lost his switches")
print("\n%d ok, %d failed" % (1 if not bad else 0, 1 if bad else 0))
sys.exit(1 if bad else 0)
