# Reload-Kontinuität für Auth und modularen Lernraum

## Ziel
- Hard Reloads auf geschützten Svelte-Seiten sollen nicht mehr unnötig zur Loginseite führen, solange die BFF-Session refreshbar ist.
- Der modulare Lernraum soll nach Reload offene Module und vorhandene Entwürfe aus der serverseitigen Wahrheit wieder erreichbar machen.

## Entscheidungen
- `/api/app/session-bootstrap` bleibt bearer-only; es gibt keinen breiten App-Session-Cookie-Fallback für BFF-Flächen.
- Das SvelteKit-Layout ist die zentrale Bootstrap-Quelle. Page-Loads verwenden `parent()` statt erneut `/api/app/session-bootstrap` aufzurufen.
- Der BFF-Token-Refresh wird gegen parallele Reload-Requests gehärtet: Ein fehlgeschlagener Refresh/Persist löscht eine abgelaufene Session erst, wenn kein frisch gespeicherter Ersatz vorhanden ist.
- Der modulare Lernraum bleibt graph-first und lazy: Der Graph bestimmt, welche Module erreichbar sind; Inhalte und History werden gezielt nachgeladen.

## TDD
- Auth:
  - Test für konkurrierenden Refresh: Wenn ein zweiter Request die BFF-Session bereits erneuert hat, darf der erste Request die Session nicht löschen.
  - Contract-Test: Geschützte Svelte-Page-Loads nutzen Parent-Bootstrap statt direkten `session-bootstrap`-Fetch.
- Lernraum:
  - Workspace-Reconciliation soll serverseitig offene Module ergänzen, wenn der Reload aus leerem oder stale Client-State kommt.
  - Task-Karten zeigen vorhandene Entwürfe anhand der Task-Metadaten auch ohne bereits geladene History.

## Verifikation
- `npm --prefix frontend test -- --run frontend/src/lib/server/session.test.ts frontend/src/lib/learning-unit/workspace.test.ts frontend/src/routes/protected-page-bootstrap-contract.test.ts frontend/src/lib/components/learning-unit/LearningTaskCard.test.ts`
- `make verify`
