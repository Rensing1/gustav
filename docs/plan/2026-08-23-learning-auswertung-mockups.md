# Gestaltungsstudie: Qualitative Auswertung im bestehenden Lernraum

## Ziel

Die vorhandene lernendenseitige Auswertung wird nicht als neue Seite gedacht, sondern innerhalb des bestehenden Zwei-Spalten-Arbeitsraums weiterentwickelt. Die Studie untersucht drei Darstellungen für qualitative Kriterienbewertungen, die GUSTAVs dunkles Erscheinungsbild, harte Konturen, Punkt-Raster, Typografie und Offenlegungslogik beibehalten.

## Varianten

1. Nummerierte Kriterienzeilen mit einer festen Statusspalte.
2. Offene Kriterienblöcke als direkte Weiterentwicklung der heutigen Liste.
3. Verschachtelte Offenlegungen für lange Auswertungen mit vielen Kriterien.

Alle Varianten verwenden exemplarisch die vier Formulierungen `Stimmig`, `Weitgehend`, `In Ansätzen` und `Fehlt noch`. Sie entfernen ausschließlich in der Lernendensicht die numerischen Einzelbewertungen. Die intern gespeicherten Scores und die Lehrkraftdiagnostik sind nicht Gegenstand dieser Studie.

## Abgrenzung

- keine Änderung an Anwendungscode oder Stylesheets;
- keine Änderung am OpenAPI-Vertrag;
- keine Datenbank- oder Migrationsänderung;
- keine abschließende Produktentscheidung;
- keine automatisierten Tests, da nur statische Mockup-Bilder entstehen.

## Artefakte

- `2026-08-23-learning-auswertung-variante-1-nummerierte-zeilen.png`
- `2026-08-23-learning-auswertung-variante-2-kriterienbloecke.png`
- `2026-08-23-learning-auswertung-variante-3-offenlegungen.png`

## Vertiefung: Rückmeldung als Lernweg

Aufbauend auf Variante 3 entsteht eine zusammenhängende Bildfolge. Sie ordnet die Kriterienauswertung der formativen Rückmeldung unter und zeigt nicht nur einen statischen Zustand, sondern drei aufeinanderfolgende Schritte aus Sicht der Lernenden:

1. Die geöffnete Rückmeldung nennt eine konkrete Stärke und genau einen priorisierten nächsten Schritt.
2. „Kriterien im Detail“ erklärt die Rückmeldung mit kompakten Offenlegungszeilen; das für den nächsten Schritt relevante Kriterium ist bereits geöffnet.
3. Beim Weiterarbeiten bleibt der nächste Schritt als kompakter Hinweis oberhalb des Editors sichtbar.

Die bisher gleichrangige Offenlegung „Auswertung“ entfällt in diesen Entwürfen. „Meine Abgabe“ bleibt als eigenständige, geschlossene Offenlegung erhalten. Farbige Statusangaben werden zurückhaltend und ohne Ampellogik eingesetzt.

Zusätzliche Artefakte:

- `2026-08-23-learning-rueckmeldung-schritt-1-orientierung.png`
- `2026-08-23-learning-rueckmeldung-schritt-2-kriterien.png`
- `2026-08-23-learning-rueckmeldung-schritt-3-weiterarbeiten.png`

## Gestaltungsrunde nach dem ersten Live-Stand

Die folgenden Varianten reagieren auf den Eindruck des implementierten Live-Stands: Vertikale Akzentlinien und ineinander verschachtelte Rahmen erzeugen zu viel visuelle Unruhe. Die neue Gestaltungsrunde verwendet deshalb eine flache, redaktionelle Hierarchie aus Weißraum, Schriftgrößen und zurückhaltenden horizontalen Trennungen.

1. **Ruhiger Lernweg:** Die Rückmeldung bildet einen lesbaren Lernbrief. Ein eigener Abschnitt verbindet den priorisierten nächsten Schritt mit dem Weiterarbeiten. Kriterien und Abgabe bleiben nachgeordnet.
2. **Handlungsfokus:** Ein einzelnes, flächiges Fokusband bringt den nächsten Arbeitsschritt vor die ausführliche Rückmeldung. Diese Variante unterstützt besonders Lernende, die lange Texte nicht vollständig lesen; sie setzt jedoch einen zuverlässig abgeleiteten nächsten Schritt voraus.
3. **Redaktionelle Kriterienliste:** Die vorhandenen Daten bleiben unverändert. Vollständige Kriteriennamen, qualitative Stufen und genau eine geöffnete Begründung bilden eine flache Leseliste ohne Karten oder Statusfarben.

Neue Artefakte:

- `2026-08-23-learning-rueckmeldung-variante-1-ruhiger-lernweg.png`
- `2026-08-23-learning-rueckmeldung-variante-2-handlungsfokus.png`
- `2026-08-23-learning-rueckmeldung-variante-3-redaktionelle-kriterienliste.png`
