# UI/UX-Leitfaden für GUSTAV Alpha-3

> Archivhinweis
>
> Dieses Dokument ist fachlich ersetzt durch `docs/DESIGN.md` und dient nur
> noch als historischer Zwischenstand aus dem frühen Alpha-3-Rework.
> Neue UI-Entscheidungen werden nicht mehr hier dokumentiert.

## Zweck

Dieser Leitfaden definiert die verbindliche Gestaltungsrichtung für die neue
SvelteKit-Oberfläche von GUSTAV Alpha-3. Er ersetzt die frühere SSR-/HTMX-
geprägte UI-Logik durch ein klares, modernes und ablenkungsarmes Produktbild.

GUSTAV ist kein Marketing-Auftritt und kein generisches SaaS-Dashboard. GUSTAV
ist eine Arbeitsoberfläche für Lernen, Unterrichten, Diagnostik und Live-
Begleitung im Unterricht. Die Oberfläche muss deshalb ruhig, eindeutig,
zugänglich und auf Dauer angenehm nutzbar sein.

Referenzimpulse für diesen Leitfaden:

- aktuelle Alpha-3-Architektur mit SvelteKit-App-Shell und Browser-BFF
- bestehende Fachräume `learning`, `teaching`, `diagnostics`, `live`
- OpenAI-Artikel `Designing delightful frontends with GPT-5.4`

## Leitbild

Die Alpha-3-Oberfläche folgt vier Grundsätzen:

1. Fokus vor Dekoration
   Inhalte, Status und nächste Handlungen sind wichtiger als visuelle Effekte.
2. Orientierung vor Dichte
   Auch bei vielen Daten bleibt immer klar, wo man ist und was als Nächstes
   möglich ist.
3. Ein Produkt, keine Teilprodukte
   `learning`, `teaching`, `diagnostics`, `live` und `auth` gehören sichtbar
   zu derselben Plattform.
4. Ruhe als Qualitätsmerkmal
   Wenige Farben, wenige Container, starke Typografie und klare Abstände sind
   wichtiger als viele Karten, Badges oder Trennlinien.

## Produktentscheidungen für Alpha-3

- Visuelle Richtung: ruhig-operativ
- Layoutmodell: `Top-Bar + Workspace + Sheet`
- Rollenmodell: ein gemeinsames Designsystem für Lernende und Lehrkräfte
- Bildsprache: nur gezielt und funktional
- Themes: Light und Dark sind gleichwertig
- Informationsdichte: mittel und gut scanbar
- Motion: subtil und funktional
- Typografie: prägnant, aber sachlich
- Auth: dieselbe Produktsprache wie die restliche App

## App-Shell

### Kanonisches Layout

Die Standardstruktur aller Produktflächen ist:

- `Top-Bar`
  Primäre Navigation zwischen den Produkträumen.
- `Workspace`
  Die eigentliche Arbeitsfläche mit Inhalt, Formularen, Tabellen, Aufgaben oder
  Kurskontext.
- `Sheet`
  Temporäre oder kontextuelle Zweitfläche für Details, Auswahlzustände,
  Filter, Formulare oder Detailblätter.

Diese Struktur gilt als Default. Abweichungen müssen fachlich begründet sein.

Die visuelle Gewichtung innerhalb dieser Struktur ist ebenfalls festgelegt:

- Die `Top-Bar` ist funktional, aber visuell zurückgenommen.
- Die `Top-Bar` bleibt möglichst leise: keine starke Flächeninszenierung, keine
  dekorativen Badges, keine optische Konkurrenz zum Workspace.
- Die `Top-Bar` trägt die primäre Navigation dauerhaft sichtbar.
- Die `Top-Bar` darf in Alpha-3 etwas hochwertiger komponiert sein, solange
  diese Aufwertung ruhig bleibt: kleines Brand-Signet, fein abgestimmter
  Aktivzustand und reduzierte Account-Zone statt zusätzlicher Meta-Chrome.
- Der `Workspace` trägt die Aufmerksamkeit.
- `Sheets` sind präzise Zweitflächen und dürfen nicht wie gleichrangige
  Hauptseiten konkurrieren.

### Verhalten nach Gerät

- iPad first
  Das iPad ist die primäre Zielgröße. Top-Bar und Workspace sollen dort stabil,
  verständlich und ohne überladene Dichte funktionieren.
- Desktop close second
  Desktop ist keine völlig andere Oberfläche. Die Grundstruktur bleibt
  identisch; nur Breiten, Persistenz und parallele Sichtbarkeit nehmen zu.
- Phone third
  Auf dem Telefon bleibt der Workspace dominant. Top-Bar und Sheets werden
  temporär und dürfen den Hauptfluss nicht zerreißen.

### Inhaltsbreite

- Textnahe Standardflächen folgen einer ruhigeren, iPad-orientierten
  Lesebreite statt maximaler Desktop-Ausnutzung.
- Default für den inneren Workspace-Container ist eine Breite von ungefähr
  `42rem`.
- Zielbild: Auf einem iPad im Hochformat bleiben spürbare Seitenränder, damit
  längere Sätze nicht zu breit und die Oberfläche nicht zu technisch wirkt.
- Breitere Darstellungen für Matrizen, Live-Ansichten oder tabellarische
  Diagnostik sind erlaubt, aber explizit zu begründen.

### Navigation

- Die Top-Bar ist rollenabhängig und zeigt nur die für den aktuellen Nutzer
  sinnvollen Primärziele.
- Für Lernende bleibt die Top-Bar reduziert:
  - `Lernraum`
- Für Lehrkräfte ist die Top-Bar arbeitsorientiert:
  - `Kurse`
  - `Lerneinheiten`
  - `Diagnostik`
  - `Live`
- Die aktive Position muss klar markiert sein.
- Die Top-Bar darf keine zweite Startseite sein. Wenig Chrome, wenig Meta,
  keine dekorativen Status-Chips.
- Die Lehrkraft-Startseite bleibt unter `/teaching` erhalten, ist aber kein
  eigener Primärtab. Sie ist ein Arbeitsstarter für `Unterrichten` und
  `Vorbereiten`, keine zweite Navigation oder Bestandsübersicht.
- Das Brand-Element `[LOGO] GUSTAV` darf für Lehrkräfte explizit auf diese
  Home-Seite zurückführen.
- Links darf ein kleines Komplettlogo mit ruhiger Wortmarke stehen. Das Logo
  bleibt klein genug, um nicht wie eine Illustration im Header zu dominieren.
- Primärnavigation nutzt keine zusätzlichen Abkürzungs-Badges neben dem
  eigentlichen Linklabel.
- Primärnavigation nutzt keine zusätzlichen Icons pro Raum.
- Die Top-Bar ist textbasiert. Orientierung entsteht durch Reihenfolge,
  Typografie, Abstände und genau einen ruhigen Aktivzustand.
- Für Alpha-3 ist ein feiner Pill-Aktivzustand für den aktuellen Raum
  ausdrücklich erlaubt, solange die inaktiven Punkte textbasiert bleiben.
- Die Top-Bar läuft über die volle Breite der App-Shell, ihr innerer Inhalt
  sitzt jedoch in einem ruhigen, zentrierten Container.
- Die Top-Bar ist dauerhaft sichtbar; für Alpha-3 ist sie der bevorzugte
  Default gegenüber einer einklappbaren Rail.
- Die Top-Bar ist kein Ablageort für jede Unterseite. Tiefe Navigation gehört
  in Breadcrumbs, den Workspace oder in kontextuelle Sheets.
- Bewegungen in der Hauptnavigation müssen minimal bleiben. Layoutsprünge durch
  Ein- und Ausklappen einer Seitennavigation sind zu vermeiden.
- Die rechte Seite der Top-Bar zeigt standardmäßig keinen permanent sichtbaren
  Rollen- oder Logout-Chrome. Stattdessen wird ein kleines Account-Menü mit
  Name und Avatar-/Monogramm-Trigger bevorzugt; Rolle und `Abmelden` leben im
  geöffneten Menü.

### Breadcrumbs

- Breadcrumbs sind die sekundäre Navigation direkt unter der Top-Bar.
- Breadcrumbs erscheinen erst ab Ebene 2 einer Raumhierarchie.
- Breadcrumbs beantworten nur die Frage: „Wo bin ich innerhalb dieses Raums?“
  Sie enthalten keine Aktionen.
- Der letzte Breadcrumb-Eintrag markiert den aktuellen Ort und ist nicht
  klickbar.
- Der Seitentitel darf die letzte Breadcrumb-Stufe wiederholen.
- Breadcrumbs stehen oberhalb des Seitentitels und bleiben typografisch
  zurückhaltend.
- Auf Ebene 1 bleibt die Breadcrumb-Zeile leer oder entfällt vollständig.
- Eine knappe Ebene-1-Ausnahme ist erlaubt, wenn der erste Breadcrumb eine
  Teacher-Arbeitsseite ruhiger verankert, etwa bei `Kurse`.
- Für Lehrkräfte beginnen Breadcrumbs auf Arbeitsseiten bei `Kurse` oder
  `Lerneinheiten`, nicht bei der unsichtbaren Home-Seite `Lehrenden-Welt`.

### Weitere Sekundärnavigation

- Weitere sekundäre Navigation nutzt Tabs, Segment-Controls,
  In-Page-Navigation oder Listen im Workspace, nicht zusätzliche globale
  Navigationsleisten.
- Sekundäre Navigation darf die Top-Bar nicht optisch duplizieren.

## Übergangshinweis

- Frühere Alpha-3-Slices experimentierten mit einer einklappbaren Rail.
- Diese Richtung gilt nicht mehr als bevorzugtes Shell-Modell.
- Neue Arbeit an der Shell richtet sich an der Top-Bar plus Breadcrumb-Zeile
  aus.

## Raumprinzipien

### Lernraum

Der Lernraum ist die fokussierteste Fläche des Produkts.

- Nur Informationen zeigen, die für das aktuelle Lernen nötig sind.
- Inhalte, Aufgaben und Rückmeldungen folgen einer klaren Lesereihenfolge.
- Nebenreize, Meta-Informationen und Steuerungselemente bleiben zurückhaltend.
- H5P, Material und native Aufgaben sollen sich wie Teile derselben Oberfläche
  anfühlen, nicht wie eingebettete Fremdprodukte.

### Lehrenden-Startseite und Lehrenden-Welt

Die Lehrenden-Welt ist operativer, aber nicht dashboardhaft.

- `/teaching` beantwortet ausschließlich die Frage „Wo arbeite ich jetzt
  weiter?“: Kurs und Lerneinheit für Live wählen oder eine der drei zuletzt
  bearbeiteten Lerneinheiten öffnen.
- Kurse, Diagnostik und die globale Navigation werden im Inhalt dieser Seite
  nicht wiederholt. Kennzahlen und erklärende Einführungstexte entfallen.
- Beide Arbeitswege sind auf breiten Ansichten gleichwertig und nur durch eine
  Linie getrennt. Auf Tablet und Smartphone stehen sie untereinander.
- `PageActionHead` bildet den knappen Seitenkopf. Letzte Lerneinheiten nutzen
  die ruhige Listenfamilie; die abhängige Live-Auswahl bleibt fachbezogen.

- Kurse, Lerneinheiten, Mitglieder und Arbeitsstände müssen schnell scanbar
  sein.
- Priorität haben gute Listen, klare Zustände und direkte Handlungen.
- Große Kachelwände sind zu vermeiden.
- Der Raum darf dichter sein als der Lernraum, aber nicht unruhig.
- Der globale Shell-Header ist die obere Orientierung. Inhaltsseiten
  wiederholen Titel und Einleitung nicht noch einmal lokal.
- Indexseiten der Lehrenden-Welt beginnen möglichst direkt mit der eigentlichen
  Arbeit: Primäraktion und Objektübersicht.
- Kleine Seitenaktionen wie `Kurs erstellen` sitzen im Kopfbereich der
  Arbeitsfläche und nicht in einer eigenen Aktions-Lane.
- Klare Teacher-Arbeitsseiten dürfen noch stärker reduziert werden: sichtbar
  bleiben dann nur `Breadcrumb + Kopfaktion + Objektübersicht`.
- Auf solchen Arbeitsseiten sind zusätzlicher Seitentitel und Introtext nicht
  verpflichtend, wenn sie keine neue Information liefern.
- Objektübersichten der Lehrenden-Welt liegen nicht noch einmal in einer
  äußeren Rahmen- oder Kartenfläche. Die Objektkarten selbst sind die einzige
  sichtbare Objektebene.
- Für `Kurse` gilt ein flacher Katalog mit den getrennten Zuständen `Aktiv` und
  `Archiv`. Karten oder Dashboard-Kacheln werden hier nicht verwendet.
- Jede Zeile zeigt Titel, `Fach · Jahrgang · Schuljahr`, Mitglieds- und
  Lerneinheitenanzahl sowie genau eine zustandsabhängige Hauptaktion.
- Aktive Kurse sind alphabetisch sortiert. Das Archiv wird nach Schuljahren
  absteigend gruppiert. Suche, Schuljahr und Fach verfeinern dieselbe Liste.
- Die Mehrfachauswahl gehört ausschließlich zur Sammelarchivierung. Auf kleinen
  Breiten stapeln sich Metadaten und Aktion innerhalb derselben Kurszeile.
- Unvollständige Bestandskurse bleiben lesbar, werden aber ruhig markiert. Vor
  Mitglieder-, Lerneinheiten- oder Archivänderungen führt die Kursseite zur
  Ergänzung von Fach, Jahrgang und Schuljahr.
- Kurs-Detailseiten bleiben derselben Sprache treu: kein lokaler Intro-Block,
  sondern direkte Arbeitsbereiche unterhalb des globalen Headers.
- Kurs-Detailseiten für Lehrkräfte dürfen als ruhiges Listen-Werkzeug
  organisiert sein, wenn Kursdetails, Mitglieder und Lerneinheiten direkt auf
  derselben Seite bearbeitbar bleiben sollen.
- Für `Kurse` ist dabei das bevorzugte Modell:
  - schmale Kopfzeile mit Rücksprung, Kurstitel, Metazeile und kleinem
    Overflow-Menü
  - dominante Hauptspalte `Lerneinheiten`
  - ruhige Sidecar-Spalte für `Mitglieder` und `Kurs`
- `Lerneinheiten` ist der Standardfokus der Seite und bildet den
  `primary workspace`:
  - geordnete Liste
  - Reihenfolge ändern
  - Einheiten ergänzen oder entfernen
- `Mitglieder` und `Kursdetails` leben im `secondary context`:
  - als kompakte Sidecar-Blöcke auf breiten Ansichten
  - als Drawer auf iPad hochkant und schmaleren Breiten
- Zeilenaktionen bleiben textnah oder liegen in kleinen Zeilenmenüs statt in
  dauerpräsenten Buttonleisten.
- `Kurs bearbeiten` liegt im Kurskontext als Drawer/Dialog. Archivierung und
  Wiederherstellung sind dort eigenständige Lebenszyklusaktionen.
- `Kurs endgültig löschen` zeigt zuerst die aktuelle Löschfolge. Die Lehrkraft
  muss Kurstitel und Verlust aller Schülerdaten bestätigen; ein unmittelbarer
  Löschknopf ohne diesen Ablauf ist unzulässig.
- Diagnostik ist aus dem Kurskontext direkt erreichbar, jedoch als Kopf- oder
  Sekundäraktion statt als eigener Hauptblock.
- Das Hinzufügen von Lerneinheiten darf direkt auf der Kursseite stattfinden,
  wenn es einen ruhigen, klar begrenzten Dialog oder ein Sheet nutzt.

### Diagnostik

`diagnostics` ist datenorientiert und analytisch.

- Matrizen, Listen und Profilansichten müssen in erster Linie gut lesbar sein.
- Zahlen, Labels, Zustände und Fokuswechsel brauchen eine stabile visuelle
  Hierarchie.
- Farbe dient hier vor allem der Orientierung und Statusmarkierung, nicht der
  Dekoration.
- Detailinformationen gehören in Sheets, Detailseiten oder gezielte Drilldowns,
  nicht in überladene Tabellenzellen.

### Live

`live` ist ein operativer Echtzeitraum.

- Statuswechsel, Blickführung und schnelle Erfassbarkeit stehen im Vordergrund.
- Die Fläche muss unter Zeitdruck funktionieren.
- Detailblätter gehören in klare Sheets oder sekundäre Panels.
- Alles, was nach „Analyse im Nachhinein“ aussieht, gehört eher in
  `diagnostics` als in `live`.

### Auth

`auth` gehört optisch zur Plattform.

- Keine separate Brand-Welt.
- Dieselbe Typografie, dieselben Flächentöne, dieselbe Akzentlogik.
- Auth-Flächen dürfen reduzierter und großzügiger sein, aber nicht emotionaler
  oder „heroischer“ als der Rest der App.

## Visuelles System

### Typografie

Alpha-3 nutzt höchstens zwei Schriftfamilien. Für die App-Shell und die
operativen Räume ist eine einzige gute humanistische Sans ausdrücklich
erwünscht, wenn sie ruhiger wirkt als eine künstlich gemischte Zweifont-Lösung.

Praktischer Default:

- eine humanistische Sans für UI, Navigation, Überschriften, Listen und
  Fließtext der Arbeitsflächen
- eine zweite Schrift nur dann, wenn sie in echten Lesephasen einen klaren
  Mehrwert schafft und nicht nach Stilbruch wirkt

Aktueller Implementierungs-Default in Alpha-3:

- `Nunito` als lokal gebündelte Primärschrift für Shell, Arbeitsflächen,
  Lernmaterial und Schülerabgaben
- keine separaten Serif-Schriften in Shell, Navigation, Überschriften,
  Aktionsflächen oder regulären Inhaltsflächen

Typografie erzeugt die Hierarchie der Oberfläche. Sie ersetzt keine fehlende
Struktur, aber sie trägt sie sichtbar.

Regeln:

- Überschriften sind knapp, klar und funktional.
- Auf kompakten Arbeitsseiten hat typografische Hierarchie Vorrang vor
  zusätzlicher Textmenge. Kennzahlen und Metazeilen bleiben sichtbar
  zurückhaltender als der Objekttitel.
- Typografische Hierarchie entsteht primär über Gewicht, Größe, Zeilenhöhe und
  Abstand, nicht über einen Font-Wechsel.
- Utility Copy schlägt Marketing-Sprache.
- Labels, Meta-Texte und Hilfetexte sind bewusst zurückhaltend.
- Große Überschriften sind nur dort richtig, wo sie der Orientierung dienen.
  Die Shell darf nicht durch permanente Großtypografie schwer wirken.
- Zeilenlängen bleiben angenehm lesbar.
- Längere Lerntexte dürfen etwas mehr Luft haben als operative Lehrkraft-Flächen.

Empfohlene Skala:

| Stil | Schrift | Größe | Gewicht | Zeilenhöhe |
| --- | --- | --- | --- | --- |
| H1 | Humanistische Sans | 2.25rem | 700 | 1.1 |
| H2 | Humanistische Sans | 1.75rem | 700 | 1.15 |
| H3 | Humanistische Sans | 1.375rem | 600 | 1.2 |
| Body | Humanistische Sans | 1rem | 400 | 1.55 |
| UI | Humanistische Sans | 0.95rem | 500 | 1.35 |
| Meta | Humanistische Sans | 0.85rem | 500 | 1.3 |

### Farbe und Tonwerte

GUSTAV arbeitet nicht mit vielen Markenfarben. Jede Theme-Variante besitzt:

- eine dominante Akzentfarbe
- einen ruhigen Hintergrund
- klar getrennte Surface-Stufen
- ausreichend kontrastreiche Textfarben

Empfohlene Light-Defaults:

- `--color-bg-base`: `#FAF4ED`
- `--color-bg-surface`: `#FFFAF3`
- `--color-bg-elevated`: `#F7EFE7`
- `--color-text`: `#575279`
- `--color-text-muted`: `#9893A5`
- `--color-accent`: `#286983`
- `--color-border`: `#E8DDD2`
- `--color-success`: `#56949F`
- `--color-warning`: `#EA9D34`
- `--color-danger`: `#B4637A`

Empfohlene Dark-Defaults:

- `--color-bg-base`: `#272E33`
- `--color-bg-surface`: `#2E383C`
- `--color-bg-elevated`: `#374145`
- `--color-text`: `#D3C6AA`
- `--color-text-muted`: `#9AA79D`
- `--color-accent`: `#A7C080`
- `--color-border`: `#414B50`
- `--color-success`: `#7FBBB3`
- `--color-warning`: `#DBBC7F`
- `--color-danger`: `#E67E80`

Regeln:

- Pro Theme nur eine dominante Akzentfarbe.
- Statusfarben nur für echte Statussignale.
- Große Flächen bleiben ruhig und textfreundlich.
- Links und Aktionen nutzen dieselbe gedämpfte Akzentfamilie; billige
  Standard-Linkfarben oder stark gesättigte CTA-Töne sind zu vermeiden.
- Keine dekorativen Verläufe in Routine-Produktflächen.
- Kontrast ist funktional, nicht optional.

### Fläche statt Kartenwand

Alpha-3 nutzt standardmäßig ruhige Arbeitsflächen statt Card-Mosaike.

Container werden nur eingesetzt, wenn sie einen klaren Zweck erfüllen:

- Gruppierung
- Fokus
- Interaktion
- Statusabgrenzung
- Kontextwechsel

Nicht jede Liste braucht Karten. Oft sind bessere Alternativen:

- eine gut gesetzte Tabelle
- eine dichte, saubere Liste
- ein Abschnitt mit typografischer Hierarchie
- ein Sheet für Details statt einer weiteren Box im Hauptbereich

## Komponenten- und Interaktionsmuster

### Listen, Tabellen und Matrizen

- Listen sind die Standarddarstellung für scanbare operative Inhalte.
- Tabellen und Matrizen dürfen dichter sein als Lernflächen, brauchen aber
  klare Spaltenlogik, Sticky-Kontext und gut sichtbare Interaktionsziele.
- Zellen sind nur dann klickbar, wenn dies visuell und semantisch eindeutig ist.
- Namen, Status und nächste Handlung müssen schneller erfassbar sein als
  sekundäre Metadaten.

### Formulare

- Formulare folgen einer klaren vertikalen Leselogik.
- Primäre Aktion steht stabil am erwartbaren Ort.
- Hilfetexte sind knapp und direkt.
- Fehler erscheinen feldnah und verständlich.
- Auf kleinen Flächen keine unnötigen Mehrspalten-Formulare.

### Sheets und Drawer

Sheets sind das Standardmuster für kontextuelle Zweitflächen.

Geeignete Fälle:

- Detailansicht
- Schnellbearbeitung
- Filter
- Auswahl eines Unterobjekts
- Live-Detailblatt

Sheets sind keine Ablage für beliebige Restinformationen. Wenn der Inhalt eine
eigene Lese- oder Arbeitslogik hat, bekommt er eine eigene Seite.

### Buttons und Aktionen

- Eine Fläche hat idealerweise genau eine primäre Aktion.
- Sekundäre Aktionen sind sichtbar, aber klar nachgeordnet.
- Destruktive Aktionen sind selten und eindeutig markiert.
- Icon-only-Buttons nur bei sehr vertrauten Mustern.

### Leere Zustände

- Leere Zustände erklären, was fehlt und was man als Nächstes tun kann.
- Sie sind kurz, sachlich und ohne produktferne Metaphern.
- Illustration nur, wenn sie wirklich Orientierung schafft.

## Motion

Motion unterstützt Orientierung und Reaktionsverständnis.

Erlaubt:

- sanfte Sheet- und Drawer-Transitions
- ruhige Rail-Transitions beim Ein- und Ausklappen
- kurze Hover- oder Focus-Reaktionen
- dezente State-Wechsel
- wenige, bewusst gesetzte Entrance-Momente

Nicht erlaubt:

- dauernde Ambient-Animationen
- dekorative Parallax- oder Glow-Effekte
- konkurrierende Bewegungen in mehreren Bereichen gleichzeitig
- lange, träge Übergänge

Bei `prefers-reduced-motion` werden Übergänge deutlich reduziert oder
entfernt.

## Copy und Tonalität

- Sprache ist klar, ruhig und direkt.
- Die Oberfläche erklärt Handlungen, nicht sich selbst.
- Begriffe folgen `docs/glossary.md`.
- Fachräume sollen korrekt benannt werden:
  - `Lernraum`
  - `Lehrenden-Welt`
  - `Diagnostik`
  - `Live`
- Mikrocopy soll handlungsorientiert sein:
  - gut: `Kurs öffnen`
  - gut: `Abgabe speichern`
  - schlecht: `Entdecke deine Möglichkeiten`

## Barrierefreiheit

Barrierefreiheit ist keine Nacharbeit, sondern Standard.

Pflichtregeln:

- semantisches HTML zuerst
- vollständige Tastaturbedienbarkeit
- sichtbare Fokuszustände
- ausreichender Kontrast in Light und Dark
- keine Information ausschließlich über Farbe
- sinnvolle Touch-Ziele auf Tablet und Telefon
- lesbare Schriftgrößen und stabile Zeilenhöhen
- respektierter Reduced-Motion-Modus

Zusätzlich für Alpha-3 wichtig:

- Rail, Tabs, Tabellen und Sheets müssen auf iPad zuverlässig per Tastatur und
  Touch funktionieren.
- Interaktive Matrizen brauchen klare Fokus- und Hover-Zustände.
- H5P-Einbettungen dürfen die Tastaturnavigation des restlichen Workspace nicht
  unverständlich machen.

## Verbindliche Anti-Patterns

Die folgenden Muster gelten für Alpha-3 als unerwünscht:

- Startseiten aus großen Kachelrastern ohne klare Priorität
- dekorative Verläufe hinter Standard-Produktflächen
- mehrere gleich starke Akzentfarben auf einer Fläche
- beliebig wiederholte Karten für Inhalte, die besser als Listen funktionieren
- überlaute Badges und Statuschips ohne Informationsgewinn
- zentrierte „heroische“ Auth-Seiten, die nicht zur App passen
- visuell getrennte Mini-Produkte pro Raum
- Copy im Stil von Marketing-Websites

## Konsequenz für die Umsetzung

Wenn eine neue Oberfläche entsteht, ist die Default-Frage nicht:

`Welche Karte bauen wir?`

Sondern:

`Welche Arbeitsfläche braucht der Nutzer gerade, und welcher Kontext muss jetzt sichtbar bleiben?`

Genau daraus leiten sich in Alpha-3 Rail, Workspace, Sheets, Typografie,
Kontrast, Dichte und Motion ab.
