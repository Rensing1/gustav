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

Die synchrone Arbeit der Live-Abgabezusammenfassung wird als zusammenhängender Aufruf im begrenzten Threadpool ausgeführt. `backend/teaching/live_tasks.py` liest Aufgaben einmal gebündelt für die Einheit und ordnet sie ausdrücklich nach Abschnittsposition und Aufgabenposition. Der kleine Leseport kennt kein FastAPI; Berechtigungsprüfung und HTTP-Antwort bleiben im Adapter. Echte DB-Tests sichern konstante Aufgabenabfragezahl und Reihenfolge, ein synchronisierter Test die Freigabe des Event Loops. Die vollständige Ablösung globaler Route-Provider ist davon getrennt und noch offen.

Die Profilrouten sind der erste vollständig appbezogene Bereich dieser Provider-Migration: `create_app(profile_providers=...)` bindet typisierte Identity-/Claims-Provider an genau eine App. Die Standardverdrahtung verwendet deren OIDC-Laufzeit und erzeugt einen frischen Admin-Client pro Aufruf. `backend/identity_access/profile.py` enthält die frameworkunabhängigen Profilregeln einschließlich Attributerhalt und 180-Tage-Namenssperre; Normalisierung liegt daneben in `profile_helpers.py`. CLI-Verwaltung und Authentifizierung greifen auf denselben appbezogenen Token-Store zu. Alle sechs Profil-/CLI-Handler sind synchrone FastAPI-Handler und laufen deshalb im begrenzten Threadpool. Sie benötigen keine dynamische App-Fassade oder Endpoint-Globals-Reparatur. Die optionale Factory-Abhängigkeit `access_token_verifier` ermöglicht isolierte Auth-Adaptertests bei unveränderter Middleware. Teaching/Learning und die übrigen BFF-Bereiche sind damit noch nicht vollständig migriert.

Der Kummerkasten ist als zweiter Bereich appbezogen: `create_app(concern_box_providers=...)` bindet den verzögert erzeugten RLS-Repository-Adapter und die kanonische Namensauflösung. `backend/teaching/services/concern_box.py` kapselt Kursauswahl, Mitgliedschaftsprüfung und die öffentliche Posteingangsprojektion ohne HTTP-Abhängigkeit. Ausschließlich benannte Beiträge erreichen die Namensauflösung; interne Subject-IDs fehlen in der Antwort. Die fünf synchronen Handler in `app_concern_box_routes.py` laufen im begrenzten Threadpool und greifen auf keine dynamische Route-Fassade zu. Die bestehende atomare Mitgliedschaftsprüfung beim Schreiben sowie die Eigentümer-RLS bleiben erhalten. Die Home-Router sind davon getrennt und besitzen inzwischen ihre eigene explizite Verdrahtung.

Für Lernraum-Startseite, persönliche Kursliste und Kurs-Lerneinheiten stellt `create_app(learning_course_providers=...)` den Datenbankzugang ausdrücklich bereit. Die beiden Kurs-Handler liegen in `learning_course_routes.py`, die Startseite bleibt in `app_learner_view_routes.py`. Beide verwenden die bestehenden Kurs-Anwendungsfälle; `LearnerHomeUseCase` ergänzt nur die Home-Projektion. Alle drei Handler führen synchrone DB-Arbeit im begrenzten Threadpool aus, ohne Rückgriff auf globale Learning-Repositories oder die App-Fassade. Die bisherigen Mitgliedschafts-/Archivregeln, Seitenbegrenzungen, Reihenfolge und privaten Antworten bleiben bestehen.

Lehrer-Startseite und Lerneinheitenkatalog erhalten ihren Datenbankzugang über `create_app(teacher_catalog_providers=...)`. `UnitCatalogService` in `backend/teaching/services/unit_catalog.py` bündelt Status-, Such-, Sortier- und Kurszuordnungsregeln ohne Kenntnis von FastAPI. Beide synchronen Handler verwenden dieselben eigentümergebundenen Repository-Operationen; die Startseite übernimmt die ersten drei Katalogeinträge und liest ihre Kursliste nur einmal. Die noch vorhandenen Abfragen pro Kurs und Einheit sind eine getrennte, offene Performanceschuld (TD-009).

Der Inhaltseditor erhält seinen Datenzugang über `create_app(teacher_editor_providers=...)`. `NodeEditorService` prüft den Autor und ordnet dem angefragten Abschnitt oder Modul die Materialien und Aufgaben zu. Bei Modulen verwendet er ausschließlich deren einheitengebundene Backing-Section. Die bestehenden 403-/404-Regeln und privaten Antworten bleiben erhalten. Die reine Aufgaben-Normalisierung liegt in `teaching/task_payload.py`; `teaching_serialization._serialize_task` bleibt ein statischer Alias für übrige Aufrufer. Der Editor verwendet keine globalen Teaching-Provider oder Workspace-Helfer; sein synchroner HTTP-Handler arbeitet im begrenzten Threadpool.

Der Lehrkraft-Workspace erhält seinen Datenzugang über `create_app(teacher_workspace_providers=...)`. `UnitWorkspaceService` prüft die Autorenschaft und bereitet lineare Abschnitte beziehungsweise modulare Phasen, Knoten und Kanten auf. Auswahlpriorität, Inhaltszähler und private 400-/403-/404-/503-Antworten bleiben erhalten. Der synchrone Handler benötigt keine globalen Teaching-Provider; ausschließlich Live-/Diagnostikansichten verwenden noch die verbliebenen Legacy-Helfer in `app_teacher_unit_routes.py` (TD-004). Die gemeinsamen Geometrieprüfungen gelten weiterhin für beide Rollen.

Der Schülergraph erhält seinen getrennten Datenzugang über `create_app(learning_graph_providers=...)`. `LearningGraphUseCase` prüft Kursmitgliedschaft, Einheitenzuordnung und modularen Einheitentyp über die bisherigen Repository-Operationen. Die eigentliche Graphabfrage prüft die Mitgliedschaft erneut und verwendet weiterhin die zentrale SQL-Freischaltung; es gibt keinen zweiten Statusalgorithmus. `learning_graph_routes.py` enthält den synchronen HTTP-Handler mit unveränderten UUID-, Fehler- und Cache-Regeln einschließlich `Vary: Origin`, ohne globale Learning-Fassade.

Die Modulinhalte verwenden `create_app(learning_module_providers=...)` und `LearningModuleUseCase`. Graph und Inhaltszugriff teilen die frameworkunabhängige Zuordnungsprüfung in `modular_unit_access.py`; die erneute Prüfung im jeweiligen DB-Lesezugriff bleibt erhalten. `learning_module_routes.py` verarbeitet HTTP im begrenzten Threadpool. Modulinhalt und anschließende Materialsichtbarkeitsabfrage verwenden denselben ausdrücklich übergebenen Adapter. Die URL-Projektion für lineare Abschnitte und Module ist gemeinsam; sie erzeugt nur bei bestätigter Sichtbarkeit und passendem Materialtyp einen Link und verändert die Eingabedaten nicht.

Die drei Materialabrufe (Datei, historischer Abschnitts-Alias und Simulation) erhalten ihre DB-, Storage- und Download-Abhängigkeiten über `create_app(learning_material_providers=...)`. Die vorhandenen SQL-Helfer prüfen beim Abruf erneut Mitgliedschaft und Freigabe beziehungsweise Modulstatus. Repository-Aufbau, Metadatenabfrage und Storage-Signierung laufen im begrenzten Threadpool; der begrenzte Download bleibt asynchron und verwendet unverändert den gemeinsamen Origin-/Redirect-Schutz. Der Storage3-Client und der bestehende Supabase-Adapter werden erst nach bestätigter Sichtbarkeit aus den üblichen ENV-Werten aufgebaut, ohne globale Teaching-/Learning-Adapterumschaltung. Fehlgeschlagener Aufbau ist wiederholbar. Der Abschnitts-Alias behält seine Abschnittsprüfung und zweite Sichtbarkeitsabfrage; Simulationen verwenden unverändert die gemeinsame Sandbox-Antwort. Uploads, Abgaben und die übrige globale Storage-Verdrahtung bleiben eigenständige Folgearbeiten (TD-004).

Die kursweiten und einheitenbezogenen Abschnittslisten verwenden `create_app(learning_section_providers=...)`. Die synchronen Handler in `learning_section_routes.py` rufen die vorhandenen frameworkunabhängigen Abschnitts-Anwendungsfälle im begrenzten Threadpool auf; Paginierung und SQL-Sichtbarkeit bleiben unverändert. Kursweite Leerlisten ergeben weiterhin 404, einheitenbezogene Leerlisten `200 []`. Abschnittsdaten und nachgelagerte Material-Metadaten werden mit demselben expliziten Repository gelesen. `learning_material_files.py` benötigt nun durchgehend einen übergebenen Adapter und keine globale Learning-Fassade; unbenutzte Einzeldatei-URL-Helfer sind entfernt. Ein bei der Metadatenabfrage nicht bestätigtes Material erhält keinen Link; der tatsächliche Dateiabruf prüft den Zugriff erneut.

Die H5P-Zugriffsprüfung verwendet `create_app(learning_h5p_providers=...)` und den unveränderten `CheckH5PContentAccessUseCase`. `learning_h5p_routes.py` prüft Rolle und IDs vor dem Datenzugriff; Repository-Aufbau und DB-Abfrage laufen im begrenzten Threadpool. Die Antwort bleibt eine private 204 ohne Inhalt oder eine private 404 bei fehlendem Zugriff. Die SQL-Prüfung für Mitgliedschaft und mindestens eine zugängliche passende Aufgabe bleibt zentral. Kein Learning-Endpunkt benötigt mehr globale `_REPO`-Variablen; die entsprechende nachträgliche Endpunkt-Reparatur aus `set_repo` ist entfernt. Die globalen Aliase für übrige Upload-/Abgabehelfer bestehen bis zu deren Migration weiter. Der H5P-Dienst behält seinen bisherigen kurzlebigen Zugriffscache; ein Mitgliedschaftsentzug wird von der Learning-API sofort, beim erneuten Player-Modellabruf nach Cacheablauf berücksichtigt.

Der interne Upload-Proxy erhält Transport und Telemetrie über `create_app(learning_upload_proxy_providers=...)`. Sein typisierter Provider verwendet den bestehenden asynchronen HTTP-Transport und die unveränderte, gegen Loggerfehler abgesicherte Protokollierung aus `learning_upload_proxy.py`. Anmeldung, Same-Origin-, Zieladress-, Header-, MIME- und Größenprüfungen bleiben im HTTP-Adapter; erst danach wird weitergeleitet. Der Proxy löst Transport und Telemetrie nicht mehr über die Learning-Fassade oder Endpoint-Globals auf. Gemeinsame Authentifizierungs-/Konfigurationshelfer und DB-/Storage-Zugriffe der Upload-Intents bleiben separate Folgearbeit; die vorhandene Proxy-Konfiguration ändert sich nicht.

Die Erstellung von Upload-Freigaben erhält ihren Datenbankzugang über `create_app(learning_upload_intent_providers=...)`. Der Handler löst den Adapter nach Rollen-, CSRF- und Eingabeprüfung einmal auf; der bestehende `ListSubmissionsUseCase` und die anschließende Aufgabentyp-Abfrage verwenden denselben Adapter. Beide Operationen behalten ihre DB-Sichtbarkeitsprüfungen. Repository-Aufbau, Abfragen und vorhandene Storage-Signierung laufen im begrenzten Threadpool. Fehler beim Aufbau bleiben wiederholbar und ergeben die bisherige private Autorisierungsfehlerantwort. Die gemeinsame Speicherinitialisierung und übrigen dynamischen Authentifizierungs-/Konfigurationshelfer sind damit noch nicht migriert; weder Dateityp-Regeln noch Upload-Vertrag ändern sich.

„Appbezogen“ bezeichnet hier die interne Zuordnung von Abhängigkeiten zum beim Start erzeugten Backend-Anwendungsobjekt. Es bedeutet weder mehrere Produkte noch zusätzliche Server oder Datenbanken: Je Dev-/Prod-System bleibt eine GUSTAV-Installation vorgesehen. Der Zweck ist nachvollziehbare Verdrahtung und gezielter Austausch von Abhängigkeiten in Tests ohne globale Seiteneffekte.

Ältere Teaching-DB-Verträge prüfen ihre Voraussetzung mit `backend/tests/utils/teaching.py`: erst sichere DB-Verfügbarkeit, danach Auflösung des aktuellen Teaching-Adapters. Die Hilfe verändert keine Abhängigkeiten und repariert keine globalen Variablen. Ist die DB erreichbar, aber der aktive Adapter falsch verdrahtet, schlägt der Test fehl statt still zu überspringen. Dies ersetzt die betroffenen Prüfungen gegen seit der Testsammlung veraltete Modul-Aliase; es ist keine neue Produktionsschicht oder allgemeine Ablösung aller bisherigen Test-Fixtures.

Die modularen Graphansichten beider Rollen teilen bereits die Positionsberechnung in `frontend/src/lib/graph/teacher-unit-flow.ts`; `buildLearningUnitFlow` ergänzt die schülerbezogene Projektion ohne einen zweiten Layoutalgorithmus. Gespeicherte Phasenpositionen und eine eindeutige Sortierung verzweigter Kanten bestimmen die Geometrie unabhängig von der Eingabelistenreihenfolge. `GraphViewportControls` ist der gemeinsame UI-Baustein für Fokus und Gesamtansicht. Der Startfokus wartet auf gemessene Knoten und eine initialisierte Zeichenfläche und wird nur einmal angewandt. Schülersperren, Fortschritt und Öffnen bleiben im Learning-Adapter; die Teaching- und Learning-API sowie ihre Eigentümer-/Mitgliedschaftsprüfungen bleiben getrennt. `graph-role-parity` vergleicht denselben gespeicherten Graphen in zwei authentifizierten Browserkontexten einschließlich tatsächlicher Knoten- und Pfeilgeometrie.

Die Namenssperre benötigt das explizit verwaltete Keycloak-Profilattribut `name_locked_until`. Es ist optional, einwertig und ausschließlich für Administratoren les-/schreibbar; Endnutzer dürfen es nicht umgehen oder zurücksetzen. Die Realm-Vorlage enthält diese Deklaration. Bestehende Realms müssen dieselbe gezielte Konfigurationsänderung übernehmen, da der initiale Realm-Import keine bestehenden Realms aktualisiert. Die allgemeine Freigabe unverwalteter Attribute ist dafür nicht erforderlich.

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

Die Druckfassung ist ein transienter Teaching-Use-Case für eigene Lerneinheiten. Ein autorengebundener Batch-Snapshot ordnet ausgewählte Materialien und Aufgaben, entfernt Lehrkraft-Felder vor der Übergabe an den PDF-Adapter und liest nur ausgewählte private Dateien. Der Satz läuft ohne Netzwerkzugriff in einem kurzlebigen, begrenzten Prozess; eingefügte PDF-Seiten werden in neue A4-Seiten überführt. Weder Auswahl noch Ergebnis werden persistiert, und der Ablauf ist nicht an einen Kurs oder eine Freigabe gebunden.

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
- `make verify-feature FEATURE=<spec-stem>` ergänzt für nutzerseitige Änderungen genau den zugeordneten authentifizierten Browser-Rundlauf und verweigert schreibende entfernte Ziele; die vollständige Browserregression bleibt mit `make test-feature-regression` opt-in.
- `make test-architecture-boundaries` schützt Clean-Architecture-Grenzen mit `architecture-boundary-scan`.
- `make test-route-map` hält die technische Route Map synchron und bestätigt, dass es keine aktiven Legacy-Produktseiten gibt.
- `make docker-validate` prüft Compose-, Proxy- und Image-Verträge bei Infrastrukturänderungen.

Weitere Nachweise stehen unter `docs/harness/` und `docs/tests/e2e_howto.md`.
