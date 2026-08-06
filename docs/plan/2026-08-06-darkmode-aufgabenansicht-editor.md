# Darkmode und Markdown-Editor in der Aufgabenansicht

## User Story

Als Schüler möchte ich die Aufgabenansicht und den Markdown-Editor in Hell und Dunkel als zusammengehörige Arbeitsfläche erleben, damit Text, Bedienelemente und Fokuszustände in beiden Themes gut lesbar sind und mich keine hellen Fremdflächen beim Schreiben ablenken.

## Produktentscheidung

- Die Lernraum-Kopfzeile verwendet in beiden Themes die zentralen Oberflächenfarben und keine feste Cremefarbe.
- Der Markdown-Editor bildet eine einzige zusammengehörige Eingabefläche aus Werkzeugleiste und Schreibbereich.
- Werkzeugleiste, Schreibfläche, Steuerelemente, Platzhalter, Auswahl, Links und Tabellen verwenden ausschließlich zentrale Theme-Werte.
- Bedienelemente bleiben kantig und ohne harte Aktionsschatten; aktive Formatierungen erhalten eine zurückhaltende Akzentmarkierung.
- Auf schmalen Flächen bricht die Werkzeugleiste geordnet um und erzeugt keinen horizontalen Überlauf.
- Inhalte, Editorfunktionen und Abgabeabläufe bleiben unverändert.

## BDD-Szenarien und Testzuordnung

### Kopfzeile im Darkmode

**Gegeben** ein Schüler befindet sich in einer Aufgabe im dunklen Theme, **wenn** die Lernraum-Kopfzeile angezeigt wird, **dann** verwendet sie eine dunkle Theme-Oberfläche mit lesbaren Marken- und Brotkrumentexten statt des festen hellen Hintergrunds.

- Automatisierung: Stil-Vertrag und berechnete Browserstyles in der echten Lernansicht.

### Kopfzeile im Light-Mode

**Gegeben** dieselbe Aufgabenansicht im hellen Theme, **wenn** die Kopfzeile angezeigt wird, **dann** verwendet sie die neutrale zentrale Oberfläche und keinen abweichenden Cremeton.

- Automatisierung: berechnete Browserstyles und Referenzbild der echten Lernansicht.

### Editor im Darkmode

**Gegeben** der Markdown-Editor ist im dunklen Theme geöffnet, **wenn** Werkzeugleiste, Schreibbereich und Steuerelemente gerendert werden, **dann** bleiben alle Flächen dunkel, Text und Platzhalter lesbar und es erscheint keine helle Editorinsel.

- Automatisierung: Komponentenvertrag, berechnete Browserstyles und Referenzbilder für Desktop und Smartphone.

### Editor im Light-Mode

**Gegeben** der Editor ist im hellen Theme geöffnet, **wenn** der Schüler schreibt, **dann** bilden Werkzeugleiste und Schreibbereich eine ruhige zusammenhängende Eingabefläche mit klarer Begrenzung.

- Automatisierung: Komponentenvertrag und Referenzbild der echten Lernansicht.

### Formatieren und Fokussieren

**Gegeben** der Schüler fokussiert den Editor oder aktiviert eine Formatierung, **wenn** sich der Zustand ändert, **dann** zeigen Fokusrahmen und aktive Formatierung den Zustand sichtbar, ohne eine kräftig gefüllte Aktionsfläche oder einen Schlagschatten zu erzeugen.

- Automatisierung: Markdown-Editor-Komponententest und berechneter Browserstil.

### Schmale Arbeitsfläche

**Gegeben** die Aufgabenansicht ist auf einem Smartphone geöffnet, **wenn** alle Formatierungsaktionen sichtbar sind, **dann** bricht die Werkzeugleiste innerhalb der verfügbaren Breite um und die Seite läuft nicht horizontal über.

- Automatisierung: authentifizierter `@feature-acceptance`-Rundlauf, Layoutprüfung und mobiles Referenzbild.

## Technische Abgrenzung

- OpenAPI, Datenbank, Backend und fachliche DTOs ändern sich nicht.
- Die bestehenden Theme-Werte bleiben die einzige Farbquelle.
- Produktive Regeln verbleiben in den vorhandenen CSS-Schichten; es entstehen keine komponentenlokalen Styles.
- Abschließend laufen die gezielten Komponenten- und Browserprüfungen, `make test-visual-smoke` und `make verify-feature`.
