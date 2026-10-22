# Security-Update vom 22.10.2026

## Auftrag und Grenzen

User Story: Als Lehrkraft und Schüler möchte ich GUSTAV mit gepflegten, überprüften Abhängigkeiten nutzen, ohne bestehende Anmelde-, Lern- oder Uploadfunktionen zu verlieren.

Basis ist ausschließlich origin/master (3ac665c54a7573e13526711eee65af767f8bf53f). Der isolierte Branch enthält keine lokalen Zusatzcommits, Produktionsdaten oder Betriebsunterlagen. Es erfolgt kein Produktionsrollout. Öffentliche HTTP-Verträge und GUSTAV-Schemata bleiben unverändert; Keycloaks interne Migration wird isoliert geprüft.

## Umsetzung in Red–Green–Refactor-Schritten

1. Sicherheitsverträge für Versionsuntergrenzen, Tokenverifikation, Markdown und Uploads ergänzen; Fehler vor Umsetzung nachweisen.
2. Node 24.22.1, Python 3.11.17, Caddy 2.11.7, Keycloak 26.8.1, bcrypt-Provider 1.7.0 und PostgreSQL 16.15 pinnen. Provider gegen exakt dieselbe Keycloak-Version testen.
3. Frontend- und H5P-Abhängigkeiten aktualisieren. image-size 2.0.4 benötigt im Lumi-Adapter imageSizeFromFile für Dateipfade. Frühe Upload-Fehler und Abbrüche müssen temporäre Dateien bereinigen.
4. python-jose/ecdsa durch PyJWT 2.15.1 ersetzen. RS256, issuer, audiences, zeitliche Grenzen, nonce, subject-Bindung und koordinierter JWKS-Refresh bleiben erhalten.
5. Die Python-Mindestversionen des Auftrags übernehmen. LiteLLM und Supabase/HTTPX konsistent aktualisieren; DSPy 3.4.1 gezielt migrieren.
6. Den gewählten sicheren Festplatten-Cache mit diskcache-community 5.8.1 umsetzen. Ein kleiner, nachvollziehbarer DSPy-Patch ersetzt die Pflichtabhängigkeit und erzwingt SafeDisk mit eng begrenzten Datenklassen. Kein unsicherer Fallback. Neuer Cache-Unterordner, keine Übernahme alter Pickle-Dateien. Manipulierte Einträge sind Cache-Misses.
7. Ein deterministisch gebautes DSPy-Wheel 3.4.1+gustav.1 aus geprüftem Upstream-Artefakt und versioniertem Patch erzeugen. make lock-python erzeugt beide vollständigen Hash-Locks. Installation mit Hashprüfung und pip check; Upstream-DSPy zusätzlich auditieren.
8. Supply-Chain-Inventar und DSPy-Baseline aktualisieren; alle Gates ausführen und ausschließlich tatsächlich erfolgreiche Nachweise dokumentieren.

## BDD und Testzuordnung

| Given – When – Then | Automatisierter Test |
| --- | --- |
| Signierte gültige/ungültige Tokens – Login/Refresh – nur gültige Identität wird akzeptiert | Token-, Session-, Bearer- und JWKS-Pytests |
| Große/pathologische Markdown-Eingabe – Rendering – sichere Ausgabe ohne Hängen | Markdown-Vitest und begrenzter separater Prozess |
| Erlaubter/verbotener/zu großer/abgebrochener Upload – Multipart-Verarbeitung – Grenzen greifen, keine Restdateien | H5P-Node-Integrationstests |
| Bild als Bytes/Dateipfad – Lumi-Upload – korrekte Maße oder definierter Fehler | image-size-Kompatibilitätstest |
| Gültiger/manipulierter Cache – Lesen nach Neustart – persistenter Treffer oder sicherer Miss ohne Codeausführung | DSPy-Cache-Integrationstests |
| Lehrkraft/Schüler – authentifizierter Aufgaben-/Markdown-/H5P-Rundlauf – bestehende Abläufe bleiben nutzbar | security-update.spec.ts mit @feature-acceptance |

Zusätzlich: Bild/PDF-Regressionen, KI-Verträge für Text/Dialog/Vision und Verbrauchserfassung. Keycloak-Smoke mit leerer PostgreSQL-Datenbank, Discovery und synthetischem bcrypt-Konto; Upgrade-Smoke mit synthetischem Altbestand.

## Abnahme und Freigabe

Pflicht: make test; make test-frontend-h5p; make test-docker-image-smoke; make supply-chain-check; make dependency-audit; make docker-validate; make verify-feature FEATURE=security-update. Vor Browsertests make local-ca-status. Locks zweimal identisch erzeugen. Keine Advisory-Unterdrückung oder gelockerten Schwellen. Fehler und nicht ausgeführte Prüfungen sind Freigabeblocker, keine bestandenen Tests.

## Upgrade und Rollback

Keycloak: Vor einer späteren Migration Datenbank sichern. Rollback nur mit vorheriger Datenbanksicherung, vorherigem Image und dazugehörigem bcrypt-Provider; kein Downgrade auf bereits migriertem Schema. Der neue Cache ist abgeleiteter Zustand, bleibt von alten Dateien getrennt und wird bei Bedarf neu aufgebaut. Keine automatische Rückkonvertierung.

## Kompatibilitätsentscheidungen

- LiteLLM 1.88.6 verlangt `httpx>=0.28.0,<1.0`, `openai>=2.20.0,<3.0.0` und `importlib-metadata>=8.0.0,<9.0`. Deshalb werden HTTPX 0.28.1, OpenAI 2.20.0 und importlib-metadata 8.5.0 ausdrücklich gepinnt. Supabase 2.33.0 löst den bisherigen HTTPX-Konflikt; aiohttp 3.14.4 verlangt zusätzlich yarl mindestens 1.25.1. Die übrigen AI-Constraints bleiben explizit.
- Der ursprüngliche Pfad `dspy → diskcache>=5.6.0 → diskcache 5.6.3` enthält CVE-2025-69872 ohne sichere Veröffentlichung des Originalpakets. Er wird vollständig durch das überprüfte lokale DSPy-Wheel und `diskcache-community==5.8.1` mit erzwungener SafeDisk-Konfiguration ersetzt. Alte Pickle-Dateien werden nie geöffnet. Tests prüfen echte Prozessneustarts, manipulierte Pickles, Dateipfadausbrüche und die Ablehnung zusätzlicher Typfreigaben. LiteLLMs optionales `caching`-Extra wird nicht installiert, da es das Original-diskcache wieder einführen würde.
- Das Audit kann die lokale DSPy-Versionskennung nicht bei PyPI zuordnen. Deshalb werden alle tatsächlich aufgelösten Abhängigkeiten und zusätzlich die exakte unveränderte DSPy-Upstream-Version geprüft. Es gibt keine Advisory-Ignore-Liste und keine gelockerten Schwellwerte. Der lokale Patch bleibt eine eigene Wartungsverantwortung; nach einer geeigneten Upstream-Behebung wird er mit denselben Sicherheits- und KI-Vertragstests abgelöst.
- WeasyPrint 70 benötigt `URLFetcherResponse` statt des bisherigen Dictionaries. Der Adapter gibt ausschließlich bereits autorisierte Bytes aus dem Speicher zurück. HTTPS-, Datei- und Data-URLs außerhalb dieser Menge werden abgewiesen; fatale Ladefehler werden in den vorhandenen PDF-Fehlervertrag übersetzt.
- H5P verwendet für image-size 2 die asynchrone Dateischnittstelle. Der kleine Lumi-Patch prüft die vollständige Eingangsdatei per SHA-256 und bricht bei Abweichungen ab. Uploadbereinigung läuft auch bei vorzeitiger Antwort und Verbindungsabbruch. Compose aktiviert den bereits vorgesehenen einzelnen internen Proxy-Hop; ohne diese Konfiguration werden Weiterleitungsheader ignoriert.
- Zusätzlich werden Vite auf 6.4.5, Vitest auf 4.1.12, DOMPurify auf 3.4.17 und sanitize-html auf 2.18.1 angehoben, weil niedrigere Mindeststände weitere Audit-Funde beließen.
- Der Upgrade-Test enthält eine ausschließlich synthetisch verwendete Keycloak-26.7.3-/bcrypt-1.6.0-Testvorlage. Sie ist kein ausgeliefertes Runtime-Image. Ihre Build-Helfer sind ebenfalls gepinnt; die Provider-Quelle wird per SHA-256 geprüft. Dadurch funktioniert der Test auch nach dem Merge und in flachen Checkouts.

## Nachweise

- Beide vollständigen Hash-Locks zweimal mit `make lock-python` erzeugt und mit SHA-256 bytegenau verglichen; `pip check` erfolgreich.
- `make dependency-audit`: Frontend und H5P jeweils 0 Funde, Python und zusätzliche DSPy-Upstream-Prüfung ohne bekannte Schwachstellen. Keine fixlosen Funde im ausgelieferten Python-/Node-Abhängigkeitsbaum verbleibend.
- `make supply-chain-check`, `make docker-validate` und lokale CA-Prüfung erfolgreich.
- Caddy-Image isoliert gebaut und tatsächliche Version 2.11.7 geprüft.
- `make verify-feature FEATURE=security-update` vollständig erfolgreich: 3181 Backend-Tests bestanden, 35 reguläre Opt-in-Tests übersprungen; 845 Frontend-Tests und 74 H5P-Tests bestanden; authentifizierter Browserrundlauf erfolgreich. Darin enthalten: `make test`, `make test-frontend-h5p`, `make test-docker-image-smoke` sowie Architektur-, API-, Datenbankinventar- und Lint-Gates.
- Keycloak-Smokes: beide Fälle erfolgreich (leere PostgreSQL-Datenbank und synthetisches Schema-Upgrade mit Passwortprüfung). Der neue bcrypt-Provider wird gegen exakt Keycloak 26.8.1 gebaut.
- Der Browsernachweis lief mit Node 24.22.1, Python 3.11.17 und einem temporären Keycloak 26.8.1 auf leerer PostgreSQL-16.15-Datenbank. Konten verwendeten ausschließlich die im öffentlichen Realm erlaubte Beispieldomain. Bereinigung aller laufbezogenen Konten, Kurse, Einheiten, Sessions, Tokens und H5P-Inhalte wurde bestätigt. Der vorherige lokale Identitätscontainer und die vorherigen Anwendungsimages wurden danach wiederhergestellt.
- Änderungen bleiben zunächst ausschließlich auf dem lokalen Security-Branch zur späteren Integration mit UI-Änderungen. Kein Push, kein PR und kein Produktionsrollout. Nach dieser Integration sind die Gates für den zusammengeführten Stand erneut erforderlich.
