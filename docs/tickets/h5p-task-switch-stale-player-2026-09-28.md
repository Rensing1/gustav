# H5P: Aufgabenwechsel zeigt zuvor bearbeiteten Inhalt

## Nutzerperspektive

Als Lernender möchte ich mehrere H5P-Aufgaben eines Moduls nacheinander bearbeiten, sodass jede ausgewählte Aufgabe ihren eigenen Inhalt und Fortschritt zeigt.

## Fehler und Befund

Beim Wechsel von Aufgabe A zu Aufgabe B kann der bereits bearbeitete Inhalt von A sichtbar bleiben. Die Arbeitsfläche verwendet `LearningTaskCard` erneut; deren H5P-Zweig hatte keine eigene Identität. `H5PTaskPlayer` erstellt sein Webcomponent dagegen ausschließlich in `onMount`. Neue Props allein ersetzen dessen Inhalt nicht. Eine verspätete Speicherantwort konnte zusätzlich den inzwischen geänderten Fortschritts-Callback erreichen.

Der Fehler ist mit synthetischen Aufgaben und dem echten Svelte-Player reproduziert: Vier Wechselvarianten und der verspätete Callback scheitern vor dem Fix. Der H5P-Runtime-Loader und HTTP-Zugriffe sind im Test ersetzt; keine produktiven Inhalte oder Konten werden verwendet.

## Korrektur

Der H5P-Zweig erhält einen Svelte-Key aus Kurs-, Aufgaben- und Inhalts-ID. Ein Identitätswechsel räumt den bisherigen Player über dessen vorhandenen Destroy-Hook auf und initialisiert den ausgewählten Inhalt. Fortschrittsaktualisierungen derselben Aufgabe behalten den Player. Nach einem bereits gestarteten Speichervorgang unterdrückt ein zerstörter Player den inzwischen veralteten UI-Callback; der laufende Speichervorgang selbst wird nicht abgebrochen.

Kein neuer Zustandsmanager, keine Abhängigkeit und keine Änderung an API, Datenbank oder H5P-Inhalten. Der Hotfix betrifft H5P-Aufgaben in der Lernarbeitsfläche. Die eigenständige Übungssitzung ist nicht Gegenstand dieser Änderung.

## Akzeptanz und Regressionen

- Gegeben ist eine bearbeitete Aufgabe A; wenn B im selben Arbeitsbereich gewählt wird, erscheint ein neuer Player mit Inhalt und Kontext von B.
- Modellabruf und nächste Abgabe verwenden Kurs und Aufgabe B; Ereignisse des entfernten Players erzeugen keine weiteren Abgaben.
- Auch verschiedene Aufgaben mit demselben H5P-Inhalt sowie ein Kurs- oder Inhaltswechsel erhalten einen passenden Player.
- Eine reine Fortschrittsaktualisierung derselben Aufgabe erhält den laufenden Player.
- Eine verspätete erfolgreiche Speicherung von A verändert die Anzeige beziehungsweise Zuordnung von B nicht.

## Validierung

Vor dem Fix: fünf neue Regressionen fehlgeschlagen, ein Kontrollfall bestanden. Nach dem Fix: sechs neue und vier vorhandene H5P-Tests bestanden; Svelte-/TypeScript-Prüfung ohne Fehler oder Warnungen. Die vollständige Frontend-Suite, acht Build-/CSS-Regeltests und der Produktionsbuild sind erfolgreich abgeschlossen. Keine Datenbank-/Browsertests gegen Produktion und keine künstlichen Lernabgaben.
