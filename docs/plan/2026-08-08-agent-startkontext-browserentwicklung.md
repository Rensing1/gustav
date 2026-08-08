# Dauerhafter Agent-Startkontext für lokale Browserentwicklung

**Status:** Implementiert

## Ziel

Künftige Entwicklungsagenten beginnen ohne Gesprächskontext. Die zwei wiederkehrenden Grundlagen für Browserarbeit müssen deshalb bereits im automatisch geladenen Arbeitskontext sichtbar sein:

- Zertifikatsfehler bei `app.localhost` und `id.localhost` werden über die lokale Caddy-CA behoben und niemals durch Abschalten der TLS-Prüfung umgangen.
- Die feste Lehrkraft- und Schüler-Persona samt modularer Testlandschaft ist das bevorzugte Instrument für manuelle und automatisierte Browserprüfungen.

## Umsetzung

- Das lokal verwaltete, absichtlich nicht versionierte `AGENTS.md` erhält eine kurze verpflichtende Browser-Checkliste und verweist für Einzelheiten auf die versionierte E2E-Anleitung.
- Das öffentliche `README.md` erhält denselben Einstieg in kompakter Form, damit die Information auch nach einem frischen Clone auffindbar bleibt.
- Die ausführlichen Betriebs-, Sicherheits- und Resetregeln bleiben zentral in `docs/tests/e2e_howto.md` und `docs/references/make_targets.md`; sie werden nicht dupliziert.

## Abgrenzung und Verifikation

Es handelt sich ausschließlich um Dokumentation. API-Vertrag, Datenbank und Produktverhalten ändern sich nicht; daher sind weder Migration noch automatisierter Feature-Test erforderlich. Geprüft werden die Verweise, die Git-Diff-Hygiene und die Beschränkung des Commits auf die versionierte Dokumentation dieses Schritts.
