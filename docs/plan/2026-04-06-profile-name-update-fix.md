# 2026-04-06 - Profil: Namensänderung stabilisieren

Status: abgeschlossen

## Zusammenfassung

- Die Reststörung bei `Vorname`/`Nachname` konnte auf einen klaren
  Keycloak-Validierungsfall eingegrenzt werden.
- Betroffen sind Konten, deren gespeicherte E-Mail-Adresse nicht zur live
  aktiven Domain-Regel `@gymalf.de` passt.
- Für Konten mit zulässiger E-Mail-Adresse läuft der Profil-Updatepfad mit dem
  reduzierten Payload.
- Es wird keine zusätzliche App-Datenbankablage für Profilnamen eingeführt; die
  dazu kurz angelegte Migration wurde wieder verworfen.

## BDD-Szenarien

1. Given ein authentifizierter Nutzer, when er `Vorname` und `Nachname`
   speichert, then sendet das Backend nur `firstName`, `lastName`, `email` und
   die benötigten Attribute an Keycloak.
2. Given ein authentifizierter Nutzer, when er nur den `Anzeigenamen`
   speichert, then sendet das Backend nur das aktualisierte Attribut
   `display_name` plus die bestehende `email` und überschreibt keine anderen
   User-Felder.
3. Given ein Konto mit einer nicht erlaubten Alt-/Test-E-Mail wie
   `test1@test.de`, when Vor- oder Nachname geändert werden, then lehnt die
   live konfigurierte Keycloak-Validierung den Update-Request mit einer
   E-Mail-Domain-Fehlermeldung ab.
4. Given ein Konto mit erlaubter `@gymalf.de`-Adresse, when Vor- oder Nachname
   geändert werden, then verarbeitet Keycloak denselben Updatepfad erfolgreich.

## Tests

- API-nahe Unit-Tests für `_update_profile_name`
- API-nahe Unit-Tests für `_update_profile_display_name`
- Reproduktion gegen laufenden Container und direkte Prüfung des betroffenen
  Keycloak-Users
- Log-Inspektion der live aktiven User-Profile-Konfiguration

## Annahmen

- Die laufende Keycloak-Instanz besitzt Konfigurationsdrift gegenüber dem
  eingecheckten `realm-gustav.json`: live ist zusätzlich eine
  `pattern`-Validierung für `email` aktiv.
- Der verbleibende Fehler ist damit ein Daten-/Konfigurationsfall für nicht
  mehr zulässige Altadressen und kein genereller Defekt des aktuellen
  Profil-Updatepfads.
- Der Cooldown für Namensänderungen bleibt unverändert.
