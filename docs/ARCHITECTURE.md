# GUSTAV – Architektur

Stand: Version 0.0.4, zuletzt geprüft am 2026-08-16.

Dieses Dokument beschreibt die gegenwärtige Architektur von GUSTAV. Verbindliche Detailverträge liegen in `api/openapi.yml`, den Migrationen unter `supabase/migrations/` und den thematischen Referenzen unter `docs/references/`.

## Leitlinien

- **Pädagogik vor Technik:** Die Software unterstützt Lernen und professionelles pädagogisches Urteil.
- **KISS und Lehrbarkeit:** Schichten, Abhängigkeiten und Sicherheitsentscheidungen sollen auch für Lernende nachvollziehbar bleiben.
- **Security und Privacy by Design:** Autorisierung, Datensparsamkeit, RLS und bereinigte Fehlermeldungen sind Teil der Architektur.
- **Clean Architecture:** Fachliche Regeln bleiben von FastAPI, SvelteKit, DSPy, PostgreSQL und Supabase unabhängig.
- **Contract First:** Öffentliche HTTP-Verträge beginnen in `api/openapi.yml`.
- **TDD:** Verhalten wird durch Tests beschrieben, bevor die minimale Implementierung entsteht.
- **Lokal = Produktion:** Compose, Hostnamen, Migrationen, Sicherheitsgrenzen und Konfigurationsnamen sind in beiden Umgebungen gleich.

## Systemüberblick

```text
Browser
  |
  v
Caddy (TLS und Routing)
  |-- Produktoberfläche ----------> SvelteKit-Browser-BFF
  |                                  |
  |                                  v
  |-- /api, /health, interne BFF --> FastAPI-API-Adapter
  |                                  |
  |                                  v
  |                         Fachkontexte und Repositories
  |                                  |
  |                                  v
  |                         PostgreSQL / Supabase Storage
  |
  |-- /h5p -----------------------> isolierter H5P-Service
  |
  `-- id.localhost ---------------> Keycloak

Learning-Worker --> Learning Use Cases --> DSPy-Adapter --> konfigurierter KI-Anbieter
```

### SvelteKit-Browser-BFF

`frontend/` ist die produktive Weboberfläche. SvelteKit übernimmt:

- App-Shell, Navigation und rollenbezogene Arbeitsräume;
- serverseitige Seitenkomposition und View Models;
- kurzlebige Browser-BFF-Sessions und Token-Aktualisierung;
- sichere Weiterleitung von Lese- und Schreibzugriffen an FastAPI;
- UI-Zustände, Formulare, barrierefreie Rückmeldungen und progressive Interaktion.

Die Produkträume `learning`, `teaching`, `diagnostics` und `live` werden ausschließlich hier dargestellt. Das verbindliche visuelle System steht in `docs/DESIGN.md`.

### FastAPI-API-Adapter

`backend/web/` ist der HTTP- und Kompositionsadapter. FastAPI übernimmt:

- öffentliche, durch OpenAPI beschriebene Fachendpunkte;
- interne Browser-BFF-Endpunkte und den Auth-Bridge-Vertrag;
- Authentifizierungs- und Autorisierungsgrenzen;
- DTO-Validierung, HTTP-Fehlerabbildung und sichere Cache-Header;
- Wiring von Repositories, Storage, Workern und Laufzeitkonfiguration.

FastAPI registriert keine aktiven Legacy-Produktseiten mehr. Ehemalige SSR-/HTMX-Produktpfade werden ausschließlich über einen kleinen Retirement-Adapter kontrolliert mit `410 Gone` beziehungsweise einem sicheren Redirect beantwortet. Verbliebene HTML-Helfer dienen nur dieser Rückzugskompatibilität oder isolierten Inhalten wie Simulationsdarstellungen; sie sind kein zweites Frontend.

### Fachkontexte

Die fachliche Verantwortung ist in vier Bounded Contexts aufgeteilt:

- `identity_access`: Keycloak, Identität, Rollen, App- und BFF-Sessions sowie CLI-Tokens;
- `teaching`: Kurse, Mitgliedschaften, Kurseinladungen, Lerneinheiten, Modulgraphen, Inhalte und Freigaben;
- `learning`: Lernwege, Abgaben, Dialoge, KI-Verarbeitung, Portfolio, Exporte und Übungssitzungen;
- `diagnostics`: lesende, datensparsame Projektionen für Unterrichtsdiagnostik und Live-Begleitung.

Die fachliche Context Map steht in `docs/bounded_contexts.md`; kanonische Begriffe stehen in `docs/glossary.md`.

## Clean-Architecture-Schichten

### Fachlogik und Application Layer

Framework-unabhängige Use Cases und Services liegen in den jeweiligen Kontextpaketen, beispielsweise unter:

- `backend/learning/usecases/`;
- `backend/learning/practice/`;
- `backend/teaching/services/`;
- `backend/identity_access/`.

Ports werden als kleine Python-Protokolle an der konsumierenden Schicht definiert. Use Cases und Services importieren weder FastAPI noch Request-, Response- oder Router-Typen.

Nicht jede einfache CRUD-Operation besitzt eine eigene Use-Case-Klasse. Einige ältere API-Adapter orchestrieren Repository-Aufrufe noch direkt. Das ist begrenzter Refactoring-Spielraum innerhalb etablierter Grenzen und keine noch ausstehende Architektur-Migration. Neue Fachregeln gehören in framework-unabhängige Services oder Use Cases.

### Interface- und Infrastrukturadapter

- `backend/web/`: HTTP, Auth-Bridge, Serialisierung und Komposition;
- `backend/*/repo_db.py`: PostgreSQL-Adapter mit RLS- und Helper-Verträgen;
- `backend/learning/adapters/`: DSPy-, Vision-, Feedback- und Dialogadapter;
- `backend/storage/`: Binärspeicher-Ports und Supabase-Adapter;
- `backend/identity_access/`: Keycloak- und Sessionadapter;
- `h5p-service/`: isolierter H5P-Driver mit eigener Sicherheitsgrenze.

Direkte Datenbankverbindungen oder Supabase-Client-Erzeugung aus Routen sind verboten. `make test-architecture-boundaries` führt dafür `backend.tools.architecture_boundary_scan` gegen eine Null-Baseline aus und blockiert neues Grenzwachstum.

## Zentrale Abläufe

### Authentifizierter Browserzugriff

1. Der Browser ruft eine SvelteKit-Seite auf.
2. SvelteKit liest die serverseitige BFF-Session und erneuert Tokens bei Bedarf.
3. Der Browser-BFF ruft FastAPI mit der dafür vorgesehenen internen oder öffentlichen Authentifizierung auf.
4. FastAPI bildet die Identität auf einen minimalen User Context aus `sub`, Rollen und Anzeigename ab.
5. Repository und Datenbank erzwingen Ownership, Mitgliedschaft, Sichtbarkeit und RLS.
6. SvelteKit rendert das View Model; private Antworten bleiben `private, no-store`.

Details: `docs/references/auth_sessions_and_cookies.md` und `docs/references/user_management.md`.

### Teaching und Authoring

Lehrkräfte bearbeiten Kurse und wiederverwendbare Lerneinheiten im SvelteKit-Arbeitsraum. Die Oberfläche verwendet objektorientierte Teaching-Endpunkte für Mutationen und dedizierte Read Models für komplexe Räume. Modulare Lerneinheiten bestehen aus Phasen, Lernmodulen, Übungsmodulen, Abschnitten und gerichteten Kanten. Freigaben binden Inhalte an einen Kurs, ohne die wiederverwendbare Lerneinheit zu duplizieren.

Kurseinladungen gehören zum Teaching-Kontext. Pro aktivem Kurs existiert höchstens eine aktive, 24 Stunden gültige Einladung. Das Capability-Token liegt weder vollständig in PostgreSQL noch in Logs, reist ausschließlich im URL-Fragment und wird erst nach erfolgreichem Keycloak-Login beziehungsweise Registrierung eingelöst. Rotation, Widerruf, Archivierung und Einlösung sind atomar. QR-Codes werden lokal im Browser erzeugt; der Worker nutzt für einzelne Einladungsmails dasselbe konfigurierte SMTP-Relay wie Keycloak.

Details: `docs/references/teaching.md` und `docs/references/user_management.md`.

### Learning und KI-Verarbeitung

1. Eine lernende Person sieht nur freigegebene Inhalte ihres Kurses.
2. Abgaben werden idempotent gespeichert und erzeugen bei Bedarf einen Job.
3. Der Worker beansprucht Jobs konkurrierungssicher, führt externe KI-Aufrufe außerhalb von Datenbanktransaktionen aus und persistiert ausschließlich validierte Ergebnisse.
4. Vision-, Feedback- und Dialogprogramme verwenden DSPy über klar begrenzte Adapter.
5. Die Oberfläche lädt Status, Auswertung und formatives Feedback nach und unterstützt Überarbeitung beziehungsweise endgültige Abgabe.

Prompts, Schülertexte und Providerantworten werden nicht in Anwendungslogs geschrieben. Telemetrie beschränkt sich auf technische, bereinigte Zähler und Fehlercodes.

Details: `docs/references/learning.md` und `docs/references/learning_ai.md`.

### H5P

Der H5P-Service ist ein isolierter Driver. Browserzugriff erhält kurzlebige, zweckgebundene Berechtigungen. Inhalte und Bibliotheken gelten als vertrauenswürdiger ausführbarer Inhalt und dürfen nur durch berechtigte Lehrkräfte importiert oder bearbeitet werden. Same-Origin-, Cookie- und interner Service-Authentifizierungsschutz bleiben an jeder Übergabe erhalten.

## Daten, Sicherheit und Betrieb

- `supabase/migrations/` ist die einzige Quelle der Wahrheit für das Datenbankschema.
- Die Anwendung verwendet eine begrenzte Datenbankrolle; privilegierte Migrationen und Worker-Zugriffe sind getrennt.
- RLS und eng begrenzte `SECURITY DEFINER`-Funktionen schützen fachliche Projektionen und atomare Abläufe.
- Supabase Storage ist privat. Downloads und Uploads erfolgen über kurzlebige, geprüfte Intents oder Proxy-Grenzen.
- Secrets liegen ausschließlich in der Umgebung. Produktion und lokale Umgebung verwenden dieselben Namen und Startprüfungen.
- Personenbezogene Daten, Tokens, Prompts und Inhaltsdaten dürfen nicht in Logs, Beispielen oder öffentlichen Tickets erscheinen.
- Ein produktiver Schulbetrieb benötigt ein eigenes Datenschutz-, Backup-, Monitoring- und Wiederherstellungskonzept.

## Quellstruktur

- `frontend/` – SvelteKit-Produktoberfläche und Browser-BFF;
- `backend/web/` – FastAPI-API-Adapter und Runtime-Komposition;
- `backend/identity_access/` – Identität, Sessions und Keycloak-Adapter;
- `backend/teaching/` – Teaching-Modelle, Services und Persistenzadapter;
- `backend/learning/` – Learning Use Cases, Practice, Worker und KI-Adapter;
- `backend/storage/` – Storage-Ports und Adapter;
- `h5p-service/` – isolierter H5P-Service;
- `api/openapi.yml` – öffentlicher API-Vertrag;
- `supabase/migrations/` – versioniertes Datenbankschema;
- `reverse-proxy/` – Caddy-Konfiguration;
- `docs/` – Architektur, Referenzen, Entscheidungen und wissenschaftliche Grundlagen;
- `legacy-code-alpha1/` – historische Referenz, nicht Teil der aktiven Runtime.

## Qualitätsgrenzen

- `make verify` prüft Backend, Frontend, H5P, OpenAPI, Importgrenzen, Repository-Sicherheit und Dokumentationsverträge.
- `make verify-feature` ergänzt für nutzerseitige Änderungen den authentifizierten Browser-Rundlauf.
- `make test-architecture-boundaries` schützt Clean-Architecture-Grenzen mit `architecture-boundary-scan`.
- `make test-route-map` hält die technische Route Map synchron und bestätigt, dass es keine aktiven Legacy-Produktseiten gibt.
- `make docker-validate` prüft Compose-, Proxy- und Image-Verträge bei Infrastrukturänderungen.

Weitere Nachweise stehen unter `docs/harness/` und `docs/tests/e2e_howto.md`.
