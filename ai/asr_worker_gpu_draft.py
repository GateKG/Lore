# -*- coding: utf-8 -*-
"""DRAFT — LORE's transcriber with an OPTIONAL GPU (llama.cpp GGUF) path.

This is a COPY of asr_worker.py for the Qwen3-ASR GGUF A/B evaluation.
The real worker is untouched. Do not wire this into the app until the
A/B verdict (see asr-gguf-ab.html) says the GGUF path is good enough.

    asr_worker_gpu_draft.py <input.wav> <output.json>

Env flags (all optional — without them this behaves exactly like the
production worker, CPU transformers path):

    LORE_ASR_GGUF=1                          route ask() to a llama-server
    LORE_ASR_SERVER=http://127.0.0.1:8911    where that server listens

The server is expected to be llama.cpp (build >= b9173 — earlier builds
loop on ASR) serving the official GGUF:

    llama-server -m Qwen3-ASR-1.7B-bf16.gguf \
                 --mmproj mmproj-Qwen3-ASR-1.7B-bf16.gguf \
                 -ngl 99 --port 8911 --host 127.0.0.1

Everything else — Silero VAD, utterance grouping, the language leash,
progress files, output shape — is identical to the production worker, so
the app cannot tell which engine produced the json (except for the
"engine" field).
"""
import base64
import io
import json
import os
import re
import sys
import urllib.request

MODEL = os.environ.get("LORE_ASR_MODEL", "Qwen/Qwen3-ASR-1.7B-hf")
CHUNK_S = 28          # at most this much SPEECH per request
GROUP_GAP_S = 0.8     # speech separated by less than this is one utterance

USE_GGUF = (os.environ.get("LORE_ASR_GGUF") or "").strip() in ("1", "true", "yes")
SERVER = (os.environ.get("LORE_ASR_SERVER") or "http://127.0.0.1:8911").rstrip("/")


def main(src, dst):
    import numpy as np
    import soundfile as sf
    import torch
    from silero_vad import get_speech_timestamps, load_silero_vad

    # HOW MUCH OF THE MACHINE THIS MAY TAKE, AND IT CAN CHANGE ITS MIND.
    # (Only matters for the CPU path; the GPU path burns almost no CPU.)
    ctl_path = src + ".ctl"
    default_threads = max(2, (os.cpu_count() or 8) - 4)

    def wanted_threads():
        try:
            with open(ctl_path, encoding="utf-8") as fh:
                n = int(json.load(fh).get("threads") or 0)
            if n > 0:
                return max(1, min(n, os.cpu_count() or n))
        except Exception:
            pass
        try:
            return max(1, int(os.environ.get("LORE_ASR_THREADS") or 0)) \
                if os.environ.get("LORE_ASR_THREADS") else default_threads
        except ValueError:
            return default_threads

    have_threads = [0]

    def apply_threads():
        n = wanted_threads()
        if n != have_threads[0]:
            torch.set_num_threads(n)
            have_threads[0] = n
        return n

    apply_threads()

    prog_path = src + ".prog"

    def say_progress(done, total, secs_done, secs_total):
        try:
            tmp = prog_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"done": done, "total": total,
                           "audio_done": round(secs_done, 1),
                           "audio_total": round(secs_total, 1),
                           "threads": have_threads[0]}, fh)
            os.replace(tmp, prog_path)
        except Exception:
            pass
    a, sr = sf.read(src, dtype="float32")
    if a.ndim > 1:
        a = a.mean(axis=1)

    say_progress(0, 0, 0.0, len(a) / float(sr))    # "started, finding speech"
    spans = get_speech_timestamps(torch.from_numpy(a), load_silero_vad(),
                                  sampling_rate=sr,
                                  min_silence_duration_ms=300,
                                  max_speech_duration_s=CHUNK_S,
                                  speech_pad_ms=200)
    engine = "qwen3-asr-gguf" if USE_GGUF else "qwen3-asr"
    if not spans:
        json.dump({"segments": [], "model": MODEL, "engine": engine},
                  open(dst, "w", encoding="utf-8"))
        say_progress(0, 0, 0.0, 0.0)
        return 0

    # group neighbouring speech into requests, remembering the REAL times so
    # the transcript still lines up with the video
    groups, cur = [], None
    for s in spans:
        if cur and (s["start"] - cur["end"]) / sr <= GROUP_GAP_S \
                and (cur["len"] + s["end"] - s["start"]) <= sr * CHUNK_S:
            cur["parts"].append(a[s["start"]:s["end"]])
            cur["len"] += s["end"] - s["start"]
            cur["end"] = s["end"]
        else:
            if cur:
                groups.append(cur)
            cur = {"parts": [a[s["start"]:s["end"]], ], "start": s["start"],
                   "end": s["end"], "len": s["end"] - s["start"]}
    if cur:
        groups.append(cur)

    # WHAT THIS AUDIO IS — same free-text biasing context as production.
    ctx = (os.environ.get("LORE_ASR_CONTEXT") or "").strip() or None

    if USE_GGUF:
        # ---- GPU path: llama-server (llama.cpp mtmd) --------------------
        # Mirrors the HF processor exactly: context is the system message,
        # the user turn is the audio alone, and forcing a language is done
        # by prefilling the assistant turn with "language <Name><asr_text>"
        # (llama-server continues a trailing assistant message).
        def ask(audio, language):
            buf = io.BytesIO()
            sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            msgs = []
            if ctx:
                msgs.append({"role": "system", "content": ctx})
            msgs.append({"role": "user", "content": [
                {"type": "input_audio",
                 "input_audio": {"data": b64, "format": "wav"}}]})
            if language:
                msgs.append({"role": "assistant",
                             "content": "language %s<asr_text>"
                                        % language.capitalize()})
            body = {"messages": msgs, "temperature": 0, "max_tokens": 440,
                    "repeat_penalty": 1.15}
            req = urllib.request.Request(
                SERVER + "/v1/chat/completions",
                json.dumps(body).encode("utf-8"),
                {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as resp:
                raw = json.load(resp)["choices"][0]["message"]["content"] or ""
            if "<asr_text>" in raw:
                lang = (re.search(r"language\s+([A-Za-z]+)\s*<asr_text>", raw)
                        or [None, ""])[1]
                m = re.search(r"<asr_text>(.*)", raw, re.S)
                return (m.group(1) if m else raw).strip(), lang.lower()
            # prefilled reply: the server answered with the bare
            # transcription (the prefix lived in the prefill)
            return raw.strip(), (language or "").lower()
    else:
        # ---- CPU path: identical to production asr_worker.py ------------
        from transformers import (Qwen3ASRForConditionalGeneration,
                                  Qwen3ASRProcessor)
        try:
            proc = Qwen3ASRProcessor.from_pretrained(
                MODEL, local_files_only=True)
            mdl = Qwen3ASRForConditionalGeneration.from_pretrained(
                MODEL, dtype=torch.float32, local_files_only=True).eval()
        except Exception:
            proc = Qwen3ASRProcessor.from_pretrained(MODEL)
            mdl = Qwen3ASRForConditionalGeneration.from_pretrained(
                MODEL, dtype=torch.float32).eval()

        def ask(audio, language):
            inp = proc.apply_transcription_request(
                audio=audio, language=language, prompt=ctx, sampling_rate=sr,
                return_tensors="pt")
            with torch.no_grad():
                ids = mdl.generate(**inp, max_new_tokens=440,
                                   repetition_penalty=1.15,
                                   no_repeat_ngram_size=8)
            raw = proc.batch_decode(ids, skip_special_tokens=True)[0]
            lang = (re.search(r"language\s+([A-Za-z]+)\s*<asr_text>", raw)
                    or [None, ""])[1]
            m = re.search(r"<asr_text>(.*)", raw, re.S)
            return (m.group(1) if m else raw).strip(), lang.lower()

    # THESE TWO ARE THE ONLY LANGUAGES IN THIS HOUSE.
    KEEP = ("english", "arabic")
    speech_total = sum(g["len"] for g in groups) / float(sr)
    speech_done = 0.0
    out, last = [], "english"
    for i, g in enumerate(groups):
        apply_threads()
        audio = np.concatenate(g["parts"])
        if len(audio) < sr * 0.4:
            continue
        txt, lang = ask(audio, None)
        if lang and lang not in KEEP:
            txt, lang = ask(audio, last)
        if lang in KEEP:
            last = lang
        if txt:
            out.append({"a": int(g["start"] / sr * 1000),
                        "b": int(g["end"] / sr * 1000), "t": txt,
                        "lang": lang or last})
        speech_done += g["len"] / float(sr)
        say_progress(i + 1, len(groups), speech_done, speech_total)

    json.dump({"segments": out, "model": MODEL, "engine": engine},
              open(dst, "w", encoding="utf-8"), ensure_ascii=False)
    say_progress(len(groups), len(groups), speech_total, speech_total)
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: asr_worker_gpu_draft.py <in.wav> <out.json>",
              file=sys.stderr)
        sys.exit(2)
    try:
        sys.exit(main(sys.argv[1], sys.argv[2]))
    except Exception as e:
        print(f"ASR_WORKER_FAILED {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
