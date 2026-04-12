# Teaching-Datei-Upload auf Browser-Upload zurückführen

## User Story
- Als Lehrkraft möchte ich Datei-Materialien im Node-Editor zuverlässig hochladen können, ohne dass der Upload an Container-/Proxy-Topologie oder serverseitigen Presign-Aufrufen scheitert.
- Als Maintainer möchte ich, dass Teaching und Learning dieselbe technische Upload-Basis nutzen, damit Header-Normalisierung, Hashing und Fehlerbehandlung nicht auseinanderlaufen.

## BDD-Szenarien
- Given eine Lehrkraft öffnet den Node-Editor mit aktiviertem JavaScript, When sie ein Datei-Material anlegt, Then fordert der Browser einen Upload-Intent an, lädt die Datei direkt hoch, berechnet `sha256` lokal und sendet anschließend nur noch `intent_id` und `sha256` an die Finalize-Action.
- Given eine Lehrkraft wechselt nach vorbereiteten Datei-Metadaten die ausgewählte Datei oder den Materialtyp, When sie erneut speichert, Then werden veraltete `intent_id`-/`sha256`-Werte verworfen und neu vorbereitet.
- Given eine Lehrkraft versucht ohne aktiviertes JavaScript ein Datei-Material anzulegen, When die Server-Action einen Datei-POST ohne vorbereitete Metadaten erhält, Then antwortet sie mit einer verständlichen Fehlermeldung statt einen serverseitigen Storage-Upload zu versuchen.
- Given Learning und Teaching erzeugen Upload-Intents, When der Storage-Adapter beim Request noch nicht verdrahtet ist, Then versuchen beide Pfade denselben Lazy-Rewire und liefern erst danach `503 storage_adapter_not_configured`.
- Given ein Lernender lädt PDF, Bild, SB3 oder HEX hoch, When der Browser den gemeinsamen Upload-Helper nutzt, Then bleiben MIME-Erkennung, Header-Normalisierung und Hash-Berechnung konsistent.

## Vertragsfolgen
- Keine neue REST-API und keine Datenbankmigration.
- `api/openapi.yml` bleibt fachlich unverändert; die technische Dokumentation in `docs/references/teaching.md` wird später auf Browser-Upload + Finalize-only präzisiert.

## Tests zuerst
- Frontend:
  - gemeinsamer Browser-Upload-Helper für `intent -> PUT -> sha256`
  - Teaching-Seite bereitet Datei-Uploads clientseitig vor und submitet danach erst die Finalize-Action
  - Teaching-Server-Action lehnt rohe Datei-Posts ohne vorbereitete Metadaten mit „JavaScript erforderlich“ ab
- Backend:
  - Teaching-Upload-Intent nutzt Lazy-Rewire analog zu Learning
  - bestehende Teaching-/Learning-Upload-Intent- und Storage-Tests bleiben grün
- Integration:
  - Supabase-E2E für Teaching-Material-PDF sowie Learning-PDF/Bild
  - zusätzliche Learning-Integration für SB3 und HEX in dieser Phase ergänzen

## Implementierungsnotizen
- Der bisherige serverseitige Teaching-Upload (`uploadFileMaterial`, serverseitiges Hashing, serverseitiger PUT auf die Presign-URL) wird entfernt.
- Der Browser-Upload-Teil wird als wiederverwendbarer Frontend-Helper geschnitten, damit Learning und Teaching nicht zwei verschiedene Implementierungen derselben Technik behalten.
- Datei-Materialien setzen JavaScript voraus; Text-Material bleibt ohne JavaScript funktionsfähig.
