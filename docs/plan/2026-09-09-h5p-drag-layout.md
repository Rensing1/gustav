# H5P-Zuordnung: Kontrast und responsive Einbettung

Auftrag vom 09.09.2026: Die im lokalen Browser reproduzierten Kontrast- und Bedienprobleme beheben. Ausschließlich lokaler Stack; keine Produktion, keine Änderung der Referenzkopie im Unterrichtsrepo.

## User Story und Ursache

Als Lernender möchte ich Zuordnungskarten in beiden Farbmodi lesen, voneinander unterscheiden und bei wechselnder Fensterbreite zuverlässig ablegen können.

Die Unterrichtspakete verwenden für Breite/Höhe irrtümlich Prozentwerte statt der von DragQuestion erwarteten em-Werte. Diese Paketkorrektur erfolgt im Unterrichtsrepo. Unabhängig davon fehlen DragQuestion-Themeregeln, der bisherige Button-Token `--color-primary` fehlt im Svelte-Theme, und intrinsische Gridbreiten verhindern das Schrumpfen des Players.

## BDD und Nachweis

- Gegeben eine durch die echte Lehrkraftoberfläche angelegte H5P-Aufgabe, wenn die Testdatei importiert und vom Lernenden geöffnet wird, dann ist die Aufgabe bedienbar (authentifizierter Rundlauf, `h5p-drag-layout.spec.ts`, `@feature-acceptance`).
- Gegeben Hell- oder Dunkelmodus, wenn Karten unzugeordnet oder abgelegt sind, dann sind Schrift und Flächen kontrastreich; auch Auswerten und Fokus sind erkennbar (derselbe Browsertest plus manuelle Sichtprüfung).
- Gegeben die geladene Aufgabe, wenn das Fenster auf Tabletbreite schrumpft und wieder wächst, dann liegen Karten innerhalb des Players und es gibt keinen horizontalen Seitenüberlauf (derselbe Test).
- Gegeben eine falsche Zuordnung, wenn sie korrigiert und alle Karten ausgewertet werden, dann wird der vollständige Erfolg tatsächlich gespeichert (echte Maus-/Tastatureingabe, kein synthetisches xAPI).

Keine Änderung an API, Datenbankschema, Berechtigungen oder Auswertung. Daher keine OpenAPI-/SQL-Änderung nötig.

## Umsetzung und Prüfung

1. Browser-Regression mit synthetischen Begriffen und realem H5P.DragQuestion anlegen und zunächst rot ausführen. Standardbibliothek muss im lokalen H5P-Stack installiert sein; das Inhaltspaket selbst bleibt bibliotheksfrei.
2. Theme und intrinsische Layoutgrenzen minimal korrigieren; nur bei nachgewiesenem Bedarf Container-Resize ergänzen.
3. Vier Unterrichtspakete ohne Änderung ihrer fachlichen Zuordnungen auf korrekte Maße umstellen und in der lokalen Umgebung prüfen.
4. Gezielter Browsernachweis und `make verify-feature FEATURE=h5p-drag-layout`; reale Sichtprüfung an Desktop-/Tabletbreite in Hell/Dunkel.
5. Ergebnisse und verbleibende Grenzen hier dokumentieren. H5P-Skill anschließend planen.

## Nachweis vor Korrektur

Der echte Browserlauf erreicht den Player und scheitert bei der Kontrastprüfung: 1,05:1 statt mindestens 4,5:1. Zuvor wurden die Selektoren für versteckte Statuskopien und den dynamischen Startknopf an die tatsächliche Oberfläche angepasst.

## Implementierter Stand

- DragQuestion-Karten, Labels, Zielflächen, Ablage-/Hoverzustände und Richtig/Falsch erhalten passende Themefarben. Lange Labels dürfen umbrechen.
- JoubelUI-Schaltflächen verwenden den vorhandenen Linkfarbtoken mit Fallback auf den früheren Primary-Token.
- Player und Practice-Karte besitzen schrumpfbare Gridspalten; ein zusätzlicher ResizeObserver war im realen Browser nicht notwendig.
- `h5p-drag-layout.spec.ts` prüft kontrastreiche Darstellung, Textüberlauf, Geometrie und den vollständigen authentifizierten Import-/Lernendenrundlauf mit Maus und Tastatur. `H5P_LAYOUT_PACKAGE` kann für eine ausdrücklich lokale Prüfung auf ein vorhandenes Paket zeigen; ohne diese Variable nutzt der Test seine synthetische Fixture. Die Standardbibliotheken H5P.DragQuestion 1.14 und Abhängigkeiten müssen im lokalen Stack installiert sein.
- Alle vier korrigierten Unterrichtspakete bestanden den gleichen Browserlauf. Bei der ersten Artikelzuordnung wurde dabei zunächst eine zu niedrige Karte entdeckt und im Inhaltspaket korrigiert.
- Sichtprüfung der echten Artikel-/Prinzipientexte: keine Überlappung, keine abgeschnittenen Texte in den geprüften Ansichten; Kontrast und sichtbare Zielfeldgrenzen verbessert. Prüfung bei 1280 × 900 und 768 × 1024 Pixeln; keine Behauptung über echte Touch-Hardware oder Smartphone-Eignung.
- Produktion wurde nicht verändert. Die Paketkorrekturen werden getrennt im Unterrichtsrepo verwaltet; die Plattformänderung allein korrigiert keine falsch verfassten em-Abmessungen.

## Abschließendes Prüfergebnis

`make verify-feature FEATURE=h5p-drag-layout` erfolgreich: 3035 Backendtests bestanden (33 übersprungen), 688 Frontendtests bestanden, Svelte-Prüfung ohne Fehler oder Warnungen, 67 H5P-Service-Tests bestanden und authentifizierter Browser-Akzeptanztest bestanden. Die vier endgültigen Unterrichtspakete bestanden zusätzlich jeweils denselben Browserlauf. Testeigene Daten wurden nach den Akzeptanzläufen entfernt. Eine dauerhaft vorgesehene lokale Dev-Testaufgabe wurde abschließend auf das endgültige zweite Artikelpaket aktualisiert.
