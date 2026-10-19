# Learning-UI: Umsetzung der SaaS-Gestaltung

## User Story und Umfang
Als Schüler möchte ich Materialien, Aufgaben und Rückmeldungen in einer ruhigen, lesbaren Arbeitsoberfläche nutzen. Gemeinsame Tokens und Bedienelemente folgen DESIGN.md; Modulansicht und Aufgabenraum erhalten 8 px Inhaltsradien und 16 px Arbeitsbereichsabstand. Bestehende Inhalte, Entwürfe, Navigation und Abgabe bleiben erhalten. API, Datenmodell und Berechtigungen ändern sich nicht; Vertragsänderungen und Migrationen sind daher nicht erforderlich.

## Prüffälle vor der Implementierung
- Gegeben eine geöffnete Modulansicht, wenn ich Materialien lese und eine Aufgabe öffne, dann bleiben Inhalt und Navigation zugänglich, bei einheitlicher Schrift und ruhigen Flächen. Nachweis: bestehender authentifizierter `learner-reference-workspace.spec.ts`, ergänzt um berechnete Gestaltungswerte.
- Gegeben ein Aufgabenentwurf, wenn ich Materialien, Lesemodus und schmale Ansicht wechsle, dann bleibt mein Entwurf erhalten und es entsteht kein horizontaler Seitenüberlauf. Nachweis: bestehende Szenarien derselben Spec.
- Gegeben Hell- oder Dunkelmodus, wenn ich Eingaben und Aktionen nutze, dann bleiben Kontraste, Fokus und Grenzen erkennbar. Nachweis: eigene visuelle Prüfung; zentrale Token- und Theme-Vertragstests nach Sichtabnahme.
- Gegeben Text-, Datei- oder Rückmeldungsansicht, wenn ich sie öffne, dann bleibt die relevante Aktion verständlich, ohne redundante Bedienerklärungen. Nachweis: visuelle Prüfung und bestehende Komponentenprüfungen.

## Reihenfolge und Abnahme
1. Prüffälle entwerfen, dann Tokens, gemeinsame UI-Primitiven und Lernansichten ändern. Keine fachlichen Zustandsänderungen.
2. Frontend für den lokalen produktionsnahen Stack bauen; eigene Browserprüfung einschließlich schmaler Ansicht, Hell-/Dunkelmodus und Stichprobe gemeinsamer Oberflächen.
3. Felix die tatsächliche Oberfläche vorlegen. Seine Sichtprüfung ist ein ausdrücklicher Haltepunkt.
4. Erst danach betroffene Komponentenprüfungen und `make verify-feature FEATURE=learner-reference-workspace` ausführen. Keine historische Gesamtsuite. Bis dahin kein Commit und keine vollständige Fertigmeldung.

Die ausdrücklich gewünschte visuelle Reihenfolge ersetzt für diesen Auftrag den üblichen vorgezogenen Testlauf. Tests werden vorher entworfen, aber erst nach Sichtabnahme ausgeführt.

## Zwischenstand zur Sichtabnahme

Die Umsetzung ist im lokalen Frontend bereitgestellt; der Produktionsbuild war erfolgreich. Eigene Browserprüfung: Modulansicht, Textaufgabe mit vorhandener Rückmeldung, Dateiaufgabe, Hell-/Dunkelmodus und schmale Ansicht mit Materialumschalter. Die gerenderte Desktop-Spaltenaufteilung bestätigt 16 px Zwischenraum und 8 px Inhaltsradius; die schmale Arbeitsfläche passt ohne horizontalen Überlauf. Kursübersicht und Kopfzeile wurden als gemeinsame Oberflächen mit angesehen. Redundante Material-Platzhalter und die Bedienerklärung zur Arbeitsfläche entfallen; die mobile Aufgabenstellung ist ohne verschachtelte Hintergrundflächen dargestellt.

Automatisierte Tests wurden auf ausdrücklichen Wunsch noch nicht ausgeführt. Die Feature-Abnahme, weitere gegebenenfalls veraltete CSS-Vertragsassertionen und der Commit bleiben bis nach Felix’ Sichtprüfung offen. Die Browserprüfung ist keine vollständige funktionale Regression, insbesondere kein Nachweis einer neuen Abgabe.

### Offene Beobachtung aus der Browserprüfung
Nach dem Wechsel von der Dateiaufgabe zurück zur Textaufgabe erschien deren Editor leer, obwohl zu Beginn der Sitzung Text angezeigt wurde. Die vorhandene Rückmeldung ist weiterhin sichtbar; auch nach Neuladen blieb der Editor leer. Es wurde keine neue Abgabe abgesendet und kein Editorinhalt bewusst geändert. Ursache und Vorbestehen sind noch nicht geklärt. Diese Beobachtung muss vor funktionaler Abnahme gezielt untersucht werden; sie wird nicht als bestandener Entwurfserhalt gewertet.

## Zweite Gestaltungsrunde: Seitenkomposition

Felix hat eine grundlegende Überarbeitung der Hierarchie beauftragt. Die Modulansicht erhält den Modultitel als Hauptüberschrift und ein ruhiges Inhaltsverzeichnis. Der Aufgabenraum zeigt einen einzigen Aufgabentitel, einen Rückweg zum Modul und eine klar hervorgehobene Antwortfläche; Materialien sind visuell untergeordnet. Antwortform und Eingabe bilden eine zusammenhängende Gruppe, die Feedback-Anforderung ist die Primäraktion. Keine Änderungen an Speicherung oder Abgabezuständen.

Vorab entworfene Sichtprüffälle: (1) Desktop: eindeutige Titelhierarchie, erreichbare Layout-Einstellungen, 16 px Spaltentrennung; (2) schmal: vollständige Aufgabenstellung und Materialumschalter ohne horizontalen Überlauf; (3) Hell/Dunkel: Antwortfläche, Hauptaktion und Fokus lesbar; (4) Modul: Navigation und Materialien ohne doppelte Lerneinheitenüberschrift. Automatisierte Szenarien und der offene Entwurfsbefund bleiben bis zur erneuten Sichtabnahme zurückgestellt. Der Build dient ausschließlich der Bereitstellung der Oberfläche, Tests werden nicht gestartet.

### Sichtprüfung der zweiten Runde
Die zweite Komposition ist lokal bereitgestellt. Im Browser wurden Desktop-Aufgabenraum, Modulansicht, Dunkelmodus und 390 px schmale Ansicht angesehen. Der mobile Arbeitsbereich bleibt bei 366 px ohne horizontalen Überlauf; Kopfzeile und Breadcrumb sind auf zwei kompakte Zeilen reduziert. Die Aufgabenansicht hat eine einzige Hauptüberschrift, eine ungerahmte Kontextspalte und die hervorgehobene Antwortfläche. Kein Testlauf und kein Commit; erneute Sichtabnahme durch Felix steht aus. Der zuvor dokumentierte leere Editor bleibt ein offener funktionaler Befund.

## Dritte Runde: orientierende Modulnavigation

Vorab entworfene Prüffälle: Die Navigation sortiert Materialien vor Aufgaben wie die Leseansicht; ein Klick auf eine Aufgabe erreicht tatsächlich deren Zeile. Die aktuelle Leseposition wird beim Scrollen markiert und ihr Modul geöffnet. Modulgruppen sind unabhängig ein-/ausklappbar. Schmale Ansichten starten mit geschlossener Inhaltsnavigation und zeigen den aktuellen Modulnamen; nach einem Sprung schließt die Navigation und fokussiert den Zielinhalt. Desktop behält die Navigation sichtbar. Symbole unterscheiden Aufgaben und Materialien auch ohne Farbe, Bedienelemente bleiben mindestens 44 px hoch. Automatisierte Tests erst nach Sichtprüfung; keine Änderungen an Entwürfen oder Abgaben.

### Sichtprüfung der dritten Runde
Desktop und schmale Ansicht wurden am lokalen Stack im Browser geprüft. Die aktuelle Materialposition ist markiert, weitere Module sind zunächst eingeklappt. Ein Klick auf Aufgabe 2 erreicht die tatsächliche Aufgabenzeile und markiert den Eintrag. In der schmalen Ansicht startet die Inhaltsnavigation geschlossen; nach Auswahl eines Materials schließt sie wieder. Der schmale Inhaltsbereich hat keinen horizontalen Überlauf. Screenshots beider Ansichten und der aufgeklappten mobilen Navigation liegen für Felix vor. Build erfolgreich, keine automatisierten Tests ausgeführt, kein Commit. Die Sichtabnahme und funktionale Testphase einschließlich des bereits dokumentierten Editorbefunds bleiben offen.
