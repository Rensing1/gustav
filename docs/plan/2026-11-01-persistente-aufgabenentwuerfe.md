# Persönliche Aufgabenentwürfe

## Ziel und Entscheidungen

Als Schüler möchte ich eine normale Markdown-Aufgaben-Antwort später auf demselben oder einem anderen Gerät fortsetzen, ohne eine Rückmeldung anzufordern oder abzugeben. Ein privater Arbeitsentwurf je Schüler/Kurs/Aufgabe, ohne Ablaufzeit oder Versionshistorie. Letztes erfolgreiches Speichern gewinnt. KI-Dialoge, Uploads, Lehrer-Editoren und Übungssitzungen sind ausgenommen. Keine neue Infrastruktur und keine allgemeine Kontolöschung.

## Vertrag und Datenhaltung

GET/PUT `/api/learning/courses/{course_id}/tasks/{task_id}/draft`: GET liefert 204 ohne Entwurf, sonst 200 mit `text_body` und `updated_at`; PUT ersetzt den Text atomar und liefert 200. Leere Texte erlaubt, maximal 65.536 Zeichen, keine Normalisierung. Fehler 400/401/403/404/503, private/no-store, Same-Origin für PUT. Identität ausschließlich aus der Anmeldung. Neue Tabelle `learning_task_drafts` mit zusammengesetztem Schlüssel, RLS, Mitgliedschafts-/Kurs-/Aufgaben-Fremdschlüsseln und Löschkaskaden. Aktive Mitgliedschaft, Aufgabenfreigabe und native Lernaufgabe erforderlich. Archivierung und entzogene Freigabe erhalten die Daten, sperren aber Zugriff.

## Oberfläche und Wartbarkeit

Ein separat testbares Modul ersetzt die bisherige Tab-Speicherlogik. Nur der aktive Antwort-Editor lädt/speichert. Wiederherstellung: unbestätigter benutzerbezogener Tabtext, Servertext, Rückmeldungsstand, leer. Vorhandene Tabtexte werden als unbestätigt übernommen; unzugeordnete Alttexte nicht übernommen. Echte Änderungen nach 1 Sekunde Schreibpause, spätestens nach 5 Sekunden speichern. Pro Kontext serialisieren, verspätete Antworten ignorieren, nur exakt bestätigte lokale Texte entfernen. Ladefehler sperren den Editor bis zum erfolgreichen Wiederholen. Barrierefreie Anzeige: wird gespeichert / Entwurf gespeichert – noch nicht abgegeben / noch nicht gespeichert.

Pausieren wartet auf Bestätigung, bei Fehler bleibt der Editor offen. Navigation speichert oder erlaubt nach Warnung ausdrücklich den Wechsel. Tab-Speicher und Browserwarnung sichern unbestätigte Änderungen bestmöglich; kein Versprechen für Offline-Schließen. Temporäre Fehler nach 10 Sekunden und bei `online` wiederholen, Auth-/Zugriffsfehler stoppen Wiederholungen. Blockierter Tab-Speicher verhindert keine Serverspeicherung. Rückmeldung/Abgabe bleiben unabhängig, löschen keine Entwürfe und überschreiben keine neueren Änderungen.

## BDD und Testzuordnung

| Given – When – Then | Nachweis |
| --- | --- |
| Geschriebener Text – Speicherung bestätigt – frischer Browser zeigt denselben Text | `learner-draft-persistence.spec.ts`, @feature-acceptance |
| Bestehender Entwurf – geleert – bleibt nach Laden leer | API/DB, Speichersteuerung |
| Laufende Anfrage – weitere Eingabe – alte Antwort verwirft keine neuen Zeichen | Speichersteuerung |
| Zwei Tabs – nacheinander speichern – letzter Stand wird geladen | API/DB, Browser |
| Netzausfall – Pausieren – Text bleibt, Wiederverbindung speichert | Speichersteuerung, Browser |
| Alter benutzerbezogener Tabtext – Editor öffnet – Text wird übernommen | Komponente |
| Fremder Schüler/Lehrer – Zugriff – verweigert | API/DB und direkte RLS |
| Freigabe fehlt/Kurs archiviert – Zugriff – verweigert; physische Löschung entfernt Entwürfe | API/DB |
| Rückmeldung/Abgabe – weitere Bearbeitung – Entwurf bleibt unabhängig | Komponente/Regression |

Zusätzlich: Unicode/Markdown, Grenzen, DB-Ausfall, Anmeldung, blockierter Speicher, Aufgabenwechsel, alte Antworten, Vorschauen ohne Schreibzugriff.

## Arbeitsfolge und Abnahme

Contract-first, dann Red-Green-Refactor: API/DB-Tests, Migration via Supabase CLI, Backend, Speichersteuerungstests, Editorintegration, Browsernachweis. Frameworkfreie Anwendungsfälle und explizite Dependencies, keine Inhalte in Logs. Migration vor Anwendungscode. `make local-ca-status`, dann `make verify-feature FEATURE=learner-draft-persistence` gegen den freigegebenen lokalen Stack. Keine Fertigmeldung oder Commit ohne erfolgreiches Gate; kein Push ohne Auftrag.

## Durchführungsnachweis

- Ausgangspunkt: sauberer `master`, `git pull --ff-only`: bereits aktuell.
- Implementierung abgeschlossen; die Nachweise stehen unten.

### Präzisierungen bei der Integration

- Die bestehende Rückmeldungs-Arbeitsansicht enthält einen aktiven Antworteditor. Dieser wird ebenso abgesichert; reine Vorschauen und abgeschlossene, schreibgeschützte Arbeitsansichten starten keine Speicherung.
- Die Kontextnavigation verwendet ausdrücklich vollständige Seitenwechsel. Ein zentraler Klickschutz wartet deshalb zusätzlich zur internen Navigation vor solchen Links auf die Speicherung. Bei einem Fehler kann der Schüler den Wechsel ablehnen.
- Die kurze bestehende Verzögerung für Tab-Speicherzugriffe (200 ms) bleibt erhalten. Serverzugriffe werden unabhängig davon nach 1 Sekunde Schreibpause/spätestens 5 Sekunden gebündelt.
- Red nachgewiesen: API zunächst 404 statt 204; fehlende Speichersteuerung; fehlende Editor-Serverspeicherung; fehlende Wiederherstellung bei initialem Netzfehler. Die gezielten Backend- und Frontendtests wurden danach grün.

- Datenschutzfall ergänzt: Der Browser sendet `X-Draft-Owner` als Behauptung über die beim Öffnen verwendete Identität. Bei Abweichung zur aktuellen Anmeldung lehnt der Server mit 403 ab. Das optionale Feld wählt niemals einen Eigentümer aus; Eigentümer bleibt ausschließlich die authentifizierte Person. So kann ein alter Tab nach Kontowechsel keine fremden Entwürfe in das neue Konto übertragen. Red: vorher 200 statt 403; danach gezielter API-/DB-Test.

### Abschluss und Nachweise

- Migration `20261101194250_learning_task_drafts.sql` mit `supabase migration up` lokal angewendet. Bestehende ENV-Konfiguration unverändert, keine neuen Geheimnisse oder Dienste. Web und Frontend über Docker Compose gebaut und gestartet; Supabase-Status erfolgreich geprüft.
- API-TDD: erwarteter erster Fehler 404 statt 204. Danach 14 gezielte API-/DB-Tests erfolgreich, einschließlich RLS, Kaskaden, Archivierung, beendeter Mitgliedschaft, modularer Freigaben, Übungsausschluss, Ausfall und Kontowechsel.
- Frontend-TDD: 12 Speichersteuerungstests und drei neue Komponentenabläufe erfolgreich; vorhandene Editorregressionen an den Servertransport angepasst. Svelte-Prüfung ohne Fehler oder Warnungen.
- `make local-ca-status`: System, Chromium/Codex und Firefox vertrauen der aktuellen lokalen CA. TLS-Prüfung unverändert aktiv.
- `make verify-feature FEATURE=learner-draft-persistence`: erfolgreich (Exit 0). 3.255 Backendtests bestanden, 48 bewusst übersprungene Tests; 954 Frontendtests bestanden, Produktionsbuild und H5P-Prüfungen erfolgreich. Der zusätzlich während der Abschlussprüfung ergänzte Kontowechseltest wurde im vollständigen gezielten API-Lauf separat grün nachgewiesen.
- Authentifizierter Browsernachweis im Gate erfolgreich: frischer Kontext mit erneutem Login, mehrere Schreibgeräte, leerer Text, verweigerter Lehrkraftzugriff und Netzausfall mit abgelehntem Seitenwechsel und anschließender Wiederherstellung. Laufbezogene Testkonten und Inhalte anschließend durch das vorhandene Harness bereinigt. Speicheranzeige anhand des Browser-Screenshots visuell geprüft.
- Dokumentation in Lernraum-Handbuch, Abgabehandbuch, Learning-Referenz und Changelog aktualisiert; Route Map und DB-Testinventar ergänzt. `git diff --check` und Ruff erfolgreich.
- Grenzen bleiben bewusst: keine Versionshistorie, keine parallele Live-Synchronisation, keine Zusicherung für Offline-Schließen des Tabs und keine allgemeine Kontolöschung. Kein Push.
