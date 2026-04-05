# H5P Session Sync nach Frontend-Rebuilds

## Zusammenfassung
- Der H5P-Player und der H5P-Editor scheiterten nach einem Frontend-Neustart mit `unauthenticated`.
- Ursache war die geteilte Session-Architektur:
  - SvelteKit nutzt `gustav_bff_session` mit In-Memory-Token-Store.
  - H5P und ältere Backend-Pfade verlassen sich auf `gustav_session`.
- Der Fix ergänzt einen gezielten Brückenschlag statt eines großen Auth-Umbaus.

## Umsetzung
- Neues API-Contract-Element `POST /api/app/session-sync` in `api/openapi.yml`.
- Neue FastAPI-Route erzeugt aus einem gültigen Bearer-Kontext eine normale `gustav_session` und ersetzt dabei eine mitgesendete Alt-Session best effort.
- Der Svelte-Auth-Callback ruft `session-sync` nach erfolgreichem Token-Austausch auf und reicht das resultierende `Set-Cookie` an den Browser weiter.
- H5P-Player und H5P-Editor übersetzen `unauthenticated` in eine klare Sitzungs-Meldung für Nutzerinnen und Nutzer.

## Tests
- OpenAPI-Contract für `POST /api/app/session-sync`.
- API-Tests für Session-Erzeugung, Ersetzung einer Alt-Session und Bearer-Pflicht.
- Packaging-Contracts für den Svelte-Auth-Callback und die H5P-Session-Meldung.
- Nachbarverträge für `session-bootstrap` und die bestehende BFF-Bearer-Absicherung bleiben grün.

## Annahmen
- Der Fix stabilisiert neu aufgebaute Sitzungen; bereits kaputte Browserzustände ohne `gustav_session` brauchen einmalig einen Reload oder Re-Login.
- Es gibt bewusst keine Persistenz des Svelte-In-Memory-Stores und keine komplette Vereinheitlichung aller Auth-Flows in diesem Schritt.
