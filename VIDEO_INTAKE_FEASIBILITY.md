# Video intake capability check

Historical capability check from 2026-10-29, before the selected-frame fallback was implemented. Native video analysis remains unverified. See README.md and VIDEO_FRAME_REVIEW.md for the implemented selected-still review and its verification.

## Official documentation

[Baseten Vision](https://docs.baseten.co/inference/model-apis/vision) documents Muse Spark Open under `meta-models/muse-spark-open`. It accepts MP4, MOV, MKV and WebM with H.264, H.265, VP9 or AV1, up to 4K/60 fps. Published limits are two videos per request, 300 seconds per video, 200 MB per video by URL, 200 MB combined media and a 100 MiB base64 request body. There is also an 896 MiB encoded-media budget. Base64 overhead counts toward the request body. At most 96 frames are sampled; the audio track is ignored. Speech requires a separate audio part. These family limits are not verified limits for the hackathon variant.

[Meta's official Baseten cookbook](https://github.com/meta-models/meta-oss-cookbook/blob/main/muse-spark/hosted/baseten.md) describes a `video_url` content part for Chat Completions. The intended request is a user message containing text and `{type: "video_url", video_url: {url: "data:video/mp4;base64,..."}}`, sent to Baseten's `/v1/chat/completions` endpoint. Credentials belong in the authorization header only.

## Exact configured hackathon model

The configured model is `meta-models/muse-spark-open-1026`. The official pages checked do not identify this slug or guarantee its video capabilities.

Live probes used only a temporary two-second, 320 x 240, silent blue MP4 encoded with H.264 (1,720 bytes). No customer files were sent and no credentials were printed or written to the report.

- The sandbox request timed out.
- A request with normal network access reached Baseten and returned HTTP 200, but no answer text with a 160-token output budget. Payload acceptance does not demonstrate usable video understanding.
- A follow-up using a 2,048-token output budget timed out after 55 seconds. There was no completed analysis to verify.

Result: exact-model native video analysis remains unverified. Do not present mock responses as live video analysis. No alternate model was silently substituted.

## Feasible fallback

Use user-selected still frames from the video in the existing image review flow, and review any extracted speech separately through audio intake. Keep each reviewed input separate, link it to an explicitly selected order, and confirm each attachment. This is a proposed fallback, not an implemented video feature. A dedicated future implementation should preserve the original video as its source and disclose frame sampling, without claiming verified quotes, timestamps or synchronized audiovisual understanding. Missing quantities, colours, variants and intent must remain unresolved until reviewed.

Before native implementation, obtain a completed response for the exact hackathon slug using a synthetic order-list clip and confirm the usable payload and limits with Baseten. Then implement server validation, source persistence and human review, and test them with synthetic fixtures and temporary databases.

## Verification

All 57 selected API regression tests passed using temporary databases and mocked AI, covering text, images, audio, catalogue, attachments, overlap decisions, orders and tracking. The two startup checks also passed separately. Local FFmpeg tests used synthetic audio. No mock video analysis was built. Browser automation timed out while opening the isolated fixture, so no completed browser verification is claimed. The temporary fixture was stopped. The real database and `.env.local` hashes are unchanged, and application code is unchanged.
