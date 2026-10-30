# Judge preparation verification — 2026-10-30

These are local engineering checks, not AI accuracy results. No live provider calls were made during this preparation.

| Check actually run | Result and boundary |
| --- | --- |
| `python check_setup.py` | Passed on Python 3.11.9, Pillow 12.2.0, imageio-ffmpeg 0.6.0; local FFmpeg starts. Provider-key presence checked without displaying values. Presence is not provider access. |
| `python -m pip check` | No broken installed requirements. A clean-machine package download/install was not repeated. |
| `python -m unittest -q test_demo` | 5 passed. Generated image/script assets, blank evaluation records, busy-port safety, synthetic banner and actual subprocess launcher startup with a fresh isolated database. GET-only smoke checks; no AI. |
| `python evaluate.py offline` | All 8 labelled cases passed their application-rule expectations. Seven use hand-authored proposals/ledger inputs; the pickup case uses explicitly mocked audio AI and synthetic silence. Unique local JSON records actual observations and warning differences. Not extraction/transcription accuracy. |
| Regression command below | 110 passed in 92.846 seconds. Temporary databases; provider responses mocked where applicable. Real local FFmpeg media checks use synthetic inputs. Includes inherited repeats from AudioTests. |
| `node recorder_test.cjs` | Passed; mocked browser/media APIs, not a physical microphone test. |
| `node video_frames_test.cjs` | Passed; mocked DOM/network plus inline page JavaScript parsing, not an interactive browser test. |
| `python demo.py --prepare-only` | Generated labelled synthetic list images and pickup script; follow-up image visually inspected. No server/provider call. |
| `python evaluate.py template --mode live-ai` | Created a blank ignored record, with null observations and not-run outcomes. No request or live result. |
| Python compilation and `git diff --check` | Passed. |
| Preservation / Git exclusions | Hash comparison found no changes to pre-existing files outside intended README/ignore edits. Existing configuration, database and user files preserved. Candidate path and credential-signature scans found no matches; generated sessions and observations are ignored. No secret values displayed. |

Regression command:

```sh
python -m unittest -q test_app.AppTests test_audio.AudioTests test_mobile_audio.MobileAudioTests test_attachments.AttachmentTests test_overlaps.OverlapTests test_startup test_catalogue.CatalogueTests test_video_frames.VideoFrameTests
```

The JavaScript commands required execution outside the Windows filesystem sandbox because Node otherwise could not resolve the user directory. Their checks passed there; whitespace was checked separately in the workspace. No application source, normal database schema or provider settings were changed in this preparation.

## Still required before judging

- Run DEMO.md end to end with actual usable responses from the configured provider/model. Record raw proposals, corrections, errors, modalities and observed results in the blank live record. No completed live rehearsal is claimed here.
- Verify physical microphone permission, audible playback and live transcription, or prepare a clearly synthetic presenter-recorded upload. The supplied voice script is not a generated recording or a measured transcript.
- Confirm the actual browser rendering and confirmation steps during rehearsal. The smoke check verifies HTTP startup/banner/empty orders; the existing earlier browser report is not a new interactive demonstration check.
- Verify setup on the judge's machine if they will run it themselves, including package installation and account/model access. This preparation verified the installed local runtime, not a fresh OS environment.
- Arrange authorized access to the private repository and local instructions, or a presenter-run screen share. Event submission links/media and any future authenticated hosting are separate work. No deployment, collaborator invitation, visibility change, commit or push was performed in this preparation.

## Pre-commit recheck — 2026-10-30

The combined demo and regression command passed all 115 tests in 96.204 seconds. All eight offline evaluation cases passed again. Setup, installed-package consistency, both JavaScript checks and whitespace checks passed; JavaScript required execution outside the Windows filesystem sandbox. GitHub API verification confirmed `chyokore/OrderThread` has private visibility. The ten explicit candidate files passed a credential-signature scan, and tracked paths contained no excluded local data files. Live AI, physical microphone, interactive browser rehearsal and clean-machine setup remain unverified.
