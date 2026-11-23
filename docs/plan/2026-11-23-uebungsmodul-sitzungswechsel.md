# Übungsmodule gezielt öffnen

Als Schüler möchte ich beim Öffnen eines Übungsmoduls nur dessen Aufgaben bearbeiten.

- Gegeben eine gemischte Sitzung mit einer aktuellen Aufgabe aus Modul B. Wenn ich B im Graphen öffne und starte, dann ersetzt eine Sitzung ausschließlich für B die alte. Beim erneuten Öffnen bleibt die neue Sitzung erhalten. Abnahme in `practice-session.spec.ts`.
- Gegeben eine aktive Sitzung. Wenn zwei Startanfragen dieselbe Sitzung ersetzen wollen, dann gewinnt genau eine. Wenn die Ersatz-ID fremd oder veraltet ist oder der Zielstapel keine zulässigen Aufgaben liefert, dann bleibt die aktive Sitzung erhalten. API-Regression gegen die lokale PostgreSQL-Datenbank.
- Gegeben ein Modul-Link. Wenn ich Aktionen ausführe oder neu lade, dann bleibt der Modulbezug bis zum Abschluss erhalten. Der allgemeine Einstieg erlaubt mehrere Stapel. Frontend-Tests für die Auswahl und die Aktions-URLs.

Zuerst den OpenAPI-Vertrag ergänzen. Sitzungen geben ihre gespeicherten Stapel zurück. Ein Start mit einem Stapel kann eine konkrete aktive Sitzung derselben Person ersetzen. Zielaufgaben prüfen, die betroffene Sitzungszeile sperren und die vorhandene Abschlusslogik mit der Neuanlage in derselben Transaktion verwenden. Die vorhandenen Tabellen und der eindeutige Index genügen. Keine Migration.

Vor Abschluss `make local-ca-status` und `make verify-feature FEATURE=practice-session` gegen den freigegebenen lokalen Stack ausführen.
