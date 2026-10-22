# Registrierung: Wartezustand und Bestätigungsmail

## Manueller Prüfplan

Mit einem neuen, ausschließlich für diese Sichtprüfung angelegten Konto die echte Registrierung bis zum E-Mail-Wartezustand durchlaufen. Erste Bestätigungsmail lokal auffangen, Desktop (1113 × 720) und mobil (390 × 720) ansehen, erneuten Versand über die Oberfläche auslösen und den Eingang einer zweiten Mail für dasselbe Prüfkonto kontrollieren. Keine automatisierten Tests. Keine Änderungen an bestehenden Nutzerkonten. Nach Abschluss SMTP-Konfiguration wiederherstellen, Empfänger stoppen und Prüfkonto deaktivieren.

Prüfpunkte: eindeutiger nächster Schritt, korrekte Zieladresse, verständlicher Link für erneuten Versand, sichtbare Rückmeldung, keine abgeschnittenen Inhalte oder horizontalen Überläufe.

## Ergebnisse

Echte Registrierung über die Oberfläche mit neuem Prüfkonto abgeschlossen, ohne E-Mail-Verifizierung auszuführen. Erste Bestätigungsmail beim ausschließlich lokalen Empfänger nachgewiesen. Anschließend „Hier klicken“ betätigt; zweite Bestätigungsmail an dasselbe Prüfkonto lokal nachgewiesen. Wartezustand vor und nach erneutem Versand auf Desktop und mobil visuell geprüft.

- Funktionaler Versand und erneuter Versand erfolgreich. Kein horizontaler Überlauf und keine abgeschnittenen Aktionen sichtbar.
- Die Seite enthält noch „E-Mail verifizieren“ und Sie-Anrede. Zielzustand: „Bestätige deine E-Mail-Adresse“ und konsistente Du-Anrede.
- „Hier klicken“ benennt die Aktion nicht. Empfohlen: „Bestätigungsmail erneut senden“.
- Nach erneutem Versand erscheint keine unterscheidbare Bestätigung, obwohl die zweite Mail tatsächlich angekommen ist. Empfohlen: kurze sichtbare Rückmeldung „Bestätigungsmail erneut gesendet“.
- Die Zieladresse wird korrekt angezeigt, ist aber in einen langen Satz eingebettet und bricht mobil um. Eigene Zeile mit gut lesbarer Adresse wäre klarer.
- „Anmelden“ konkurriert mit dem eigentlichen nächsten Schritt, die Mail zu öffnen. Nachrangige Gestaltung beibehalten, den nächsten Schritt expliziter benennen.
- Desktop zeigt noch einen isolierten Punkt zwischen den Aktionslinks.

Keine Produktänderungen in diesem Durchgang und keine automatisierten Tests. Ursprüngliche SMTP-Konfiguration wiederhergestellt, lokaler Empfänger gestoppt, Prüfkonto deaktiviert. Temporäre Prüfdateien einschließlich Zugangsdaten entfernt. Keine Änderung an vorhandenen Nutzerkonten.
