# Ticket: Modular unit file materials show title but no preview (no <img>)

**Status:** abgeschlossen

**Abschluss-Hinweis (2026-03-14):**
Das SSR-Modulfragment nutzt jetzt einen modularen Fallback-Resolver, wenn kein
linearer Section-Release-Pfad verfuegbar ist. Dabei bleiben
Kursmitgliedschaft, Unit-in-Course und
`modular_section_is_open_or_done_for_student(...)` verpflichtend. Verifiziert
mit den gezielten SSR-Tests in
`backend/tests/test_learning_modular_unit_page_ui.py`.

## Summary
In modular learning units, students can see file-material titles (e.g. an uploaded PNG/PDF), but the inline preview markup is missing entirely (no `<img>` / `<iframe>`). This blocks image-based materials in the modular workspace.

## Impact
- Students cannot view uploaded images/PDFs in modular units without leaving the platform (if any download fallback exists).
- Teachers perceive materials as “broken” even though the storage object exists.
- The issue is silent: SSR swallows errors and renders an empty preview.

## Reproduction (PII-free)
1. Create a **modular** unit (unit_type=`modular`) with at least one module (backed by a section).
2. Upload a file material (PNG/JPEG/PDF) into that module’s section.
3. Enroll a student and open the modular unit.
4. Open the module in the “Inhalte” view.
5. Observe: the material card shows the title, but there is no preview markup (`<img>` not present).

## Verified Findings
- `unit_materials` row exists with `kind='file'`, `mime_type` set, and a valid `storage_key`.
- The corresponding object exists in Supabase Storage (bucket `materials`).
- The modular content endpoint returns materials metadata but does not include `storage_key` (by design).
- SSR modular fragments attempt to resolve a preview URL via released-sections mapping; this fails for modular units because they do not use section releases.

## Root Cause
`/learning/.../modules/{module_id}/fragment` renders file materials only when it has a `preview_url`.

The fragment currently derives `section_id` via `/api/learning/.../units/{unit_id}/sections` and then calls a resolver that uses `get_released_materials_for_student(...)` (linear release mechanism).

For modular units, there are no section releases, so:
- the mapping/lookup returns nothing,
- `preview_url` remains empty,
- `FilePreview` renders nothing,
- the page contains no `<img>` / `<iframe>`.

## Fix Specification
### Scope
Backend SSR only (student modular module fragment). No DB schema changes required.

### Required changes
1. Add a modular-aware resolver that can presign `file_url` for a material in a module **under student scope**:
   - Validate course membership.
   - Validate unit belongs to course.
   - Resolve `section_id` from `unit_modules` (`module_id -> section_id`).
   - Enforce modular unlock: `modular_section_is_open_or_done_for_student(...)` must be true.
   - Fetch `storage_key` from `unit_materials` (id + section_id + kind='file').
   - Presign an inline URL via the server storage adapter (bucket from `get_materials_bucket()`).
   - Return only the signed URL (never expose storage_key to the client).

2. Wire this resolver into `learning_modular_unit_module_fragment` as a fallback when section mapping is unavailable.

3. Cache per-fragment request to avoid repeated DB queries/presigns for multiple materials.

### Non-goals
- Do not expose `storage_key` in student-facing APIs.
- Do not change modular unlock rules.
- Do not introduce new external endpoints if the SSR fragment can solve it safely.

## Files of Interest
- `backend/web/main.py` (SSR route `/learning/.../modules/{module_id}/fragment`)
- `backend/web/components/file_preview.py` (preview rendering)
- `backend/learning/repo_db.py` (modular unlock checks / helper functions)

## Acceptance Criteria
1. In a modular unit module fragment, file materials render a `FilePreview` with an `<img>` (images) or `<iframe>` (PDF).
2. Locked modules do **not** leak file URLs (fail-closed).
3. Behaviour for linear units and already-working paths remains unchanged.

## Test Scenarios
1. **No section mapping available**
   - Internal unit-sections lookup fails/returns empty.
   - Fragment still renders `data-file-preview="true"` markup for a file material.

2. **Module locked**
   - When module is locked for the student, fragment must not render a signed URL.

3. **Regression**
   - Existing section-mapping path continues to render previews unchanged.

## Risk Assessment
Medium-low. The change is localized to SSR fragment rendering but touches authorization boundaries. The fix must remain fail-closed and must not expose `storage_key` to the client.

## Follow-ups
- Signed URL TTL vs. `loading="lazy"`: very short TTLs can cause sporadic preview failures when students scroll later or keep the tab open for long periods. Consider longer TTL and/or a “reload preview” UX for materials similar to submission artifacts.
