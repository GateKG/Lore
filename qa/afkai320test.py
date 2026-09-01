# -*- coding: utf-8 -*-
"""AFK CATCH-UP, proven - including the part he cares about most: that
it hands everything back exactly as he left it.

He has been told twice that AFK detection was fixed and twice found it
was not, so nothing here trusts a boolean; every claim is driven
through the real functions with the real clock stubbed at known values.
"""
import io
import json
import os
import sys
import time

sys.path.insert(0, r"D:\Gate LLC")
import lore  # noqa: E402

# A SUITE THAT TICKS MUST PEN THE LIBRARY WALK. _ai_tick carries the
# once-per-boot migrations (strikes, the eye's gate, the re-fold) and
# every one of them WRITES. Without this the walk would be pointed at
# the real D:\Records the moment a guard above the hook stops
# returning early.
import lore as _pen_lore
_pen_lore._library_dirs = lambda out: []
_pen_lore._scan_dir_mp4s = lambda d, k: []

SAID = []
lore.log = lambda m: SAID.append(m)
lore.load_settings()
lore._ai_state_save = lambda: None
lore._ai_abort = lambda *a, **k: None
# hold the REAL clock before anything stubs it - restoring it from
# lore.__dict__ later just hands back whichever stub was last installed
_REAL_IDLE = lore._afk_idle_seconds
_REAL_RECENT = lore._afk_idle_recent

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


LANES = ("listening", "hearing", "thinking", "auditing")


def idle(sec):
    # both the raw poll and the shared reading, so nothing falls back
    lore._afk_idle_seconds = lambda: float(sec)
    lore._afk_idle_recent = lambda max_age=2.0: float(sec)


def reset(afk_on=True, mins=15, shutdown=False, held=None):
    lore._AFKAI.update({"on": False, "since": 0.0, "idle": 0.0,
                        "held": None, "shut": None})
    lore.SETTINGS["afk_ai"] = afk_on
    lore.SETTINGS["afk_ai_minutes"] = mins
    lore.SETTINGS["bg_shutdown"] = shutdown
    lore._AI["held"] = dict(held or {k: False for k in LANES})
    lore._AI["busy"] = None
    SAID[:] = []


print("--- it uses the RECORDER'S OWN clock, not a second one ---")
src = io.open(r"D:\Gate LLC\lore.py", encoding="utf-8").read()
tick = src.split("def _afk_ai_tick")[1].split("\ndef ")[0]
check("the catch-up reads the recorder's own reading",
      "_afk_idle_recent()" in tick)
check("...which is backed by _afk_idle_seconds and nothing else",
      "_afk_idle_seconds()" in src.split("def _afk_idle_recent")[1]
      .split("\ndef ")[0])
check("...which is the same call the recording pause makes",
      "_afk_idle_seconds()" in src.split("def _afk_track")[1]
      .split("\ndef ")[0])
check("and that clock reads keyboard/mouse AND the controller",
      "_kbms_idle_ms()" in src.split("def _afk_idle_seconds")[1]
      .split("\ndef ")[0]
      and "_pad_check()" in src.split("def _afk_idle_seconds")[1]
      .split("\ndef ")[0])

print("\n--- switched off, it does nothing at all ---")
reset(afk_on=False)
idle(9999)
lore._afk_ai_tick()
check("no override while the setting is off",
      lore._AFKAI["on"] is False)
check("and a shut-down tome stays shut down",
      lore._bg_work_allowed() is True)   # shutdown False here
reset(afk_on=False, shutdown=True)
idle(9999)
lore._afk_ai_tick()
check("...really stays shut down", lore._bg_work_allowed() is False)

print("\n--- on, but he is still at the desk ---")
reset(mins=15)
idle(14 * 60)
lore._afk_ai_tick()
check("14 minutes away does not fire a 15-minute setting",
      lore._AFKAI["on"] is False)

print("\n--- away long enough: the whole suite wakes ---")
reset(mins=15, shutdown=True,
      held={"listening": True, "hearing": True,
            "thinking": True, "auditing": True})
idle(15 * 60)
lore._afk_ai_tick()
check("the catch-up is running", lore._AFKAI["on"] is True)
check("every lane is awake - sound, words, review AND audit",
      not any(lore._AI["held"][k] for k in LANES))
check("it speaks over the master switch too",
      lore._bg_work_allowed() is True)
check("...WITHOUT rewriting his saved preference",
      lore.SETTINGS["bg_shutdown"] is True)
check("the beat is asked to start now", lore._AI["t_last"] == 0)
check("and it says so, naming all four", any(
    "AFK catch-up" in m and "audit" in m for m in SAID))

print("\n--- and it gives it ALL back the moment he returns ---")
SAID[:] = []
idle(2)
lore._afk_ai_tick()
check("the override is over", lore._AFKAI["on"] is False)
check("every lane he had paused is paused again",
      all(lore._AI["held"][k] for k in LANES))
check("the derived 'paused' flag agrees", lore._AI["paused"] is True)
check("his master switch is still exactly what he chose",
      lore.SETTINGS["bg_shutdown"] is True)
check("and the tome is quiet again", lore._bg_work_allowed() is False)
check("it says what happened", any("back exactly as you left it" in m
                                   for m in SAID))

print("\n--- a PARTIAL hold comes back partial, not all-or-nothing ---")
reset(mins=10, shutdown=False,
      held={"listening": False, "hearing": True,
            "thinking": True, "auditing": False})
idle(600)
lore._afk_ai_tick()
check("all four ran while he was away",
      not any(lore._AI["held"][k] for k in LANES))
idle(1)
lore._afk_ai_tick()
check("hearing was held before, and is held again",
      lore._AI["held"]["hearing"] is True)
check("thinking likewise", lore._AI["held"]["thinking"] is True)
check("listening was NOT held, and is still not",
      lore._AI["held"]["listening"] is False)
check("auditing likewise", lore._AI["held"]["auditing"] is False)

print("\n--- turning the switch off mid-run hands the card straight back ---")
api = lore._JsApi.__new__(lore._JsApi)
_save = lore.save_settings
# *args ON PURPOSE. The zero-arg stub that used to be here is exactly
# what hid the critical bug: save_settings takes the dict, afk_ai_set
# called it with none, and the stub happily accepted that. A stub must
# have the same shape as the thing it stands in for, or the test is
# testing the stub. (C1 below drives the REAL save into a temp file.)
lore.save_settings = lambda *a, **k: None
try:
    reset(mins=5, held={k: True for k in LANES})
    idle(600)
    lore._afk_ai_tick()
    check("it is running", lore._AFKAI["on"] is True)
    api.afk_ai_set(on=False)
    check("switching it off releases immediately",
          lore._AFKAI["on"] is False)
    check("and his holds are back",
          all(lore._AI["held"][k] for k in LANES))

    print("\n--- the status the page shows is the REAL clock ---")
    reset(mins=15)
    idle(300)
    st = api.afk_ai_status()
    check("it reports the seconds away", st["idle_s"] == 300.0)
    check("and how long is left", st["left_s"] == 15 * 60 - 300)
    check("it names which device is holding the clock down",
          st["source"] in ("keyboard or mouse", "the controller"))
    check("it says whether a controller has ever been seen",
          isinstance(st["pad_seen"], bool))
    st2 = api.afk_ai_set(minutes=30)
    check("the minutes can be set from the page", st2["minutes"] == 30)
    check("and are clamped to something sane",
          api.afk_ai_set(minutes=9999)["minutes"] == 240
          and api.afk_ai_set(minutes=0)["minutes"] == 1)
finally:
    lore.save_settings = _save

print("\n--- a controller alone keeps him 'here' ---")
# the real clock is min(keyboard/mouse, controller) - so a pad that
# moved 3 seconds ago beats a keyboard idle for an hour
lore._afk_idle_seconds = _REAL_IDLE
_kb = lore._kbms_idle_ms
lore._kbms_idle_ms = lambda: 3600 * 1000
lore._PAD["active_t"] = time.time() - 3
try:
    got = lore._afk_idle_seconds()
    check("the pad's 3 seconds win over an hour of no typing", got < 10)
finally:
    lore._kbms_idle_ms = _kb

print("\n--- it never silently does less than the whole suite ---")
# a switch that is OFF is a deliberate choice, not a pause, so the
# catch-up leaves it alone - but it must SAY so, because every one of
# his complaints this week was the tome doing less without saying
_hl = lore.SETTINGS.get("ai_highlights", True)
_tr = lore.SETTINGS.get("ai_transcribe", True)
try:
    lore.SETTINGS["ai_highlights"] = False
    lore.SETTINGS["ai_transcribe"] = False
    off = lore._afk_ai_off_kinds()
    check("a switched-off part of the suite is named, in his words",
          "sound & gold moments" in off and "transcripts" in off)
    reset(mins=5)
    idle(600)
    lore._afk_ai_tick()
    check("and the start message says what it will NOT do",
          any("switched off in Settings" in m for m in SAID))
    check("the page's status carries the same list",
          "sound & gold moments"
          in (api.afk_ai_status().get("skipping") or []))
    lore.SETTINGS["ai_highlights"] = True
    lore.SETTINGS["ai_transcribe"] = True
    check("with those on, neither is claimed to be skipped",
          "sound & gold moments" not in lore._afk_ai_off_kinds()
          and "transcripts" not in lore._afk_ai_off_kinds())
finally:
    lore.SETTINGS["ai_highlights"] = _hl
    lore.SETTINGS["ai_transcribe"] = _tr

print("\n--- H1: the catch-up adds NO extra controller poll ---")
# _afk_idle_seconds CALLS _pad_check, which reads "the stick moved" as
# a DELTA against the previous poll. More callers = smaller deltas =
# a slow stick sweep that used to register stops registering, which
# would blunt the recorder's own AFK pause.
lore._afk_idle_recent = _REAL_RECENT
lore._afk_idle_seconds = _REAL_IDLE
polls = [0]
_realpad = lore._pad_check


def _counting_pad():
    polls[0] += 1
    return _realpad()


lore._pad_check = _counting_pad
try:
    lore._AFK_SEEN["t"] = 0.0
    lore._afk_idle_seconds()               # the recorder's own beat
    before = polls[0]
    for _ in range(6):                     # six readers straight after
        lore._afk_idle_recent()
    check("six extra readings cost ZERO extra polls",
          polls[0] == before)
    check("...and still return a live number",
          lore._afk_idle_recent() >= 0)
    lore._AFK_SEEN["t"] = time.time() - 30      # stale
    lore._afk_idle_recent()
    check("a stale reading is refreshed, not trusted",
          polls[0] == before + 1)
finally:
    lore._pad_check = _realpad

print("\n--- H2: a switch he touches while away is HIS ---")
reset(mins=5, held={k: False for k in LANES})
idle(600)
lore._afk_ai_tick()
check("the catch-up is running", lore._AFKAI["on"] is True)
lore._AI["held"] = {k: True for k in LANES}   # he is back, presses Stop
idle(1)
lore._afk_ai_tick()
check("his Stop is NOT undone by the release",
      all(lore._AI["held"][k] for k in LANES))
reset(mins=5, held={"listening": True, "hearing": False,
                    "thinking": False, "auditing": False})
idle(600)
lore._afk_ai_tick()
lore._AI["held"]["hearing"] = True            # he pauses ONE lane
idle(1)
lore._afk_ai_tick()
check("the lane he paused stays paused",
      lore._AI["held"]["hearing"] is True)
check("and the lane he never touched is restored",
      lore._AI["held"]["listening"] is True)

print("\n--- K1: the beat REACHES the catch-up during a recording ---")
# the watcher only calls _ai_tick while a session exists if always_read
# is on or something is forced. always_read defaults False - so without
# this the catch-up could never fire (nor release) in the one scenario
# it was built for: a game left running while he walks away.
_w = src.split("if session is not None and (SETTINGS.get(\"always_read\")")[1]
_w = _w.split("_ai_tick(ctl)")[0]
check("the recording-time beat asks when afk_ai is on",
      'SETTINGS.get("afk_ai")' in _w)

print("\n--- K2: a SUSPENDED recording no longer vetoes it ---")


class Ctl:
    saving = 0
    rec_t0 = time.time()

    def __init__(self, sess):
        self.session = sess

    def set_status(self, *a):
        pass

    def notify(self, *a):
        pass


class Sess:
    def __init__(self, susp):
        self.suspended = susp


import tempfile  # noqa: E402
EMPTY = tempfile.mkdtemp(prefix="afkgate_")
_out = lore.SETTINGS.get("output_dir")
lore.SETTINGS["output_dir"] = EMPTY
lore.SETTINGS["always_read"] = False


def got_past(sess, afk_on):
    """Did the beat get past the politeness gate? t_last is only
    stamped after it.

    The override is driven the real way - the setting plus a clock that
    says he is away - because _ai_tick runs _afk_ai_tick FIRST, and
    setting the flag by hand just gets it released again on the spot
    (which the first cut of this test proved, usefully)."""
    lore.SETTINGS["afk_ai"] = afk_on
    idle(9999 if afk_on else 0)
    lore._AFKAI.update({"on": False, "since": 0.0,
                        "held": None, "shut": None, "set": None})
    lore._AI["held"] = {k: False for k in LANES}
    lore._AI["busy"] = None
    lore._AI["force"] = None
    with lore._AI_FORCE_LOCK:
        lore._AI["force_queue"] = []
    lore._AI["t_last"] = 0
    lore._ai_tick(Ctl(sess))
    return lore._AI["t_last"] > 0


try:
    check("a LIVE recording still vetoes, catch-up or not",
          got_past(Sess(False), True) is False)
    check("a suspended recording vetoes when the catch-up is off",
          got_past(Sess(True), False) is False)
    check("...but NOT while the catch-up is running",
          got_past(Sess(True), True) is True)
    check("no recording at all still works normally",
          got_past(None, False) is True)
    lore.SETTINGS["afk_ai"] = True
    idle(9999)
    lore._AFKAI.update({"on": False, "held": None, "shut": None,
                        "set": None})
    lore._AI["held"] = {k: False for k in LANES}
    lore._AI["t_last"] = 0
    c = Ctl(Sess(True))
    c.saving = 1
    lore._ai_tick(c)
    check("a SAVE still vetoes - it has his video file open",
          lore._AI["t_last"] == 0)
finally:
    lore.SETTINGS["output_dir"] = _out
    lore._AFKAI["on"] = False

print("\n--- K3/K4: off costs nothing, and a pinned pad is named ---")
polls2 = [0]
_rp2 = lore._pad_check


def _cnt2():
    polls2[0] += 1
    return _rp2()


lore._pad_check = _cnt2
lore._afk_idle_recent = _REAL_RECENT
lore._afk_idle_seconds = _REAL_IDLE
_sv = lore.save_settings
lore.save_settings = lambda: None
try:
    lore.SETTINGS["afk_ai"] = False
    lore._AFK_SEEN["t"] = time.time() - 3600      # deliberately stale
    before2 = polls2[0]
    for _ in range(4):
        api.afk_ai_status()
    check("with the switch OFF the page's polling costs no pad reads",
          polls2[0] == before2)
    lore.SETTINGS["afk_ai"] = True
    lore._kbms_idle_ms = lambda: 900 * 1000       # 15 min, no typing
    lore._PAD["active_t"] = time.time() - 2       # ...but the pad talks
    lore._AFK_SEEN["t"] = 0.0
    st3 = api.afk_ai_status()
    check("a controller talking while the keyboard is silent is flagged",
          st3.get("pad_stuck") is True)
    # A LIVE CONTROLLER ON HIS DESK MUST NOT DECIDE THIS. _pad_check
    # reads real XInput, so a pad that is merely awake re-stamps
    # active_t between the set and the assertion and the check fails
    # for a reason that has nothing to do with the code. The poll is
    # silenced for this one question.
    lore._pad_check = lambda: None
    lore._PAD["active_t"] = time.time() - 900
    lore._AFK_SEEN["t"] = 0.0
    check("and a quiet pad is not",
          api.afk_ai_status().get("pad_stuck") is False)
    lore._pad_check = _cnt2
finally:
    lore._pad_check = _rp2
    lore._kbms_idle_ms = _kb
    lore.save_settings = _sv

print("\n--- C1: the switch actually saves (it did NOT) ---")
# save_settings takes the dict; afk_ai_set called it with none, so
# every press raised TypeError. My first test hid this by stubbing
# save_settings to a no-op - I was testing my stub, not the code.
# So this one drives the REAL save into a throwaway file.
import tempfile as _tf  # noqa: E402
_sp = lore._settings_path
_dir = _tf.mkdtemp(prefix="afkset_")
lore._settings_path = lambda: os.path.join(_dir, "settings.json")
try:
    r = api.afk_ai_set(on=True, minutes=25)
    check("the toggle returns a status instead of raising",
          isinstance(r, dict) and r.get("enabled") is True)
    check("and it really reached the disk",
          os.path.isfile(lore._settings_path()))
    saved = json.load(io.open(lore._settings_path(), encoding="utf-8"))
    check("with the switch in it", saved.get("afk_ai") is True)
    check("and the minutes he chose", saved.get("afk_ai_minutes") == 25)
    api.afk_ai_set(on=False)
    saved2 = json.load(io.open(lore._settings_path(), encoding="utf-8"))
    check("turning it off persists too", saved2.get("afk_ai") is False)
finally:
    lore._settings_path = _sp

print("\n--- C3: a Resume while away is not undone on release ---")
reset(mins=5, held={k: True for k in LANES})
idle(600)
lore._afk_ai_tick()
check("running, with his four holds remembered",
      lore._AFKAI["on"] is True)
api.ai_resume_all()          # he presses Resume everything while away
idle(1)
lore._afk_ai_tick()
check("his Resume stands - the old holds are NOT put back",
      not any(lore._AI["held"][k] for k in LANES))

reset(mins=5, held={k: False for k in LANES})
idle(600)
lore._afk_ai_tick()
api.ai_pause(True, "thinking")   # he pauses ONE lane while away
idle(1)
lore._afk_ai_tick()
check("a lane he paused while away stays paused",
      lore._AI["held"]["thinking"] is True)
check("and the others are still free",
      not lore._AI["held"]["listening"])

print("\n--- C2: release stops the job riding a re-held lane ---")
aborted = [0]
_ab = lore._ai_abort
lore._ai_abort = lambda *a, **k: aborted.__setitem__(0, aborted[0] + 1)
try:
    reset(mins=5, held={"thinking": True, "listening": False,
                        "hearing": False, "auditing": False})
    idle(600)
    lore._afk_ai_tick()
    lore._AI["busy"] = ("thinking", "something.mp4")
    idle(1)
    lore._afk_ai_tick()
    check("the describer is stopped when its lane is held again",
          aborted[0] == 1)
    aborted[0] = 0
    reset(mins=5, held={k: False for k in LANES})
    idle(600)
    lore._afk_ai_tick()
    lore._AI["busy"] = ("thinking", "something.mp4")
    idle(1)
    lore._afk_ai_tick()
    check("but a job on a FREE lane is left to carry on",
          aborted[0] == 0)
finally:
    lore._ai_abort = _ab

print("\n--- C5: the saved file records HIS holds, not the override's ---")
reset(mins=5, held={"listening": True, "hearing": False,
                    "thinking": True, "auditing": False})
idle(600)
lore._afk_ai_tick()
true_held = lore._afk_ai_true_held()
check("the live dict is all-false while away",
      not any(lore._AI["held"][k] for k in LANES))
check("but what gets written down is what HE set",
      true_held["listening"] is True and true_held["thinking"] is True
      and true_held["hearing"] is False)

print("\n--- and the two switches answer each other ---")
UI = io.open(r"D:\Gate LLC\ui.html", encoding="utf-8").read()
check("the pill defines the refresher the settings row calls",
      "window._afkPillRefresh=async()=>{" in UI)
check("and the settings row defines one for the pill",
      "window._afkRowRefresh=async()=>{" in UI)

print("\n--- M1: BOTH tick gates let the catch-up be asked ---")
# there are two: one for "a recording exists", one twelve lines below
# for "a game is in front and nothing is recording". Missing either
# means opening a game, tabbing out and walking away never ticks.
# the watcher has three _ai_tick(ctl) sites: one for "truly idle"
# (unguarded) and TWO guarded by always_read - "a recording exists"
# and "a game is in front". Both guarded ones must ask.
_w = src.split("READING WHILE RECORDING")[1].split("if auto:")[0]
_guarded = [seg for seg in _w.split("_ai_tick(ctl)")[:-1]
            if 'SETTINGS.get("always_read")' in seg]
check("both always_read-guarded gates are in the watcher",
      len(_guarded) == 2)
check("and both of them ask when afk_ai is on",
      all('SETTINGS.get("afk_ai")' in seg for seg in _guarded))

print("\n--- M2: a by-name ask is not re-paused behind him ---")
reset(mins=5, held={k: True for k in LANES})
idle(600)
lore._afk_ai_tick()
check("running, holding his four", lore._AFKAI["on"] is True)
lore._ai_ask_unhold("all")        # he asks for something BY NAME
idle(1)
lore._afk_ai_tick()
check("the lanes his ask lifted are NOT re-held on his return",
      not lore._AI["held"]["thinking"]
      and not lore._AI["held"]["auditing"])

print("\n--- and the AFK row is on the WORKING page, as he asked ---")
UIW = io.open(r"D:\Gate LLC\ui.html", encoding="utf-8").read()
_work = UIW.split("if(app.key==='work'){")[1].split("if(app.key===")[0]
check("the time selector lives under Working",
      "Work while I am away" in _work)
_video = UIW.split("if(app.key==='video'){")[1].split("if(app.key===")[0]
check("...and no longer under Video",
      "Work while I am away" not in _video)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
