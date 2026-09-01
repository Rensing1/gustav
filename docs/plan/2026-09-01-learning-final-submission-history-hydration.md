# Zuverlässige finale Textabgabe nach History-Restore

## User Story

Als Schüler möchte ich einen bereits ausgewerteten Textentwurf nach direktem Aufruf oder Neuladen endgültig abgeben können, ohne dass ein eigener abweichender Entwurf überschrieben oder ungeprüft finalisiert wird.

## BDD-Szenarien und Testzuordnung

1. **Asynchron geladene Rückmeldung**
   - **Given** die Aufgabenkarte startet ohne History, **when** eine fertige Text-Rückmeldung eintrifft, **then** wird ein unberührter Editor mit deren Text hydriert und die Finalisierung aktiviert.
   - Nachweis: `LearningTaskCard`-Komponententest.
2. **Atomar gebundene Fassung**
   - **Given** eine Submission wechselt von `pending` zu `completed`, **when** die fertige Fassung übernommen wird, **then** beziehen sich Editor-Baseline, Button, Hidden Field und Idempotenzschlüssel auf dieselbe Submission-ID.
   - Nachweis: Komponentenregressionstest.
3. **Geschützter lokaler Entwurf**
   - **Given** ein abweichender Session-Entwurf oder eine lokale Änderung, **when** History eintrifft, **then** bleibt der Text erhalten und die Finalisierung gesperrt.
   - Nachweis: Komponententests einschließlich eines vorhandenen leeren Storage-Werts.
4. **Rückkehr zur geprüften Fassung**
   - **Given** ein veränderter Editor, **when** der Text wieder der normalisierten Baseline entspricht, **then** wird die Finalisierung erneut möglich.
   - Nachweis: Komponententest.
5. **Direktlink und Reload**
   - **Given** eine fertige Rückmeldung, **when** die Aufgabe direkt mit Ergebnisparameter geöffnet oder neu geladen wird, **then** ist die geprüfte Fassung ohne vorheriges Öffnen über den Lernpfad finalisierbar.
   - Nachweis: Seitenvertrag und authentifizierter `@feature-acceptance`-Playwright-Test.
6. **Fehlgeschlagener History-Load**
   - **Given** das Laden scheitert, **when** die Ergebnisansicht erscheint, **then** zeigt sie einen verständlichen Fehler mit „Erneut versuchen“ und keine Behauptung über eine veränderte Fassung.
   - Nachweis: Komponenten- und Routentest.
7. **Bestehende Sicherheitsgrenzen**
   - **Given** eine Finalisierung läuft bereits oder eine Upload-/Dialogabgabe wird verwendet, **when** der Ablauf fortgesetzt wird, **then** entsteht höchstens eine finale Submission und die anderen Abgabearten behalten ihr Verhalten.
   - Nachweis: bestehende und erweiterte Komponenten- und Browsertests.

## Architektur- und Vertragsentscheidung

- Eine reine Finalisierungsfunktion bildet aus der neuesten abgeschlossenen Feedback-Submission eine atomare Baseline aus Submission-ID, Kind und mit `trim()` normalisiertem Text.
- Die Aufgabenkarte unterscheidet serverseitige Baseline, vorhandenen Session-Entwurf und lokale Bearbeitung. Nur ein unberührter, nicht abweichender Entwurf darf nachträglich aus der Baseline hydriert werden.
- Serverseitig gelieferte History wird synchron in den initialen Clientzustand übernommen. Wiederhergestellte Aufgaben mit bekannter Abgabe laden History vor der Aktivierung.
- Der gemeinsame History-Ladezustand wird bis zur Aufgabenkarte weitergereicht. Ein fehlgeschlagener Load bietet denselben deduplizierten Loader als Retry an.
- OpenAPI, Finalisierungsendpunkt, Datenbank, RLS und Worker bleiben unverändert; eine Migration ist nicht erforderlich.

## Red–Green–Refactor

1. Die Komponenten-, Seiten- und Browserregressionen zuerst fehlschlagend ergänzen.
2. Baseline und kontrollierte Editor-Hydration minimal implementieren.
3. Initiale History-Seeds, Restore-Preload und Retry-Vertrag ergänzen.
4. Gemeinsame Typen zentralisieren und den nicht mehr importierten `LearningSubmissionWorkspace` einschließlich Tests und exklusivem CSS entfernen.
5. Ticketstatus und Changelog aktualisieren, gezielte Tests ausführen und abschließend `make verify-feature` vollständig bestehen.

## Sicherheits- und Datenschutzgrenzen

- Die bestehende Bindung an `feedback_submission_id` und `finalize-{feedback_submission_id}` wird nicht gelockert.
- Ein abweichender lokaler Entwurf wird weder überschrieben noch gegen eine ältere Rückmeldung finalisiert.
- Tests, Meldungen und Dokumentation verwenden ausschließlich synthetische Daten ohne PII oder Secrets.

## Umsetzungsergebnis

- Die gemeinsame Baseline und die kontrollierte Reconciliation sind implementiert. Buttonfreigabe, `feedback_submission_id` und `finalize-{id}` leiten sich aus demselben Snapshot ab.
- History-Seeding, Restore-Preload, URL-Race-Guard und Retry sind bis zur aktiven Aufgabenkarte verdrahtet.
- Der veraltete alternative Abgabe-Arbeitsbereich und seine ausschließlich verwendeten Styles und Tests sind entfernt.
- OpenAPI und Persistenz wurden nach Prüfung nicht geändert, weil der Fehler ausschließlich im clientseitigen Restore lag.

## Verifikation

- Red: Vier neue Regressionen zeigten die fehlende asynchrone Hydration, die nicht atomare `pending → completed`-Übernahme, den fehlenden Retry und das fehlende Restore-Preload.
- Green: Die abschließende gezielte Suite aus Serverroute, Seitenvertrag, Finalisierungshelper und Aufgabenkarte bestand mit 120 Tests; alle 638 Frontendtests, die Svelte-Prüfung und beide authentifizierten Finalisierungsszenarien bestanden.
- PR-Fix-Regressionsschutz: Ein initialer serverseitiger History-`503` erreicht nun die Retry-fähige Ergebnisansicht, Auth-Redirects bleiben fail-closed und eine ungültige Submission-ID kann keine Finalisierungsbaseline erzeugen.
- `make verify-feature`: Der vollständige deterministische Teil bestand. Von 24 Feature-Acceptance-Szenarien bestanden 22, einschließlich beider Finalisierungsszenarien. Zwei bestehende, isoliert reproduzierbare KI-Ausgabeverträge außerhalb dieses Plans blieben rot: Schutz eines synthetischen vertraulichen Markers und Ein-Satz-Format im Übungsfeedback. Das Ticket wird erst geschlossen, wenn dieses unabhängige Gesamt-Gate grün ist.
