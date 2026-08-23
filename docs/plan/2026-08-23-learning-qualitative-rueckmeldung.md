# Qualitative Rückmeldung als Lernweg

## User Story

Als lernende Person möchte ich nach einer ausgewerteten Abgabe zuerst eine verständliche formative Rückmeldung sehen, die Kriterien bei Bedarf nachvollziehen und anschließend direkt weiterarbeiten können, ohne numerische Einzelwerte als vermeintliche Benotung angezeigt zu bekommen.

## BDD-Szenarien

### Rückmeldung steht zuerst

**Given** eine abgeschlossene Abgabe mit Rückmeldung und Kriterien  
**When** die Verarbeitung abgeschlossen oder die Ergebnisansicht direkt geöffnet wird  
**Then** ist „Rückmeldung“ geöffnet, „Meine Abgabe“ geschlossen und „Auswertung“ erscheint nicht als gleichrangiger Bereich.

### Vier qualitative Stufen

**Given** Kriterien mit den Scores 0, 2, 3, 6, 7, 8, 9 und 10  
**When** „Kriterien im Detail“ geöffnet wird  
**Then** erscheinen an den Grenzen „Mangelhaft“, „Ansatzweise“, „Gelungen“ und „Hervorragend“ und kein numerischer `/10`-Wert.

### Abweichendes Maximum

**Given** ein Kriterium mit einem `max_score` ungleich 10  
**When** der qualitative Status berechnet wird  
**Then** wird der Score ohne Rundung auf die Zehnerskala normalisiert und derselben Einteilung zugeordnet.

### Fehlende oder ungültige Werte

**Given** ein Kriterium ohne Score oder mit einem ungültigen Score beziehungsweise Maximum  
**When** die Kriterien angezeigt werden  
**Then** bleibt die Begründung sichtbar und der Status lautet „Ohne Einstufung“.

### Direktes Weiterarbeiten

**Given** eine bearbeitbare Abgabe mit fertiger Rückmeldung  
**When** „Im Entwurf weiterarbeiten“ aktiviert wird  
**Then** erhält je nach Antwortform der Texteditor oder das Dateifeld den Fokus und der Entwurf bleibt unverändert.

### Konsistente Schüleransichten

**Given** aktuelle oder ältere Abgaben mit langen Kriterien und Markdown-Begründungen  
**When** sie in einer Schüleransicht geöffnet werden  
**Then** verwenden alle Ansichten dieselbe qualitative Darstellung, umbrechen responsiv und rendern Markdown weiterhin bereinigt.

## Produktentscheidungen

- Die Stufen lauten: 0–2 „Mangelhaft“, 3–6 „Ansatzweise“, 7–8 „Gelungen“, 9–10 „Hervorragend“.
- Werte mit einem abweichenden Maximum werden vor der Einordnung ohne Rundung auf die Zehnerskala normalisiert.
- Fehlende, negative oder außerhalb des gültigen Maximums liegende Scores sowie ungültige Maxima erhalten „Ohne Einstufung“.
- Beim Öffnen der Kriterienliste bleiben zunächst alle einzelnen Kriterien geschlossen. Die lernende Person öffnet Begründungen bewusst nach Bedarf.
- Die Begriffe beschreiben ausschließlich den Erfüllungsstand eines Kriteriums, nicht die lernende Person.
- Schüleransichten zeigen keine numerischen Einzelwerte mehr. Die Lehrkraftdiagnostik und gespeicherte Scores bleiben unverändert.
- „Im Entwurf weiterarbeiten“ fokussiert in dieser Version das passende Eingabefeld. Ein angehefteter nächster Schritt gehört nicht zum Umfang.

## Architektur und Verträge

- Eine reine Frontend-Funktion ordnet Kriterienwerte den qualitativen Stufen zu.
- Ein gemeinsamer Svelte-Baustein rendert die verschachtelte Kriterienoffenlegung in allen Schülerkontexten.
- `analysis_json.criteria_results`, `api/openapi.yml` und das Datenbankschema bleiben unverändert.
- Der bestehende bereinigte Markdown-Renderer bleibt die einzige Rendering-Pipeline für Rückmeldungen und Kriterienbegründungen.
- Der Markdown-Editor erhält eine explizite Fokus-Schnittstelle; die Aufgabenansicht greift nicht auf interne Editor-DOM-Klassen zu.

## Testzuordnung

- Unit-Test der Zuordnungsfunktion: alle Bandgrenzen, normalisierte Werte und ungültige Eingaben.
- Komponententest des Kriterienbausteins: qualitative Statusangaben, niedrigstes geöffnetes Kriterium, lange Titel, Markdown und keine numerischen Scores.
- Komponententests der Aufgabenansicht: Rückmeldung zuerst, verschachtelte Kriterien, Text- und Dateifokus.
- Bestehende Tests für Antwortgruppe, Referenzdokument und Abgabenverlauf werden auf die gemeinsame Darstellung umgestellt.
- Der vorhandene authentifizierte Playwright-Lernweg bleibt `@feature-acceptance` und prüft Oberfläche, Server und produktionsnahe Datenhaltung vollständig.
- Vor Fertigmeldung ist `make verify-feature` verpflichtend.

## Dokumentation

- `docs/DESIGN.md` beschreibt die neue Offenlegungshierarchie.
- Das Schülerhandbuch ersetzt die getrennte „Auswertung“ durch „Kriterien im Detail“ innerhalb der Rückmeldung.
- `docs/CHANGELOG.md` nennt die qualitative lernendenseitige Darstellung.

## Ergänzung: Zweistufiger Aktionsbereich

### User Story

Als lernende Person möchte ich nach einer Rückmeldung bewusst zwischen Überarbeiten und endgültigem Abgeben wählen und nach dem Abschluss direkt sinnvoll im Lernpfad weitergeführt werden.

### BDD-Szenarien

1. **Entwurf nach Rückmeldung weiterführen oder abschließen**
   - Given eine abgeschlossene Rückmeldung zur unveränderten aktuellen Fassung
   - When der Aktionsbereich angezeigt wird
   - Then erscheinen `Im Entwurf weiterarbeiten`, `Endgültig abgeben` und der ruhige Rückweg `Zurück zum Lernpfad`.
2. **Geänderte Fassung noch nicht endgültig abgeben**
   - Given eine Rückmeldung und ein anschließend veränderter Entwurf
   - When der Aktionsbereich angezeigt wird
   - Then bleibt `Endgültig abgeben` deaktiviert und verweist auf eine erneute Rückmeldung.
3. **Nach Abschluss zur nächsten offenen Aufgabe**
   - Given eine endgültig abgegebene Aufgabe und eine nachfolgende, sichtbare, noch nicht endgültig abgegebene Aufgabe im selben Modul
   - When der Abschlusszustand angezeigt wird
   - Then ersetzt `Weiter zu <Aufgabentitel>` die Bearbeitungsaktionen.
4. **Nach Abschluss ohne eindeutige Folgeaufgabe**
   - Given eine endgültig abgegebene Aufgabe ohne nachfolgende offene Aufgabe im selben Modul
   - When der Abschlusszustand angezeigt wird
   - Then führt der Aktionsbereich ausschließlich zurück zum Lernpfad.

### Technische Abgrenzung

- Die nächste Aufgabe wird ausschließlich aus der vorhandenen Reihenfolge des aktuellen Inhaltsmoduls bestimmt; bereits endgültig abgegebene Aufgaben werden übersprungen.
- Es entstehen keine neuen API-Endpunkte, Datenfelder oder Migrationen.
- Der vorhandene Finalisierungs-Request wird aus dem Aktionsbereich abgesendet; die doppelte Finalisierungsaktion unter dem Editor entfällt.
- Die Ergänzung wird mit gezielten Komponenten- und Helper-Tests sowie einer visuellen Prüfung im lokalen Lernraum überprüft. Auf Wunsch des Produktverantwortlichen wird in dieser Gestaltungsrunde kein umfassender Prüflauf ausgeführt.

## Ergänzung: Kriterien als verschachtelte Liste

### User Story

Als lernende Person möchte ich die Kriterien zunächst als übersichtliche Liste überblicken und die Begründung jedes einzelnen Ergebnisses nur bei Bedarf öffnen, damit ich Stärken und nächste Lernschritte schnell erfassen kann.

### BDD-Szenarien

1. **Gesamte Kriterienliste ein- und ausklappen**
   - Given eine Rückmeldung mit mehreren Kriterien
   - When `Kriterien im Detail` geschlossen beziehungsweise geöffnet wird
   - Then ist die gesamte Kriterienliste verborgen beziehungsweise als semantische Liste sichtbar und alle einzelnen Begründungen sind zunächst geschlossen.
2. **Einzelne Begründung öffnen**
   - Given eine geöffnete Kriterienliste
   - When ein einzelnes Kriterium aktiviert wird
   - Then öffnet sich ausschließlich dessen Begründung; Kriterienname und qualitative Einstufung bleiben in der Listenzeile sichtbar.
3. **Qualitative Stufen dezent unterscheiden**
   - Given Kriterien aller vier Stufen sowie ein Kriterium ohne gültige Einstufung
   - When die Liste angezeigt wird
   - Then erscheint jede ausgeschriebene Einstufung als zurückhaltend getönte Textmarke und bleibt auch ohne Farbwahrnehmung eindeutig verständlich.
4. **Lange Kriterien responsiv lesen**
   - Given ein langer Kriterienname auf einer schmalen Ansicht
   - When die Kriterienliste angezeigt wird
   - Then umbrechen Nummer, Name und Einstufung in einer stabilen Hierarchie, ohne horizontalen Bildlauf oder abgeschnittenen Text.

### Gestaltungsentscheidung

- Die Offenlegung `Kriterien im Detail` bleibt die erste Ebene und nennt zusätzlich die Anzahl der Kriterien.
- Darin erscheint eine echte nummerierte Liste. Jede Listenzeile ist eine eigene Offenlegung; die Begründung richtet sich typografisch am Kriteriennamen aus.
- Beim Öffnen der Liste wird kein einzelnes Kriterium automatisch bevorzugt oder geöffnet.
- Die Einstufungen verwenden kleine, entsättigte Farbflächen. Text und Farbe sind redundant, damit die Bedeutung nicht von Farbwahrnehmung abhängt.
- Die Palette bleibt ruhig und vermeidet kräftige Ampelsignale. Geöffnete Zustände werden weiterhin ausschließlich durch den Korall-Akzent und das Minuszeichen gekennzeichnet.
- Datenhaltung, Schwellenwerte, API und Lehrkraftansichten bleiben unverändert.
