# Kursregistrierung über QR-Code und E-Mail-Einladung

## Ziel

Lehrkräfte erzeugen für einen aktiven, vollständig konfigurierten Kurs genau einen gemeinsamen Klassenlink. Der Link ist 24 Stunden gültig, widerrufbar und wird als kopierbarer Link, E-Mail-Einladung sowie QR-Code angeboten. Lernende bestätigen den Beitritt einmal, registrieren sich bei Bedarf über Keycloak und werden danach automatisch dem Kurs zugeordnet.

Der QR-Code lässt sich in den nativen Browser-Vollbildmodus schalten. Falls dieser nicht verfügbar ist, verwendet GUSTAV eine bildschirmfüllende, kontrastreiche Overlay-Darstellung.

## User Story

Als Lehrkraft möchte ich einen Klassenlink als großen Vollbild-QR-Code präsentieren und an mehrere Schul-E-Mail-Adressen senden, damit neue Lernende sich selbst registrieren und automatisch meinem Kurs beitreten können.

## BDD-Szenarien

1. **Einladung erstellen**
   - Given eine Lehrkraft besitzt einen aktiven und vollständig konfigurierten Kurs
   - When sie eine Einladung erstellt
   - Then erhält sie einen 24 Stunden gültigen Link und QR-Code.
2. **Vollbild anzeigen und schließen**
   - Given ein aktiver QR-Code
   - When die Lehrkraft „Im Vollbild anzeigen“ auswählt
   - Then erscheint der QR-Code groß, zentriert und kontrastreich
   - And bei fehlender Fullscreen-API verwendet GUSTAV ein bildschirmfüllendes Overlay
   - And `Esc`, Schließen und Browser-Zurück stellen den Ausgangszustand wieder her.
3. **Link erneuern oder widerrufen**
   - Given ein aktiver Klassenlink
   - When die Lehrkraft ihn erneuert oder widerruft
   - Then ist der vorherige Link unmittelbar ungültig.
4. **Neue Registrierung**
   - Given ein nicht registrierter Lernender öffnet eine gültige Einladung
   - When er den Beitritt bestätigt, sich mit erlaubter Schuladresse registriert und die Adresse verifiziert
   - Then wird er automatisch Kursmitglied und sieht den Kurs.
5. **Bestehendes Konto und Idempotenz**
   - Given ein registrierter Lernender
   - When er den Link annimmt und sich anmeldet
   - Then wird er genau einmal hinzugefügt
   - And eine wiederholte Einlösung bleibt erfolgreich, ohne eine zweite Mitgliedschaft anzulegen.
6. **Entferntes Mitglied**
   - Given ein Lernender trat über den Link bei und wurde danach entfernt
   - When er denselben Link erneut einlöst
   - Then bleibt der Wiedereintritt blockiert
   - And erst ein neu erzeugter Klassenlink erlaubt einen erneuten Beitritt.
7. **Ungültige Einladung und Berechtigungen**
   - Given ein abgelaufener, widerrufener oder zu einem archivierten Kurs gehörender Link
   - When er geöffnet oder eingelöst wird
   - Then entsteht keine Mitgliedschaft und die Antwort bleibt fail-closed
   - And nur der Kurs-Owner verwaltet Links
   - And ausschließlich Lernende lösen sie ein.
8. **E-Mail-Versand und Datensparsamkeit**
   - Given mehrere gültige Schuladressen
   - When die Lehrkraft den Versand anstößt
   - Then erhält jede Adresse eine eigene Nachricht
   - And erfolgreiche Klartextadressen werden sofort entfernt
   - And fehlgeschlagene Adressen werden spätestens nach sieben Tagen gelöscht.

## API-Vertrag

Contract-first werden in `api/openapi.yml` folgende Wege ergänzt:

- `POST /api/teaching/courses/{course_id}/invitations`
- `GET /api/teaching/courses/{course_id}/invitations/active`
- `DELETE /api/teaching/courses/{course_id}/invitations/{invitation_id}`
- `POST /api/teaching/courses/{course_id}/invitations/{invitation_id}/email-deliveries`
- `GET /api/teaching/courses/{course_id}/invitations/{invitation_id}/email-deliveries/status`
- `POST /api/teaching/courses/{course_id}/invitations/{invitation_id}/email-deliveries/retry`
- `POST /api/course-invitations/preview`
- `POST /api/course-invitations/redeem`

Einladungsantworten sind privat und nicht cachebar. Preview und Redemption erhalten Tokens ausschließlich im Request Body. Der öffentliche Preview-Endpunkt gibt nur Kurstitel und Ablaufzeit zurück.

## Datenmodell und Sicherheit

Eine Supabase-Migration führt `course_invitations`, `course_invite_redemptions`, `course_invite_mail_batches` und `course_invite_mail_deliveries` ein. RLS ist für alle Tabellen aktiv. Owner- und Worker-Operationen laufen über eng begrenzte `SECURITY DEFINER`-Funktionen mit festem `search_path`.

Ein versioniertes HMAC-Token besteht aus Einladungs-ID und zufälliger Nonce. Das vollständige Token wird nicht gespeichert. Ein dediziertes `COURSE_INVITE_SIGNING_SECRET` ist in produktionsnahen Umgebungen Pflicht. Einladungserzeugung, Widerruf und Einlösung erfolgen transaktional. Kursarchivierung widerruft bestehende Einladungen; Wiederherstellung reaktiviert sie nicht.

## E-Mail-Verarbeitung

Die bestehende Worker-Schleife verarbeitet zusätzlich Course-Invitation-Mail-Jobs mit den vorhandenen `KC_SMTP_*`-Werten. Jede Adresse erhält eine einzelne Multipart-Nachricht. Temporäre Fehler werden höchstens fünfmal mit gedeckeltem Backoff wiederholt, jedoch nie nach Ablauf oder Widerruf. Token, Adressen und Nachrichtentexte erscheinen nicht in Logs.

## Oberfläche

Der Mitglieder-Drawer erhält „Klasse einladen“. Die Ansicht enthält QR-Code, Linkkopie, PNG-Download, Vollbild, Ablaufzeit, Einlösungszahl, Widerruf/Neuerzeugung, Mehrfach-Eingabe für E-Mail-Adressen und Versandstatus.

Der native Vollbildmodus zeigt nur Kurstitel, Ablaufzeit, QR-Code und Schließen-Aktion. Ein `position: fixed`-Fallback liefert dieselbe Bedienung. Fokus, `Esc`, `fullscreenchange`, Zurück-Navigation und Orientierungsänderungen werden deterministisch behandelt.

Der Link trägt das Token im URL-Fragment. Die SvelteKit-Seite übermittelt es per HTTPS im Request Body, entfernt das Fragment aus der Historie und speichert die bestätigte Beitrittsabsicht in einem signierten `HttpOnly; Secure; SameSite=Lax`-Cookie bis zum Auth-Rücksprung.

## Red-Green-Refactor und Abnahme

1. OpenAPI-Vertrag und Contract-Tests rot.
2. Migrationstests und API-/Repository-Tests gegen echte lokale PostgreSQL-Datenbank rot.
3. Minimale Migration, Use Cases und Routen grün.
4. Worker-Tests für SMTP, Retry, Bereinigung und PII-freie Logs rot, dann grün.
5. Svelte-/SvelteKit-Tests für QR, Vollbild, Fallback und Auth-Fortsetzung rot, dann grün.
6. Ein `@feature-acceptance`-Playwright-Test prüft Lehrkraft-UI, Vollbild-QR, Registrierung im echten Keycloak, E-Mail-Verifikation, automatische Mitgliedschaft und Sichtbarkeit in beiden Rollen.
7. Abschließend `make verify-feature` und wegen Compose-Anpassungen `make docker-validate`.

## Nicht enthalten

- Persönliche Einmallinks
- Konfigurierbare Ablaufzeit
- CSV-Import
- Individuell bearbeitbare Mailtexte
- Ersatz der bestehenden manuellen Mitgliederverwaltung

## Umsetzungsstatus

Am 15. August 2026 vollständig umgesetzt. Der Klassenlink, die E-Mail-Zustellung, der lokale QR-Code, der native Vollbildmodus mit seitenfüllendem Fallback sowie der Registrierungs- und Beitrittsfluss sind in Oberfläche, API, Datenbank und bestehendem Worker integriert.

Die Abnahme erfolgte mit `make docker-validate` und `make verify-feature`. Der verpflichtende Browser-Rundlauf umfasst 17 erfolgreiche `@feature-acceptance`-Tests. Der neue Einladungstest durchläuft mit echtem Chromium die Lehrkraft-Oberfläche, den Vollbild-QR-Code, Keycloak-Registrierung und E-Mail-Verifikation, PostgreSQL sowie den automatischen Kursbeitritt.
