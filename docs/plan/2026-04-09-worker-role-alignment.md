# Worker-Rollenangleichung für Learning-Queue

## Zusammenfassung
- Der Learning-Worker soll konsistent als dedizierte Rolle `gustav_worker` laufen.
- `gustav_app` bleibt der Login für Web/App-Kontexte.
- Health-Probe und Compose werden auf den tatsächlichen Runtime-Zustand ausgerichtet.

## Umsetzung
- Eigener Worker-Login via `LEARNING_WORKER_DB_USER` / `LEARNING_WORKER_DB_PASSWORD`
- Compose-Fallback für `learning-worker` nutzt nicht mehr `APP_DB_USER`
- Neuer lokaler Provisioning-Target `make learning-worker-db-login-user`
- Python-Health-Service prüft `current_user == 'gustav_worker'`
- SQL-Health-Probe liefert nur noch Queue-Sichtbarkeit

## Tests
- Worker-DSN-Fallback baut standardmäßig eine DSN für `gustav_worker`
- Health-Service degradiert bei `current_user=gustav_app`
- Health-Endpoint bleibt bei Queue-Sichtbarkeit funktionsfähig

## Annahmen
- Der dedizierte Worker-Login wird lokal per Make-Target und in Prod out-of-band provisioniert.
- Keine Änderung an den eigentlichen Worker-DML-/Feedback-Pfaden.
