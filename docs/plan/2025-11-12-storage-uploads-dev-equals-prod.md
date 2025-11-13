# Plan: Directe Browser-Uploads zu Supabase (dev = prod)

Ziel
- Dev = Prod herstellen: Der Browser lädt Uploads direkt zur öffentlichen Supabase‑Storage‑API, identisch wie in Produktion. Kein App‑Proxy im Uploadpfad.

User Story
- Als Schüler möchte ich meine Lösung (Bild/PDF) hochladen, ohne CORS/Netzwerkprobleme, sodass der gleiche Flow lokal und in Produktion funktioniert.

Akzeptanzkriterien (BDD)
- Given ein eingeloggter Schüler und ein freigegebener Task
  - When der Client einen Upload‑Intent anfordert
  - Then enthält die Antwort eine signierte URL deren Host SUPABASE_PUBLIC_URL entspricht (z. B. supabase.localhost)
  - And ein anschließendes PUT des Browsers auf diese URL liefert 2xx
  - And das Finalisieren der Submission (POST /submissions) antwortet 200/201
- Edge: disallowed MIME → 400 mime_not_allowed
- Edge: size > MAX_UPLOAD_BYTES → 400 size_exceeded
- Fehler: CSRF (Origin/Referer mismatch) → 403 csrf_violation (weiterhin erzwungen)

Vorgehen (High‑Level)
1) Reverse‑Proxy: öffentliche Supabase‑Basis
   - Caddy: neue Site `supabase.localhost:443 { tls internal; reverse_proxy supabase_kong_gustav-alpha2:8000 }`
   - Ergebnis: Der Browser erreicht die Storage‑API unter `https://supabase.localhost/storage/v1/...`.
2) ENV‑Trennung „internal vs. public“
   - Behalten: `SUPABASE_URL=http://supabase_kong_gustav-alpha2:8000` (intern)
   - Neu: `SUPABASE_PUBLIC_URL=https://supabase.localhost` (browser‑tauglich)
   - Proxy deaktiviert lassen: `ENABLE_STORAGE_UPLOAD_PROXY=false`
3) Code (klein, ohne API‑Änderung)
   - `backend/teaching/storage_supabase.py` → `_normalize_signed_url_host()` so anpassen, dass (falls gesetzt) `SUPABASE_PUBLIC_URL` für Host‑Umschreibung bevorzugt wird; Pfadpräfix `/storage/v1` sicherstellen; Doppelslashes kollabieren.
   - Keine Änderung der Routen/Contracts nötig.
4) Tests (TDD)
   - Unit‑Test „rewrite public host“: Given `SUPABASE_PUBLIC_URL=https://supabase.localhost` und eine signierte URL mit internem Host → Then Host wird auf `supabase.localhost` umgeschrieben, Pfad ist `/storage/v1/object/...`.
   - API‑Test „upload‑intent response“: Antwort enthält `url` (https://supabase.localhost/...), erlaubte `headers`, `max_size_bytes`, `expires_at`.
5) Sicherheit/Trust
   - Browser‑Trust: Das Caddy‑Root‑Zertifikat muss lokal in die OS‑Trust‑Stores importiert werden (ansonsten scheitern XHRs wegen untrusted CA).
   - Alternativ: öffentlich vertrauenswürdiges Zertifikat (nicht Teil dieses Plans).
6) Rollout
   - Caddyfile ergänzen, `docker compose up -d caddy`
   - Compose ENV für `web` um `SUPABASE_PUBLIC_URL` erweitern
   - Minimal‑Patch im Adapter, Tests grün, App neu starten

Risiken / Gegenmaßnahmen
- Untrusted CA im Browser → Upload scheitert: Root‑CA via `.tmp/caddy-root.crt` exportieren und in den Host‑Trust‑Store installieren (Dokumentationsschritt). 
- Abweichende Pfadformate aus Bibliotheken (supabase vs storage3): Pfadnormalisierung + Doppelslash‑Kollaps sind Teil des Patches.
- Prod‑Parität: In Prod bleibt alles identisch (öffentliche Supabase‑Domain), kein App‑Proxy.

Nicht‑Ziele
- Keine Änderung am OpenAPI‑Vertrag (Responses bleiben unverändert)
- Keine DB‑Migrationen erforderlich

Aufgabenliste (Umsetzung in Reihenfolge)
1) Caddyfile: Site `supabase.localhost:443` hinzufügen (Reverse Proxy → supabase_kong_gustav-alpha2:8000)
2) docker-compose.yml (web): `SUPABASE_PUBLIC_URL=https://supabase.localhost` ergänzen; Proxy bleibt aus
3) Adapter‑Patch `_normalize_signed_url_host()` (Public vor Internal priorisieren; Pfadpflege)
4) Tests schreiben (Unit + kleiner Intent‑Test)
5) Dokumentation „Uploads (Dev = Prod)“ ergänzen (ENV, Trust‑Hinweise, Troubleshooting)

Backout‑Plan
- Bei Problemen: `SUPABASE_PUBLIC_URL` vorübergehend entfernen und (nur in Dev) den Same‑Origin‑Proxy wieder aktivieren. Diese Option bleibt dokumentiert, ist aber nicht dev=prod‑konform und daher nur als Fallback gedacht.

