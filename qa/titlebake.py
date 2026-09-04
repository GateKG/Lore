# -*- coding: utf-8 -*-
"""The title bake-off: the same nights, the same model or another, the
prompt the app uses today against a prompt that hands the model what
actually happened - measured side by side, never guessed.

    titlebake.py plan [--n 12]
        pick the nights (complete review, rich transcript, spread over
        games) -> <scratch>/bake_plan.json

    titlebake.py run <label> [--model PATH] [--runtime llama|llama2]
                     [--url http://127.0.0.1:8999] [--ngl 99|0]
                     [--variant A|B|AB] [--n N] [--temp 0.4]
        start a PRIVATE llama-server on port 8999 (never LORE's own
        ports), ask every planned night under each variant, append
        rows to <scratch>/bake_<label>.jsonl, stop the server.
        REFUSES the GPU when a llama-server is already running or a
        game is detected (watch.beat) - one model on the card, ever.
        --url alone = talk to a server somebody else started.

    titlebake.py report
        every bake_*.jsonl -> <scratch>/BAKE_REPORT.md, one block per
        night: the served title, then each label/variant's answer,
        with the cheap shape checks (list? verb? generic? grounded?).

Variant A is the app's title ask reconstructed from lore.py verbatim
(chapter NAMES ranked by salience, nothing else). Variant B hands the
model the evidence the night already holds - what each chapter WAS,
the quotes, the moments and why, what the senses heard, what the eye
saw, what the HUD printed - and asks for the event, not the topic.
"""
import glob
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from collections import Counter

TH = r"D:\Records\.lore_thumbs"
LIB = r"D:\Records"
SCRATCH = os.environ.get("LORE_BAKE_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "bake")
os.makedirs(SCRATCH, exist_ok=True)
INSTALL = r"C:\Program Files\Lore"
MODELS = os.path.join(INSTALL, "ai", "models")
PORT = 8999

# ----------------------------------------------------------------- disk


def side(base, kind):
    p = os.path.join(TH, base + "." + kind + ".json")
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return None


def video_of(base):
    for pat in (os.path.join(LIB, "*", "Videos", base + ".mp4"),
                os.path.join(LIB, "*", "Clips", base + ".mp4"),
                os.path.join(LIB, "*", base + ".mp4")):
        got = glob.glob(pat)
        if got:
            return got[0]
    return None


def game_of(base):
    v = video_of(base)
    if v:
        pp = os.path.dirname(v)
        if os.path.basename(pp).lower() in ("videos", "clips"):
            return os.path.basename(os.path.dirname(pp))
        return os.path.basename(pp)
    return re.sub(r"_\d{8}_\d{6}$", "", base)


def mmss(t):
    t = max(0, int(t or 0))
    return "%d:%02d" % (t // 60, t % 60)


# --------------------------------------------------------------- evidence


def chapters_ranked(ins, hl):
    """cinfo exactly as _insights_one builds it, then _sal's ranking."""
    wins = ins.get("windows") or {}
    cinfo = []
    for k in sorted(wins, key=lambda x: float(x)):
        w = wins[k]
        segs = (w.get("segments") if isinstance(w, dict) else w) or []
        moms = (w.get("moments") if isinstance(w, dict) else None) or []
        for sgm in segs:
            nm = str(sgm.get("name") or "").strip()
            if not nm:
                continue
            try:
                a2 = float(sgm.get("from") or 0.0)
                b2 = float(sgm.get("to") or 0.0)
            except (TypeError, ValueError):
                a2 = b2 = 0.0
            try:
                sr = sgm.get("src") or []
                rw = max(1, int(sr[1]) - int(sr[0]) + 1)
            except (TypeError, ValueError, IndexError):
                rw = 1
            cinfo.append({"n": nm, "d": max(0.0, b2 - a2), "r": rw,
                          "a": a2, "b": b2,
                          "what": str(sgm.get("what") or ""),
                          "quote": str(sgm.get("quote") or ""),
                          "topics": list(sgm.get("topics") or []),
                          "m": sum(1 for mm in moms
                                   if a2 <= float(mm.get("t") or -1) <= b2),
                          "moms": [mm for mm in moms
                                   if a2 <= float(mm.get("t") or -1) <= b2],
                          "g": 0, "gk": Counter()})
    for e in ((hl or {}).get("events") or []):
        tt = e.get("t")
        if not isinstance(tt, (int, float)):
            continue
        for c in cinfo:
            if c["a"] <= float(tt) <= c["b"]:
                c["g"] += 1
                if e.get("kind"):
                    c["gk"][str(e["kind"])] += 1
                break
    ch = sum(c["d"] for c in cinfo) or 1.0
    rt = sum(c["r"] for c in cinfo) or 1
    mg = sum(c["m"] + c["g"] for c in cinfo) or 1
    for c in cinfo:
        c["s"] = (0.45 * c["d"] / ch + 0.30 * c["r"] / rt
                  + 0.25 * (c["m"] + c["g"]) / mg)
    return sorted(cinfo, key=lambda c: -c["s"])


def evidence(base):
    ins = side(base, "ins") or {}
    hl = side(base, "hl") or {}
    if isinstance(hl, list):
        hl = {"events": hl}
    sns = side(base, "sns") or {}
    vis = side(base, "vis") or {}
    stt = side(base, "stt") or {}
    segs = [s for s in (stt.get("segments") or []) if not s.get("nn")]
    game = game_of(base)
    dur = float(ins.get("vdur") or 0.0)
    ranked = chapters_ranked(ins, hl)
    kinds = Counter(str(e.get("kind") or "loud")
                    for e in (hl.get("events") or []) if isinstance(e, dict))
    ocr = [(float(o.get("t") or 0), str(o.get("kind") or ""),
            str(o.get("text") or "")) for o in (sns.get("ocr") or [])]
    places = [str(p.get("name") or "") for p in (vis.get("places") or [])
              if isinstance(p, dict)]
    creatures = [str(c.get("name") or "") for c in (vis.get("creatures") or [])
                 if isinstance(c, dict)]
    names = [str(v) for v in (sns.get("names") or {}).values() if str(v)]
    words = sum(len((s.get("t") or "").split()) for s in segs)
    you = sum(1 for s in segs if s.get("src") == "you")
    return {"base": base, "game": game, "dur": dur, "ins": ins,
            "ranked": ranked, "kinds": kinds, "ocr": ocr,
            "places": places, "creatures": creatures, "names": names,
            "words": words, "lines": len(segs), "you": you,
            "moments": list(ins.get("moments") or []),
            "served_title": str(ins.get("title") or ""),
            "served_summary": str(ins.get("summary") or "")}


# ---------------------------------------------------------------- prompts

T_SYS = ("You name recordings of gaming sessions. Reply with STRICT JSON "
         "and nothing else, in exactly the shape the user asks for.")

SCHEMA_A = {"type": "object",
            "properties": {"title": {"type": "string"},
                           "summary": {"type": "string"}},
            "required": ["title", "summary"]}

SCHEMA_B = {"type": "object",
            "properties": {"title": {"type": "string"},
                           "summary": {"type": "string"},
                           "because": {"type": "array", "maxItems": 4,
                                       "items": {"type": "string"}}},
            "required": ["title", "summary", "because"]}


def prompt_A(ev):
    """lore.py's t_ask, line for line."""
    lines = "\n".join(
        "- %s [%d min, %d lines%s]"
        % (c["n"], int(round(c["d"] / 60.0)), c["r"],
           (", %d marked moments" % (c["m"] + c["g"]))
           if (c["m"] + c["g"]) else "")
        for c in ev["ranked"][:40])
    return (f"These are the chapters of one session of {ev['game']}, "
            f"heaviest first - the bracket says how much of the night "
            f"each one actually was:\n" + lines
            + "\n\nReply with STRICT JSON and nothing else: "
              '{"title": "...", "summary": "one or two sentences"}. '
              "The title names what actually happened, in the session's "
              "own words and names - if it would fit a thousand other "
              "recordings it is wrong. Prefer a chapter near the top of "
              "the list, but a short chapter that is the point of the "
              "night beats a long one that is not. At most nine words, "
              "and it is a name, not a list. Write Arabic words in Arabic "
              "letters. Never name a person unless that name is in the "
              "chapter list above - unheard names are the one "
              "unforgivable error.")


B_SYS = """You name one recorded night of a game for the friend who was there.
The people speak Emirati Gulf Arabic and English mid-sentence; never mention
the language. Reply with STRICT JSON and nothing else."""


def prompt_B(ev, write=None):
    r = ev["ranked"]
    top = r[:14]
    chs = []
    for c in sorted(top, key=lambda c: c["a"]):
        bits = "%s-%s  %s" % (mmss(c["a"]), mmss(c["b"]), c["n"])
        if c["what"]:
            bits += "\n     what: " + c["what"][:180]
        if c["quote"]:
            bits += "\n     said: \"" + c["quote"][:120] + "\""
        gk = ", ".join("%s x%d" % (k, n) for k, n in c["gk"].most_common(4))
        if gk:
            bits += "\n     heard: " + gk
        chs.append(bits)
    moms = []
    for m in sorted(ev["moments"], key=lambda m: -len(str(m.get("why") or "")))[:8]:
        moms.append("%s [%s] %s" % (mmss(m.get("t")), m.get("kind") or "-",
                                    str(m.get("why") or "")[:140]))
    senses = ", ".join("%s x%d" % (k, n) for k, n in ev["kinds"].most_common(8))
    ocr = "; ".join("%s %s \"%s\"" % (mmss(t), k, x) for t, k, x in ev["ocr"][:10])
    body = (f"THE NIGHT: {ev['game']}, {int(ev['dur'] // 60)} minutes, "
            f"{ev['lines']} spoken lines"
            + (f", {len(ev['names'])} named voice(s): " + ", ".join(ev['names'][:5])
               if ev["names"] else "") + ".\n\n"
            "THE CHAPTERS, in order (name / what happened / a real line / what the ears marked):\n"
            + "\n".join("  " + x for x in chs) + "\n\n"
            + ("THE MOMENTS somebody would clip:\n  " + "\n  ".join(moms) + "\n\n"
               if moms else "")
            + (f"THE SENSES over the whole night: {senses}.\n" if senses else "")
            + (f"THE SCREEN printed: {ocr}.\n" if ocr else "")
            + (f"THE EYE saw these places: {'; '.join(ev['places'][:8])}.\n"
               if ev["places"] else "")
            + (f"THE EYE saw: {'; '.join(ev['creatures'][:6])}.\n"
               if ev["creatures"] else "")
            + "\nWRITE:\n" + (write or WRITE_B))
    return body


WRITE_B = (
    "- \"title\": the ONE thing that happened that night, the way the friend who was there would "
    "say it in one breath. An EVENT with a subject and a verb, or a specific named thing - "
    "never a list of topics, never 'X and Y', never 'Session', 'Initial', 'Chat', 'Talk', "
    "'Discussion', 'Gameplay', 'Adventures', 'Struggles'. At most nine words. Use the real "
    "names, places, bosses and words from the evidence above - and ONLY those; a name not "
    "written above must not appear. Arabic in Arabic letters.\n"
    "- \"summary\": two sentences telling what happened, the same way.\n"
    "- \"because\": up to four short quotes or facts copied from the evidence above that "
    "the title rests on.\n"
    "GOOD titles (shape only): \"The goalie finally beats the goat demon\", \"The generator "
    "night nobody survived\", \"Three hours lost to one Rocket League kickoff\", "
    "\"A bachelor party plan takes over Hearthstone\".\n"
    "BAD titles: \"Battles and Minions\", \"Initial Setup and Discord Chat\", "
    "\"Rocket League Session: Boost, Frustration, and Victory\".")

WRITE_C = (
    "- \"title\": what HAPPENED that night, in the narrator's voice - the first line of the "
    "story a friend would tell about it. A subject and a verb, or the one concrete thing that "
    "stood out (a boss, a place, a run, a fight, a phone call, a bet). Not a mood, not a theme, "
    "not a list. It is NEVER a line somebody said - lines go in \"because\", not in the title. "
    "No swearing in the title. Never 'X and Y', never a colon, never 'Session', 'Initial', "
    "'Chat', 'Talk', 'Discussion', 'Gameplay', 'Adventures', 'Struggles', 'Chaos', 'Journey', "
    "'Vibes', 'Shenanigans'. At most nine words. Use only names, places, bosses and words that "
    "appear in the evidence above - a name not written above must not appear. Arabic in Arabic "
    "letters.\n"
    "- \"summary\": two sentences telling what happened, the same way, with the one or two "
    "details that made this night this night.\n"
    "- \"because\": up to four short quotes or facts copied from the evidence above that the "
    "title rests on.\n"
    "GOOD (shape only): \"The goat demon finally goes down\", \"Nobody survives the generator "
    "night\", \"Three hours lost to one kickoff\", \"A bachelor party plan takes over the "
    "Hearthstone table\", \"Fifteen deaths to the same bridge\".\n"
    "BAD: \"Battles and Minions\" (a list), \"Late Game Chaos\" (a mood), \"What a pass!\" "
    "(a quote), \"Rocket League Session: Boost, Frustration, and Victory\" (a colon and a "
    "list).")


def prompt_C(ev):
    return prompt_B(ev, WRITE_C)


# ---- variant D: the app's own ask and guard, lifted from lore.py ----
_APP = {}


def _app():
    """lore.py's _title_evidence / _title_guard, by name, once."""
    if _APP:
        return _APP
    import ast
    import textwrap
    src = io.open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "lore.py"), encoding="utf-8").read()
    ns = {"re": re, "json": json, "os": os}
    for name in ("_TITLE_SWEAR", "_TITLE_MOOD", "_TITLE_STOP"):
        m = re.search(r"^%s = frozenset\(\((.*?)\)\)" % name, src,
                      re.M | re.S)
        ns[name] = frozenset(eval("(" + m.group(1) + ")"))
    m = re.search(r"^_TITLE_WRITE = \((.*?)\)\n_TITLE_SWEAR", src,
                  re.M | re.S)
    ns["_TITLE_WRITE"] = eval("(" + m.group(1) + ")")
    ns["_TITLE_SYS"] = eval("(" + re.search(r"^_TITLE_SYS = \((.*?)\)\n",
                                            src, re.M | re.S).group(1) + ")")
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name in (
                "_title_guard", "_title_evidence"):
            code = textwrap.dedent("\n".join(
                src.splitlines()[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<" + node.name + ">", "exec"), ns)
    _APP.update(ns)
    return _APP


def prompt_D(ev):
    app = _app()
    pack = {"game": ev["game"], "dur": ev["dur"], "lines": ev["lines"],
            "names": ev["names"],
            "ranked": [{"n": c["n"], "a": c["a"], "b": c["b"],
                        "w": c["what"], "q": c["quote"], "gk": dict(c["gk"])}
                       for c in ev["ranked"][:14]],
            "moments": ev["moments"], "kinds": dict(ev["kinds"]),
            "ocr": ev["ocr"], "screen": ev.get("screen") or [],
            "places": ev["places"], "creatures": ev["creatures"]}
    return app["_title_evidence"](pack)


def ask_D(url, ev, temp):
    """The ask, the guard, the one re-ask - as lore.py does it."""
    app = _app()
    said = [c["quote"] for c in ev["ranked"]]
    user = prompt_D(ev)
    got = ask(url, app["_TITLE_SYS"], user, SCHEMA_B, temp, max_tokens=360)
    title = str(got.get("title") or "")
    why = app["_title_guard"](title, said)
    got["guard"] = why
    got["first"] = title
    if why:
        g2 = ask(url, app["_TITLE_SYS"], user + "\n\nYour title \"" + title[:80]
                 + "\" is " + why + ". Name what HAPPENED instead - a subject "
                 "and a verb, in your own words: no quotation, no swearing, "
                 "no colon, no list, no mood word. Same JSON.",
                 SCHEMA_B, temp, max_tokens=360)
        cand = str(g2.get("title") or "")
        got["second"] = cand
        got["_secs"] = (got.get("_secs") or 0) + (g2.get("_secs") or 0)
        if cand and not app["_title_guard"](cand, said):
            got["title"] = cand
            got["summary"] = g2.get("summary") or got.get("summary")
            got["because"] = g2.get("because") or got.get("because")
            got["kept"] = "second"
        else:
            got["kept"] = "first"
    return got


# ------------------------------------------------------------------ model


def ask(url, system, user, schema, temp=0.4, max_tokens=260, timeout=900):
    payload = {"messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}],
               "max_tokens": max_tokens, "temperature": temp,
               "stream": False,
               "chat_template_kwargs": {"enable_thinking": False},
               "response_format": {"type": "json_schema",
                                   "json_schema": {"name": "answer",
                                                   "schema": schema}}}
    req = urllib.request.Request(
        url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    txt = (d.get("choices") or [{}])[0].get("message", {}).get("content", "")
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S).strip()
    usage = d.get("usage") or {}
    try:
        got = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
    except Exception:
        got = {"title": "", "summary": "", "raw": txt[:300]}
    got["_secs"] = round(time.time() - t0, 1)
    got["_tokens"] = usage
    return got


def other_server_running():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq llama-server.exe"],
                             capture_output=True, text=True, timeout=15).stdout
        return "llama-server.exe" in out
    except Exception:
        return False


def game_detected():
    try:
        p = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Lore", "watch.beat")
        d = json.load(io.open(p, encoding="utf-8"))
        return bool(str(d.get("sees") or "").strip())
    except Exception:
        return False


def serve(model, runtime, ngl):
    exe = os.path.join(INSTALL, "ai", runtime, "llama-server.exe")
    if not os.path.isfile(exe):
        raise SystemExit("no llama-server at " + exe)
    if not os.path.isfile(model):
        raise SystemExit("no model at " + model)
    if int(ngl) > 0:
        if other_server_running():
            raise SystemExit("REFUSED: a llama-server is already running - "
                             "one model on the card, ever")
        if game_detected():
            raise SystemExit("REFUSED: LORE sees a game - the card is his")
    cmd = [exe, "-m", model, "--port", str(PORT), "-ngl", str(ngl),
           "-c", "8192", "--no-webui",
           "-t", str(int(os.environ.get("LORE_BAKE_THREADS") or 10))]
    if int(ngl) <= 0:
        cmd += ["-dev", "none"]      # CPU only: the card is never touched
    if "qwen" in os.path.basename(model).lower():
        cmd += ["-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0"]
    # no console window ever, and below normal: his game keeps its cores
    flags = (getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
             | getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        urllib.request.urlopen("http://127.0.0.1:%d/health" % PORT,
                               timeout=2).read()
        raise SystemExit("REFUSED: something already answers on port %d "
                         "- a stale bake server? kill it first" % PORT)
    except SystemExit:
        raise
    except Exception:
        pass
    pr = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, creationflags=flags)
    t0 = time.time()
    while time.time() - t0 < 900:
        if pr.poll() is not None:
            raise SystemExit("the server died at birth")
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/health" % PORT,
                                   timeout=2).read()
            print("server up in %ds: %s (ngl %s)" % (
                time.time() - t0, os.path.basename(model), ngl))
            return pr
        except Exception:
            time.sleep(1)
    pr.terminate()
    raise SystemExit("the server never answered /health")


# ------------------------------------------------------------------ shape

_LISTY = re.compile(r"[,\u060c]|\band\b|&|\+", re.I)
_VERB = re.compile(
    r"\b(beat|beats|dies|died|dying|kills?|killed|wins?|won|loses?|lost|"
    r"escapes?|escaped|fails?|failed|finally|first|last|again|never|can't|"
    r"cannot|tries|trying|finds?|found|survives?|survived|falls?|fell|"
    r"breaks?|broke|gets?|got|goes|went|comes?|came|takes?|took|makes?|made|"
    r"saves?|saved|carries|carried|drops?|dropped|misses|missed|nobody|"
    r"everyone|vs\.?|versus|against|until|before|after|while)\b", re.I)
_GENERIC = re.compile(
    r"\b(session|introduction|gameplay|discussion|conversation|chat|chatting|"
    r"banter|talk|talking|exploration|exploring|adventure|adventures|journey|"
    r"struggles?|challenges?|chaos|fun|friends?|moments?|highlights?|strategy|"
    r"strategies|planning|preparation|intro|initial|early|setup|start|begins?|"
    r"beginning)\b", re.I)


def shape(title, ev):
    t = str(title or "")
    hay = " ".join([ev["game"]] + [c["n"] + " " + c["what"] + " " + c["quote"]
                                   for c in ev["ranked"]]
                   + [str(m.get("why") or "") for m in ev["moments"]]
                   + ev["places"] + ev["creatures"] + ev["names"]
                   + [x for _, _, x in ev["ocr"]]).lower()
    caps = [w for w in re.findall(r"\b[A-Z][a-z']{2,}\b", t)
            if w.lower() not in ("the", "and", "with", "night", "night's")]
    unheard = [w for w in caps if w.lower() not in hay]
    return {"words": len(t.split()), "listy": bool(_LISTY.search(t)),
            "verb": bool(_VERB.search(t)), "generic": bool(_GENERIC.search(t)),
            "unheard": unheard}


# ---------------------------------------------------------------- commands


def cmd_plan(n):
    rows = []
    for f in sorted(os.listdir(TH)):
        if not f.endswith(".ins.json"):
            continue
        base = f[:-9]
        ins = side(base, "ins") or {}
        if not (ins.get("complete") and ins.get("chapters")):
            continue
        stt = side(base, "stt") or {}
        words = sum(len((s.get("t") or "").split())
                    for s in (stt.get("segments") or []) if not s.get("nn"))
        if words < 600:
            continue
        rows.append({"base": base, "game": game_of(base), "words": words,
                     "dur": float(ins.get("vdur") or 0),
                     "n_ch": len(ins.get("chapters") or []),
                     "title": ins.get("title") or ""})
    # spread over games: round-robin, richest first inside a game
    by = {}
    for r in sorted(rows, key=lambda r: -r["words"]):
        by.setdefault(r["game"].lower(), []).append(r)
    plan, i = [], 0
    games = sorted(by, key=lambda g: -len(by[g]))
    while len(plan) < n and any(by.values()):
        g = games[i % len(games)]
        if by[g]:
            plan.append(by[g].pop(0))
        i += 1
        if i > 10 * n:
            break
    p = os.path.join(SCRATCH, "bake_plan.json")
    io.open(p, "w", encoding="utf-8").write(json.dumps(plan, ensure_ascii=False, indent=1))
    print("planned %d nights of %d eligible -> %s" % (len(plan), len(rows), p))
    for r in plan:
        print("  %-28s %5dw %3dch %4dmin | %s" % (r["game"][:28], r["words"],
                                                  r["n_ch"], int(r["dur"] // 60),
                                                  r["title"][:70]))


HARD_LIMIT = 1200      # seconds per night-variant, wall clock


def guarded(fn):
    """fn() on a thread; None past HARD_LIMIT (the caller restarts the
    server - the stuck request is still inside it)."""
    import threading
    box = {}

    def run():
        try:
            box["got"] = fn()
        except Exception as e:
            box["err"] = str(e)[:200]
    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(HARD_LIMIT)
    if th.is_alive():
        return None
    if "err" in box:
        return {"title": "", "summary": "", "raw": "ERR " + box["err"]}
    return box["got"]


def cmd_run(label, model, runtime, url, ngl, variants, n, temp):
    plan = json.load(io.open(os.path.join(SCRATCH, "bake_plan.json"),
                             encoding="utf-8"))[:n]
    pr = None
    if model:
        pr = serve(model, runtime, ngl)
        url = "http://127.0.0.1:%d" % PORT
    out = os.path.join(SCRATCH, "bake_%s.jsonl" % label)
    try:
        for r in plan:
            ev = evidence(r["base"])
            for v in variants:
                if v == "A":
                    fn = lambda: ask(url, T_SYS, prompt_A(ev), SCHEMA_A, temp)
                elif v == "C":
                    fn = lambda: ask(url, B_SYS, prompt_C(ev), SCHEMA_B, temp,
                                     max_tokens=360)
                elif v == "D":
                    fn = lambda: ask_D(url, ev, temp)
                else:
                    fn = lambda: ask(url, B_SYS, prompt_B(ev), SCHEMA_B, temp,
                                     max_tokens=360)
                got = guarded(fn)
                if got is None:
                    print("%-22s %s TIMEOUT after %ds - restarting the server"
                          % (ev["game"][:22], v, HARD_LIMIT))
                    got = {"title": "", "summary": "", "raw": "TIMEOUT",
                           "_secs": HARD_LIMIT}
                    if pr is not None:
                        pr.kill()
                        try:
                            pr.wait(timeout=30)
                        except Exception:
                            pass
                        time.sleep(2)
                        pr = serve(model, runtime, ngl)
                row = {"label": label, "variant": v, "base": r["base"],
                       "game": ev["game"], "title": got.get("title", ""),
                       "guard": got.get("guard"), "first": got.get("first"),
                       "second": got.get("second"), "kept": got.get("kept"),
                       "summary": got.get("summary", ""),
                       "because": got.get("because", []),
                       "secs": got.get("_secs"), "tokens": got.get("_tokens"),
                       "raw": got.get("raw"),
                       "shape": shape(got.get("title", ""), ev)}
                io.open(out, "a", encoding="utf-8").write(
                    json.dumps(row, ensure_ascii=False) + "\n")
                print("%-22s %s %-14s %5.1fs | %s" % (
                    ev["game"][:22], v, label[:14], got.get("_secs") or 0,
                    str(got.get("title", ""))[:80]))
    finally:
        if pr is not None:
            pr.terminate()
            try:
                pr.wait(timeout=30)
            except Exception:
                pr.kill()


def cmd_report():
    rows = []
    for f in sorted(os.listdir(SCRATCH)):
        if f.startswith("bake_") and f.endswith(".jsonl"):
            for ln in io.open(os.path.join(SCRATCH, f), encoding="utf-8"):
                try:
                    rows.append(json.loads(ln))
                except Exception:
                    pass
    plan = json.load(io.open(os.path.join(SCRATCH, "bake_plan.json"),
                             encoding="utf-8"))
    L = ["# Title bake-off", ""]
    tally = {}
    for r in plan:
        ev = evidence(r["base"])
        L.append("## %s — %d min, %d lines (%s)" % (
            ev["game"], int(ev["dur"] // 60), ev["lines"], r["base"]))
        s0 = shape(ev["served_title"], ev)
        L.append("- **served**: %s  `%s`" % (ev["served_title"], _tag(s0)))
        if ev["served_summary"]:
            L.append("  - %s" % ev["served_summary"][:220])
        top = sorted(ev["ranked"], key=lambda c: c["a"])[:6]
        L.append("  - chapters: " + " · ".join(c["n"] for c in top)
                 + (" · …" if len(ev["ranked"]) > 6 else ""))
        for x in [x for x in rows if x["base"] == r["base"]]:
            key = x["label"] + "/" + x["variant"]
            sh = x.get("shape") or {}
            L.append("- **%s**: %s  `%s` (%ss)" % (key, x["title"], _tag(sh),
                                                   x.get("secs")))
            if x.get("summary"):
                L.append("  - %s" % str(x["summary"])[:220])
            if x.get("because"):
                L.append("  - because: " + " | ".join(str(b)[:80]
                                                     for b in x["because"][:4]))
            t = tally.setdefault(key, Counter())
            t["n"] += 1
            t["listy"] += bool(sh.get("listy"))
            t["verb"] += bool(sh.get("verb"))
            t["generic"] += bool(sh.get("generic"))
            t["unheard"] += bool(sh.get("unheard"))
        L.append("")
    L.append("## Shape tally (lower listy/generic/unheard, higher verb = better)")
    L.append("| run | n | list-shaped | event verb | generic word | unheard name |")
    L.append("|---|---|---|---|---|---|")
    srv = Counter()
    for r in plan:
        ev = evidence(r["base"])
        s0 = shape(ev["served_title"], ev)
        srv["n"] += 1
        srv["listy"] += bool(s0["listy"])
        srv["verb"] += bool(s0["verb"])
        srv["generic"] += bool(s0["generic"])
        srv["unheard"] += bool(s0["unheard"])
    for key, t in [("served", srv)] + sorted(tally.items()):
        L.append("| %s | %d | %d | %d | %d | %d |" % (
            key, t["n"], t["listy"], t["verb"], t["generic"], t["unheard"]))
    p = os.path.join(SCRATCH, "BAKE_REPORT.md")
    io.open(p, "w", encoding="utf-8").write("\n".join(L))
    print("report -> " + p)


def _tag(sh):
    bits = []
    if sh.get("listy"):
        bits.append("LIST")
    if sh.get("generic"):
        bits.append("GENERIC")
    if sh.get("verb"):
        bits.append("verb")
    if sh.get("unheard"):
        bits.append("UNHEARD:" + ",".join(sh["unheard"][:3]))
    return " ".join(bits) or "ok"


def _arg(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        return sys.argv[i + 1] if i + 1 < len(sys.argv) else default
    return default


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    c = sys.argv[1]
    if c == "plan":
        cmd_plan(int(_arg("--n", 12)))
    elif c == "run":
        label = sys.argv[2]
        model = _arg("--model")
        if model and not os.path.isabs(model):
            model = os.path.join(MODELS, model)
        cmd_run(label, model, _arg("--runtime", "llama"),
                _arg("--url", "http://127.0.0.1:%d" % PORT),
                int(_arg("--ngl", 99)),
                list(_arg("--variant", "AB")), int(_arg("--n", 99)),
                float(_arg("--temp", 0.4)))
    elif c == "report":
        cmd_report()
    else:
        print(__doc__)
        sys.exit(2)
