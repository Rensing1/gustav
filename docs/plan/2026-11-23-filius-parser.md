# Filius-Auswertung für Programme, Dateien und Dienste

Als Lehrkraft möchte ich installierte Programme, gespeicherte Dateien und Diensteinstellungen einem Gerät zuordnen können. Elf Aufgaben aus zwei Netzwerkeinheiten begründen die Anforderungen. In den vier untersuchten Hilfsdateien wirken sich insbesondere die ausgelassenen Browser, eine typfreie DNS-Datei und indirekte Statuswerte aus.

1. Die drei Fehler im Endtext mit Pytest reproduzieren. Das bestehende Format filius.evidence.v1 und seine API- und Datenbankverträge verwenden.
2. Die Installationsliste je Gerät auswerten. Dateien mit Pfad und Typ erfassen, DNS- und Webtext begrenzt ausgeben und private Maildateien auslassen. Boolesche Dienstwerte nur bei expliziter Speicherung übernehmen.
3. Parser, Worker und Abgabevorschau anhand öffentlicher oder synthetischer Daten prüfen. Vor der Abnahme den lokalen Stack bauen, das CA-Vertrauen prüfen und make verify-feature FEATURE=filius-submission-evidence ausführen.
4. Den Weg vom Projekt zum Endtext und die Grenzen für die Bewertung in Parser-Referenz und Handbuch erklären.

| Gegeben | Wenn | Dann und automatisierter Nachweis |
| --- | --- | --- |
| Zwei Clients mit Browser | Ein Client verliert seinen Installationseintrag | Pytest prüft die Browserzuordnung für beide Varianten. |
| DNS-Datei ohne Typ sowie private und allgemeine Dateien | Der Endtext entsteht | Pytest prüft DNS-Inhalt, Gerätezuordnung und vertrauliche Inhalte. |
| Direkter, indirekter oder fehlender Statuswert | Der Parser liest den Dienst | Pytest unterscheidet true, false und unknown. |
| Authentifizierter Upload | Die Abgabe wird gespeichert und erneut geöffnet | Worker-Test und Playwright prüfen den extrahierten Text bis zur Vorschau. |

## Ergebnis

Die vier privaten Hilfsdateien aus Filius 2.14.0 wurden lokal mit ihrem Material-Prüfwert abgeglichen. Der Endtext ordnet die Browser in den vier Dateien jeweils den erwarteten Clients zu. In der DNS-Aufgabe erscheinen beide Client-Installationen und der vollständige DNS-Eintrag. Indirekte Dienstwerte erscheinen als unbekannt.

38 gezielte Parser-, Adapter- und Validierungstests bestanden. Das vollständige Featuregate bestand mit 3.315 erfolgreichen Backendtests, 48 übersprungenen Tests, erfolgreichem Frontend-Build und authentifiziertem Browser-Rundlauf bis zur erneut geöffneten Abgabe.
