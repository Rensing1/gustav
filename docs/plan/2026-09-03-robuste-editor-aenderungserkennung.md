# Robuste Änderungserkennung in Lernenden- und Lehrkrafteditoren

**Status:** umgesetzt
**Datum:** 3. September 2026

## Ausgangslage

Die Lernendenoberfläche vergleicht den lokalen Editorinhalt als rohe Zeichenkette mit dem serverseitig gespeicherten Rückmeldungsentwurf. Der Speicherpfad entfernt jedoch führenden und abschließenden Weißraum. Dadurch kann „Überarbeitung noch nicht geprüft“ erscheinen, obwohl nur eine vom Server verworfene Leerzeile abweicht.

Im Moduleditor besitzt die lokale Entwurfserkennung nur für bestehende Materialien einen gespeicherten Ausgangs-Snapshot. Für bestehende Aufgaben speichert deshalb bereits ein technisch ausgelöstes `input`- oder `change`-Ereignis einen Browserentwurf, selbst wenn alle Werte unverändert sind.

## User Stories

- Als lernende Person möchte ich eine unveränderte rückgemeldete Fassung ohne falschen Warnhinweis endgültig abgeben können, auch wenn mein lokaler Editor nur führenden oder abschließenden Weißraum enthält.
- Als Lehrkraft möchte ich eine gespeicherte Aufgabe öffnen und wieder verlassen können, ohne dass technische Editorereignisse einen fachlich falschen Entwurfsstatus erzeugen.
- Als Lehrkraft möchte ich echte Änderungen weiterhin im aktuellen Browser-Tab wiederfinden und die Entwurfsmarkierung durch vollständiges Zurücksetzen entfernen können.

## BDD-Szenarien und Testzuordnung

1. **Unveränderte Lernendenfassung mit Rand-Weißraum**
   - Given ein lokaler Text unterscheidet sich vom gespeicherten Rückmeldungsentwurf nur durch führenden oder abschließenden Weißraum, when „Endgültig abgeben“ gewählt wird, then beginnt die Finalisierung ohne Warnhinweis.
   - Nachweis: Finalisierungshelper, `LearningTaskCard` und authentifizierter Browserlauf in `learner-task-finalization.spec.ts`.
2. **Echte oder leere Überarbeitung**
   - Given der innere Text wurde geändert oder die nichtleere Fassung vollständig geleert, when finalisiert wird, then erklärt der bestehende Dialog, dass die ältere geprüfte Fassung abgegeben wird.
   - Nachweis: bestehende und ergänzte Komponentenregressionen.
3. **Unveränderte Lehrkraftaufgabe**
   - Given eine gespeicherte Aufgabe, when der Editor ein gleichwertiges Eingabeereignis meldet und die Lehrkraft zu „Inhalte“ zurückkehrt, then erscheinen weder „Entwurf“ noch „Verwerfen“.
   - Nachweis: reine Snapshot-Tests, Seiteninteraktionstest und authentifizierter Browserlauf in `teacher-graph-module-actions.spec.ts`.
4. **Echte Aufgabenänderung und vollständige Rücknahme**
   - Given eine gespeicherte Aufgabe, when ein relevantes Feld geändert wird, then wird nur für diese Aufgabe ein lokaler Entwurf gespeichert; when alle Felder wieder der gespeicherten Fassung entsprechen, then wird dieser Entwurf entfernt.
   - Nachweis: Snapshot- und Seiteninteraktionstests.
5. **Aufgabenvarianten**
   - Given eine normale, H5P-, Datei-/Projekt- oder Dialogaufgabe in einem Lern- oder Übungsmodul, when deren Formularwerte verglichen werden, then umfasst die Baseline genau die für diesen Typ speicherbaren Felder und dieselbe Normalisierung wie der Serverpfad.
   - Nachweis: tabellarische Unit-Tests für Aufgaben-Snapshots und Normalisierung.

## Vertrag, Daten und Sicherheitsgrenze

Die bestehenden API-Endpunkte, Request-Bodies, Datenbanktabellen und RLS-Regeln bleiben unverändert. Die Korrektur betrifft ausschließlich lokale Vergleichs- und Browserentwurfslogik. Die endgültige Abgabe bleibt an die explizite `feedback_submission_id` und den daraus abgeleiteten Idempotenzschlüssel gebunden. Lehrkraftentwürfe bleiben über Lehrkraft, Lerneinheit, Modul und Inhalt im `sessionStorage` getrennt.

Die verbindliche Gleichheitsregel lautet „wie gespeichert“: Felder werden mit derselben Normalisierung verglichen, die der jeweilige Speicherpfad tatsächlich anwendet. Unterschiedliche Markdown-Quelltexte bleiben Änderungen, wenn sie unterschiedlich gespeichert würden.

## Red–Green–Refactor

1. Fehlende Regressionen für Rand-Weißraum und gleichwertige Aufgabenereignisse rot ergänzen.
2. Lernendentexte vor dem Warnvergleich auf beiden Seiten mit `trim()` normalisieren.
3. Reine, typabhängige Aufgaben-Snapshots ergänzen und aktuelle Aufgabenwerte nach der serverseitigen Speichersemantik normalisieren.
4. Die bestehende Materialsemantik unverändert lassen und die Svelte-Seite nur noch Baseline-Auflösung und Browserpersistenz koordinieren lassen.
5. Gezielte Tests, Svelte-Typprüfung und beide zugeordneten Feature-Gates ausführen.

## Abschlusskriterien

- Rand-Weißraum erzeugt keinen falschen Lernendenhinweis; innere Änderungen und Leeren bleiben erkennbar.
- Gleichwertige Aufgabenereignisse erzeugen keinen Lehrkraftentwurf; echte Änderungen und Rücknahmen funktionieren für alle Aufgabentypen.
- `make verify-feature FEATURE=learner-task-finalization` und `make verify-feature FEATURE=teacher-graph-module-actions` bestehen.
- Changelog und dieser Plan enthalten den abschließenden Red-Green-Refactor- und Prüfnachweis.

## Umsetzung und Prüfnachweis

- **Red:** Die ergänzten Unit-, Komponenten- und Seiteninteraktionstests zeigten elf erwartete Fehler: Der Lernendenvergleich behandelte Rand-Weißraum als Änderung, und für bestehende Aufgaben fehlten Snapshot-Aufbau und normalisierter Vergleich vollständig.
- **Green:** Der Lernendenvergleich normalisiert beide Fassungen wie der Speicherpfad mit `trim()`. Der Lehrkrafteditor baut für bestehende Materialien und alle Aufgabenarten reine Baselines auf; Aufgabenwerte werden feldspezifisch wie beim Speichern normalisiert. Gleichwertige Editorereignisse entfernen einen vorhandenen Sitzungseintrag, echte Unterschiede speichern ihn weiterhin.
- **Refactor:** Snapshot-Aufbau und Vergleich liegen als frameworkfreie Funktionen außerhalb der Svelte-Seite. Die Materialsemantik bleibt unverändert; insbesondere wird gespeicherter Markdown-Materialinhalt nicht pauschal getrimmt.
- **Gezielte Prüfung:** Vier Vitest-Dateien mit insgesamt 118 Tests bestanden; `npm run check` meldete 0 Fehler und 0 Warnungen.
- **Authentifizierte Abnahme:** Der Lernenden-Kernpfad finalisierte eine Fassung mit abschließender Leerzeile ohne Warnung und zeigte bei einer echten späteren Überarbeitung weiterhin die Warnung. Der Lehrkraft-Kernpfad erzeugte bei einem unveränderten Editorereignis keinen Entwurf, bei einer echten Änderung dagegen schon und entfernte ihn nach vollständiger Rücknahme.
- **Verbindliche Gates:** `make verify-feature FEATURE=learner-task-finalization` und `make verify-feature FEATURE=teacher-graph-module-actions` bestanden jeweils einschließlich 2.556 Backendtests, 673 Frontendtests, Svelte-Typprüfung, Produktionsbuild, H5P-Sidecar-Tests, Chromium-Abnahme und bestätigter Bereinigung der Testdaten.
- **Schnittstellen:** `api/openapi.yml`, Datenbank, Migrationen, RLS und Backend-Endpunkte blieben unverändert.
