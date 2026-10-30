# Synthetic sewing-materials demonstration

All people, lists, quantities and instructions here are invented. No customer data is needed. Allow about 8–10 minutes after setup. This walkthrough uses the real UI, configured provider and confirmation paths. It has no canned provider responses. A provider error is a failed live step: record it rather than substituting a mock.

## Start safely

Complete README setup, then run `python demo.py`. Each invocation creates a new ignored `.demo-runs/synthetic-.../` folder, two labelled list images, a voice script and an isolated database. Open **http://127.0.0.1:8885**, not the normal app on 8765. Check the yellow **SYNTHETIC JUDGE DEMO / LIVE AI** banner. Nothing is preloaded and the normal database is never opened by the demo launcher. Close stale tabs; stop with Ctrl+C. Restarting starts a fresh scenario and retains the old session locally.

The launcher reads the existing provider configuration without editing it. Requests occur only when you click a review button. Text requests include this isolated session's confirmed history. `python demo.py --prepare-only` generates the images/script without starting a server or making requests. Voice is deliberately recorded by the presenter: the supplied script is not a fabricated transcript or a silent WAV pretending to contain speech.

## Walkthrough and checkpoints

1. **Initial order list.** Select Baseten (or an enabled image provider), choose Order-list image and upload `01-initial-list.png` from the printed folder. Click Review image. Inspect the actual proposal: correct to **10 zips, blue 20 cm** and **5 zips, red 20 cm** if needed. Explain corrections aloud. Choose New for each item, check the image verification box, and save reviewed decisions. Saving a review alone must not create an order. In Apply a saved review, select this review, create a new order named **SYNTHETIC DEMO — sewing materials**, select the intended new lines, check confirmation and apply. Check ordered quantities 10 and 5; dispatched and received both zero.

2. **Separate pickup voice instruction.** Choose Voice note and Baseten. Record yourself reading `pickup-script.txt`: “This is a synthetic demonstration. I have sent the list. I will pick it up tomorrow. Please keep the same quantities.” Stop and listen to playback before Review voice note. Compare the actual AI-generated transcript with what you said. Expect **no items** and a pickup instruction preserving **tomorrow** as relative wording. Correct errors, resolve uncertainty if prompted, verify and save. Explicitly attach this reviewed source to the synthetic order. Do not invent items or apply it as quantities. Check the pickup instruction in the order's attached review history and unchanged quantities 10/5. If microphone permission is unavailable, upload a locally recorded copy of this script; do not call the text fallback an audio test.

3. **Follow-up list: repeat plus addition.** Upload `02-follow-up-list.png` in image mode and review the actual output. Expect 10 blue 20 cm zips and 2 packs of white buttons. The list explicitly says blue zips are the same as the first list. Verify all details and save decisions (Repeat for blue zips; New for buttons). Select the same synthetic order in Apply. The blue-zips overlap must warn even if a review decision was already saved. Resolve it as **Repeat only — quantities unchanged**; choose a new line for white buttons and explicitly confirm application. Check **10 blue zips, 5 red zips, 2 packs white buttons**. If the warning is absent, record a missed overlap and stop before making a wrong change. Never choose addition merely because the product appears again.

4. **Partial dispatch, separate from receipt.** In dispatch/receipt tracking, select the synthetic order and Dispatch. Enter **4** only for blue 20 cm zips; leave other inputs blank. Check the tracking confirmation and record. Check blue ordered **10**, dispatched **4**, outstanding dispatch **6**, received **0**. Red zips remain 5 outstanding; buttons remain 2 outstanding. Do not record receipt without separate confirmation of actual receipt.

5. **Persistence and traceability.** Refresh. Confirm the three source reviews, pickup wording, order quantities and dispatch history remain. Explain that image extraction and transcription can be wrong; the human decisions and deterministic ledger are separate. Use `python evaluate.py template --mode live-ai` before rehearsal to create a blank evaluation record, and record actual outcomes/corrections/errors as described in EVALUATION.md.

## Before presenting

Verify your account can use the configured model for image and audio, credits/network work, microphone permission works, and the screenshots show only synthetic content. A configured key indicator does not prove provider access. Record the rehearsal date, provider/model, original output and corrections. No live response or accuracy score is supplied by this repository. If using the older browser fixtures for a UI-only rehearsal, state **MOCKED AI / NOT LIVE**; those fixtures are separate from `demo.py`.

Judges need an authorized private-repository collaborator invitation and local setup, or a presenter-run screen share. This local server has no authentication or production hosting; no deployment or visibility change is included.
