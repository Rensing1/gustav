# H5P: Platznutzung und fensterfüllende Ansicht

User Story: Als Schüler möchte ich H5P-Aufgaben ohne unnötige Platzverluste bearbeiten und bei Bedarf die ganze Fensterfläche nutzen, ohne meinen Bearbeitungsstand zu verlieren.

Prüffälle vor Implementierung: Given eingebetteter Player, when Vollbild geöffnet und per Button oder Escape verlassen wird, then bleibt derselbe Player im DOM und der Fokus kehrt zum Schalter zurück. Given schmale Ansicht, then sind Schalter und Inhalt ohne horizontalen Seitenüberlauf sichtbar. Given Größenwechsel, then wird H5P neu vermessen. Given große Drag-and-drop-Fläche, then bleibt sie im Vollbild innerhalb des verfügbaren Inhaltsbereichs scrollbar. Given Navigation, then werden Beobachter entfernt.

Spätere automatisierte Zuordnung: H5PTaskPlayer.test.ts für Öffnen/Schließen und Instanzerhalt; authentifizierte learner-reference-workspace-Spec mit @feature-acceptance für Desktop/mobil, Escape, Fokus und Interaktionsstand. Auf Nutzerwunsch jetzt keine automatisierten Tests. Manuelle Prüfung mit vorhandenem H5P-Platzhalter; umfangreiche reale Inhalte bleiben gesondert zu prüfen.

Umsetzung: nativer modaler Dialog als fensterfüllende Ansicht, ohne Re-Mount des Players. Browserdialog übernimmt Fokusbegrenzung und Escape; kein Betriebssystem-Vollbild erforderlich. Reduzierte zusätzliche Rahmen/Abstände. Ein Scrollbereich im Vollbild; Größenbeobachter benachrichtigt den bestehenden H5P-Player. Keine API-/Datenbankänderungen.

## Manuelle Sichtprüfung
Frontend-Build erfolgreich (inklusive vorhandener Build-Kompatibilitätsprüfung; keine automatisierten Testläufe). Desktop: Vollbild geöffnet, Rückkehr per Escape und Button, Fokus jeweils wieder am Vollbildschalter. Schmale Ansicht 390 × 844: normale Inhaltsbreite steigt von 298 auf 332 px, Vollbild bietet 358 px Breite bei 16 px Rand; kein horizontaler Seitenüberlauf. Rückkehr per Button erfolgreich. Der Player wird im Code weder umgehängt noch neu erzeugt; Größenwechsel werden an seine resize-Methode gemeldet.

Prüfgrenze: vorhandener Inhalt ist nur der technische Minimal-Platzhalter. Zustandsbehaftete komplexe Drag-and-drop-Aufgaben, lange Inhalte und reale Touch-Geräte bleiben manuell nachzuprüfen. Keine Aufgaben abgegeben oder Daten zurückgesetzt.
