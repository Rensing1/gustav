Title: Testing environment hardening — dotenv guard & auth state isolation

Date: 2025-11-05
Authors: GUSTAV Lehrteam
Status: In progress

Context
- Upload-Proxy- und Auth-Tests liefern bei einzelnen Kollegen 400/502, sobald pytest produktive `.env`-Werte einliest.
- Globale OIDC-State-Verwaltung (`main.STATE_STORE`) wird zwischen Tests nicht zurückgesetzt; Folgetests sehen abgelaufene/nonce-fremde Zustände.
- Ziel: Testumgebung deterministisch halten, ohne produktive Secrets zu laden, und globale Auth-States pro Testlauf isolieren.

Objectives
- Dotenv-Ladevorgang in `backend/tests/conftest.py` nur aktivieren, wenn RUN_E2E=1 (E2E erwartet produktive Umgebungswerte).
- Autouse-Fixture ergänzen, die `main.STATE_STORE` vor jedem Test zurücksetzt.
- Begleitende Tests erstellen, die die Guards erzwingen (TDD).

Out of scope
- Keine Änderungen an Produktionsstart oder API-Verträgen.
- Kein Umbau der bestehenden Upload-/Auth-Routen.

Risks & Mitigations
- Risiko: Reload von `backend.tests.conftest` im Test könnte seitliche Effekte haben. Mit Rück-Reload und Wiederherstellung des echten `dotenv`-Moduls absichern.
- Risiko: Zusätzliche Autouse-Fixture verlangsamt Tests. Erwartet minimal, da nur Reset eines kleinen Dicts.

Test strategy
- Neuer Pytest (`backend/tests/test_testing_environment_guards.py`) prüft, dass `load_dotenv` bei RUN_E2E≠1 nicht aufgerufen wird und dass die State-Reset-Fixture existiert und wirkt.
- Bestehende Auth-/Upload-Tests laufen unverändert als Regression.
