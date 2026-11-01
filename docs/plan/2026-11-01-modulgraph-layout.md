# Modulgraph: horizontale Lernwege und strukturelle Zeilenumbrüche

## User Story und Designvertrag

Als Schüler oder Lehrkraft möchte ich Lernwege, Verzweigungen und Voraussetzungen in derselben übersichtlichen Modulkarte erkennen können. Phasen folgen untereinander; jede Zeile läuft von links nach rechts. Vier Spalten sind die normale Kapazität. Eine Verzweigung bleibt bis zu ihrer Zusammenführung zusammen und darf breiter werden. Freie Module bilden ein Raster ohne erfundene Verbindungen. Geräte und Rollen teilen dieselbe Geometrie.

Der verbindliche Designvertrag bleibt maßgeblich: gemeinsame Kartenmaße, ruhige Flächen, bestehende Tokens, phasenweise Zentrierung, gemeinsame Phasenbreite, lesbarer Startfokus und ausdrückliche Gesamtansicht. Auswahl, Fortschritt und Eigenschaftenleiste verändern weder Geometrie noch Ausschnitt. Lineare Lerneinheiten bleiben unverändert.

## Umsetzung und Schnittstellen

1. Red: Trennstellen, Ketten mit 1/3/4/5/8 Modulen, offene und geschlossene Verzweigungen, überspringende Kanten, freie Module und leere Phasen testen.
2. Green: reine Strukturplanung je Phase. Zusammenhängende Komponenten nach gespeicherter Position ordnen, Abhängigkeitsebenen bestimmen, nur Grenzen mit genau einer überquerenden Kante schneiden. Letzte Grenze innerhalb von vier Ebenen verwenden, sonst nächste Grenze dahinter. Einzelmodule in Viererzeilen zusammenfassen.
3. ELK ordnet jede Zeile horizontal an und berechnet orthogonale Kanten. Unsichtbare Ein-/Ausgänge führen externe Verbindungen an den Zeilenrand. Reservierte Spuren verbinden Zeilen und Phasen. Alle Pfade und Maße werden gemeinsam berechnet; der Renderer zeichnet die gelieferten Wegpunkte.
4. Bestehende Rollenadapter und Worker wiederverwenden. Rollenunabhängige Geometrie innerhalb einer Ansicht bei gleicher Struktur wiederverwenden; überholte Ergebnisse und Fehler dürfen keinen neueren gültigen Zustand überschreiben. Nur den Kameraschlüssel versionieren.
5. Drag & Drop verändert ausschließlich die gezogene ID relativ zum Zielmodul. Unverändertes Loslassen erzeugt keine Umsortierung. Serverseitig abgelehnte Reihenfolgen stellen den gültigen Zustand wieder her.
6. Refactor: klare englische Why-Kommentare, kleine Funktionen, stabile Eingaben, keine zweite Layoutbibliothek und kein allgemeiner eigener Hindernisrouter.

API Contract-First geprüft: vorhandene Graph- und Reorder-Verträge reichen aus; keine API-, Berechtigungs-, Schema- oder Migrationsänderung und deshalb kein neuer pytest-Endpunkttest. Die bestehende ELK-JavaScript-Version kann manuell vorgegebene Umbruchlisten nicht importieren; diese Option wird nicht verwendet. Neue Typen bleiben interne Frontend-Geometrie.

## BDD und Testzuordnung

| Gegeben | Wenn | Dann | Nachweis |
| --- | --- | --- | --- |
| Ketten mit 1/3/4/5/8 Modulen | Graph aufbauen | Viererzeilen; fünf als 4 + 1, acht als 4 + 4 | Struktur- und ELK-Integrationstests |
| Verzweigungen, Zusammenführungen und lange Kanten | Zeilen planen | Nur eine echte Verbindung überquert jede Trennstelle | Strukturtests |
| Freie Module, getrennte Teilgraphen, Übungsmodule, leere Phasen | Anordnen | Alle Elemente vorhanden, keine erfundenen Kanten | Layouttests |
| Interne, umgebrochene und phasenübergreifende Kanten | Pfade berechnen | Keine fremden Karten oder Phasenbeschriftungen durchschnitten | Geometrische Integrationstests mit echtem ELK |
| Beide Rollen und geänderte Auswahl/Fortschritte | Graph aktualisieren | Identische Geometrie, unveränderter Ausschnitt | Paritätstests und `graph-role-parity.spec.ts` |
| Authentifizierter Schüler | Modul öffnen, zurückkehren, neu laden | Echter Inhalt erreichbar, Fokus und Kamera erhalten | `@feature-acceptance` in derselben Spec |
| Lehrkraft, unabhängige oder abhängige Module | Loslassen oder umsortieren | Nur gezogene ID bewegt; Ablehnung stellt Zustand wieder her | Reorder-Unit- und Browsertests |
| Fehler oder überholtes Layout | Ergebnis empfangen | Verständlicher Fehler, wiederholbar, kein Überschreiben neuerer Ergebnisse | Fehler-/Aktualisierungstests |
| 320/390/768/1024/1440 px, Hell/Dunkel | Graph bedienen | Gleiche Karte, lesbarer Einstieg, erreichbare 44-px-Werkzeuge, kein Seitenüberlauf | Browsermatrix und Sichtprüfung |

## Abnahme

- Vor Browserprüfungen `make local-ca-status`; reguläres TLS und freigegebener lokaler Stack.
- Verbindlich vor Fertigmeldung und Commit: `make verify-feature FEATURE=graph-role-parity`.
- Betroffene visuelle Referenzen und Graph-Kompatibilitätsfälle gezielt prüfen. Referenzen erst nach Sichtprüfung aktualisieren. Keine historische Gesamtsuite.
- Designvertrag, Anleitungen und Changelog an den geprüften Stand anpassen.
- Direkt auf `master` committen; kein Push.

## Verlauf

- Ausgangsarbeitsbaum sauber; `master` ist mit Remote abgeglichen.
- Implementierung beginnt mit fehlschlagenden Verhaltenstests.

+- Red nachgewiesen: zunächst 21 fehlschlagende Verhaltenstests; neue Browserprüfungen weisen die alte senkrechte Darstellung nach. Weitere Regressionstests reproduzieren den 61-px-Zeilenversatz und die blockierte Kindmodul-Verschiebung bei ausgewählter Phase.
+- Green: Strukturplanung, horizontales ELK-Zeilenlayout und explizite Verbindungsspuren umgesetzt. Sichtbare Karten werden als gemeinsamer Phasenblock zentriert; auch eine kurze Fortsetzungszeile beginnt links. Ein- und Ausgänge werden ausschließlich für die Berechnung verwendet.
+- Refactor: Kanten je Zeile vorab indexiert, eigene Geometrie je Ansicht bei gleicher Struktur wiederverwendet, gezielte Knotensubskriptionen für die Drag-Vorschau. Die Auswahl einer Phase ist ein visueller Zustand und keine technische Gruppenauswahl; damit bleiben ihre Kindmodule ziehbar.
+- Der Kantenrenderer übernimmt die Wegpunkte und verankert Enden an den tatsächlichen Handles. Die bestehende Auswahlaktion liegt auf einem geraden Pfadsegment. Neue berechnete Kanten verwenden den vorhandenen kontrastreichen Kontur-Token; der Browser prüft mindestens 3:1 in Hell und Dunkel.
+- Ein zentraler authentifizierter Abnahmerundlauf in `graph-role-parity.spec.ts` verbindet Rollenvergleich, Browsermatrix, Achterkette, freies Raster, gültige und abgelehnte Verschiebung sowie Modulöffnung/Rückkehr. Das Repository erlaubt ausdrücklich nur einen zentralen Abnahmerundlauf je Spec.
+- Gezielte Graph- und Integrationsprüfungen sowie Svelte-Check erfolgreich; vollständige Frontendtests: 923 Tests und 11 Toolingtests erfolgreich.
+- Authentifizierter Graph-Rundlauf erfolgreich (40,1 Sekunden); alle laufbezogenen Daten durch den vorhandenen Owner-Cleanup entfernt.
+- Die sechs bestehenden Graph-Kompatibilitätsfälle unter Chromium und WebKit mit den Profilen camera/combined/modern sind erfolgreich. Das ist Browseremulation, keine Prüfung auf einem physischen alten iPad.
+- Die betroffenen visuellen Graph-Referenzen für Inspector und Löschdialog in Hell/Dunkel sowie Desktop/Tablet/Mobil bestehen unverändert. Zusätzlich die neuen Zeilenlayouts anhand der Browserbilder kontrolliert; lokale Nachweise liegen ignoriert unter `.tmp/modulgraph-layout/`.
+- Der erste vollständige Gateversuch scheiterte an einem TLS-Timeout beim Abruf des unveränderten Keycloak-Basisimages. Isolierte Wiederholung: alle 14 Prüfungen erfolgreich. Der nächste Gateversuch fand zwei nach der Auslagerung anzupassende Quelltextverträge (Worker-Ladestelle und ein zentraler Abnahmerundlauf je Spec); beide sind korrigiert und in 11 gezielten Prüfungen erfolgreich, die übrigen 3.193 Backendtests bestanden.
+- Abschluss: `make verify-feature FEATURE=graph-role-parity` besteht vollständig für den endgültigen Stand: 14 Keycloak-Prüfungen, 3.195 Backendtests (48 regulär übersprungen), 923 Frontendtests, 11 Toolingtests, 80 H5P-Tests und der authentifizierte Graph-Rundlauf (36,5 Sekunden). Svelte-Check ohne Fehler/Warnungen und Produktionsbuild erfolgreich. Der Owner-Cleanup bestätigt, dass keine laufbezogenen Benutzer, Kurse, Lerneinheiten, Sitzungen, Tokens oder registrierten H5P-Inhalte verbleiben.
