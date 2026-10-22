# Live: Abgabe erreichen und zur Klasse zurückkehren

## Umsetzung

Als Lehrkraft möchte ich eine ausgewählte Abgabe sofort sehen und anschließend an derselben Stelle der Klassenübersicht weiterarbeiten. Die Matrix bleibt montiert, damit Modulwahl und horizontale Scrollposition erhalten bleiben. Nach erfolgreicher Auswahl wird das Detail fokussiert und in den sichtbaren Bereich gescrollt. Eine Aktion „Zur Klassenübersicht“ stellt Fokus und vorherige Seitenposition wieder her. Direkte Detail-URLs führen ebenfalls zum Detail. Mobil bleiben nur die Namen fixiert; Stand und Üben sind rechts in der horizontal scrollbaren Tabelle erreichbar. Der Modulwähler erhält eine begrenzte Breite.

## Vorab entworfene Prüffälle

- Gegeben eine lange Klasse, wenn eine Aufgabe oder Person ausgewählt wird, dann ist das geladene Detail sichtbar und fokussiert.
- Gegeben ein geöffnetes Detail, wenn „Zur Klassenübersicht“ gewählt wird, dann sind die vorherige Position, Modulwahl und Spaltenposition erhalten.
- Gegeben ein direkter Detail-Link, dann ist das Detail erreichbar; Rückkehr ohne vorherigen Klick führt zur Klassenübersicht.
- Gegeben 390 px Breite und mehrere Aufgaben, dann stehen mehrere Aufgaben neben dem Namen zur Verfügung; die Zusammenfassungen bleiben durch horizontales Scrollen erreichbar, ohne Überlauf der Seite.
- Gegeben ein Aufgabenwechsel im Detail oder Live-Aktualisierung, dann springt die Ansicht nicht unerwartet zur Klassenübersicht.

Manuelle Browserprüfung Desktop und mobil. Keine automatisierten Tests auf ausdrücklichen Wunsch. Für spätere Automatisierung: gezielter authentifizierter Live-Feature-Test für Auswahl/Rückkehr und Komponententest für mobile Spalten. Keine API-/Datenbankänderung. Andere Befunde des vorherigen Reviews bleiben außerhalb dieses Schritts.

## Manuelles Ergebnis

Frontend erfolgreich gebaut. Im Browser Desktop (1113 × 916) und mobil (390 × 844) geprüft: Auswahl fokussiert das Schülerdetail, Rückkehr fokussiert dieselbe Aufgabe. Mit seitlich gescrollter mobiler Tabelle bleiben horizontal 44 px und vertikal 184 px nach dem Hin- und Rückweg unverändert. Modulwahl bleibt erhalten. Beide Aufgaben eines Moduls sind mobil nebeneinander sichtbar; Stand und Üben sind rechts erreichbar. Kein horizontaler Seitenüberlauf (Dokumentbreite 375 px bei 390 px Fenster inklusive Scrollleiste). Direkter Detailaufruf nach Neuladen und Rückkehr ohne gespeicherten Auslöser ebenfalls manuell geprüft. Keine automatisierten Tests ausgeführt.
