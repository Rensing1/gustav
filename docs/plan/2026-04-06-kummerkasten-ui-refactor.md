# Kummerkasten UI-Refactor

## Ziel

Der Kummerkasten soll gestalterisch an den verbindlichen Designvertrag aus
`docs/DESIGN.md` angepasst werden. Die Seiten für Lernende und Lehrkräfte
bleiben fachlich unverändert, werden aber auf globale Komponenten und
wiederverwendbare Kummerkasten-Bausteine umgestellt.

## Vorgehen

1. Zuerst fehlschlagende Frontend-Tests für die gewünschte Struktur schreiben.
2. Gemeinsame Kummerkasten-Komponenten für Formular und Inbox-Eintrag anlegen.
3. Beide Routen auf `PageActionHead`, `ModeSwitch`, `QuietList` und die neuen
   gemeinsamen Komponenten umstellen.
4. Den globalen Seitenkopf in den beiden Kummerkasten-Loads ausblenden, damit
   der Seitenkopf nicht doppelt erscheint.
5. Darstellung an die harte Produktsprache anpassen: keine pilligen Umschalter,
   keine generischen Karten, formatierte Metadaten.

## Akzeptanz

- Die Route-Dateien enthalten keine route-lokalen Kummerkasten-Layouts mehr.
- Lehrkraft-Scopes verwenden `ModeSwitch`.
- Lehrkraft-Beiträge werden als ruhige Liste mit gemeinsamer Eintragskomponente
  dargestellt.
- Lernende verwenden eine gemeinsame Formular-Komponente.
- Die Kummerkasten-Seiten zeigen keinen doppelten Seitenkopf.
