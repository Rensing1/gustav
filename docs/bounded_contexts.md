## Bounded Contexts
1. **Benutzerverwaltung:** Verwaltet die Identitäten, Rollen und Gruppenzugehörigkeiten von allen Benutzern.
2. **Unterrichten:** Ermöglicht Lehrern das Erstellen, Verwalten und Wiederverwenden von Lerninhalten (Lerneinheiten) und deren Organisation in Kursen.
3. **Lernen:** Wickelt den interaktiven Prozess der Aufgabenbearbeitung durch Schüler und die Generierung von Feedback ab.
4. **Diagnostik:** Bereitet Leistungsdaten aus dem Lernprozess zur Analyse für Lehrer auf.

### Unterrichten
**1. `Kurs`-Aggregat** Dieses Aggregat ist nun deutlich "leichter". Es verwaltet nicht mehr den Inhalt der Lerneinheiten, sondern nur noch die _Beziehung_ zu ihnen und die kurs-spezifischen Konfigurationen.
- **`Kurs` (Aggregats-Stamm)**
    - Kurs-ID
    - Titel
    - Lehrer-ID (Autor) (externe Referenz)
    - Kontextwissen (kurs-spezifisch)
    - **Liste von `Kursmodulen` (Entitäten innerhalb des Kurs-Aggregats)**
        - **Lerneinheit-ID** (externe Referenz zum `Lerneinheit`-Aggregat)
        - **Reihenfolge** im Kurs
        - **Liste der freigegebenen Abschnitts-IDs** (Hier leben die Freigaben!)
**2. `Lerneinheit`-Aggregat** Dies ist der wiederverwendbare Baustein. Er existiert unabhängig von einem Kurs.
- **`Lerneinheit` (Aggregats-Stamm)**
    - Lerneinheit-ID
    - Titel
    - Autor-ID (wer hat diesen Baustein erstellt?)
    - Liste von `Abschnitten`
        - Liste von `Material`
        - Liste von `Aufgaben`
            - ... (inkl. Kriterien, Lösungshinweise, Versuchszahl etc.)
### Lernen
**`Einreichung` (Aggregats-Stamm)**
- Einreichung-ID
- **Schüler-ID** (externe Referenz zur `Benutzerverwaltung`)
- **Aufgaben-ID** (externe Referenz zur `Lerneinheit` im "Unterrichten"-Kontext)
- **Kurs-ID** (wichtiger Kontext, externe Referenz)
- Eingereichter Inhalt (z.B. Text, Dateipfad)
- Zeitstempel der Einreichung
- Liste von **`Bewertungen` (Entitäten innerhalb des Aggregats)**
    - Bezug zum `Analysekriterium` der Aufgabe
    - Ergebnis/Score
- **`Formatives Feedback` (Wertobjekt oder Entität innerhalb des Aggregats)**
    - Generierter Feedback-Text

### Beziehungen zwischen den Kontexten
Die Benutzerverwaltung muss folgendes über jeden Nutzer wissen:
- ID
- E-Mail
- Name
- Rolle
- Account erstellt an:
- Passwort-Hash
  
Weitergeben muss die Benutzerverwaltung aber nur folgende Informationen:
- Name
- ID
- Rolle


Der Unterrichten-Kontext weiß über einen Kurs:
- ID
- Name
- Lehrer-ID
- Kontextwissen
- Liste von Lerneinheiten, inkl. Reihenfolge im Kurs und Abschnittsfreigaben

Der Unterrichten-Kontext weiß über eine Lerneinheit:
- ID
- Titel
- Ersteller (Autor-ID)
- Liste von Abschnitten (inkl. Liste von Material, Liste von Aufgaben)

Der Unterrichten-Kontext muss an den Lernen-Kontext weitergeben:
- alles über eine Lerneinheit
- Freigabestatus der Abschnitte
- Kontextwissen
  
Der Unterrichten-Kontext muss an den Diagnostik-Kontext weitergeben:
- alles, was auch an den Lernen-Kontext weitergegeben wurde
  
Der Lernen-Kontext muss an den Diagnostik-Kontext weitergeben:
- Einreichungen der Schüler
- KI-Analyse und KI-Feedback

Außerdem muss der Lernen-Kontext auch an den Unterricht-Kontext weitergeben (für die Live-Unterrichts-Ansicht):
- Einreichungen der Schüler
- KI-Analyse und KI-Feedback

### **Context Map**

```
graph TD
    subgraph "Core Services (Upstream)"
        Benutzerverwaltung
        Unterrichten
    end

    subgraph "Process & Analytics (Downstream)"
        Lernen
        Diagnostik
    end

    Benutzerverwaltung -- UserContextDTO --> Unterrichten
    Benutzerverwaltung -- UserContextDTO --> Lernen
    Benutzerverwaltung -- UserContextDTO --> Diagnostik

    Unterrichten -- LerninhaltFuerLernprozessDTO --> Lernen

    Lernen -- EinreichungsdatenDTO --> Diagnostik
    Unterrichten -- (Strukturdaten) --> Diagnostik

    %% Die NEUE Feedback-Schleife für die Live-Ansicht
    Lernen -- EinreichungsdatenDTO (Echtzeit) --> Unterrichten

