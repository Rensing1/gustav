# UI/UX-Design-Leitfaden für eine performante und barrierefreie FOSS-Lernplattform

## Einleitung: Die stille Pädagogik des Designs

Dieses Dokument dient als zentraler Leitfaden für die Gestaltung einer Lernplattform, bei der das Design nicht nur eine ästhetische Komponente ist, sondern ein integraler Bestandteil der pädagogischen Erfahrung. Es übersetzt die Kernprinzipien des Projekts – Performance, Fokus, Benutzerfreundlichkeit und Barrierefreiheit – in konkrete, umsetzbare Designentscheidungen.

Die zugrundeliegende Philosophie folgt dem Grundsatz „Weniger, aber besser“. Jedes Element auf dem Bildschirm muss seinen Platz rechtfertigen und dem Lernenden dienen. Ein minimalistisches Design reduziert die kognitive Belastung, also die Menge an mentaler Anstrengung, die zur Bedienung der Oberfläche notwendig ist.1 Dies ermöglicht es den Schülerinnen und Schülern, sich vollständig auf das Wesentliche zu konzentrieren: den Lerninhalt.2

Der Leitfaden ist in vier logische Teile gegliedert. Er führt schrittweise von der übergeordneten Struktur der Plattform über die Gestaltung der einzelnen Komponenten bis hin zu den Details des visuellen Systems und den grundlegenden technischen Aspekten der Barrierefreiheit.

## Teil 1: Fundament für Fokus und Klarheit: Layout, Struktur und Hierarchie

Dieser Teil legt das strukturelle Fundament der gesamten Plattform. Ein durchdachtes Layout ist die Basis für eine intuitive Nutzerführung und stellt sicher, dass die Lerninhalte immer im Mittelpunkt stehen.

### Das responsive Grundgerüst: Ein Mobile-First-Ansatz

Ein modernes Layout für eine Lernplattform sollte auf einem einfachen Drei-Zonen-Prinzip basieren, das auf allen Geräten konsistent funktioniert.

- **Header (Kopfzeile):** Die Kopfzeile ist bewusst minimalistisch gehalten. Sie enthält lediglich das Logo oder den Titel der Plattform, den Namen des angemeldeten Nutzers und eine Funktion zum Ausloggen. Auf mobilen Geräten wird hier zusätzlich das „Hamburger“-Icon platziert, das zur Steuerung der Seitenleiste dient.
    
- **Seitenleiste (Navigation):** Dies ist das primäre Navigationsinstrument. Die Gestaltung folgt einem responsiven Muster, das sich an die Grösse des Anzeigegeräts anpasst.
    
- **Inhaltsbereich (Main Content):** Dies ist der grösste Bereich der Seite, der ausschliesslich den Lerninhalten gewidmet ist. Um die Lesbarkeit auf sehr grossen Bildschirmen zu gewährleisten und übermässig lange Textzeilen zu vermeiden, sollte die maximale Breite des Inhaltsbereichs begrenzt werden, beispielsweise auf einen Wert von 1200px.
    

Die einklappbare Seitenleiste erfordert eine flexible Strategie, die sich an die jeweilige Bildschirmgrösse anpasst:

- **Mobilgeräte (Bildschirmbreite unter 768px):** Auf kleinen Bildschirmen ist die Seitenleiste standardmässig ausgeblendet (ein sogenanntes Off-Canvas-Muster). Sie wird durch das Tippen auf das Hamburger-Icon im Header eingeblendet und legt sich über den Inhaltsbereich. Dieses Vorgehen maximiert den knappen Bildschirmplatz für den eigentlichen Inhalt.5
    
- **Tablets & Desktops (Bildschirmbreite 768px und grösser):** Auf grösseren Bildschirmen ist die Seitenleiste standardmässig sichtbar, jedoch in einem schmalen, Icon-basierten Modus (ca. 60px Breite). Dies bietet einen schnellen Zugriff auf die Navigation, ohne viel Platz zu beanspruchen. Eine Schaltfläche zum Erweitern erlaubt das Ausklappen auf die volle Breite (ca. 250px), um auch die Textbeschriftungen der Navigationspunkte anzuzeigen.5 Diese duale Funktionalität – eingeklappt für einen schnellen Überblick, ausgeklappt für volle Lesbarkeit – ist eine bewährte Methode für komplexe Webanwendungen.8
    

Die technische Logik zum Umschalten zwischen den Zuständen der Seitenleiste (z.B. eine CSS-Klasse `.active` für die mobile Ansicht und `.min` für den eingeklappten Desktop-Zustand) lässt sich mit wenigen Zeilen JavaScript realisieren, was eine performante und leichtgewichtige Lösung darstellt.5

Der Mobile-First-Ansatz ist für eine EdTech-Plattform nicht nur eine technische Best Practice, sondern eine Frage der Bildungsgerechtigkeit. Für viele Schüler, insbesondere in sozioökonomisch schwächeren Verhältnissen, ist das Smartphone das primäre oder sogar einzige Gerät für den Zugang zum Internet.1 Ein Design, das auf mobilen Geräten nicht einwandfrei funktioniert, schliesst diese Schülerinnen und Schüler effektiv von der Teilhabe aus.9 Indem die mobile Erfahrung als Grundlage des Designs dient, wird sichergestellt, dass die Kernfunktionalität für alle zugänglich ist.8 Die Desktop-Ansicht wird dann zu einer „progressiven Verbesserung“, die den zusätzlichen Platz sinnvoll nutzt, anstatt nur eine verkleinerte Version einer für grosse Bildschirme konzipierten Seite zu sein. Dies ist eine direkte Umsetzung des Prinzips der Inklusivität.

### Die visuelle Ordnung: Lerninhalte in den Mittelpunkt rücken

Eine klare visuelle Hierarchie führt den Blick der Nutzer und schafft eine intuitive Ordnung auf der Seite. Dies wird durch den bewussten Einsatz von Grösse, Kontrast und Leerraum erreicht.

- **Grösse & Skalierung:** Das wichtigste Element auf einer Seite, beispielsweise der Titel einer Lerneinheit, muss auch das grösste und prominenteste Textelement sein. Unterüberschriften sind entsprechend kleiner, der Fliesstext am kleinsten. Diese Abstufung schafft eine sofort verständliche Informationsstruktur.10
    
- **Kontrast:** Interaktive Elemente wie Buttons oder Links müssen sich farblich klar vom Hintergrund und von nicht-interaktiven Elementen abheben. Ein hoher Kontrast zieht die Aufmerksamkeit auf sich und signalisiert dem Nutzer: „Hier kannst du etwas tun“.10
    
- **Leerraum (Whitespace):** Der grosszügige Einsatz von Leerraum um Textblöcke, Bilder und Aufgaben ist entscheidend. Leerraum reduziert visuelles „Rauschen“, gruppiert zusammengehörige Elemente und lenkt den Fokus auf den Inhalt.12 Dies ist ein Kernprinzip des minimalistischen Designs, das Ablenkungen minimiert.2
    

Am Beispiel einer Lerneinheit zur Fotosynthese lässt sich dies konkret illustrieren:

- **H1-Überschrift:** `<h1>Fotosynthese: Die Energie des Lichts</h1>` – Gross, fette Schrift, mit deutlichem Abstand nach oben und unten, um als klarer Startpunkt der Seite zu dienen.
    
- **Einleitungsabsatz:** Normaler Fliesstext, direkt unter der H1-Überschrift platziert.
    
- **Interaktives Element:** Ein Button mit der Aufschrift `[Video ansehen]` erhält eine klare Akzentfarbe und ist visuell vom umgebenden Text getrennt.
    
- **H2-Unterüberschrift:** `<h2>Die zwei Phasen der Fotosynthese</h2>` – Kleiner als die H1, aber deutlich grösser als der Fliesstext, um einen neuen Abschnitt zu signalisieren.
    
- **Aufgabenblock:** Visuell in einem Kasten (einer sogenannten „Card“) mit einem leicht abgetönten Hintergrund gruppiert, um ihn klar vom umgebenden Lesetext zu trennen.
    

Eine starke visuelle Hierarchie fungiert als eine Art unsichtbarer Lehrer. Sie führt den Schüler durch die Lektion, ohne explizite Anweisungen geben zu müssen. Eine unklare Hierarchie kann zu „Choice Paralysis“ führen, einem Zustand, in dem der Nutzer unsicher ist, was als Nächstes zu tun ist.13 Dies erhöht die kognitive Belastung 1 und lenkt vom eigentlichen Lernprozess ab. Eine gut gestaltete Hierarchie hingegen schafft einen natürlichen „Flow“ 10: Der Blick wird von der Hauptüberschrift zum einleitenden Text und dann zur ersten Aufgabe gelenkt. Diese implizite Führung ist besonders wichtig für Schülerinnen und Schüler mit Konzentrationsschwierigkeiten und unterstützt das ablenkungsfreie Kernprinzip der Plattform. Die Hierarchie ist somit nicht nur ein Design-Aspekt, sondern eine didaktische Methode.

## Teil 2: Gestaltung der Kernkomponenten für einen nahtlosen Lernfluss

Hier wird das Design der wiederkehrenden Bausteine definiert, die das Herz der Plattform bilden. Konsistenz und eine intuitive Bedienbarkeit sind hier der Schlüssel zum Erfolg.

### Intuitive Kurs-Navigation in der Seitenleiste

Die verschachtelte Struktur von Kursen, Lerneinheiten und Abschnitten muss in der Seitenleiste klar und verständlich abgebildet werden.

- **Visuelle Darstellung:** Ein Akkordeon-Muster ist hierfür ideal. Zunächst sind nur die Kurstitel sichtbar. Ein Klick oder Tippen auf einen Kurs klappt die zugehörigen Lerneinheiten auf. Lerneinheiten und Abschnitte werden durch Einrückungen visuell hierarchisiert, um ihre Beziehung zueinander darzustellen. Der aktuell ausgewählte Abschnitt wird farblich oder durch eine fette Schriftart hervorgehoben, um dem Nutzer jederzeit Orientierung zu geben („You are here“). Icons können diese Hierarchie zusätzlich unterstützen: ein Buch-Icon für den Kurs, ein Kapitel-Icon für die Lerneinheit und ein Seiten-Icon für den Abschnitt.
    
- **Visualisierung des Fortschritts:** Neben jedem Navigationspunkt (Lerneinheit, Abschnitt) sollte ein subtiler Fortschrittsindikator platziert werden. Ein einfacher Kreis, der sich mit zunehmendem Fortschritt füllt, oder ein Haken-Icon bei 100% Abschluss ist ausreichend. Diese Indikatoren sollten dezent sein, um nicht abzulenken, aber präsent genug, um Motivation zu schaffen und einen schnellen Überblick zu ermöglichen.4 Komplexe Prozentzahlen sollten in der Navigation vermieden werden; eine visuelle Repräsentation ist schneller erfassbar.
    

### Die Aufgabenansicht und das KI-Feedback: Ein konstruktiver Dialog

Die Darstellung des KI-Feedbacks ist ein kritischer Moment in der Nutzererfahrung. Das Design muss Vertrauen schaffen und den Lernprozess unterstützen.

- **Visuelle Trennung:** Die Einreichung des Schülers und das KI-Feedback müssen klar voneinander getrennt sein.
    
    - **Schülereinreichung:** In einem neutralen Container mit einem klaren Titel, z.B. „Deine Antwort“.
        
    - **KI-Feedback:** In einem separaten Container direkt darunter, der sich visuell abhebt. Eine leicht andere Hintergrundfarbe (z.B. ein sehr helles Blau oder Grün) und ein eindeutiges Icon (z.B. eine Glühbirne oder ein stilisiertes „KI“-Symbol) machen die Quelle des Feedbacks sofort kenntlich.
        
- **Gestaltung des KI-Feedbacks:**
    
    - **Sprache und Tonalität:** Das Feedback sollte stets positiv und konstruktiv formuliert sein. Statt „Das ist falsch“ sind Formulierungen wie „Guter Ansatz! Überlege doch mal, ob…“ zu bevorzugen.15
        
    - **Struktur:** Das Feedback sollte in leicht verdauliche Abschnitte gegliedert werden. Ein Akkordeon ist hierfür ein ideales UI-Element: Eine kurze Zusammenfassung ist immer sichtbar, während Details zu spezifischen Punkten (z.B. „Rechtschreibung“, „Argumentationsstruktur“) bei Bedarf aufgeklappt werden können.
        
    - **UI-Elemente:** Info-Boxen eignen sich für allgemeine Hinweise. Icons können die Textwand aufbrechen und das Feedback leichter scannbar machen: eine Glühbirne für Ideen, eine Lupe für Detailanalysen oder ein Zitat-Icon für Textbeispiele. Aggressive Farben sollten vermieden werden. Insbesondere reines Rot für Fehler kann demotivierend wirken. Besser ist ein sanftes Orange oder eine einfache Hervorhebung der betreffenden Stelle, deren Problematik im Text erklärt wird.2
        
- **Flexibilität für die Zukunft:** Das Design in separaten Containern ist zukunftssicher. Langfristig können die Feedback-Container einfach in Sprechblasen umgewandelt werden, um eine dialogbasierte Ansicht zu ermöglichen, ohne die grundlegende Struktur der Seite ändern zu müssen.
    

Das UI-Design des KI-Feedbacks definiert die Beziehung zwischen dem Schüler und der künstlichen Intelligenz. Es muss Vertrauen aufbauen und die KI als ein Werkzeug zur Selbstverbesserung positionieren, nicht als einen urteilenden Richter. Schüler, insbesondere in der Sekundarstufe, können empfindlich auf Kritik reagieren. Ein schlecht gestaltetes, wertend wirkendes Feedback kann demotivieren und die Akzeptanz der gesamten Plattform untergraben. Die Forschung zum Thema KI-Feedback betont die Wichtigkeit eines positiven Framings 15 und der Möglichkeit, es mit menschlicher Aufsicht zu kombinieren.17 Das UI muss diese pädagogische Sensibilität widerspiegeln. Durch die Verwendung von sanften Farben, einer konstruktiven Sprache und einer Struktur, die zur Exploration einlädt (wie bei Akkordeons), wird die Interaktion als eine sichere, private Konversation gestaltet. Dies fördert eine wachstumsorientierte Denkweise („growth mindset“) und ist entscheidend für den Lernerfolg.

### Das Karteikarten-Modul: Effizienz durch Reduktion

Das Design des Karteikarten-Moduls sollte sich auf maximale Effizienz und minimale Ablenkung konzentrieren, ähnlich wie bei bewährten Tools wie Anki.18

- **Minimalistische Karten-UI:** Die Karteikarte sollte das zentrale und fast einzige Element auf dem Bildschirm sein. Ein klares Card-UI-Design mit deutlichen Rändern und viel Leerraum drumherum ist hierfür passend.20 Die Vorderseite zeigt nur die Frage. Ein Klick oder Tippen auf die Karte deckt die Antwort auf, idealerweise mit einer dezenten Flip-Animation. Die Rückseite zeigt die Antwort und darunter die Bewertungsbuttons.
    
- **Design der Selbsteinschätzungs-Buttons:** Die Beschriftung muss klar und einfach sein: „Erneut“ (oder „Schwer“), „Gut“, „Einfach“. Die Buttons sollten am unteren Rand der Karte platziert werden, mit ausreichend Abstand zueinander, um Fehleingaben auf Touch-Geräten zu vermeiden. Farben können die Bedeutung unterstützen, dürfen aber nicht das einzige Unterscheidungsmerkmal sein, um die Barrierefreiheit zu gewährleisten. Beispielsweise könnte „Erneut“ ein warnendes Orange, „Gut“ ein neutrales Grau oder die Primärfarbe der Plattform und „Einfach“ ein positives Grün erhalten. Diese Farben müssen immer mit Text und/oder Icons kombiniert werden.
    

### Das Lehrer-Dashboard: Aussagekräftige Einblicke ohne Informationsflut

Ein Dashboard für Lehrkräfte muss schnell erfassbare und handlungsrelevante Informationen liefern.

- **Best Practices:** Lehrkräfte haben wenig Zeit. Das Dashboard muss daher auf einen Blick die wichtigsten Informationen vermitteln („at a glance“).22 Die Informationen sollten eine Geschichte erzählen: Die wichtigste Kennzahl steht oben links, gefolgt von detaillierteren Aufschlüsselungen.22 Anstatt zu versuchen, alles darzustellen, sollte sich das Dashboard auf 2-3 Schlüsselmetriken konzentrieren, die eine pädagogische Handlung erfordern.22
    
- **Vorgeschlagene Visualisierungen:**
    
    1. **Fortschrittsübersicht (Tabelle):** Eine einfache Tabelle listet die Schüler in den Zeilen und die Lerneinheiten in den Spalten auf. Die Zellen werden farblich kodiert (z.B. Grün für „abgeschlossen“, Gelb für „in Arbeit“, Grau für „nicht begonnen“). Dies gibt einen schnellen Überblick darüber, welche Schüler möglicherweise Unterstützung benötigen.
        
    2. **Aufgabenschwierigkeit (Balkendiagramm):** Ein horizontales Balkendiagramm zeigt die durchschnittliche Anzahl der Versuche oder die Bearbeitungszeit pro Aufgabe. Lange Balken signalisieren der Lehrkraft sofort, welche Aufgaben möglicherweise zu schwer oder unklar formuliert sind und einer Überarbeitung bedürfen.
        
    3. **Engagement-Metrik (KPI):** Eine einzelne, grosse Zahl, die anzeigt, wie viele Schüler in der letzten Woche aktiv waren. Dies dient als einfacher „Gesundheitscheck“ für die Klasse.
        

Ein gutes Lehrer-Dashboard ist kein Überwachungsinstrument, sondern ein diagnostisches Werkzeug, das pädagogische Interventionen ermöglicht. Die reine Darstellung von Noten oder Abschlussquoten ist wenig hilfreich. Die Daten müssen eine Geschichte erzählen.22 Das Balkendiagramm zur Aufgabenschwierigkeit beispielsweise verlagert den Fokus von der reinen Schülerleistung („Wer ist schlecht?“) auf die Qualität des Lehrmaterials („Was ist schlecht?“). Dies befähigt die Lehrkraft, proaktiv den eigenen Unterricht zu verbessern, anstatt nur reaktiv Schüler zu bewerten. Das Dashboard wird so von einem reinen Reporting-Tool zu einem Instrument der Unterrichtsentwicklung.

## Teil 3: Ein minimalistisches und barrierefreies Design-System

Ein Design-System stellt sicher, dass die Plattform konsistent, wiedererkennbar und effizient zu entwickeln ist. Für ein FOSS-Projekt ist ein logisches, regelbasiertes System von unschätzbarem Wert.

### Typografie: Lesbarkeit als oberste Priorität

Die Wahl der Schriftart und die Definition einer klaren typografischen Hierarchie sind grundlegend für die Lesbarkeit und Barrierefreiheit.

- **Schriftart-Empfehlungen (Google Fonts):**
    
    - **Fliesstext & UI:** **Lexend**. Diese Schriftart wurde speziell entwickelt, um visuellen Stress zu reduzieren und die Lesbarkeit zu verbessern, insbesondere für Menschen mit Leseschwächen wie Legasthenie.25 Ihre erweiterten Zeichenabstände und klaren Buchstabenformen kommen jedoch allen Lesern zugute.27
        
    - **Überschriften (Optional):** **Inter** oder **Work Sans**. Dies sind sehr vielseitige, neutrale und extrem gut lesbare serifenlose Schriften. Sie sind in vielen Schriftstärken verfügbar und harmonieren gut mit Lexend.31
        
- **Typografische Skala:** Für Schriftgrössen sollten relative Einheiten (`rem`) verwendet werden. Dies respektiert die im Browser individuell eingestellte Standardschriftgrösse des Nutzers – eine wichtige Anforderung der Barrierefreiheit. Eine Basis-Schriftgrösse von `1rem` (entspricht meist 16px) für den Fliesstext ist ein guter Ausgangspunkt. Darauf aufbauend wird eine klare Skala definiert.
    

Die folgende Tabelle dient als „Single Source of Truth“ für alle Textstile. Sie stellt Konsistenz sicher und kann direkt in CSS-Variablen oder ein Theming-System übersetzt werden. Ohne ein solches definiertes System treffen Entwickler Ad-hoc-Entscheidungen, was zu einem inkonsistenten Erscheinungsbild führt. Diese Tabelle formalisiert die Hierarchie 11, stellt sicher, dass die Schriftgrössen WCAG-konform sind, und beschleunigt die Entwicklung.

**Tabelle 1: Typografie-System**

|Stilbezeichnung|Schriftart|Schriftgrösse (rem)|Schriftstärke|Zeilenhöhe|
|---|---|---|---|---|
|Überschrift H1|Inter|2.441|700 (Bold)|1.2|
|Überschrift H2|Inter|1.953|700 (Bold)|1.3|
|Überschrift H3|Inter|1.563|600 (SemiBold)|1.4|
|Fliesstext (Body)|Lexend|1.0|400 (Regular)|1.6|
|UI-Element/Button|Lexend|0.9|500 (Medium)|1.2|
|Hilfetext (Caption)|Lexend|0.8|400 (Regular)|1.5|

### Farbpalette: Kontrastreich, ruhig und bedeutungsvoll

Die Farbpalette sollte ruhig und nicht ablenkend sein, um den Fokus auf den Inhalt zu legen.2 Jede Farbkombination für Text und Hintergrund muss mindestens das WCAG-AA-Kontrastverhältnis von 4.5:1 für normalen Text und 3:1 für grossen Text erfüllen.32

Die folgende Übersicht knüpft direkt an die im Code definierten Themes an. Beide Farbsets sind WCAG-AA geprüft und werden in `app/static/css/gustav.css` als Variablen hinterlegt. Indem wir in den Komponenten ausschließlich mit semantischen Rollen (z.B. `--color-primary`) arbeiten, können neue Paletten ohne refactor eingeführt werden – ein Muss für FOSS-Projekte, die von Schulen oder Schüler:innen weiterentwickelt werden.

**Tabelle 2: Rosé Pine Dawn – Standard-Light-Theme**

|Rolle|CSS-Variable|HEX|Hinweis|
|---|---|---|---|
|Grundfläche|`--color-bg-base`|`#FAF4ED`|Canvas/Fensterhintergrund|
|Surface|`--color-bg-surface`|`#FFFAF3`|Karten, Panels|
|Overlay|`--color-bg-overlay`|`#F2E9E1`|Modale Ebenen, Tabellenkopf|
|Text|`--color-text`|`#575279`|Primäre Schrift|
|Text (Muted)|`--color-text-muted`|`#9893A5`|Sekundärtexte, Meta|
|Primär|`--color-primary`|`#286983` (`var(--rp-pine)`) |Buttons, Links, Fokus|
|Sekundär|`--color-secondary`|`#D7827E`|Akzent, Highlights|
|Success|`--color-success`|`#56949F`|Positive Statusmeldungen|
|Warning|`--color-warning`|`#EA9D34`|Hinweise, Warnungen|
|Error|`--color-error`|`#B4637A`|Fehler, destruktive Aktionen|
|Border|`--color-border`|`#F2E9E1`|Rahmen, Linien|

**Tabelle 3: Everforest Dark Hard – Standard-Dark-Theme**

|Rolle|CSS-Variable|HEX|Hinweis|
|---|---|---|---|
|Grundfläche|`--color-bg-base`|`#272E33`|Hintergrund dunkler Screens|
|Surface|`--color-bg-surface`|`#2E383C`|Karten, Panels|
|Overlay|`--color-bg-overlay`|`#374145`|Modale Ebenen, Tabellenkopf|
|Text|`--color-text`|`#D3C6AA`|Primäre Schrift|
|Text (Muted)|`--color-text-muted`|`#859289`|Sekundärtexte, Meta|
|Primär|`--color-primary`|`#A7C080` (`var(--ef-green)`) |Buttons, Links, Fokus|
|Sekundär|`--color-secondary`|`#83C092`|Akzent, Highlights|
|Success|`--color-success`|`#A7C080`|Positive Statusmeldungen|
|Warning|`--color-warning`|`#DBBC7F`|Hinweise, Warnungen|
|Error|`--color-error`|`#E67E80`|Fehler, destruktive Aktionen|
|Border|`--color-border`|`#414B50`|Rahmen, Linien|

**Interaktionszustände (Hover, Fokus, Active)**

|Zustand|Light Theme (Rosé Pine)|Dark Theme (Everforest)|Verwendung|
|---|---|---|---|
|Hover|`rgba(40, 105, 131, 0.08)`|`rgba(167, 192, 128, 0.08)`|`--color-bg-hover`, Links & Sidebar|
|Fokus|`rgba(40, 105, 131, 0.15)`|`rgba(167, 192, 128, 0.15)`|`--color-bg-focus`, Fokusflächen|
|Active|`rgba(40, 105, 131, 0.20)`|`rgba(167, 192, 128, 0.20)`|`--color-bg-active`, aktive Navigation|
|Fokus-Ring|`#286983`|`#A7C080`|`--color-focus-ring`, Skip-Link, Buttons|

Alle Komponenten und Utility-Klassen greifen ausschließlich auf diese Variablen zurück. Beispiel: Die Skip-Link-Schaltfläche nutzt `--color-primary`, die Sidebar-Links erhalten ihre Hoverflächen über `--color-bg-hover`. Dadurch bleiben Hell- und Dunkelmodus automatisch synchron und DSGVO-konforme Barrierefreiheit (konstante Kontrastwerte) ist bereits auf Codeebene abgesichert.

### Abstände und Raster: Das 8-Pixel-Raster als Ordnungsprinzip

Das 8-Pixel-Raster (oder 8pt Grid) ist ein einfaches, aber wirkungsvolles System zur Schaffung visueller Ordnung.

- **Konzept:** Alle Grössen (Breite, Höhe) und Abstände (margin, padding) von UI-Elementen sind ein Vielfaches von 8 (z.B. 8px, 16px, 24px, 32px).34
    
- **Vorteile:** Dieses System schafft ein harmonisches und aufgeräumtes Erscheinungsbild. Es vereinfacht Design- und Entwicklungsentscheidungen, da es ein klares Regelwerk für Abstände gibt. Zudem schafft es eine gemeinsame Sprache zwischen Design und Entwicklung und erleichtert die Implementierung eines responsiven Designs über verschiedene Bildschirmgrössen hinweg.
    

## Teil 4: Barrierefreiheit in der Praxis: Die Top 3 für Entwickler

Dieser Abschnitt konzentriert sich auf die drei Massnahmen mit dem grössten positiven Einfluss auf die Barrierefreiheit, die von Entwicklern sofort umgesetzt werden können.

### Semantisches HTML: Die kostenlose Grundlage für Zugänglichkeit

Das grundlegendste Prinzip der Web-Barrierefreiheit ist die Verwendung von semantischem HTML. Das bedeutet, immer das HTML-Element zu verwenden, das die Bedeutung seines Inhalts am besten beschreibt. Ein Browser und Screenreader wissen, wie sich ein `<button>`-Element verhält, aber ein `<div>`-Element, das mit CSS wie ein Button gestaltet wurde, ist für sie nur eine bedeutungslose Box.35

- **Beispiele:**
    
    - Verwenden von `<nav>` für die Hauptnavigation anstelle von `<div id="nav">`.
        
    - Verwenden von `<main>` für den Hauptinhaltsbereich.
        
    - Verwenden von `<button>` für Aktionen, die auf der aktuellen Seite stattfinden (z.B. „Antwort senden“), und `<a>` für die Navigation zu einer anderen Seite.
        
    - Strukturierung von Text mit `<h1>`, `<h2>`, `<p>`, `<ul>` etc.
        

### Vollständige Tastaturbedienbarkeit: Navigation ohne Maus

Jeder interaktive Teil der Seite muss ausschliesslich mit der Tastatur (Tab, Shift+Tab, Enter, Leertaste, Pfeiltasten) erreichbar und bedienbar sein.37

- **Fokus-Indikator:** Der Standard-Fokusring des Browsers (oft ein blauer Rahmen) darf **niemals** mit `outline: none;` entfernt werden, ohne eine gut sichtbare Alternative zu bieten. Ein sichtbarer Fokus ist die einzige Orientierung für Tastaturnutzer.
    
- **Logische Reihenfolge:** Die Reihenfolge, in der Elemente beim Drücken der Tab-Taste fokussiert werden, sollte der visuellen Lesereihenfolge entsprechen. Dies wird durch eine logische DOM-Struktur meist automatisch erreicht.
    
- **Keine Fokus-Fallen:** Der Nutzer darf nicht in einem Element (z.B. einem Pop-up-Fenster) gefangen sein, ohne mit der Tastatur wieder herauszukommen.
    

### ARIA für dynamische Komponenten: Wenn HTML nicht ausreicht

ARIA (Accessible Rich Internet Applications) ist eine „Zusatzschicht“ an Informationen für Screenreader, wenn die Semantik von HTML nicht ausreicht, um den Zustand oder die Funktion eines dynamischen Widgets zu beschreiben.38 ARIA ändert nichts am Aussehen oder Verhalten eines Elements; es fügt lediglich Bedeutung hinzu. Die erste und wichtigste Regel von ARIA lautet: Wenn es ein natives HTML-Element für den Zweck gibt, sollte dieses immer bevorzugt werden.40

- **Anwendungsfälle für dieses Projekt:**
    
    - **Icon-Buttons:** Ein Button, der nur ein Icon enthält, benötigt eine textliche Beschreibung für Screenreader: `<button aria-label="Menü öffnen"><svg>...</svg></button>`.
        
    - **Akkordeons (in der Navigation):** Der Button, der ein Akkordeon öffnet, muss seinen Zustand kommunizieren: `<button aria-expanded="false">Kurs A</button>`. Wenn das Akkordeon geöffnet ist, wird der Wert per JavaScript auf `true` geändert.
        
    - **Dynamische Fehlermeldungen:** Wenn eine Fehlermeldung nach einer Aktion erscheint, kann `aria-live="polite"` dafür sorgen, dass der Screenreader die Meldung vorliest, ohne den Fokus des Nutzers zu unterbrechen.
        

Die folgende Tabelle fasst die drei wichtigsten, sofort umsetzbaren Massnahmen zusammen und liefert Code-Beispiele als direkte Vorlage. Für einen Entwickler, der neu im Thema Barrierefreiheit ist, kann die Menge an WCAG-Richtlinien überwältigend sein. Diese Tabelle reduziert die Komplexität auf die drei fundamentalsten und wirkungsvollsten Punkte und bietet einen klaren, priorisierten Einstiegspunkt.

**Tabelle 3: WCAG-Schnellstart für Entwickler**

|Massnahme|Warum es entscheidend ist|Konkretes Code-Beispiel|
|---|---|---|
|**1. Semantisches HTML**|Bietet eine robuste, kostenlose Basis für Screenreader und Tastaturnavigation. Der Browser kümmert sich um viele Aspekte der Zugänglichkeit automatisch.|**Falsch:** `<div class="button" onclick="doSomething()">Senden</div>` **Richtig:** `<button onclick="doSomething()">Senden</button>`|
|**2. Sichtbarer Fokus-Indikator**|Zeigt Tastaturnutzern, wo sie sich auf der Seite befinden. Ohne ihn ist die Navigation praktisch unmöglich.|**Niemals tun:** `*:focus { outline: none; }` **Besser (Beispiel für einen benutzerdefinierten Stil):** `*:focus-visible { outline: 2px solid #1d4289; outline-offset: 2px; }`|
|**3. `aria-label` für Icon-Buttons**|Gibt rein visuellen Steuerelementen einen zugänglichen Namen, den Screenreader vorlesen können. Ohne ihn sind diese Elemente für blinde Nutzer „stumm“.|**Falsch:** `<button><svg... /></button>` **Richtig:** `<button aria-label="Einstellungen öffnen"><svg... /></button>`|

## Schlussfolgerung: Ein lebendiges System

Dieser Leitfaden legt ein solides Fundament für eine Lernplattform, die ihre pädagogischen Ziele durch klares, fokussiertes und inklusives Design unterstützt. Die Kernprinzipien – ein responsives Layout, eine klare visuelle Hierarchie, intuitiv gestaltete Komponenten und ein barrierefreies Design-System – arbeiten zusammen, um eine ablenkungsfreie und effektive Lernumgebung zu schaffen.

Es ist jedoch wichtig zu verstehen, dass dieser Leitfaden kein starres Regelwerk ist, sondern der Startpunkt für ein lebendiges Design-System. Die wichtigste Empfehlung ist, regelmässig Feedback von den echten Nutzern – den Schülerinnen, Schülern und Lehrkräften – einzuholen und das Design auf dieser Grundlage iterativ zu verbessern.9 Als FOSS-Projekt besteht die einzigartige Chance, eine Plattform zu schaffen, die nicht nur von einer Person, sondern mit und für die Community wächst und sich weiterentwickelt.
