# Synthetic evaluation protocol

`evaluation_cases.json` is a small labelled fixture set, not a representative benchmark. Labels describe desired behaviour, not measured outputs. Each case starts independently with 10 blue 20 cm zips; do not carry additions/replacements from one case into the next. The longer demonstration is in DEMO.md.

| Case | Expected warning | Human action / expected result |
| --- | --- | --- |
| Repeat plus buttons | Blue zips only | Repeat blue zips; add new buttons; quantities 10 and 2 |
| Intentional addition | Blue zips | Add 3 to existing 10; total 13 |
| Replacement | Blue zips | Replace unfulfilled quantity with 7; total 7 |
| Different colour | None | Keep blue 20 cm at 10; new red 20 cm line at 3 |
| Different length | None | Keep blue 20 cm at 10; new blue 30 cm line at 3 |
| Unclear quantity | Not scored | Leave quantity unresolved; saving blocked; clarify with buyer |
| Separate pickup | Not scored | Audio review has no items; explicit attachment; quantity stays 10 |
| Partial dispatch | Not scored | Confirm dispatch 4; ordered 10; outstanding 6; received 0 |

## Repeatable records

Run `python evaluate.py offline` for fresh temporary databases and real local HTTP handlers. It uses hand-authored proposals to exercise deterministic confirmation, overlap and ledger rules. The pickup case **mocks AI**, with synthetic silence; it tests the audio review/attachment path, not speech recognition. Other cases never invoke AI, and unexpected provider calls are blocked. Output is a unique ignored `.evaluation-runs/offline-....json` with actual observations, expected labels, pass/fail and overlap differences. A nonzero exit means at least one check failed. Do not use Python's `-O` flag: checks use assertions.

Run `python evaluate.py template --mode live-ai` (or `manual`, `mocked-ai`) for a blank record with every outcome **not-run** and observations **null**. It makes no requests. Fill it locally during a real rehearsal; don't commit responses or recordings. Record provider/model, date, source type, reviewer and any latency/error in notes. Record the raw proposal **before corrections**, human corrections separately, and final observed quantities/history. Live run input may use the case's text source; use labelled list images for the demonstration and record the supplied pickup script for the audio case. Note the modality: text success does not establish image/audio performance.

For each independent case, start `python demo.py` for a fresh isolated session, establish the baseline through real review/confirmation, then submit the source. Compare provider extraction to the label first. An incorrect extraction is an extraction failure even if a correction later makes the order right. Next, record the overlap warning **indexes from the displayed incoming proposal**, after identifying which item corresponds to the labelled blue zips. If item order differs, map indexes explicitly in notes before comparing them. Test the labelled human resolution and final ledger separately. A human confirmation is intentional input, not AI intent accuracy.

For overlap cases:

- **Missed overlap** = labelled warning item absent from observed warning items. Record its incoming item index in `missed_overlap_indexes`.
- **False warning** = observed warning item with no labelled overlap. Record it in `false_warning_indexes`.
- Record empty arrays only after observing no errors. Leave null for unrun, blocked or inapplicable comparisons; never turn missing observations into zero errors.
- For unclear quantities, record whether the actual proposal kept uncertainty and whether confirmation blocked unresolved data. This is separate from overlap scoring.

Use outcomes `pass`, `fail`, `blocked` or `not-run`; include evidence references and provider errors without credentials. Inspect JSON locally or use an editor to fill observations. Keep corrections, retry behaviour and blocked steps visible. No accuracy percentage is computed. Eight synthetic examples and mocked workflows cannot establish real-world accuracy.

## Verification boundaries

Deterministic tests verify application rules. Mocked-provider tests verify contracts and UI/API behaviour. Real local FFmpeg decoding tests verify media handling. Live AI evaluation requires real completed provider responses for the configured account/model. An API key being present, an HTTP 200 without usable content, or passing mocked tests does not count as live AI success. See VERIFICATION.md for checks actually run during this preparation.
