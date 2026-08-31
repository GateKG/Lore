# LORE code and AI-output review

**Reviewed:** 2026-09-01  
**Repository state:** `ffeb213` / LORE v3.21  
**Scope:** static review of the repository, with a full pipeline trace and a deep review of inputs, transcription, senses, OCR, vision, description, auditing, search, and user-facing AI answers.  
**Change policy:** no application code, configuration, prompts, or existing documentation was changed. This review file is the only deliverable.

## Executive conclusion

LORE's main AI problem is not simply model quality. It is **unsupported information becoming more authoritative as it travels through the pipeline**.

The system already contains thoughtful safeguards: voice-activity detection, prompt-echo retries, foreign-script checks, structured JSON generation, atomic sidecar writes, line-number-to-timestamp mapping, proper-name checks, and an auditor. Those are real strengths. However, several later stages treat probabilistic outputs as facts:

1. ASR produces transcript lines without usable uncertainty or acoustic evidence.
2. Senses, OCR, and the eye can promote a single model result into a highlight or narrative hint.
3. The describer receives those hints as things already "marked," drops transcript lines when a window is too large, and is still asked to write a continuous story.
4. Generated chapter names become input to the title and summary, so an invention can be repeated and look corroborated.
5. The auditor counts temporal co-occurrence as "agreement," even though the layers are correlated and may all descend from the same mistake.
6. The auditor can automatically rewrite transcripts, strike lines, and regenerate descriptions.

That is an **error-amplification loop**. A better model may reduce its frequency, but it will not remove the underlying failure mode.

The highest-value change is to make LORE an **evidence-first system**:

- observations remain observations;
- generated claims cite exact source IDs;
- every quote, time, name, and event is checked before display;
- uncertain outputs can abstain;
- the auditor proposes changes but does not silently alter source material;
- accuracy is measured on a held-out, human-labeled set before prompt or model changes ship.

I would not make a model upgrade the first project. I would first stop automatic auditor mutations, stop dropping transcript lines, enforce citations, and build a small evaluation set. Those changes will both improve the current output and tell you whether a future model is genuinely better.

## Review boundary and method

This is a static code review, not a live accuracy benchmark. I traced the data flow through the repository and inspected the validation, prompts, schemas, persistence, retry behavior, user-facing rendering, build path, and recent Git history. I did not run the 35+ GB model stack against recordings, and no labeled source recordings were present in the repository. Therefore:

- findings about control flow and missing validation are direct code findings;
- findings about likely hallucination paths are evidence-based design findings;
- actual WER, precision, recall, and hallucination rates still need to be measured on recordings.

LORE has changed very quickly since tag `v2.30`: the current diff is 28,712 insertions and 2,093 deletions, including four new AI workers and roughly 18,000 added backend lines. The recent v3.09-v3.21 history shows many thoughtful, incident-driven fixes. The risk is that fixes are being validated against individual failures rather than a stable regression suite.

## System map

The effective AI flow is:

```text
recording + audio tracks
        |
        +--> loudness/highlights -----------------------+
        |
        +--> VAD --> ASR transcript (.stt) ------------+
        |                                                |
        +--> CLAP/hype/voice/laughter/OCR (.sns) -------+--> describer (.ins)
        |                                                |        |
        +--> selected still frames --> eye (.vis) ------+        |
                                                                 v
                   auditor reads all sidecars (.aud) --> may rewrite .stt/.ins
                                                                 |
                                                                 v
                                             timeline, title, summary,
                                             Ask Video, Ask Library
```

The intentional runtime order appears at `lore.py:19623-19696`: transcription and highlights are separate jobs; during "thinking," senses run first, the eye runs next, the describer follows, and the auditor runs last.

That order is reasonable for enrichment, but it also means an early false positive can influence every later stage.

## Priority findings

| Priority | Finding | Why it affects output |
|---|---|---|
| **P0** | The auditor automatically edits source and derived sidecars | A text-only guess can rewrite the transcript, strike a line, and trigger a new description, multiplying one mistake. |
| **P0** | The describer drops transcript lines to fit fixed 30-minute windows | It is told to cover every line, but it may never receive many of them. It can create a continuous-sounding story across missing evidence. |
| **P0** | Claims are structurally valid but not semantically verified | JSON grammar prevents malformed output; it does not prove that a quote, name, event, or explanation came from the recording. |
| **P0** | There is no reproducible AI evaluation suite | Current improvements cannot be distinguished reliably from regressions or overfitting to the recordings that inspired each fix. |
| **P1** | ASR output has no calibrated confidence, word timestamps, alternatives, or retained evidence | Downstream stages treat every line as equally trustworthy and cannot relisten only where uncertainty is high. |
| **P1** | OCR and vision can promote weak single observations | OCR ignores OCR confidence; the eye interprets sparse stills and a creature result can become a gold mark. |
| **P1** | Auditor "agreement" is temporal presence, not semantic corroboration | Nearby but unrelated words, sounds, frames, and review text count as multiple agreeing layers. |
| **P1** | Generated text is used to validate more generated text | Chapter names feed the final title/summary and are included in the "heard" corpus used by the proper-name guard. |
| **P1** | Ask Video and Ask Library trust model-provided quotes/reasons/times | Outputs are range-checked but not evidence-checked before reaching the UI. |
| **P1** | Sidecar freshness is mostly file mtime | A prompt, model, setting, schema, dependency, or upstream sidecar can change without invalidating downstream output. |
| **P2** | AI settings validation and budget semantics are inconsistent | Invalid AI controls can cross the bridge; zero/invalid budget is documented as blocked in one place but implemented as unlimited. |
| **P2** | Two very large application files, no tests, and many swallowed exceptions | Regression isolation is difficult and optional-stage failures can quietly degrade output quality. |

## Detailed findings

### 1. The auditor can amplify hallucinations instead of containing them

This is the most important issue.

`_audit_one()` says it writes only its own `.aud` file (`lore.py:18095-18104`), but its actual completion path:

- applies fixes to `.stt` (`lore.py:18333-18340`);
- applies strikes to transcript lines;
- refreshes stored explanations;
- applies names;
- re-describes affected windows and regenerates derived review text (`lore.py:18349-18368`).

`_aud_apply_fixes()` directly replaces `sg["t"]` with the model's proposed `heard` value (`lore.py:17906-17980`). It preserves the original in `was`, which is good for recovery, but reversibility does not make an uncertain automatic edit accurate.

The correction gate `_aud_sense()` only rejects a proposal when at least two tokens are unseen and more than half its tokens are unseen (`lore.py:15769-15798`). A fluent but wrong correction made of common words passes. A wrong single proper noun can also pass.

The shortlist `_aud_garble()` is useful for finding odd text, but its evidence is library frequency rather than the audio (`lore.py:15845-15930`). It misses plausible hallucinations composed of common words, long lines, and recurring canned errors. A library of model-generated transcripts is also not ground truth.

**Recommendation:** make the auditor advisory by default.

- Write proposals to `.aud` with `before`, `proposed`, reason, evidence, confidence, and a short playable audio interval.
- Let the user accept, reject, or edit a proposal.
- Only allow automatic correction if it is supported by independent acoustic evidence: for example, two decoding passes agree, or a second ASR model agrees, with stable timestamps and a high calibrated threshold.
- Do not re-describe a window until the correction is accepted.
- Preserve raw ASR output permanently. Treat corrected text as a separate revision, not as replacement truth.
- Measure auditor **net harm**: accepted correction rate, false correction rate, false strike rate, and change in WER before/after audit.

### 2. Auditor agreement is not real agreement

`_aud_says()` marks a layer present when any qualifying item is near a timestamp (`lore.py:16005-16098`):

- any transcript line;
- any sound/OCR event;
- any eye place or creature;
- any review moment or chapter;
- any laugh/scream.

`_aud_condemn()` then calls other present layers `agrees` (`lore.py:16135-16150`). There is no check that they describe the same entity or event. A sentence about a door, a generic cheer tag, and an eye label naming a corridor can count as three witnesses merely because they are nearby.

These layers are also correlated. The review was created from the transcript, senses, and eye. It is not an independent witness to those sources. Counting review text as a vote for its own inputs is circular.

**Recommendation:** replace layer counting with claim-level support.

- Parse or create an atomic claim: `event=win`, `entity=Azazel`, `speaker=Gate`, `quote=X`.
- Require supporting evidence to match the claim, not only its timestamp.
- Record lineage. Evidence derived from another item does not add an independent vote.
- Weight direct sources above derived sources: audio/frame/OCR region > ASR/vision label > description > title/summary.
- Treat missing evidence as `unknown` unless that sensor demonstrably covered the interval and was expected to detect that particular claim.

### 3. The describer silently loses input

Description works in 30-minute windows. When a window is too large, `lore.py:13992-14000` evenly samples transcript segments until the text fits, with a floor of 24 lines. The model is nevertheless instructed to cover every supplied line and return three-to-five continuous stretches.

This creates two problems:

1. Important dialogue may be omitted solely because of sampling position.
2. The model can write a continuous chapter spanning minutes for which it received no words.

The timestamp mapping itself is good: the backend maps cited line IDs back to transcript times rather than trusting invented seconds (`lore.py:14105-14123`). The problem is that the line IDs refer to the downsampled subset, not the complete window.

**Recommendation:** never drop an utterance from a claim-producing pass.

- Build chunks by token count, not a fixed 30-minute clock.
- Break on real pauses/topic boundaries while keeping all segments.
- Use a small overlap and stable global segment IDs.
- If one chunk is still large, summarize only after first extracting cited facts from every subchunk.
- Represent silence/gaps explicitly; do not stretch a chapter across unsent intervals.
- Add a deterministic coverage check: every non-rejected transcript segment is either cited by a chapter, marked `no narrative content`, or left `uncertain`.

### 4. JSON validity is being mistaken for factual validity

The describer uses a JSON schema, which is an excellent reliability measure (`lore.py:12816-12839`, `lore.py:13143-13150`). However:

- `quote` is described in the prompt as required evidence but is optional in the schema;
- no backend check confirms a returned quote exists in the cited segment;
- `what`, `name`, `topics`, and moment `why` are not checked against their cited evidence;
- a valid line number proves only time, not the prose attached to it.

The same distinction applies to the eye schema (`lore.py:14383-14394`) and the question-answer schemas. A grammar guarantees shape, not truth.

**Recommendation:** add semantic validators immediately after parsing.

- Make `quote` and `evidence_ids` required for every description claim.
- Normalize punctuation/spacing and require the quote to be an exact substring of a cited transcript line. Never use fuzzy matching to turn a non-match into a match.
- Require proper nouns to occur in direct transcript/OCR/frame evidence, not in prior generated prose.
- If evidence validation fails, drop the claim or return it as uncertain. Do not ask the model to make the unsupported output sound better.
- Use temperature `0` for extraction and verification. Keep creativity, if desired, in a separate title-writing pass over validated claims only. The describer and auditor currently use temperature `0.4` (`lore.py:13138-13142`, `lore.py:17122-17133`).

### 5. Generated text launders other generated text

The final title and summary are generated from chapter names alone (`lore.py:14220-14246`), not from the underlying quotes or validated claims. An invented chapter detail can therefore become a polished title and summary.

There is a proper-name guard, which is the right idea. But the corpus used to decide whether the final title's names were heard is expanded with the generated chapter names (`lore.py:14256-14264`). A name invented during chapter generation has now become part of the allowed corpus.

**Recommendation:** enforce a one-way evidence hierarchy.

```text
direct audio / frame / OCR region
        -> extracted observation
        -> validated atomic claim
        -> chapter
        -> title and summary
```

Nothing may validate an item above it. Specifically:

- a chapter cannot validate a title name;
- a description cannot validate the eye or transcript it was derived from;
- a title cannot become search evidence;
- generated prose cannot enter the "heard" corpus.

Generate the title and summary from validated claims plus their direct quotes, not from chapter labels alone.

### 6. Speaker names are passed without line-level identity

The describer formats transcript lines as `YOU:` only when the segment source is the user's clean mic (`lore.py:13645-13649`). It does not include the general speaker cluster ID. Later, the prompt supplies mappings such as `speaker 2 = Alice` and says to use the names (`lore.py:14020-14023`).

The model cannot reliably apply that mapping because the transcript line does not say `speaker 2`. This invites speaker-name misattribution.

**Recommendation:** join diarization to transcript segments before generation.

- Add `speaker_id` and optional `speaker_name` directly to each segment.
- Only show a name when cluster confidence and runner-up margin pass calibrated thresholds.
- Otherwise render `unknown speaker` or omit the speaker.
- For overlapping voices, allow multiple/overlap rather than forcing one speaker.
- Keep user-confirmed names separate from auto-assigned names.

### 7. ASR has useful guards but not enough evidence for downstream use

The ASR worker is one of the stronger parts of the AI system. It has:

- Silero VAD before transcription;
- deterministic temperature `0` and repetition controls;
- English/Arabic script restrictions;
- prompt-echo detection and a retry without biasing context;
- second-pass heuristics for Arabic/Arabizi/code-switching;
- a refusal to accept an empty transcript after substantial detected speech;
- atomic output and version metadata.

The main limitations are:

- VAD spans can be concatenated into requests containing up to 28 seconds of speech (`ai/asr_worker.py:55-56`, `ai/asr_worker.py:802-820`). One text result receives the whole group's start/end.
- Output segments contain text, language, and source hints, but no word timestamps, acoustic confidence, alternatives, or stability score (`ai/asr_worker.py:1113-1125`).
- The biasing context strongly asserts a game, Discord friends, casual chat, Emirati Arabic, and English (`lore.py:12223-12227`). This is helpful when true, but it can seed plausible words that were not spoken.
- `_ctx_echo()` only flags outputs with at least seven content words and at least 40% prefix overlap (`ai/asr_worker.py:958-976`). Short or fluent prompt-induced hallucinations can pass.
- Many heuristics are tuned from the same personal library they operate on. That can improve those nights while harming unseen games, audio conditions, or speakers.

**Recommendation:** make uncertainty a first-class output.

- Use shorter pause-aligned chunks, with a small overlap, for difficult or low-speech intervals.
- Keep both biased and unbiased decodes for suspect chunks and score their agreement.
- Retain raw model output, exact audio interval, VAD score/coverage, decoding settings, and alternatives.
- Add word timestamps where supported; otherwise mark timing granularity honestly as segment-level.
- Do not pass a low-confidence transcript line to narrative generation as fact.
- Evaluate on held-out recordings using WER/CER, named-entity error, hallucinated-utterance rate, language/script error, timestamp coverage, and silence false positives.
- Keep corrections the user has confirmed, but never use unverified model corrections as training truth.

### 8. Senses are calibrated on too little data

The sound layer contains thoughtful relative scoring and a room-noise panel. The `ROOM_MARGIN = 3.0` threshold is explicitly derived from two nights (`ai/senses_worker.py:70-75`). Event gating uses median/MAD, negative prompts, and the room margin (`ai/senses_worker.py:112-127`). That is better than trusting the top CLAP label.

Two sessions are not enough to establish a stable threshold across games, microphones, Discord mixes, music, and room conditions. The stored event probability `p` is a relative score, not a calibrated probability.

**Recommendation:**

- Build a labeled held-out sound set and measure per-label precision/recall.
- Optimize for low false-positive rate because false events become narrative seeds.
- Preserve the top label, runner-up, room score, negative score, margin, and threshold version.
- Add `unknown` when no label clearly wins.
- Calibrate per game only after there are enough labeled examples; otherwise use a global conservative gate.
- Do not describe `p` as confidence until it has been calibrated against human labels.

### 9. OCR ignores confidence and samples circularly

The OCR worker joins all returned text and searches broad event regexes without using OCR confidence (`ai/ocr_worker.py:79-91`). It samples around existing gold marks and chapter starts, as its own header explains. This means:

- low-confidence OCR can become an event;
- broad text such as `#1`, `FELLED`, or boss-like words can create false gold moments;
- sampling around already selected events reinforces prior choices instead of providing independent coverage.

**Recommendation:**

- Retain bounding box, recognized text, OCR confidence, frame time, and crop identity.
- Require a minimum OCR score and two-of-three persistence across adjacent frames.
- Use game-specific HUD crops where possible.
- Separate independent periodic sampling from event-focused sampling.
- Validate event phrases against a per-game pack; unknown text remains searchable OCR, not a gold event.
- Never convert one OCR regex hit directly into narrative truth.

### 10. The eye over-interprets sparse still frames

The eye prompt correctly tells the model to say `none` when uncertain (`lore.py:14365-14379`). But it still asks one still frame for a place, creature, and what is being done. A static frame is often insufficient to infer an action. Frame selection is partly based on existing gold, chapters, and senses, so it is not fully independent. A creature result can be copied into the gold timeline (`lore.py:14840-14913`).

**Recommendation:**

- Show a small temporal bundle: before, at, and after the timestamp.
- Separate visible facts (`object`, `screen text`, `scene`) from temporal inference (`doing`).
- Require repeated consistency or OCR support before naming a boss/place/proper noun.
- Store `unknown` and an evidence score rather than treating every nonempty field as a sighting.
- Do not promote a single vision answer directly to gold. Require confirmation or keep it as a low-confidence visual hint.
- Reserve part of the frame budget for uniform coverage so highlight-driven selection does not become self-confirming.

### 11. Ask Video and Ask Library need evidence validation

`ask_video()` checks that a path is safe and a question is nonempty, retrieves matching and sampled transcript lines, then trusts the model's quote and time (`lore.py:21587-21663`). Returned times are clamped to nonnegative values, but they are not snapped to a source segment, and quotes are not checked against the transcript.

`ask_library()` validates only that a returned row index is in range (`lore.py:21769-21808`). It often searches generated titles and summaries, so narrative hallucinations can also affect retrieval.

**Recommendation:**

- Cap question length and normalize/control characters at the bridge.
- Retrieve source IDs, not display strings.
- Require every answer clause to cite one or more source IDs.
- Exact-check quotes against the transcript and derive time from the matched segment. Ignore model-provided time when direct evidence exists.
- If a quote does not match, remove the hit. If the answer then has no evidence, return "the recording does not establish that."
- Prefer direct transcript/OCR evidence to generated title/summary evidence.
- Label search results by provenance: `said`, `shown on screen`, `vision inference`, or `AI summary`.
- Put transcript and library text inside a clear data envelope and tell the model that instructions occurring inside those records are untrusted content. This reduces prompt-injection behavior from recorded speech or on-screen text.

### 12. Sidecar freshness is too weak for an AI dependency graph

`_ai_sidecar_fresh()` considers a sidecar fresh when it exists and is newer than the video (`lore.py:11309-11320`). Some layers also have generation/version logic, which is helpful, but mtime alone cannot represent the real dependency graph.

A result may be stale when any of these changes:

- model or model quantization;
- worker code;
- prompt or JSON schema;
- decoding settings;
- game pack or speaker-name mapping;
- upstream transcript/senses/vision sidecar;
- source audio-track mapping;
- user correction.

**Recommendation:** put a reproducible fingerprint in every sidecar.

```json
{
  "schema_version": 4,
  "stage_version": "asr-reader-3",
  "source": {"video_sha256": "...", "track_map_sha256": "..."},
  "inputs": {"stt_sha256": "...", "sns_sha256": "..."},
  "model": {"name": "...", "file_sha256": "..."},
  "runtime": {"worker_git": "ffeb213", "dependency_lock": "..."},
  "generation": {"prompt_version": 7, "temperature": 0},
  "created_at": "2026-09-01T00:00:00Z"
}
```

Recompute a stage only when its dependency fingerprint changes. This is more accurate than rebuilding everything and safer than retaining stale derived claims.

### 13. AI inputs need a complete schema

`_sanitize_settings()` clamps several recorder values and validates a few enums (`lore.py:644-688`), but key AI values such as `eye_looks`, `ai_budget_cents`, `ai_spent_cents`, and `claude_model` are not covered there.

The budget logic is internally inconsistent:

- defaults say zero means no ceiling (`lore.py:88-90`);
- `_ai_budget()` says zero means never spend automatically (`lore.py:12472-12477`);
- `_ai_spend_room()` implements zero or negative as unlimited (`lore.py:12480-12490`);
- invalid budget input falls back to zero and therefore becomes unlimited;
- `_claude()` selects the estimated cost kind by looking up a nonexistent `deep` model key (`lore.py:12512-12515`), so its pre-request estimate can be wrong.

Cloud use is currently narrow: `_claude()` is only called for last-resort game naming (`lore.py:9848-9869`). Still, this is a boundary that should be made correct before new cloud features use it.

**Recommendation:**

- Validate every persisted setting with type, range, enum, and default.
- Choose one explicit budget meaning. Safer: `null = no configured budget`, `0 = no spending`, positive = hard ceiling. Avoid overloading zero.
- Reject nonnumeric and negative values rather than converting them to unlimited.
- Estimate cost by the actual selected model and reserve the estimate before a request.
- Expose a separate, explicit `allow_cloud` setting.

### 14. Failure handling is resilient but too quiet

`lore.py` contains 759 `except Exception` occurrences and 429 standalone `pass` statements. Many are intentional fail-open boundaries for optional features, and the job wrapper does log uncaught worker crashes. Even so, this scale makes it difficult to distinguish:

- no evidence found;
- feature unavailable;
- invalid sidecar;
- model timeout;
- model returned invalid semantics;
- code defect.

**Recommendation:** every stage should return a structured result:

```text
status: success | no_evidence | uncertain | unavailable | invalid_output | failed | aborted
error_code: stable machine-readable code
message: short user-facing explanation
metrics: duration, items examined, items accepted/rejected
provenance: stage/model/input fingerprint
```

Catch expected exception types locally. At broad process boundaries, log the full traceback plus stage and recording ID. Do not turn invalid output into an empty success.

### 15. There is no test or evaluation safety net

No test/spec files were found. `lore.py` is about 26,700 lines and `ui.html` about 13,800 lines, with the entire backend and frontend intentionally kept in those two files. That makes cross-stage regression especially likely.

The problem is larger than traditional unit testing: AI accuracy requires a labeled evaluation set.

**Recommendation:** add both deterministic tests and model evaluations.

Deterministic tests should cover:

- sidecar schema validation and migration;
- mtime/hash invalidation;
- path containment;
- Arabic/Latin/script and prompt-echo heuristics;
- transcript chunk coverage and overlap;
- exact quote validation;
- proper-name provenance;
- speaker-line joins;
- audit proposal/application/undo behavior;
- Ask result source and timestamp validation;
- representative UI rendering with hostile/special-character AI text.

Model evaluations should run separately because they are slower and hardware-dependent.

### 16. Build and privacy documentation are inconsistent

The README says the application is fully offline and makes no network calls except Discord (`README.md:28-33`). The code also downloads models/runtimes from Hugging Face, Zenodo, and GitHub (`lore.py:11376-11482`), and has an Anthropic API path for last-resort game naming (`lore.py:12423`, `lore.py:9848-9869`). The behavior may be user-triggered and legitimate, but the documentation should distinguish runtime inference from downloads and optional cloud calls.

`CURRENT-BUILD.md` says v3.18 and commit `6b6fc46`, while the repository and installer are v3.21 (`CURRENT-BUILD.md:7-11`). The README says this generated report cannot quietly go stale (`README.md:62-65`). It did.

The build report counts the entire source `ai` directory as "what ships" (`tools/build_report.py:105-119`), while `build.bat` explicitly excludes model/runtime directories and selectively copies workers/vendor folders plus an existing `ai/venv` (`build.bat:117-140`). The worker environment is not reproducible from the root `requirements-lock.txt`.

**Recommendation:**

- Document three modes clearly: local inference, network model download, and optional cloud API.
- Gate external requests behind explicit UI consent and log the destination without secrets.
- Generate the build report from the staged installer tree, not the source tree.
- Make stale build metadata fail CI/build verification.
- Add a pinned worker lockfile and a scripted worker-environment build. Shipping a hand-built venv makes model behavior difficult to reproduce.

## What is already strong

The review should not erase the solid engineering already present:

- Library file operations go through a containment check using `os.path.commonpath` (`lore.py:23905-23915`).
- The media server binds to `127.0.0.1` and uses a random per-launch token (`lore.py:21042-21144`).
- Discord upload restricts the destination host (`lore.py:7862-7864`).
- Many state and sidecar writes use temp files plus `os.replace`, reducing torn writes.
- AI workers are abortable and scheduled around game activity/GPU ownership.
- ASR has unusually thoughtful code-switching and prompt-echo defenses.
- The describer maps cited line IDs to real transcript times rather than trusting model timestamps.
- Structured generation is already used for description and vision.
- The UI generally escapes AI text or assigns it with `textContent`; the main review rendering uses `esc()` (`ui.html:11059-11070`).
- Originals are retained for at least several auditor mutations, making recovery possible.

These mechanisms are good foundations. The next step is to connect them with explicit provenance, semantic validation, and measurable quality gates.

## Recommended target design: an evidence ledger

Instead of allowing each stage to pass free-form prose to the next, give every observation and claim a stable identity.

```json
{
  "claim_id": "claim:session123:0042",
  "kind": "event",
  "text": "The group defeated the boss",
  "time": {"start_ms": 481200, "end_ms": 486900},
  "evidence": [
    {"id": "stt:seg:188", "type": "transcript", "quote": "finally, he's down"},
    {"id": "ocr:frame:481.8", "type": "screen_text", "quote": "BOSS DEFEATED"}
  ],
  "lineage": ["stt:seg:188", "ocr:frame:481.8"],
  "certainty": "supported",
  "confidence": null,
  "provenance": {"stage": "claim-extractor-v1", "input_hash": "..."}
}
```

Important rules:

- `confidence: null` is better than an invented probability.
- `supported` means the evidence validator passed; it does not mean philosophically certain.
- A derived item lists lineage so it cannot be counted as independent support for its own sources.
- User corrections are a separate evidence type with the highest display authority, but the original remains accessible.
- Titles and summaries cite claim IDs internally even if the UI shows clean prose.

## Evaluation plan

### Build a held-out corpus

Start small but representative. Freeze a set of short clips that are not used for prompt tuning:

- clear English speech;
- clear Gulf Arabic;
- code-switching within a sentence;
- overlapping Discord voices;
- clean mic plus mixed system audio;
- silence, music-only, game dialogue, and room hum;
- dark/fast-moving scenes and stable HUD scenes;
- positive and negative OCR events;
- sessions with no meaningful event, where abstention is correct.

Human-label the exact words, speakers where knowable, visible text, visible entities, event times, and which narrative claims are supported. Keep a separate development set for tuning and never tune on the held-out set.

### Measure each stage

| Stage | Minimum metrics |
|---|---|
| ASR | WER, Arabic CER, named-entity error, hallucinated-utterance rate, silence false-positive rate, timestamp coverage |
| Speaker | assignment accuracy, unknown/abstain rate, overlap handling, false-name rate |
| Sound | per-label precision/recall, false events per hour, room-noise false-positive rate |
| OCR | text precision, event precision/recall, persistence-check rejection rate |
| Eye | entity/place precision, unsupported proper-noun rate, abstention rate |
| Description | atomic-claim precision, exact-quote validity, proper-name provenance, segment coverage, unsupported claim rate |
| Auditor | proposal precision, false strike rate, accepted/rejected ratio, net WER/claim-precision change |
| Ask | answer support rate, quote validity, timestamp validity, correct abstention rate |

### Add release gates

Every model, prompt, heuristic, or threshold change should produce a before/after report. At minimum:

- no regression in direct-source metrics;
- 100% of displayed quotes match stored source evidence;
- 100% of generated proper nouns have direct provenance or are visibly marked uncertain;
- no automatic auditor change without its configured evidence threshold;
- no chapter silently spans omitted transcript input;
- stale dependency fingerprints trigger recomputation or a visible stale state.

## Implementation order

### P0: stop the system from making its own errors authoritative

1. Disable automatic transcript strikes/corrections and automatic re-description; retain proposals in `.aud`.
2. Stop downsampling description windows; use token-bounded, all-line chunks.
3. Require and validate evidence IDs and exact quotes for every chapter/moment.
4. Validate proper nouns against direct evidence only.
5. Create the first held-out corpus and record a v3.21 baseline.

### P1: make uncertainty and provenance visible

1. Version and validate sidecar schemas.
2. Add dependency/model/prompt hashes.
3. Retain ASR alternatives and acoustic intervals.
4. Add OCR confidence/persistence and multi-frame vision checks.
5. Join speaker IDs directly to transcript segments.
6. Validate Ask quotes, source IDs, and timestamps before returning them.
7. Show `direct`, `inferred`, and `uncertain` badges in the UI, with a click-through to evidence.

### P2: make future improvement safe and reproducible

1. Add deterministic unit/integration tests.
2. Add the slow AI evaluation runner and baseline reports.
3. Split `lore.py` gradually along existing sidecar boundaries: capture, library, AI scheduler, ASR orchestration, senses, vision, description, audit, and bridge.
4. Split the frontend by view/component while keeping a simple build if that is a product goal.
5. Replace broad silent catches with structured stage statuses.
6. Make worker dependencies and build reports reproducible.
7. Only then compare model or quantization upgrades using the same frozen evaluation set.

## Practical product changes that would improve trust

- Add a **Literal / Story** control. Literal mode uses only validated claims and direct quotes; Story mode may write a nicer title but never adds facts.
- Let the user click any title, chapter, moment, answer, or correction to open its transcript line, audio interval, OCR crop, or frame bundle.
- Show an `uncertain` badge instead of forcing a label.
- Provide a corrections inbox rather than silently applying auditor changes.
- Capture simple feedback: correct, wrong, wrong speaker, wrong name, wrong time, not in recording. Store it as evaluation data, not immediately as automatic truth.
- Make “no reliable description” an acceptable result. Honest abstention is better than a polished hallucination.

## Final assessment

LORE has a strong product idea and much more defensive AI code than many personal projects. The code comments show that real failures have been investigated carefully. The current weakness is that those fixes are mostly local heuristics inside a pipeline that still lacks a strict definition of evidence.

The fastest path to visibly better output is:

1. **auditor proposes, user approves;**
2. **no transcript lines are dropped;**
3. **every claim cites evidence and every citation is checked;**
4. **proper nouns can only come from direct evidence;**
5. **quality changes are measured on a frozen held-out set.**

Once those are in place, model selection becomes a controlled optimization instead of guesswork. Without them, a stronger model may write more convincing hallucinations and the rest of the pipeline may still promote them as fact.
