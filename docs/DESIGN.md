# DESIGN.md

## Status

Dieses Dokument ist der verbindliche Designvertrag für die Svelte-Oberfläche von GUSTAV. Es ersetzt `docs/UI-UX-Leitfaden.md` fachlich vollständig.

Die am 18. Oktober 2026 abgestimmte Zielgestaltung ist eine ruhige, moderne Arbeitsoberfläche mit vertrauten SaaS-Mustern. Grundlage ist der besprochene Gestaltungsentwurf für Modulansicht und Aufgabenraum mit 8 px Rundung der Inhaltsflächen und 16 px Abstand zwischen Arbeitsbereichen. Die verbindlichen Regeln sind hier vollständig beschrieben; der Vertrag benötigt keinen Zugriff auf den Chatentwurf.

Die Preview-Route `/ui-lab` bleibt die visuelle Referenzfläche. Gemeinsame Tokens, Navigation und produktive Arbeitsansichten wurden auf diesen Vertrag umgestellt. Der [Abgleich vom 22. Oktober 2026](plan/2026-10-22-ui-gesamtpruefung-commits.md) dokumentiert die Sichtprüfung und 102 aktualisierte Referenzbilder. Dies ist keine Abnahme einer alten Safari-Engine; die reale Geräteprüfung für iPadOS 15.3.1 bleibt separat offen. Frühere Entwürfe überstimmen die hier beschriebenen Regeln nicht. Künftige Referenzänderungen erfordern weiterhin eine bewusste Umsetzung und visuelle Prüfung.

Die Prüfung `frontend/src/lib/styles/token-ownership.test.ts` sichert für die globalen Stylesheets ab, dass Schrift-, Farb-, Radius-, Abstands- und Layouttokens ausschließlich in `theme-tokens.css` definiert werden und alle entsprechenden Referenzen auflösbar sind. Lokale Komponentenstyles sind noch nicht vollständig durch diese Prüfung abgedeckt. Im Dialog verwenden Produkt und UI-Labor denselben `DialogMessage`-Baustein; das Labor nutzt außerdem den produktiven Aufgaben-/Kontextbaustein und Spaltentrenner. Das ersetzt keine vollständige Prüfung aller Produktseiten.

## 1. Produktbild

### Reparaturvertrag: rollenübergreifende Graphbedienung

Beide Rollen verwenden dieselben deutschen Werkzeugnamen, kontrastreichen Zustände und geometrisch identischen Knoten und Kanten. Die Graphfläche nutzt die nach Kopf- und Kontextleisten verbleibende Bildschirmhöhe; mobile Symbolaktionen bleiben mindestens 44 × 44 px groß. Der lesbare Startfokus bleibt erhalten, Gesamtansicht ist eine ausdrückliche Übersicht. Ein selbst gewählter Ausschnitt bleibt bei Aktualisierung und Rückkehr im selben Tab erhalten.

Gesperrte Lernendenmodule tragen ausdrücklich „Gesperrt“ und die tatsächlich gelieferten Freischaltangaben. Fehlen diese, wird dies verständlich benannt; es werden keine Bedingungen aus Vermutungen abgeleitet. Sperren ändern weder Knotenmaße noch Koordinaten und bleiben serverseitig durchgesetzt.

### Reparaturvertrag: Inhalte und lineare Abschnitte

Markdown-Code (inline und als Block) ist darstellbarer Text, keine ausführbare Funktion. Der visuelle Editor muss diese Inhalte beim Öffnen, unveränderten Speichern und erneuten Laden erhalten; die zentrale sichere Markdown-Ausgabe bleibt verbindlich.

Die Auswahl eines linearen Abschnitts zeigt wie bei Modulen eine flache Kontextleiste mit „Inhalte bearbeiten“ und „Eigenschaften“. Nur die ausdrückliche Eigenschaften-Aktion öffnet das Formular. Rückkehr aus dem Inhaltseditor erhält Auswahl und Graphausschnitt; ältere Direktlinks bleiben gültig. Lernende sehen „Abschnitt 1 · Titel“, bei fehlendem Titel nur die Abschnittsnummer.

### Reparaturvertrag: gemeinsame Aktionen, Felder und Dialoge

Die bestehende Workspace-Aktionsbasis gilt auch für Practice, Kataloge, Profil und Verwaltungsdialoge. Primär, sekundär, dezent und destruktiv unterscheiden ihre Gewichtung, nicht Schriftfamilie oder Grundform. Normale Aktionen und einzeilige Felder sind mindestens 44 px hoch; mehrzeilige Beschriftungen dürfen wachsen. Kleinere Desktopwerkzeuge benötigen eine ausdrückliche kompakte Ausnahme; mobile Symbolaktionen haben mindestens 44 × 44 px Bedienfläche. Akzentflächen verwenden das kontrastgeprüfte Text-/Flächenpaar des jeweiligen Themes. Navigationslinks bleiben Links, Zustandsänderungen Buttons.

Radiofelder und Checkboxen stehen kompakt neben ihrer Beschriftung und werden von allgemeinen Vollbreitenregeln ausgenommen. Suchfelder verwenden dieselbe Feldbasis und Theme-Farben wie Formulare. Drawer ordnen ihren Inhalt oben an; freie Bildschirmhöhe streckt keine Eingabefelder.

Dialoge und Drawer verwenden dezente Konturen, die gemeinsamen Radien und Innenabstände und eine beschriftete Schließen-Aktion. Fokus wechselt hinein, Tab bleibt im obersten Dialog, Escape schließt nur diesen, danach kehrt der Fokus zum noch vorhandenen Auslöser zurück. Löschen liegt im sichtbar beschrifteten Menü „Weitere Aktionen“ und erfordert weiterhin die vorhandene Bestätigung. Öffnen und Bearbeiten bleiben direkt zugänglich.

### Reparaturvertrag: Anmeldung und Einladungen

Anmeldung und Passwort-Reset bezeichnen das normale Anmeldefeld als „E-Mail-Adresse“ und verwenden E-Mail-Autofill. Registrierung bleibt an die Schul-E-Mail gebunden; IServ und bestehende Kontonamen werden nicht verändert. Keycloak-Seiten teilen genau einen äußeren Rahmen sowie dieselbe Initialisierung und sichtbare Umschaltung von Hell/Dunkel. Felder passen einschließlich Innenabständen und Rahmen in ihre Fläche.

Beim Einstieg über GUSTAV wird ausschließlich die validierte Darstellung `light` oder `dark` übergeben. Ohne diesen Hinweis gilt die auf der Auth-Domain gespeicherte Auswahl, danach die Systemeinstellung. Keine Sitzungs- oder Identitätsdaten werden dafür übergeben. Fehlerseiten bieten einen festen Rückweg zur Anmeldung über den konfigurierten GUSTAV-Ursprung; freie Rücksprungadressen sind dafür nicht zulässig. Gültige und ungültige Einladungen verwenden dieselbe ruhige, kontrastreiche Gestaltung. Die Auth-Ressourcen erhalten ihre Grundwerte beim Build aus `theme-tokens.css`, ohne Abrufe zwischen den Oberflächen zur Laufzeit.

### Reparaturvertrag: H5P-Arbeitsflächen

H5P übernimmt beim Build die zentralen Designwerte. Player und Editor verwenden dieselben auflösbaren Farben, Schriften und Zustände; die Standardbedienung ist deutsch, gespeicherte Autorentexte bleiben unverändert. Äußere GUSTAV-Rahmen und innere Bibliotheksflächen werden getrennt gestaltet. Es gibt keine neue Bibliothek und keinen Fork.

DragQuestion startet in „Lesbare Ansicht“: Die tatsächliche Renderbreite wird aus den gemessenen Karten- und Beschriftungsschriften berechnet, sodass diese mindestens 16 px erreichen. Die Originalgeometrie bleibt unverändert. „Gesamtansicht“ passt die vollständige Aufgabe in die verfügbare Breite; Vergrößern und Verkleinern ändern die echte Renderbreite und lösen das reguläre H5P-Resize aus. Keine optische Skalierung mit abweichenden Ziehkoordinaten.

Nur die beschriftete Aufgabenfläche scrollt horizontal. Native Scrollbedienung bleibt erhalten; zusätzliche Ziehgesten zum Verschieben dürfen das Antwortziehen nicht überlagern. Tastaturfokus macht das aktive Aufgabenelement innerhalb der Arbeitsfläche sichtbar. Ansichtssteuerung und H5P-Auswertung bleiben voneinander unabhängig; Zoomen erzeugt weder Antworten noch Bewertungen.

„Vollbild“ vergrößert die bestehende Player-Instanz auf die Browserfläche; Antworten und laufender Zustand bleiben erhalten. „Vollbild verlassen“ und Escape führen zurück und stellen den Fokus wieder her. Hintergrundbedienung und Seitenscrollen sind währenddessen gesperrt. Diese Regeln gelten auch auf iPadOS 15.3.1 ohne native Dialog-APIs und ohne `inert`, `:modal` oder `:has()`. Moderne Browser dürfen ihre native Dialogebene verwenden; die Gestaltung folgt in beiden Fällen derselben Zustandsklasse und den gemeinsamen Tokens.

### Reparaturvertrag: Live, Diagnostik und Mitglieder

Live und Diagnostik verwenden die vorhandenen Workspace-Flächen, Felder und Aktionsvarianten. Lange Kurs-, Einheiten- und Personennamen dürfen nur innerhalb dafür vorgesehener Tabellenbereiche horizontales Scrollen erfordern, niemals für die ganze Seite. Tabellenbereiche sind beschriftet und per Tastatur erreichbar; schmale Ansichten ordnen Übersicht und Details untereinander an. Reiter besitzen lesbare aktive, Hover- und Fokuszustände in beiden Darstellungen.

Die Live-Aufgabenleiste gruppiert nach tatsächlichem Abschnitt beziehungsweise Modul. Gruppentitel und sichtbare Aufgabennummern ersetzen unbeschriftete Miniaturfelder; die Bewertungslogik bleibt erhalten. Diagnostik beginnt mit einer konkreten Kursauswahl und „Kursmatrix öffnen“, bleibt aber aus der Hauptnavigation verborgen. Profil- und Matrixverweise öffnen die vorhandene Live-Ansicht mit Kurs, Lerneinheit und Lernendem. Mitgliederansichten zeigen verständliche Namen und Aktionen, keine technischen Personenkennungen oder Entwicklungsformulierungen.

Die kanonische Live-Hauptansicht ist eine Schüler-Aufgaben-Matrix. Lernaufgaben
werden nach ihren tatsächlichen Lernmodulen gruppiert; die sticky Namensspalte
enthält keine zusätzliche Bearbeitungsquote. Unmittelbar vor `Üben` fasst eine
88 px breite, rechts fixierte Spalte `Stand` den Lernfortschritt zweizeilig als
`abgegeben/gesamt` und `Ø Bewertung` zusammen. Unbewertete Abgaben zählen nur
zum Fortschritt; Übungsaufgaben fließen in keine der beiden Kennzahlen ein.
Die 72 px breite Spalte `Üben` zeigt ausschließlich zwei beschriftete
Kennzahlen je Schüler: neue beziehungsweise fällige Übungsaufgaben und aktuell
sichere, noch nicht wieder fällige Übungsaufgaben. Übungsaufgaben werden niemals
zwischen den Lernaufgaben einsortiert. Beide kompakten Kennzahlenspalten bleiben
beim horizontalen Scrollen rechts sichtbar. Die lokale Auswahl `Aufgaben |
Üben` verwendet `ChoiceSwitch`.

Die getrennte Übungsansicht ordnet je Übungsmodul eine Spalte an und unterscheidet
`Gesperrt`, `Fällig`, `Noch nicht sicher`, `Teilweise sicher` und `Sicher`.
Farbe unterstützt diese ausgeschriebenen Zustände, ersetzt sie aber nicht.
Auf schmalen Flächen begrenzt eine Modulauswahl die sichtbaren Spalten; Tabelle
und Detail stehen untereinander. Horizontaler Überlauf bleibt auf den
beschrifteten Tabellenbereich begrenzt. Aufgabenstellung, Abgabe, Rückmeldung
und Auswertung bleiben aus Lern- und Übungszellen über denselben Detailbereich
erreichbar. Die Aufgabenleiste im Detailpanel verwendet die nummerierten Bedienflächen aus Abschnitt 5; die frühere Miniaturfeld-Ausnahme ist abgelöst.

Die Live-Tabelle und das Schülerdetail stehen auch auf großen Bildschirmen untereinander und nutzen dieselbe volle Arbeitsbreite. Innerhalb des Details folgen Aufgabenstellung und Antwortbereich ebenfalls untereinander. Die Tabelle nutzt mindestens die verfügbare Breite; bei vielen Aufgaben scrollt ausschließlich der Tabellenbereich horizontal.

GUSTAV ist eine ruhige, moderne Arbeitsanwendung. Vertraute SaaS-Muster für Navigation, Formulare, Reiter, Dialoge und Arbeitsflächen erleichtern die Bedienung und eine konsistente Umsetzung durch Menschen und KI-Agenten.

Verbindliche Zielwahrnehmung:

- klar und gut lesbar
- ruhig und konzentriert
- modern und verlässlich

Logo, Orange als Akzentfarbe und eine konsistente Sprache tragen die Wiedererkennbarkeit. Gemeinsame Komponenten und wenige eindeutige Regeln haben Vorrang vor individuellen Gestaltungsideen pro Seite. Die Aufgabenfläche ist der Primäranker; der Graph verwendet dieselben Farben, Schriften und Bedienelemente.

Die Weiterentwicklung gestaltet vorhandene Inhalte und Abläufe. Sie verlangt keine neuen Lernziele, Aufgabentitel, Zeitangaben oder sonstigen Pflichtangaben von Lehrkräften. Der Entwurf ist keine Erlaubnis, fachliche Zustände, Berechtigungen, Abgaben oder Lernpfade zu verändern.

## 2. Rollen und Grundhaltung

GUSTAV optimiert weiterhin im Zweifel zuerst für Lernende. Lehrkraftflächen
teilen dieselben Flächen, moderaten Rundungen und zugänglichen Kontraste.

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

Die Top-Bar ist kompakt und gegenüber der eigentlichen Arbeit zurückhaltend.

Regeln:

- neutrale Oberfläche mit feiner Trennlinie zum Workspace
- aktiver Navigationszustand bleibt typografisch und durch eine dezente Markierung erkennbar
- Primärnavigation ist textbasiert und verwendet die gemeinsame Leseschrift
- Marke, Navigation und Kontosteuerung teilen eine klare Ausrichtung
- mobile Kopfbereiche umbrechen geordnet; wiederholte Titel und zusätzliche Leerzeilen entfallen

### 3.3 Breadcrumbs

Für Lernende bleiben Breadcrumbs ein Primärelement.

Regeln:

- Schülerpfad bleibt `Lernraum -> Kurs -> Lerneinheit`
- Breadcrumbs sitzen im Lernfluss in der Top-Bar
- Breadcrumbs sind zurückhaltend, klar lesbar und verwenden die gemeinsame Leseschrift
- Breadcrumbs enthalten keine Aktionen

### 3.4 Seitenkopf

Viele Seiten beginnen weiterhin direkt mit der Arbeit.

Regeln:

- kein Hero-Pattern
- Primäraktionen sitzen im Seitenkopf
- Sekundäraktionen bleiben sichtbar, aber schwächer
- Seitenkopf nutzt eine klare Titelhierarchie; eine Meta-Zeile erscheint nur bei zusätzlichem Informationswert

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
- Light verwendet einen dezenten neutralen Seitenhintergrund, helle Inhaltsflächen und orange Akzente
- Dark verwendet abgestufte dunkle Flächen und zurückhaltende Konturen; Text und Bedienelemente bleiben kontrastreich
- neue Komponenten ohne definierte Dark-Regeln sind unvollständig

## 5. Farbe

Die folgende Zielpalette übernimmt die neutralen Flächen des abgestimmten Entwurfs. Werte werden bei der Umsetzung zentral in `theme-tokens.css` gepflegt. Dieses Dokument ändert noch keine Laufzeittokens. Akzentflächen und ihre Vordergrundfarbe bilden immer ein Paar; vor einer Umsetzung sind die Kontraste in beiden Themes zu prüfen.

### 5.1 Light

- `--color-bg-base`: `#f6f7f9`
- `--color-bg-surface`: `#ffffff`
- `--color-bg-muted`: `#f0f2f5`
- `--color-bg-soft`: `#fff0e9`
- `--color-text`: `#242830`
- `--color-text-muted`: `#626b78`
- `--color-link`: `#bd3d1f`
- `--color-accent`: `#c84425`, mit `#ffffff` als Vordergrund auf gefüllten Primäraktionen
- `--color-accent-soft`: `#fff0e9`
- `--color-border`: `#e4e7ec`
- `--color-line`: `#e4e7ec`
- `--color-success`: `#356a50`
- `--color-success-soft`: `#edf5ef`

### 5.2 Dark

- `--color-bg-base`: `#15171b`
- `--color-bg-surface`: `#202329`
- `--color-bg-muted`: `#2a3039`
- `--color-bg-soft`: `#3b2b26`
- `--color-text`: `#edf0f4`
- `--color-text-muted`: `#aeb7c6`
- `--color-link`: `#ff997c`
- `--color-accent`: `#ff9b7e`, mit `#281910` als Vordergrund auf gefüllten Primäraktionen
- `--color-accent-soft`: `#3b2b26`
- `--color-border`: `#363c46`
- `--color-line`: `#363c46`
- `--color-success`: `#9bceb0`
- `--color-success-soft`: `#24382d`

### 5.3 Farbnutzung

- Orange hebt primäre Aktionen und die aktive Auswahl hervor. Ein offener oder begonnener Zustand erhält keine konkurrierende große Akzentfläche.
- Zustände werden verständlich beschriftet; Farbe und Symbole unterstützen die Bedeutung. Grün als Erfolg und eine grün getönte KI-Nachricht werden durch Beschriftung und Kontext eindeutig unterschieden.
- Konturen von Inhaltsflächen und dekorative Trennlinien sind dezent. Erforderliche Feldgrenzen, Fokus- und Auswahlmarkierungen erhalten stärkere, kontrastgeprüfte Farben; die leichten Strukturfarben reichen dafür allein nicht aus.
- Warnungen und Fehler behalten eigene semantische Tokenpaare für Light und Dark. Bestehende Werte werden bei der Umsetzung auf den neuen Flächen geprüft, nicht ersatzlos entfernt.
- Hover verändert Fläche oder Textfarbe zurückhaltend; Farben entstehen aus gemeinsamen Tokens statt lokalen Einzelwerten.
- Es gibt keine zonenspezifischen Farbwelten für Rollen.

### Live-Aufgabenfelder: verbindliche Bewertungsfarben

Die bisherige Live-Bewertungspalette bleibt erhalten. Ihre Werte liegen ausschließlich als `--color-live-score-*` und `--color-live-on-*` in `theme-tokens.css`; Komponenten dürfen keine eigenen Farbtöne festlegen. Die folgenden Farbpaare gelten für die nummerierten Aufgabenfelder, nicht für allgemeine Erfolgsmeldungen.

| Bewertung | Fläche Hell | Text Hell | Fläche Dunkel | Text Dunkel |
|---|---|---|---|---|
| 0 (`zero`) | `#7a0000` | `#ffffff` | `#ff4d4d` | `#000000` |
| über 0 bis unter 4 (`low`) | `#c62828` | `#ffffff` | `#ff6b57` | `#000000` |
| 4 bis unter 8 (`mid`) | `#d87a00` | `#000000` | `#ff9a2f` | `#000000` |
| ab 8 (`high`) | `#2f8f5b` | `#000000` | `#49b36f` | `#000000` |

Offene Aufgaben bleiben ungefüllt (`transparent`) mit gestrichelter Kontur in `--color-control-border` und Text in `--color-text`. Abgegebene, noch unbewertete Aufgaben verwenden die blaue Informationsfläche `--color-info-soft` mit durchgezogener Kontur und Text in `--color-info`. Damit unterscheiden sich beide Zustände durch Fläche und Rahmenform, nicht allein durch Farbe. Die gemeinsamen Tokens bestimmen beide Themes; lokale Farbwerte sind nicht zulässig. Die vollständige Beschriftung unterscheidet „Noch offen“ und „Noch unbewertet“. Zahlen bleiben lesbar; die Bewertung wird zusätzlich in der Statuszeile und der zugänglichen Beschriftung angegeben.

Auswahl und Bewertung sind getrennte Zustände: Eine Umrandung in der gemeinsamen Akzentfarbe mit 2 px Abstand markiert die Auswahl, ohne die Bewertungsfläche zu ersetzen. Ein zusätzlicher orangefarbener Unterstrich für die jüngste Abgabe entfällt. Die größeren nummerierten Bedienflächen bleiben erhalten.

## 6. Typografie

Die Oberfläche verwendet eine gut lesbare Sans-Serif als gemeinsame Schriftfamilie. Hierarchie entsteht durch Größe, Gewicht, Abstand und Farbe.

Rollen:

- `Reading Sans`: Standard für Inhalte, Navigation, Buttons, Formularbeschriftungen, Status und Breadcrumbs.
- `Display Sans`: verwendet dieselbe Familie mit stärkerem Gewicht für Seiten- und Modultitel; keine eigenständige technisch-breite Titelschrift.
- `Technical Mono`: bleibt Code, technischen Kennungen und fachlich notwendigen tabellarischen Ausrichtungen vorbehalten.

Regeln:

- Standardtext und Bedienelemente verwenden 14–16 px, längerer Lesetext und Eingabefelder mindestens 16 px; Metadaten 12–14 px.
- Seitentitel verwenden ungefähr 24–28 px, Bereichstitel 16–20 px. Überschriften im Material bleiben der umgebenden Modulhierarchie untergeordnet.
- Fließtext verwendet eine Zeilenhöhe von ungefähr 1,5–1,7 und bleibt auf etwa `68ch` begrenzt.
- Beschriftungen stehen in normaler deutscher Schreibweise. Versalien und zusätzliche Laufweite sind kurzen, sparsam eingesetzten Bereichsmarkern vorbehalten.
- Lesbarkeit hat Vorrang vor Dichte. Zoom und größere Schrift dürfen keine Inhalte oder Aktionen abschneiden.

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

Der Standardabstand zwischen benachbarten Arbeitsbereichen beträgt `--space-4` (16 px). Zusammengehörige Elemente verwenden 4–8 px, Inhaltsflächen 16–24 px Innenabstand und größere Abschnittswechsel 24–32 px. Die Skala beschreibt Beziehungen; freie Höhe wird nicht durch gestreckte Felder oder dekorative Leerzonen gefüllt.

### 7.2 Radius

Zielwerte für die gemeinsamen Tokens:

- `--radius-s`: `4px` für kleine Markierungen
- `--radius-m`: `8px` für Buttons, Felder und Inhaltsflächen
- `--radius-l`: `12px` für Dialoge und Popover
- `--radius-xl`: `12px`; größere Rundungen sind kein Standardmuster

Neue Inhaltsflächen verwenden 8 px. Avatare dürfen kreisförmig bleiben; Modusumschalter und gewöhnliche Aktionen erhalten keine beliebig wechselnden Pillenformen.

### 7.3 Flächen

- Ein neutraler Seitenhintergrund und wenige klar abgegrenzte Inhaltsflächen bilden die Grundstruktur.
- Inhaltsflächen verwenden eine feine Kontur und standardmäßig keinen Schatten. Unterabschnitte werden mit Abstand oder Trennlinien gegliedert, nicht jeweils neu eingerahmt.
- Buttons, Eingabefelder und ausgewählte Elemente bleiben als bedienbare Objekte erkennbar. Nicht jedes Textelement erhält eine Karte.
- Subtile Schatten kennzeichnen primär schwebende Menüs, Popover und Dialoge. Harte versetzte Schatten und dekorative Tiefenstaffelungen entfallen.
- Das Punktraster ist auf die Graphfläche begrenzt und bleibt dort zurückhaltend. Lesen, Schreiben, Rückmeldungen und gewöhnliche Formulare verwenden ruhige Hintergründe.

### 7.4 Motion

- Hover-, Fokus- und Auswahlzustände reagieren subtil und konsistent.
- Kurze Farb- und Konturübergänge unterstützen die Bedienung; Buttons springen nicht durch Translate- oder Schatteneffekte.
- Bewegung ist für das Verständnis nie erforderlich und respektiert `prefers-reduced-motion`.

## 8. UI-Sprache

Die UI-Sprache ist kurz, verständlich und situationsbezogen. Sie benennt Handlungen und Zustände mit vertrauten Begriffen aus dem Produkt. Lernende werden einheitlich mit „du“ angesprochen.

### 8.1 Textökonomie

- Jeder UI-Text erfüllt einen konkreten Zweck: eine Handlung benennen, eine benötigte Information vermitteln oder einen relevanten Zustand beziehungsweise eine Folge erklären.
- Überschrift, Beschreibung und Aktion wiederholen nicht dieselbe Aussage. Bereits sichtbarer Kontext wird nicht erneut erläutert.
- Vertraute Bedienelemente benötigen keine Gebrauchsanweisung. Formulierungen wie „Klicke hier, um …“, Einleitungen über gewöhnlichen Formularen und Erklärungen normaler Reiter entfallen.
- Beschriftungen sind kurz und eindeutig. „Speichern“ genügt bei klarem Bearbeitungskontext; bei einer folgenreichen Aktion wie „Kurs löschen“ wird das betroffene Objekt ausdrücklich genannt.
- Hinweise erscheinen am relevanten Ort und im relevanten Zustand. Statische Hilfetexte sind nur zulässig, wenn eine tatsächliche Anforderung oder Unklarheit sonst verborgen bliebe.
- Leere Flächen werden nicht mit Begrüßungen, Motivation, Tipps, Zusammenfassungen oder künstlichen Kennzahlen gefüllt. Ein leerer Zustand nennt bei Bedarf knapp den Grund und eine verfügbare nächste Aktion.
- Aufgabenstellungen, Materialien und fachlich notwendiges Feedback sind Lerninhalte. Sie werden durch diese Regel weder automatisch gekürzt noch inhaltlich verändert.
- Kürze darf Sicherheit und Zugänglichkeit nicht beeinträchtigen: notwendige Feldbeschriftungen, Formatvorgaben, Fehlermeldungen, Hinweise zu Datenverlust, Datenschutz und endgültigen Aktionen bleiben erhalten. Symbole erhalten verständliche zugängliche Namen; Platzhalter ersetzen keine Labels. Pflichtinformationen werden nicht ausschließlich in Tooltips versteckt.

### 8.2 Verbindliche Regel für KI-Agenten

Neue UI-Texte benötigen einen konkreten Informationsbedarf. Ergänze keine erklärenden Untertitel, Hilfetexte oder Statusmeldungen allein deshalb, weil Platz vorhanden ist. Prüfe zuerst, ob Struktur, Platzierung oder ein bestehendes Bedienelement die Information bereits vermitteln. Entferne redundante Texte vor der Fertigstellung.

Die Prüfung erfolgt bei jeder UI-Änderung:

1. Welche Entscheidung oder Handlung unterstützt dieser Text?
2. Steht dieselbe Information bereits sichtbar im Kontext?
3. Reichen eine eindeutige Beschriftung und eine bessere Anordnung aus?
4. Bleibt ohne den Text eine notwendige Information zu Sicherheit, Zugänglichkeit oder Bedienung verborgen?

Fehlt ein konkreter Zweck, entfällt der Text. Ein längerer Text braucht einen tatsächlichen Informationsbedarf, keine rein dekorative Begründung.

| Situation | Bevorzugte Darstellung |
| --- | --- |
| Formular mit bereits sichtbarer Überschrift „Kurseinstellungen“ | Felder und „Speichern“; keine zusätzliche Einleitung „Hier kannst du deine Kurseinstellungen bearbeiten.“ |
| Reiter „Materialien“ | Materialliste; keine unmittelbar wiederholte Überschrift mit gleichem Wortlaut |
| Aufgabe mit vorhandener Startaktion | „Aufgabe beginnen“; kein zusätzlicher Satz „Klicke auf den Button, um die Aufgabe zu beginnen.“ |
| Dateiauswahl mit einer notwendigen Formateinschränkung | „Bild oder PDF“ unmittelbar am Feld |
| Fehlgeschlagenes Speichern | Knapp benannter Fehler und eine tatsächlich mögliche Wiederherstellungsaktion |

### 8.3 Aktionen

- `accent` für Primäraktionen im jeweiligen Arbeitskontext
- `quiet` für normale Sekundäraktionen
- `subtle` für kleine, nicht-dominante Nebenaktionen wie `Pausieren`, `Schließen` oder `Bearbeiten`
- Aktionen teilen Schriftfamilie, Radien und Höhen; Gewichtung entsteht durch Farbe und Kontur, nicht durch wechselnde Formensprache.

## 9. Accessibility

Accessibility ist Teil des Designvertrags.

Regeln:

- hohe Kontraste in Light und Dark
- klare Fokuszustände
- vollständige Tastaturbedienbarkeit
- semantische Struktur, zugängliche Namen und notwendige Hinweise bleiben unabhängig von visueller Reduktion erhalten

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

Die Detailreiter der Live-Ansicht teilen diese visuelle Basis über `choice-tabs`: identische Schrift, Grundlinie, Akzentlinie sowie Hover- und Fokuszustände, keine aktive Füllfläche. Die Semantik bleibt getrennt: native Radiofelder für die Auswahl, `tablist`/`tab`/`tabpanel` für Detailinhalte. Überflüssige Überschriften wie „Detail“ und Wiederholungen des aktiven Reiternamens im Inhalt entfallen; die zugängliche Panelbeschriftung bleibt erhalten.

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
  durchlaufen dieselben Stufen. Ein sichtbarer Rückweg verwendet den nativen
  Browser-Verlauf nur dann, wenn GUSTAV das bezeichnete Ziel als exakte
  Elternstufe dieses Eintrags angelegt hat; nach Direktaufruf oder Neuladen wird
  stattdessen die kanonische Ziel-URL hergestellt. Alte `view`- und
  `history`-Links werden sicher normalisiert.
- Die URL bestimmt nach einem Neuladen die sichtbare Stufe. Schülerbezogene
  lokale Speicherung ergänzt nur geöffnete Module, Lesepositionen, Kontext und
  Entwürfe.

### 11.2 Lernpfad

Lehrkraft- und Schüleransicht verwenden für dieselbe modulare Lerneinheit dieselbe Graphgeometrie: Phasenreihenfolge, relative Knotenpositionen, Knotengrößen und Anschlusspositionen stimmen überein. Statusfarben, Fortschritt, Auswahl und Bearbeitungsaktionen sind dagegen rollenbezogen. Die gemeinsame Steuerung trennt einen lesbaren Startfokus von der bewussten `Gesamtansicht`; diese darf auch auf schmalen Bildschirmen unter die Lesevergrößerung herauszoomen. Nach dem einmaligen Startfokus setzen Datenaktualisierungen den gewählten Ausschnitt nicht automatisch zurück. Lernende erhalten keinen Schalter zum Aktivieren der Knotenbearbeitung.

- Graph bleibt Phasen-zentriert
- Knoten verwenden die gemeinsamen 8-px-Radien, ruhige Flächen und dezente Konturen; Titel dominieren gegenüber Nummern und Bestandszahlen
- aktive Auswahl ist orange markiert; Bearbeitungszustand und Tastaturfokus bleiben davon unterscheidbar
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
- `Materialien` und `Aufgaben` sind zurückhaltende Bereichsüberschriften in normaler Leseschrift; der Modultitel bleibt die stärkste Ebene
- Zwei Zeilen für lange Modultitel sind erlaubt; der Modulkopf wächst nicht
  beliebig
- Der Abstand vom Modulkopf zum ersten Abschnitt ist größer als der Abstand vom
  Abschnittslabel zu seinem Block
- Rückmeldung, Auswertung und die zugehörige Abgabe verwenden gemeinsame, ruhige Offenlegungen mit feinen Trennlinien; ihre fachliche Hierarchie bleibt erhalten
- kompakte Task-Zeilen im modularen Lernraum nutzen eine Vorschauzeile statt
  redundanter Status-/Titellabels. Die Vorschau wird lesbar aus der
  Markdown-Aufgabenstellung abgeleitet.
- Lange oder mehrteilige Aufgaben dürfen in dieser Vorschau höchstens zwei
  Zeilen belegen und erhalten den sichtbaren Hinweis `Weitere Angaben in der
  Aufgabe`. Unter `48rem` steht die Startaktion darunter und nimmt die
  verfügbare Breite ein.
- Relevante Zustände erhalten eine knappe verständliche Beschriftung; Balken, Tönung oder Symbol unterstützen sie. Eine bereits eindeutige Aktionsbeschriftung wird nicht durch ein gleichlautendes Statuslabel wiederholt.
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

#### Eigene Abgaben in der Leseansicht

In Modulen und linearen Abschnitten bleibt die kompakte Aufgabenstellung sichtbar und erhält keine Offenlegung. Direkt darunter steht die eigene Abgabe: zunächst höchstens drei gerenderte Zeilen einer lesbaren Textvorschau. Nur die Abgabe wird über die dezente Aktion „Ausklappen“ verlängert. „Meine Abgabe“ und Zeitpunkt benennen den Snapshot; „Abgegeben“ beschreibt ausschließlich den Abgabestatus. Ohne endgültige Abgabe heißt der gespeicherte Feedback-Stand „Mein Entwurf · Noch nicht abgegeben“. Eine endgültige Abgabe hat Vorrang; ein neuerer gespeicherter Entwurf erhält einen eigenen Hinweis und die Aktion „Entwurf weiterbearbeiten“.

Aufgabe und Abgabe bilden einen zusammenhängenden Lesebereich. Die eigene Antwort steht leicht eingerückt und ohne eigenständige Karte, Außenrahmen oder abgetrennte Tabellenkopfzeile darunter. Die Aufgabenstellung bleibt in normaler Leseschriftgröße erkennbar, Metadaten treten zurück. Drei Vorschauzeilen sind eine Obergrenze: Kurze Antworten erzeugen keine künstliche Leerfläche. Bearbeitungsaktionen für bestehende Abgaben sind nachgeordnet und verzichten hier auf Schatten und Versalschreibung.

Der gemeinsame Lesebereich von Aufgabe und Antwort besitzt einen ruhigen Hintergrund ohne durchscheinendes Punktraster. Die Einrückungen folgen festen Achsen; Antworttext und Beschriftungen der zugehörigen Offenlegungen stehen bündig. Metadaten bleiben klar getrennt und nachgeordnet. Auf breiten Flächen kann die dezente Aufklappaktion neben der geschlossenen Antwort am unteren rechten Rand stehen; auf schmalen Flächen folgt sie darunter. Lesetext bleibt auf ungefähr `68ch` begrenzt.

Am Ende der verlängerten Abgabe stehen „Rückmeldung“ und „Auswertung“ als getrennte, zunächst geschlossene Offenlegungen innerhalb derselben Abgabefläche. Beide Aufklappzeilen verwenden dieselbe Leseschrift, links platzierte Chevrons und je eine feine Trennlinie. Die Auswertung verwendet die bestehenden qualitativen Kriterien und anfangs geschlossene Kriterienbegründungen. Fehlende Inhalte erzeugen keine leeren Bereiche. „Einklappen“ schließt die untergeordneten Offenlegungen. Kurze Antworten benötigen „Ausklappen“ nur bei zusätzlichen Inhalten oder Verarbeitungszuständen. Diese Anordnung gilt ausschließlich für die Leseansicht; Aufgabenraum und Materialkontext behalten ihre eigene Hierarchie.

Bilder erscheinen klein und unverzerrt; PDFs und andere Dateien beginnen mit tatsächlich verfügbaren Metadaten. Umfangreiche Datei-, Code- und Dialogdarstellungen werden erst beim Öffnen eingebunden. Die Vorschau verwendet zentrale Farben, Typografie und Abstände in Hell und Dunkel. Die dezenten Textbuttons besitzen mindestens 44 Pixel Bedienhöhe, sichtbaren Fokus und aria-expanded/aria-controls. Öffnen verändert weder URL noch Browserhistorie; Abgabetexte werden nicht zusätzlich lokal gespeichert.

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
- Oberhalb der Bearbeitung steht `Rückmeldung` als inhaltliches Dach. Das
  formative `feedback_md` steht zuerst; tatsächliche Kriterienergebnisse folgen
  darin als verschachtelte Offenlegung `Kriterien im Detail`. `Meine Abgabe`
  bleibt eine getrennte Offenlegung und zeigt unverändert den Snapshot, auf den
  sich die Hinweise beziehen. Leere Bereiche und Platzhalter werden nicht
  gerendert.
- Lernende sehen Kriterienwerte qualitativ als `Mangelhaft` (0–2),
  `Ansatzweise` (3–6), `Gelungen` (7–8) oder `Hervorragend` (9–10). Bei einem
  anderen Maximum wird der Wert ohne Rundung auf die Zehnerskala normalisiert;
  ungültige Werte erscheinen als `Ohne Einstufung`. Die numerischen Scores
  bleiben in der Lehrkraftdiagnostik erhalten. `Kriterien im Detail` öffnet
  eine nummerierte Liste; jede Zeile lässt sich für ihre Begründung einzeln
  öffnen. Kleine entsättigte Statusmarken unterscheiden die Stufen zusätzlich,
  ohne die ausgeschriebene Bezeichnung durch eine Ampellogik zu ersetzen. Beim
  Öffnen der Liste sind alle einzelnen Kriterien zunächst geschlossen.
- `Rückmeldung einholen` wechselt nicht auf eine andere Seite. Während der
  Verarbeitung sind Editor, Antwortform, Dateiauswahl und Abgabeaktionen
  gesperrt. Sowohl `Rückmeldung einholen` als auch `Abgeben` zeigen
  unmittelbar einen sichtbaren Verarbeitungsstatus und verhindern weitere
  Abgabeversuche. Erfolg bleibt in der Aufgabenfläche erkennbar; bereinigte
  Fehler erscheinen dort mit einer möglichen nächsten Aktion. Nach
  erfolgreicher Verarbeitung und beim direkten Öffnen der Ergebnisansicht
  öffnet sich `Rückmeldung` inline, ohne den Tastaturfokus ungefragt zu
  verschieben. Manuelles Schließen wird durch Polling nicht rückgängig gemacht.
  Der flache Aktionsbereich bündelt danach die Entscheidung: `Abgeben` schließt die geprüfte Fassung ab, `Überarbeiten` bleibt als Nebenaktion erreichbar. `Überarbeiten` verschiebt
  den Fokus erst nach einer ausdrücklichen Aktivierung zum Texteditor
  beziehungsweise Dateifeld. Die Abschlussaktion wird nicht zusätzlich unter
  dem Editor wiederholt.
- Bei einer Textänderung gegenüber dem geprüften Snapshot, auch nach dem Wechsel von Bild zu Text, bleibt die bisherige Rückmeldung lesbar und `Neue Rückmeldung einholen` erreichbar. `Abgeben` öffnet dann die Warnung `Überarbeitung noch nicht geprüft`: `Weiter überarbeiten` kehrt zur Eingabe zurück; `Trotzdem abgeben` finalisiert ausdrücklich den zuvor geprüften Snapshot. Eine neu ausgewählte Datei benötigt zuerst Rückmeldung und sperrt die Abschlussaktion. Nach der Finalisierung bleibt der Aufgabenraum sichtbar und wird schreibgeschützt.
  `Aufgabe abgeschlossen` führt bei einer anderen noch offenen Aufgabe im selben
  Modul zurück zur Modulansicht, andernfalls zum Lernpfad. Eine Aufgabe mit
  formativer Rückmeldung, aber ohne endgültige Abgabe, gilt weiterhin als offen;
  bereits endgültig abgegebene Aufgaben werden nicht berücksichtigt. Es gibt
  keinen automatischen Sprung in eine Aufgabe oder ein anderes Modul. In linearen
  Lerneinheiten führt der Abschluss zurück zu den Inhalten. Ein erlaubter weiterer
  Versuch öffnet die Aufgabe erneut zur Bearbeitung.

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

- Die Abfolge „Gespräch → Abschlussaufgabe → Abgabe“ kündigt einen vorhandenen Abschlussauftrag früh an. `Zur Abschlussaufgabe` öffnet dessen Bearbeitung; ohne Abschlussauftrag heißt die Aktion `Zur Abgabe`.
- Die linke Spalte zeigt wie bei anderen Aufgaben zuerst `Aufgabe N · KI-Dialog`
  und die Aufgabenstellung, anschließend den unveränderten gemeinsamen
  Materialbrowser. Dialogeigene Partnerkarten, Sonderrahmen und abweichende
  Materialflächen sind dort nicht zulässig.
- Partnername, Antwortmodus und Rundenstand stehen im Dialogkopf rechts.
  `Dialog ohne Abgabe abbrechen`, optional `Pausieren` und `Zur Abschlussaufgabe` beziehungsweise `Zur Abgabe` gehören zu den
  Sitzungsaktionen im Hauptbereich und werden nicht in der Materialspalte
  dargestellt.
- Ein fehlgeschlagener KI-Turn mit verbleibenden Generierungsversuchen zeigt
  `KI-Antwort erneut versuchen` und, sofern bereits eine Runde abgeschlossen
  wurde, weiterhin `Zur Abschlussaufgabe` beziehungsweise `Zur Abgabe`. Nach dem dritten Fehlversuch entfällt die
  Wiederholungsaktion vollständig; Abschluss beziehungsweise erlaubter Abbruch
  bleiben als erreichbare Auswege sichtbar.
- `Antwort senden` steht ausschließlich unmittelbar beim Eingabefeld. In der Abschlussphase stehen `Zurück zum Gespräch` und `Gespräch und Antwort abgeben` beim Abschlussfeld. Ohne Abschlussauftrag heißt die abschließende Aktion `Gespräch abgeben`.
- Der Hauptbereich beginnt mit Partnername, Modus, dem sichtbaren Text `Runde X
  von N` und einem zugänglichen Fortschrittsbalken. Er zeigt ausschließlich den
  tatsächlichen Rundenstand. Die angekündigte Abfolge beschreibt zusätzlich die vorhandenen Schritte bis zur Abgabe; sie verändert keine fachlichen Sitzungszustände.
- Auf breiten Flächen besteht der Hauptbereich aus drei Zeilen: Fortschritt,
  intern scrollbarer Verlauf und Eingabe beziehungsweise Abschluss. Nach dem
  Laden, einer neuen KI-Antwort und einer Größenänderung bleibt die aktuelle
  Frage vollständig sichtbar; der Tastaturfokus wird dabei nicht verschoben.
- KI-Beiträge stehen links mit ruhiger Rollenbeschriftung; Schülerbeiträge stehen rechts auf einer dezenten neutralen Fläche.
  Dekorative Seitenleisten und zusätzliche Innenrahmen sind im Dialog verboten.
- Genau die jüngste beantwortbare KI-Nachricht trägt die sichtbare Kennzeichnung
  `Aktuelle Frage` und eine stärkere Kontur. Frühere Beiträge bleiben vollständig
  verfügbar, erhalten aber keine konkurrierende Hervorhebung.
- Sprecher werden knapp und eindeutig bezeichnet. Verwendete Satzanfänge
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
- Alle produktiven `.dialog-*`-Regeln liegen im fachlichen Stylesheet
  `frontend/src/lib/styles/learning-unit.css`. Lokal begrenzte Dialogvariablen
  für Rundungen und Mischflächen werden aus den zentralen Farb- und
  Typografietokens abgeleitet und verändern keine andere Aufgabenart.
- Das UI-Labor zeigt Gespräch und Abschluss jeweils als vollwertige
  Referenzfläche in Light und Dark sowie auf Desktop, Tablet und Smartphone.

Im laufenden Gespräch bleiben sämtliche Beiträge ohne Aufklappen zugänglich. Ada steht links mit ruhiger Rollenbeschriftung; eigene Antworten stehen rechts auf einer dezenten neutralen Fläche. Farbbalken und dekorative Avatare entfallen. Nach der Abgabe steht die Abschlussantwort zuerst. In der Ergebnisansicht ist die Rückmeldung geöffnet; Verlauf und Auswertung lassen sich unabhängig aufklappen. Fehlende Abschlussantworten erzeugen keinen leeren Platzhalter. Die vollständige Referenzlesefassung bleibt verfügbar.

Der optionale Abschlussauftrag wird im KI-Dialog früh durch die kurze Abfolge „Gespräch → Abschlussaufgabe → Abgabe“ angekündigt. Aktionen benennen den nächsten Schritt: „Zur Abschlussaufgabe“, ohne Abschlussauftrag „Zur Abgabe“. Der Auftrag steht sowohl beim Schreiben als auch in der gespeicherten Abgabe direkt bei der eigenen Antwort. „Fazit“ oder „Zusammenfassung“ werden nicht pauschal unterstellt. Gesprächsbeiträge bleiben Teil der Abgabe.

Abgeschlossene KI-Dialoge verwenden dieselbe Abgabedarstellung wie die Modulansicht. Auftrag und eigene Abschlussantwort bleiben sichtbar; Rückmeldung ist in der Ergebnisansicht geöffnet, der Verlauf aufklappbar. Die Ergebnisansicht wächst mit dem Inhalt statt die Gesprächsfläche auf volle Höhe zu strecken. Eine sichtbare Rückkehraktion nutzt das bestehende Rücksprungziel. Ergebnisadressen laden ausschließlich die Sitzung der zugehörigen Abgabe und starten keinen neuen Dialog.

### Reparaturvertrag: Wiederholung und Druckfassung

Eine Aufgabenpräsentation mit `presentation_number > 1` trägt sichtbar „Wiederholung“. Ein kurzer Text erklärt, dass dieselbe Aufgabe erneut geübt wird und die bisherigen Antworten erhalten bleiben. Der Hinweis bleibt bei Antwort und Rückmeldung sichtbar; die erste Präsentation erhält ihn nicht. Zähler, Bewertungslogik und gespeicherte Antworten werden dafür nicht verändert. Darstellung und Abstände nutzen die vorhandenen Practice- und Textbausteine.

In der Druckfassung erhalten Abschnitts-/Modulüberschriften einen einheitlichen Abstand zum vorherigen Inhalt. Überschriften bleiben mit dem Beginn des nächsten Inhalts zusammen; lange Inhalte dürfen regulär über mehrere Seiten laufen. Die bestehende sichere Markdown-Ausgabe, Bildprüfung, importierten PDF-Seiten, A4-Ränder und Seitenzählung bleiben erhalten. Der Abstand zwischen Inhaltsüberschrift und Text wird nicht mit dem größeren Abstand zwischen Abschnitten verwechselt.

### Druckgestaltung vom 13. September 2026

- Arbeitsblätter sind ruhig und schwarz-weiß kopierbar: vorhandene lokale Schrift, Fließtext 11 pt mit Zeilenhöhe 1,45, Titel 18 pt, Abschnitt/Modul 14 pt und Material/Aufgabe 12 pt. Überschriften innerhalb des verfassten Markdown-Inhalts sind kleiner als die Materialüberschrift.
- Ein kompakter Kopf enthält den umbrechenden Einheitstitel und Name/Kurs/Datum. Dünne schwarze Abschnittslinien und einheitliche Abstände gliedern die Inhalte. Keine zusätzlichen Logos, Farbflächen, Antwortflächen oder Druckoptionen.
- Überschriften bleiben beim Folgeinhalt; lange Texte dürfen Seiten wechseln. Fußzeilen bleiben klar vom Inhalt getrennt, auch bei eingebundenen PDF-Seiten.
- Bei Grafiken entfällt die automatisch angehängte Dateinamenzeile. Materialtitel, Beschreibung, Bild und bewusst verfasste Dateinamen bleiben unverändert. Lesbarkeit geht vor Platzersparnis: keine pauschale Verkleinerung, kein Beschnitt und keine Verzerrung; bisherige Größenbegrenzungen bleiben bestehen.
- Importierte PDFs behalten Gestaltung und Ausrichtung. Nur die von GUSTAV ergänzten Kopf-/Fußbereiche werden vereinheitlicht; die Dateinamenregel gilt zunächst ausschließlich für Grafiken.

### Übergreifende Nachbesserung vom 12. September 2026

- Mobile Headeraktionen bilden ein Paar: Theme-Schalter und Benutzerbutton teilen dieselbe Höhe von 44 px und mindestens 44 × 44 px Bedienfläche. Die Desktophöhe bleibt unverändert.
- „Aufgabe beginnen“ und „Entwurf weiterbearbeiten“ sind gleich gewichtete orange Hauptaktionen. Erst „Erneut bearbeiten“ nach endgültiger Abgabe bleibt dezent; die Zustandsmarkierung der Aufgabenzeile ist davon unabhängig.
- Historisch: Die Miniaturfeld-Ausnahme vom 12. September ist durch die am 22. Oktober eingeführten nummerierten Bedienflächen abgelöst. Maßgeblich sind Abschnitt 5 und der Vertrag „Live, Diagnostik und Mitglieder“; die alte Ausnahme ist keine aktuelle Implementierungsvorgabe.

## 12. Auth und Preview

- Auth gehört sichtbar in dieselbe Produktsprache
- `/ui-lab` ist die interne Referenzfläche
- `/ui-lab` muss Shell, Task-Sprache, Graph-Sprache, Auth und Theme-Wechsel
  gleichzeitig zeigen

## 13. Verbotene Alt-Muster

- harte versetzte Schatten und schwere Rahmen als Standard auf jeder Fläche
- technische Monospace-Schrift, Versalien und gesperrte Beschriftungen als allgemeine UI-Sprache
- Punktraster hinter Lese- und Schreibinhalten
- wechselnde Rundungen, übergroße Pillen und individuelle Buttonformen pro Seite
- verschachtelte Karten ohne funktionale Gruppierung
- dekorative Verläufe, übergroße Überschriften und unnötige Dashboard-Kennzahlen
- erklärende Untertitel, Hilfetexte und Statusmeldungen ohne zusätzlichen Informationswert
- lokale Farb- und Abstandsvarianten außerhalb der gemeinsamen Tokens

## 14. Technische Pflege des Designsystems

`frontend/src/lib/styles/index.css` ist der einzige globale CSS-Einstiegspunkt. Er importiert die Stylesheets in folgender Reihenfolge:

1. `theme-tokens.css`
2. `app.css`
3. `typography.css`
4. `ui-primitives.css`
5. `learning-unit.css`
6. `practice.css`
7. `teaching-workspace.css`
8. `auth-theme.css`
9. `overrides.css`
10. `navigation.css`
11. `teacher-theme.css`

Die Importreihenfolge ist die lesbare Ordnungs- und Prioritätsregel für den Quellcode. GUSTAV verwendet hier bewusst keine CSS Cascade Layers: Safari auf iPadOS 15.3 versteht sie noch nicht und würde sonst fast das gesamte globale Stylesheet verwerfen. Ein Build-Gate parst alle erzeugten Client-Stylesheets und bricht ab, falls dort trotzdem eine `@layer`-Regel oder ein mit `layer(...)` qualifizierter `@import` vorkommt. Dadurch erhalten alte und aktuelle Browser dasselbe einfache CSS ohne browserspezifischen Sonderpfad.

Verbindliche Regeln:

- `theme-tokens.css` ist die einzige Quelle für globale `--color-*`, `--font-*`, `--space-*` und `--radius-*`-Variablen.
- Fachliche Stylesheets dürfen globale Tokens verwenden, aber nicht neu definieren.
- Eindeutig fachlich benannte, komponentenlokale Variablen bleiben erlaubt.
- Neue globale Stylesheets werden nicht direkt in `+layout.svelte` importiert, sondern an der fachlich passenden Position in `index.css` eingebunden.
- `@layer` und Layer-Zusätze an `@import` werden im globalen CSS nicht verwendet und dürfen auch nicht im erzeugten Client-CSS vorkommen.
- Benachbarte Bedienelemente mit derselben Funktionsebene teilen gemeinsame Chrom-Regeln; Theme- und Account-Schalter der Top-Bar sind die Referenz dafür.
- Die ehemalige warme Papier-/Petrolpalette darf nicht lokal über hart codierte Werte zurückkehren.

Das UI-Labor und ausgewählte vollständige Arbeitsansichten besitzen am 22. Oktober 2026 abgeglichene Light- und Dark-Referenzbilder für Desktop und Mobil. Sie dokumentieren den geprüften Implementierungsstand. Bei weiteren Änderungen ersetzt eine bloße Aktualisierung der Referenzbilder keine Sichtprüfung. Der Moduleditor wird als echte, authentifizierte Arbeitsansicht bei 1920 × 1080, 1024 × 768 und 390 × 844 Pixeln geprüft. `make test-visual-smoke` vergleicht diese Referenzen, während `make update-visual-baselines` ausschließlich für eine beabsichtigte und anschließend visuell geprüfte Designänderung verwendet wird.


### Seitenkomposition der Lernansichten

Die Aufgabenansicht hat eine einzige Hauptüberschrift für die aktive Aufgabe und einen kompakten Rückweg zum Modul. Eine zusätzliche Lernpfad-Leiste entfällt während der Bearbeitung; Layout-Einstellungen bleiben erreichbar. Aufgabenstellung und Materialien bilden den unterstützenden Kontext, die Antwort erhält die zusammenhängende hervorgehobene Arbeitsfläche. Überschriften in Materialauszügen bleiben der Aufgabenhierarchie visuell untergeordnet. Die Antwortform ist direkt an der Eingabe angeordnet und benötigt keine zusätzliche sichtbare Erklärung. Während der Bearbeitung ist die Rückmeldungsanforderung die Primäraktion; Überarbeiten ist eine Nebenaktion. Bestehende Bedingungen für die endgültige Abgabe bleiben unverändert.

In der modularen Leseansicht trägt der Modultitel die visuelle Hierarchie; der bereits im Breadcrumb sichtbare Lerneinheitstitel wird nicht nochmals groß wiederholt. Das Inhaltsverzeichnis ist eine zurückhaltende Navigation statt einer zusätzlichen umrahmten Inhaltskarte. Auf schmalen Bildschirmen bleiben Kopfzeile und Breadcrumb kompakt, ohne erreichbare Navigation oder Bedienelemente zu entfernen.


### Inhaltsnavigation in der Modulansicht

Die Modulnavigation folgt der Reihenfolge der Leseansicht: Materialien, dann Aufgaben. Ein Dokument- bzw. Stiftsymbol unterscheidet die Inhaltstypen; ein Häkchen wird nicht als allgemeines Aufgabensymbol verwendet, weil es Abschluss suggeriert. Der aktuelle Eintrag wird anhand der Leseposition mit dezenter Akzentfläche, stärkerer Schrift und `aria-current="location"` markiert. Beim Wechsel der Leseposition in ein anderes Modul öffnet sich dessen Gruppe; Modulgruppen bleiben manuell aufklappbar. Dekorative Striche vor jedem Eintrag entfallen.

Bis einschließlich 64 rem startet die Navigation geschlossen als kompakte Zeile „Inhalt“ mit aktuellem Modulnamen. Nach Auswahl eines Eintrags schließt sie und fokussiert den Zielinhalt. Auf größeren Ansichten bleibt die Navigation sichtbar. Zielpositionen berücksichtigen die feste Kopfzeile, Einträge und Gruppen bleiben mindestens 44 px hoch.

### Gemeinsame Seitennavigation
Modulansicht und Aufgabenräume verwenden dieselbe `WorkspaceOutline` für Modulgruppen, Materialzeilen, Symbole und aktive Auswahl. Dialog-, Text- und Dateiaufgaben binden sie über `LearnerTaskContext` ein. Materialien stehen vor eigenen Abgaben. Im Aufgabenraum öffnet die Auswahl den gemeinsamen Referenzleser; die Rückkehr führt zur laufenden Bearbeitung. Auf schmalen Bildschirmen bleibt die Navigation im vorhandenen Materialien-Bereich direkt sichtbar, ohne eine zusätzliche Einklappebene. Dialogspezifische Layoutregeln dürfen keine eigene Navigationsoptik erzeugen.

### Auth-Formulare

Anmeldung, Registrierung und Passwort-Hilfe verwenden denselben ruhigen visuellen Vertrag in App und Anmeldedienst: Leseschrift, normal geschriebene Beschriftungen, mindestens 16 px für Eingaben, 8 px Inhaltsradien und dezente Rahmen ohne dekorative Schatten oder Punktraster. Die Formularabstände betragen grundsätzlich 16 px. Der Darstellungswechsel bleibt nachrangig. Hauptaktionen benennen ihr Ergebnis; Nebenaktionen sind als Links erkennbar. Passwortanforderungen stammen aus der aktiven Policy, Anforderungen mit Wert null werden nicht als Regeln angezeigt.
