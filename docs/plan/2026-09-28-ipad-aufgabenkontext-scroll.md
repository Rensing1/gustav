# Erreichbarer Aufgabenkontext auf dem iPad

## User Story

Als Schüler möchte ich in der zweispaltigen Aufgabenansicht die linke Kontextspalte bis zum Ende scrollen können, damit ich „Weitere Materialien und eigene Abgaben“ erreichen und die dort angebotenen Inhalte während der Bearbeitung einblenden kann.

Die Änderung betrifft ausschließlich die responsive Höhe der bestehenden Aufgabenarbeitsfläche und ihre automatisierten Browsernachweise. API-Vertrag, Datenbankschema, Berechtigungen, gespeichertes Spaltenverhältnis und fachliche DTOs bleiben unverändert.

## Diagnose

Ab `60rem` Containerbreite erhält `.learner-task-workbench` derzeit `height: calc(100svh - 7.25rem)` und zugleich eine feste Mindesthöhe von `36rem`. Auf dem iPad im Querformat belegen App-Kopf, Lernraum-Werkzeugleiste und Aufgabenkopf jedoch mehr als die abgezogenen `7.25rem`. Die Arbeitsfläche reicht deshalb unter den sichtbaren Viewport. Der innere Kontext kann rechnerisch bis zu seinem Ende scrollen, während sein unterer Bereich weiterhin außerhalb des Bildschirms liegt. `overscroll-behavior: contain` verhindert zusätzlich, dass die Geste anschließend auf die äußere Seite übergeht.

Die bestehende Browserprüfung kontrolliert den numerischen Scroll-Endpunkt, aber nicht, ob Scrollfläche und letzter Bedienpunkt innerhalb des sichtbaren Viewports liegen.

## BDD-Szenarien und Testzuordnung

| Szenario | Given | When | Then | Automatisierter Test |
|---|---|---|---|---|
| Aufklapper auf dem iPad erreichbar | Eine angemeldete lernende Person bearbeitet eine Aufgabe mit weiterem geöffnetem Material im iPad-Querformat | Sie scrollt die linke Kontextspalte bis zum Ende | Scrollflächenende und Aufklapper liegen vollständig im Viewport | `frontend/e2e/learner-reference-workspace.spec.ts` (`@feature-acceptance`, Chromium und WebKit-iPad) sowie Detailprüfung in `learner-task-responsive.spec.ts` |
| Weiteres Material einblenden | Derselbe Aufklapper ist sichtbar | Er wird betätigt | Das weitere Modul und sein Material erscheinen in der linken Spalte | `frontend/e2e/learner-reference-workspace.spec.ts` |
| Unabhängige Spalten | Beide Spalten enthalten lange Inhalte | Links und rechts wird getrennt gescrollt | Nur die jeweils bediente Spalte verändert ihre Scrollposition | bestehender Ablauf in `frontend/e2e/learner-task-responsive.spec.ts` |
| Kurzer Viewport | Die breite Aufgabenansicht hat weniger als `36rem` nutzbare Höhe | Das Layout wird berechnet | Die Mindesthöhe überschreitet nicht die tatsächlich verfügbare Viewporthöhe | CSS-Vertrag in `LearnerContentWorkspace.test.ts` |
| Responsive Regression | Die Aufgabe wird im Querformat, Hochformat und auf dem Smartphone angezeigt | Die Viewportbreite wechselt | Zweispaltenansicht, kompakter Umschalter und Spaltentrenner behalten ihr bestehendes Verhalten ohne horizontalen Überlauf | bestehender Ablauf in `frontend/e2e/learner-task-responsive.spec.ts` |
| Dialog-Regression | Eine KI-Dialogaufgabe verwendet dieselbe Arbeitsfläche | Die breite Ansicht wird dargestellt | Gespräch und Eingabe bleiben innerhalb der gemeinsamen viewportbegrenzten Höhe nutzbar | `LearningDialogWorkspace.test.ts` |

## Red-Green-Refactor

1. CSS-Vertrag und authentifizierten Browserablauf so erweitern, dass die aktuelle Höhenregel fehlschlägt.
2. Die breite Arbeitsfläche auf den bereits für Dialogaufgaben verwendeten Höhenvertrag `calc(100svh - 14rem)` umstellen und die Mindesthöhe mit der verfügbaren Höhe begrenzen.
3. Doppelte Dialog-Höhenregeln entfernen; dialogspezifische Scroll- und Composer-Regeln unverändert lassen.
4. Komponenten- und Browserprüfungen bei `1024 × 768`, `1180 × 820`, `820 × 1180` und `390 × 844` ausführen.

## API- und Datenbankentwurf

Es sind keine Änderungen an `api/openapi.yml` und keine Supabase/PostgreSQL-Migration erforderlich. Die Korrektur verändert ausschließlich die Darstellung bereits autorisierter Daten im Browser.

## Abnahme

- Gezielte Vitest-Prüfungen für Lernenden- und Dialogarbeitsfläche.
- `make local-ca-status` vor Browserprüfungen; TLS und Secure-Cookies bleiben unverändert.
- `make test-feature-detail FEATURE=learner-task-responsive` für die vollständige Responsive-Matrix.
- `make verify-feature FEATURE=learner-reference-workspace` vor Fertigmeldung und Commit.
