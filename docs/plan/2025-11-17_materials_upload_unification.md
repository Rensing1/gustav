# Plan: Gemeinsamer Upload-Flow für Materialien (Lehrkräfte) mit Schüler-Pattern

Ziel: Die Material-Erstellen-Seite für Lehrkräfte nutzt den gleichen einfachen Datei-Upload-Flow wie Schüler-Submissions. Statt manueller Felder (Dateiname, MIME, Größe) gibt es eine Umschaltung Text|Datei und einen automatisierten Upload-Intent→Upload→Finalize-Ablauf. Code-Dopplungen werden durch einen geteilten JS-Helfer vermieden (KISS, Security-first, Clean Architecture respektiert: nur UI/Adapter-Schicht betroffen).

## User Story
Als Lehrkraft möchte ich beim Anlegen eines Materials zwischen Text und Datei wählen und bei Datei nur eine Datei auswählen müssen. Der Upload soll automatisch vorbereitet und abgeschlossen werden, damit ich ohne technische Details (MIME, Größe, SHA) schnell Materialien hochladen kann.

## BDD-Szenarien (Given-When-Then)
- Happy Path (Datei): Given ich bin Lehrkraft (Autor) und die Seite `/materials/new` ist geladen, When ich „Datei“ wähle, eine PDF/PNG/JPEG auswähle und auf „Anlegen“ klicke, Then werden Intent geholt, Datei hochgeladen, finalize aufgerufen und das Material erscheint in der Liste.
- Happy Path (Text): Given ich wähle „Text“, When ich Titel + Markdown absende, Then entsteht ein Markdown-Material wie bisher.
- Fehler: Ungültiges Format/Größe: When ich eine Datei außerhalb der Whitelist oder größer als das Limit wähle, Then blockt der Client und/oder die API antwortet mit 400 `mime_not_allowed`/`size_exceeded`.
- Fehler: Intent abgelaufen oder Upload fehlgeschlagen: When der Upload schiefgeht oder Intent-API 4xx/5xx liefert, Then bleibe ich auf der Seite und sehe einen verständlichen Fehler (kein teilweises Material).
- Fallback: When JS deaktiviert ist, Then die Text-Variante bleibt nutzbar und der Datei-Upload zeigt einen Hinweis, dass JS nötig ist.

## API-Vertrag
- Keine neuen Endpunkte. Wir nutzen weiter:
  - `POST /api/teaching/units/{unit_id}/sections/{section_id}/materials/upload-intents`
  - `POST /api/teaching/units/{unit_id}/sections/{section_id}/materials/finalize`
- Vertrag bleibt unverändert; Client ruft ihn automatisiert.

## Datenbank/Migration
- Keine Migration nötig. Schema für Materialien/Upload-Intents bleibt unverändert.

## Technischer Ansatz
- UI: In `/units/{u}/sections/{s}/materials/new` eine Umschaltung (Tabs/Radio) „Text“ | „Datei“. Nur der gewählte Block sichtbar.
- JS-Helper (shared): Extrahiere den Upload-Flow aus `learning_upload.js` in einen konfigurierbaren Helfer (z. B. `upload_flow.js`) mit `data-*`-Attributen für:
  - Dateieingabefeld
  - Intent-URL (Teaching/Learning)
  - Allowed MIME + Size-Limit
  - Hidden-Felder für intent_id, material_id, storage_key, mime_type, size_bytes, sha256
  - Finalize-Trigger (SSR-Submit) inkl. CSRF bleibt unverändert
- Lehrer-Wrapper: Kleiner Initializer, der den Helfer mit den Teaching-Pfaden (`…/materials/upload-intents`, `…/materials/finalize`) verdrahtet.
- Sichtbare Felder bei Datei: Datei-Input, Titel, optional Alt-Text. Keine manuellen MIME/Größe-Felder.
- Progressive Enhancement: Ohne JS Hinweis ausgeben; Text-Flow bleibt voll funktionsfähig.
- Context Awareness: Der gemeinsame JS-Helfer wird pro Kontext initialisiert (Teaching vs. Learning) und nimmt Endpunkt-URLs aus `data-*`-Attributen, keine Hardcodes über Kontextgrenzen hinweg.
- No-JS-Fallback: Nur der Text-Flow bleibt nutzbar; der Datei-Upload zeigt bei deaktiviertem JS einen Hinweis.

## Tests (Rot-Grün)
- UI-Tests (pytest/httpx/ASGI) für `/materials/new`:
  - Sichtbarkeit: genau eine Sektion sichtbar pro Modus (Text vs. Datei).
  - Datei-Flow: Mock Storage/Intent? (Client-seitig schwer in SSR; wir testen korrekte Hidden-Felder-Vorbereitung und dass Intent-URL/MIME/Size-Limit im Markup sind).
- Optional JS-Unit (falls Test-Infrastruktur vorhanden): Hash/Intent/Upload-Pipeline Happy Path + Fehlerpfade.
- Keine DB-Änderungstests nötig, da APIs unverändert.
- Konkrete Testfälle (Teaching, Lehrer):
  - SSR-Markup `/units/{u}/sections/{s}/materials/new`: Umschaltbare Blöcke (Text vs. Datei), No-JS-Hinweis bei Datei, `data-*` mit Intent-/Finalize-URLs und allowed MIME/Size.
  - Datei-Flow End-to-End (mit Fake-Storage/Intent): Intent→Upload (stub)→Finalize ergibt 201/200, Material `kind=file` angelegt und gelistet.
  - Fehlerpfade: 400 `mime_not_allowed`/`size_exceeded` werden gebubbelt; CSRF/Authorisierung gibt 403/404/400 passend zurück.
  - Regression Text-Flow: Markdown-Material weiterhin 201 und am Listenende.
  - Cache: SSR-Page liefert `Cache-Control: private, no-store`.
- Regression (Learning, Schüler):
  - Umschaltung Text/Upload weiterhin funktionsfähig; Intent→Upload→Submit füllt Hidden-Felder korrekt.
  - Client-Checks für MIME/Size entsprechen der API-Whitelist; keine Hardcodes von Teaching-URLs in Learning-Forms.
- JS-Helfer (falls Unit-Tests erlaubt):
  - Happy Path: Hidden-Felder (intent_id/material_id/storage_key/mime/size/sha256) werden nach Intent+Upload gesetzt.
  - Fehler: Intent 4xx/5xx blockiert Submit, ungültiges MIME/Size blockiert, fehlende Datei verhindert Submit.
  - No-JS: Datei-Block zeigt Hinweis; Text-Block submitbar.

## Schritte
1) Layout umbauen: Umschalt-UI (Radio/Choice-Cards) in `materials/new` mit getrennten Blöcken für Text/Datei; Hilfetext für No-JS.
2) JS extrahieren: Kern aus `learning_upload.js` in generischen Helfer auslagern; kleinen Initializer für Materialien hinzufügen.
3) Markup anpassen: Datei-Formular mit File-Input + Hidden-Feldern, die der Helfer füllt; Text-Form unverändert.
4) Tests ergänzen: SSR-Render-Tests für Umschaltung und Markup (Intent-URL/MIME/Size-Limit vorhanden).
5) Review gegen KISS/Security: Keine doppelten Flows, CSRF bleibt, gleiche Grenzen wie API, klarer Fehlertext.
