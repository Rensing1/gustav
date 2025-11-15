# Plan: Unify Supabase Buckets (materials, submissions)

Owner: Felix / GUSTAV Core
Status: Draft → To be executed
Last update: 2025-11-05

## Motivation
- Make bucket provisioning deterministic and versioned (via SQL migrations).
- Keep a symmetric, private-by-default security posture with signed URLs.
- Centralize configuration to avoid drift between teaching (materials) and learning (submissions).
- Reduce developer friction while avoiding risky auto-provisioning in prod.

## Scope & Assumptions
- Buckets in scope: `materials` (teaching) and `submissions` (learning).
- Both buckets remain private (no public read); clients use signed URLs only.
- Runtime auto-provisioning stays dev-only and opt-in.
- No breaking change to existing storage_key values; forward-compatible helpers only.

## Design Overview
- Source of truth: Supabase SQL migrations provision both buckets idempotently.
- Central config module defines defaults, size/MIME, and URL TTLs used across domains.
- Runtime bootstrap remains available (disabled by default) and reads the centralized config.
- Standardize storage_key path shape with helper functions (teaching/learning), without forcing uniqueness where not needed.

## Detailed Steps
1) Migration: provision `submissions` bucket
   - Add SQL mirroring the existing `materials` creation:
     - `insert into storage.buckets (id, name, public) select 'submissions','submissions', false where not exists (...)` guarded by feature detection for `storage.buckets`.
   - Rationale: determinstic provisioning across envs; matches `materials`.

2) Centralize storage configuration
   - Create a small Python module (e.g., `backend/storage/config.py`) exposing:
     - `MATERIALS_BUCKET_DEFAULT = "materials"`
     - `SUBMISSIONS_BUCKET_DEFAULT = "submissions"`
     - Allowed MIME sets, max size limits, URL TTLs (teaching/learning), all reading env with sane defaults.
   - Refactor `materials.py` and `web/routes/learning.py` to import these constants instead of hard-coded defaults.

3) Retain runtime bootstrap as dev-only fallback
   - Keep `backend/storage/bootstrap.ensure_buckets_from_env()` but:
     - Default `AUTO_CREATE_STORAGE_BUCKETS=false` in examples.
     - Emit a warning log if enabled and env != development.
     - Read bucket names from new config to avoid divergence.

4) Standardize storage_key schema (non-breaking)
   - Add helpers:
     - Teaching: `make_materials_key(unit_id, section_id, material_id, filename)` → `materials/{unit}/{section}/{material}/{uuid}.{ext}`.
     - Learning: keep current shape but move generation to a helper to centralize sanitization.
   - Keep DB constraints intact: `unit_materials.storage_key` partial unique index remains; `learning_submissions` relies on attempt keys and integrity constraints.

5) Security symmetry & policy alignment
   - Verify both domains use private buckets + signed URLs only.
   - Ensure MIME and size constraints match centralized policy (teaching vs learning can differ intentionally, but defined in one place).
   - Preserve upload-intents for teaching and integrity verification for learning.

6) Tests
   - Add a migration test that asserts presence and `public=false` for both buckets.
   - Unit tests for key-generation helpers (path shape, sanitization, length caps).
   - Adjust integration tests to import centralized config and confirm signed URL flows.
   - Negative tests for policy (MIME/size) alignment.

7) Documentation & Runbook
   - Update `/docs/ARCHITECTURE.md`: Storage governance and flow diagrams.
   - Update env reference in `README.md` (.env.example): defaults and when to use `AUTO_CREATE_STORAGE_BUCKETS`.
   - Add a short “Why private buckets?” and “Dev bootstrap safety” note.

8) Rollout & Migration Checklist
   - Staging:
     - Apply new migration; verify `materials` and `submissions` exist, `public=false`.
     - Ensure `AUTO_CREATE_STORAGE_BUCKETS=false` in staging/prod.
     - Smoke test uploads/downloads for teaching and learning.
   - Production:
     - Apply migration (idempotent).
     - Monitor logs for storage errors; verify signed URL flows.
   - Rollback:
     - Safe (migration is additive and idempotent). Runtime bootstrap provides a temporary fallback if needed.

## Open Questions
- Unify max size across domains (e.g., 10 MiB) or keep: teaching=20 MiB, learning=10 MiB?
- Should materials keys include `course_id` for easier triage, or keep unit/section/material only?
- Do we want optional per-course buckets later (out of scope now)?

## Acceptance Criteria
- Both buckets provisioned by migrations; no runtime dependency in prod.
- Centralized config consumed by both adapters; env overrides documented.
- Tests pass and cover provisioning, key helpers, and policy checks.
- Docs updated; rollout performed with no downtime.

