# Paket 4: Designvergleich Learning und Teaching

Stand: 9. September 2026. Ergänzt um H5P und Auth auf ausdrücklichen Folgeauftrag. Konkrete Befunde sind von Gestaltungsvorschlägen und Prüfgrenzen getrennt. Noch keine Designimplementierung und keine vollständige Abnahme der Plattform.

## Ergebnis in verständlicher Form

GUSTAV hat bereits eine erkennbare gemeinsame Gestaltung: kantige Flächen, klare Rahmen, Monospace-Beschriftungen für Aktionen und harte Schatten. Diese Sprache tragen die Lehrkraft-Startseite, die Katalogaktionen, der Kursbereich und auch der Kummerkasten für Lernende. Daneben bestehen andere Gestaltungen fort: die Übungsbuttons, die Kurserstellung, Teile der Dialoge und die Mitgliedersuche. Es geht deshalb nicht um ein neues Design für jede Rolle, sondern um das konsequente Anwenden derselben Regeln auf vergleichbare Elemente.

Die frühere Prüfung hat diesen Vergleich nicht ausreichend durchgeführt. `/learning/practice` hätte als offensichtlicher Gegenvergleich aufgenommen werden müssen. Dieser Katalog ergänzt die [Aufgabenraum-Stichprobe vom 8. September](2026-09-08-lernenden-ui-befundkatalog.md), ohne deren Reichweite nachträglich größer darzustellen.

## Grundlage und Nachweisgrenzen

- Laufende lokale Installation, regulär vertrautes TLS, echte getrennte Browserlogins mit den vorhandenen synthetischen Dev-Personas. Keine neuen Übungssitzungen, Abgaben, Beiträge, Kurse oder Lerneinheiten angelegt; nichts gespeichert, gelöscht oder freigegeben.
- Quellabgleich: `master`, `f9610e80`. Kein Neuaufbau der laufenden Installation für diesen Audit; Gleichheit aller Container mit dem Commit nicht vollständig nachgewiesen.
- Headless Chromium; Desktop 1440 × 1000, Tabletgröße 1024 × 768 und Mobilgröße 390 × 844 CSS-Pixel. Kein echter Touchgerätetest und keine Safari-/Firefox-Abnahme.
- Screenshots wurden tatsächlich betrachtet; berechnete CSS-Eigenschaften ergänzen die Sichtprüfung. Maßstab: [DESIGN.md](../DESIGN.md), insbesondere gemeinsame Formen, Aktionshierarchie und Light/Dark. Kein externer Designentwurf.
- Buttonmessungen unten beziehen sich auf benannte sichtbare Aktionen. Versteckte Menüaktionen und kurzzeitige Navigations-/Theme-Zwischenstände sind kein Befundnachweis.
- Funktionsstichproben: Thema auswählen aktiviert den Übungsstart; Kurs- und Lerneinheitenauswahl aktiviert „Live öffnen“; Startaktionen nicht ausgelöst. Kurserstellungsdialog geöffnet und abgebrochen, Mitgliederdrawer geöffnet und geschlossen, Lerneinheitensuche ohne Treffer und zurück, Mitgliedersuche ohne Treffer. Sichtbarer Tastaturfokus am Übungsstart und Hover am Live-Button. Kein vollständiger Tastatur- oder Screenreader-Rundlauf.

## Tatsächliche Abdeckung

„Sichtprüfung“ bedeutet den erreichten Zustand, nicht alle Zustände der Route. D = Desktop, T = Tabletgröße, M = Mobilgröße; L = Light, N = Dark.

| Bereich | Erreichter und betrachteter Zustand | Umfang |
| --- | --- | --- |
| `/teaching` | Start, deaktivierte Auswahl; aktivierter Live-Button, Hover | D L/N; T L; M L/N |
| `/teaching/courses` | Belegter Kurskatalog; „Neuer Kurs“ mit leerem Formular | D L |
| `/teaching/courses/[courseId]` | Kursdetail; Mitgliederverwaltung belegt/ohne Suchtreffer; Kurseinstellungen geöffnet | D L; Mitgliedersuche zusätzlich D N |
| `/teaching/courses/[courseId]/ai-usage` | Belegte Tokenübersicht und Filter | D L, kein Filter-/Export-Rundlauf |
| `/teaching/units` | Belegter Katalog, leere Suche; Erstellungsdialog | D L |
| `/teaching/units/[unitId]` | Modularer Graph, Werkzeugleiste, Gesamtansicht | D L; keine erneute rollenübergreifende Geometrieabnahme |
| `/teaching/units/[unitId]/print` | Inhaltsauswahl, oberer sichtbarer Bereich | D L; keine Druckerzeugung oder Drucklayout-Abnahme |
| `/teaching/kummerkasten` | Leere offene Ansicht | D L; keine Beiträge vorhanden |
| `/learning/practice` | Themenauswahl, deaktivierter/aktivierter Start, Tastaturfokus; mobil auch bis zum Startbutton gescrollt | D L/N; T L; M L/N, Startbutton separat M L |
| `/learning` und `/learning/courses/[courseId]` | Belegte Kurs-/Lerneinheitenlisten | D L |
| `/learning/courses/[courseId]/archive` | Oberer Bereich vorhandener Abgaben/Rückmeldungen und Exportaktion | D L; Export nicht ausgelöst |
| `/learning/kummerkasten` | Leeres Eingabeformular | D L; nichts gesendet |
| `/live`, `/diagnostics` | Jeweilige Einstiegsseite | D L; keine Detailansichten |

Offen bleiben insbesondere die übrigen Modul-Inhaltseditoren, lineare Lerneinheiten, vollständige Graphzustandsvergleiche beider Rollen, die separate Mitgliederroute, Einladungen, belegter Lehrkraft-Kummerkasten, laufende Übung und Zusammenfassung, Live-/Diagnostikdetails, Profil sowie umfassende Fehler-/Ladezustände. Aufgabenraum und Lernendengraph wurden am Vortag untersucht, heute nicht vollständig wiederholt. Der H5P-Inhaltseditor wurde im Folgeauftrag über die bekannte Modulroute geöffnet; der Übergang vom Graphknoten zum Editor ist damit nicht vollständig abgenommen. Nicht alle Desktop-Unterseiten wurden mobil oder dunkel geprüft.

### Erweiterte Abdeckung: H5P und Auth

| Bereich | Tatsächlich geprüft | Grenze |
| --- | --- | --- |
| H5P-Lernendenaufgabe | Vorhandenes Beispiel im Aufgabenraum geladen; D L/N und M N | Nur Minimalinhalt ohne echte Antwort-/Auswertungsbuttons; keine Abgabe erzeugt |
| H5P-Lehrkrafteditor | Modul-Inhaltseditor direkt geöffnet, H5P-Aufgabe ausgewählt, eingebetteter Editor geladen; D L/N und M N | Keine Änderungen gespeichert, kein Import/Reset/Export, keine anderen Inhaltstypen |
| Keycloak-Anmeldung | D L und M L; leeres Login abgeschickt; beide echten Dev-Logins vorher erfolgreich | Kein absichtlich falsches Passwort eines Kontos; kein IServ-Rundlauf |
| Registrierung und Passwort vergessen | Formulare über echte Links geöffnet, D L und M L | Keine Registrierung, keine Reset-Mail, kein Mail-/Token-Folgeablauf |
| Auth-Dark-Mode | Betriebssystem-Farbpräferenz im Browser auf Dark gestellt und Login neu geladen | Seite blieb hell; kein erreichbarer Theme-Umschalter, daher keine künstlich erzwungene Dark-Abnahme |

Die Anmeldung mit vollständig leeren Feldern erreichte den Server und zeigte „Ungültiger Benutzername oder Passwort.“; es wurde kein Konto angegeben. Die Fehlerdarstellung wurde betrachtet. Weitere Auth-Zustände wie abgelaufene Links, Verifikation, Passwortänderung und Logoutbestätigung bleiben offen.

## Konkrete Befunde

P2 = regulär zu behebende Inkonsistenz oder Darstellungsfehler. Die Reihenfolge innerhalb dieser Gruppe priorisiert Lesbarkeit und fehlerhafte Anordnung vor reiner Optik.

### DS-01 · P2 · Mitgliedersuche im Dark Mode kaum lesbar

Reproduktion: Kurs öffnen → „Mitglieder verwalten“ → Dark Mode → Suchtext eingeben. Der Text ist `rgb(240, 241, 241)`, der Hintergrund bleibt `rgba(255, 252, 247, 0.92)`. Die Eingabe ist dadurch fast weiß auf fast weiß. Vergleich: Die Kursauswahl auf `/teaching` wechselt passend auf eine dunkle Fläche.

Quelle: `frontend/src/lib/styles/teaching-workspace.css`, `.workspace-member-search input` (ab Zeile 368), fest eingetragener heller Hintergrund statt Theme-Fläche. Ziel: passende gemeinsame Feldfarben in beiden Modi; Lesbarkeit mit eingegebenem Text testen, nicht nur mit Platzhalter.

![Mitgliedersuche im Dark Mode](assets/2026-09-09-designvergleich/members-dark.png)

### DS-02 · P2 · Mitgliederverwaltung streckt Felder und Abstände

Bei einem Mitglied und Desktophöhe 1000 px misst das Suchfeld rund 128 px Höhe und 15,2 px Eckenradius. Zwischen Kopf, Aktionen und Suche entstehen große Leerflächen; auch „Profil“ wird unüblich hoch und schmal. Nach erneutem Öffnen reproduziert. Das ist nicht nur eine andere Dichte: Ein einzeiliges Suchfeld nimmt die Form eines großen Textkastens an. Vergleich: 44 px Suchfeld im Lerneinheitenkatalog.

Quelle: `frontend/src/routes/teaching/courses/[courseId]/+page.svelte`, Mitgliederbereich; `teaching-workspace.css`, `.workspace-modal-card`, `.workspace-drawer-card`, `.workspace-member-search`. Das Zusammenspiel aus vollhohem Drawer und Grid-Streckung ist ein Ursachenverdacht, noch kein isoliert getesteter Fix. Ziel: Inhalt am Anfang anordnen, Feldhöhe unabhängig von freier Drawerhöhe halten.

![Gestreckte Mitgliederverwaltung](assets/2026-09-09-designvergleich/members-drawer-light.png)

### DS-03 · P2 · Üben verwendet eine eigene Buttonfamilie

Vergleich im gleichen Desktop-/Light-Zustand:

| Merkmal | „1 Aufgabe starten“ auf Practice | „Neue Lerneinheit“ auf Teaching | „Kurs anlegen“ im Kursdialog |
| --- | --- | --- | --- |
| Schrift | Space Grotesk, 14,4 px, fett | Monospace, 12,16 px, fett | Inter, 16 px, fett |
| Schreibweise | normale Groß-/Kleinschreibung | Großbuchstaben | normale Groß-/Kleinschreibung |
| Eckenradius | 4 px | 0 px | 13,12 px |
| Schatten | keiner | hart, 4 × 4 px | keiner |

Eine primäre Aktion darf farblich anders aussehen als eine sekundäre Navigation. Das erklärt aber nicht den gleichzeitigen Wechsel von Schrift, Form und Schatten. Auch „Beitrag senden“ im Lernenden-Kummerkasten und „Lernleistung exportieren“ verwenden die kantige Sprache: Der Unterschied ist nicht allein durch die Rolle begründet. Practice bleibt auch mobil und dunkel eine eigene Familie.

Quelle: `frontend/src/lib/styles/practice.css:265`, `.practice-button`; `PracticeStackSelector.svelte`. Ziel: dieselbe Basis und bewusst benannte primäre/sekundäre Varianten, nicht alle Aktionen identisch einfärben.

![Practice mit aktivem Startbutton](assets/2026-09-09-designvergleich/practice-light.png)

![Teaching als direkter Vergleich](assets/2026-09-09-designvergleich/teaching-light.png)

### DS-04 · P2 · Erstellungsdialoge mischen unterschiedliche Gestaltungen

„Neuer Kurs“ öffnet einen Dialog mit runden `primary-button`-/`ghost-button`-Aktionen, normaler Schrift und Textbutton „Schließen“. „Neue Lerneinheit“ nutzt für das Anlegen einen kantigen Workspace-Button, aber ein rundes Dialoggehäuse und ein Kreuz zum Schließen. Beide Dialoggehäuse haben etwa 16,8 px Radius und einen weichen Schatten. Die Mitgliederschublade verwendet wiederum einen kantigen „Schließen“-Button.

Quellen: `frontend/src/routes/teaching/courses/+page.svelte:120`, `frontend/src/routes/teaching/units/+page.svelte:92`, `frontend/src/lib/styles/app.css:331`, `teaching-workspace.css:278`. Ziel: gemeinsame Dialog- und Aktionsregeln; Größe und Modal-vs-Drawer dürfen fachlich variieren, die Grundsprache und Schließbedienung sollen nachvollziehbar einheitlich sein.

![Kurserstellung](assets/2026-09-09-designvergleich/course-drawer-light.png)

![Lerneinheitenerstellung](assets/2026-09-09-designvergleich/unit-drawer-light.png)

### DS-05 · P2 · Suchfelder der beiden Kataloge sind nicht gleich gestaltet

Im Kurskatalog: Suche 26 px hoch, Innenabstand 1 × 2 px, schmaler Standardrahmen. Im Lerneinheitenkatalog: Suche 44 px hoch, horizontal 12 px Innenabstand. Damit unterscheiden sich direkt benachbarte Verwaltungslisten bei derselben Grundfunktion deutlich. Die zusätzliche Filteraktion im Kurskatalog kann fachlich begründet sein; die Feldgestaltung ist davon unabhängig vereinheitlichbar.

Quellen: `frontend/src/routes/teaching/courses/+page.svelte`, Filterformular; `frontend/src/routes/teaching/units/+page.svelte`, Suchbereich. Ziel: eine Feldbasis, konsistente Beschriftungen und bewusst definierte Dichte.

![Kurskatalog](assets/2026-09-09-designvergleich/courses-light.png)

![Lerneinheitenkatalog](assets/2026-09-09-designvergleich/units-light.png)

### DS-06 · P2 · Radioauswahl im Lerneinheitendialog ist falsch angeordnet

„Neue Lerneinheit“ → Typ: Die nativen Auswahlkreise stehen mittig oberhalb der linksbündigen Texte „Modular“ und „Linear“, statt jeweils eine kompakte Auswahlzeile mit ihnen zu bilden. Zusätzlich ist die Auswahl blau, während Practice und der Kummerkasten den Plattformakzent verwenden. Die starke räumliche Trennung ist der wichtigere Fehler; eine aufwendige Practice-Karte muss deshalb nicht in ein kleines Formular übernommen werden.

Nachweis: Screenshot unter DS-04. Quelle: `frontend/src/routes/teaching/units/+page.svelte:128` und `frontend/src/lib/styles/ui-primitives.css:143`: Die generische Regel für `.workspace-field input` setzt auch Radios auf `width: 100%`. Ziel: Textfelder und Auswahlfelder getrennt gestalten; Radio und Beschriftung zusammenhalten.

### DS-07 · P2 · Graph-Bedienelemente bleiben sprachlich uneinheitlich

Die Lehrkraftansicht enthält „Zoom In“, „Zoom Out“ und „Toggle Interactivity“ neben „Gesamtansicht“ und „Auswahl fokussieren“ im zugänglichen DOM. Verbindungen tragen technische IDs. Das bestätigt den älteren Befund UI-06 nun auch für die Lehrkraftrolle. Die kompakte Symbolwerkzeugleiste ist als funktionale Variante sinnvoll; uneinheitliche Sprache und technische Beschriftungen sind es nicht. Keine neue Behauptung, die Knotengeometrie beider Rollen sei heute vollständig verglichen worden.

## Weitere Gestaltungsvorschläge, noch keine Fehlerentscheidung

- DS-08 / P3: Aktionsgewichtung prüfen. Im Lerneinheitenkatalog ist „Löschen“ die auffällige rote Zeilenaktion; im Kurskatalog steht dort „Kurs verwalten“. Die unterschiedlichen Funktionen sind legitim. Dennoch sollte die normale Weiterarbeit visuell Vorrang haben und Destruktives nach einer gemeinsamen Regel platziert werden. Nicht ohne Beratung verschieben.
- DS-09 / P3: `/diagnostics` zeigt eine runde Karte, „GUSTAV“ als Haupttitel und erklärenden Text über die interne Aufteilung der Arbeitsflächen statt einer direkten Diagnosehandlung. Die Einstiegsseite wirkt gegenüber `/teaching` wie ein älterer Entwurf. Zielrichtung: sinnvoller Einstieg mit gemeinsamer Seitenüberschrift; Inhalt und Navigation zuerst beraten, nicht bloß CSS austauschen.

## Ergänzung: H5P und Auth

### Ergänzende Befunde zu H5P und Auth

- **DS-10 / P2 – Auth-Felder laufen mobil aus dem Rahmen.** Bei 390 px Viewport ragen Anmeldung, Registrierung und Passwort-vergessen-Felder rechts über die Karte; die Anmeldung hat 397 px Dokumentbreite. Schon am Desktop sind die Felder breiter als der Aktionsbutton. Gemessen: `box-sizing: content-box`, rund 75,4 px Feldhöhe und 100-Prozent-Breite plus Innenabstände. Quellen: `keycloak/themes/gustav/login/resources/css/auth-theme.css`, `.kc-input`, sowie `gustav.css`, `.kc-form .workspace-field .kc-input`. Ziel: gemeinsames Größenmodell für Felder und Karte; den gesamten schmalen Auth-Rundlauf vergleichen, nicht nur den Button.
- **DS-11 / P2 – Auth-Beschriftung verspricht mehr als das Feld erlaubt.** „E-Mail-Adresse oder Benutzername“ steht an einem `type="email"`-Feld. Bei der rein lokalen Eingabe `testname` meldet der Browser `validity.typeMismatch=true`; es wurde damit kein Login abgeschickt. Quelle: `keycloak/themes/gustav/login/login.ftl`. Das ist eine Bedieninkonsistenz, nicht nur Stil. Vor einer Änderung klären, ob Benutzernamen weiterhin unterstützt werden sollen; dann Beschriftung und Feldtyp passend testen.
- **DS-12 / P2 – Auth-Theme ist nicht durchgängig erreichbar.** Trotz emulierter dunkler Systemeinstellung bleibt der Login hell, ohne Theme-Auswahl. Der Quellabgleich zeigt zusätzlich, dass `login.ftl` alte Theme-Bezeichner liest, während `template.ftl` auch `dark` kennt. Das belegt unterschiedliche Theme-Initialisierung, aber keinen vollständigen Test aller Auth-Vorlagen. Ziel: gemeinsame, tatsächlich erreichbare Theme-Strategie; nicht nur vorhandene Dark-CSS-Regeln als erfolgreiche Unterstützung zählen.
- **DS-13 / P2 – H5P-Rahmen bleiben rund.** Die GUSTAV-Aufgabenkarte um den Lernendenplayer und der GUSTAV-Rahmen um den Lehrkrafteditor sind deutlich gerundet; daneben stehen kantige Arbeitsflächen und Buttons. Der Editorrahmen verwendet `.teacher-h5p-editor` mit `border-radius: 1rem` in `teaching-workspace.css:1347`. Das liegt außerhalb des eingebetteten H5P-Inhalts und kann deshalb unabhängig von dessen Bibliothek vereinheitlicht werden. Den Inhalt selbst nicht pauschal mit globalen CSS-Regeln überschreiben.
- **DS-14 / P2 – H5P-Editor mischt deutsche und englische Bedienung.** Die GUSTAV-Leiste zeigt „Importieren“, „Zurücksetzen“, „H5P speichern“; der geladene eingebettete Editor daneben „Copy“, „Paste & Replace“, „Title“, „Metadata“, „Enter fullscreen“. Unterschiedliche Buttondarstellung innen/außen ist ebenfalls sichtbar. Bibliotheksbedienung und Inhaltsschema sind getrennt zu betrachten: „Text“ und der Inhaltstitel stammen aus der Minimalbibliothek; eine deutsche Lokalisierung aller realen Inhaltstypen ist damit noch nicht geprüft. Zuerst die unterstützte H5P-Lokalisierung und Theme-Anbindung prüfen, nicht die Bibliothek ungeprüft umbauen.

![Auth-Felder außerhalb des Rahmens](assets/2026-09-09-designvergleich/auth-login-mobile.png)

![Registrierung auf schmalem Bildschirm](assets/2026-09-09-designvergleich/auth-register-mobile.png)

![H5P-Lernendenrahmen im dunklen Modus](assets/2026-09-09-designvergleich/h5p-dark.png)

![Geladener H5P-Lehrkrafteditor](assets/2026-09-09-designvergleich/h5p-teacher-light.png)

H5P-Prüflücke: Der vorhandene Inhalt zeigt lediglich „Fixture OK: GUSTAV Minimal“. Ein erfolgreicher Ladevorgang beweist weder konsistente Quizbuttons noch Drag-and-drop, Rückmeldung, Wiederholen oder Bewertung. Dafür ist eine zusätzliche repräsentative Auswahl tatsächlich genutzter Inhaltstypen nötig. Es wurden keine synthetischen Bewertungsereignisse ausgelöst, um einen scheinbaren Browsernachweis zu erzeugen.

### DS-15 · P2 · Reale H5P-Zuordnungsaufgabe: Schriftgröße und Dark-Kontrast

Zusätzliche Belegquelle: Zwei von Felix am 9. September bereitgestellte Screenshots derselben laufenden Übungsaufgabe, jeweils Light und Dark. Diese Bilder sind ein Sichtnachweis, kein eigener Interaktions- oder CSS-Messnachweis. Sie werden wegen sichtbarer Kontoinformationen nicht unverändert ins öffentliche Repository übernommen.

- Die Artikelbeschriftungen und verschiebbaren Begriffe erscheinen im Verhältnis zu Aufgabenstellung und Plattformtext extrem klein. Die großen, fast vollbreiten Zuordnungsflächen verschärfen den Größenbruch. Ob Inhaltsautoring, interne Skalierung oder GUSTAV-CSS die Ursache ist, muss an genau diesem Inhalt untersucht werden.
- In Dark bleiben die Begriffskarten hellgrau, während ihre Schrift sehr hell wird; dadurch sind die Begriffe kaum lesbar. Die H5P-Fläche wechselt nur teilweise passend zum Theme. Dies ist unabhängig von der offenen Größenursache ein sichtbarer Lesbarkeitsmangel.
- „Auswerten“ ist in beiden Bildern sehr kontrastarm, „Aufgabe überspringen“ dagegen deutlich lesbar, aber anders gestaltet. Der tatsächliche Aktivierungszustand von „Auswerten“ lässt sich aus den Bildern nicht bestimmen. Nicht vorschnell einen deaktivierten Zustand als aktiven Kontrastfehler werten; Standard, deaktiviert, Fokus und aktiv müssen separat geprüft werden.
- Der abgerundete H5P-Rahmen bestätigt DS-13 auch für einen realen Übungsinhalt. Die Formulierung „Ordnen Sie …“ weicht vom sonstigen Du ab; das ist zunächst Inhaltssprache, nicht automatisch ein Plattform- oder DSPy-Fehler.

Nächster gezielter Nachweis: dieselbe Zuordnungsaufgabe in beiden Modi öffnen, Schrift-/Flächenmaße und Styles innen/außen getrennt ermitteln, einen echten Drag-/Tastaturablauf und den Wechsel des Auswerten-Zustands prüfen. Erst danach Ursache und Reparatur festlegen. Die separate, parallel erschienene H5P-Layout-Arbeit wird hier nicht als eigener erledigter Nachweis vereinnahmt.

### DS-16 · P2 · H5P-Lehrkrafteditor im Dark Mode nur teilweise angepasst

Eigener Browsernachweis, Desktop und mobil: Der äußere Editorrahmen bleibt hellgrau, während seine Überschrift hell wird. Im eingebetteten Editor bleiben „Title“, „Text“ und der Hilfetext dunkel auf dunklem Hintergrund; die H5P-Hub-Zeile bleibt weiß. Die Formulareingaben selbst wechseln dagegen korrekt auf dunkle Flächen mit heller Schrift. Das ist eine unvollständige Theme-Anbindung, kein pauschales Versagen des gesamten Editors. Außen ist der feste helle Hintergrund von `.teacher-h5p-editor` ein konkreter Quellhinweis; innen muss die Theme-Integration mit H5P gesondert geprüft werden.

![H5P-Editor mit unvollständiger Dark-Anpassung](assets/2026-09-09-designvergleich/h5p-teacher-dark.png)

### Bereits konsistente Elemente

Teaching-Start, Kursaktionen, Lerneinheitenaktionen, Graph-Textwerkzeuge, KI-Nutzung und Lernenden-Kummerkasten teilen große Teile der kantigen Aktionssprache. Teaching und Practice brechen in den geprüften schmalen Ansichten auf eine Spalte um; der Practice-Start bleibt durch Scrollen erreichbar. Sein Tastaturfokus war sichtbar. Unterschiedliche Inhaltsbreiten für Graph, Listen und längere Lesetexte sind nicht automatisch Fehler. Rot für Destruktives und kompakte Symbolwerkzeuge sind ebenfalls keine grundsätzlichen Abweichungen.

## Empfohlene Reihenfolge für konsistente Weiterentwicklung

1. DS-01, DS-02 und DS-06 als konkrete Lesbarkeits-/Layoutfehler behandeln. Vor Umsetzung jeweils gezielte fehlschlagende Tests für Dark-Mode-Eingabe, Drawerhöhen und Radioanordnung entwerfen.
2. Eine gemeinsame Aktionsbasis und Feldbasis anhand der vorhandenen Designregeln festlegen. Varianten nach Bedeutung benennen: primär, sekundär, klein/kontextuell, destruktiv; außerdem Standard, Hover, Fokus und deaktiviert. Practice und Kurserstellung als verpflichtende Vergleichsseiten aufnehmen.
3. Dialoge und Schubladen anschließend auf diese Grundlagen bringen. Gleiche Aufgaben sollen gleich wirken; unterschiedliche Arbeitsabläufe bleiben erhalten.
4. Offene Routen und Zustände aus der Abdeckungstabelle ergänzen, bevor eine plattformweite Freigabe behauptet wird. Graphen dabei immer für beide Rollen mit denselben Inhalten vergleichen. Diagnose-Einstieg und Aktionsgewichtung gesondert beraten.
5. Bei einer späteren Implementierung einen gezielten authentifizierten Browser-Akzeptanztest samt `make verify-feature FEATURE=<konkrete-spec>` zuordnen und zusätzlich echte Vergleichsscreenshots prüfen. Bestandene Funktions- oder Komponententests allein beweisen keine visuelle Konsistenz.

DSPy, Optimierung und KI-Inhalte bleiben außerhalb dieses Designauftrags. Der Browser-Skill hat die Trennung zwischen Sichtprüfung, Bedienprüfung und ausdrücklich offenen Zuständen bestimmt; Produktcode, API und Schema wurden nicht geändert.

## Repository-Prüfung

`PYTEST_ADDOPTS=-rs make verify` erfolgreich (Exit 0). Der Lauf prüft die technische Basis, nicht die visuelle Konsistenz. Während der Untersuchung neu erschienene, fremde H5P-Test-/Plan-Dateien bleiben unangetastet und gehören nicht zu dieser Dokumentationsänderung.
