# Learning Submission-History Course-Context Guard

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Der Lernraum setzt keine Submission-History-Requests mehr mit fehlendem Kurs- oder Aufgabenkontext ab.

**Architecture:** Der Backend-Vertrag bleibt UUID-streng und fail-closed. Der Fix sitzt an der Frontend-Boundary, an der Verlauf-URLs gebaut werden: Ein kleiner gemeinsamer Helper validiert nur, ob Kurs- und Aufgaben-IDs als nutzbare Route-Segmente vorhanden sind, ohne die Backend-UUID-Prüfung zu duplizieren.

**Tech Stack:** SvelteKit, Svelte 5, Vitest, Testing Library, FastAPI/OpenAPI als unveränderter Backend-Vertrag.

Referenz-Ticket: `docs/tickets/learning-submission-history-undefined-course-id-2026-05-28.md`

## Ticketverständnis

Das Ticket beschreibt einen einzelnen Produktions-Request auf `/api/learning/courses/undefined/.../submissions`. Anschaulich: Die UI wollte den Lernverlauf einer Aufgabe laden, hatte aber beim Zusammenbauen der Adresse keinen echten Kursausweis im Zustand. JavaScript hat daraus nicht "fehlender Wert", sondern den Text `undefined` in der URL gemacht.

Das Backend verhält sich korrekt: `backend/web/routes/learning.py` validiert `course_id` und `task_id` als UUID und antwortet bei `undefined` mit HTTP 400. Die Ursache sitzt deshalb im Frontend: `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte` und die ältere `LearningSubmissionWorkspace.svelte` bauen Submission-History-URLs ohne vorherigen Runtime-Guard.

## User Story und BDD

Als Lernende möchte ich meine Abgabe und Rückmeldung öffnen können, ohne dass die UI bei kurzzeitig fehlendem Kurskontext ungültige API-Aufrufe absetzt, damit der Lernraum bedienbar bleibt und echte Fehler nicht durch vermeidbare 400er verdeckt werden.

- Given `courseId` und `taskId` sind gültige nichtleere Strings, When die Lernende "Meine Abgabe" öffnet, Then lädt die UI `/api/learning/courses/{courseId}/tasks/{taskId}/submissions?limit=10&offset=0`.
- Given `courseId` ist `undefined`, `null`, leer, whitespace oder der String `"undefined"`, When die Lernende den Verlauf öffnet, Then wird kein `fetch()` abgesetzt und die UI zeigt eine lokale Verlauf-Fehlermeldung.
- Given `taskId` ist `undefined`, `null`, leer, whitespace oder der String `"undefined"`, When die UI Verlauf oder Polling starten würde, Then wird kein `fetch()` abgesetzt.
- Given das Backend erhält dennoch `/api/learning/courses/undefined/.../submissions`, When der Request ankommt, Then bleibt HTTP 400 `invalid_uuid` unverändert.
- Given die alte `LearningSubmissionWorkspace.svelte` wird in Tests oder künftig wiederverwendet, When ihr Kurskontext fehlt, Then konserviert sie dieselbe Guard-Semantik.

## Contract-First-Entwurf

- `api/openapi.yml` bleibt unverändert: `course_id` und `task_id` sind weiterhin UUID-Pfadparameter.
- Keine Supabase/PostgreSQL-Migration ist nötig.
- Keine neue öffentliche API wird eingeführt.

## Umsetzung

- [x] Neuen Helper `frontend/src/lib/utils/learning-submission-history-url.ts` testgetrieben ergänzen:
  - `isUsableLearningRouteId(value: unknown): value is string`
  - `buildLearningSubmissionHistoryUrl(courseId: unknown, taskId: unknown): string | null`
  - `MISSING_SUBMISSION_HISTORY_CONTEXT_MESSAGE`
- [x] `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte` in `loadSubmissionHistory(taskId)` vor dem `fetch()` guardieren; bei fehlendem Kontext lokal `history_missing_context` auslösen und im bestehenden Fehlerpfad eine verständliche Verlaufsmeldung setzen.
- [x] `pollFeedbackSubmission(...)` nutzt denselben guarded Fetch indirekt und bricht kontrolliert ab, statt ohne gültigen Kurskontext weiterzupollen.
- [x] `frontend/src/lib/components/learning-unit/LearningSubmissionWorkspace.svelte` auf denselben Helper umstellen, damit die Altkomponente keine veraltete Semantik konserviert.

## Test Plan

- `frontend/src/lib/utils/learning-submission-history-url.test.ts`: gültige IDs erzeugen exakt die erwartete URL; `undefined`, `null`, `""`, `"   "`, `"undefined"` und `"null"` liefern `null`.
- `frontend/src/lib/components/learning-unit/LearningSubmissionWorkspace.test.ts`: Rendering mit `courseId="undefined"` und `initialTab="history"` setzt keinen `fetch()` ab und zeigt eine lokale Verlauf-Fehlermeldung.
- `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/page-contract.test.ts`: `+page.svelte` importiert den Helper, ruft ihn vor dem Submission-History-`fetch()` auf und behandelt `history_missing_context` separat.
- Fokussiert: `cd frontend && npm test -- --run src/lib/utils/learning-submission-history-url.test.ts src/lib/components/learning-unit/LearningSubmissionWorkspace.test.ts src/routes/learning/courses/[courseId]/units/[unitId]/page-contract.test.ts`
- Abschluss: `cd frontend && npm run check`; danach `make verify`.

## Annahmen

- Der Fix bleibt bewusst clientseitig eng auf Submission-History beschränkt.
- Das Frontend prüft nicht auf UUID-Format, weil die Backend-Validierung die Quelle der Wahrheit bleibt und bestehende Frontend-Tests teilweise lesbare Fixture-IDs verwenden.
- OpenAPI und Datenbank bleiben unverändert.
