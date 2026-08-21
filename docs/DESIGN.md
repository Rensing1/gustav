# DESIGN.md

## Status

Dieses Dokument ist der verbindliche Designvertrag für die Svelte-Oberfläche
von GUSTAV. Es ersetzt `docs/UI-UX-Leitfaden.md` fachlich vollständig. Die
Preview-Route unter `/ui-lab` dient als visuelle Referenzfläche; Stitch-Projekt
`7234666190356643774` ist die kanonische visuelle Quelle für diese Fassung.

Primäre Stitch-Referenzen sind die Task- und Graph-Referenzflächen sowie das
Designsystem `Gustav Logic` im oben genannten Projekt.

## 1. Produktbild

GUSTAV folgt einer präzisen, kontrastreichen und technisch-scharfen
Produktsprache. Es ist kein
freundlich-rundes EdTech-Produkt und keine warme Editorial-Oberfläche mehr.

Verbindliche Zielwahrnehmung:

- Präzision
- Klarheit
- Eigenständigkeit

Verbindliche Negativrichtung:

- nicht weichgespült
- nicht generisch-SaaS
- nicht verspielt

Der Primäranker ist die Aufgabenfläche. Der Graph übernimmt dieselbe Sprache,
ordnet sich aber der Task-Fläche gestalterisch unter.

## 2. Rollen und Grundhaltung

GUSTAV optimiert weiterhin im Zweifel zuerst für Lernende. Lehrkraftflächen
teilen jedoch dieselbe harte Formensprache und denselben Kontrast.

Verbindliche Regeln:

- Schüler- und Lehrkraftflächen wirken wie ein Produkt.
- Unterschiede entstehen über Dichte, Werkzeuge und Kontext, nicht über
  verschiedene Designwelten.
- Die noch nicht freigegebene `Diagnostik` bleibt aus der Hauptnavigation
  verborgen. Direkte Entwicklungsansichten folgen dennoch derselben
  Formensprache wie die produktiven Lehrkraftflächen.

## 3. Shell

### 3.1 Grundstruktur

Die Produktoberfläche folgt dieser Reihenfolge:

1. `TopBar`
2. `Workspace`
3. `Dialog`, `Popover` oder `InlineEdit`

Zusätzliche globale Navigationsleisten sind nicht erlaubt.

### 3.2 Top-Bar

Die Top-Bar ist technisch-präzise und kontrastreich.

Regeln:

- klare Objektkanten statt weicher Flächen
- aktiver Navigationszustand bleibt typografisch markiert
- Primärnavigation ist textbasiert
- Marke darf präsenter sein als zuvor
- Meta und Steuerung nutzen technische Kleinformate

### 3.3 Breadcrumbs

Für Lernende bleiben Breadcrumbs ein Primärelement.

Regeln:

- Schülerpfad bleibt `Lernraum -> Kurs -> Lerneinheit`
- Breadcrumbs sitzen im Lernfluss in der Top-Bar
- Breadcrumbs sind klein, technisch und klar lesbar
- Breadcrumbs enthalten keine Aktionen

### 3.4 Seitenkopf

Viele Seiten beginnen weiterhin direkt mit der Arbeit.

Regeln:

- kein Hero-Pattern
- Primäraktionen sitzen im Seitenkopf
- Sekundäraktionen bleiben sichtbar, aber schwächer
- Seitenkopf nutzt klare Kante und kompakte Meta-Zeile

### 3.5 Arbeitsbreiten

Workspace-Seiten folgen einer klaren Seitenachse. Zentrierung wird nicht über
viewport-relative Sonderrechnungen gelöst.

Regeln:

- jede Seite hat genau eine zentrierte Layoutachse
- unterschiedliche Inhaltsbreiten werden über innere Container mit
  `max-width` und `margin-inline: auto` gesteuert
- `100vw`, `50vw` oder ähnliche Breakout-Formeln sind für reguläre
  Workspace-Flächen nicht erlaubt
- wenn eine Seite zwei Breiten benötigt, dann als klar benannte Bereiche, nicht
  als lokale CSS-Hacks

Spezialfall `/live`:

- der Auswahl- und KPI-Bereich bleibt kompakter
- der Arbeitsbereich aus Tabelle und Detailpanel ist breiter, aber bleibt auf
  derselben Mittelachse zentriert
- der breite Arbeitsbereich darf auf großen Displays spürbar großzügiger sein
  als Standard-Workspace-Flächen
- Tabelle und Detailpanel sind getrennte Objekte, kein gemeinsamer Außenrahmen

## 4. Light und Dark

Light und Dark bleiben gleichrangig.

Regeln:

- beide Modi teilen exakt dieselbe Kompositionslogik
- Light ist off-white, dunkel konturiert und orange akzentuiert
- Dark ist tief, kontrastreich und technisch, nicht weich getönt
- neue Komponenten ohne definierte Dark-Regeln sind unvollständig

## 5. Farbe

Die Startpalette orientiert sich am Stitch-Designsystem `Gustav Logic`.

### 5.1 Light

- `--color-bg-base`: `#f9f9f9`
- `--color-bg-surface`: `#ffffff`
- `--color-bg-muted`: `#f3f3f4`
- `--color-bg-soft`: `rgba(255, 81, 47, 0.08)`
- `--color-text`: `#1a1c1c`
- `--color-text-muted`: `#5c5c5c`
- `--color-link`: `#b41f00`
- `--color-link-hover`: `#da3717`
- `--color-accent`: `#ff512f`
- `--color-accent-soft`: `rgba(255, 81, 47, 0.14)`
- `--color-border`: `#1b1b1b`
- `--color-line`: `rgba(27, 27, 27, 0.14)`
- `--color-success`: `#387f50`
- `--color-success-soft`: `rgba(56, 127, 80, 0.14)`
- `--color-warning`: `#8d5a00`
- `--color-warning-soft`: `rgba(141, 90, 0, 0.14)`
- `--color-danger`: `#ba1a1a`
- `--color-danger-soft`: `rgba(186, 26, 26, 0.14)`

### 5.2 Dark

- `--color-bg-base`: `#121212`
- `--color-bg-surface`: `#1a1a1a`
- `--color-bg-muted`: `#1d1d1d`
- `--color-bg-soft`: `rgba(255, 81, 47, 0.10)`
- `--color-text`: `#f0f1f1`
- `--color-text-muted`: `#c6c6c6`
- `--color-link`: `#ff866b`
- `--color-link-hover`: `#ffb4a4`
- `--color-accent`: `#ff512f`
- `--color-accent-soft`: `rgba(255, 81, 47, 0.20)`
- `--color-border`: `#f0f1f1`
- `--color-line`: `rgba(240, 241, 241, 0.18)`

### 5.3 Farbnutzung

- Orange markiert aktive Lernmomente und primäre Aktionen.
- Grün markiert Systemlogik, AI oder Erfolg.
- Linien und Rahmen bleiben monochrom, Akzente gezielt.
- Es gibt keine zonenspezifischen Farbwelten für Rollen.

## 6. Typografie

Konkrete Implementierungen dürfen leicht variieren, die Rollen sind
verbindlich.

Rollen:

- `Display Sans`
  - technisch, breit, präzise
  - für Titel, Phasenüberschriften und starke Einstiegsmomente
- `Reading Sans`
  - hoch lesbar und neutraler für längere Inhalte
- `Technical Mono`
  - für Kicker, Meta, Labels, Status, Breadcrumbs und Werkzeuge

Regeln:

- keine Serif als Leitmotiv
- Meta-Texte bevorzugt in Monospace/Technical-Sprache
- Headlines sind kompakt, kontrastreich und enger gesetzt
- UI-Labels dürfen häufiger uppercase erscheinen als bisher

## 7. Form, Raum und Bewegung

### 7.1 Spacing

Die bestehende Spacing-Skala bleibt erhalten:

- `--space-1`: `0.25rem`
- `--space-2`: `0.5rem`
- `--space-3`: `0.75rem`
- `--space-4`: `1rem`
- `--space-5`: `1.5rem`
- `--space-6`: `2rem`
- `--space-7`: `3rem`
- `--space-8`: `4rem`

### 7.2 Radius

Radien sind praktisch deaktiviert:

- `--radius-s`: `0`
- `--radius-m`: `0`
- `--radius-l`: `2px`
- `--radius-xl`: `4px`

Default-Regel:

- neue Komponenten starten mit `0px`
- Abweichungen brauchen Begründung

### 7.3 Flächen

- Interactive Objects erhalten klare Rahmen
- große Flächen bleiben ruhig und hell
- Tiefe entsteht primär über Kontrast und harte Schatten
- Standard-Schatten folgen dem Objektprinzip, nicht dem SaaS-Prinzip

### 7.4 Motion

- Motion bleibt subtil
- Hover und Fokus dürfen deutlicher und technischer reagieren
- kleine Translate-/Shadow-Verschiebungen sind erlaubt

## 8. UI-Sprache

Die UI-Sprache bleibt kurz, sachlich und direkt.

Zusätzliche Regeln:

- technisch-präzise statt pädagogisch-begleitend
- Actions eher knapp und objektartig
- Status- und Metatexte dürfen technischer klingen
- `accent` für Primäraktionen
- `quiet` für normale Sekundäraktionen
- `subtle` für kleine, nicht-dominante Nebenaktionen wie `Pausieren`,
  `Schließen` oder `Bearbeiten` in dichten UI-Kontexten

## 9. Accessibility

Accessibility ist Teil des Designvertrags.

Regeln:

- hohe Kontraste in Light und Dark
- klare Fokuszustände
- vollständige Tastaturbedienbarkeit
- semantische Struktur bleibt trotz technischer Stilrichtung erhalten

### 9.1 Meldungen und Validierungsfehler

Aktionsmeldungen verwenden ausschließlich die gemeinsamen Komponenten `StatusMessage` und `FieldError`. `StatusMessage` ist eine kompakte Karte mit Symbol, Überschrift, optionaler Beschreibung und optionaler Wiederherstellungsaktion. Farbe unterstützt die Bedeutung, ersetzt aber weder Symbol noch Text.

- Neue Aktionsfehler werden als `alert` angekündigt, bleiben bis zur Behebung oder zum Schließen sichtbar und führen den Fokus zum ersten ungültigen Feld oder zur Meldung.
- Erfolg und laufende Vorgänge werden höflich als `status` angekündigt und stehlen keinen Fokus. Erfolg verschwindet nach sechs sichtbaren Sekunden; die Frist pausiert bei verborgenem Dokument, Hover und Fokus innerhalb der Meldung.
- Laufende Vorgänge bleiben an ihren Fachzustand gebunden. Es gibt weder künstliche Prozentwerte noch einen unabhängigen globalen Meldungsspeicher.
- Statische Hinweise besitzen keine Live-Region. Toasts bleiben folgenlosen Bestätigungen wie „Link kopiert“ vorbehalten.
- Feldfehler stehen unmittelbar am Feld, sind über `aria-describedby` verbunden und ergänzen eine zusammenfassende Aktionsmeldung oberhalb des Formulars.
- Bewegung wird bei `prefers-reduced-motion` abgeschaltet; semantische Meldungsfarben sind für Hell- und Dunkelmodus definiert.

## 10. Komponentenfamilien der ersten Welle

Die bestehende Komponentenarchitektur bleibt erhalten.

Verbindliche Familien:

- `AppShell`
- `TopBar`
- `BreadcrumbBar`
- `PageActionHead`
- `ModeSwitch`
- `ChoiceSwitch`
- `QuietList`
- `QuietListEntry`
- `AuthFrame`
- `TeacherGraphCommandBar`
- `GraphPhaseBand`
- `GraphModuleNode`
- `LearningDialogWorkspace`
- `LearningResponseGroup`

### Lehrenden-Arbeitsstarter

`/teaching` ist keine Navigations- oder Kennzahlenübersicht. Die Seite zeigt
zwei gleichwertige Arbeitsflächen: `Unterrichten` mit einer bewusst leeren
Kurs-/Lerneinheiten-Auswahl und `Vorbereiten` mit höchstens drei zuletzt
bearbeiteten Lerneinheiten. `PageActionHead` stellt den einzigen Seitenkopf;
`QuietList` und `QuietListEntry` bilden die flachen Authoring-Zeilen.

Der Kurskatalog verwendet dieselbe knappe Kopf- und Aktionshierarchie. Unter
`PageActionHead` folgen Statusumschalter und Filter, anschließend flache
Kurszeilen. Aktive Kurse und das nach Schuljahren gruppierte Archiv verwenden
dieselbe Zeilenstruktur; mobile Ansichten stapeln nur deren innere Informationen.
Archivierte Kursseiten bleiben strukturell identisch, kennzeichnen aber den
schreibgeschützten Zustand und blenden fachliche Mutationen aus.

Kurs- und Lerneinheitenkatalog verwenden gemeinsam `.teacher-catalog`: Beide
richten sich an der 80-rem-Inhaltsbreite der Kopfzeile aus und teilen
Werkzeugleisten-, Spaltenkopf- und Zeilenrhythmus. Fachlich unterschiedliche
Spalten werden nur über `--teacher-catalog-columns` beschrieben. Eigene
Maximalbreiten oder unabhängige Tabellenabstände in einzelnen Katalogen sind
nicht zulässig.

Die Kurs-Detailseite setzt diese 80-rem-Achse als flache
`.teacher-course-workspace` fort. `PageActionHead` enthält genau einen
Rücksprung zu `Kurse` und keine konkurrierende Kopfaktion. Danach folgen Lerneinheiten,
Mitglieder und Kurseinstellungen als drei durch Linien getrennte Bereiche ohne
Außenkarten oder Sidecar. Die Lerneinheitenliste ist der einzige ausführliche
Arbeitsbereich; Mitglieder und Einstellungen bleiben knappe Verwaltungszeilen
und öffnen ihre vorhandenen Drawer. Unvollständige Stammdaten werden einmalig
in einer schmalen Statuszeile benannt. Archivierte Kurse behalten dieselbe
Struktur, bieten aber keine fachlichen Mutationen an.

Lehrkraft-Drawer verwenden den gemeinsamen `WorkspaceDrawer`. Sie lassen sich
über die sichtbare Schließen-Aktion, mit `Escape` oder durch einen Klick auf die
abgedunkelte Außenfläche schließen. Interaktionen innerhalb des Drawers dürfen
ihn nicht schließen. Liegt ein weiterer modaler Dialog darüber, reagiert der
darunterliegende Drawer nicht auf `Escape`.

Das persönliche Lernarchiv der Schüler ist eine lineare Belegliste. Es zeigt
ausschließlich eigene Abgaben und Rückmeldungen; Kursmaterialien, Teilnehmerlisten
und fremde Leistungen werden dort weder angedeutet noch nachgeladen.

Ab `64rem` stehen beide Flächen nebeneinander und werden ausschließlich durch
eine vertikale Linie getrennt. Darunter werden sie in derselben Reihenfolge
gestapelt und durch eine horizontale Linie getrennt. Außenkarten,
verschachtelte Rahmen, Kennzahlen und wiederholte Hauptnavigation sind für
diese Seite nicht vorgesehen. Alle Zustände verwenden die zentralen Theme-,
Fokus- und Kontrastwerte.

`ModeSwitch` verbindet Navigationsziele und markiert die aktuell geöffnete Ansicht. `ChoiceSwitch` bildet dagegen eine lokale, gegenseitig ausschließende Auswahl mit nativen Radiofeldern ab. Seine aktive Option bleibt transparent und wird nur durch kräftigeren Text sowie eine zurückhaltende Akzentlinie markiert. Gefüllte Signalfarben, Schatten und Pillenformen sind für diese Auswahl nicht vorgesehen.

### Lerneinheiten-Editor

Bei modularen Lerneinheiten bleibt der Graph der dauerhafte Arbeitskontext.
Phasen und Module werden über genau eine kontextuelle Seitenleiste angelegt und
bearbeitet; Werkzeugleisten-Popover und Editoren direkt am Knoten sind nicht
zulässig. Die gesamte 112-rem-Arbeitsbreite steht dem Graphen zur Verfügung.
Ein Klick auf eine Phase oder ein Modul wählt nur aus. Eine flache Kontextleiste
nennt Titel, reale Bestandszahlen und die nächsten Aktionen; erst
`Eigenschaften` öffnet das Formular. Nach dem Anlegen bleibt das neue Element
ausgewählt, fokussiert und bewusst zur weiteren Bearbeitung geöffnet. Der
Modulinhaltseditor führt mit `Zurück zum Graph` wieder zum markierten Modul,
öffnet dessen Eigenschaften aber nicht ungefragt.

Die Eigenschaftenseitenleiste liegt auf Desktop und Tablet über dem rechten
Graphbereich und darf die gemessene Graphbreite nicht verändern. Auswahl,
Öffnen, Schließen und Speichern erhalten den aktuellen Ausschnitt. Der erste
Aufruf fokussiert die ausgewählte oder erste Phase mit lesbarer Vergrößerung;
`Gesamtansicht` und `Auswahl fokussieren` bleiben getrennte, bewusste Aktionen.
Auswahl und Seitenleistenmodus werden als getrennte URL-Zustände in einem
gemeinsamen Navigationsschritt aktualisiert. Damit stellt die Browsernavigation
beides eindeutig wieder her.

Der Modulinhaltseditor selbst ist eine flache Inhaltsarbeitsfläche. Ab `64rem`
Komponentenbreite stehen links eine etwa 22rem breite Inhaltsübersicht und
rechts genau ein Bearbeitungskontext. Materialien und Aufgaben bilden getrennte
Listen mit eigener Reihenfolge; eine schmale Akzentkante markiert die einzige
Auswahl. Außenkarten, gleichzeitig geöffnete Formulare und ein zweiter
Eigenschafteneditor sind nicht zulässig. Ohne Auswahl zeigt die rechte Fläche
einen ruhigen Überblick.

Unter `64rem` wird daraus der gestufte Ablauf `Inhalte → Bearbeiten`; die
zurückliegende Stufe bleibt montiert und Entwürfe bleiben erhalten. Formwerte
werden pro Lehrkraft, Lerneinheit, Modul und Ziel nur im aktuellen Browsertab
gesichert. Beim Öffnen eines bestehenden Inhalts wird sein fachlicher
Ausgangszustand festgehalten. Erst eine davon abweichende Fassung gilt als
Entwurf; bloßes Öffnen und Zurückgehen erzeugt keinen Entwurf, und eine exakte
Rückkehr zum Ausgangszustand entfernt ihn wieder. Dateiobjekte werden nie lokal
gespeichert. Markdown-Materialien und Aufgabenstellungen verwenden denselben
zentralen Editor wie Lernendenantworten.
Kriterien beginnen mit einem Eintrag und können bis höchstens zehn ergänzt und
sortiert werden. Material- und Aufgabenlöschungen benötigen einen modalen
Bestätigungsdialog.

Auf schmalen Ansichten belegt die Seitenleiste die verfügbare Breite, ohne den
Graphen zu demontieren. `Escape`, die Schließen-Aktion und ein Klick auf die
freie Graphfläche schließen sie und geben den Fokus an den Auslöser zurück.
Interne Implementierungsbegriffe werden nicht als sichtbare Beschriftungen
verwendet.

Das Löschen einer Phase oder eines Moduls verlangt immer einen modalen
Bestätigungsdialog. Er nennt Titel sowie die Zahl betroffener Module,
Materialien, Aufgaben und Verbindungen. `Abbrechen` ist die sichere
Standardaktion; die destruktive Aktion benennt ausdrücklich, dass auch Inhalte
gelöscht werden. Derselbe Dialog wird im Graphen und im Modulinhaltseditor
verwendet. Fehler lassen Dialog und Graphzustand unverändert sichtbar.

## 11. Lernraum und Lerneinheit

### 11.1 Lernweg und URL

- Der Lernraum folgt der Hierarchie `Lernpfad → Module lesen → Aufgabe bearbeiten`.
- Modulare Lerneinheiten beginnen im Lernpfad; lineare Lerneinheiten beginnen
  ohne künstliche Graphstufe in der Leseansicht.
- Es gibt keine gleichrangigen Umschalter `Übersicht | Inhalte`. Ein Modulaufruf
  wechselt aus dem Lernpfad in die Leseansicht, `Aufgabe beginnen` von dort in
  den eigenen Aufgabenraum.
- Die kanonische URL verwendet `module` und `task`. Ein bestehender Link mit
  `panel=result` bleibt kompatibel, öffnet aber denselben Aufgabenraum und dort
  die Offenlegung `Meine Abgabe`. Browser-Zurück und sichtbare Rückwege
  durchlaufen dieselben Stufen. Alte `view`- und `history`-Links werden sicher
  normalisiert.
- Die URL bestimmt nach einem Neuladen die sichtbare Stufe. Schülerbezogene
  lokale Speicherung ergänzt nur geöffnete Module, Lesepositionen, Kontext und
  Entwürfe.

### 11.2 Lernpfad

- Graph bleibt Phasen-zentriert
- Knoten sind harte, klar gerahmte Objekte
- aktiver Status ist orange
- gesperrte Zustände sind reduziert und monochrom
- bereits geöffnete Module sind erkennbar markiert
- ein Modul wird höchstens einmal geöffnet und in der Leseansicht nach seiner
  didaktischen Graph- und Phasenposition eingeordnet

### 11.3 Leseansicht und Inhalte

- Die Aufgabenbearbeitung ist ein eigener Fokusraum und nicht mehr Teil einer
  symmetrischen Zwei-Pane-Ansicht.
- `← Zum Lernpfad` ist der eindeutige Rückweg. Das Inhaltsverzeichnis navigiert
  ausschließlich innerhalb der geöffneten Module. Ab `64rem` ist es links
  sticky, darunter eine kompakte Aufklappleiste oberhalb des Inhalts.
- Kopfzeile, Toolbar und Lernraum verwenden dasselbe zentrale Raster von
  höchstens `80rem`. Vollbreiten-Ausbrüche des Lernraums sind nicht zulässig.
- Der Modultitel ist der klare Einstiegspunkt eines Moduls
- `MATERIALIEN` und `AUFGABEN` bleiben technische Marker, keine konkurrierenden
  Subheadlines
- Zwei Zeilen für lange Modultitel sind erlaubt; der Modulkopf wächst nicht
  beliebig
- Der Abstand vom Modulkopf zum ersten Abschnitt ist größer als der Abstand vom
  Abschnittslabel zu seinem Block
- Rückmeldung, Auswertung und die zugehörige Abgabe erscheinen als kantige,
  technische Disclosure-Familie, niemals als Pill- oder Tabnavigation
- kompakte Task-Zeilen im modularen Lernraum nutzen eine Vorschauzeile statt
  redundanter Status-/Titellabels. Die Vorschau wird lesbar aus der
  Markdown-Aufgabenstellung abgeleitet.
- Lange oder mehrteilige Aufgaben dürfen in dieser Vorschau höchstens zwei
  Zeilen belegen und erhalten den sichtbaren Hinweis `Weitere Angaben in der
  Aufgabe`. Unter `48rem` steht die Startaktion darunter und nimmt die
  verfügbare Breite ein.
- Status wird primär über Balken und Tönung getragen
- Die vollständige Aufgabenstellung erscheint in der aktiven Detailansicht inline.
  In der kompakten Ansicht bleibt sie für native Text-/Dateiaufgaben, H5P und
  KI-Dialoge direkt bei der Bearbeitung sichtbar. In der zweispaltigen Ansicht
  wird sie nicht dupliziert, weil `Aufgabe & Kontext` sie bereits vollständig
  zeigt.
- Text-, Bild- und PDF-Materialien sind beim ersten Lesen geöffnet. Die gesamte
  linksbündige Titelzeile klappt ein Material zugänglich ein oder aus und zeigt
  `aria-expanded` sowie `aria-controls` an.
- Materialtext beginnt auf derselben linken Achse und bleibt bei ungefähr
  `68ch`. Bilder und PDF-Vorschauen laden verzögert, besitzen eine begrenzte
  Vorschauhöhe und bieten eine Aktion zum separaten Öffnen.
- Auf breiten Flächen gibt es genau zwei funktionale Bereiche: links `Aufgabe &
  Kontext`, rechts die Bearbeitung. Es gibt niemals eine dritte Spalte.
- Ab `60rem` verfügbarer Komponentenbreite ist die Buchseite
  `clamp(32rem, 44cqw, 38rem)` breit. Darunter wechseln `Aufgabe` und
  `Materialien` als montiert bleibende Vollbreitenansichten; unter `48rem`
  werden Aktionsgruppen gestapelt. Ein übliches iPad mit 1024 CSS-Pixeln im
  Querformat nutzt damit die zweispaltige Ansicht, im Hochformat bleibt die
  kompakte Ansicht erhalten.
- Breiten und Abstände werden responsiv bestimmt. Nutzereinstellungen bieten
  nur Navigation, `Klein | Standard | Groß` und das Zurücksetzen der
  Darstellung.
- Markdown im Schüler-Lernraum wird zentral über einen sanitizten GFM-Renderer
  ausgegeben
- Unterstützt werden mindestens: Überschriften, Fett, Kursiv, Listen,
  nummerierte Listen, Links, Tabellen, `<br>`
- Die Lernraum-Kopfzeile verwendet in beiden Themes die neutralen zentralen Oberflächenfarben. Der Markdown-Editor bildet aus Werkzeugleiste und Schreibbereich eine einzige gerahmte Eingabefläche; feste helle Sonderfarben, Aktionsschatten und voneinander abgesetzte Editorboxen sind nicht zulässig.
- Editorwerkzeuge brechen auf schmalen Komponentenbreiten geordnet um. Aktive Formatierungen werden durch eine dünne Akzentkante gekennzeichnet; Fokus, Platzhalter, Auswahl, Links und Tabellen müssen in Light und Dark lesbar bleiben.
- Lernraum-spezifische Overrides unter `.learning-unit-content-shell` gehören in
  das aktive Lernraum-CSS-Bundle (`frontend/src/lib/styles/learning-unit.css`
  plus gemeinsame Primitives), nicht zurück in `frontend/src/lib/styles/design-system.css`,
  nicht nur in `app.css`, damit Surface-, Spacing- und Typografie-Regeln im
  Lernraum wirksam bleiben

### 11.4 Aufgabe und Kontext

- Ein sticky Aufgabenkopf zeigt `← Zurück zu Modul …`, Aufgabenbezeichnung und
  Status. Dieser Rückweg stellt Scroll- und Fokusposition wieder her. Eine
  endgültige Abgabe verbleibt als Ergebnis im Aufgabenraum.
- Der Aufgabenraum bleibt flach: keine Modulkarte, keine wiederholte
  Aufgabenzeile und keine vollständigen Rahmen um Kontext oder Bearbeitung.
- Beim Wechsel zum Lernpfad endet der temporäre Aufgabenraum. Der Modulgraph
  zeigt keine tab-lokale Aufgabenmeldung und keinen direkten Rücksprung, weil
  dort weder Verfügbarkeit noch Abgabestatus zuverlässig bestimmt werden.
  Ein tab-lokaler Textentwurf ist an lernende Person, Kurs und Aufgabe gebunden.
  Beim Aufgabenwechsel wird ausschließlich der Entwurf genau dieser Aufgabe
  geladen; Antworten anderer Aufgaben dürfen niemals erscheinen. Nach einer
  endgültigen Abgabe wird nur der Entwurf dieser Aufgabe entfernt. Ein neuer
  Versuch beginnt ausschließlich über `Erneut bearbeiten`.
- `Aufgabe beginnen`, `Entwurf weiterbearbeiten` und `Erneut bearbeiten`
  öffnen denselben Text- oder Datei-Arbeitsbereich. Ein tab-lokaler Textentwurf
  hat beim Wiedereinstieg Vorrang; andernfalls wird der Text der neuesten
  Abgabe geladen. Eine vorhandene Datei erscheint als Vorschau mit Metadaten
  und der Aktion `Andere Datei auswählen`; ein natives Dateifeld wird niemals
  vorbefüllt.
- Oberhalb der Bearbeitung steht in fester Reihenfolge die bedingte
  Disclosure-Familie `Rückmeldung`, `Auswertung`, `Meine Abgabe`.
  `Rückmeldung` setzt `feedback_md`, `Auswertung` mindestens ein tatsächliches
  Kriterienergebnis voraus. Leere Bereiche und Platzhalter werden nicht
  gerendert. `Meine Abgabe` zeigt unverändert den Snapshot, auf den sich die
  Hinweise beziehen.
- `Rückmeldung einholen` wechselt nicht auf eine andere Seite. Während der
  Verarbeitung sind Editor, Antwortform, Dateiauswahl und Abgabeaktionen
  gesperrt. Sowohl `Rückmeldung einholen` als auch `Endgültig abgeben` zeigen
  unmittelbar einen sichtbaren Verarbeitungsstatus und verhindern weitere
  Abgabeversuche. Erfolg bleibt in der Aufgabenfläche erkennbar; bereinigte
  Fehler erscheinen dort mit einer möglichen nächsten Aktion. Nach
  erfolgreicher Verarbeitung öffnet sich `Rückmeldung` inline, ohne den
  Tastaturfokus ungefragt zu verschieben. Beim späteren Wiedereinstieg bleiben
  alle Offenlegungen zunächst geschlossen.
- Weicht die sichtbare Fassung vom zuletzt rückgemeldeten Snapshot ab, bleibt
  die bisherige Rückmeldung lesbar, aber `Endgültig abgeben` ist mit dem Hinweis
  `Für diese Fassung zuerst Rückmeldung einholen.` deaktiviert. Nach der
  Finalisierung bleibt der Aufgabenraum sichtbar und wird schreibgeschützt; ein
  erlaubter weiterer Versuch öffnet ihn erneut zur Bearbeitung.

- Die linke Fläche funktioniert als fortlaufende Buchseite. Sie zeigt bei
  modularen Lerneinheiten ausschließlich Module, die der Schüler zuvor im
  Lernpfad geöffnet hat. Das Modul der aktiven Aufgabe steht zuerst und bleibt
  geöffnet; weitere Module folgen in Lernpfad-Reihenfolge und beginnen
  eingeklappt.
- Der Materialbereich besitzt keine eigene Quellenverwaltung. Weitere Inhalte
  werden ausschließlich über `Zum Lernpfad` geöffnet. Währenddessen bleibt die
  Aufgabenarbeitsfläche montiert und wird nur für Tastatur und Screenreader
  verborgen. Die Auswahl eines Moduls führt direkt zur Aufgabe zurück.
- Beim ersten Öffnen eines Moduls ist dessen erstes Material geöffnet. Danach
  dürfen mehrere Dokumente gleichzeitig vollständig im gemeinsamen
  Materialscrollbereich geöffnet bleiben. Wiederholte Typ- und Herkunftsmarker
  in jeder Dokumentzeile sind zu vermeiden.
- Der Materialbereich visualisiert seine Hierarchie als flachen Baum statt als
  Sammlung verschachtelter Karten: Module bilden die oberste Ebene,
  Materialien und die Untergruppe `Eigene Abgaben` die zweite und einzelne
  Abgaben die dritte. Dünne Verbindungslinien und eine maßvolle Einrückung
  tragen die Hierarchie; zusätzliche Flächen, Rahmen und Herkunftslabels sind
  dafür nicht zulässig.
- Offenlegungschevrons stehen links vor dem Titel und drehen sich im geöffneten
  Zustand. Rechts stehen ausschließlich Aktionen, die zur jeweiligen Ebene
  gehören: `Groß lesen` an Dokumenten und `Modul schließen` an zusätzlichen
  Modulen. `Eigene Abgaben` besitzt keine konkurrierende Nebenaktion.
- Unter `32rem` Komponentenbreite wird die Einrückung verdichtet. Titel dürfen
  mehrzeilig werden, während Offenlegungen und Symbolaktionen mindestens 44
  Pixel hohe Berührungsflächen behalten und keinen horizontalen Überlauf
  erzeugen.
- Zusätzliche Module können im Materialbereich geschlossen werden. Das Modul der
  aktiven Aufgabe ist geschützt; nach dem Schließen bietet eine lokale
  Statuszeile einmalig `Rückgängig` an. Schließen entfernt nur den
  Lernraumzustand und niemals Inhalte oder Abgaben.
- Lineare Lerneinheiten zeigen alle freigeschalteten Abschnitte. Der Abschnitt
  der aktiven Aufgabe steht zuerst und ist geöffnet; weitere Abschnitte beginnen
  eingeklappt und besitzen keine Schließen-Aktion.
- Jedes Modul besitzt eine standardmäßig geschlossene Untergruppe `Eigene
  Abgaben`. Ihre Historie wird erst beim Öffnen geladen; die neueste finale
  Abgabe steht zuerst. Rückmeldung, Kriterienauswertung und ältere Versuche
  bleiben darin zunächst eingeklappt.
- Entzogene oder gesperrte Inhalte werden beim Wiederherstellen verworfen
  beziehungsweise mit einem sicheren Ladefehler angezeigt.
- Ein normales Öffnen ersetzt niemals den Dokumentstapel. Erst
  die bewusste Aktion `Groß lesen` öffnet unter dem Aufgabenkopf eine
  Vollbreiten-Leseansicht. Die Buchseite und das Arbeitsheft bleiben montiert,
  sind dabei aber für Tastatur und Screenreader inaktiv. `Zurück zur Aufgabe`
  stellt Fokus und beide Scrollpositionen wieder her, ohne URL oder
  Browserhistorie zu ändern.
- Fließtext bleibt auf ungefähr `68ch` begrenzt. Bilder erscheinen direkt im
  Lesefluss, unverzerrt und unbeschnitten mit verständlichem Alternativtext.
  PDFs besitzen eine begrenzte Vorschau sowie `Groß lesen` und `Separat öffnen`;
  andere Dateien zeigen Dateityp, Größe und eine Öffnen-Aktion. Sichere
  Dialogtranskripte werden als flacher Sprecherverlauf wiedergegeben.
- Buchseite und Arbeitsheft besitzen auf breiten Flächen unabhängige vertikale
  Scrollbereiche. Leseposition, ausgewählter Eintrag sowie Modul- und
  Dokumentoffenlegungen bleiben schülerbezogen im aktuellen Tab erhalten.
- Gespeichert werden ausschließlich IDs und Ansichtsstatus, niemals Material-
  oder Abgabetexte.

### 11.5 Dialogarbeitsbereich

KI-Dialogaufgaben trennen das Gespräch sichtbar von der endgültigen Abgabe. Die
linke Spalte verwendet dieselbe Aufgaben- und Materialstruktur wie alle anderen
Aufgabenarten. Nur die Bearbeitungsfläche rechts erhält mit Fortschritt, Verlauf
und Eingabe eine dialogspezifische Form.

Verbindliche Regeln:

- Der Abschlussauftrag wird erst nach der bewussten Aktion `Dialog beenden`
  sichtbar.
- Die linke Spalte zeigt wie bei anderen Aufgaben zuerst `Aufgabe N · KI-Dialog`
  und die Aufgabenstellung, anschließend den unveränderten gemeinsamen
  Materialbrowser. Dialogeigene Partnerkarten, Sonderrahmen und abweichende
  Materialflächen sind dort nicht zulässig.
- Partnername, Antwortmodus und Rundenstand stehen im Dialogkopf rechts.
  `Dialog ohne Abgabe abbrechen`, `Pausieren` und `Dialog beenden` gehören zu den
  Sitzungsaktionen im Hauptbereich und werden nicht in der Materialspalte
  dargestellt.
- Ein fehlgeschlagener KI-Turn mit verbleibenden Generierungsversuchen zeigt
  `KI-Antwort erneut versuchen` und, sofern bereits eine Runde abgeschlossen
  wurde, weiterhin `Dialog beenden`. Nach dem dritten Fehlversuch entfällt die
  Wiederholungsaktion vollständig; Abschluss beziehungsweise erlaubter Abbruch
  bleiben als erreichbare Auswege sichtbar.
- `Antwort senden` steht ausschließlich unmittelbar beim Eingabefeld. In der
  Abschlussphase stehen `Zurück zum Dialog` und `Endgültig abgeben` beim
  Abschlussfeld.
- Der Hauptbereich beginnt mit Partnername, Modus, dem sichtbaren Text `Runde X
  von N` und einem zugänglichen Fortschrittsbalken. Er zeigt ausschließlich den
  tatsächlichen Rundenstand und erfindet keine fachlichen Dialogphasen.
- Auf breiten Flächen besteht der Hauptbereich aus drei Zeilen: Fortschritt,
  intern scrollbarer Verlauf und Eingabe beziehungsweise Abschluss. Nach dem
  Laden, einer neuen KI-Antwort und einer Größenänderung bleibt die aktuelle
  Frage vollständig sichtbar; der Tastaturfokus wird dabei nicht verschoben.
- KI-Beiträge stehen links in einer ruhig grün getönten Gesprächsfläche;
  Schülerbeiträge stehen rechts in einer zurückhaltend akzentgetönten Fläche.
  Dekorative Seitenleisten und zusätzliche Innenrahmen sind im Dialog verboten.
- Genau die jüngste beantwortbare KI-Nachricht trägt die sichtbare Kennzeichnung
  `Aktuelle Frage` und eine stärkere Kontur. Frühere Beiträge bleiben vollständig
  verfügbar, erhalten aber keine konkurrierende Hervorhebung.
- Sprecher werden technisch und eindeutig bezeichnet. Verwendete Satzanfänge
  bleiben als Hilfestellung sichtbar.
- Satzanfänge stehen ausschließlich im Hybridmodus direkt am Eingabebereich als
  optionale Hilfestellungen. Im Freitextmodus werden keine Ersatzfragen
  erfunden.
- Die Arbeitsfläche folgt demselben Kontextvertrag wie alle Aufgaben. Ab `60rem`
  steht der Partner- und Kontextbereich mit `clamp(32rem, 44cqw, 38rem)` links
  neben dem Gespräch. Darunter wechseln `Aufgabe` und `Materialien` als
  Vollbreitenansichten; beide bleiben dabei montiert. Damit bleibt auch hier ein
  übliches iPad im Querformat zweispaltig.
- Aktuelle und geöffnete Materialien sowie eigene frühere Abgaben bleiben auch
  während des Dialogs im einen Materialbereich verfügbar. Der bewusst geöffnete
  Vollbreiten-Lesemodus verwendet dieselbe Komponente wie andere Aufgaben und
  lässt Gespräch und Eingabe montiert.
- Auf Smartphonebreite nutzen Nachrichten und `Antwort senden` die volle
  verfügbare Breite. Sitzungsaktionen stehen nebeneinander und werden erst unter
  `22rem` Containerbreite gestapelt.
- Ohne Container-Query-Unterstützung bleibt der einspaltige Grundaufbau nutzbar;
  große, nicht geteilte Lernansichten erhalten einen Viewport-Fallback.
- Der Sicherheitshinweis steht als schmale Zeile im Eingabebereich, also direkt
  dort, wo Text an die KI übermittelt wird. Er wird im Partner- oder
  Materialkontext nicht dupliziert.
- Alle produktiven `.dialog-*`-Regeln liegen in der Cascade-Layer `learning` in
  `frontend/src/lib/styles/learning-unit.css`. Lokal begrenzte Dialogvariablen
  für Rundungen und Mischflächen werden aus den zentralen Farb- und
  Typografietokens abgeleitet und verändern keine andere Aufgabenart.
- Das UI-Labor zeigt Gespräch und Abschluss jeweils als vollwertige
  Referenzfläche in Light und Dark sowie auf Desktop, Tablet und Smartphone.

## 12. Auth und Preview

- Auth gehört sichtbar in dieselbe Produktsprache
- `/ui-lab` ist die interne Referenzfläche
- `/ui-lab` muss Shell, Task-Sprache, Graph-Sprache, Auth und Theme-Wechsel
  gleichzeitig zeigen

## 13. Verbotene Alt-Muster

- weiche SaaS-Radien
- warm-editoriale Blau/Papier-Sprache
- diffuse Schatten
- pillige Modusumschalter als Default
- generische Card-Haufen ohne klare Objektlogik

## 14. Technische Pflege des Designsystems

`frontend/src/lib/styles/index.css` ist der einzige globale CSS-Einstiegspunkt. Er ordnet die Stylesheets mit CSS Cascade Layers in folgender Reihenfolge:

1. `reset`
2. `tokens`
3. `base`
4. `typography`
5. `primitives`
6. `learning`
7. `teaching`
8. `auth`
9. `overrides`

Verbindliche Regeln:

- `theme-tokens.css` ist die einzige Quelle für globale `--color-*`, `--font-*`, `--space-*` und `--radius-*`-Variablen.
- Fachliche Stylesheets dürfen globale Tokens verwenden, aber nicht neu definieren.
- Eindeutig fachlich benannte, komponentenlokale Variablen bleiben erlaubt.
- Neue globale Stylesheets werden nicht direkt in `+layout.svelte` importiert, sondern einer Schicht in `index.css` zugeordnet.
- Benachbarte Bedienelemente mit derselben Funktionsebene teilen gemeinsame Chrom-Regeln; Theme- und Account-Schalter der Top-Bar sind die Referenz dafür.
- Die ehemalige warme Papier-/Petrolpalette darf nicht lokal über hart codierte Werte zurückkehren.

Das UI-Labor und ausgewählte vollständige Arbeitsansichten besitzen freigegebene Light- und Dark-Referenzbilder für Desktop und Mobil. Der Moduleditor wird als echte, authentifizierte Arbeitsansicht bei 1920 × 1080, 1024 × 768 und 390 × 844 Pixeln geprüft. `make test-visual-smoke` vergleicht diese Referenzen, während `make update-visual-baselines` ausschließlich für eine beabsichtigte und anschließend visuell geprüfte Designänderung verwendet wird.
