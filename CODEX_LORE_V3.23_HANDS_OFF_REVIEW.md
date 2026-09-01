# LORE v3.23 hands-off AI review

**Reviewed:** 2026-09-01  
**Repository state:** `6da17da` / LORE v3.23  
**Compared with:** v3.21 `ffeb213` and the original `CODEX_LORE_AI_REVIEW.md`  
**Context read:** `REVIEW_BRIEFING_FOR_CODEX.md`  
**Change policy:** review only. No application code, prompts, settings, or existing files were changed. This Markdown file is the only new artifact from this follow-up.

## Product decision accepted

The production system must be hands-off. The owner should not have to approve transcript corrections, work through an inbox, or resolve uncertainty as part of normal use.

The original recommendation that the auditor should always propose and wait for user approval is therefore withdrawn.

The replacement rule is:

> LORE automatically applies changes when evidence is strong enough, automatically preserves the original when evidence is inconclusive, and automatically rejects unsupported generated output. Human judgment belongs in development QA, not in the production workflow.

Hands-off does not require LORE to alter every uncertain result. **Automatically preserving the current reading is itself an autonomous decision.** It is safer than forcing a correction that the available evidence cannot support.

Banking and reversibility remain important, but they solve a different problem. A banked wrong correction is recoverable; it is still the primary result shown to a hands-off user. The automatic mutation gate therefore has to establish accuracy before applying a change, while banking protects against defects that escape that gate.

## Executive assessment

v3.22 and v3.23 contain meaningful improvements that directly address several findings from the v3.21 review:

- ASR now detects physically impossible text density and retries without context.
- The short game-title prompt-echo hole was closed.
- stored language follows the script that was actually produced rather than trusting the model's language tag;
- cloud-budget handling now fails closed and uses the selected model for its estimate;
- Ask Video checks returned quotes and derives timestamps from matched transcript segments;
- Ask Library tries to ground times in the transcript;
- named voices are attached to describer lines where overlap attribution exists;
- describer quotes are checked against cited transcript content;
- title/summary name checks now include a narrow Arabic kinship-claim detector;
- network and build documentation are substantially more accurate.

These are good changes. The present system is nevertheless not fully evidence-closed yet. The largest remaining risks are:

1. auditor corrections and strikes can still be applied without deterministic agreement with the audio re-listen;
2. Ask endpoints can still display unsupported answer prose or timestamps after their supporting evidence fails;
3. the describer still omits transcript lines and verifies quotes rather than the factual claims built around them;
4. existing generation-3 descriptions do not automatically receive the new validation;
5. the claimed QA roster is not reproducible from the repository.

None of the remedies below require a manual production workflow.

## Current automatic pipeline

```text
recording
   |
   +--> VAD and ASR --------------------------- transcript (.stt)
   |
   +--> loudness / CLAP / voices / OCR ------- senses (.sns)
   |
   +--> selected frames ----------------------- vision (.vis)
   |                                               |
   +-----------------------------------------------+
                                                   v
                                       describer review (.ins)
                                                   |
                                                   v
                                      auditor and mutations (.aud)
                                                   |
                                                   v
                                  title, chapters, moments, Ask UI
```

The correct target is not to add a human between these stages. It is to make every automatic promotion—from observation to claim, and from claim to mutation—pass a machine-verifiable evidence rule.

## Priority findings

| Priority | Finding | Hands-off consequence |
|---|---|---|
| **P0** | Auditor fixes do not have to agree with the audio re-listen | A plausible model correction can become primary transcript truth without acoustic consensus. |
| **P0** | Auditor `noise` verdicts can automatically strike speech without a deterministic no-speech/no-readable-speech gate | A legitimate rare name or phrase can become `[unintelligible]`. |
| **P0** | Ask Video retains the model's answer after rejecting its evidence | The UI can display an unsupported assertion followed by a warning that its quotes were invalid. |
| **P0** | Ask Library falls back to a model-generated time precisely when transcript grounding fails | A fabricated seek position is accepted by construction. |
| **P1** | Description still samples away transcript lines, and a retry can remove more | The model writes continuous narrative over evidence it never received. |
| **P1** | Quote validation does not validate chapter and moment claims | Valid source wording can be attached to an unsupported explanation. |
| **P1** | Quote recovery has a Latin-only speaker-prefix regex | Honest Arabic named-speaker quotes can be blanked. |
| **P1** | New description guards are not retroactive for existing generation-3 reviews | Much of the existing library remains under the older validation behavior. |
| **P1** | Auditor layer agreement remains temporal and lineage-blind | Correlated, unrelated outputs can be counted as multiple witnesses. |
| **P2** | QA suites and measured results are not committed | Pre-ship claims cannot be independently replayed or used as stable regression gates. |

## Detailed findings and automatic remedies

### 1. Auditor correction still lacks acoustic consensus

The auditor now performs a genuine audio re-listen, which is stronger than the v3.21 path. `_aud_relisten()` extracts the doubtful span and re-runs Qwen ASR (`lore.py:16881-16970`). However:

- the re-listen uses the same ASR family rather than an independent model;
- it always primes the answer as Arabic (`lore.py:16927-16936`), even though the product is deliberately bilingual;
- the result is stored as `g["ear"]` and given to the thinker as contextual evidence;
- `_aud_parse()` does not require the proposed correction to match `g["ear"]` (`lore.py:17255-17300`);
- the hard gate is `_aud_sense()`, which checks whether enough output words have appeared in the transcript library (`lore.py:16020-16049`).

The vocabulary test is useful for rejecting gibberish. It cannot prove that a fluent sentence made of familiar words is what the audio contains.

#### Automatic remedy

For every shortlisted span, produce a small decode panel:

1. no-context, language-auto;
2. no-context, English-pinned;
3. no-context, Arabic-pinned;
4. optional clean-mic decode when the mic track substantially covers the interval.

Normalize each decode without destroying Arabic morphology or code-switching. A candidate correction may be applied automatically only when:

- at least two sufficiently different decodes agree on the candidate or a stable token core;
- the candidate passes duration/physics and permitted-script checks;
- source-track/VAD evidence confirms speech exists;
- the candidate is not merely plausible library language;
- the candidate does not introduce a proper noun unsupported by the stable decode set.

If the panel does not converge, LORE should automatically preserve the original and record an internal `unresolved` result. That requires no user action.

The sidecar should retain the decode panel and the exact reason for the decision so development QA can determine whether thresholds are too strict or too permissive.

### 2. Noise strikes need a stricter automatic gate

`_aud_apply_strikes()` replaces a full line with `[unintelligible]` or keeps only a readable split when the thinker assigns `verdict = noise` (`lore.py:17957-18048`). Originals are banked, which is good.

The problem is upstream: `_aud_parse()` accepts the model's `noise` verdict without requiring that the re-listen was empty, marked `ear_junk`, or disagreed with all readable alternatives. The thinker sees the dossier, but this is still prompt-level judgment rather than a deterministic mutation condition.

#### Automatic remedy

A full strike should require all of the following:

- the original line was shortlisted by a non-LLM detector;
- multiple re-decodes fail to produce a stable readable core;
- no clean-mic decode supports the original;
- no nearby transcript continuity depends on the line;
- no screen text or user-confirmed name supports the rare term;
- the audio duration/energy does not make the proposed readable text credible.

If those conditions are not satisfied, preserve the original automatically. A partial strike should retain every token span supported by any stable decode.

Banking stays in place as defense in depth, not as the accuracy gate itself.

### 3. Ask Video verifies hits but not answer prose

The v3.23 Ask Video verifier is a strong improvement. It normalizes returned quotes, finds them in transcript segments, and snaps result times to the source segment (`lore.py:21919-22006`).

When a quote cannot be verified, the hit is removed. But the original model answer is still returned and only receives an appended warning (`lore.py:22009-22013`). If every quote supporting “Alice said the key is under the bridge” is rejected, the answer can still say Alice said it.

#### Automatic remedy

The final answer must be downstream of verification:

- If verified hits remain, regenerate or deterministically construct the answer using only their source text.
- If the original answer contains a clause with no surviving source, remove or rewrite that clause automatically.
- If no evidence remains, return a direct automatic result such as: “LORE could not verify that in this transcript.”

This is not a silent drop. It is an explicit, fully automatic evidence verdict.

### 4. One-word quote checking is not boundary-safe

For a one-word quote, `ask_video()` checks whether the raw normalized word is a substring of the transcript line (`lore.py:21979-21984`). This can verify `no` inside `know`, `he` inside `the`, or another short token inside a longer word.

#### Automatic remedy

Tokenize both values with bilingual-aware boundaries and require exact token equality. Apostrophe normalization can remain. For Arabic, normalize presentation differences conservatively but do not remove characters that distinguish words.

Add regression fixtures for:

- `no` versus `know`;
- `he` versus `the`;
- curly versus straight apostrophes;
- Arabic punctuation;
- code-switched single tokens.

### 5. Ask Library accepts an invented time when evidence is weakest

The v3.23 comment correctly states that the rows shown to the model contain no timestamps, so a nonzero `t` returned by the model is invented by construction (`lore.py:22139-22151`). `_moment_of()` first tries to find the reason/question in the recording's transcript. If that fails, the implementation falls back to the model's number (`lore.py:22152-22163`).

This is the inverse of a safe evidence rule: the unsupported time is trusted exactly when transcript grounding fails.

#### Automatic remedy

- When `_moment_of()` finds evidence, use the transcript-derived time.
- When it does not, return the recording with `time_unknown = true` or open it without seeking.
- Never retain the model's timestamp when the model was not shown timestamps.
- Verify the returned `why` against the selected recording. If it cannot be grounded, replace it with an extractive reason from the indexed row or transcript.
- Construct the final library answer only from validated result rows.

Again, no manual action is needed.

### 6. Describer input loss remains open

Description still uses fixed 30-minute windows and evenly samples lines until the context fits (`lore.py:14179-14193`). If parsing fails, the retry halves the selected line count again (`lore.py:14274-14296`). The retry also rebuilds a smaller prompt header without all of the earlier frame/senses/eye context.

Telling the model that lines were sampled may reduce overconfidence, but it cannot make the missing content available. A counter measures frequency; it does not correct the output.

#### Automatic remedy

Use token-bounded subwindows that preserve all lines:

1. advance through transcript segments in time order;
2. add complete segments until the token budget is near its limit;
3. end at a pause where possible;
4. overlap a small number of stable global segment IDs;
5. extract cited claims from every subwindow;
6. merge adjacent chapters only after coverage is complete;
7. automatically verify that every included transcript segment was classified as narrative, non-narrative, or uncertain.

A parse retry should retry the same evidence with stricter decoding or smaller output limits. It should not solve parsing failure by removing source lines.

### 7. Citation validity is narrower than claim validity

`_q_check()` validates a stretch quote, and `_m_qcheck()` checks a leading quote in a moment explanation (`lore.py:13780-13840`). This proves that the words exist somewhere in the cited range. It does not prove that:

- the chapter label follows from those words;
- the `what` sentence is supported;
- the topics were actually discussed;
- the event category is correct;
- an unquoted remainder of a moment explanation is factual.

The assembled output still writes `what`, topics, and labels without a semantic evidence gate (`lore.py:14039-14065`).

There is also a boundary issue: `_q_check()` joins every transcript line in the stretch and tests one substring against the combined text. A phrase assembled from the end of one segment and the start of a later segment can pass even though the prompt says the quote is copied from a line.

#### Automatic remedy

Have the extraction pass return atomic fields with direct evidence IDs:

```json
{
  "claim": "The group defeated the boss",
  "evidence_ids": ["stt:188", "ocr:481.8"],
  "quote": "finally, he's down",
  "kind": "event"
}
```

Then apply deterministic checks:

- quotes must match one line or two immediately adjacent lines separated by a small audio gap;
- names must occur in direct evidence;
- event categories must have the required evidence type;
- summary/title generation receives only validated atomic claims;
- unsupported claims are automatically omitted or rewritten from supported evidence.

A small entailment verifier can be added after deterministic checks, but it must not be allowed to overrule a failed exact citation.

### 8. Arabic speaker-prefix recovery is Latin-only

When a copied quote initially misses, the validator removes interface dressing such as `[#12 4:05]` and then removes a speaker prefix using:

```text
^[A-Za-z][\w' .-]{0,24}:\s+
```

at `lore.py:13807-13808`.

An honest copied line beginning with an Arabic speaker name, such as `مريم: ...`, does not match that recovery path and may be blanked.

#### Automatic remedy

Strip a prefix only when it exactly matches the speaker label that LORE itself attached to the cited line. This is safer than a broad multilingual regex and naturally supports Latin, Arabic, mixed-script names, and `YOU:`.

### 9. Existing reviews do not automatically receive v3.23 validation

`_INS_GENERATION` remains `3` (`lore.py:5066`). `_ins_owing_raw()` only schedules an upgrade when a complete review's generation is below the current generation (`lore.py:13625-13639`). Generation 3 dates back to v3.09.

Therefore, existing complete generation-3 `.ins` files are not automatically rerun or revalidated merely because v3.23 added quote and speaker safeguards. The new protections affect future descriptions and windows that are regenerated for another reason.

#### Automatic remedy

Do not necessarily force an expensive model rerun. Add a separate lightweight validation version, for example:

```text
ins_generation: controls model/prompt regeneration
ins_validation: controls deterministic post-validation
```

At idle, apply the new deterministic quote/name checks to existing sidecars, bank the old file, and stamp the validation version. Queue a model rerun only when deterministic validation proves that derived claims need rebuilding.

This brings the existing library forward automatically without using the GPU unnecessarily or requiring a user workflow.

### 10. Auditor layer agreement remains lineage-blind

`_aud_says()` still counts any nearby transcript, sound/OCR event, eye label, review moment/chapter, or laugh as a layer at the same second (`lore.py:16256-16349`). `_aud_condemn()` calls the non-origin layers `agrees` without checking semantic agreement (`lore.py:16386-16401`).

The review layer is derived from transcript, senses, and vision. It cannot be an independent witness for those inputs. Two unrelated observations near one timestamp also do not support the same claim merely by co-occurring.

#### Automatic remedy

Every item should carry lineage:

```json
{
  "id": "ins:moment:12",
  "claim": "boss defeated",
  "derived_from": ["stt:188", "ocr:481.8"]
}
```

The auditor should count support only when:

- the evidence matches the same atomic claim or entity;
- the source is capable of observing that claim;
- the vote is not derived from another vote already counted.

Review text can explain direct evidence but should have vote weight zero for corroborating its own inputs.

## Hands-off decision matrix

| Stage | Evidence passes | Evidence conflicts | Evidence absent |
|---|---|---|---|
| ASR correction | Apply candidate and bank original | Preserve original; store unresolved diagnostics | Preserve original |
| Noise strike | Strike/partially strike only after multi-decode failure | Preserve original | Preserve original |
| OCR event | Promote after confidence + temporal persistence | Keep as raw OCR only | No event |
| Vision event | Promote after multi-frame consistency | Keep as weak visual observation | No event |
| Description claim | Display after citation and claim checks | Rewrite from supported evidence | Omit with no invented replacement |
| Ask answer | Construct from verified hits | Remove unsupported clauses | Return an explicit not-verified answer |
| Auditor vote | Count independent semantic support | Record conflict | Do not infer silence unless coverage is proven |

No row requires user approval.

## Development QA required to reach hands-off quality

The owner is willing to perform QA to make the automatic system reliable. That is exactly where human review belongs.

The briefing reports roughly 30 scratch-pad suites and more than 400 checks, but no test files or reproducible evaluation artifacts are present in the repository. External review can verify code paths but cannot replay the reported false-positive measurements.

Create a development-only `qa/` or equivalent area containing:

- pure unit tests for every deterministic guard;
- minimal synthetic transcript/sidecar fixtures;
- hashes or manifests for private held-out media kept outside Git;
- expected labels and decision outputs;
- a runner that produces before/after metrics;
- a checked-in summary of the last accepted baseline;
- explicit regression thresholds.

This does not add anything to the production UI and does not ask the user to review recordings during normal use.

### Minimum hands-off metrics

| Component | Required measurements |
|---|---|
| ASR | WER/CER, hallucinated utterances, false blank rate, named-entity error |
| Auto-corrector | correction precision, harmful correction rate, stable-decode agreement |
| Auto-striker | false strike rate, partial-strike precision |
| OCR | event precision, false events/hour, adjacent-frame persistence benefit |
| Vision | entity/place precision, unsupported proper-noun rate |
| Description | supported-claim precision, exact citation rate, coverage rate |
| Ask | supported answer-clause rate, quote validity, timestamp validity |
| Auditor | independent-support precision, correlated-vote rejection, net output improvement |

For mutation stages, precision matters more than recall. It is acceptable for an uncertain line to remain unchanged. It is not acceptable for a fluent but wrong automatic correction to become the primary truth.

## Recommended implementation order

### P0 — close automatic mutation and answer holes

1. Require decode consensus before transcript corrections.
2. Require deterministic multi-signal failure before noise strikes.
3. Rebuild Ask Video answers from verified hits.
4. Remove the ungrounded Ask Library timestamp fallback.
5. Make one-word quote matching token-boundary safe.

### P1 — make descriptions evidence-complete

1. Replace even sampling with all-line token chunks.
2. Preserve evidence on parse retries.
3. Add atomic claim/evidence IDs.
4. Validate labels, `what`, topics, and moments, not only quotes.
5. Make speaker-prefix validation source-derived and bilingual.
6. Add lightweight retroactive validation for existing generation-3 reviews.

### P2 — make automatic quality provable

1. Add lineage-aware auditor voting.
2. Add OCR confidence and adjacent-frame persistence.
3. Add multi-frame vision consistency.
4. Commit the deterministic QA harness and baseline reports.
5. Gate future prompt/model/threshold changes on measured regressions.

## Small documentation observation

`CURRENT-BUILD.md` now correctly reports v3.23 and the staged worker size, but its “Last commit” row still says `6ff787e` / v3.22. The report was generated before the v3.23 commit and committed alongside it, so it remains one commit behind even though its version is current. If commit identity matters, generate or amend it after the release commit, or report a source-tree hash that is available before committing.

## Final position

The owner's rejection of manual production review is compatible with the evidence-first direction. The recommendation changes from:

```text
AI proposes -> user approves -> mutation
```

to:

```text
AI proposes
    -> deterministic and acoustic evidence passes -> mutate automatically
    -> evidence conflicts or is insufficient      -> preserve automatically
    -> output is unsupported                      -> reject automatically
```

Development QA supplies the labeled truth needed to tune those gates. Production remains fully hands-off.

The most important next change is the auditor mutation boundary: a correction or strike should never land merely because it is plausible and passed a vocabulary check. It should land only when the recording itself provides stable, machine-verifiable support.
