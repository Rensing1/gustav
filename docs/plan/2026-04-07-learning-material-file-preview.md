# Lehrmaterial-Dateivorschau im Lernraum

## Ziel
- Die Bild-/Dateivorschau aus der Schüler-Abgabe soll auch für vom Lehrer hochgeladenes Material genutzt werden.

## Geplanter Umfang
- `LearningMaterial` im Lernraum erhält eine kurzlebige `file_url` für freigegebenes Datei-Material.
- Die Lernraum-API reichert lineare und modulare Materialantworten mit dieser URL an.
- Die Schüler-UI zeigt:
  - Bilder inline
  - PDFs inline
  - andere Dateien als Link `Datei öffnen`

## Leitplanken
- Keine Persistenzänderung und keine Schema-Migration.
- Keine Storage-Keys im Student-Response.
- Kurzlebige Download-URLs nur für tatsächlich sichtbares Material.

## Verifikation
- API-Contract-Tests für lineare und modulare Lernmaterialien.
- Komponententests für `LearningMaterialCard`.
- `npm run check` und Container-Neubau für Frontend/Web.
