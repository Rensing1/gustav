# Touch-Bedienung am Spaltentrenner reparieren

Als Schüler möchte ich den sichtbaren Griff mit dem Finger horizontal ziehen können, um der Aufgabenstellung oder meiner Antwort mehr Platz zu geben.

## Befund

Bei 1024 × 768 CSS-Pixeln reproduzierbar in Chromium mit Touch-Eingabe, sowohl bei einer Textaufgabe als auch bei einem KI-Dialog. Der Browser bindet die Berührung an den Griff. Beim Übergang zum Ziehen übernimmt der Trenner die Pointer-Bindung. Das Ereignis `lostpointercapture` des Griffs erreicht den Trenner und setzt die Breite zurück. Beim Ziehen oberhalb des Griffs ist der Trenner von Anfang an das gebundene Element.

## BDD und Umsetzung

- **Gegeben** ist eine freigegebene Textaufgabe im breiten Layout. **Wenn** der Schüler den sichtbaren Griff mit dem Finger horizontal über die Trefferfläche hinauszieht, **dann** ändert sich die gerenderte Kontextspaltenbreite und bleibt nach dem Neuladen erhalten. Nachweis über `learner-task-divider.spec.ts` mit authentifizierter Browser-Geste.
- **Gegeben** ist eine vertikale oder abgebrochene Geste. **Wenn** der Browser scrollt oder den Pointer abbricht, **dann** wird keine neue Breite gespeichert. Nachweis über vorhandene Komponententests. Maus, Tastatur, Grenzwerte und kompakte Darstellung prüfen die bestehenden Komponenten- und Responsive-Tests.
- Zuerst die Browserregression rot nachweisen. Die Capture-Funktion der gemeinsamen Komponente erhält anschließend eine vorhandene Pointer-Bindung des getroffenen Elements. Ohne bestehende Bindung greift die bisherige explizite Bindung des Trenners. Ein kurzer englischer Kommentar erklärt den Grund. API-Vertrag und Datenbankschema sind von der Änderung nicht betroffen.

## Abnahme

`make local-ca-status` vor Browserläufen, dann `make verify-feature FEATURE=learner-task-divider` und `make test-feature-detail FEATURE=learner-task-responsive` gegen den lokalen Stack. Falls verfügbar, den Griff bei Textaufgabe und KI-Dialog auf einem physischen iPad in Safari prüfen.

Der neue Chromium-Fall blieb vor der Korrektur nach dem Zug bei rund 508 statt über 562 Pixeln. Mit der Korrektur wächst die Spalte und stellt ihre neue Breite nach dem Neuladen wieder her. Die Probe mit Chromium-Touch-Eingabe änderte die Breite auch im KI-Dialog. Der Responsive-Test verwendet den Materialknopf der aktuellen Seitenleiste und war in Chromium und Playwright-WebKit erfolgreich. Die Touch-Prüfung in Safari auf einem physischen iPad steht aus.
