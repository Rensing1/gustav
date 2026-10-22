# Auth: verständliche Mail- und Tokenzustände

## Plan und vorab entworfene Prüffälle

Als Nutzer möchte ich nach einer Mailanforderung, einem Bestätigungslink oder einem ungültigen Link erkennen, was passiert ist und was ich als Nächstes tun kann.

- Gegeben eine angeforderte Passwortmail: Die Antwort zeigt „Prüfe dein Postfach“ statt eines dominanten Anmeldeformulars; die Meldung verrät keine Kontenexistenz. Erneute Anforderung und Anmeldung bleiben erreichbar.
- Gegeben eine Aktionsmail: Überschrift und Aktion benennen bei genau einer bekannten Aktion die E-Mail-Bestätigung oder das neue Passwort. Mehrere Aktionen behalten eine allgemeine, verständliche Darstellung.
- Gegeben eine erfolgreiche Aktion: Nachrichtenschlüssel werden übersetzt; keine technischen Schlüssel sichtbar.
- Gegeben ein ungültiger/abgelaufener Link: klare Überschrift, Rückweg zur Anmeldung und Passwort-Hilfe. Keine Tokeninterpretation im Browser, keine ungeprüften Redirect-Ziele.
- Gegeben ein Passwortformular: konsistente Du-Anrede, „Neues Passwort“ und „Passwort speichern“.
- Manuelle Sichtprüfung bei 1113 × 720 und 390 × 720 über echte lokale Aktionsmails. Kein Passwortwechsel, keine automatisierten Tests gemäß Nutzerauftrag. Keine API-/Schemaänderung.

Temporärer lokaler Mail-Empfänger und separates Prüfkonto sind bereits freigegeben; anschließend SMTP wiederherstellen und Prüfkonto deaktivieren.

## Ergebnis

Umgesetzt: übersetzte Erfolgstitel, konkrete Aktionen bei E-Mail-Bestätigung und Passwortwechsel, eigene Postfachansicht nach Mailanforderung, konsistente Du-Anrede, konkrete Passwortbeschriftungen und zusätzliche Passwort-Hilfe bei Tokenfehlern. Sprachwahl bleibt nachrangig und auch mobil nebeneinander. Redirect-Prüfungen und Tokenvalidierung bleiben unverändert.

Manuell mit echten lokalen Aktionsmails geprüft: Bestätigungsaktion und Erfolg, verwendeter und tatsächlich abgelaufener Link, Rückweg zur Passwort-Hilfe, Mailanforderung und erneute Anforderung, echtes Rücksetzformular sowie administratives Passwort-Aktionsformular. Jeweils Desktop (1113 × 720) und mobil (390 × 720); keine abgeschnittenen Aktionen sichtbar. Nach Neustarts waren neue Vorgänge nötig; finale Screenshots stammen aus frischen Vorgängen. Die zweite Passwortmeldung `resetPasswordMessage` wurde dabei zusätzlich entdeckt und korrigiert.

Build erfolgreich. Keine automatisierten Tests, keine Passwortänderung und kein Commit. SMTP-Konfiguration wiederhergestellt, lokaler Empfänger gestoppt, Prüfkonto deaktiviert. Selbstregistrierungs-Wartezustand und tatsächlicher Abschluss einer Passwortänderung bleiben ungeprüft.
