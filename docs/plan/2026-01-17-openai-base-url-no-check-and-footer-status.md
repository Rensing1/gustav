# Plan: OPENAI_BASE_URL ohne Sicherheits-Blocker + UI-Status in der Fußleiste

Datum: 2026-01-17  
Autor: Codex (mit Felix)  
Status: DONE (implementiert 2026-01-17)

## Implementation (done)
- Security-Blocker entfernt: `OPENAI_BASE_URL` wird auch in `prod` nicht mehr auf HTTPS/Host eingeschränkt.
- Neuer Status-Endpunkt: `GET /internal/health/openai` (teacher/operator only, private/no-store).
- Footer-Indikator (teacher/operator only) + JS polling (60s) für schnelle Sichtbarkeit im UI.
- Tests ergänzt/angepasst, damit Verhalten regressionssicher bleibt.

## Kontext / Problem
- Beim Einreichen von Bild/PDF-Abgaben kann die KI-Auswertung fehlschlagen mit der Meldung **„insecure_OPENAI_BASE_URL“**.
- Ursache: In `GUSTAV_ENV=prod` prüft der Worker, ob `OPENAI_BASE_URL` bei `http://...` nur auf „lokale“ Hosts zeigt. Remote-Hosts werden blockiert.
- In unserem Setup läuft der KI-Server auf einem anderen PC, erreichbar via Tailscale. Die Verbindung ist in der Praxis verschlüsselt, aber GUSTAV kann das nicht sicher erkennen.

## Ziel(e)
1. **Keine Blockade mehr:** GUSTAV akzeptiert jede `OPENAI_BASE_URL` (auch `http://...` zu Remote-Hosts) ohne Vorab-Prüfung.
2. **Transparenz für Lehrkräfte:** In der UI-Fußleiste gibt es einen kleinen Indikator, der zeigt:
   - ist die KI-URL erreichbar?
   - liefert der Endpoint eine Modell-Liste (mindestens ein Model)?

## User Story
Als Lehrer möchte ich, dass die KI-Auswertung nicht an einer „Sicherheitsprüfung“ scheitert, und ich möchte im Alltag schnell sehen, ob die KI gerade erreichbar ist und ob Modelle verfügbar sind, damit ich Probleme schneller einordnen kann.

## BDD-Szenarien (Given–When–Then)
1) **OPENAI_BASE_URL wird nicht geblockt**
- Given `GUSTAV_ENV=prod` und `OPENAI_BASE_URL=http://example.com/api/v1`  
- When der Feedback-Adapter initialisiert wird  
- Then gibt es keinen Fehler „insecure_OPENAI_BASE_URL“ mehr.

2) **Footer-Indikator zeigt „nicht konfiguriert“**
- Given `OPENAI_BASE_URL` ist nicht gesetzt  
- When die Lehrkraft eine Seite lädt  
- Then zeigt der Indikator „KI: nicht konfiguriert“.

3) **Footer-Indikator zeigt erreichbar + Modelle**
- Given `OPENAI_BASE_URL` ist gesetzt und `GET {base_url}/models` liefert eine Liste mit mindestens einem Eintrag  
- When die Lehrkraft eine Seite lädt  
- Then zeigt der Indikator „KI: ok (N Modelle)“.

4) **Footer-Indikator zeigt nicht erreichbar**
- Given `OPENAI_BASE_URL` ist gesetzt, aber der Server antwortet nicht (Timeout/Netzfehler)  
- When die Lehrkraft eine Seite lädt  
- Then zeigt der Indikator „KI: nicht erreichbar“.

5) **Berechtigung**
- Given ein nicht angemeldeter Nutzer ruft den Status-Endpunkt auf  
- When `GET /internal/health/openai`  
- Then Antwort ist 401 (private/no-store).

## Umsetzung (TDD: Red → Green → Refactor)
1. **Tests anpassen:** bestehende Adapter-Tests so ändern, dass `http://` zu Remote-Hosts in `prod` nicht mehr fehlschlägt.
2. **Neuer Status-Endpunkt:** `GET /internal/health/openai` (teacher/operator) liefert JSON mit `reachable` und `modelsCount`.
3. **Footer-Markup:** Layout erweitert um eine kleine Status-Anzeige (nur für Lehrkräfte/Operator).
4. **JS-Update:** Browser fragt den Status-Endpunkt ab und aktualisiert die Anzeige; bei 401/403 bleibt sie verborgen.

## Risiken / Abwägung
- Das Entfernen des Blockers kann Fehlkonfigurationen nicht mehr „früh“ abfangen (z.B. versehentlich `http://` ins Internet).  
  → Bewusst akzeptiert, weil der Betreiber die Verantwortung übernimmt (Felix-Anforderung).
