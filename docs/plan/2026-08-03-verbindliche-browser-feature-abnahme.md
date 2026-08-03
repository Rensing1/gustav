# Verbindliche Browser-Feature-Abnahme und Dialogeditor-Korrektur

**Stand:** 03.08.2026
**Status:** In Umsetzung

## User Story

Als Produktverantwortlicher möchte ich, dass neue nutzerseitige Features vor ihrem Abschluss einen echten Browser-Rundlauf durchlaufen, damit Fehler an den Übergängen zwischen Oberfläche, Server und Datenbank nicht durch isolierte Tests unentdeckt bleiben.

Als Lehrkraft möchte ich eine KI-Dialogaufgabe speichern, neu laden und mit allen konfigurierten Feldern wiedersehen, damit ich mich auf den Aufgabeneditor verlassen kann.

## BDD-Szenarien und Testzuordnung

| Szenario | Automatisierter Nachweis |
| --- | --- |
| **Given** ein neues nutzerseitiges Feature, **when** es als fertig gemeldet wird, **then** wurden die schnelle Verifikation und mindestens ein authentifizierter Browser-Rundlauf erfolgreich ausgeführt. | `backend/tests/test_feature_acceptance_gate_contract.py`, `make verify-feature` |
| **Given** das produktionsnahe Gesamtprofil, **when** es ausgeführt wird, **then** enthält es die verbindliche Feature-Abnahme. | `backend/tests/test_feature_acceptance_gate_contract.py` |
| **Given** eine Lehrkraft füllt alle Felder einer KI-Dialogaufgabe aus, **when** sie speichert und die Seite neu lädt, **then** werden alle Werte unverändert angezeigt. | `backend/tests/test_teaching_unit_workspace_view_api.py`, `frontend/e2e/dialog-task-authoring.spec.ts` |
| **Given** eine neu gespeicherte KI-Dialogaufgabe, **when** der Editor sie zur Kontrolle öffnet, **then** bleibt das Probefeld geschlossen, bis die Lehrkraft es bewusst aufklappt. | Frontend-Komponententest, `frontend/e2e/dialog-task-authoring.spec.ts` |
| **Given** die Erstellung scheitert an einer Validierung, **when** das Formular erneut angezeigt wird, **then** bleiben Aufgabentyp und Dialogfelder erhalten. | Frontend-Komponententest und Serveraktionstest |

## Umsetzung

1. Das verbindliche Feature-Gate wird testgetrieben in Makefile, Arbeitsanweisungen und Harness-Dokumentation verankert und zunächst mit einem bestehenden authentifizierten Browsertest nachgewiesen.
2. Erst danach wird die unvollständige Lehrkraftprojektion testgetrieben korrigiert.
3. Die Dialogvorschau wird standardmäßig geschlossen dargestellt; die Aufgabe selbst bleibt nach dem Speichern geöffnet.
4. Ein neuer authentifizierter Browsertest prüft Erstellen, Speichern, explizites Neuladen und Wiederanzeige aller Dialogfelder ohne Modellaufruf.

## Verträge und Datenhaltung

OpenAPI-Vertrag, Datenbankschema und fachliche DTOs ändern sich nicht. Die gespeicherten Daten sind vollständig; korrigiert wird die bereits vertragswidrig verkürzte Editorprojektion.

## Abschlusskriterien

- `make verify-feature` ist erfolgreich.
- Der Browsertest lädt die Seite nach dem Speichern ausdrücklich neu.
- Bereits gespeicherte Dialogkonfigurationen werden wieder angezeigt.
- Gate und Fehlerkorrektur werden getrennt committed.
