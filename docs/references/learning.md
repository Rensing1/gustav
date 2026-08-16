# Lernen (Learning) – Referenz

Stand: Version 0.0.4, zuletzt geprüft am 2026-08-16.

Diese Referenz beschreibt den Learning-Kontext: sichtbare Lernwege, Bearbeitung, Abgaben, formative Rückmeldung, Dialoge, Portfolio und Übung. Der vollständige HTTP-Vertrag steht in `api/openapi.yml`; Details zur KI-Verarbeitung stehen in `docs/references/learning_ai.md`.

## SvelteKit-Lernarbeitsbereich

Die produktive Lernoberfläche liegt in SvelteKit:

- `/learning` – persönliche Kursübersicht;
- `/learning/courses/{courseId}` – Lerneinheiten eines Kurses;
- `/learning/courses/{courseId}/units/{unitId}` – Modulgraph und Arbeitsbereich;
- `/learning/courses/{courseId}/archive` – eigene Lernleistung und Export;
- `/learning/practice` – Auswahl fälliger oder neuer Übungsstapel;
- `/learning/practice/sessions/{sessionId}/summary` – Abschluss einer Übungssitzung.

Die Modulgraphansicht macht den Lernweg als Advance Organizer sichtbar. Geöffnete, gesperrte und bearbeitete Knoten werden aus der Kursfreigabe und den fachlichen Voraussetzungen abgeleitet. Materialien, Aufgabe und Rückmeldung erscheinen in einem gemeinsamen Arbeitsbereich, ohne den Lernkontext zu verlassen.

SvelteKit lädt View Models und Fachobjekte über FastAPI. Es gibt keine produktiven Learning-Seiten im früheren FastAPI-SSR-/HTMX-Layer.

## Sichtbarkeit und Zugriff

Eine lernende Person sieht ausschließlich:

- aktive Kurse mit eigener Mitgliedschaft;
- dem Kurs zugeordnete Lerneinheiten;
- freigegebene lineare Abschnitte;
- im Modulgraphen sichtbare beziehungsweise freigeschaltete Knoten;
- Materialien und Aufgaben, die zu diesem sichtbaren Kontext gehören;
- eigene Abgaben, Dialoge, Übungszustände und Exporte.

Diese Regeln werden nicht nur in der Oberfläche geprüft. Repository, RLS und eng begrenzte Datenbank-Helper erzwingen Mitgliedschaft, Sichtbarkeit und Ownership erneut.

Wichtige Leseverträge liegen unter:

- `/api/learning/views/learner-home`;
- `/api/learning/courses`;
- `/api/learning/courses/{course_id}/units`;
- `/api/learning/courses/{course_id}/units/{unit_id}/modules/graph`;
- `/api/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}`;
- `/api/learning/courses/{course_id}/units/{unit_id}/sections` für lineare Kompatibilität.

## Materialien

Lernende können freigegebene Markdown-, Datei- und Simulationsmaterialien verwenden.

- Markdown wird als bereinigter Inhalt dargestellt.
- Private Dateien werden nur nach erneuter Sichtbarkeitsprüfung ausgeliefert.
- Simulationen laufen bewusst gestartet in einer Offline-CSP-/Iframe-Sandbox ohne Same-Origin-Rechte, Tracking oder Ergebnisübertragung.
- H5P-Inhalte erhalten eine eigene kurzlebige, auf Kurs, Aufgabe, Person und Inhalt begrenzte Zugriffsberechtigung.

Direkte Storage-Pfade werden nicht veröffentlicht.

## Abgaben

Abgaben sind unveränderliche Versuche einer lernenden Person zu einer Aufgabe. Je nach Aufgabentyp können Text oder ein zuvor hochgeladenes Artefakt verarbeitet werden; H5P-Ergebnisse werden idempotent aus signierten beziehungsweise tokengebundenen Ereignissen übernommen.

Der typische native Ablauf:

1. Ein Entwurf wird über einen idempotenten Request gespeichert.
2. Bei Dateien wird zuvor ein Upload Intent erzeugt und das gespeicherte Artefakt anhand von Größe, Hash, MIME-Typ und Inhaltssignatur geprüft.
3. Ein Hintergrundjob verarbeitet Vision beziehungsweise Feedback.
4. Die Oberfläche fragt den Status nach und zeigt anschließend Auswertung und formative Rückmeldung.
5. Nach Reflexion kann die lernende Person den aktuellen Entwurf endgültig abgeben.

Der Server erzwingt Versuchslimits, Mitgliedschaft, Freigabe, Aufgabenbindung und Idempotenz. Die UI ergänzt Doppel-Submit-Schutz und Wiederherstellung bei abgelaufener Session, ist aber nicht die Sicherheitsgrenze.

## Verarbeitungsstatus

`analysis_status` verwendet diese fachlichen Zustände:

- `pending`: gespeichert und zur Verarbeitung vorgemerkt;
- `extracted`: Artefakt wurde sicher vorverarbeitet, Feedback steht noch aus;
- `completed`: validierte Auswertung und Rückmeldung sind verfügbar;
- `failed`: Verarbeitung endete mit einem stabilen, bereinigten Fehlercode.

Teilweise Ergebnisse werden nicht vorzeitig veröffentlicht. Telemetrie enthält nur begrenzte technische Zähler und bereinigte Fehlermeldungen; Pfade, Secrets, Prompts und Inhaltsdaten gehören nicht hinein.

## KI-Analyse und formatives Feedback

Die produktive Pipeline verwendet DSPy-basierte Adapter:

- `backend/learning/adapters/local_vision.py` für Bild-, PDF- und Artefaktvorverarbeitung;
- `backend/learning/adapters/local_feedback.py` für strukturierte Analyse und formative Rückmeldung;
- `backend/learning/adapters/local_dialog.py` für fachliche Dialoge;
- Programme und Signatures unter `backend/learning/adapters/dspy/`.

Stub-Adapter sind explizite Testwerkzeuge und in produktionsnahen Umgebungen verboten. Der Worker führt externe Modellaufrufe außerhalb von Datenbanktransaktionen aus, validiert strukturierte Ergebnisse und schreibt nur erlaubte Daten zurück.

Die pädagogische Verantwortung bleibt bei Lehrkraft und lernender Person. GUSTAVs KI-Rückmeldung ist formativ, kein automatisches abschließendes Urteil.

## Aufgabentypen

- `native`: Text- oder Dateiarbeit mit Kriterien und formativem Feedback;
- `h5p`: interaktive Aufgabe mit idempotent gespeichertem Versuch und Score;
- `visual`: bildbezogene Bearbeitung mit direkter visueller Analyse;
- `scratch`: Analyse einer Scratch-Projektdatei;
- `calliope`: Analyse eines MakeCode-HEX-Artefakts;
- `filius`: Analyse einer Filius-Netzwerkdatei;
- `dialog`: fortsetzbarer, begrenzter KI-Dialog mit fachlicher Abschlussauswertung.

Artefaktadapter extrahieren nachvollziehbare Evidenz, bevor Feedback entsteht. Sie dürfen untrusted input nicht ausführen und keine eingebetteten Secrets oder personenbezogenen Daten protokollieren.

## Dialogaufgaben

Dialoge besitzen eine serverseitige Sitzung und klar begrenzte Gesprächskontexte. Startimpulse, Antworten und Abschlussauswertung werden durch framework-unabhängige Use Cases validiert. Gleichzeitige oder wiederholte Requests dürfen keine doppelten Turns erzeugen. Lehrkräfte sehen Dialoge ausschließlich über berechtigungsgeprüfte Learning- beziehungsweise Diagnostikprojektionen.

## Übungsmodule

Ein `Practice Module` ist ein wiederholbarer Graphknoten. In der Lernoberfläche erscheint es als `Practice Stack`, sobald es offen ist und Aufgaben enthält.

Der Übungsablauf:

1. GUSTAV ermittelt offene Stapel sowie neue und fällige Aufgaben.
2. Die lernende Person wählt einen oder mehrere Stapel.
3. Der Server erzeugt einen persistenten Snapshot als `Practice Session`.
4. Native Aufgaben werden mit KI-Rückmeldung, H5P-Aufgaben über den H5P-Ablauf bearbeitet.
5. Das Ergebnis aktualisiert den kurs- und aufgabenspezifischen `Practice State` nach dem versionierten Scheduler-Vertrag `gustav-practice-v1`.

Pro lernender Person existiert höchstens eine aktive Übungssitzung. Wiederholungen verändern nicht den Abschlusszustand des Modulgraphen; Übungsmodule bleiben erneut nutzbar.

## Portfolio und Export

Lernende können ihre eigene Arbeit kursbezogen einsehen und einen Export anfordern. Exporte entstehen als wiederholbare Hintergrundaufträge und enthalten ausschließlich eigene, freigegebene Daten. Downloadberechtigungen sind kurzlebig; interne Speicherpfade bleiben verborgen.

## Architektur

- HTTP-Adapter: aufgeteilte Router unter `backend/web/routes/learning_*.py` sowie `practice.py`;
- Use Cases: `backend/learning/usecases/`;
- Practice-Service: `backend/learning/practice/`;
- PostgreSQL-Adapter: `backend/learning/repo_db.py`;
- Worker: `backend/learning/workers/`;
- KI-Adapter: `backend/learning/adapters/`;
- Browser-BFF: `frontend/src/routes/learning/`;
- H5P-Driver: `h5p-service/`.

Use Cases kennen FastAPI nicht. Repositories kapseln RLS, Transaktionen und Datenbank-Helper. Provider- und Storagezugriffe liegen hinter Ports beziehungsweise Adaptern.

## Sicherheit und Datenschutz

- Alle Antworten mit Lern- oder Sitzungsdaten sind `private, no-store`.
- Abgaben und Dateien sind owner- und kursgebunden.
- Uploads verwenden zentrale Größenlimits, Signaturprüfung und sichere Storage-Keys.
- Fehlerantworten enthalten keine Providertexte, Pfade oder Secrets.
- Prompts, Schülertexte und Modellantworten werden nicht in Anwendungslogs geschrieben.
- H5P- und Simulationsinhalte laufen in eigenen, eingeschränkten Sicherheitsgrenzen.
- Learning-Daten werden nie über eine allgemeine Lehrkraftsuche offengelegt, sondern nur über zweckgebundene Diagnostikprojektionen.

## Verifikation

- API- und Use-Case-Tests: `backend/tests/test_learning_*.py` und spezialisierte Contract-Tests;
- Adaptertests: `backend/tests/learning_adapters/`;
- Datenbank- und Migrationsverträge: `backend/tests/migration/`;
- SvelteKit-Tests: `frontend/src/routes/learning/`;
- authentifizierte Rundläufe: `frontend/e2e/` und `backend/tests_e2e/`.

Für nutzerseitige Learning-Änderungen ist `make verify-feature` der Abschlussnachweis.
