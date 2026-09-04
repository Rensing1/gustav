# Druckfassung für Lerneinheiten

## User Story

Als Lehrkraft möchte ich einzelne Materialien und Aufgaben einer selbst erstellten Lerneinheit auswählen und als kompakte PDF-Schülerfassung herunterladen, damit Schüler ohne Tablet inhaltlich am Unterricht teilnehmen können.

Die Druckfassung ist in Version 1 ausschließlich ein Bereitstellungsweg. Handschriftliche Lösungen werden nicht zurück in GUSTAV übertragen. Der Export ist nicht kursgebunden, berücksichtigt keine Freigaben und wird nicht gespeichert.

## Fachliche Entscheidungen

- Der Einstieg liegt ausschließlich in der Arbeitsfläche einer Lerneinheit.
- Die Auswahl startet leer und erlaubt einzelne Inhalte sowie hierarchische Sammelwahl für Abschnitte, Phasen und Module.
- Der Server leitet die Reihenfolge aus den aktuellen Autorendaten ab: Materialien erscheinen vor Aufgaben.
- Die Schülerfassung enthält weder Kriterien noch Lehrkraft-Kontext, Musterlösung, Fälligkeit oder maximale Versuche.
- Interaktive Inhalte enthalten ihre Beschreibung und einen Hinweis auf die notwendige digitale Umgebung.
- Bilder werden eingebettet. PDF-Materialien werden auf A4 eingepasst und ohne aktive PDF-Elemente übernommen.
- Das GUSTAV-Layout ist schwarz-weiß-tauglich; ursprüngliche Bilder und PDF-Seiten behalten ihre Farben.
- Ein Export umfasst höchstens 200 ausgewählte Inhalte, 200 Seiten und jeweils 50 MiB Eingabe- und Ausgabedaten.
- Datei-, Größen- und Rendererfehler brechen den gesamten Export ab. Es entsteht kein unvollständiges Dokument.

## BDD-Szenarien und Testzuordnung

| Szenario | Given | When | Then | Nachweis |
|---|---|---|---|---|
| Vollständiger Browserablauf | Eine angemeldete Autorin besitzt eine modulare Einheit mit Material und Aufgabe. | Sie öffnet die Druckauswahl, wählt einen Inhalt und lädt die Schülerfassung herunter. | Der Browser erhält über Oberfläche, Server und PostgreSQL ein gültiges PDF mit sicherem Dateinamen. | `frontend/e2e/teacher-unit-print.spec.ts` mit `@feature-acceptance`; Datei- und Storagevarianten werden zusätzlich in den isolierten Use-Case- und Renderer-Tests geprüft. |
| Lineare Reihenfolge | Eine lineare Einheit besitzt Inhalte an erster und letzter Position. | Ausgewählte Inhalte werden exportiert. | Abschnitte, Materialien und Aufgaben erscheinen in gespeicherter Reihenfolge. | Use-Case- und DB-Integrationstest |
| Modulare Reihenfolge | Eine modulare Einheit besitzt mehrere Phasen und Module. | Inhalte aus verschiedenen Modulen werden exportiert. | Nur betroffene Phasen und Module erscheinen in ihrer gespeicherten Reihenfolge. | Use-Case- und DB-Integrationstest |
| Schülerfassung | Eine Aufgabe besitzt Kriterien, Lehrkraft-Kontext, Musterlösung und digitale Metadaten. | Die Aufgabe wird exportiert. | Nur Aufgabenart und Aufgabenstellung erscheinen. | PDF-Inhalts- und Negativtest |
| Dateiintegration | Bild- und PDF-Materialien besitzen verschiedene Ausrichtungen. | Sie werden ausgewählt. | Sie erscheinen farbig, proportional und an ihrer Materialposition auf A4. | Renderer-Integrationstest und gerenderte PNG-Prüfseiten |
| PDF-Sicherheit | Ein PDF enthält Annotationen, Formulare, Aktionen oder Metadaten. | Es wird eingebaut. | Das Gesamtdokument übernimmt nur den statischen Seiteninhalt. | PDF-Strukturtest |
| Interaktive Inhalte | Eine Simulation oder interaktive Aufgabe ist ausgewählt. | Das PDF wird erzeugt. | Beschreibung und Digitalhinweis erscheinen, aber keine ausführbare Ressource. | Use-Case- und PDF-Texttest |
| Ungültige Auswahl | Die Auswahl ist leer, doppelt, gelöscht oder einheitenfremd. | Der Export wird angefordert. | Es entsteht kein PDF und die API liefert einen stabilen Fehler. | API- und UI-Fehlertest |
| Autorisierung | Der Aufrufer ist unangemeldet, Schüler, fremde Lehrkraft oder sendet eine fremde Origin. | Auswahl oder Export werden aufgerufen. | GUSTAV antwortet mit `401`, `403`, `404` beziehungsweise CSRF-Fehler. | API-Integrationstest sowie Besitz- und Batch-Lesetest gegen die lokale Datenbank |
| Ressourcenbegrenzung | Auswahl, Seitenzahl, Datenmenge, Zeit oder Speicher überschreiten die Grenze. | Der Export läuft. | Die Erzeugung wird vollständig abgebrochen und nichts gespeichert. | Policy-, Unterprozess- und API-Test |

## API-Vertrag

1. `GET /api/teaching/units/{unit_id}/printable-content` liefert die autorisierte lineare oder modulare Auswahlstruktur und die Exportgrenzen. Die Antwort enthält nur die zur Auswahl nötigen Metadaten, nicht die vollständigen Druckinhalte.
2. `POST /api/teaching/units/{unit_id}/printable-pdf` erhält `material_ids` und `task_ids` als UUID-Listen. Mindestens eine eindeutige ID ist erforderlich; der Server lädt alle Inhalte erneut und bestimmt ihre Reihenfolge selbst.
3. Erfolg liefert `200 application/pdf` mit `Cache-Control: private, no-store`, `X-Content-Type-Options: nosniff` und einem sicheren `Content-Disposition`-Dateinamen.
4. Fehlercodes: `400` ungültige Auswahl, `401/403/404` Authentifizierung/Autorisierung, `413` Exportgrenze, `422 material_unprintable` und `503` Repository-, Storage- oder Renderer-Ausfall.
5. Beide Endpunkte sind cookie-authentifiziert und autorengebunden. Der POST verlangt zusätzlich strikte Same-Origin-Prüfung.

## Schema und Migration

Es ist keine PostgreSQL- oder Supabase-Migration erforderlich. Auswahl und Ergebnis sind flüchtig; alle benötigten Inhalte, Positionen und Autorenbeziehungen existieren bereits. Insbesondere wird keine Exporthistorie angelegt.

## Architektur und Sicherheit

- Ein frameworkfreier Teaching-Use-Case erstellt einen unveränderlichen Druck-Snapshot und schließt interne Aufgabenfelder aus.
- Repository, Storage und PDF-Renderer werden über Ports angebunden; die FastAPI-Route enthält nur Transport-, Authentifizierungs- und Fehlerabbildungslogik.
- Sichere Markdown-Konvertierung verwendet kein Roh-HTML. Der PDF-Renderer erhält ausschließlich festes CSS und explizit freigegebene temporäre Bildressourcen; Netzwerk- und beliebige Dateizugriffe sind gesperrt.
- PDF-Erzeugung läuft als nicht privilegierter, kurzlebiger Unterprozess mit 30 Sekunden CPU-Zeit, 35 Sekunden Gesamtzeit und 1,5 GiB virtuellem Adressraum. Die größere Adressraumgrenze berücksichtigt reservierten, nicht zwingend belegten Speicher nativer Schrift- und Bildbibliotheken. Der Renderer verwendet keine temporären Dateien.
- Ursprungsmetadaten und personenbezogene Kennungen werden weder ins PDF noch in Logs übernommen.

## Red-Green-Refactor und Abnahme

1. OpenAPI-Vertrag ergänzen.
2. Fehlende Contract-, API-, Use-Case-, Renderer- und UI-Tests rot schreiben.
3. Minimale Backend- und Frontend-Implementierung bis Green ergänzen.
4. Auf klare Verantwortlichkeiten, N+1-Abfragen, Autorprüfung, inhaltsfreie Logs sowie verständliche englische Docstrings und Kommentare refaktorieren.
5. Handbuch, Changelog, Architektur-/Route- und Supply-Chain-Inventar aktualisieren.
6. PDF-Seiten mit Poppler in PNG rendern und A4 hoch/quer, lange Überschriften, Tabellen, Codeblöcke, Umlaute und Seitenwechsel visuell prüfen.
7. Vor dem Browserlauf `make local-ca-status`, anschließend `make docker-validate` und `make verify-feature FEATURE=teacher-unit-print` erfolgreich ausführen.
