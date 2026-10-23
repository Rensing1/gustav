# Keycloak-Follow-ups vom 23.10.2026

## Auftrag und User Story

Als Verantwortlicher für GUSTAV möchte ich Keycloak 26.8.1 mit aktuellen Bootstrap-Optionen und einer passenden Einzelknotenkonfiguration betreiben und die verbleibende interne bcrypt-Abhängigkeit nachvollziehen können, damit Neuinstallation und Upgrade bestehende Anmeldungen erhalten.

Die Änderung betrifft ausschließlich den Infrastruktur- und Konfigurationsvertrag. Es entsteht kein neuer nutzerseitiger Ablauf; deshalb ist kein neuer Playwright-Featuretest erforderlich. `api/openapi.yml`, GUSTAV-Schema und Supabase-Migrationen bleiben unverändert. Die vorhandenen API- und Migrationsgrundlagen wurden geprüft; lokale ENV-Werte werden weder ausgegeben noch übernommen. Keycloaks eigenes Schema wird ausschließlich vom jeweiligen Keycloak-Image in einer synthetischen PostgreSQL-Testinstanz migriert.

## Plan: Red – Green – Refactor

1. Vertragstests für moderne Bootstrap-Namen, Vorrang neuer Werte, Rückwärtskompatibilität alter ENV-Eingaben und explizit deaktivierte Routenanhänge ergänzen. Den roten Zustand vor der Konfigurationsänderung nachweisen.
2. An Keycloak ausschließlich `KC_BOOTSTRAP_ADMIN_USERNAME` und `KC_BOOTSTRAP_ADMIN_PASSWORD` übergeben. Bestehende `KEYCLOAK_ADMIN*`-Eingaben bleiben Fallback; neue Eingaben haben Vorrang. Das pauschale `.env`-Durchreichen im Keycloak-Service entfernen, damit alte Variablen nicht zusätzlich im Container landen. Alle benötigten Einstellungen bleiben explizit konfiguriert.
3. Die versionsgenaue `shouldAttachRoute`-Implementierung prüfen und den Routenanhang für den einzelnen Keycloak-Knoten explizit deaktivieren. Keine Änderung an TLS, Cookiesicherheit oder Proxy-Vertrauen.
4. Den vorhandenen isolierten Smoke erweitern: Neuinstallation, Upgrade 26.7.3/bcrypt 1.6.0 → 26.8.1/bcrypt 1.7.0, OIDC-Discovery, richtige/falsche bcrypt-Passwörter, unveränderter vorhandener Admin trotz geänderter Bootstrap-Werte und Nachweis der internen Password-Hashing-SPI-Abhängigkeit.
5. Öffentliche Konfigurationsreferenz, Upgrade-Risiko und Changelog aktualisieren. `make verify` und `make docker-validate` ausführen; erst nach erfolgreichen Nachweisen lokal auf `master` committen. Kein Push und kein Produktionsrollout.

## BDD und Testzuordnung

| Given – When – Then | Nachweis |
| --- | --- |
| Alte oder neue synthetische ENV-Werte – Compose rendert Keycloak – nur moderne Containernamen mit dokumentiertem Vorrang entstehen | Compose-Vertragstests und isolierte Compose-Interpolation |
| Einzelner Keycloak-Knoten – 26.8.1 startet – Routenanhang ist explizit aus und die `shouldAttachRoute`-Warnung fehlt | Konfigurationsvertrag und Laufzeit-Smoke |
| Leere PostgreSQL-Datenbank – 26.8.1 startet – Bootstrap-Admin und OIDC-Discovery funktionieren | `test_discovery_bcrypt_and_schema_compatibility[empty-postgres]` |
| Synthetischer 26.7.3-Bestand – Upgrade mit anderen Bootstrap-Werten – vorhandener Admin bleibt gültig, neuer Bootstrap-Zugang wird nicht angelegt | `test_discovery_bcrypt_and_schema_compatibility[schema-upgrade]` |
| Importierter bcrypt-Hash – richtiges/falsches Passwort, auch wiederholt nach Upgrade – Token oder `invalid_grant` | Beide Laufzeit-Smokes; Hash bleibt für die Upgrade-Prüfung bcrypt |
| Gebautes Provider-Artefakt 1.7.0 – SPI-Metadaten und Keycloak-Registrierung werden geprüft – interne Abhängigkeit ist sichtbar | Artefakt-/Serverinfo-Prüfung im isolierten Smoke |

## Grenzen und Risiken

Bootstrap-Einstellungen erzeugen nur beim erstmaligen Anlegen des Master-Realms einen temporären Admin; sie setzen keine bestehenden Passwörter zurück. Bestehende Werkzeugkonfigurationen mit `KEYCLOAK_ADMIN*` bleiben verwendbar. Die öffentliche Referenz enthält ausschließlich generische Konfigurationssemantik und synthetische Beispiele, keine Produktionswerte oder privaten Betriebsanweisungen.

Die interne Password-Hashing-SPI ist keine stabile Erweiterungsschnittstelle. Ein erfolgreicher 26.8.1-Smoke ist keine Kompatibilitätszusage für das nächste Keycloak-Major-Upgrade. Vor dessen Freigabe müssen Provider-Build, SPI-Verwendung und beide Datenbank-/Anmeldesmokes erneut geprüft werden; gegebenenfalls ist eine neue Provider-Version oder Anpassung nötig.

## Nachweise

- Red: Die drei neuen Compose-/Beispielverträge schlugen vor der Umsetzung fehl; ebenso alle fünf neuen echten Compose-Interpolationsfälle wegen fehlender moderner Bootstrap-Namen.
- Green: 18 gezielte Vertrags-/Interpolationsprüfungen bestanden. `make docker-validate` und `git diff --check` erfolgreich. Der lokale Supabase-Status wurde ohne Ausgabe seiner Zugangsdaten geprüft.
- Beide isolierten Laufzeit-Smokes und die fünf Interpolationsfälle bestanden innerhalb von `make verify`: 7 Tests in 56,32 Sekunden. Neuinstallation mit 26.8.1 und Upgrade aus 26.7.3 jeweils gegen eigene PostgreSQL-16.15-Instanzen, ohne vorhandene Datenbanken oder Konten zu verwenden.
- Discovery und JWKS erreichbar; falsches Passwort vor und nach richtiger bcrypt-Anmeldung jeweils mit `invalid_grant` abgewiesen. Die gespeicherte Passwortkennung bleibt bcrypt, auch über den Upgrade-Schritt hinweg.
- `/admin/serverinfo` bestätigt in beiden Versionen die interne Password-Hashing-SPI samt geladenem bcrypt-Provider; das jeweilige Provider-JAR 1.6.0 beziehungsweise 1.7.0 ist im gebauten Runtime-Image vorhanden. Keine `shouldAttachRoute`- oder alte Admin-ENV-Warnung beim 26.8.1-Start.
- Nach Upgrade mit abweichendem Bootstrap-Namen und -Passwort funktioniert der vorhandene Admin weiterhin. Sein Passwort wird nicht ersetzt und der neue Bootstrap-Admin wird nicht angelegt. Laufbezogene Container, Netzwerke und Image-Tags wurden vollständig entfernt.
- Vollständiges `make verify` erfolgreich: alle Architektur-, API-, Inventar-, Lieferketten-, Lint- und Image-Gates bestanden; 3.195 Backend-Tests bestanden, 41 reguläre Opt-in-Tests übersprungen, zwei bestehende Bibliothekswarnungen. Svelte-Prüfung ohne Fehler oder Warnungen; 879 Frontend-Tests und 80 H5P-Tests bestanden. Auch die zusätzlichen Frontend-Tooling-Verträge bestanden. Keine Änderung am produktiv verwendeten Stack und keine Veröffentlichung von Secrets oder privaten Betriebsunterlagen.

## Kritische Prüfung

Die Änderung bleibt auf der Infrastrukturgrenze; fachliche Schichten und Berechtigungslogik werden nicht berührt. Das explizite ENV-Mapping ist kleiner und nachvollziehbarer als ein zusätzliches Startskript zum Entfernen alter Variablen. Es verhindert außerdem die pauschale Weitergabe anderer Anwendungsgeheimnisse. Bestehende zusätzliche Keycloak-ENV-Anpassungen außerhalb der expliziten Liste benötigen künftig einen Compose-Eintrag; diese Grenze steht in der Konfigurationsreferenz. Die Smoke-Erweiterung prüft die tatsächliche SPI-Registrierung statt nur das Vorhandensein eines Warntexts. Keine neue Runtime-Abhängigkeit, kein Datenbankzugriff in Schleifen der Anwendung, keine Schema- oder RLS-Änderung.
