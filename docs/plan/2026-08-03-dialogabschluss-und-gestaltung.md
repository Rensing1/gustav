# Dialogabschluss und fokussierte Schülerarbeitsfläche

## User Story

Als Schüler möchte ich mich zunächst vollständig auf das KI-Gespräch konzentrieren und erst nach einer bewussten Entscheidung zur Abschlussaufgabe wechseln, damit Gespräch, Abschlussantwort und endgültige Abgabe klar voneinander getrennt sind.

## Festgelegtes Verhalten

- Die Oberfläche kennt die lokalen Phasen `Gespräch` und `Abschluss vorbereiten`; der fachliche Sitzungsstatus bleibt bis zur endgültigen Abgabe `active`.
- Nach mindestens einer vollständig beantworteten Runde erscheint `Dialog beenden`. Der optionale Abschlussauftrag bleibt bis zu diesem bewussten Wechsel verborgen.
- `Zurück zum Dialog` verändert keine Serverdaten. `Endgültig abgeben` verwendet den bestehenden Abschlussendpunkt und verbraucht einen Versuch.
- Phase und Abschlussentwurf werden schüler-, kurs-, aufgaben- und sitzungsbezogen in `sessionStorage` gespeichert. Ohne bekannte Schülerkennung erfolgt keine lokale Speicherung.
- Auch ohne Abschlussauftrag bleibt die Abgabe zweistufig. Nach Erreichen der Höchstrundenzahl ist weiterhin der ausdrückliche Wechsel zum Abschluss nötig.
- Die Aufgabenstellung bleibt kompakt sichtbar. Verlauf, Hilfestellungen, Eingabe und Abschluss erhalten eine kontrastreiche, kantige Gestaltung aus den zentralen Designvariablen.

## BDD-Szenarien und Testzuordnung

| Szenario | Given | When | Then | Automatisierter Test |
| --- | --- | --- | --- | --- |
| Noch keine Runde | Eine aktive Sitzung ohne beantworteten Zug | Der Dialog wird geöffnet | Abschlussauftrag und `Dialog beenden` sind verborgen | Svelte-Komponententest |
| Gespräch fortsetzen | Eine aktive Sitzung mit beantwortetem Zug | Die Gesprächsphase wird angezeigt | `Dialog beenden` ist sichtbar, der Abschlussauftrag nicht | Svelte-Komponententest |
| Abschluss vorbereiten | Eine aktive Sitzung mit beantwortetem Zug | Der Schüler wählt `Dialog beenden` | Abschlussauftrag, Rückkehr und endgültige Abgabe erscheinen | Svelte-Komponententest und Playwright |
| Zurückkehren | Die Abschlussansicht ist geöffnet | Der Schüler wählt `Zurück zum Dialog` | Die Eingabe erscheint wieder, ohne Servermutation | Svelte-Komponententest |
| Wiederaufnahme | Ein Abschlussentwurf wurde begonnen | Die Seite wird neu geladen oder pausiert | Phase und Entwurf werden im selben Browsertab wiederhergestellt | Svelte-Komponententest und Playwright |
| Isolation | Ein lokaler Entwurf gehört zu einer anderen Sitzung oder einem anderen Schüler | Der Dialog wird geöffnet | Der fremde Entwurf wird nicht übernommen | Svelte-Komponententest |
| Ohne Abschlussauftrag | Der Lehrer hat keinen Abschlussauftrag konfiguriert | Der Schüler beendet den Dialog | Eine Abgabebestätigung ohne Textfeld erscheint | Svelte-Komponententest |
| Letzte Runde | Die maximale Rundenzahl wurde erreicht | Die letzte KI-Antwort liegt vor | Es gibt keine weitere Eingabe; der Abschluss bleibt ein bewusster Schritt | Svelte-Komponententest |
| Endgültige Abgabe | Die Abschlussansicht ist ausgefüllt | Der Schüler gibt endgültig ab | Sitzung und Abgabe werden serverseitig abgeschlossen, der lokale Entwurf wird gelöscht | Playwright-Feature-Abnahme |
| Gestaltung | Gespräch oder Abschluss wird in Light oder Dark dargestellt | Desktop- und Mobilbreiten werden geprüft | Kanten, Farben, Sprecheranordnung und Aktionshierarchie entsprechen dem Designvertrag | CSS-Vertrag, berechnete Browserstyles und Referenzbilder |

## Technischer Vertrag

- OpenAPI, produktives Datenbankschema und fachliche DTOs ändern sich nicht.
- `LearningDialogWorkspace` erhält intern `learnerSub` für die sichere Entwurfsschlüsselung.
- Dialogstyles liegen in der `learning`-Schicht und definieren keine globalen Variablen oder hart codierten Produktfarben.
- Der Browsertest startet die echte Sitzung über Oberfläche und Server. Eine beantwortete Runde wird nur als deterministische Testvorbereitung direkt in der lokalen produktionsgleichen Datenbank angelegt; dadurch ist kein Modellaufruf nötig.
- Die Testvorbereitung liest `E2E_DATABASE_URL`, ersatzweise `SESSION_DATABASE_URL`, und gibt Zugangsdaten niemals aus.

## Abnahme

- Die gezielten Komponenten-, Vertrags- und Playwright-Tests sind grün.
- Die visuellen Referenzen für beide Phasen, beide Themes und Desktop/Mobil sind geprüft.
- `make verify-feature` läuft vor Fertigmeldung und Commit erfolgreich durch.
