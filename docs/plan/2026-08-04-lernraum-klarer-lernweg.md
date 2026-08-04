# Lernraum als klaren Lernweg neu ordnen

## User Story

Als Schüler möchte ich vom Lernpfad in ein Modul und von dort in einen eindeutig abgegrenzten Aufgabenarbeitsraum gelangen, damit ich jederzeit verstehe, wo ich mich befinde und wie ich zu meinem Lernstoff zurückkehre.

## Produktentscheidungen

- Modulare Lerneinheiten beginnen im Lernpfad, lineare Lerneinheiten in der Leseansicht.
- Der Lernraum kennt genau die Oberflächenzustände `graph`, `reading` und `task`.
- Die URL ist nach einem Neuladen die Quelle für den sichtbaren Zustand.
- Geöffnete Module werden in didaktischer Reihenfolge gelesen und nicht dupliziert.
- Materialien sind zunächst vollständig geöffnet und können pro Browsertab eingeklappt werden.
- Eine Aufgabe besitzt einen eigenen Arbeitsraum und einen festen Rückweg zum Ursprungsmodul.
- Die Kontextfläche ist eine Arbeitshilfe, keine zusätzliche Navigationsebene.
- Kopfzeile, Toolbar und Lernraum verwenden ein gemeinsames Raster mit höchstens `80rem` Breite.
- OpenAPI, Datenbankschema und fachliche DTOs bleiben unverändert.

## BDD-Szenarien und Testzuordnung

| Szenario | Given | When | Then | Automatisierter Test |
|---|---|---|---|---|
| Hierarchischer Lernweg | Eine angemeldete Person öffnet eine modulare Lerneinheit | Sie öffnet ein Modul und beginnt eine Aufgabe | Graph, Leseansicht und Aufgabenraum folgen als getrennte Verlaufseinträge; sichtbare Rückwege führen jeweils eine Ebene zurück | `frontend/e2e/learner-navigation.spec.ts` (`@feature-acceptance`) |
| Kanonische URLs | Ein zugängliches Modul und eine Aufgabe existieren | Eine URL mit `module`, `task` oder `panel=result` wird direkt geladen | Der passende Zustand wird wiederhergestellt; alte `view`- und `history`-Parameter werden sicher normalisiert | `frontend/src/lib/learning-unit/learner-navigation.test.ts`, Route-Vertragstest |
| Didaktische Reihenfolge | Mehrere Module wurden in beliebiger Reihenfolge geöffnet | Die Leseansicht erscheint | Die Module stehen in Graph- und Phasenreihenfolge und jedes Modul kommt nur einmal vor | bestehender `workspace.test.ts`, Komponenten-Test |
| Zugängliche Materialien | Ein Modul enthält Text-, Bild- und PDF-Material | Die Leseansicht wird geöffnet und ein Materialtitel betätigt | Alle Materialien sind zunächst offen; Titelzeile und Pfeil sind bedienbar und der Zustand wird tabbezogen gespeichert | `LearningMaterialCard.test.ts`, `learner-workspace-state.test.ts` |
| Kompakte Arbeitsaufträge | Eine Aufgabe besitzt eine lange Anweisung | Die Leseansicht erscheint | Die Vorschau belegt höchstens zwei Zeilen; auf kleinen Breiten steht die Startaktion darunter | Stil-Vertrag und Visual-Smoke |
| Einheitlicher Aufgabenraum | Eine Text-, Upload-, H5P-, Werkzeug- oder Dialogaufgabe wird begonnen | Der Arbeitsraum öffnet sich | Ein gemeinsamer sticky Aufgabenkopf zeigt den Rückweg; Aufgabe und Kontext sind von der Bearbeitung nur durch eine Linie getrennt | `LearnerContentWorkspace.test.ts`, Browserabnahme |
| Dialognavigation | Eine Dialogaufgabe ist aktiv | Der Schüler arbeitet oder beendet den Dialog | Es gibt keine zusätzliche Pausieren-Aktion im Partnerkontext; der gemeinsame Rückweg bleibt sichtbar | Dialog-Komponententest und Browserabnahme |
| Rückkehrposition | Eine Aufgabe wird aus einem gescrollten Modul begonnen | Der sichtbare Rückweg oder Browser-Zurück wird verwendet | Modul, Scrollposition und Fokus werden wiederhergestellt | Komponenten-Test und Browserabnahme |
| Sichere Korrektur | URL oder lokaler Zustand verweist auf gesperrte Inhalte | Die Seite wird geladen | Der nächste gültige Zustand wird mit `replaceState` gewählt, ohne gesperrte Inhalte anzuzeigen | Navigations- und Server-Vertragstest |
| Responsive Hierarchie | Der Lernraum wird auf Desktop, Notebook, Tablet und Smartphone geöffnet | Die Breite ändert sich | Es entstehen weder horizontales Überlaufen noch drei funktionale Spalten; die kompakte Inhaltsnavigation bleibt zugänglich | Visual-Smoke bei 1920×1080, 1366×768, 1024×768 und 390×844 |

## Umsetzung

1. Navigationszustand und URL-Vertrag testgetrieben auf `graph | reading | task` umstellen.
2. Lernpfad und schulbuchartige Leseansicht hierarchisch verbinden; alte Ansichtstabs entfernen.
3. Materialzustand, barrierefreie Titelzeilen und Medienvorschauen korrigieren.
4. Gemeinsamen Aufgabenkopf und flachen Arbeitsraum für alle Aufgabenfamilien einführen.
5. Dialog- und Kontextaktionen in den gemeinsamen Navigationsrahmen einordnen.
6. Alte produktive Pane- und Split-Zustände entfernen.
7. Gemeinsames `80rem`-Raster, Responsive-Regeln und integrierte Referenzbilder aktualisieren.

## Abnahme

Vor jedem Commit laufen die betroffenen Komponenten- und Vertragstests. Vor der Fertigmeldung laufen zusätzlich `make test-visual-smoke` und `make verify-feature`. Der vollständige authentifizierte Browser-Rundlauf löst keine unbeständigen Modellaufrufe aus.

## Ergänzende Arbeitsphase: Schulbuch-Arbeitsraum mit Quellenstapel

### User Story

Als Schüler möchte ich während der Aufgabenbearbeitung relevante Materialien und eigene frühere Abgaben wie auf einer aufgeschlagenen Buchseite lesen können, damit ich Quellen nachschlagen kann, ohne meine aktuelle Arbeit oder Gesprächsposition zu verlieren.

### Produktentscheidungen

- Ab `72rem` Komponentenbreite stehen eine ausreichend breite Buchseite und das Arbeitsheft als zwei unabhängig scrollbare Flächen nebeneinander.
- Die Buchseite ist `clamp(32rem, 44cqw, 38rem)` breit; darunter bleibt die umschaltbare Vollbreitenansicht `Aufgabe | Materialien` erhalten.
- Aufgabenstellung, aktuelles Material und bewusst hinzugefügter Kontext erscheinen als fortlaufender Dokumentstapel, nicht als gegenseitig ersetzende Ansichten.
- Aktuelle und angeheftete Dokumente sind zunächst geöffnet. Rückmeldungen, Kriterien und ältere Versuche bleiben zunächst eingeklappt.
- `Groß lesen` ist eine bewusste Vollbreitenansicht innerhalb des Aufgabenraums. Sie ändert weder URL noch Browserhistorie und lässt die Aufgabe montiert.
- Bilder aus Materialien und eigenen Abgaben erscheinen direkt, unverzerrt und unbeschnitten im Lesefluss. PDFs erhalten eine eingebettete Vorschau; andere Dateien eine sichere Öffnen-Aktion.
- Ein gemeinsamer Dokumentrenderer wird in Leseansicht, Aufgabenarbeitsraum und Dialogkontext verwendet.
- Der schülerbezogene Zustandsvertrag wird auf Version 3 angehoben. Version 2 wird ohne den damals automatisch gesetzten Leseschlüssel übernommen.
- OpenAPI, Datenbankschema und fachliche DTOs bleiben unverändert.

### Ergänzende BDD-Szenarien und Testzuordnung

| Szenario | Given | When | Then | Automatisierter Test |
|---|---|---|---|---|
| Fortlaufende Buchseite | Eine Aufgabe besitzt mehrere Materialien | Der Arbeitsraum öffnet sich | Aufgabenstellung und Materialien stehen vollständig, geöffnet und in didaktischer Reihenfolge untereinander | `LearnerContentWorkspace.test.ts` |
| Kontext hinzufügen | Ein weiteres Material oder eine eigene frühere Abgabe ist zugänglich | Der Schüler fügt den Eintrag hinzu | Der Eintrag erscheint geöffnet am Ende des Stapels, ohne den Lesemodus zu öffnen | Komponenten- und Zustandstest |
| Deduplizierung | Ein Material ist bereits als aktuelles Material sichtbar | Derselbe Schlüssel wird als manueller Kontext angeboten | Das Dokument erscheint nur einmal | Komponenten-Test |
| Zugänglicher Aufklappzustand | Ein Dokument ist geöffnet | Die Titelzeile wird betätigt | Inhalt und `aria-expanded` wechseln gemeinsam und werden tabbezogen wiederhergestellt | Dokument- und Zustandstest |
| Eigene Abgabe | Eine frühere Text-, Bild- oder Datei-Abgabe liegt vor | Sie wird dem Kontext hinzugefügt | Inhalt und Datei erscheinen direkt; Rückmeldung, Kriterien und ältere Versuche bleiben zunächst eingeklappt | Dokument-Komponententest |
| Bildmaterial | Ein sichtbares Dateimaterial ist ein Bild | Die Buchseite lädt | Das echte Bild lädt mit korrektem Alternativtext und positivem `naturalWidth`, ohne Beschnitt | Komponenten-Test und authentifizierte Browserabnahme |
| Angeheftetes Bild nach Neuladen | Ein Bild aus einem weiteren zugänglichen Modul wurde angeheftet | Der Schüler lädt den Aufgabenraum neu | Das Quellmodul wird sicher nachgeladen; Titel und Bild erscheinen erneut statt UUID und dauerhaftem Ladehinweis | Route-Vertragstest und `frontend/e2e/learner-navigation.spec.ts` (`@feature-acceptance`) |
| Ladefehler | Eine Bilddatei ist nicht verfügbar | Der Browser meldet einen Bildfehler | Eine verständliche Meldung und die weiterhin mögliche Öffnen-Aktion erscheinen | Dokument-Komponententest |
| Bewusster Lesemodus | Ein längeres Dokument ist sichtbar | `Groß lesen` und anschließend `Zurück zur Aufgabe` werden betätigt | Nur der bewusste Klick öffnet die Vollbreitenansicht; Fokus, Buchposition und Entwurf bleiben erhalten | Komponenten-Test und Browserabnahme |
| Unabhängiges Arbeiten | Buchseite und Arbeitsheft enthalten lange Inhalte | Beide Flächen werden auf Desktop gescrollt | Beide Scrollpositionen verändern und erhalten sich unabhängig | Browserabnahme und berechnete Styles |
| Kompakte Breiten | Derselbe Arbeitsraum erscheint auf Tablet oder Smartphone | Zwischen `Aufgabe` und `Materialien` gewechselt wird | Jeweils eine Vollbreitenfläche ist sichtbar; beide bleiben montiert und behalten ihren Zustand | Komponenten-Test und Visual-Smoke |
| Dialogkontext | Eine Dialogaufgabe besitzt Material und frühere Abgaben | Der Dialogarbeitsraum öffnet sich | Partnerinformationen und Dokumentstapel stehen links, Gespräch und Eingabe rechts; dieselbe bewusste Leseansicht wird verwendet | Dialog-Komponententest und Browserabnahme |
| Datenschutz | Zwei Schüler verwenden dieselbe Aufgabe | Beide laden ihren Tabzustand | Referenzen, Aufklappzustände und Lesepositionen bleiben schülerbezogen getrennt | Zustandstest |

### Umsetzung und Abnahme dieser Arbeitsphase

1. Zustandsvertrag und Tests auf Version 3 erweitern.
2. Gemeinsamen Renderer für Markdown, Bilder, PDFs, sonstige Dateien und eigene Abgaben testgetrieben einführen.
3. Automatische und manuelle Referenzen zu einem deduplizierten Dokumentstapel zusammenführen.
4. Bewussten Vollbreiten-Lesemodus mit Fokus- und Scrollwiederherstellung implementieren.
5. Den identischen Quellenstapel in Dialogaufgaben verwenden.
6. Responsive Zweiflächen- und Kompaktansicht gestalten, dokumentieren und visuell abnehmen.
7. Abschließend `make test-visual-smoke` und `make verify-feature` ausführen.
