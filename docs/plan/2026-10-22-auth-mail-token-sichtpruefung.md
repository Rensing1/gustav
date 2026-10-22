# Auth: E-Mail- und tokengebundene Zustände im Browser

## Vorgehen

Manuelle Sichtprüfung echter Keycloak-Seiten auf Desktop (1113 × 720) und mobil (390 × 720), ohne automatisierte Tests. Vorher lokale CA-Vertrauensstellung prüfen. Bestehende Sitzung und Nutzerkonten erhalten. Für gültige Mail-Links ausschließlich ein separates Prüfkonto und einen lokalen Mail-Empfänger nach Freigabe verwenden; anschließend ursprüngliche Konfiguration wiederherstellen.

## Prüffälle

- Ungültiger Token: verständliche Fehlermeldung, sichtbare Aktion zurück zur Anmeldung, kein Überlauf auf schmaler Ansicht.
- Zurücksetzen angefordert: Bestätigung zeigt den nächsten Schritt, ohne eine Kontenexistenz zu verraten.
- Gültiger Passwort-Link: Formular und Passwortregeln erreichbar; kein Passwort durch den Agenten ändern.
- E-Mail-Verifizierung: Versandhinweis, erneuter Versand und erfolgreicher Bestätigungslink.
- Bereits verwendeter oder abgelaufener Link: verständliche Erklärung und sicherer Neustart.

## Bisherige Beobachtungen

- CA-Prüfung erfolgreich.
- Ungültigen Action-Token tatsächlich im Browser geöffnet; Desktop, mobil und mobil dunkel geprüft. Keine abgeschnittenen Inhalte. „Erneut anmelden“ führt zur echten Anmeldung.
- Text ist noch technisch und uneinheitlich: „Ungültiger Code“, „Applikation“ und Sie-Anrede. Für den Nutzer wäre „Dieser Link ist nicht mehr gültig. Bitte starte den Vorgang erneut.“ verständlicher.
- Der Titel „Anmeldung nicht möglich“ beschreibt einen ungültigen Bestätigungslink nur ungenau.
- Sprachlinks erhalten denselben kräftigen Akzent wie relevante Aktionen; auf mobil beanspruchen sie zwei eigene Zeilen. Nachrangige Gestaltung wäre ruhiger.
- Lokaler Mail-Empfänger und separates Prüfkonto sind noch nicht eingerichtet; Freigabe dazu angefragt. Gültige, abgelaufene und bereits verwendete echte Mail-Links daher noch nicht geprüft.

## Freigegebener Prüflauf

Lokaler Mail-Empfänger und separates Prüfkonto sind vom Nutzer freigegeben. Echte Keycloak-Aktionsmails werden ausschließlich lokal aufgefangen. Die Prüfung verändert keine bestehenden Passwörter und verwendet keine automatisierten Tests. Ursprüngliche SMTP-Konfiguration wird vorab gesichert und anschließend wiederhergestellt.

## Ergebnis des freigegebenen Browserdurchgangs

Alle nachfolgenden Seiten wurden vom echten lokalen Keycloak gerendert und jeweils bei 1113 × 720 sowie 390 × 720 visuell geprüft:

- E-Mail-Aktionslink mit VERIFY_EMAIL: vorgeschaltete Bestätigung und erfolgreiche Ausführung.
- Derselbe bereits verwendete Link: Ablehnung mit Rückweg zur Anmeldung.
- Echter kurzlebiger Aktionslink nach Ablauf: Ablehnung, ohne Veränderung der globalen Token-Laufzeiten.
- Passwort-Aktionslink: Passwortformular einschließlich Anforderungen.
- Passwort-Hilfe über die Oberfläche: Mail lokal angefordert, Versandhinweis angezeigt, Link aus der tatsächlich empfangenen Mail geöffnet und Rücksetzformular geprüft.

### Befunde

1. Erfolgsseite zeigt den unübersetzten Schlüssel `accountUpdatedTitle`. Die Meldung „Ihr Benutzerkonto wurde aktualisiert“ erklärt die erfolgreiche E-Mail-Bestätigung nicht konkret.
2. Die Aktionsbestätigung „Führen Sie die folgende(n) Aktion(en) aus“ und „Klicken Sie hier um fortzufahren“ sind technisch und unpräzise.
3. Nach Anforderung einer Rücksetzmail erscheint erneut das Anmeldeformular. Der eigentliche nächste Schritt, das Postfach zu öffnen, ist zu wenig hervorgehoben.
4. Passwortformular mischt „Sie müssen Ihr Passwort ändern“ mit „Dein Passwort benötigt“. „Absenden“ sollte die konkrete Aktion benennen; „Neues Passwort“ wäre die passendere Feldbezeichnung.
5. Abgelaufene und verwendete Links erhalten allgemeine Anmeldefehler. Ein kontextbezogener Hinweis und eine neue Linkanforderung wären verständlicher.
6. Die geprüften Formulare und Aktionen passen auf beide Bildschirmgrößen. Keine abgeschnittenen Inhalte oder horizontalen Überläufe sichtbar.

### Grenzen und Abschluss

Keine Passwörter eingegeben oder geändert, keine automatisierten Tests ausgeführt. E-Mail-Verifizierung wurde über einen echten administrativen Aktionslink geprüft; der Wartezustand unmittelbar nach Selbstregistrierung und die Passwortänderungs-Erfolgsseite wurden nicht durchlaufen. Keine Änderung an Produktcode in diesem Prüfschritt.

Die ursprüngliche SMTP-Konfiguration wurde wiederhergestellt; das maskierte SMTP-Passwort wurde dabei aus der bestehenden lokalen ENV-Konfiguration übernommen. Der lokale Mail-Empfänger wurde gestoppt und das separate Prüfkonto deaktiviert. Keine Nachrichten wurden an einen externen Mailserver übertragen.
