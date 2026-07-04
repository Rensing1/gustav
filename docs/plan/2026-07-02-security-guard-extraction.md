# Security Guard Extraction

Status: Implemented as first PR 14 slice in working tree
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_web_security_guards_contract.py backend/tests/test_auth_middleware.py backend/tests/test_api_auth_unauthenticated.py backend/tests/test_bff_authorization_session_api.py`
CI status: `make harness-minimum` prüft den Guard-Contract; `make verify` führt die breiteren Security- und Auth-Suites aus.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`, `docs/plan/2026-07-02-architecture-boundary-rules.md`
Review cadence: nach jedem Guard-/Authz-Refactor

## Zweck
PR 14 beginnt die Extraktion wiederverwendbarer Security Guards. Der erste Schnitt zentralisiert Rollenprüfungen für Web-Adapter in `backend/web/security/guards.py` und entfernt lokale Duplikate aus `backend/web/routes/app.py` und `backend/web/routes/users.py`; `operations.py` nutzt denselben Guard für teacher/operator.

## User Story
Als Produktverantwortlicher will ich, dass wiederkehrende Rollenprüfungen zentral und testbar sind, damit Security-Semantik beim Refactor nicht versehentlich driftet.

## BDD-Szenarien
- Given ein Nutzer hat nur das Primärfeld `role`, when `has_role` aufgerufen wird, then wird diese Rolle erkannt.
- Given ein Nutzer hat eine `roles`-Liste mit gemischter Groß-/Kleinschreibung, when `has_role` oder `has_any_role` aufgerufen wird, then wird case-insensitiv geprüft.
- Given ein Route-Modul braucht teacher/admin oder teacher/operator, when es Rollen prüft, then nutzt es das zentrale Guard-Modul statt lokaler Duplikate.

## Teststrategie
- Rot: `backend/tests/test_web_security_guards_contract.py` forderte das neue Guard-Modul und die Entfernung lokaler Duplikate.
- Grün: `backend/web/security/guards.py` stellt `normalized_roles`, `has_role` und `has_any_role` bereit.
- Refactor: `app.py`, `users.py` und `operations.py` nutzen die zentralen Rollen-Guards.

## Evidenz
- Rot: `.venv/bin/pytest -q backend/tests/test_web_security_guards_contract.py` → 2 failed, weil das Guard-Modul fehlte.
- Grün: `.venv/bin/pytest -q backend/tests/test_web_security_guards_contract.py backend/tests/test_auth_middleware.py backend/tests/test_api_auth_unauthenticated.py backend/tests/test_bff_authorization_session_api.py` → 36 passed.
- Grün: `make harness-minimum` → 105 passed; Docker-Compose-Konfiguration valide.

## Offene Arbeit
- Größere Authz-/CSRF-Guards in späteren PR14-Schnitten aus Route-Monolithen extrahieren.
- Alte Tests mit flachen `routes.*`-Monkeypatches im PR9-Testimport-Cleanup auf package-orientierte Imports umstellen.
