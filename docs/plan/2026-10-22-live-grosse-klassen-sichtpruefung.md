# Live-Ansicht: größere Klassen und Abgabearten

## Auftrag und Prüfumfang

Manuelle Sichtprüfung auf Desktop (1113 × 916) und schmalem Bildschirm (390 × 844), ohne automatisierte Tests und ohne Änderungen an Lernständen. Klassen mit 20 und 28 Lernenden sowie bis zu 17 Aufgaben wurden geöffnet; zusätzlich wurde eine Klasse mit 23 Lernenden zur Suche nach weiteren Abgabearten betrachtet. Keine Namen, Abgabeinhalte oder personenbezogenen URLs werden hier festgehalten.

## Beobachtungen

- Die Klassenübersicht bleibt grundsätzlich nutzbar. Mobil beanspruchen die fixierten Spalten für Name, Stand und Üben fast die gesamte Breite. Bei mehreren Aufgaben bleibt nur ungefähr eine Aufgabenspalte sichtbar. Der Modulwähler wird am rechten Kartenrand abgeschnitten.
- Beim vertikalen Scrollen verschwinden die Tabellenüberschriften. Lange Namen werden gekürzt. Die horizontale Scrollleiste liegt erst am unteren Ende der langen Tabelle.
- Eine Auswahl lädt die Abgabe unterhalb aller Schülerzeilen, ohne die Ansicht zum Detail zu führen. Gerade bei großen Klassen bleibt das Ergebnis des Klicks außerhalb des sichtbaren Bereichs.
- Die Aufgabenleiste im Detail nummeriert Aufgaben fortlaufend, die Matrix dagegen je Modul. Beispiel: Aufgabe 1 im Modul entspricht Schaltfläche 15 im Detail. Das erschwert die Zuordnung.
- H5P-Ergebnisse erscheinen in der Matrix mit Punkten, in der Aufgabenleiste jedoch als „Noch unbewertet“. Die Statusquellen müssen vereinheitlicht werden.
- Eine vorhandene JPEG-Abgabe zeigt auf beiden Bildschirmgrößen eine defekte Bildvorschau. Das Bild ist geladen/abgeschlossen gemeldet, hat aber natürliche Breite 0. Ursache noch offen (Dateiverfügbarkeit, Berechtigung oder Auslieferung); kein Beleg für einen reinen CSS-Fehler. Ein verständlicher Fehlerzustand fehlt.
- Die Detailansicht selbst passt in die schmale Bildschirmbreite; die 17 Aufgabenknöpfe brechen in mehrere Zeilen um und beanspruchen viel Höhe.

## Offene Abdeckung

Eine gespeicherte KI-Dialogabgabe wurde in den geöffneten Beispielen nicht gefunden. Dieser Teil ist **nicht visuell abgenommen**. Quellcodebefund: Gesprächsbeiträge und Abschlussantwort werden noch als ähnliche Karten gerendert; die Abschlussantwort steht nach dem vollständigen Verlauf. Ein reales langes Dialogbeispiel muss desktop und mobil nachgeprüft werden. Auch eine funktionierende PDF-/Bildvorschau bleibt nachzuprüfen.

## Empfohlene nächste Änderungen

1. Auswahl und Detail verbinden: sichtbarer Wechsel zur Abgabe mit klarer Rückkehr zur Klassenübersicht und erhaltener Position.
2. Mobil Platz für Aufgaben priorisieren; Zusammenfassungen kompakter oder außerhalb des horizontalen Aufgabenbereichs zeigen. Modulwähler auf verfügbare Breite begrenzen.
3. Spaltenzuordnung bei langen Klassen erhalten; Nummerierung zwischen Matrix und Detail vereinheitlichen.
4. H5P-Bewertungsstatus konsistent ableiten.
5. Dateifehler diagnostizieren und verständlich darstellen.

Keine Implementierung, keine automatisierten Tests, kein Commit in diesem Prüfschritt.
