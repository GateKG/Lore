# -*- coding: utf-8 -*-
"""The process manager, proven on the real module: stop-stands-the-
lane-down on every lane, nothing thrown away, the line surviving a
restart, the master shutdown, queue management, and the sweep-next
preview on the real shelf."""
import os
import sys
import tempfile

sys.path.insert(0, r"D:\Gate LLC")
import lore  # noqa: E402

lore.log = lambda m: None
try:
    lore.load_settings()
except Exception:
    pass
lore.save_settings = lambda *a, **k: None
TD = tempfile.mkdtemp(prefix="sched_")
lore._data_dir = lambda: TD
REAL = r"D:\Records\Devour\Videos\devour_20260801_185559.mp4"

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


def reset():
    lore._AI["held"] = {"listening": False, "hearing": False,
                        "thinking": False, "auditing": False}
    lore._AI["wind"] = False
    lore._AI["wind_src"] = None
    lore._AI["force"] = None
    lore._AI["force_want"] = None
    lore._AI["force_redo"] = False
    lore._AI["force_ran"] = set()
    lore._AI["force_queue"] = []
    lore._AI["busy"] = None
    lore._AI["busy_path"] = None
    lore._AI["paused"] = False
    lore._AI.pop("aud_prog", None)
    lore._AI.pop("next_pick", None)
    lore.SETTINGS["bg_shutdown"] = False


api = lore._JsApi.__new__(lore._JsApi)

print("--- the effective lane, one sniff for everyone ---")
check("plain kinds pass through",
      lore._ai_effective_lane("listening", "x.mp4") == "listening")
check("the audit's coat is seen through",
      lore._ai_effective_lane("thinking", "the audit \u00b7 n.mp4")
      == "auditing")
lore._AI["aud_prog"] = {"at": 1}
check("a chain-tail audit is seen through its heartbeat",
      lore._ai_effective_lane("thinking", "n.mp4") == "auditing")
lore._AI.pop("aud_prog", None)

print("\n--- STOP stands the lane down; nothing disappears ---")
reset()
lore._AI["busy"] = ("listening", "song.mp4")
lore._AI["busy_path"] = r"D:\x\song.mp4"
lore._AI["force_queue"] = [(r"D:\x\a.mp4", "all", False, []),
                           (r"D:\x\b.mp4", "sound", False, [])]
r = api.ai_stop_current()
check("stop holds the SOUND lane",
      r["lane"] == "listening" and lore._AI["held"]["listening"])
check("the waiting line is untouched",
      len(lore._AI["force_queue"]) == 2)
check("nothing memoed failed",
      r"D:\x\song.mp4" not in lore._AI["failed"])
reset()
lore._AI["busy"] = ("hearing", "song.mp4")
lore._AI["busy_path"] = r"D:\x\song.mp4"
r = api.ai_stop_current()
check("stop holds the WORDS lane too", r["lane"] == "hearing"
      and lore._AI["held"]["hearing"])
reset()
lore._AI["busy"] = ("thinking", "devour.mp4")
lore._AI["busy_path"] = r"D:\x\dev.mp4"
lore._AI["force"] = r"D:\x\dev.mp4"
lore._AI["force_want"] = "think"
lore._AI["force_ran"] = {"listening"}
lore._AI["force_queue"] = [(r"D:\x\z.mp4", "all", False, [])]
r = api.ai_stop_current()
check("a by-name job returns to the FRONT with its memory",
      r["requeued"] and lore._AI["force_queue"][0][0] == r"D:\x\dev.mp4"
      and "listening" in lore._AI["force_queue"][0][3]
      and len(lore._AI["force_queue"]) == 2)
reset()
lore._AI["busy"] = ("thinking", "the audit \u00b7 n.mp4")
lore._AI["busy_path"] = r"D:\x\n.mp4"
r = api.ai_stop_current()
check("audit stop still lands on the auditing lane",
      r["lane"] == "auditing" and lore._AI["held"]["auditing"])

print("\n--- the MASTER SWITCH ---")
reset()
lore._AI["busy"] = ("thinking", "dev.mp4")
lore._AI["busy_path"] = r"D:\x\d.mp4"
r = api.ai_shutdown(True)
# 3.08: a PAUSE FOR PLAY frees the card at once - it aborts the piece
# in hand instead of winding it down, because he asked for his machine
check("the pause takes the card at once and persists the setting",
      r["shutdown"] and lore._AI.get("abort") is True
      and lore.SETTINGS["bg_shutdown"] is True)
api.ai_pause(True, "listening")
check("a pause press cannot wake the master switch",
      lore.SETTINGS["bg_shutdown"] is True)
check("forced asks refuse with the reason",
      "shut down" in (lore._force_blocked("all") or ""))
check("the audit door refuses",
      lore._audit_ask(r"D:\x\n.mp4", redo=True) is False)
check("the audit's why says it",
      "shut down" in lore._audit_why(REAL, redo=True))
r2 = api.ai_shutdown(False)
check("waking clears its own wind and only its own",
      not r2["shutdown"] and not lore._AI["wind"]
      and lore.SETTINGS["bg_shutdown"] is False)

print("\n--- queue management ---")
reset()
lore._AI["force_queue"] = [(r"D:\x\a.mp4", "all", True, []),
                           (r"D:\x\b.mp4", "sound", False, [])]
lore._AI["held"]["listening"] = True
q = api.ai_queue_list()
check("the list carries want, redo and held-wait",
      q["queue"][0]["redo"] is True and q["queue"][1]["held"] is True
      and q["queue"][0]["want"] == "all")
r = api.ai_queue_drop(r"D:\x\a.mp4")
check("one row lets out", r["ok"] and len(lore._AI["force_queue"]) == 1)
r = api.ai_queue_drop(r"D:\x\nope.mp4")
check("dropping a stranger says so", not r["ok"] and r["why"])
r = api.ai_queue_clear()
check("the line clears without touching the job in hand",
      r["dropped"] == 1 and not lore._AI["force_queue"])

print("\n--- the line SURVIVES a restart ---")
reset()
lore._AI["force"] = REAL
lore._AI["force_want"] = "think"
lore._AI["force_redo"] = True
lore._AI["force_ran"] = {"listening"}
lore._AI["force_queue"] = [("D:\\gone\\nothere.mp4", "all", False, [])]
lore._AI["held"]["auditing"] = True
lore._ai_state_save()
reset()
lore._ai_state_load()
q = lore._AI["force_queue"]
check("the live job comes back at the head; dead paths fall out",
      len(q) == 1 and q[0][0] == REAL and q[0][1] == "think"
      and q[0][2] is True and "listening" in q[0][3])
# 3.18: a hold means "not right now" and DIES with the tome - one
# Stop press used to silence every lane for weeks across restarts
check("the holds do NOT come back (a hold dies with the tome)",
      lore._AI["held"]["auditing"] is False)

print("\n--- the sweep-next preview, on the real shelf ---")
reset()
nx = lore._ai_next_sweep()
check("next-sweep answers by NAME (or honest None)",
      nx is None or (nx.get("name") and nx.get("kind") in
                     ("listening", "hearing", "thinking", "auditing")))
lore.SETTINGS["bg_shutdown"] = True
lore._AI.pop("next_pick", None)
check("shutdown silences the preview", lore._ai_next_sweep() is None)
lore.SETTINGS["bg_shutdown"] = False

reset()
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
