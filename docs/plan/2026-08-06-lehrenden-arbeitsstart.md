# Lehrenden-Startseite als Arbeitsstarter

## User Story

Als Lehrkraft möchte ich auf der Startseite unmittelbar Unterricht durchführen oder eine zuletzt bearbeitete Lerneinheit weiter vorbereiten, damit ich ohne Umweg über selten benötigte Verwaltungsübersichten zu meiner eigentlichen Arbeit gelange.

## Produktentscheidungen

- Die Startseite zeigt ausschließlich die gleichwertigen Arbeitswege `Unterrichten` und `Vorbereiten`.
- Die Live-Auswahl beginnt bewusst leer. Erst Kurs und dann Lerneinheit werden gewählt.
- Vor dem Öffnen von Live werden keine Lernenden- oder Aufgabenkennzahlen geladen.
- Der Authoring-Einstieg zeigt höchstens drei Einträge in derselben Reihenfolge wie der nach letzter Bearbeitung sortierte Lerneinheitenkatalog.
- Kurse und Diagnostik werden im Seiteninhalt nicht wiederholt.
- Auf breiten Ansichten trennt nur eine Linie die beiden Arbeitsbereiche; kompakte Ansichten stapeln sie.

## BDD-Szenarien und Testzuordnung

### Live-Unterricht auswählen

**Gegeben** eine angemeldete Lehrkraft mit mehreren eigenen Kursen, **wenn** sie `/teaching` öffnet, einen Kurs und anschließend eine zugeordnete Lerneinheit auswählt, **dann** führt `Live öffnen` mit beiden IDs zur bestehenden Live-Ansicht.

- Automatisierung: API-, Komponenten- und authentifizierter `@feature-acceptance`-Browsertest.

### Bewusst leere Auswahl

**Gegeben** eine Lehrkraft öffnet die Startseite, **wenn** noch keine Auswahl getroffen wurde, **dann** ist kein Kurs vorausgewählt, die Lerneinheit deaktiviert und die Live-Aktion nicht ausführbar.

- Automatisierung: Komponententest und Browserabnahme.

### Kurswechsel und verspätete Antworten

**Gegeben** eine laufende Lerneinheitenanfrage, **wenn** die Lehrkraft rasch zu einem anderen Kurs wechselt, **dann** werden Auswahl und Fehler zurückgesetzt und eine verspätete Antwort des ersten Kurses nicht dargestellt.

- Automatisierung: Komponententest mit kontrollierten Anfrageantworten.

### Fehlende oder nicht ladbare Lerneinheiten

**Gegeben** ein eigener Kurs ohne Lerneinheit oder ein vorübergehender Ladefehler, **wenn** der Kurs ausgewählt wird, **dann** bleibt `Live öffnen` deaktiviert und die Oberfläche zeigt einen knappen Leerzustand beziehungsweise eine gezielte Wiederholung.

- Automatisierung: Komponenten- und Routentest.

### Vorbereitung fortsetzen

**Gegeben** mehr als drei eigene Lerneinheiten, **wenn** die Lehrkraft die Startseite öffnet, **dann** erscheinen höchstens die drei zuletzt bearbeiteten Einheiten in derselben Reihenfolge wie im Katalog und führen direkt in ihr Authoring.

- Automatisierung: API-, Komponenten- und authentifizierter `@feature-acceptance`-Browsertest.

### Neue Lerneinheit beginnen

**Gegeben** die Startseite, **wenn** die Lehrkraft `Neue Lerneinheit` wählt, **dann** öffnet `/teaching/units?create=1` zuverlässig den vorhandenen Erstellungsdialog.

- Automatisierung: Server-, Komponenten- und authentifizierter `@feature-acceptance`-Browsertest.

### Eigentümergrenzen und leere Bestände

**Gegeben** fremde Kurse oder Lerneinheiten sowie wahlweise ein vollständig leerer eigener Bestand, **wenn** die Lehrkraft die Startseite lädt, **dann** werden ausschließlich eigene Objekte ausgeliefert und passende leere Arbeitszustände angeboten. Lernende erhalten keinen Zugriff.

- Automatisierung: API-, Autorisierungs- und Datenbankintegrationstest.

### Responsivität und Themes

**Gegeben** Light oder Dark auf Desktop, Tablet oder Smartphone, **wenn** die Startseite dargestellt wird, **dann** bleiben beide Arbeitswege kontrastreich und tastaturbedienbar, wechseln unter `64rem` in eine gestapelte Darstellung und erzeugen keinen horizontalen Überlauf.

- Automatisierung: Komponenten-, berechneter Browserstil- und visueller Browsertest.

## Technische Abgrenzung

- `TeacherHome` wird als internes BFF-Read-Model auf Kursoptionen, letzte Lerneinheiten und Authoring-Links zugeschnitten.
- Die vorhandene autorisierte Live-Lerneinheitenprojektion eines Kurses bleibt unverändert.
- Es gibt keine Datenbankmigration und keine lokale Speicherung der Auswahl.
- `PageActionHead`, `QuietList` und `QuietListEntry` bleiben die gemeinsamen UI-Grundbausteine; die abhängige Live-Auswahl bleibt eine kleine fachbezogene Komponente.
- Abschließend laufen gezielte Tests, die visuelle Browserprüfung, `make test-visual-smoke` und `make verify-feature`.
