# Ticket: Visual feedback provider rate-limit handling

## Summary

On 2026-05-12, a valid PNG image submission failed because the external model
provider returned repeated rate-limit errors during visual feedback generation.
This was first observed in the new classroom upload flow and is separate from
the wrong-file-type upload failures.

The image payload itself was valid. Follow-up testing indicates that the
failure is not ordinary account credit exhaustion and not upload corruption.
The likely trigger is provider-side admission/tokenization behavior for a
large PNG submitted as a base64 data URI through Mistral's OpenAI-compatible
chat-completions endpoint.

No learner names, user IDs, storage object paths, hashes, provider request IDs,
or other PII are included in this ticket.

## Status

Minimal reproduction fix implemented on 2026-05-14.

- Large provider-bound PNG screenshots are converted to RGB JPEG and downscaled to a maximum edge length of 1280 px before the Visual Feedback provider call.
- Direct high-pixel PNG uploads above 16 MP are rejected as `input_too_large` before full raster decoding, closing the review finding where a small-on-disk PNG could otherwise allocate a large in-memory image during normalization.
- Transparent PNGs are composited onto white before JPEG conversion, closing the review finding where hidden RGB values in transparent pixels could turn a worksheet or drawing canvas background black.
- Stitched PDF page images in direct Visual Feedback use the same provider-bound normalization as direct PNG uploads, with a separate 64 MP budget so normal multi-page A4 PDFs can downscale before provider submission.
- Pillow `DecompressionBombWarning` exceptions are treated as `input_too_large` instead of falling back to the original PNG.
- The original upload remains unchanged in storage; only the data URI sent to the provider is normalized.
- Provider `RateLimitError` exceptions are now classified internally as `provider_rate_limited` and logged with token-free diagnostic fields.
- No DB migration, public API error-code change, new ENV variable, or frontend behavior change was introduced in this minimal slice.

The provider-side root cause is still not fully documented by Mistral. The known reproduction is avoided by no longer sending the original full-size PNG data URI directly to the provider.

Verification commands:

- `.venv/bin/pytest -q backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py backend/tests/learning_adapters/test_local_feedback_dspy.py`
- `.venv/bin/pytest -q backend/tests/test_learning_worker_feedback_error_mapping.py`
- `.venv/bin/pytest -q backend/tests/test_learning_worker_jobs.py -k feedback`
- `make verify`

## Impact

- A valid image submission can end in a terminal feedback failure even though
  retrying later may succeed.
- Learners and teachers receive a generic failure instead of a clear
  provider-busy state.
- Operations cannot easily distinguish provider rate limits from invalid image
  payloads without reading detailed logs.
- Provider error `rate_limited` can be misleading here because the observed
  failure reproduces for one PNG representation while smaller/JPEG variants of
  the same image succeed with the same key and model.

## Observed Context

- One genuine PNG image reached visual feedback processing.
- The provider returned rate-limit errors repeatedly.
- Current retry behavior exhausted the configured retry budget too quickly for
  a provider-capacity condition.
- The final state became a feedback failure even though the underlying upload
  was valid.

## Requeue Verification

The affected valid-image submission was reset with the existing operational
script using `--apply --limit 1`, after a dry-run confirmed that this targeted
only the newest active failed submission. The reset changed that submission back
to `analysis_status='pending'`, set the related job to `queued`, cleared the job
error, and reset the job retry counter to `0`.

The worker picked the job up again and loaded the same valid PNG image. The
provider then returned `RateLimitError` again on every feedback attempt. The
worker scheduled the normal retry sequence and finally marked the same
submission failed again with `error_code='feedback_failed'` and
`feedback_last_error='visual_feedback_failed'`.

This means the failure was reproducible after requeue. It did not disappear by
resetting the submission. The upload itself was not the limiting factor; the
current provider/model path was still rate-limited at retry time.

## File-Specific Finding

The failing upload is a valid PNG screenshot:

- format: PNG
- dimensions: 1920 x 1200
- mode: RGBA, fully opaque
- size: about 373 KB
- PNG chunks: normal image chunks plus `gAMA`/`sRGB`
- hash and stored size match the submission metadata

The image content itself is not corrupt and can be decoded locally. However, a
minimal provider request with this exact full-size PNG still returns HTTP 429
with provider error `type="rate_limited"` and `code="1300"`.

Control tests with variants of the same image showed:

- full-size original PNG: 429 `rate_limited`
- full-size RGB PNG without alpha: 429 `rate_limited`
- full-size JPEG version: 200 OK
- 960px-wide PNG version: 200 OK
- 960px/640px/480px-wide JPEG versions: 200 OK

Additional threshold tests showed:

- 1600px-wide PNG, about 374 KB / 499k base64 chars: 429
- 1440px-wide PNG, about 312 KB / 416k base64 chars: 429
- 1280px-wide PNG, about 266 KB / 354k base64 chars: 200 OK
- 1120px-wide PNG, about 227 KB / 303k base64 chars: 200 OK
- full-size blank white PNG, about 10 KB / 13k base64 chars: 200 OK
- full-size palette-quantized PNG, about 81 KB / 108k base64 chars: 200 OK

This points to the full-size PNG data-URI representation as the trigger. The
OpenAI-compatible Mistral path may be counting the large base64 image payload
toward token/rate-limit admission before or during image preprocessing. In that
case, account credit and normal dashboard usage cost can look fine while one
large PNG request is still rejected as rate-limited.

## Official Mistral Documentation Context

The public Mistral documentation does not describe this exact threshold or the
meaning of provider error code `1300`, but it gives useful boundaries:

- Vision accepts images by URL or base64 payload in chat/completions-style
  requests.
  - `https://docs.mistral.ai/studio-api/conversations/vision`
- Known Vision limitations list a maximum image size of 20 MB per image,
  supported image formats including PNG/JPEG/WebP, and note that images are
  resized internally.
  - `https://docs.mistral.ai/resources/known-limitations`
- Mistral rate limits are documented as request-per-second, token-per-minute,
  and token-per-month limits. HTTP 429 maps to "Too Many Requests".
  - `https://docs.mistral.ai/admin/user-management-finops/tier`
- The API reference states that prompt tokens plus `max_tokens` must fit inside
  the model context length.
  - `https://docs.mistral.ai/api`
- Mistral's own image-understanding cookbook converts local images to JPEG
  before base64 encoding them for requests.
  - `https://docs.mistral.ai/resources/cookbooks/mistral-image_understanding-batch_api_example`

The observed failing PNG is far below the documented 20 MB per-image limit, and
the same API key/model can process minimal text, minimal image, full-size JPEG,
and smaller PNG variants. Therefore the fix should not assume missing credit or
an invalid API key. Treat this as an undocumented provider admission behavior
for large PNG data-URI requests and normalize images before provider submission.

## Files Of Interest

- `backend/learning/adapters/local_feedback.py`
  - Visual feedback calls `visual_feedback_program.analyze_visual_feedback(...)`.
  - Generic exceptions are mapped through
    `_raise_feedback_error_for_exception(...)` with
    `default_transient_code="visual_feedback_failed"`.
  - Rate-limit exceptions need distinct classification from invalid payloads and
    generic visual feedback failures.
- `backend/learning/adapters/local_vision.py`
  - `_resolve_submission_image_bytes(...)` currently forwards the original
    image bytes as base64 and preserves the original MIME type.
  - Add a provider-bound normalization step for screenshots/large PNGs before
    building the data URI, preferably RGB conversion plus JPEG encoding and, if
    needed, downscaling under a configured pixel/byte budget.
- Learning worker configuration/runtime
  - Current production configuration observed `WORKER_MAX_RETRIES=3` and short
    exponential retry timing from `WORKER_BACKOFF_SECONDS`.
  - The implementation should classify provider rate limits distinctly before
    deciding whether retry behavior needs to change.
- Worker/job processing code that records `analysis_status`, retry count,
  failure reason, and next retry time.
  - Use the existing job state model where possible, but add a distinct
    provider-rate-limit reason if one does not exist.
- Tests around learning adapters and worker retry behavior.
  - Add focused tests for provider rate-limit classification and recovery.

## Required Behavior

- Classify provider rate-limit responses separately from:
  - invalid upload content,
  - unsupported MIME type,
  - malformed provider request,
  - generic transient visual feedback failure.
- Avoid immediate repeated provider calls when the provider explicitly reports
  rate limiting.
- Normalize large screenshot-style PNG uploads before provider calls so the
  data-URI payload stays below provider admission limits. Use JPEG for
  screenshot-style images unless a task requires PNG transparency.
- Keep the user-facing submission state as pending/retrying or provider busy
  while recovery is still possible.
- Do not mark a valid image submission as terminally failed after only a short
  burst of rate-limited attempts.
- Add PII-free logging/metrics for rate-limit frequency and retry outcomes.
- Capture provider-limit diagnostics without secrets:
  - HTTP status and provider error type/code,
  - `Retry-After` when present,
  - rate-limit response headers such as remaining/reset values when present,
  - provider request ID/correlation ID when present,
  - configured base URL host, model, feedback stage, modality, and worker
    attempt number,
  - a non-secret API-key/workspace label supplied by configuration, not the key
    value itself.
- Provide an operator-visible way to identify and requeue provider-rate-limited
  submissions after provider recovery.

## Test Scenarios

- Simulated provider `RateLimitError` on the first visual feedback attempt
  records a distinct rate-limit reason.
- Full-size screenshot PNG is converted/downscaled before visual feedback and
  no longer triggers provider 429 in the known reproduction case.
- Full-size JPEG and downscaled PNG variants of the same image remain accepted
  by the provider path.
- Simulated provider recovery after a rate-limit response completes the
  feedback successfully.
- Repeated provider rate limits remain distinguishable from invalid uploads and
  generic visual feedback failures.
- Final user-facing errors identify a provider availability/rate-limit
  condition rather than an invalid upload.
- Invalid image or bad-request provider errors do not use the long rate-limit
  retry path.

## Acceptance Criteria

1. Valid image submissions are not prematurely marked failed solely because the
   provider is temporarily rate-limited.
2. Provider rate limits are visible in structured, PII-free logs or metrics.
3. Learner-facing messaging distinguishes provider-busy/retrying from invalid
   upload and permanent feedback failure.
4. Provider rate-limit handling avoids tight repeated calls and records enough
   detail to diagnose which upstream limit was hit, including relevant
   provider headers and request IDs when available.
5. Large PNG screenshots are normalized before provider submission, while valid
   smaller PNG/JPEG uploads still work.
6. The known reproduction case no longer sends the original full-size PNG
   data URI directly to Mistral.
7. Tests cover both successful recovery and terminal provider-limit failure.
