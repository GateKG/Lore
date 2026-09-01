# LORE v3.24 external review

*(Publication note: name examples were synthesized to fiction before this file entered the public repo - same skeleton properties, no real tokens.)* — high-value findings only

**Reviewed:** 2026-09-01  
**Revision:** `d54cbc4` (`LORE v3.24 - the auditor's ear earns its vote`)  
**Scope:** current checkout, the v3.24 delta, the committed QA roster, and the AI path from transcript evidence through description, audit mutation, and Ask output.  
**Change policy followed:** no product code or data was changed. This report is the only added file. `D:\Records` was not touched and no live model port was contacted.

## Bottom line

v3.24 is a meaningful improvement, not a cosmetic response to the previous review. The Ask verification changes work, Arabic quote recovery works, refused corrections now leave an automatic trace, and readable multi-word re-listens can prevent a destructive noise strike.

I would still not call the auditor's mutation boundary safe enough yet. Two deterministic holes remain in the new gates:

1. An unrelated correction can pass because it shares one generic word such as **“the”** with the re-listen.
2. A one-word re-listen can exactly repeat the transcript and still be replaced with `[unintelligible]` if the model votes `noise`.

Those are the only new product recommendations I am elevating. They directly affect hallucination and loss of real input. They do not require manual review, an approval inbox, a model change, or a new architecture.

The QA addition is valuable, but its current runner is not reproducibly green here and one recorder scenario tests stale, reimplemented code while calling it “verbatim.” Those are test-confidence defects, not evidence that the current recorder is broken.

## Priority findings

| Priority | Finding | Concrete effect |
|---|---|---|
| **P0** | Any shared token is treated as audio agreement | A fluent library-plausible hallucination can mutate the transcript when its only overlap with the ear is a stopword. |
| **P0** | Exact one-word ear agreement does not veto `noise` | A real name, command, or short response can be banked away as `[unintelligible]` even though the re-listen repeated it. |
| **P1 QA** | Recorder scenario simulates obsolete production logic | The suite reports an “ACTIVE” finding that v3.24 production already fixed, weakening trust in the test oracle. |
| **P1 QA** | The documented full runner does not own its Python environment | `qa\run_all.bat` fails `micheal` on this checkout because its selected Python lacks `pyaudiowpatch`. |

## P0-1 — “shares ground with the ear” currently means “shares any 3-character token”

### Evidence

The correction gate builds two token sets and allows the correction whenever their intersection is non-empty:

- [`lore.py` lines 17357–17371](lore.py#L17357)
- `_et` and `_ht` include every Latin-normalized token of length three or more.
- There is no stopword removal, information score, overlap ratio, or minimum content-anchor count.
- `_aud_ear_agrees()` is only consulted when the exact-token intersection is empty.

The comment says **“distinctive token,”** but the implementation does not calculate distinctiveness.

I exercised the live `_aud_parse()` function with the current v3.24 code and a vocabulary in which all proposal words are established:

```text
ear:       "get behind the door now"
proposal:  "the sniper boss"
overlap:   "the" only
result:    correction accepted (fix count = 1)
```

This gets through both existing gates:

1. `_aud_sense()` says the proposal is plausible language because all its words occur elsewhere in the library.
2. The exact set intersection contains `the`, so the audio-agreement refusal never runs.

That distinction matters: **library plausibility answers “could someone have said this?”; it does not answer “did this recording say it?”** The present code lets the first question substitute for the second after one generic overlap.

### Automatic fix direction

Keep the existing fail-closed behavior—refuse the mutation, preserve the current transcript, write `unclear` plus the reason—but replace “any shared token” with a content-agreement rule.

A safe immediate rule is:

- Ignore bilingual stopwords and very high-frequency library terms as anchors.
- For a multi-word proposal, require either:
  - at least two content-token/skeleton anchors, or
  - one strong rare anchor plus a meaningful proposal-to-ear overlap ratio.
- For a one-word proposal, require whole-utterance token/skeleton/phonetic agreement, not substring agreement with a longer sentence.
- Continue using the consonant skeleton fallback for Arabic/Latin equivalents such as `Rastin` / `راستن`.

The exact thresholds should be replayed against the existing historical repair set. The important invariant is simpler: **a stopword alone must never authorize a transcript mutation.**

### Regression cases to add

```text
REJECT  ear="get behind the door now"
        fix="the sniper boss"                 # only "the" overlaps

REJECT  ear=<Arabic phrase>
        fix=<unrelated fluent phrase sharing only an Arabic stopword>

ACCEPT  ear="get behind the door now"
        fix="get behind door"                 # multiple content anchors

ACCEPT  ear="راستن"
        fix="Rastin"                          # whole-name skeleton agreement
```

The existing C1 test in [`qa/codex324test.py` lines 43–56](qa/codex324test.py#L43) proves zero overlap is refused, but it does not test generic-only overlap.

## P0-2 — an exact one-word re-listen can still be struck as noise

### Evidence

The v3.24 noise veto requires all of the following:

- `_aud_sense()` passes;
- at least two word tokens exist;
- no token is unknown;
- no CJK static appears.

See [`lore.py` lines 17279–17306](lore.py#L17279).

The two-token rule has no exception for direct agreement between the audio re-listen and the transcript. I exercised the live function with `Vontrelle` present in the test vocabulary:

```text
transcript: "Vontrelle"
ear:        "Vontrelle"
model vote: noise
result:     verdict remains "noise"
```

That verdict is not merely cosmetic. `_aud_apply_strikes()` consumes every `noise` row ([`lore.py` lines 18061–18072](lore.py#L18061)). Its readable-sentence splitter refuses a single-part line ([`lore.py` lines 17941–17944](lore.py#L17941)), so the line takes the full-strike branch and becomes `[unintelligible]` ([`lore.py` lines 18119–18134](lore.py#L18119)). The original remains banked under `was`, which is good reversibility, but no later audit re-litigates an `nn` strike automatically.

This is exactly the class most likely to contain valuable rare input: names, places, “yes,” “no,” item names, and short commands. Requiring two tokens is a reasonable defense against a random one-word re-listen, but it should not overrule **exact repeated evidence**.

### Automatic fix direction

Keep the current two-token readability veto as the broad rule, then add a narrower agreement veto before it:

- If a non-junk ear is a whole-token/skeleton match for the current transcript or standing text, downgrade `noise` to `unclear` even when it is one token.
- Do not preserve an unrelated one-word ear merely because it is a known word.
- For a cross-script name, use the existing skeleton/phonetic comparator.
- Mark the row `ear_kept` so the current fresh-reconsideration behavior remains intact.

This preserves hands-off operation: matching evidence keeps the line automatically; disagreement can still strike automatically.

### Regression cases to add

```text
KEEP    text="Vontrelle"  ear="Vontrelle"  vote=noise
KEEP    text="Rastin"     ear="راستن"       vote=noise
STRIKE  text="Vontrelle"  ear="door"        vote=noise
STRIKE  text="Vontrelle"  ear_junk=true      vote=noise
```

The current W1 test explicitly locks in the unsafe broad outcome—“a single-token ear does not veto a strike”—at [`qa/codex324test.py` lines 185–188](qa/codex324test.py#L185). Do not make every single token authoritative; replace that assertion with the direct-agreement exception above.

## P1 QA — the recorder “ACTIVE finding” is stale, not active

The committed recorder scenario says its `active_gone_poll()` is a **“VERBATIM replica”** of production and simulates this old behavior:

```text
missing from two raw process walks -> stop and save
```

See [`qa/rectests/recorder_scenarios.py` lines 173–184](qa/rectests/recorder_scenarios.py#L173) and the reported finding at [lines 352–364](qa/rectests/recorder_scenarios.py#L352).

That is no longer the current production behavior:

- `_looks_gone()` requires a trustworthy process walk, the process to be absent, and no matching window: [`lore.py` lines 887–899](lore.py#L887).
- The active recording path calls `_looks_gone()` and requires three consecutive positive polls: [`lore.py` lines 9147–9155](lore.py#L9147).

So the suite currently prints:

```text
FINDING ACTIVE gone check ... 2 untrustworthy walks STOP a live recording
```

while the live v3.24 code refuses those walks. The stale line reference `8641` now points to `_apply_track_act`, another clear sign the oracle drifted.

There are two test-quality problems here:

1. The README says outcome tests use real functions and **never reimplement** production behavior ([`qa/README.md` lines 41–49](qa/README.md#L41)); this scenario reimplements the old branch.
2. `finding()` counts a demonstrated defect as an `ok`, so a known live defect could still leave the suite green ([`recorder_scenarios.py` lines 197–204](qa/rectests/recorder_scenarios.py#L197)).

Recommended QA-only correction:

- Drive `_looks_gone()` and the current debounce branch directly or AST-extract the current branch as the other suites do.
- Delete the obsolete two-poll replica.
- Make unresolved findings fail the pre-ship gate, or label them explicit expected failures that cannot be mistaken for green coverage.

I am **not** reporting a v3.24 recorder regression here. The production path is stronger than this test claims.

## P1 QA — the full roster is not reproducible from its documented command

`qa\run_all.bat` invokes plain `python` for every suite ([`qa/run_all.bat` lines 9–20](qa/run_all.bat#L9)). The README does not define a QA environment or dependency install; it says to run `qa\run_all.bat` ([`qa/README.md` lines 29–39](qa/README.md#L29)).

On this checkout:

- Focused v3.24 suite: **25 passed, 0 failed**.
- Full runner: **failed `micheal`**.
- Both `_mic_watch` threads raised `ModuleNotFoundError: pyaudiowpatch` at [`lore.py` line 2592](lore.py#L2592).
- The existing `ai\venv` can import LORE and run the main QA files, but `importlib` confirms it does not contain `pyaudiowpatch`.

This is a QA reproducibility defect, not proof that the installed application lacks audio support. `PyAudioWPatch` is pinned in `requirements-lock.txt` and collected by `build.bat`. The problem is that the pre-ship runner does not declare or select the environment it expects.

Recommended QA-only correction:

- Give `qa` a small locked dependency file or a declared test interpreter.
- Make `run_all.bat` preflight `sys.executable`, required imports, and Node before running suites.
- Fail once with an environment message instead of letting daemon thread imports fail inside a behavioral test.
- Keep the production-package test separate from pure unit tests if the full build environment is intentionally required.

Until then, “all suites green” is not independently replayable from the documented command on this machine.

## What v3.24 successfully closed

| v3.24 item | Review result |
|---|---|
| Refuse correction with no ear overlap | **Works, but incomplete.** Zero-overlap correction was refused in the real function. Generic-only overlap is the P0 hole above. |
| Skeleton fallback across Arabic/Latin | **Works.** The committed `Rastin` / `راستن` case passes. |
| Readable ear vetoes a noise strike | **Works for the intended multi-word case.** `get behind the door` becomes `unclear`, not `noise`. Exact one-word agreement is the P0 hole above. |
| Refused correction leaves a trace | **Works.** It records `unclear` plus a refusal reason without changing the transcript. |
| Vetoed strike is reconsidered later | **Works.** `ear_kept` rows are excluded from carry at [`lore.py` lines 18455–18464](lore.py#L18455). |
| Ask Video: all evidence fails | **Works.** The unsupported prose is replaced at [`lore.py` lines 22129–22146](lore.py#L22129). |
| Ask Video: one-word substring issue | **Works.** Whole-token comparison prevents `no` from verifying inside `know`; Arabic punctuation is normalized first. |
| Ask Library: invented time | **Works.** Ungrounded hits use the no-seek convention at [`lore.py` line 22295](lore.py#L22295). |
| Arabic speaker-prefix quote recovery | **Works** in the committed functional test. |
| Transcriber changes in v3.24 | **No new transcriber logic.** The `asr_worker.py` delta is synthetic docstring/example text only; the v3.22 physics, echo, and script-language gates remain the current behavior. |

## Recommended order of work

1. Close generic-token authorization in the correction gate.
2. Add the exact one-word agreement exception to the noise veto.
3. Add the four focused regressions under each finding and replay the historical repair/strike sets.
4. Repair the stale recorder oracle and make unresolved findings non-green.
5. Make the QA runner own or preflight its interpreter.
6. Continue the already-agreed queue: multi-decode consensus, token-bounded description chunks, claim-level validation, lineage-aware voting, retroactive `.ins` validation, and OCR/vision persistence.

Items in step 6 remain important, but I found no value in restating their existing designs as if they were new recommendations. The two P0 gates above are smaller, directly demonstrated, and should land first because they protect every future model from two avoidable classes of bad automatic decision.

## What I deliberately did not recommend

- No manual review, approval inbox, or user moderation workflow.
- No split of `lore.py` / `ui.html`, no bundler, and no architecture rewrite.
- No “change the prompt” recommendation for failures that deterministic code can reject.
- No model replacement proposed without comparative evidence.
- No repeated essay on already-queued multi-decode, lineage, chunking, claim validation, or OCR work.
- No recorder fix for the stale `ACTIVE` QA finding; production already contains that fix.

## Acceptance bar for the next release

I would consider these two v3.24 gates closed when the real-function tests prove all of the following:

1. A stopword-only overlap cannot authorize a correction.
2. A fluent but acoustically unrelated correction leaves the transcript unchanged and records `unclear` automatically.
3. A one-word ear that matches the current line token-for-token or by whole-name skeleton cannot be fully struck.
4. An unrelated or junk one-word ear can still be struck.
5. Arabic/Latin name equivalence remains accepted.
6. Historical replay shows the new content-agreement rule does not recreate the measured 27/308 false refusals.
7. `qa\run_all.bat` either completes green from its documented environment or stops before tests with a precise dependency error.
8. Recorder scenarios exercise the live `_looks_gone()` contract rather than a handwritten copy.

That improves hallucination control and input preservation while keeping LORE fully automatic.
