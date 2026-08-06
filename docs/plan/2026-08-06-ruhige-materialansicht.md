# Materialkontext aus geöffneten Modulen ableiten

## User Story

Als Schüler möchte ich während einer Aufgabe genau die Materialien der Module sehen, die ich zuvor im Lernpfad geöffnet habe, damit der Graph und der Arbeitskontext dasselbe verständliche Modell verwenden und ich keine zweite Quellensammlung verwalten muss.

## Produktentscheidungen

- Bei modularen Lerneinheiten sind die geöffneten Module die einzige Quelle für den Materialkontext.
- Das Modul der aktiven Aufgabe steht zuerst und bleibt geöffnet. Weitere Module folgen in Lernpfad-Reihenfolge und beginnen eingeklappt.
- `Zum Lernpfad` erhält während einer laufenden Aufgabe einen Auswahlzustand. Das Öffnen eines Moduls führt direkt zur weiterhin montierten Aufgabe zurück.
- Auf kompakten Ansichten wird nach der Rückkehr die Materialfläche gezeigt und das neue Modul fokussiert.
- Zusätzliche Module können nur im Materialbereich geschlossen werden. Ein lokaler Hinweis bietet das Wiederherstellen des zuletzt geschlossenen Moduls an.
- Eigene frühere Abgaben stehen je Modul in einer zunächst geschlossenen Untergruppe und werden erst beim Öffnen geladen.
- Lineare Lerneinheiten zeigen alle freigeschalteten Abschnitte; nur der Abschnitt der aktiven Aufgabe beginnt geöffnet.
- Anheftungen, Quellenbaum, `Material suchen` und wiederholte Herkunftsmarker entfallen.
- Die sichtbare Hierarchie folgt einem ruhigen Baum: Modul → Material oder
  Untergruppe `Eigene Abgaben` → einzelne Abgabe. Verbindungslinien und
  Einrückung verdeutlichen die Ebenen, nicht zusätzliche Karten oder Rahmen.
- Offenlegungschevrons stehen immer links vor dem zugehörigen Titel. Rechts
  erscheinen ausschließlich Aktionen der jeweiligen Ebene: `Groß lesen` an
  Dokumenten und `Modul schließen` an zusätzlichen Modulen.

## BDD-Szenarien und Testzuordnung

### Geöffnete Module bilden den Kontext

**Gegeben** mehrere zugängliche, aber nur zwei geöffnete Module, **wenn** der Schüler eine Aufgabe bearbeitet, **dann** zeigt die Materialfläche ausschließlich diese beiden Module, das Aufgabenmodul zuerst und weitere Module in Lernpfad-Reihenfolge.

- Automatisierung: Zustands-, Komponenten- und authentifizierter `@feature-acceptance`-Browsertest.

### Weiteres Modul über den Lernpfad öffnen

**Gegeben** eine laufende Aufgabe mit Text-, Datei- oder Dialogzustand, **wenn** der Schüler über `Zum Lernpfad` ein weiteres Modul öffnet, **dann** bleibt die Arbeitsfläche montiert, die Aufgabe erscheint wieder und das neue Modul ist mit seinem ersten Material geöffnet.

- Automatisierung: Komponenten- und authentifizierter `@feature-acceptance`-Browsertest.

### Kompakte Rückkehr

**Gegeben** eine Tablet- oder Smartphonebreite, **wenn** ein weiteres Modul über den Lernpfad geöffnet wird, **dann** zeigt die Rückkehr die Materialfläche und fokussiert das neue Modul ohne horizontalen Überlauf.

- Automatisierung: Browserstil- und `@feature-acceptance`-Test.

### Zusätzliches Modul schließen und wiederherstellen

**Gegeben** ein zusätzlich geöffnetes Modul, **wenn** der Schüler es im Materialbereich schließt, **dann** verschwindet es aus Lernraum und Kontext und kann über `Rückgängig` mit seinem vorherigen Offenlegungszustand wiederhergestellt werden. Das Modul der aktiven Aufgabe besitzt keine Schließen-Aktion.

- Automatisierung: Zustands-, Komponenten- und Browsertest.

### Dokumente lesen

**Gegeben** ein geöffnetes Modul mit mehreren Materialien, **wenn** der Schüler Dokumente aufklappt, **dann** dürfen mehrere gleichzeitig geöffnet bleiben und vollständige Inhalte erscheinen im gemeinsamen Scrollbereich. Die Großansicht bleibt verfügbar.

- Automatisierung: Komponenten-, CSS-Vertrags- und visueller Browsertest.

### Eigene Abgaben laden

**Gegeben** Aufgaben mit früheren eigenen Abgaben in einem sichtbaren Modul, **wenn** der Schüler `Eigene Abgaben` öffnet, **dann** werden die Historien erst jetzt geladen und neueste Abgabe, ältere Versuche, Rückmeldung und Auswertung zugänglich dargestellt.

- Automatisierung: Komponenten- und Routentest.

### Lineare Lerneinheit

**Gegeben** eine lineare Lerneinheit mit mehreren freigeschalteten Abschnitten, **wenn** eine Aufgabe bearbeitet wird, **dann** stehen alle Abschnitte im Materialbereich, der aktuelle zuerst und geöffnet, die übrigen eingeklappt und ohne Schließen-Aktion.

- Automatisierung: Komponententest.

### Wiederherstellung und verlorener Zugriff

**Gegeben** gespeicherte Zustände einer älteren Version oder eines anderen Schülers, **wenn** der Lernraum wiederhergestellt wird, **dann** werden alte Anheftungen verworfen, nur weiterhin zugängliche Module und Offenlegungen übernommen und keine fremden Zustände gelesen.

- Automatisierung: Zustandskomponententest.

### Kontrast und Responsivität

**Gegeben** die Materialfläche in Light oder Dark, **wenn** Module, Dokumente und eigene Abgaben dargestellt werden, **dann** bleiben Inhalte und Aktionen kontrastreich, fokussierbar und bei Desktop-, Tablet- und Smartphonebreite ohne horizontalen Überlauf.

- Automatisierung: statischer Stil-Vertrag, berechnete Browserstyles und visuelle Referenzen.

### Baumhierarchie und Aktionszuordnung

**Gegeben** ein geöffnetes Modul mit Materialien und eigenen Abgaben, **wenn**
der Schüler den Materialbereich betrachtet, **dann** erkennt er Modul,
Dokumente, Abgabengruppe und einzelne Abgaben an abgestuften Baumebenen mit
linksstehenden Chevrons. Ein Material oder eine Abgabe bietet nur `Groß lesen`,
die Abgabengruppe keine Nebenaktion und ein zusätzliches Modul nur `Modul
schließen`.

- Automatisierung: Komponenten-, statischer CSS-Vertrags- und authentifizierter
  Browserstiltest.

**Gegeben** dieselbe Hierarchie bei schmaler Komponentenbreite, **wenn** Titel
mehrzeilig werden, **dann** wird die Einrückung verdichtet, alle Titel bleiben
lesbar, die Berührungsflächen mindestens 44 Pixel hoch und es entsteht kein
horizontaler Überlauf.

- Automatisierung: berechneter Browserstiltest und visuelle Referenzen bei
  Tablet- und Smartphonebreite.

## Technische Abgrenzung

- OpenAPI, Datenbank, Backend-Endpunkte und fachliche DTOs ändern sich nicht.
- `openedModuleIds` beziehungsweise die geöffneten Modultabs werden zur alleinigen Quelle modularer Kontextgruppen.
- Der tabbezogene Zustand speichert Modul- und Dokumentoffenlegungen, Rückkehrzweck, Fokus und Scrollposition, aber keine Material- oder Abgabeinhalte.
- Die lokale Speicherversion wird erhöht. Ältere manuelle Referenzen und Pickerzustände werden bewusst nicht übernommen.
- Produktive Gestaltung verbleibt in der vorhandenen CSS-Lernschicht und verwendet ausschließlich zentrale Theme-Werte.
- Abschließend laufen gezielte Komponenten- und Browsertests, die visuelle Prüfung sowie `make verify-feature`.
