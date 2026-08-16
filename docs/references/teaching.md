# Unterrichten (Teaching) – Referenz

Stand: Version 0.0.4, zuletzt geprüft am 2026-08-16.

Diese Referenz beschreibt die fachlichen Fähigkeiten und technischen Grenzen des Teaching-Kontexts. `api/openapi.yml` ist die Quelle der Wahrheit für Endpunkte und Payloads; `supabase/migrations/` ist die Quelle der Wahrheit für das Schema.

## Produktoberfläche

Die Lehrkraftoberfläche liegt vollständig in SvelteKit:

- `/teaching` – Einstieg in den Teaching-Raum;
- `/teaching/courses` – aktive und archivierte Kurse;
- `/teaching/courses/{courseId}` – Kurskontext, Mitglieder, Lerneinheiten und Kurseinladung;
- `/teaching/units` – wiederverwendbare Lerneinheiten;
- `/teaching/units/{unitId}` – Modulgraph und Struktur;
- `/teaching/units/{unitId}/nodes/{nodeId}` – Inhalte und Einstellungen eines Graphknotens.

SvelteKit komponiert Seiten und Form Actions als Browser-BFF. Fachliche Mutationen laufen über die Teaching-API; es gibt keine produktiven FastAPI-SSR-/HTMX-Seiten und keinen Repository-Bypass aus dem Frontend.

## Kurse

Ein `Course` ist die konkrete organisatorische Hülle für eine Lerngruppe. Pflichtmetadaten sind Titel, Fach, Klassenstufe und Schuljahresbeginn; ein Halbjahr kann ergänzt werden.

Die API unterstützt insbesondere:

- eigene aktive oder archivierte Kurse listen;
- Kurs anlegen und Metadaten ändern;
- Kurs archivieren und versehentliche Archivierung rückgängig machen;
- mehrere Kurse gesammelt archivieren;
- Löschfolgen vorab anzeigen und endgültige Löschung als wiederholbaren Hintergrundauftrag anstoßen;
- Status eines eigenen Löschauftrags abfragen.

Archivierte oder zur Löschung vorgemerkte Kurse werden Lernenden nicht als aktive Kurse angeboten. Schreibzugriffe sind der besitzenden Lehrkraft vorbehalten.

## Mitgliedschaften

`Course Membership` verbindet einen Kurs mit dem opaken OIDC-`sub` einer lernenden Person. API und UI speichern keine E-Mail-Adresse als fachlichen Schlüssel.

Lehrkräfte können:

- Mitglieder eines eigenen Kurses paginiert lesen;
- Lernende über den Identity-&-Access-Directory-Adapter suchen;
- Mitgliedschaften idempotent hinzufügen;
- Mitgliedschaften entfernen.

Anzeigenamen werden über den Directory-Adapter aus Keycloak aufgelöst. Teaching übernimmt keine Keycloak-Benutzerdatenbank und formatiert Identitäten nicht erneut.

## Kurseinladungen (Course Invitations)

Unter „Klasse einladen“ kann die besitzende Lehrkraft eines aktiven und vollständig konfigurierten Kurses eine gemeinsame Einladung erzeugen.

- Pro Kurs existiert höchstens eine aktive Einladung.
- Eine Einladung ist fest 24 Stunden gültig.
- Eine neue Einladung widerruft die vorherige atomar.
- Archivierung widerruft die Einladung; eine Wiederherstellung reaktiviert sie nicht.
- Die Lehrkraft kann den Link kopieren, einen lokal erzeugten QR-Code anzeigen oder herunterladen und einzelne Einladungsmails versenden.
- E-Mail-Empfänger werden dedupliziert und auf erlaubte Registrierungsdomains begrenzt.
- Status und fehlgeschlagene Zustellungen können eingesehen; fehlgeschlagene Zustellungen können gezielt erneut eingeplant werden.

Das Capability-Token liegt ausschließlich im URL-Fragment. Es wird weder vollständig gespeichert noch geloggt. Die öffentliche Vorschau erhält das Token explizit im Request Body und gibt nur Kurstitel und Ablaufzeit zurück. Nach Keycloak-Registrierung beziehungsweise Login löst ausschließlich eine lernende Person die Einladung atomar und idempotent ein.

Wurde eine über diesen Link entstandene Mitgliedschaft später entfernt, verhindert derselbe Link einen unbeabsichtigten Wiedereintritt. Erst eine bewusste Rotation durch die Lehrkraft schafft eine neue Capability.

Relevante API-Gruppen:

- `/api/teaching/courses/{course_id}/invitations*` für Lehrkräfte;
- `/api/course-invitations/preview` für die datensparsame Vorschau;
- `/api/course-invitations/redeem` für den authentifizierten Beitritt.

Details zum Auth-Rücksprung, Cookie und SMTP-Betrieb stehen in `docs/references/user_management.md`.

## Lerneinheiten und Modulgraph

Eine `Unit` ist wiederverwendbarer Unterrichtsinhalt und gehört ihrer Autorin beziehungsweise ihrem Autor. GUSTAV unterstützt:

- `linear`: klassische Abschnitte mit kursbezogener Freigabe;
- `modular`: Phasen, Graphknoten und gerichtete Voraussetzungen.

Modulare Lerneinheiten bestehen aus:

- `Unit Phase`: ordnet Graphknoten visuell und fachlich;
- `Learning Module`: regulärer Lernschritt mit Material und Aufgaben;
- `Practice Module`: wiederholbarer Übungsstapel ohne ausgehende Kanten;
- `Graph Edge`: gerichtete Voraussetzung zwischen Knoten;
- `required_prereq_count`: Anzahl benötigter Vorgänger für die Freischaltung.

Die Teaching-API bietet objektorientierte Endpunkte für Units, Phasen, Module, Kanten und Inhalte sowie eigene Read Models für den SvelteKit-Arbeitsraum. Reihenfolgen werden serverseitig als vollständige ID-Mengen validiert, damit Duplikate und verlorene Elemente nicht unbemerkt übernommen werden.

## Materialien

Materialien gehören zu einem Abschnitt oder Modul. Unterstützte Arten:

- `markdown`: Textinhalt;
- `file`: private Datei mit geprüften Metadaten;
- `simulation`: vollständig eingebettetes HTML mit optionaler Orientierung.

Dateien und Simulationen verwenden den Ablauf `Upload Intent → Upload → Finalize`. Dabei werden Pfad, MIME-Typ, Größe, Hash und fachliche Bindung geprüft. Simulationen werden zusätzlich auf selbstenthaltene Inhalte untersucht und in einer Offline-Iframe-/CSP-Sandbox ausgeliefert.

Direkte Storage-Keys erscheinen nicht in der Oberfläche. Vorschau und Download verwenden berechtigungsgeprüfte, kurzlebige Zugriffe.

## Aufgaben

Aufgaben besitzen eine Anweisung und abhängig vom Typ Kriterien, Lehrkraftkontext, Musterlösung oder typbezogene Konfiguration. Unterstützte Typen:

- `native` – Text- oder Dateiabgabe mit formativem Feedback;
- `h5p` – interaktive H5P-Aufgabe;
- `visual` – bildbezogene Aufgabenstellung und visuelles Feedback;
- `scratch` – Scratch-`.sb3`-Artefakt;
- `calliope` – MakeCode-`.hex`-Artefakt;
- `filius` – Filius-`.fls`-Artefakt;
- `dialog` – KI-gestützter fachlicher Dialog.

Übungsmodule erlauben nur wiederholbare native oder H5P-Aufgaben. Für native Übungsaufgaben sind Kriterien, Lehrkraftkontext und Musterlösung erforderlich; Abgabefrist und maximale Versuche sind dort nicht zulässig.

## Kurszuordnung und Freigabe

Ein `Course Module` ordnet eine wiederverwendbare Lerneinheit einem Kurs zu. Freigaben bestimmen, welche linearen Abschnitte beziehungsweise modularen Inhalte für Lernende sichtbar sind. Ownership, Kursmitgliedschaft und Sichtbarkeit werden nicht allein in der UI, sondern an Repository- und Datenbankgrenzen geprüft.

Die Live- und Diagnostikräume greifen lesend auf eigene Projektionen zu. Details stehen in `docs/references/teaching_live.md` und `docs/bounded_contexts.md`.

## Teaching Authoring CLI

Die GUSTAV CLI verwendet dieselben Teaching-Endpunkte wie die Weboberfläche. CLI-Tokens besitzen explizite `read`-, `write`- und `delete`-Capabilities. Cookiegebundene Browserfunktionen wie vollständige Benutzerlisten, H5P-Editor-JSON oder Dialogvorschau werden nicht durch breitere CLI-Rechte ersetzt.

Aufruf- und Sicherheitsdetails: `docs/references/gustav_cli.md`.

## Architektur und Persistenz

- HTTP-Adapter: aufgeteilte Router unter `backend/web/routes/teaching_*.py`;
- fachliche Services: `backend/teaching/services/`;
- PostgreSQL-Adapter: `backend/teaching/repo_db.py`;
- Identity Directory: Adapter unter `backend/identity_access/`;
- Storage: Ports und Adapter unter `backend/storage/` und `backend/teaching/storage_supabase.py`;
- Browser-BFF: `frontend/src/routes/teaching/`.

Einige einfache Teaching-Routen orchestrieren Repository-Aufrufe direkt. Neue oder komplexe Fachregeln gehören in framework-unabhängige Services. FastAPI-Routen dürfen keine direkten PostgreSQL-Verbindungen oder Supabase-Clients erzeugen.

## Sicherheit und Datenschutz

- Owner- und Author-Prüfungen greifen fail-closed.
- Schreibende Cookie-Flows benötigen Same-Origin-/CSRF-Schutz.
- Antworten mit privaten Daten verwenden `Cache-Control: private, no-store`.
- RLS und owner-gebundene `SECURITY DEFINER`-Helper schützen Datenbankzugriffe.
- Personen werden fachlich über `sub`, nicht über E-Mail-Adressen, referenziert.
- Capability-Tokens, SMTP-Adressen und Inhaltsdaten erscheinen nicht in Logs.
- Fehlende sicherheitskritische DB-Helper führen zu `503`, nicht zu einem weniger geschützten Tabellen-Fallback.

## Verifikation

- OpenAPI-Vertrag: `backend/tests/test_openapi_teaching_*.py` und spezialisierte Contract-Tests;
- API-Verhalten: `backend/tests/test_teaching_*.py`;
- Datenbank und RLS: `backend/tests/migration/` sowie DB-markierte Repository-Tests;
- SvelteKit: Tests unter `frontend/src/routes/teaching/`;
- vollständiger Browserablauf: `@feature-acceptance`-Tests unter `frontend/e2e/`.

Für nutzerseitige Teaching-Änderungen ist `make verify-feature` der Abschlussnachweis.
