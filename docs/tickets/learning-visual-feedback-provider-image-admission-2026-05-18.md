# Ticket: Mistral image-admission failures for handwritten submissions

## Summary

Valid handwritten image submissions can fail deterministically in the Mistral visual-feedback provider path. The affected files are pedagogically valid student work and must be analyzable by GUSTAV. The existing large-PNG handling only improves failure classification and user guidance for one known image shape; it does not make the actual feedback generation more reliable.

No learner names, user IDs, course names, submission IDs, storage object paths, hashes, provider request IDs, or other PII are included in this ticket.

## Problem

The provider can reject a valid image input with HTTP `429` / throttling-style metadata even when the file is far below the documented maximum image size and uses a documented image format. The public Mistral documentation does not describe a deterministic image-content or image-rendition admission boundary that explains this behavior.

This matters because handwritten text images are a core Learning submission type. When a learner submits a photographed or scanned handwritten response, GUSTAV should preserve the original upload but send a provider-safe rendition to the visual-feedback model when the original rendition is likely to hit an undocumented provider admission boundary.

## Relationship To Previous Ticket

The earlier visual-feedback provider ticket documented a screenshot-like PNG that failed against Mistral and succeeded when represented differently. The implemented first fix intentionally kept the original provider bytes unchanged and added better diagnostics plus a clearer learner-facing message for large PNG inputs.

That first fix is insufficient for this follow-up:

- It does not make provider evaluation succeed.
- It only classifies the known large-PNG shape.
- JPEG inputs can hit the same provider-admission family but currently do not receive the same actionable UI message.
- A handwritten text submission is not comparable to an overloaded screenshot with unrelated visual UI content; it is exactly the type of work the system must evaluate reliably.

## Official Mistral Documentation Context

The public documentation gives useful boundaries but does not document the observed deterministic admission failure:

- Vision inputs are supported through the Chat Completions API, and images may be sent by URL or as base64 payloads:
  `https://docs.mistral.ai/studio-api/conversations/vision`
- Known Vision limitations currently list a maximum image size of 20 MB per image, supported formats `PNG`, `JPG`, `JPEG`, `GIF`, `WEBP`, and internal image resizing:
  `https://docs.mistral.ai/resources/known-limitations`
- Mistral rate limits are documented at organization level as requests per second, tokens per minute, and tokens per month:
  `https://docs.mistral.ai/admin/user-management-finops/tier`
- The error glossary lists HTTP `429` as "Too many requests" and documents the generic error response format, but it does not describe a stable image-rendition-specific admission code or threshold:
  `https://docs.mistral.ai/resources/error-glossary`
- The public `mistral-common` image-tokenization docs describe images as patch/grid inputs with configurable maximum image size and patching. This supports treating dimensions and rendition as provider-admission inputs, not only raw file bytes:
  `https://mistralai.github.io/mistral-common/usage/images/`

## Desired Product Behavior

- Handwritten image submissions should be evaluated successfully when the uploaded content is valid and readable.
- The stored original upload must remain unchanged for auditability and teacher review.
- The visual-feedback provider should receive a normalized, provider-safe rendition for image submissions where the original bytes are unnecessarily expensive or fragile for provider admission.
- JPEG admission failures should produce the same kind of actionable learner guidance as the known PNG case.
- Internal diagnostics must remain PII-free and must not include prompt text, student content, storage keys, hashes, or provider request IDs.

## Implementation Direction

Introduce a provider-rendition step before the visual-feedback provider call for direct image submissions:

- Decode the verified original upload server-side.
- Apply EXIF orientation and strip metadata.
- Convert to RGB.
- Bound the longest edge to a conservative provider-safe size, for example 1024-1280 px, while preserving aspect ratio and handwriting readability.
- Encode the provider-bound rendition as JPEG with stable quality, for example quality 85.
- Send the rendition to the provider as `data:image/jpeg;base64,...`.
- Persist only the regular analysis result; do not replace the original stored submission file.

If provider-rendition generation fails, fail with a clear internal reason rather than silently falling back to the fragile original representation.

## UI And Diagnostics

- Map deterministic image-admission failures for JPEG and PNG to a concrete German UI message that asks for a smaller or clearer image when needed.
- Keep internal codes out of learner-facing UI.
- Record PII-free diagnostics for both original and provider-bound rendition: MIME type, width, height, byte size, base64 length, and rendition strategy.
- Keep provider/model labels generic enough for operations but do not log student text, teacher context, object paths, hashes, or API keys.

## Acceptance Criteria

1. Valid handwritten JPEG and PNG submissions can be evaluated through a provider-safe image rendition.
2. The original uploaded file remains unchanged in storage and in teacher-facing artifact access.
3. JPEG and PNG provider-admission failures are classified consistently enough for the UI to show actionable German guidance.
4. The learner UI does not expose internal provider codes.
5. Diagnostics allow operators to compare original versus provider-bound image metadata without leaking PII.
6. Tests cover successful visual feedback using a normalized provider rendition for JPEG and PNG inputs.
7. Tests cover provider-admission failure UI mapping for JPEG and PNG inputs.
8. Tests verify that the provider call receives the normalized JPEG rendition while the stored original file is not rewritten.
