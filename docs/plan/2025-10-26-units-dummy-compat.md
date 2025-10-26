Title: Units page supports dummy sections for repo-created units
Date: 2025-10-26
Author: Lehrer/Entwickler

User Story
- Als Lehrkraft möchte ich nach dem Erstellen einer Lerneinheit (über die Teaching‑API) die Seite „Abschnitte verwalten“ (/units/{id}) öffnen können, damit ich die Dummy‑Abschnitts‑Funktionalitäten (Anlegen/Löschen/Umsortieren) nutzen kann, auch wenn die Abschnitte noch nicht an die DB angebunden sind.

BDD Szenarien (Given‑When‑Then)
- Given ich bin als Lehrkraft angemeldet, When ich eine Lerneinheit via POST /api/teaching/units erstelle und anschließend /units/{id} öffne, Then rendert die Seite den Wrapper id="section-list-section" und ich kann einen Abschnitt erstellen (200, Fragment enthält Titel).
- Given eine ungültige/anders berechtigte unit_id, When ich /units/{id} öffne, Then erhalte ich 404.
- Given ich öffne /units/{id}, When ich Abschnitte per UI anlege/lösche/umordne, Then bleibt der Wrapper stabil und die CSRF‑Prüfung greift (bereits durch bestehende Tests abgedeckt).

API Contract‑First
- Keine neuen API‑Endpunkte erforderlich. Die SSR‑Route /units/{id} erhält eine reine Lookup‑Erweiterung (Repo‑Fallback). openapi.yml unverändert.

DB‑Migration
- Nicht erforderlich. Abschnitte bleiben in diesem Schritt weiterhin Dummy/In‑Memory.

Tests (RED)
- Neu: backend/tests/test_teaching_sections_ui.py::test_sections_page_supports_repo_created_unit_and_allows_create
  Prüft, dass /units/{repo_unit_id} die Dummy‑UI lädt und Erstellen funktioniert.

Implementierung (GREEN)
- backend/web/main.py: /units/{id}
  1) Unit‑Metadaten bevorzugt über Teaching‑Repo (get_unit_for_author bzw. Fallback‑Scan list_units_for_author), 2) Fallback auf lokale Dummy‑Liste, 3) Abschnitte weiterhin aus Dummy‑Store, 4) CSRF wie gewohnt.

Refactor/Notes
- Code kommentiert (Absicht, Verhalten, Berechtigungen). Späterer Schritt: Abschnitte an DB‑Repo anbinden und Dummy‑Store entfernen. CSP/CSRF bleiben unverändert.

