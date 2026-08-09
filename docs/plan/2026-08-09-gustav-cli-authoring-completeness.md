# Vollständiges GUSTAV-CLI-Authoring

## User Story

Als Lehrkraft möchte ich Lerneinheiten, Dialogaufgaben und Kurse vollständig über die GUSTAV-CLI authoren können, damit automatisierte Workflows dieselben fachlichen Möglichkeiten und Sicherheitsregeln wie die Weboberfläche nutzen.

## Grenzen

- H5P-Editor-JSON (`editor-model` und `save`) bleibt browser- und cookiegebunden.
- Die Dialog-KI-Vorschau bleibt browser- und cookiegebunden.
- Die H5P-CLI bleibt auf Paket-Import, -Export und -Reset begrenzt.
- Es sind keine Datenbankänderungen oder Migrationen vorgesehen.

## BDD-Szenarien

- Given eine Lehrkraft mit Schreibrecht, when sie eine Unit mit `--unit-type modular` erstellt, then können darin Phasen und Module angelegt werden.
- Given keine Unit-Type-Option, when eine Unit erstellt wird, then bleibt sie linear.
- Given eine gültige Dialog-JSON-Datei, when eine Dialogaufgabe erstellt oder geändert wird, then wird die vollständige Konfiguration gespeichert.
- Given eine ungültige Dialogdatei, when der Befehl ausgeführt wird, then scheitert er lokal ohne HTTP-Anfrage und ohne vertrauliche Inhalte auszugeben.
- Given ein gesetztes optionales Aufgabenfeld, when sein Clear-Flag verwendet wird, then sendet die CLI exakt `[]` oder `null`; nicht genannte Felder bleiben unverändert.
- Given ein modularer Graph, when `modules list` ausgeführt wird, then werden Phasen, Module und Kanten lesbar und deterministisch ausgegeben; `--json` bleibt verlustfrei.
- Given eine Lehrkraft, when sie Kurse, Mitglieder, Kursmodule, Freischaltungen und Löschaufträge verwaltet, then gelten die bestehenden Rollen-, Eigentümer- und Statusregeln.
- Given ein CLI-Token ohne erforderlichen Scope, when ein neuer Authoring-Endpunkt aufgerufen wird, then wird der Zugriff abgelehnt.
- Given ein CLI-Token, when H5P-Editor-JSON, Dialogvorschau oder die vollständige Benutzerliste aufgerufen wird, then bleibt der Zugriff gesperrt.
- Given eine angemeldete Lehrkraft im Browser, when sie den H5P-Editor lädt, speichert und neu öffnet, then bleiben die Editorparameter erhalten.

## Contract-first und TDD-Reihenfolge

1. Fehlende OpenAPI-Sicherheitsprofile und CLI-Contracttests rot schreiben.
2. OpenAPI und serverseitige Capability-Tabelle mit `read`, `write` und `delete` synchron erweitern.
3. CLI-Parser-, Payload-, Validierungs- und Ausgabetests für modulare Units, Dialoge, Clear-Semantik und Modulgraph rot schreiben; anschließend minimal implementieren und refaktorieren.
4. Kursbefehle vertikal mit Tests für Kurse, Mitglieder, Kursmodule, Freischaltungen, Schülersuche und Löschjobs ergänzen.
5. Authentifizierte `@feature-acceptance`-Rundläufe, Referenzdokumentation, Changelog und Testportfolio aktualisieren.

## Abnahme

- OpenAPI, CLI-Operationsregister und serverseitige Capability-Tabelle stimmen überein.
- Bestehende Befehle und H5P-Paketworkflows bleiben kompatibel.
- Rollen, Eigentümerschaft, CSRF und CLI-Scopes sind automatisiert geprüft.
- `make verify-feature` läuft vor der Fertigmeldung erfolgreich.

## Verifikationsstand vom 9. August 2026

- Die fokussierten CLI-, OpenAPI-, Capability-, Auth- und H5P-Tests sind mit 95 bestandenen Tests grün.
- Der vollständige Python-Lauf ist mit 2.281 bestandenen und 78 vorgesehen übersprungenen Tests grün; 484 Frontend- und 62 H5P-Sidecar-Tests sind ebenfalls grün.
- Beide neuen `@feature-acceptance`-Rundläufe für CLI-Authoring und browsergebundenes H5P-Editor-JSON sind grün.
- `make verify-feature` ist im gemeinsamen Arbeitsbaum noch nicht vollständig grün: Zwei parallel bearbeitete Lernoberflächen-Tests (`learner-navigation.spec.ts` und `learner-reference-workspace.spec.ts`) scheitern reproduzierbar außerhalb der CLI-Dateien. Diese fremden Änderungen wurden nicht überschrieben.
