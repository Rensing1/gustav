# H5P Public Runtime Assets Fix

## Zusammenfassung
- Der H5P-Editor zeigte nur die GUSTAV-Hülle, aber keine eigentliche Editor-Oberfläche.
- Ursache: statische H5P-Runtime-Assets lagen im Node-Sidecar hinter `requireAuth`.
- Betroffen sind insbesondere `/h5p/webcomponents/*`, `/h5p/webcomponents/vendor/*` und `/h5p/theme/*`.

## Umsetzung
- Öffentliche statische H5P-Assets im `h5p-service` vor die Auth-Middleware verschieben.
- Inhalts- und nutzerbezogene H5P-Endpunkte weiter fail-closed hinter `requireAuth` lassen.
- Contract-Test ergänzen, der die Middleware-Reihenfolge für Assets vs. Modell-Endpunkte absichert.

## Verifikation
- Browser-Assets `GET /h5p/webcomponents/index.js` und `GET /h5p/theme/h5p-gustav.css` liefern ohne Session `200`.
- Geschützte Modell-Endpunkte wie `GET /h5p/editor/model` bleiben ohne Session `401`.
- Der H5P-Editor erscheint wieder sichtbar im Teaching-Workspace.
