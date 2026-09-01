# -*- coding: utf-8 -*-
"""The mic watch: it must speak up when the microphone goes quiet, and
must NOT nag when it is working."""
import sys
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


def reset(dev="SteelSeries Sonar - Microphone"):
    lore._MICWATCH.update({"dev": dev, "heard": None, "last_sound": None,
                           "quiet": False, "since": time.time(),
                           "said": False})
    SAID[:] = []


lore.SETTINGS["capture_mic"] = True

print("--- a mic that is working says nothing ---")
reset()
lore._MICWATCH["heard"] = time.time() - 300
lore._MICWATCH["last_sound"] = time.time() - 2
check("no nagging while sound is arriving", lore._mic_trouble() == "")

print("\n--- a mic that never made a sound ---")
reset()
lore._MICWATCH["since"] = time.time() - 30
check("it waits before crying wolf (30s in)",
      lore._mic_trouble() == "")
lore._MICWATCH["since"] = time.time() - 200
msg = lore._mic_trouble()
# 3.11 stopped blaming his device - it reconnects instead, and the
# line reports rather than accuses
check("after 90s it speaks, and NAMES the device",
      "SteelSeries" in msg and "not made a sound" in msg)
print("      -> " + msg)

print("\n--- a mic that was working and dropped out ---")
reset()
lore._MICWATCH["heard"] = time.time() - 1800
lore._MICWATCH["last_sound"] = time.time() - 400
lore._MICWATCH["cb_at"] = time.time()
msg = lore._mic_trouble()
check("it says how long it has been quiet",
      "SteelSeries" in msg and "quiet for" in msg)
print("      -> " + msg)

print("\n--- switched off means silence is expected ---")
reset()
lore.SETTINGS["capture_mic"] = False
lore._MICWATCH["since"] = time.time() - 999
check("no warning when he turned the mic off",
      lore._mic_trouble() == "")
lore.SETTINGS["capture_mic"] = True

print("\n--- the digital-silence test itself ---")
# exactly what the callback asks of each chunk
silence = b"\x00" * 4096
speech = b"\x00\x12\x00\x34" + b"\x00" * 4092
check("pure digital silence reads as nothing",
      not silence.strip(b"\x00"))
check("any real sample reads as something",
      bool(speech.strip(b"\x00")))

print("\n--- and the page is told ---")
reset()
lore._MICWATCH["since"] = time.time() - 200
api = lore._JsApi.__new__(lore._JsApi)


class _Ctl:
    status = "recording"
    session = None
    saving = 0
    rec_t0 = time.time() - 60

    def eff_status(self):
        return "recording"


api._ctl = _Ctl()
api._hdr_cache = {"t": 0, "v": False}
api._disk_cache = {"t": 0, "v": 100.0}
try:
    stt = api.state()
    check("state() carries mic_trouble to the page",
          "SteelSeries" in (stt.get("mic_trouble") or ""))
    check("and it is logged once, loudly",
          any("MICROPHONE:" in m for m in SAID))
except Exception as e:
    check("state() carries mic_trouble to the page", False)
    print("      state() raised:", str(e)[:120])

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
