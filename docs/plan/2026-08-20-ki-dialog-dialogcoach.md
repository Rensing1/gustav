# Dialogcoach für KI-Dialogaufgaben

**Status:** in Umsetzung  
**Datum:** 20. August 2026

## Entscheidungsgrundlage

Die ausgewählte Mockup-Variante „Dialogcoach“ verbessert vor allem die Informationshierarchie: aktuelle Frage, bisheriger Gesprächskontext, Hilfestellungen und Eingabe liegen räumlich nah beieinander. Die erste technische Annäherung übernahm diese Struktur, blieb visuell aber zu nah an der kantigen Arbeitsblattdarstellung. Nach der gemeinsamen Browserprüfung wird deshalb auch die ruhigere Flächenlogik des Mockups innerhalb des Dialog-Arbeitsbereichs übernommen: zwei klar begrenzte Oberflächen, kompakte Gesprächsblasen, weiche Abstände und ein integrierter Eingabebereich. Der globale GUSTAV-Rahmen bleibt unverändert.

## Visuelle Korrektur nach Browserprüfung

- Die linke Spalte folgt ohne dialogeigene Variante der bestehenden Aufgabenansicht: oben stehen Aufgabennummer, Aufgabenart und Auftrag, unmittelbar darunter folgt der unveränderte gemeinsame Materialbrowser. Eigene Dialogkarten, ein `Gesprächsbriefing` und dialogbezogene Sonderrahmen entfallen.
- Der Rundenstand gehört in den linken Aufgabenkopf. Rechts beginnt der Gesprächsraum unmittelbar mit dem Dialogpartner und enthält keinen konkurrierenden zweiten Dialogkopf.
- Rechts bilden Kopf, Verlauf und Eingabe eine zusammenhängende Dialogoberfläche. Der Verlauf richtet seine Beiträge am Inhalt aus; freie Höhe darf nicht als künstlicher Abstand zwischen Nachrichten verteilt werden.
- KI- und Schülerbeiträge erscheinen als klar unterscheidbare, kompakte Gesprächsflächen ohne dekorative Seitenleisten. Nur die aktuelle Frage erhält eine zusätzliche Hervorhebung.
- Der Eingabebereich ist Teil des Dialogpanels und kein Formular im Formular. Hinweis, Textfeld und Aktionen bleiben gruppiert, aber erhalten weichere Grenzen und Abstände.
- Rundungen und weichere Mischfarben werden ausschließlich über lokal begrenzte Dialogvariablen eingeführt. Andere Aufgabenarten und der Plattformrahmen ändern sich nicht.

## Korrigierter Ablauf nach visueller Kritik

- Die linke Spalte wird nicht länger nur mit denselben CSS-Klassen nachgebaut. Normale Aufgaben und KI-Dialoge rendern denselben wiederverwendbaren Aufgaben- und Materialkontext, damit Markup, Abstände und spätere Änderungen nicht auseinanderlaufen können.
- Der rechte Dialogbereich übernimmt die etablierte GUSTAV-Formensprache: kein schwebendes Außenpanel, keine Pillen-Buttons, keine dialogeigenen großen Radien und keine dekorativen Kartenschatten. Bestehende GUSTAV-Rahmen, kleine Standardradien, Typografie und Aktionshierarchie sind die Referenz.
- Nach gezielten Komponentenprüfungen wird ausschließlich die Desktopfassung im geöffneten Browser bereitgestellt. Responsive Referenzbilder, authentifizierter Browser-Rundlauf und `make verify-feature` folgen erst nach ausdrücklicher visueller Freigabe durch den Produktverantwortlichen.

## Präzisierung nach direktem Mockup-Abgleich

- Die beiden Arbeitsflächen werden nicht gleich gewichtet. Der gemeinsame Aufgaben- und Materialkontext erhält ungefähr 42 Prozent, der Dialog ungefähr 58 Prozent der verfügbaren Breite.
- Die gemeinsame Seitenleiste zeigt zuerst ausschließlich die aktive Aufgabe und deren relevante Materialien als ruhige Karten. Der vollständige Materialbaum bleibt in derselben gemeinsamen Komponente über eine nachgeordnete Offenlegung erreichbar; es entsteht keine nur für Dialoge gepflegte Parallelansicht.
- Der rechte Bereich bildet eine einzige begrenzte Gesprächsfläche. Namen stehen außerhalb der Nachrichten, Materialverweise können kontextuell im Verlauf erscheinen, und die Eingabe ist als Fußbereich an dieselbe Fläche angeschlossen.
- Die globale GUSTAV-Navigation, der Seitenhintergrund und die gemeinsamen Buttonkomponenten bleiben unverändert. Aus dem Mockup werden Komposition und Informationshierarchie übernommen, nicht dessen vollständiges Plattform-Redesign.

## User Story

Als lernende Person möchte ich während einer KI-Dialogaufgabe sofort erkennen, welche Frage ich gerade beantworte, wie weit der begrenzte Dialog fortgeschritten ist und welche Hilfestellungen verfügbar sind, damit ich mich auf meine nächste fachliche Antwort konzentrieren kann, ohne zwischen Gespräch, Eingabe und Materialien die Orientierung zu verlieren.

## Umfang und Abgrenzung

- Die Änderung betrifft ausschließlich Struktur, Semantik und Darstellung der bestehenden Schüleransicht für KI-Dialogaufgaben.
- Der globale GUSTAV-Kopf, der gemeinsame Aufgabenkopf, die Designsprache, Dark Mode, Materialdarstellung und der verschiebbare Aufgabentrenner bleiben erhalten.
- Dialogzustände, Nachrichten, Satzanfänge, Rundenlimit, Abschlusslogik und Fehlerbehandlung bleiben fachlich unverändert.
- Es werden keine generischen Denkfragen erfunden. Im Hybridmodus erscheinen ausschließlich die bereits serverseitig erzeugten Satzanfänge als optionale Hilfestellungen; im Freitextmodus werden keine Ersatzvorschläge angezeigt.
- Der vollständige Verlauf bleibt verfügbar und wird weder zusammengefasst noch verborgen. Die aktuelle KI-Frage erhält lediglich eine stärkere visuelle Gewichtung.
- Das Vorhaben ist kein Redesign der gesamten Plattform.

## UI-Vertrag

### Gesprächsfortschritt

Der linke Aufgabenkopf enthält den Antwortmodus und den Text `Runde {abgeschlossene Runden} von {maximale Runden}`. Eine kompakte Punktfolge visualisiert ausschließlich den tatsächlichen Rundenstand. Feste Phasen wie „Beobachten“, „Beispiel“ oder „Begründen“ werden nicht verwendet, weil sie nicht für jede konfigurierte Dialogaufgabe fachlich zutreffen.

Der sichtbare Text bleibt auch ohne Farbe und ohne Balken verständlich. Der Fortschritt wird nicht bei jedem Rendern als Live-Meldung vorgelesen, sondern nur nach einem abgeschlossenen Dialogzug aktualisiert.

### Dialogverlauf und aktuelle Frage

Der vollständige Verlauf bleibt ein semantisches Log. Frühere Beiträge behalten die etablierte Sprecherzuordnung: KI links mit Erfolgsakzent, Schüler rechts mit Produktakzent. Die jeweils letzte beantwortbare KI-Nachricht erhält innerhalb des Logs die sichtbare Kennzeichnung `Aktuelle Frage` und eine klarere, weiterhin kantige Fläche. Bei einer neuen Sitzung ist die Eröffnungsnachricht die aktuelle Frage; nach einer KI-Antwort ist es deren jüngster Beitrag.

Auf breiten Flächen wird der Hauptbereich als drei Zeilen aufgebaut: kompakter Fortschritt, intern scrollbarer Verlauf und Eingabebereich. Dadurch bleibt die Eingabe erreichbar, während lange Verläufe nur den mittleren Bereich scrollen. Nach dem Laden oder einer neuen KI-Antwort steht der Verlauf am jüngsten Beitrag. Der Tastaturfokus wird nicht automatisch verschoben.

### Eingabe und Hilfestellungen

Der Eingabebereich bleibt klar als zusammengehörige Fläche erkennbar, ist aber visuell in das rechte Dialogpanel integriert. Die optionale Hilfestellung steht direkt oberhalb des Textfelds und wird neutral als `Hilfestellungen` bezeichnet. Ein Satzanfang bleibt eine Sekundäraktion und fügt wie bisher ausschließlich den gewählten Text in den Entwurf ein.

Der Sicherheitshinweis `Antworten können Fehler enthalten. Gib keine persönlichen oder vertraulichen Informationen ein.` steht als schmale Hinweiszeile im Eingabebereich. Er ist dadurch auf der Aufgabenansicht genau dort sichtbar, wo eine lernende Person Text übermittelt. `Antwort senden`, Wiederholung, Abschluss und der im Fehlerfall erlaubte Abbruch behalten die bereits festgelegten Sichtbarkeitsregeln.

### Aufgabe und Materialien

Auf breiten Flächen verwendet der Dialog links exakt dieselbe visuelle und semantische Seitenleistenstruktur wie andere Aufgaben: Aufgabenkopf, Aufgabenstellung und ein auf die aktive Aufgabe fokussierter gemeinsamer Materialkontext. Partnername, Gespräch und Eingabe bleiben rechts. Der bestehende verschiebbare Trenner und die gespeicherte Spaltenbreite werden nicht verändert. Es entsteht keine dritte Spalte und kein zusätzliches Material-Dock im Hauptbereich.

Unterhalb der Zweispaltengrenze bleiben die montierten Ansichten `Aufgabe` und `Materialien` über den vorhandenen Umschalter erreichbar. Die Aufgabenansicht enthält Partnername, Fortschritt, Verlauf, Sicherheitshinweis und Eingabe vollständig. Die Materialansicht enthält wie bei anderen Aufgaben Aufgabenstellung und Dokumentstapel, aber keine duplizierte Eingabe.

## Responsive Zustände

| Verfügbare Komponentenbreite | Verbindliche Darstellung |
| --- | --- |
| Ab `60rem` | Zwei Spalten mit bestehendem Trenner; links Kontext und Materialien, rechts Fortschritt, scrollbarer Verlauf und am unteren Rand erreichbare Eingabe. |
| Unter `60rem` | Ein Bereich zur Zeit; Umschalter zwischen `Aufgabe` und `Materialien`; die Aufgabenansicht enthält alle zum Antworten notwendigen Elemente. |
| Unter `48rem` | Nachrichten nutzen die volle Breite; Aktionsgruppen und Eingabefeld nutzen die verfügbare Breite ohne horizontalen Überlauf. |
| Unter `22rem` | Sitzungs- und Dialogaktionen werden einspaltig gestapelt; Berührungsflächen bleiben mindestens 44 Pixel hoch. |

Die Darstellung wird bei `1600×1000`, `1024×768` und `390×844` jeweils in Light und Dark geprüft. Ein Browser ohne Container Queries behält den bestehenden nutzbaren Einspalten-Fallback.

## Zustände

### Neue Sitzung

Die Eröffnungsnachricht ist als aktuelle Frage gekennzeichnet. Der Fortschritt zeigt null abgeschlossene Runden. `Dialog beenden` bleibt verborgen; der sichere Abbruch ohne Abgabe bleibt im Kontextbereich erreichbar.

### Laufendes Gespräch

Der jüngste KI-Beitrag ist als aktuelle Frage gekennzeichnet. Die Eingabe bleibt erreichbar. Bei ausgeschöpftem Rundenlimit wird kein weiteres Antwortfeld angeboten; die vorhandene Abschlussaktion bleibt erreichbar.

### Fehlgeschlagene KI-Antwort

Der letzte erfolgreiche Gesprächsstand bleibt sichtbar. Wiederholung, ausgeschöpftes Wiederholungslimit, Abschluss und terminaler Abbruch behalten die bestehenden Regeln. Die neue Hierarchie darf keinen dieser Auswege verdecken oder aus dem sichtbaren Aktionsbereich verdrängen.

### Abschlussphase und abgeschlossene Sitzung

In der Abschlussphase ersetzt der Abschlussbereich die normale Eingabe, während der Verlauf erhalten bleibt. Nach der endgültigen Abgabe erscheinen Verarbeitungsstand und Rückmeldung wie bisher im Hauptbereich. Die Fortschrittsdarstellung behauptet keinen erfolgreich abgeschlossenen Dialog, solange die Abschlussverarbeitung noch aussteht.

## BDD-Szenarien und Testzuordnung

### Aktuelle Frage beim ersten Einstieg

**Given** eine neue Dialogsitzung ohne beantwortete Runde, **when** die Aufgabenansicht geladen wird, **then** ist die Eröffnungsnachricht genau einmal als `Aktuelle Frage` gekennzeichnet, der Fortschritt zeigt `Runde 0 von N` und die Antwortaktion steht direkt beim Eingabefeld.

Automatisierter Test: `frontend/src/lib/components/learning-unit/LearningDialogWorkspace.test.ts` prüft Semantik, eindeutige Kennzeichnung und Aktionszuordnung.

### Aktuelle Frage nach einer beantworteten Runde

**Given** ein fortsetzbarer Dialog mit früheren Nachrichten, **when** der jüngste KI-Beitrag geladen wird, **then** bleibt der gesamte Verlauf erhalten, ausschließlich der jüngste beantwortbare KI-Beitrag ist als aktuelle Frage gekennzeichnet und der Fortschritt entspricht dem serverseitigen Rundenstand.

Automatisierter Test: `LearningDialogWorkspace.test.ts` rendert mehrere Runden und prüft Log, aktuelle Frage und Fortschrittswerte.

### Fachlich konfigurierte Hilfestellungen

**Given** eine Hybridaufgabe mit verfügbaren Satzanfängen, **when** die aktuelle Frage angezeigt wird, **then** stehen die Satzanfänge als optionale rechteckige Hilfestellungen direkt am Eingabebereich und ein ausgewählter Satzanfang wird wie bisher in den Entwurf übernommen.

**Given** eine Freitextaufgabe ohne Satzanfänge, **when** die aktuelle Frage angezeigt wird, **then** werden keine generischen Denkfragen oder leeren Hilfestellungsflächen erzeugt.

Automatisierte Tests: `LearningDialogWorkspace.test.ts` prüft beide Modi und die unveränderte Auswahlfunktion.

### Langer Verlauf auf breiter Fläche

**Given** ein Dialog mit einem Verlauf, der höher als die verfügbare Arbeitsfläche ist, **when** die Seite auf einer breiten Fläche dargestellt wird, **then** scrollt der Verlauf innerhalb des Hauptbereichs, während Fortschritt und Eingabebereich erreichbar bleiben und der jüngste Beitrag sichtbar ist.

Automatisierter Test: `frontend/e2e/dialog-task-learning.spec.ts` prüft reale Geometrie und Scrollverhalten bei Desktopbreite.

### Materialzugriff auf breiter und kompakter Fläche

**Given** eine breite Ansicht, **when** der Dialog geöffnet ist, **then** bleiben Kontext und Materialien links neben dem Gespräch sichtbar und der vorhandene Trenner ist bedienbar.

**Given** eine kompakte Ansicht, **when** zwischen `Aufgabe` und `Materialien` gewechselt wird, **then** bleiben beide Ansichten montiert, die Eingabe erscheint nur in `Aufgabe` und der Entwurf geht nicht verloren.

Automatisierte Tests: bestehende Komponenten- und Separator-Tests sowie `dialog-task-learning.spec.ts` werden um den neuen Hauptbereich ergänzt.

### Responsive und authentifizierte Feature-Abnahme

**Given** eine echte angemeldete lernende Person mit fortsetzbarem KI-Dialog, **when** sie auf Desktop, iPad-Querformat und Smartphone eine Antwort sendet, den Dialog beendet und endgültig abgibt, **then** bleiben aktuelle Frage, Fortschritt, Hilfestellungen, Sicherheitshinweis und alle erlaubten Aktionen sichtbar und bedienbar; anschließend erscheint die Rückmeldung.

Automatisierter Test: Der vorhandene mit `@feature-acceptance` markierte Rundlauf in `frontend/e2e/dialog-task-learning.spec.ts` prüft Oberfläche, Server und produktionsnahe Datenhaltung. Seine visuellen Referenzen werden erst nach manueller Prüfung aktualisiert.

### Fehler- und Abschlusszustände

**Given** ein fehlgeschlagener oder terminal fehlgeschlagener KI-Zug, **when** der Dialog angezeigt wird, **then** bleiben genau die fachlich erlaubten Aktionen für Wiederholung, Abschluss oder Abbruch erreichbar.

**Given** eine endgültig abgegebene Sitzung, **when** sie erneut geöffnet wird, **then** erscheinen weder Eingabe noch Sitzungsaktionen und Verarbeitungsstand beziehungsweise Rückmeldung bleiben sichtbar.

Automatisierte Tests: die bestehenden Fehler-, Abschluss- und Read-only-Fälle in `LearningDialogWorkspace.test.ts` bleiben als Regressionstests erhalten und werden auf die neue Struktur ausgerichtet.

## API- und Datenbankbewertung

Die Änderung benötigt keinen neuen oder geänderten REST-Endpunkt. `api/openapi.yml` bleibt unverändert, weil alle dargestellten Informationen bereits im bestehenden Dialogsitzungs-Vertrag enthalten sind. Das PostgreSQL-/Supabase-Schema bleibt unverändert; eine Migration ist nicht erforderlich. Es entstehen keine neuen gespeicherten Nutzerpräferenzen oder personenbezogenen Daten.

## Red–Green–Refactor-Reihenfolge

1. Fehlgeschlagene Komponententests für Fortschritt, genau eine aktuelle Frage, Freitext-/Hybridmodus und die Position des Sicherheitshinweises ergänzen.
2. Fehlgeschlagene CSS-Vertragstests für den dreizeiligen Hauptbereich, den intern scrollbaren Verlauf und den erreichbaren Eingabebereich ergänzen.
3. Den authentifizierten `@feature-acceptance`-Test um langen Verlauf, sichtbare aktuelle Frage und die drei Zielbreiten erweitern, ohne Referenzbilder vorzeitig zu ersetzen.
4. Markup minimal in Fortschrittszeile, Verlauf und Eingabe gliedern; bestehende Fachlogik und öffentliche Komponentenschnittstelle unverändert lassen.
5. Die Layoutregeln ausschließlich in der Cascade-Layer `learning` von `frontend/src/lib/styles/learning-unit.css` mit zentralen Tokens umsetzen.
6. Nach grünen Verhaltenstests Struktur und Benennungen vereinfachen; insbesondere dürfen keine doppelten Statusquellen oder breitenabhängigen JavaScript-Zweige entstehen.
7. UI-Labor und `docs/DESIGN.md` an den akzeptierten Vertrag anpassen und Light-/Dark-Referenzen für Desktop, Tablet und Smartphone visuell prüfen.
8. Gezielte Komponenten- und Browsertests, anschließend `make verify-feature`, erfolgreich ausführen.

## Abnahmekriterien

- Die aktuelle Frage, der tatsächliche Rundenstand und die nächste erlaubte Aktion sind ohne Scrollsuche erkennbar.
- Lange Verläufe verdrängen den Eingabebereich auf breiten Flächen nicht aus der Arbeitsfläche.
- Es werden keine fachlich ungesicherten Denkfragen oder Lernphasen ergänzt.
- Materialzugriff, Split-Trenner, Entwurfszustand, Fehlerauswege und Abschlusslogik bleiben erhalten.
- Light und Dark funktionieren ohne hart codierte Farben oder komponentenlokale Styles.
- Der vollständige authentifizierte Browser-Rundlauf besteht über echte Oberfläche, Server und produktionsnahe Datenhaltung.
- `make verify-feature` ist vor Fertigmeldung und Commit erfolgreich.

## Visuell freigegebene Präzisierung vom 21. August 2026

Die manuelle Abnahme hat die zuvor aus dem ersten Mockup übernommene Bildsprache verworfen. Die Umsetzung orientiert sich nun an einem eigenständigen, ruhigen GUSTAV-Arbeitsbereich und stellt ausschließlich vorhandene Plattforminhalte dar.

- Materialien erscheinen als kompakte Inhaltszeilen mit neutralem Dokumenttyp-Symbol, Originaltitel und gekürztem Originalinhalt. Es gibt keine illustrativen Vorschaubilder, Buchgrafiken oder frei erfundenen Materialdarstellungen.
- Materialzugriff bleibt über die vorhandene Leseaktion möglich, wird aber als Teil der Inhaltszeile und nicht als zusätzliche kontextuelle Sonderaktion dargestellt.
- Im Dialog erscheinen ausschließlich tatsächlich vorhandene Nachrichten. Materialtitel werden nicht als kontextuelle Schaltflächen in den Gesprächsverlauf eingefügt.
- Fortschritt, Aufgabe, Materialien, Dialog und Eingabe bilden eine gemeinsame, zurückhaltend gerahmte Arbeitsfläche. Es gibt weder doppelte Fortschrittsanzeigen noch erfundene Uhrzeiten oder Gesprächsmetadaten.
- Der bestehende Sicherheitshinweis, die vorhandenen Fehler- und Abschlussaktionen sowie die responsive Umschaltung bleiben fachlich unverändert.

Zusätzliche gezielte Komponententests sichern ab, dass bei vorhandenen Gesprächsregeln keine Schaltfläche im Dialog erzeugt wird und fokussierte Materialien ohne illustrative Vorschau als bedienbare Inhaltszeilen erscheinen. Die visuellen Referenzen und der vollständige Feature-Rundlauf werden weiterhin erst nach erneuter manueller Sichtfreigabe aktualisiert beziehungsweise ausgeführt.

## UX-Präzisierung zum Materialzugriff vom 21. August 2026

Die kompakte Materialzeile erhält wieder progressive Offenlegung, ohne zur früheren unruhigen Baumdarstellung zurückzukehren.

- Ein Klick auf Pfeil oder Materialtitel klappt den vollständigen Inhalt direkt in der Seitenleiste auf oder zu. Aufgabenstellung, Dialog beziehungsweise Eingabefeld und vorhandene Entwürfe bleiben dabei unverändert sichtbar.
- Die Großansicht bleibt als getrennte sekundäre Symbolaktion erhalten. Ihre Beschriftung und ihr Symbol dürfen nicht mit der Aufklappaktion konkurrieren.
- Mehrere Materialien dürfen gleichzeitig geöffnet bleiben. Die Zustände werden weiterhin über die vorhandene Materialzustandsverwaltung geführt.
- Primäre und weitere Materialien verwenden dieselbe kompakte Komponente und dasselbe Interaktionsmodell. Eigene Abgaben behalten ihre bestehende aufklappbare Darstellung.
- Markdown wird inline vollständig gerendert. Dateien verwenden die vorhandene sichere Vorschau- und Separat-öffnen-Logik.

Gezielte Komponententests prüfen zunächst Aufklappen, Zuklappen, Großansicht und die unveränderte Bedienbarkeit beider Materialbereiche. Breite Feature- und visuelle Referenztests folgen weiterhin erst nach manueller Browserabnahme.
