# Kummerkasten dauerhaft in der Kopfleiste

## User Story

Als Schüler oder Lehrkraft möchte ich den Kummerkasten aus jeder Ansicht mit einem Klick erreichen, damit Rückmeldungen nicht hinter Kontoeinstellungen verborgen sind.

## BDD-Szenarien

1. Given ein angemeldeter Schüler auf einer beliebigen Seite, when die Kopfleiste erscheint, then sieht er den ausgeschriebenen Link „Kummerkasten“ und erreicht darüber `/learning/kummerkasten`.
2. Given ein Schüler arbeitet in einer geöffneten Lerneinheit, when die Hauptnavigation durch den Lernpfad ersetzt wird, then bleibt der Kummerkasten in der Kopfleiste sichtbar.
3. Given eine angemeldete Lehrkraft, when sie den Kummerkasten auswählt, then erreicht sie `/teaching/kummerkasten`.
4. Given die Kummerkasten-Seite ist geöffnet, then trägt der Kopfleistenlink `aria-current="page"`.
5. Given das Kontomenü wird geöffnet, then enthält es nur „Profil“ und „Abmelden“, aber keinen Kummerkasten-Link.
6. Given eine schmale Ansicht mit 390 Pixeln Breite, then bleiben Kummerkasten, Theme-Schalter und Konto erreichbar, ohne horizontalen Seitenüberlauf.
7. Given ein nicht angemeldeter Besucher, when die Kopfleiste erscheint, then wird kein Kummerkasten-Link angeboten und die geschützten Routen bleiben unverändert abgesichert.

## Testzuordnung und TDD

- Der Layout-Vertrag prüft den rollenabhängigen Zielpfad, den aktiven Zustand, die Position außerhalb des Kontomenüs und die responsive CSS-Regel.
- Ein mit `@feature-acceptance` markierter Playwright-Test prüft für eine echte Schüler- und Lehrkraftsitzung die Navigation über Oberfläche, Server und produktionsnahe Datenhaltung. Die Schüleransicht wird zusätzlich innerhalb einer geöffneten Lerneinheit und bei 390 Pixeln Breite geprüft.
- RED: Zuerst werden die Vertragstests und der Browser-Akzeptanztest ergänzt.
- GREEN: Danach wird nur die notwendige Layout- und CSS-Änderung umgesetzt.
- REFACTOR: Rollenpfad und aktiver Zustand werden als kleine, lesbare Layout-Helfer gekapselt.
- Abschluss: `make verify-feature` muss erfolgreich durchlaufen.

## Umsetzung

- Der Kummerkasten erscheint als ausgeschriebene Sekundäraktion vor der Werkzeuggruppe aus Theme-Schalter und Konto.
- Der Pfad wird aus der bereits geladenen Rolle abgeleitet: Schüler verwenden `/learning/kummerkasten`, Lehrkräfte `/teaching/kummerkasten`.
- Auf kleinen Bildschirmen nutzt die Steuerungszeile die verfügbare Breite. Der sichtbare Kontoname darf dort zugunsten der bereits vorhandenen Initialenkachel entfallen.
- Profil und Abmeldung bleiben im Kontomenü; der Kummerkasten wird daraus entfernt.
- Hauptnavigation, Lernpfad-Brotkrümel und Kummerkasten-Seiten bleiben unverändert.

## Schnittstellen und Datenhaltung

Es sind keine Änderungen an OpenAPI, Backend, Datenbankschema, Migrationen oder öffentlichen Typen erforderlich. Die vorhandenen Rollen- und Routenverträge werden wiederverwendet.
