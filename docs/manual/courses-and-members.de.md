# Kurse und Mitglieder

GUSTAV-Version: 0.0.4
Zuletzt geprüft: 2026-08-20
[English version](courses-and-members.en.md)

![Kursübersicht einer Lehrkraft](../assets/readme/teacher-course-overview.jpg)

## Zweck

Ein Kurs bildet eine konkrete Lerngruppe ab. Er verbindet Mitglieder mit den Lerneinheiten, die im Unterricht verwendet werden. Lehrkräfte können aktive Kurse verwalten, Klassen einladen und abgeschlossene Kurse archivieren.

## Voraussetzungen

- Du bist als Lehrkraft angemeldet.
- Für Einladungen und Änderungen muss der Kurs aktiv sein.
- Titel, Fach, Jahrgang und Schuljahr müssen vollständig eingetragen sein, bevor Mitglieder, Einladungen und Lerneinheiten zuverlässig verwaltet werden können.

## Schritt für Schritt

1. Öffne **„Kurse“** und wähle **„Neuer Kurs“**.
2. Trage Titel, Fach, Jahrgang und Schuljahr ein und wähle **„Kurs anlegen“**.
3. Öffne den Kurs. Unter **„Mitglieder“** kannst du über **„Mitglied hinzufügen“** einzelne vorhandene Lernende suchen und aufnehmen.
4. Für eine ganze Klasse wählst du **„Klasse einladen“**. Der gemeinsame Link ist 24 Stunden gültig. Du kannst ihn kopieren, als QR-Code anzeigen oder herunterladen und Einladungen an erlaubte Schul-E-Mail-Adressen senden.
5. Unter **„Lerneinheiten“** ordnest du dem Kurs vorhandene Inhalte zu. Die Erstellung der Inhalte wird in [Lerneinheiten und Freigaben](learning-units-and-releases.de.md) erklärt.
6. Nach Ende des Unterrichtszeitraums kannst du den Kurs unter **„Kurs bearbeiten“** archivieren. Eine versehentliche Archivierung lässt sich im Bereich **„Archiv“** mit **„Wiederherstellen“** rückgängig machen.

![Einladung mit Link und QR-Code](../assets/readme/course-invitation.jpg)

## Lernendensicht

Mitglieder sehen einen aktiven Kurs unter **„Aktuelle Kurse“** im Lernraum. Archivierte Kurse erscheinen als vergangene Kurse und sind nicht mehr für die aktive Bearbeitung gedacht. Wer einen gültigen Klassenlink nach Anmeldung oder Registrierung einlöst, tritt genau diesem Kurs bei.

## So funktioniert es

Nur die besitzende Lehrkraft darf einen Kurs verändern. Pro Kurs gibt es höchstens einen aktiven Klassenlink. Ein neu erzeugter Link widerruft den vorherigen; beim Archivieren wird ein vorhandener Link ebenfalls ungültig. Wird ein über den Link beigetretenes Mitglied später entfernt, ermöglicht derselbe Link keinen unbeabsichtigten Wiedereintritt.

Beim Archivieren bleiben Lernleistungen erhalten, der Kurs wird jedoch schreibgeschützt. Vor einer endgültigen Löschung zeigt GUSTAV, wie viele Mitgliedschaften, Abgaben, Dialoge und Dateien betroffen sind.

## Grenzen

- Eine gemeinsame Einladung ist immer genau 24 Stunden gültig; eine andere Laufzeit kann die Lehrkraft nicht wählen.
- Ein archivierter oder unvollständig konfigurierter Kurs kann nicht normal weiterbearbeitet werden.
- Entfernte Mitglieder verlieren den Kurszugriff. Eine neue Mitgliedschaft muss bewusst hergestellt werden.
- Das endgültige Löschen eines Kurses ist nicht rückgängig zu machen und entfernt auch zugehörige Lernleistungen.
- Ein Klassenlink ist kein öffentlicher Kurs: Anmeldung beziehungsweise Registrierung und die Lernendenrolle bleiben erforderlich.

## Typische Probleme

- **„Kursdaten unvollständig“:** Öffne **„Kurs bearbeiten“** und ergänze Fach, Jahrgang oder Schuljahr.
- **Kein gültiger Klassenlink:** Öffne **„Klasse einladen“** und erzeuge einen neuen Link.
- **Lerneinheit fehlt bei der Auswahl:** Die Lerneinheit muss dir gehören und darf dem Kurs nicht bereits zugeordnet sein.
- **Kurs ist schreibgeschützt:** Stelle einen versehentlich archivierten Kurs wieder her, bevor du ihn änderst.

## Verwandte Kapitel

- [Lerneinheiten und Freigaben](learning-units-and-releases.de.md)
- [Lernraum](learner-workspace.de.md)
- [Live-Ansicht](live-view.de.md)
- [Diagnostik](diagnostics.de.md)

Technische Details: [Teaching-Referenz](../references/teaching.md) und [Benutzerverwaltung](../references/user_management.md).
