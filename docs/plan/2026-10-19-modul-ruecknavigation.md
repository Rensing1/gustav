# Rücknavigation zu Lern- und Übungsmodulen

User Story: Als Schüler möchte ich beim Rücksprung das betreffende Modul sehen und aus einer Übung direkt zum zugehörigen Lernpfad zurückkehren.

Prüffälle vor Änderung:
- Given mehrere offene Module mit nachladenden Materialien, when Rücksprung zu einem Modul, then dessen Überschrift bleibt unter der Kopfleiste sichtbar, auch wenn vorherige Inhalte ihre Höhe ändern.
- Given ausgerichtetes Modul, when Nutzer selbst scrollt oder navigiert, then endet die automatische Ausrichtung sofort.
- Given aktives Übungsmodul, when Kontextleiste angezeigt, then tatsächlicher Kurs, Einheit und Modul werden aus zugänglichen Stapeldaten abgeleitet; Rückweg führt zum Lernpfad, ohne die Sitzung zu beenden.
- Given URL ohne Modulparameter nach Übungsaktion, then aktiver Sitzungsinhalt bestimmt den Kontext.
- Given unbekannter Stapel oder allgemeine Übungsübersicht, then generische Navigation bleibt nutzbar.

Später: gezielte Komponentenprüfungen und authentifizierter Feature-Test learner-reference-workspace sowie Übungsnavigation. Jetzt ausdrücklich keine automatisierten Tests. API und Datenbank unverändert. Build und manuelle Sichtprüfung Desktop/mobil; bestehende Antworten und Übungssitzung erhalten.

Zusätzlicher Sichtbefund: Die Inhaltsmarkierung wählte bisher das letzte bereits oberhalb des Bildschirms liegende Element. Sie berücksichtigt jetzt nur tatsächlich im sichtbaren Arbeitsbereich liegende Inhalte, damit nach Rücksprung nicht das vorherige Modul hervorgehoben bleibt.

## Ergebnis der manuellen Sichtprüfung
Frontend-Build erfolgreich. Textaufgabe → Modul bei 1280px und 390px geprüft: Überschrift des Zielmoduls steht nach Wiederherstellung unterhalb der Kopfzeile, die Seitenleiste markiert dessen erstes sichtbares Material. Nach manuellem Scrollen bleibt die neue Position erhalten. Entwurf wurde weder geändert noch abgegeben. Übungsseite mit und ohne ursprüngliche Modulparameter zeigt den aktiven Stapel; Rückpfeil öffnet den zugehörigen Lernpfad. Beim erneuten Aufruf bleibt dieselbe aktive Aufgabe mit unverändertem Fortschritt erhalten. Übungssitzung nicht beendet und keine Antwort gesendet. Automatisierte Tests wie angefordert nicht ausgeführt; Sitzungsabschluss und Mehrstapelwechsel noch nicht interaktiv durchgespielt.
