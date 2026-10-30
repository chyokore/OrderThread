# Selected-frame video review verification

This is selected still-image review, not native or synchronized video understanding. See README.md for limits, dependency and setup.

## Resumed work

Preserved the existing unfinished files and inspected the earlier logs (57 regression tests and seven focused video tests passed). No reset, deletion, commit, push or Git-history rewrite was performed.

Hardened video intake so file reads end after 15 seconds and validation/frame requests abort after 40 seconds. Controls leave their busy state on failure. Draft cleanup is nonblocking with a five-second request deadline. Added tests that reproduce stalled reads, timed-out requests and stalled old-draft cleanup. Existing non-video calls retain their previous request behaviour.

Carried original-video metadata into derived order-apply and attachment history. Confirmed stills remain image sources, with immutable server-side parent-video metadata. Fixed source labels and incorrectly encoded display punctuation. Added setup and test documentation.

## Browser check

Used browser_video_server.py on port 8884, a temporary database and generated synthetic media. Image/audio AI responses were mocked; local FFmpeg validation and frame extraction were real. No live provider requests were made.

The prior long file-picker stall did not recur after opening a normal HTTP test page and splitting chooser opening from file selection with bounded waits. The available browser had initially been an internal error page, which browser policy blocked; the user opened the HTTP test page. We cannot attribute the historical picker stall to a proven application defect.

Verified in the browser:

- Invalid synthetic MP4 gives an unreadable-content error.
- A four-second H.264 MP4 uploads and validates; the user explicitly selects a still.
- Review this frame invokes the existing image review; each item decision and source-save checkbox are explicit.
- Saved frame and original-video association appear in history after refresh.
- Explicit application creates a temporary order with 10 blue zips and 5 red zips.
- Separately uploaded WAV produces an independently reviewed instruction-only transcript. Explicit attachment adds pickup instructions without changing either quantity.
- Both distinct source histories and the pickup instruction survive another refresh.
- The persisted original video loads with duration 4 seconds, no media error, and working play/pause/seek controls.
- No browser console errors were recorded.

## Automated checks

The final combined run passed all 64 selected API tests using temporary databases. This covers existing text, image, audio, catalogue, order, attachment, overlap, dispatch and receipt behaviour plus seven video-frame tests. One earlier combined run had a connection reset reading the homepage; its isolated rerun and the complete subsequent run passed. Recorder unit tests and video-control unit tests passed, including inline page JavaScript parsing. Control-state tests use a mocked DOM/network and are reported separately from the actual browser check.

The real database and .env.local hashes match the preservation baseline. No customer media was used. No model API credentials were displayed. Original video/frame blobs are written to the configured local database only after explicit review confirmation; source associations persist independently of expiring in-memory drafts.

## Running locally

Install OrderThread/requirements.txt. Start or restart the normal app with python app.py from the repository root, then reload http://127.0.0.1:8765. The existing configuration and database remain in the canonical OrderThread directory; a separate source_videos table is created additively when the new app accesses the database. The temporary browser fixture on 8884 uses mocked AI and must not be mistaken for the main app.

## Pre-commit review, 2026-10-30

Reviewed the selected-frame implementation and working tree. The full documented Python command passed 254 tests in 209.940 seconds, including inherited repeated tests. Both `node recorder_test.cjs` and `node video_frames_test.cjs` passed; staged whitespace checks passed. The JavaScript checks required execution outside the filesystem sandbox because Node could not resolve the Windows user directory inside it.

Confirmed the existing GitHub repository is private. Tracked/candidate file checks found no local data paths or credential signatures; local configuration, databases and media remain ignored. Clarified the historical feasibility report to distinguish it from the implemented fallback. This review did not repeat the earlier interactive browser session, physical microphone check or live provider verification.
