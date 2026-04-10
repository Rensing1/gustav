# Intermittente Rueckmeldungsfehler nach erfolgreichem Bild-/PDF-Upload durch ungueltige `criterion_idx`-Ausgaben

## Problem

Bei nativen Aufgaben mit Bild- oder PDF-Upload kommt es in Prod nach erfolgreichem Upload und nach `Rueckmeldung einholen` sporadisch zu einer fehlgeschlagenen Rueckmeldung.

Aus Nutzersicht zeigt sich das so:

- der Upload selbst klappt
- die Abgabe wird angenommen
- nach einiger Wartezeit erscheint `Die Rueckmeldung konnte nicht erstellt werden.`
- eine spaetere Wiederholung kann auf derselben Aufgabe ploetzlich erfolgreich sein

Das Problem ist damit nicht als reiner Upload- oder Storage-Defekt einzuordnen.

## Beobachtete Hinweise

- Der Fehler war am 10. April 2026 in Prod mehrfach sichtbar.
- Betroffene Abgaben wurden in `public.learning_submissions` angelegt.
- Der Fehlercode der fehlgeschlagenen Faelle lautet `feedback_invalid_analysis`.
- Auf derselben Aufgabe und im selben Umfeld gab es spaeter wieder erfolgreiche Abschluesse.

## Technischer Befund

- Upload-Intent, Storage-`PUT`, Submission-Insert und Polling funktionieren.
- Der Defekt entsteht danach im strukturierten Feedback-Pfad fuer native visuelle Abgaben.
- Der Worker verwendet fuer solche Faelle den Analysemodus `visual_direct`.
- Die UI-Meldung `Die Rueckmeldung konnte nicht erstellt werden.` wird angezeigt, sobald die gepollte Submission `analysis_status = failed` hat.

Konkrete Ursache:

- Die strukturierte Visual-Analyse kann eine ungueltige `criterion_idx`-Liste erzeugen.
- In einem reproduzierten Fehlfall mit sechs Kriterien lieferte die Analyse wiederholt eine Indexfolge wie:
  - `0,1,2,3,8,5`
- Der gemeinsame Mapper fuer strukturierte Kriterienergebnisse erwartet nur Indizes im Bereich `0..N-1` und genau einen Eintrag pro Kriterium.
- Der out-of-range-Index fuehrt dadurch zu `invalid_criterion_idx`.
- Dieser Fehler wird im Worker korrekt als `feedback_invalid_analysis` gespeichert und endet terminal.

## Wichtige Abgrenzung

Nicht die Ursache:

- Upload-Header
- Storage-Allowlist
- Dateiablage in Supabase Storage
- Auth-/Session-Probleme

Der Fehler liegt nachgelagert in der strukturierten Analyse der Rueckmeldung.

## Warum das als intermittent erscheint

- Dieselbe Aufgabenart kann zunaechst mit `feedback_invalid_analysis` fehlschlagen und spaeter erfolgreich durchlaufen.
- Das spricht gegen einen dauerhaft kaputten Task oder einen defekten Upload.
- Stattdessen deutet es auf instabilen oder formal ungueltigen Modelloutput im strukturierten Analysepfad hin.

## Umsetzungsziel

Der gemeinsame strukturierte Analysepfad fuer Rueckmeldungen soll robust genug werden, dass erfolgreiche Bild-/PDF-Abgaben nicht mehr regelmaessig an ungueltigen `criterion_idx`-Ausgaben scheitern.

Der Fix soll die Ursache im Analyse-/Parser-Zusammenspiel beseitigen, nicht nur die UI-Meldung umgehen.

## Arbeitspakete

### 1. Shared-Structured-Analysis haerten

- gemeinsamen Mapper fuer strukturierte Kriterienergebnisse gegen out-of-range, duplicate und missing `criterion_idx` ueberpruefen
- entscheiden, ob es einen kontrollierten Fallback fuer formal verwertbare, aber indexseitig ungueltige Modellantworten geben soll
- Text- und Visual-Pfad gemeinsam betrachten, da dieselbe Parser-Schwachstelle in mehreren Rueckmeldungspfaden relevant ist

### 2. Analyse deterministischer machen

- pruefen, ob die strukturierte Analyse mit deterministischeren Modellparametern laufen sollte
- Analyse und Rueckmeldungssynthese gegebenenfalls getrennt konfigurieren

### 3. Logging und Telemetrie verbessern

- invaliden Modelloutput klar von Transport-, Provider- oder Storage-Fehlern unterscheiden
- strukturierte Hinweise fuer out-of-range, duplicate und missing `criterion_idx` loggen
- keine PII, keine Submission-IDs und keine Storage-Keys in oeffentliche Artefakte aufnehmen

### 4. Regressionstests erweitern

- Test fuer out-of-range `criterion_idx` in der strukturierten Analyse
- Test fuer visuelle native Abgaben mit erfolgreich angelegter Submission, aber invalidem Analyseoutput
- Test fuer das gewuenschte Verhalten bei parserseitig problematischen, aber fachlich noch auswertbaren Antworten

## Akzeptanzkriterien

- Erfolgreiche Bild-/PDF-Uploads auf nativen Aufgaben fuehren im Normalfall auch zu einer erfolgreichen Rueckmeldung.
- `feedback_invalid_analysis` sinkt fuer diese Faelle deutlich und ist in Logs klar erklaerbar.
- Out-of-range-, duplicate- und missing-`criterion_idx`-Faelle sind automatisiert getestet.
- Das Ticket und seine Umsetzung bleiben frei von PII, Secrets und konkreten Nutzerbezeichnungen.
