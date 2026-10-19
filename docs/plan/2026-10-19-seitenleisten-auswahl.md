# Einheitliche Seitenleisten: Auswahl und Reihenfolge

## User Story
Als Schüler möchte ich beim Wechsel vom Modul zur Aufgabe dieselbe Modulreihenfolge und dieselbe Markierung meines aktuellen Standorts sehen.

## Umsetzung
Gemeinsame WorkspaceOutline beibehalten. Modulreihenfolge unverändert aus der Modulansicht übernehmen. Aktuelle Aufgabe auch ohne Abgabe anzeigen und markieren; vorhandene Abgaben weiterhin separat öffnen. Navigation kompakt als „Inhalt“ beschriften, zusätzliche Einrückung entfernen und aktive Farbe beim Hover erhalten. Keine API-, Schema- oder Datenänderung.

## Prüffälle vor Implementierung
- Gegeben eine Aufgabe ohne Abgabe: Beim Öffnen erscheint sie im zugehörigen Modul farbig als aktueller Eintrag.
- Gegeben eine Aufgabe mit Abgabe: Aktuelle Aufgabe und lesbare eigene Abgabe bleiben unterscheidbar.
- Beim Wechsel Modul/Aufgabe bleibt die Modulreihenfolge gleich.
- Beim Hover auf dem aktuellen Eintrag bleibt seine aktive Markierung erhalten; andere Einträge erhalten nur Hover-Markierung.
- Materialien und Abgaben öffnen sich weiterhin, Rückkehr zeigt wieder die aktuelle Aufgabe.
- Desktop und schmale Ansicht: Keine abgeschnittenen Einträge oder horizontales Überlaufen; Text-, Datei-, Dialog- und H5P-Aufgaben verwenden dieselbe Komponente.

Spätere automatisierte Zuordnung: WorkspaceOutline-Komponentenprüfung für aktive Hover-Klasse; LearnerTaskContext-Komponentenprüfung für aktuelle Aufgabe/Abgabe; authentifizierter Feature-Rundlauf in learner-reference-workspace (@feature-acceptance) für Navigation und Rückkehr. Auf ausdrücklichen Nutzerwunsch jetzt keine automatisierten Tests und kein Feature-Gate. Manuelle Sichtprüfung vor Freigabe.

## Manuelle Sichtprüfung
Desktop und 390 × 844 geprüft: aktuelle H5P-Aufgabe farbig markiert, Module in ursprünglicher Reihenfolge, Materialien und frühere Abgabe lesbar; Rückkehr erhält Aufgabenmarkierung. Mobiler Klick auf aktuelle Aufgabe wechselt zur Bearbeitung. Keine horizontale Seitenüberbreite (390/390 px). Screenshots unter /tmp/sidebar-einheitlich-desktop.png und /tmp/sidebar-einheitlich-mobil.png. Frontend-Build erfolgreich; keine automatisierten Tests ausgeführt.
