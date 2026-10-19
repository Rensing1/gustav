# Einheitliches Scrollverhalten im Lernbereich

User Story: Als Schüler möchte ich Inhalte und Aktionen durch normales Scrollen erreichen, ohne einen schmalen Rand oder die richtige verschachtelte Fläche treffen zu müssen.

## Prüffälle vor Implementierung
- Given schmale Dialogansicht mit Materialliste, when über der Liste nach unten gescrollt wird, then erreicht die Seite das untere Ende, auch wenn die Liste selbst nicht überläuft.
- Given Desktop-Textaufgabe, when in der Bearbeitung gescrollt wird, then sind Rückmeldung und Abgeben erreichbar; die Materialspalte bleibt unabhängig nutzbar.
- Given langer Inhalt im Lesemodus, when nach unten gescrollt wird, then bleiben Dokumentende und Rückweg erreichbar, ohne einen zusätzlichen äußeren Lesescroller.
- Given schmale Modulnavigation, when die Navigation geöffnet und gescrollt wird, then scrollt die Seite und kein begrenzter Navigationskasten.
- Given Dialogauswertung, when Gespräch aufgeklappt wird, then sind Rückmeldung und Rückweg weiterhin erreichbar.
- Given H5P mit explizitem Scrollmodus oder eingebettetes PDF, then bleibt die intrinsische Interaktion erhalten; keine globale Unterdrückung von Wheel- oder Touch-Ereignissen.

Spätere Automatisierung: diese Szenarien der authentifizierten Spec `learner-reference-workspace` mit `@feature-acceptance` zuordnen, ergänzt um konkrete Scrollpositionen und sichtbare Endaktionen. Auf ausdrücklichen Wunsch jetzt keine automatisierten Tests und kein Verify-Gate. Ausschließlich Build und manuelle Browserprüfung; keine Abgaben verändern.

## Umsetzung
Bestehende CSS-Regeln ändern: mobile Kontextlisten und Leser wachsen mit ihrem Inhalt; Desktop-Arbeitsspalten bleiben begrenzt und scrollbar; Scrollbewegungen dürfen an die Seite weitergereicht werden. Der Lesemodus verwendet die Seite statt einer zusätzlich begrenzten Fläche. PDF behält seinen eigenen Viewer, H5P seinen ausdrücklich gewählten Scrollmodus. Keine API-, Datenbank- oder Berechtigungsänderungen.

## Manuelle Sichtprüfung
Frontend erfolgreich gebaut und lokal gestartet. Bei 390 × 844 px bewegt dieselbe Scrollgeste über der Dialog-Materialliste die Seite jetzt bis zum Ende (71 von 71 px statt zuvor 0 von 71 px). Die Liste besitzt keinen eigenen Scrollbereich mehr. Die aufgeklappte Dialogauswertung erreicht das Seitenende (777 von 777 px). Das geöffnete mobile Inhaltsverzeichnis hat keine Höhenbegrenzung und keinen eigenen Scroller.

Bei 1280 × 720 px bleibt die Textbearbeitung unabhängig von der Kontextspalte scrollbar; am Ende (250 von 250 px) ist Abgeben sichtbar. Beide Spalten erlauben Scrollweitergabe. Der PDF-Lesemodus wächst auf seine volle Inhaltshöhe (674 px), nutzt die Seite und erreicht deren Ende; Rückkehr zur Aufgabe und zum Modul manuell geprüft. Die Lesemodus-Werkzeugleiste bleibt im Dokumentfluss, damit sie nicht hinter die globale Kopfleiste rutscht.

Keine automatisierten Tests ausgeführt, keine Antworten geändert oder abgegeben. H5P-Interaktion, laufender Dialog mit langen neuen Antworten sowie echte Touch-Geräte mit Bildschirmtastatur wurden in diesem Durchlauf nicht vollständig geprüft. PDF-Viewer behalten ihren intrinsischen Scrollbereich.
