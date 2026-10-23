# README-Galerie an die aktuelle Oberfläche anpassen

## Auftrag und Umfang

Die sechs Produktbilder im README zeigen noch das frühere Design. Als interessierter Leser möchte ich die aktuelle Oberfläche anhand realer, verständlicher Ansichten mit ausschließlich synthetischen Beispieldaten kennenlernen.

## Vorgehen und Prüfnachweise

1. Bestehende Bildverweise und lokale HTTPS-Vertrauensstellung prüfen.
2. Die vorhandenen dedizierten Browser-Personas verwenden und die sechs Ansichten neu aufnehmen: Kursübersicht, modularer Editor, Einladungsdialog, Aufgabenarbeitsplatz, formative Rückmeldung und Übungsauswahl. Keine vorhandenen Lernstände zurücksetzen; keine aktiven Einladungstoken veröffentlichen.
3. Alle Bilder visuell auf aktuelle Gestaltung, passende Ausschnitte, Lesbarkeit und ausschließlich öffentliche Beispieldaten prüfen. Die vorhandenen Bildpfade beibehalten und den Aufnahmezeitpunkt im README nennen.
4. Bildverweise, JPEG-Dateien und Änderungen prüfen sowie `make verify` ausführen. Anschließend lokal auf `master` committen; kein Push.

Es werden ausschließlich Dokumentation und Bilddateien geändert. Produktabläufe, API-Vertrag, Datenbankschema und Browser-Kompatibilität einschließlich iPadOS 15.3.1 bleiben unverändert. Deshalb ist kein neues Feature-Abnahmeszenario nötig. Die authentifizierte Aufnahme erfolgt über den echten lokalen Stack mit regulärer Zertifikatsprüfung; die sechs Bilder werden zusätzlich einzeln visuell geprüft.

## Ausgangsprüfung

- Arbeitsbaum sauber; Ausgangsstand `aeeef48c`.
- Alle sechs Bildverweise auf `docs/assets/readme/*.jpg` vorhanden; vorherige Aufnahmen vom September 2026 zeigen die frühere Gestaltung.
- `make local-ca-status`: aktuelle Caddy-CA in System, Chromium/Codex und Firefox vertraut.
- Vorhandene Dev-Landschaft vollständig; kein Reset erforderlich.

## Umsetzung und Bildprüfung

- Alle sechs JPEGs unter den bisherigen Pfaden neu aufgenommen: Chromium, 1440 × 900 Pixel, deutsche Oberfläche, Light Mode, echter Login und lokaler Produktiv-Stack. Auf das Laden von Schriften und gespeicherten Rückmeldungen gewartet.
- Kurskatalog und vollständiger modularer Graph zeigen die aktuelle Navigation und Gestaltung. Der Aufgabenarbeitsplatz zeigt Materialnavigation und einen ausschließlich im temporären Browser-Kontext erstellten Beispielentwurf; dafür wurde keine neue Abgabe abgeschickt.
- Die bestehende synthetische Einstiegsabgabe liefert die formative Rückmeldung. Die Übungsauswahl zeigt beide vorhandenen Übungsmodule, ohne eine Sitzung zu starten oder den Lernstand zu verändern.
- Für den Einladungsdialog einen Demo-Link erzeugt, aufgenommen und unmittelbar danach über die Oberfläche widerrufen. Das erneute Erscheinen von „Klassenlink erstellen“ bestätigt den Widerruf. Keine E-Mails versandt.
- Alle sechs finalen Bilder einzeln visuell geprüft: vollständig geladene Inhalte, passende Ansichten, einheitliche Abmessungen und keine personenbezogenen Daten. Die Rückmeldung ist bewusst im gescrollten Aufgabenbereich geöffnet.
- Alle sieben README-Bildverweise einschließlich Logo gültig; JPEG-Format, Abmessungen und fehlende EXIF-Metadaten geprüft. Die Galerie umfasst zusammen 514.534 Bytes. Aufnahmezeitpunkt und widerrufener Demo-Link sind im README-Kommentar festgehalten.
- Die tatsächliche README-Tabelle zusätzlich lokal im Browser gerendert: Alle sechs Bilder laden gemeinsam und besitzen dieselben Abmessungen; die vollständige Galerie visuell geprüft.
- `git diff --check` erfolgreich. `make verify` erfolgreich: 3192 Backend-Tests bestanden, 36 übersprungen, zwei bereits bekannte Storage-URI-Warnungen; 879 Frontend-Tests in 177 Dateien, elf Build-/CSS-Prüfungen und 80 H5P-Tests bestanden. Svelte-Prüfung ohne Fehler oder Warnungen; Produktions-Build erfolgreich.
- Der Learning-Worker wurde nur während der Repository-Prüfung angehalten und danach wieder gestartet. Keine Produkt-, API-, Schema- oder Kompatibilitätsänderungen. Lokaler Dokumentationscommit; kein Push.
