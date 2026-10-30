# OrderThread

A local order review prototype for text, images and voice notes. AI proposals require human correction and confirmation before saving or applying to an explicitly selected order. Separate source attachments retain review history. Potential overlapping items require an explicit repeat, addition or replacement decision. Dispatch and receipt tracking remain separate.

## Layout

Run the outer `app.py` launcher. The canonical server and browser assets are in `OrderThread/`: `app.py`, `index.html`, `recorder.js` and `catalogue.js`. The older outer HTML page is retained locally but is not served or distributed. No files need moving or deleting.

## Setup

Requires Python 3.11 or later. From the repository root:

```sh
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r OrderThread/requirements.txt
```

Copy `OrderThread/.env.example` to `OrderThread/.env.local` and enter your own provider credentials locally. Baseten uses `BASETEN_API_KEY`; Meta uses `MODEL_API_KEY`. Select an enabled model available to your account using the corresponding model variable. Model availability and provider access must be checked with your provider. Keys stay on the server. Never paste credentials into browser source, commits or screenshots.

```sh
python app.py
```

Open http://127.0.0.1:8765. Stop an existing server with Ctrl+C before restarting; a second listener on the same port is rejected. A fresh checkout creates its own local SQLite database in `OrderThread/`. Do not overwrite an existing database or `.env.local` when updating an installation.

## Audio and review

Uploads and in-app recordings are limited to 60 seconds and 5 MiB. The server validates content, format and duration. WAV follows the existing direct path; supported phone formats use FFmpeg supplied by `imageio-ffmpeg`. The dependency must provide an executable supported on your machine; unreadable files or failed conversion produce an error. Renaming an extension does not convert a recording. Browser recording requires microphone permission and a secure context: localhost for development, HTTPS for deployment on phones. File upload remains available when recording is unsupported.

Transcripts are AI-generated and audio remains identified as the source. Instruction-only notes can be reviewed and attached to an explicitly selected order without inventing items or requiring quantities. Nothing changes automatically.

## Video frame review

Choose **Video frame review** to upload MP4, MOV or WebM video up to 60 seconds, 20 MiB and 4K. H.264 MP4 gives the broadest browser playback support. H.264/H.265, VP8/VP9 and AV1 tracks are validated locally through the existing `imageio-ffmpeg` dependency. No additional hosted video service is used.

Play, pause or seek, then explicitly select up to three stills. Review each still independently through the existing image extraction and confirmation flow. Only the chosen still is sent to AI: events between frames can be missed, and the audio track is not analysed. Playback positions are approximate selection references, not verified event timestamps or quotes. Repeated products across frames require separate human decisions and the existing order overlap checks.

Before confirmation, video/frame drafts stay in bounded server memory for up to 30 minutes (temporary decoding files are removed). Saving a reviewed frame also saves the original video in a separate additive `source_videos` table and retains its relationship in review, application and attachment history. Refresh preserves confirmed source associations; unsaved frame selections are intentionally cleared. Discarding a draft does not delete confirmed history. Original video files and local database files are excluded from Git.

Supply speech as a separate recording or audio file in Voice note mode. Review its AI-generated transcript and instructions independently, then explicitly attach the reviewed source to the selected order. Nothing automatically merges the inputs or changes quantities.

Video file reads have a 15-second deadline, validation/frame requests a 40-second deadline, and local decoding a 30-second process deadline. Draft cleanup runs independently so a failed cleanup cannot block a new upload. A timeout displays an actionable error and releases the controls.

Run focused tests with `python -m unittest -q test_video_frames.VideoFrameTests` and `node video_frames_test.cjs`. The browser fixture is `python browser_video_server.py` on port 8884; it prints a temporary synthetic-media folder and uses a temporary database with mocked image/audio responses. Stop it with Ctrl+C. It never calls a real provider.

## Catalogue

Use the catalogue panel to upload a UTF-8 CSV, preview and map product name, variant and unit columns, then explicitly confirm the import. `OrderThread/sample-catalogue.csv` contains synthetic products only. Missing names and duplicate rows are rejected. Catalogue matching offers optional references during item review; it does not change quantities or imply stock availability. Limits: 256 KiB, 1,000 rows and 30 columns per import; 10,000 catalogue products. Search returns at most 200 products and review suggestions show at most five matches.

## Tests

API tests use temporary databases and mocked AI responses. Mobile audio tests generate synthetic audio and exercise real local FFmpeg conversion. Run:

```sh
python -m unittest -q test_app test_audio test_mobile_audio test_attachments test_overlaps test_startup test_catalogue test_video_frames
node recorder_test.cjs
node video_frames_test.cjs
```

Some inherited API tests are repeated by unittest discovery. Browser scripts require Node.js, Playwright and an installed Microsoft Edge browser. Install Playwright in a separate local tooling environment (excluded from Git), or set `PLAYWRIGHT_MODULE` to its module path. Start the corresponding `browser_*_server.py` fixture before running its browser test. Fixtures use temporary databases and synthetic/mocked data on ports 8876 through 8883; they must not be pointed at the production database. `browser_recorder_test.cjs` uses the audio fixture on 8878 and a simulated microphone.

Previously verified browser flows include review, attachments, overlap decisions, recording and catalogue import. A physical microphone and live Baseten transcription have not been verified. These tests do not establish live provider availability.

## Data and deployment

This repository includes application code, synthetic catalogue data and tests, not customer orders, uploads, recordings, credentials, database files, logs or local investigation notes. Keep private backups separately. The local development server has no user authentication and is intended for a trusted local machine. Deploying it requires an appropriate authenticated hosting setup, HTTPS, protected credentials and a data backup policy.

## Submission

The GitHub repository must stay private. Invite authorized reviewers as collaborators if they need access. Any required demo, video, deployment link or hackathon submission form is separate from publishing this source; check the event's requirements.
