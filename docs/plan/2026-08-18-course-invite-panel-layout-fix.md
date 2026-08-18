# Fehlerbehebung: Kurseinladung im schmalen Drawer

## Ausgangslage

Der Einladungsbereich rendert den QR-Code mit einer hochauflösenden Canvas-Größe von 1024 × 1024 Pixeln. Die QR-Bibliothek überträgt diese Größe zusätzlich als Inline-Stil auf das Canvas. Dadurch überschreibt sie die responsive Komponentenregel und verbreitert den Inhalt des 28 rem breiten Drawers auf mehr als 1000 Pixel. Der QR-Code wird rechts abgeschnitten; Vollbildaktion und E-Mail-Formular sind nur durch horizontales beziehungsweise langes vertikales Scrollen erreichbar.

Die Versand-API, der SMTP-Worker, das E-Mail-Eingabefeld und der QR-Vollbildmodus sind bereits vorhanden. Diese Fehlerbehebung ändert daher weder API-Vertrag noch Datenbankschema.

## User Story

Als Lehrkraft möchte ich im Einladungs-Drawer einen vollständig sichtbaren QR-Code mit unmittelbar erreichbarer Vollbildaktion und einem E-Mail-Feld sehen, damit ich den Klassenlink im Unterricht projizieren oder direkt durch GUSTAV an Lernende senden kann.

## BDD-Szenarien und automatisierte Tests

1. **QR-Code passt in den Drawer**
   - Given eine aktive Kurseinladung und ein schmaler Einladungs-Drawer
   - When GUSTAV den hochauflösenden QR-Code rendert
   - Then entfernt die Komponente die von der QR-Bibliothek gesetzte feste Darstellungsgröße
   - And der QR-Code und alle weiteren Inhalte bleiben innerhalb der verfügbaren Breite
   - Test: `CourseInvitationPanel.test.ts` prüft das Entfernen der Inline-Größe und den responsiven Größenvertrag.

2. **QR-Code groß und zentral anzeigen**
   - Given eine aktive Kurseinladung
   - When die Lehrkraft „Im Vollbild anzeigen“ auswählt
   - Then erscheint der QR-Code groß, zentriert und kontrastreich im nativen Vollbild oder im seitenfüllenden Fallback
   - And „Vollbild schließen“ sowie Escape stellen den Ausgangszustand wieder her
   - Tests: bestehende Komponentenfälle für natives Vollbild, Fallback, Fokus und History; bestehender `@feature-acceptance`-Playwright-Test.

3. **Einladungen per E-Mail versenden**
   - Given eine aktive Kurseinladung
   - When die Lehrkraft eine oder mehrere gültige Schul-E-Mail-Adressen einträgt
   - Then ist die Versandaktion ohne horizontales Scrollen erreichbar
   - And GUSTAV reiht je deduplizierter Adresse genau eine Einladung ein
   - Tests: Komponenten-Layoutvertrag, vorhandene Empfänger-, API-, Datenbank- und Worker-Tests sowie bestehender `@feature-acceptance`-Playwright-Test.

4. **Ungültige oder nicht erlaubte Adresse**
   - Given eine syntaktisch ungültige Adresse oder eine nicht zugelassene Domain
   - When die Lehrkraft den Versand auslöst
   - Then lehnt GUSTAV die Anfrage ab und zeigt eine verständliche Fehlermeldung
   - Tests: vorhandene API- und Empfängervalidierungstests.

5. **Nicht berechtigte Person**
   - Given eine Person, die den Kurs nicht als Lehrkraft besitzt
   - When sie Einladungen abruft oder versendet
   - Then antwortet die API ohne Offenlegung von Einladung oder Empfängeradressen mit `403`
   - Tests: vorhandene API- und RLS-Tests.

## API- und Datenbankauswirkung

Der bestehende Vertrag `POST /api/teaching/courses/{course_id}/invitations/{invitation_id}/email-deliveries` bildet den Versand bereits vollständig ab. Request Body, Statusantworten und Fehlerfälle bleiben unverändert. Es ist kein neuer OpenAPI-Ausschnitt erforderlich.

Die bestehenden Tabellen für Kurseinladungen und temporäre Mailzustellungen decken den Anwendungsfall ab. Es ist keine Migration nötig.

## Red-Green-Refactor

1. Einen Komponententest ergänzen, dessen QR-Mock wie die echte Bibliothek feste Inline-Maße setzt. Der Test muss zunächst zeigen, dass diese Maße erhalten bleiben und damit den Drawer verbreitern.
2. Nach jedem QR-Renderlauf ausschließlich die Darstellungsmaße des Canvas zurücksetzen; die interne 1024-Pixel-Auflösung für Scanqualität bleibt erhalten.
3. Den CSS-Vertrag auf `min-width: 0`, containergebundene Breite und quadratisches Seitenverhältnis härten.
4. Komponenten- und relevante Server-/API-Tests ausführen.
5. Den echten Drawer im Browser prüfen: kein horizontaler Überlauf, sichtbare Vollbildaktion, erreichbares E-Mail-Feld und großer zentraler Vollbild-QR-Code.
6. Als nutzerseitige Fehlerbehebung abschließend `make verify-feature` ausführen.

## Sicherheits- und Datenschutzgrenzen

- Einladungs-Token und E-Mail-Adressen werden weder protokolliert noch in Testausgaben übernommen.
- Die bestehende Owner-/Rollenprüfung und Domain-Whitelist bleiben unverändert.
- TLS, Secure-Cookies und SMTP-Konfiguration werden nicht abgeschwächt.
- Die Korrektur betrifft ausschließlich Darstellung und Erreichbarkeit; die hochauflösende lokale QR-Erzeugung bleibt erhalten.

## Abschluss und Nachweis

- Der QR-Code behält intern 1024 × 1024 Pixel, erhält aber keine feste 1024-Pixel-Darstellungsbreite mehr.
- Im realen 434 Pixel breiten Drawer stimmen Inhalts- und Scrollbreite überein; Vollbildaktion, E-Mail-Feld und Versandaktion sind sichtbar.
- Der Vollbild-Fallback füllt den verfügbaren Browserbereich aus und stellt den QR-Code groß und zentriert dar.
- Eine auf 500 Millisekunden begrenzte Vollbildanfrage verhindert, dass eingebettete Browser die Oberfläche dauerhaft warten lassen. Schließt die Lehrkraft währenddessen, wird eine verspätete Browserantwort ignoriert und der Hintergrund bleibt bedienbar.
- Komponenten-, Backend-, Build- und authentifizierte Feature-Acceptance-Prüfungen decken den vollständigen Ablauf ab.
