# GUSTAV-CLI: gerichtete Synchronisation von Lerneinheiten

## User Story

Als Lehrkraft möchte ich alle von mir erstellten Lerneinheiten einschließlich ihrer Inhalte lokal spiegeln, Unterschiede zwischen lokalem und externem Stand erkennen und Änderungen kontrolliert per Pull oder Push synchronisieren, damit ich nicht zahlreiche einzelne CLI-Befehle ausführen muss.

## Umfang und Entscheidungen

- Die CLI erhält `gustav sync status|pull|push --root <pfad>`; ohne Filter werden alle Lerneinheiten der angemeldeten Lehrkraft verarbeitet.
- Der lokale Spiegel besteht aus YAML-Manifesten, Markdown-Dateien und binären Assets. Kurse, Mitglieder, Freigaben, Abgaben und Lernstände bleiben außerhalb des Umfangs.
- Ein gespeicherter Basisstand erkennt lokale, externe und beidseitige Änderungen. Ohne ausdrückliches Override wird keine neuere Zielseite überschrieben.
- Löschungen werden ausschließlich mit `--prune` ausgeführt. Remote-Löschungen erfordern zusätzlich `--yes`; lokal entfernte Inhalte werden zunächst in einen lokalen Papierkorb verschoben.
- Die bestehende Teaching-API bleibt fachliche Quelle der Wahrheit. Die Synchronisation orchestriert vorhandene Endpunkte und führt keine Geschäftslogik in der CLI ein.
- `GET /api/me` und der geschützte Simulation-Stream werden contract-first für CLI-Tokens mit `read` freigegeben. Es ist keine Datenbankmigration notwendig.
- V1 verwendet vollständigen Preflight, erneute Prüfung pro Lerneinheit, ein lokales Journal und eine Abschlussprüfung. Eine serverweite atomare Unit-Revision ist nicht Bestandteil von V1.

## BDD-Szenarien und Testzuordnung

1. **Vollständiger erster Pull**
   - Given ein leerer verwalteter Zielordner und mehr als 50 externe Lerneinheiten
   - When `gustav sync pull` ausgeführt wird
   - Then werden alle Seiten sowie lineare und modulare Strukturen vollständig gespiegelt.
   - Automatisierung: CLI-Integrationstest für Pagination und Manifestaufbau.

2. **Alle Inhaltsarten spiegeln**
   - Given eine Lerneinheit mit Markdown, Datei, Simulation und H5P
   - When der erste Pull abgeschlossen ist
   - Then liegen alle Inhalte mit korrekten Hashes lokal vor.
   - Automatisierung: Pull-/Asset-Tests und echter Simulation-CLI-API-Test gegen die lokale Datenbank.

3. **Sauberer Status**
   - Given ein unveränderter Spiegel
   - When `gustav sync status` ausgeführt wird
   - Then meldet die CLI Gleichstand und führt keine schreibende Anfrage aus.
   - Automatisierung: CLI-Unit-Test für Text-, JSON- und Exitcode-Vertrag.

4. **Lokale Änderungen pushen**
   - Given lokal geänderte oder neue Lerneinheiten, erste und letzte Positionen, Module, Kanten, Materialien und Aufgaben
   - When `gustav sync push` ausgeführt wird
   - Then werden sie erzeugt beziehungsweise aktualisiert und exakt angeordnet.
   - Automatisierung: Push-Orchestrierungs- und Payloadtests.

5. **Externe Änderungen pullen**
   - Given eine extern geänderte Lerneinheit und ein lokal sauberer Basisstand
   - When `gustav sync pull` ausgeführt wird
   - Then werden die externen Änderungen lokal übernommen.
   - Automatisierung: Drei-Stände-Vergleichstest.

6. **Konflikte schützen**
   - Given lokale Änderungen vor einem Pull, externe Änderungen vor einem Push oder Änderungen auf beiden Seiten
   - When kein Richtungs-Override gesetzt ist
   - Then bricht der Lauf vor der ersten Mutation ab und nennt Objekt und Ursache ohne vertrauliche Inhalte.
   - Automatisierung: Konflikttest mit Assert auf null Schreibaufrufe.

7. **Löschungen ausdrücklich bestätigen**
   - Given ein Objekt fehlt im Quellzustand
   - When ohne `--prune` synchronisiert wird
   - Then bleibt es erhalten; mit bestätigtem Prune wird es entfernt beziehungsweise lokal gesichert.
   - Automatisierung: Löschtests für Leaf-, Container- und Unit-Ebene.

8. **Fehler fortsetzen**
   - Given ein Push scheitert nach einzelnen erfolgreichen API-Aufrufen
   - When derselbe Push erneut ausgeführt wird
   - Then erkennt das Journal die eigenen Änderungen und setzt ohne Duplikate fort.
   - Automatisierung: injizierter Netzwerkfehler und Retry-Test.

9. **Sicherheitsgrenzen**
   - Given ein falsches Konto, ein fehlender Scope, eine andere Instanz, manipuliertes YAML, Pfadtraversal oder ein Symlink
   - When synchronisiert wird
   - Then endet der Lauf ohne Mutation.
   - Automatisierung: Manifest-Securitytests sowie API-Tests mit echten CLI-Tokens.

## Lokaler Vertrag

```text
<root>/
  gustav.yaml
  .gustav/state.json
  .gustav/journal.json            # nur während eines unvollständigen Pushs
  .gustav/trash/<zeitstempel>/    # durch Pull-Prune gesicherte Inhalte
  units/<unit-key>/
    unit.yaml
    content/<container-key>/
      materials/
      tasks/<task-key>/
```

`gustav.yaml` bindet Schema-Version und Base-URL. `state.json` bindet zusätzlich den OIDC-`sub`, ordnet lokale Schlüssel den Remote-UUIDs zu und speichert ausschließlich normalisierte Digests. Token und Rohinhalte werden dort nicht abgelegt. YAML-Schlüssel sind stabile ASCII-Tokens; Remote-Zeitstempel, Storage-Keys und lokale Dateinamen gehören nicht zum semantischen Vergleich.

## API- und Migrationsentwurf

- `GET /api/me`: zusätzlich `cliTokenAuth`, erforderlicher Scope `read`.
- `GET /api/teaching/units/{unit_id}/materials/{material_id}/simulation`: zusätzlich `cliTokenAuth`, erforderlicher Scope `read`.
- Die Runtime-Capability-Tabelle muss exakt denselben Vertrag abbilden.
- Keine neue Tabelle, Spalte, Policy oder Migration: Spiegelzustand und Journal liegen ausschließlich lokal; bestehende RLS-/Besitzprüfungen bleiben maßgeblich.

## Verifikation

- Fokussierte Pytest-Suites für OpenAPI, CLI-Token-Capabilities und Sync-Engine.
- Echter API-Test gegen die lokal migrierte Testdatenbank.
- Kein Playwright-Test: Die neue Nutzerinteraktion findet ausschließlich in der CLI statt; Profiloberfläche und Browser-Editor erhalten keinen neuen Ablauf. Contract-, Auth- und Orchestrierungstests prüfen die relevanten Systemgrenzen direkt.
- Vor Fertigmeldung erfolgreiches `make verify`.
