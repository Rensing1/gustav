# Wartemeldung bei angeforderter Rückmeldung

Als Schüler möchte ich während der Auswertung meiner Abgabe eine gleichbleibende Wartemeldung sehen.

- Gegeben ein geöffneter Entwurf, wenn ich Rückmeldung einhole, dann erscheint der neue Begleittext im Fortschrittshinweis. Komponenten- und Browsertest prüfen den Wortlaut.
- Gegeben eine laufende Rückmeldung, wenn die Statusabfrage in das langsamere Intervall wechselt, dann bleibt der Hinweis sichtbar. Der authentifizierte Browsertest prüft dies mit angehaltener Verarbeitung und vorgestellter Browseruhr.
- Gegeben eine endgültige Abgabe, wenn deren Auswertung länger dauert, dann bleibt ihre Warnung erhalten. Dies prüft der Komponententest.

Zuerst Tests anpassen, dann den Begleittext in der Aufgabenkarte anhand des Anlasses wählen und die Verzögerungswarnung in der Route auf endgültige Abgaben beschränken. Abnahme mit make verify-feature FEATURE=learner-task-finalization.
