# Plan: Filius `.fls` Upload + deterministische Evidence-Pipeline

Datum: 2026-05-01
Status: Planned

## Kontext / Problem

GUSTAV unterstützt für besondere Aufgabenformate bereits upload-only Abgaben:

- Scratch: `.sb3` wird validiert, deterministisch zu `scratch.evidence.v2` extrahiert und anschließend vom Feedback-LLM bewertet.
- Calliope: MakeCode `.hex` wird validiert, deterministisch zu `makecode.evidence.v1` extrahiert und anschließend vom Feedback-LLM bewertet.

Filius-Aufgaben sollen in dieselbe Architektur passen. Schüler laden eine Filius-Projektdatei (`.fls`) hoch. GUSTAV extrahiert daraus einen menschenlesbaren, reproduzierbaren Evidence-Text, zeigt diesen als Abgabe an und nutzt ausschließlich diesen Text für Analyse und Rückmeldung.

Eine echte inf-schule-Beispieldatei (`filius_webserver.fls`) bestätigt die technische Grundlage: `.fls` ist ein ZIP-Archiv mit `projekt/konfiguration.xml`. Diese XML ist ein `java.beans.XMLDecoder`-Dokument und enthält nacheinander Projektversion, Knoten, Kabel und Dokumentation. Weil `XMLDecoder` für untrusted data ein Deserialisierungsrisiko wäre, darf GUSTAV die Datei in der ersten Filius-Implementierung nicht per Java-Deserialisierung laden.

## Zielbild (vollständige erste Filius-Implementierung)

- Lehrkraft erstellt `Task.kind=filius`.
- Schüler können bei Filius-Tasks nur `.fls` hochladen.
- API validiert `.fls` früh beim Finalisieren der Abgabe:
  - kein ZIP oder defektes ZIP -> `400 invalid_filius_archive`
  - fehlendes `projekt/konfiguration.xml` -> `400 missing_filius_configuration`
  - XML nicht als erlaubtes Filius-XML interpretierbar -> `400 invalid_filius_configuration`
  - XML/Container überschreitet harte Limits -> `400 filius_configuration_too_large`
  - Storage-Bytes nicht abrufbar -> `503 filius_validation_unavailable`
- Worker-Pipeline bleibt wie bei Scratch/Calliope:
  - kein OCR, kein Vision-Modell
  - deterministische Extraktion aus `.fls` zu `# filius.evidence.v1`
  - Feedback-LLM bewertet Kriterien ausschließlich anhand dieses Evidence-Texts
- Schüler- und Lehreransicht rendern die Evidence als kompakten Topologiebericht, nicht als Roh-XML.
- Vollständig heißt: GUSTAV extrahiert alle fachlich relevanten, sicher und deterministisch aus der `.fls` lesbaren Filius-Simulationsdaten.
- Vollständig heißt nicht: Java-Objekte rekonstruieren, Filius-Code ausführen, Roh-XML übernehmen oder Passwörter in Evidence, Logs oder LLM-Kontext übernehmen.

## User Story

Als Informatiklehrkraft möchte ich Filius-Projekte als `.fls` einreichen lassen, damit GUSTAV Netzwerkaufgaben nachvollziehbar auswerten kann und Schüler eine verständliche Rückmeldung auf Basis ihrer tatsächlichen Projektkonfiguration erhalten.

## BDD-Szenarien

1. Filius-Task erstellen
   Given eine Lehrkraft erstellt eine Aufgabe mit `filius: {}`
   When die Teaching-API die Aufgabe speichert
   Then hat die Aufgabe `kind=filius` und gibt ein leeres `filius`-Config-Objekt zurück.

2. Upload-only UI
   Given `Task.kind=filius`
   When ein Schüler die Task-Seite öffnet
   Then sieht er nur ein Upload-Feld für `.fls`.

3. Upload-Intent erlaubt nur FLS
   Given `Task.kind=filius`
   When Upload-Intent mit `kind=file`, Dateiname `projekt.fls` und MIME `application/x.filius.fls` angefragt wird
   Then enthält die Response `accepted_mime_types=["application/x.filius.fls"]`.

4. Submission akzeptiert gültige FLS
   Given `Task.kind=filius` und eine gültige `.fls` mit `projekt/konfiguration.xml`
   When `POST .../submissions` mit `kind=file` und Filius-Metadata kommt
   Then Response `202`, Submission `analysis_status=pending`.

5. Submission lehnt falsche Abgabearten ab
   Given `Task.kind=filius`
   When ein Schüler Text, Bild, PDF, SB3 oder HEX einreicht
   Then Response `400 invalid_input` oder `400 invalid_file_payload`.

6. Nicht-Filius-Tasks lehnen FLS ab
   Given `Task.kind=native|visual|scratch|calliope`
   When ein Schüler `.fls` einreicht
   Then Response `400 mime_not_allowed` beim Upload-Intent oder `400 invalid_file_payload` beim Finalisieren.

7. Security: defekter Container
   Given eine Datei mit `.fls`-Endung, die kein gültiges ZIP ist
   When sie finalisiert wird
   Then Response `400 invalid_filius_archive`.

8. Security: fehlende Konfiguration
   Given ein gültiges ZIP ohne `projekt/konfiguration.xml`
   When es finalisiert wird
   Then Response `400 missing_filius_configuration`.

9. Security: XML nicht erlaubt
   Given `konfiguration.xml` enthält DOCTYPE/DTD, externe Entities oder unbekannte ausführungsnahe Klassen
   When sie geparst wird
   Then Response `400 invalid_filius_configuration`.

10. Worker: Evidence -> Feedback
    Given eine gültige Filius-Submission
    When der Worker den Job verarbeitet
    Then `text_md` beginnt mit `# filius.evidence.v1`, `analysis_json` bleibt im bestehenden Kriterien-Schema und `feedback_md` wird aus der Evidence erzeugt.

## Contract-first: OpenAPI-Änderungen

- `Task.kind`-Enums erweitern: `native|h5p|visual|scratch|calliope|filius`.
- Neues Schema `FiliusTaskConfig`:
  - leeres Objekt
  - `additionalProperties: false`
  - Beschreibung: upload-only Filius-Projektdatei `.fls`, MIME `application/x.filius.fls`.
- `Task`, `TaskCreate`, `TaskUpdate`, `TeacherUnitNodeEditorTask`, `LearningTask`:
  - optionales Feld `filius`
  - mutually exclusive zu `h5p`, `visual`, `scratch`, `calliope`.
- Learning Upload-Intent:
  - MIME-Beschreibung und Enum um `application/x.filius.fls` erweitern.
  - Beschreibung ergänzt: Für `Task.kind=filius` nur `.fls`.
- Learning Submissions:
  - file-MIME-Enum um `application/x.filius.fls` erweitern.
  - Task-type rules um Filius ergänzen.
  - 400/503 detail codes ergänzen:
    - `invalid_filius_archive`
    - `missing_filius_configuration`
    - `invalid_filius_configuration`
    - `filius_configuration_too_large`
    - `filius_validation_unavailable`

## Datenbank / Migration

- `public.unit_tasks.kind`-Check um `filius` erweitern.
- `public.learning_submissions` file-MIME-Check um `application/x.filius.fls` erweitern.
- Storage-Bucket-Allowlist `submissions` additiv um `application/x.filius.fls` erweitern.
- Keine Filius-spezifischen Spalten in der ersten Implementierung.

## KISS / DRY: zentrale Abgabeformat-Policy

Filius wird als vollständiges Feature umgesetzt; es werden keine fachlich relevanten Filius-Bestandteile bewusst auf später verschoben. Die Komplexität wird stattdessen durch eine kleine zentrale Format-Policy begrenzt.

### Entscheidung

Vor der Filius-Verdrahtung wird die bestehende Scratch/Calliope-Matrix in eine kleine interne Policy in `backend/storage/learning_policy.py` überführt.

Diese Policy beschreibt pro upload-only Format nur die Upload-/Submission-Regeln:

- `task_kind`
- erlaubte Submission-Art (`file`)
- erlaubte MIME-Typen
- Dateiendung für Storage-Keys
- Upload-Hinweis für die UI
- API-Detail-Code, falls Storage-Bytes für die frühe Validierung nicht geladen werden können

Diese Policy ist keine Plugin-Architektur. Sie ist nur eine einfache, typisierte Tabelle plus wenige Helper, damit Upload-Intent, Submission-Finalisierung, Repo-Guards und UI dieselbe Quelle der Wahrheit verwenden.

Worker-Backends, Evidence-Builder und Parser-Implementierungen bleiben bewusst außerhalb dieser Policy. Der Worker darf die Policy nutzen, um unterstützte MIME-Typen zu kennen; die eigentliche Extraktion bleibt aber in klar getrennten Formatmodulen (`backend/scratch`, `backend/makecode`, `backend/filius`).

Falls die Policy später zu groß wird, darf sie nach `backend/learning/submission_formats.py` umziehen. Diese Auslagerung ist kein Bestandteil der ersten Filius-Implementierung.

### Format-Matrix

- Scratch: `scratch` -> `application/x.scratch.sb3` -> `.sb3`
- Calliope: `calliope` -> `application/x.makecode.hex` -> `.hex`
- Filius: `filius` -> `application/x.filius.fls` -> `.fls`

Native, Visual und H5P bleiben fachlich unverändert. Visual bleibt Upload-only für Bild/PDF, Native bleibt Text plus Bild/PDF, H5P bleibt eigener synchroner Submission-Typ.

### Nicht-Ziele

- keine generische Submission-Plugin-Schicht
- keine dynamischen Imports aus Konfiguration
- keine neue Datenbanktabelle für Formatregeln
- keine Worker- oder Parser-Registry in der Upload-Policy
- keine Java-Deserialisierung
- keine Aufweichung der bisherigen Security-Guards

## Parser-Strategie

### Entscheidung

Die erste Filius-Implementierung nutzt einen Python-Allowlist-Parser:

- ZIP wird wie bei Scratch streng begrenzt gelesen.
- `projekt/konfiguration.xml` wird nie mit Java `XMLDecoder` deserialisiert.
- XML wird als Datenformat per allowlisted Parser interpretiert.
- Unbekannte, nicht fachlich ausgewertete XML-Teile werden nicht ausgeführt und nicht ungefiltert in Evidence übernommen.

### Begründung

Filius speichert Projekte als Java-XMLDecoder-Format. Ein Java-Worker mit Filius-Klassen wäre funktional attraktiv, würde aber untrusted Schülerdateien in einen Deserialisierungspfad bringen. Für GUSTAV im Schulkontext ist die sichere Default-Architektur daher: nur Daten extrahieren, keine Objekte rekonstruieren, keine Methoden ausführen.

Ein isolierter Java-Worker bleibt als spätere technische Ausweichstrategie möglich, falls reale Filius-Dateien mit dem Allowlist-Parser nicht zuverlässig genug abdeckbar sind. Dieser Worker müsste dann in einem eigenen Container ohne Netzwerk, ohne Secrets, mit read-only RootFS, CPU-/RAM-Limits und klarer JSON-Schnittstelle laufen. Diese Option ist kein Bestandteil der ersten Implementierung.

### Parser-Allowlist v1

Die Allowlist ist die zentrale Datenstruktur des Filius-Parsers. Sie wird im Code explizit gepflegt und getestet. Sie beschreibt, welche Java-Klassen und welche Properties aus dem XML fachlich ausgewertet werden dürfen. Alles andere wird weder ausgeführt noch roh in Evidence übernommen.

Erlaubte Hauptbereiche:

- Projektstruktur:
  - Versionsstring als erstes XML-Objekt.
  - Knotenliste aus `filius.gui.netzwerksicht.GUIKnotenItem`.
  - Kabelliste aus `filius.gui.netzwerksicht.GUIKabelItem`.
  - Dokumentationsliste aus `filius.gui.netzwerksicht.GUIDocuItem`.
- Hardware/Knoten:
  - bekannte Knotenklassen aus `filius.hardware.knoten.*`, mindestens Rechner/Notebook/Switch/Vermittlungsrechner/Modem.
  - ausgewertete Properties: Name/Label, GUI-Position, Netzwerkinterfaces, Systemsoftware.
  - unbekannte Hardwareklassen werden als `unknown`-Knoten mit Java-Klasse und auswertbaren Basisdaten geführt, nicht abgelehnt.
- Netzwerkinterfaces:
  - Properties: IP, Subnetzmaske, Gateway, DNS, MAC, Port, Wireless-Flag.
  - mehrere Interfaces pro Knoten sind erlaubt und werden stabil sortiert.
- Links:
  - `GUIKabelItem.kabelpanel.ziel1/ziel2` zur Zuordnung der Endpunkte.
  - Wireless-Flag aus dem Kabelobjekt, falls persistent vorhanden.
- Systemsoftware:
  - `InternetKnotenBetriebssystem` mit Dateisystem, installierten Anwendungen, Weiterleitungstabelle, DHCP/RIP/IP-Forwarding-Indizien, Standard-Gateway und DNS-Server-Feld, soweit persistent vorhanden.
- Anwendungen:
  - bekannte Standard-Anwendungen werden mit Java-Klasse, Anzeigename und fachlich relevanter Konfiguration aufgenommen.
  - unbekannte Standard-Anwendungen werden als `unknown_application` mit Java-Klasse gezählt, nicht abgelehnt.
- Routing:
  - manuelle Routen aus `Weiterleitungstabelle.manuelleTabelle`.
  - automatische Routen werden nur aus Interfaces/Gateways abgeleitet und klar als `derived` markiert.
- Firewall:
  - `Firewall`, `FirewallRule`, `FirewallWebKonfig`.
  - Properties: `activated`, `defaultPolicy`, `dropICMP`, `filterSYNSegmentsOnly`, `filterUdp`, `srcIP`, `srcMask`, `destIP`, `destMask`, `protocol`, `port`, `action`.
- Dateisystem:
  - Nur fachlich relevante Simulationspfade: `/dns/hosts`, `/webserver/*`, `/www.conf/vhosts`, E-Mail-Konfigurations-/Mailbox-Dateien, soweit sie als Filius-Dateisystemdaten persistiert sind.
  - Alle Dateiinhalte sind bounded, escaped und mit Truncation-Hinweisen versehen.
- E-Mail:
  - Mailserver-/Client-Apps, Domains, Server, Ports, Konten, simulierte E-Mail-Adressen, Betreff und bounded Mailkörper werden aufgenommen.
  - Passwörter werden nie aufgenommen.
- Dokumentation:
  - `GUIDocuItem` mit Typ, Text, Position, Größe, Farbe als einfache Werte, soweit vorhanden.
- Eigene Anwendungen:
  - `projekt/anwendungen/**` nur als Pfad, Größe und SHA-256.
  - Keine Ausführung, keine Quelltextanalyse, kein Inhalt im LLM-Kontext.

### Fehler- und Unknown-Semantik

Harte API-Fehler:

- `invalid_filius_archive`: kein ZIP, kaputtes ZIP, negative/inkonsistente ZIP-Metadaten.
- `missing_filius_configuration`: `projekt/konfiguration.xml` fehlt.
- `filius_configuration_too_large`: ZIP, XML, Dateianzahl, Dateisystemauszüge oder Evidence überschreiten harte Limits.
- `invalid_filius_configuration`: XML ist syntaktisch kaputt, enthält DOCTYPE/DTD/externe Entities, verletzt die erwartete Filius-Grundstruktur oder nutzt ausführungsnahe/gefährliche XMLDecoder-Konstrukte außerhalb der Allowlist.
- `filius_validation_unavailable`: Storage-Bytes können zur frühen Validierung nicht geladen werden.

Keine API-Fehler:

- unbekannte, passive Filius-Klassen oder Properties innerhalb einer ansonsten validen Projektdatei.
- fachlich noch nicht ausgewertete, aber nicht gefährliche XML-Teile.
- abgeschnittene, zu lange Simulationsinhalte.

Diese Fälle erscheinen stattdessen im Evidence-Abschnitt `Parser Notes` mit Zählern, Klassennamen und Truncation-Hinweisen. Roh-XML wird dort nicht ausgegeben.

## Evidence-Format `filius.evidence.v1`

Die Evidence ist ein kompakter Topologiebericht. Kompakt heißt: fachlich relevante Netzwerkdaten bleiben enthalten; Java-/Swing-/XML-Rauschen wird entfernt.

Der Output ist deterministisch: gleicher Input erzeugt byte-stabilen Markdown-Output. Listen werden stabil sortiert, synthetische IDs werden aus der Reihenfolge der normalisierten Daten vergeben, und alle nutzergesteuerten Texte werden Markdown-sicher escaped.

### Stabile Abschnittsreihenfolge

`filius.evidence.v1` wird immer in dieser Reihenfolge gerendert:

1. `# filius.evidence.v1`
2. `## Project`
3. `## Parser Notes`
4. `## Nodes`
5. `## Links`
6. `## Routing`
7. `## Firewall`
8. `## DNS`
9. `## Web`
10. `## Email`
11. `## Documentation`
12. `## Custom Applications`

Leere Abschnitte bleiben sichtbar mit `none`, damit Kriterien nicht zwischen „nicht vorhanden“ und „nicht extrahiert“ raten müssen.

### Sortierung und IDs

- Knoten: `n1`, `n2`, ... nach stabiler GUI-/XML-Reihenfolge; bei Gleichstand nach normalisiertem Namen und Klasse.
- Interfaces: `n1-if1`, `n1-if2`, ... nach XML-Reihenfolge, danach IP/MAC.
- Links: `e1`, `e2`, ... nach normalisierten Endpunkt-IDs.
- Anwendungen, Routen, Firewall-Regeln, DNS-/Web-/E-Mail-Einträge: stabil nach fachlichen Schlüsselwerten, dann Originalreihenfolge.

### Limits und Truncation

Die Grenzwerte werden als Konstanten im Filius-Modul definiert und in `Parser Notes` ausgegeben.

### Limit-Stichprobe

Die Defaults orientieren sich an vier realen inf-schule-Dateien:

| Datei | `.fls` Bytes | ZIP-Einträge | unkomprimiert gesamt | `konfiguration.xml` |
| --- | ---: | ---: | ---: | ---: |
| `E-Mail_Netzwerk.fls` | 3.476 | 2 | 37.631 | 37.631 |
| `filius_mehrere_netze.fls` | 3.758 | 2 | 49.106 | 49.106 |
| `filius_ClientServer.fls` | 4.589 | 2 | 75.700 | 75.700 |
| `filius_webserver.fls` | 5.572 | 2 | 90.362 | 90.362 |

Die größten beobachteten Mengen in dieser Stichprobe sind: 16 Knoten, 17 Kabel, 10 installierte Anwendungen, 6 Doku-Elemente, 3 E-Mail-Konten, ca. 410 `<object>`-Elemente und ca. 919 `<void>`-Elemente. Die Limits liegen bewusst deutlich darüber, damit umfangreiche Unterrichtsprojekte funktionieren, aber ZIP-Bombs und Prompt-Kontext-Explosionen früh abgefangen werden.

### Konkrete Defaults

- `FILIUS_MAX_INPUT_BYTES = LEARNING_MAX_UPLOAD_BYTES` (aktuell 10 MiB, aus zentraler Learning-Upload-Policy)
- `FILIUS_MAX_ZIP_ENTRIES = 256`
- `FILIUS_MAX_TOTAL_UNCOMPRESSED_BYTES = 50_000_000`
- `FILIUS_MAX_CONFIGURATION_XML_BYTES = 8_000_000`
- `FILIUS_MAX_CUSTOM_APP_BYTES = 2_000_000` je Datei unter `projekt/anwendungen/**`
- `FILIUS_MAX_NODES = 256`
- `FILIUS_MAX_LINKS = 512`
- `FILIUS_MAX_INTERFACES = 512`
- `FILIUS_MAX_APPLICATIONS = 512`
- `FILIUS_MAX_ROUTES = 512`
- `FILIUS_MAX_FIREWALL_RULES = 512`
- `FILIUS_MAX_FILESYSTEM_FILES = 256`
- `FILIUS_MAX_EMAIL_ACCOUNTS = 128`
- `FILIUS_MAX_EMAIL_MESSAGES = 512`
- `FILIUS_MAX_DOCUMENTATION_ITEMS = 256`
- `FILIUS_MAX_TEXT_FIELD_CHARS = 2_000`
- `FILIUS_MAX_FILE_EXTRACT_CHARS = 4_000`
- `FILIUS_MAX_EMAIL_BODY_CHARS = 4_000`
- `FILIUS_MAX_EVIDENCE_CHARS = 65_536`

Wenn ein fachlicher Inhalt gekürzt wird, bleibt der Datensatz erhalten und enthält einen klaren Hinweis wie `[truncated: original_chars=12345 shown_chars=4000]`.

### Enthalten

- Projekt:
  - Filius-Version aus dem Versionsstring
  - Schema `filius.evidence.v1`
  - Datei-/Parser-Limits und Truncation-Hinweise, falls relevant
- Knoten:
  - stabile synthetische IDs (`n1`, `n2`, ...)
  - Java-Klasse und normalisierter Gerätetyp (`computer`, `notebook`, `switch`, `router`, `modem`, `unknown`)
  - sichtbarer Name bzw. Label, soweit vorhanden
  - Interfaces mit IP, Subnetzmaske, Gateway, DNS, MAC, Wireless-Flag
  - DHCP-Konfiguration, RIP-Flag, IP-Forwarding-Indizien soweit persistent vorhanden
- Links:
  - stabile synthetische IDs (`e1`, ...)
  - Start-/Zielknoten aus `GUIKabelItem.kabelpanel.ziel1/ziel2`
  - Wireless-Flag, soweit persistent vorhanden
- Anwendungen:
  - installierte Standard-Anwendungen mit Java-Klasse und Aktivitätsstatus, z. B. Webserver, DNS-Server, Terminal, Browser, E-Mail, Firewall
- Routing:
  - manuelle Einträge aus `Weiterleitungstabelle.manuelleTabelle`
  - abgeleitete Netze aus Interface-IP/Subnetzmaske
  - abgeleitete Default-Gateway-Sicht, aber klar als abgeleitet markiert
- Firewall:
  - installierte Firewall/App-Konfiguration
  - `activated`, `defaultPolicy`, `dropICMP`, `filterSYNSegmentsOnly`, `filterUdp`
  - Regeln mit `srcIP`, `srcMask`, `destIP`, `destMask`, `protocol`, `port`, `action`
  - Protokoll-Codes normalisiert: `-1=*`, `1=ICMP`, `6=TCP`, `17=UDP`; Action `0=DROP`, `1=ACCEPT`
- Sichere Dateisystem-Auszüge:
  - `/dns/hosts`
  - `/webserver/*`
  - `/www.conf/vhosts`
  - jeweils bounded, textuell, mit Pfad und gekürztem Inhalt
- E-Mail:
  - Mailserver-/Client-Apps, Domain, Server/Ports
  - Kontennamen und simulierte E-Mail-Adressen
  - Betreff und bounded Mailkörper, wenn in der Filius-Datei persistent vorhanden
  - niemals Passwörter
  - Nachrichtenanzahl und Truncation-Hinweise
- Dokumentation:
  - `GUIDocuItem` mit Typ, Text, Position und Größe
- Eigene Anwendungen:
  - Dateien unter `projekt/anwendungen/**` nur als Pfad, Größe und SHA-256
  - keine Ausführung, keine Quelltextanalyse, kein Inhalt im LLM-Kontext

### Bewusst nicht enthalten

- Swing-/GUI-Rohdetails ohne fachliche Bedeutung: Icon-Pfade, Look-and-feel-Klassen, MouseListener, Font-Objekte außer dokumentationsnahen Basisdaten.
- Java-Objekt-IDs als fachliche IDs. GUSTAV erzeugt eigene stabile IDs.
- Thread-Namen und Prioritäten.
- Vollständige Roh-XML.
- Passwörter.
- Vollständige unbounded Mailboxen oder Dateiinhalte.

## Security / Hardening

- ZIP-Bomb-Schutz:
  - maximale Dateianzahl
  - maximale komprimierte und unkomprimierte Gesamtgröße
  - maximales `konfiguration.xml`
  - keine Extraktion auf Dateisystem
- Pfadschutz:
  - nur `projekt/konfiguration.xml` und optional `projekt/anwendungen/**`
  - keine absoluten Pfade, keine `..`-Segmente
- XML-Schutz:
  - DTD/DOCTYPE/externe Entities ablehnen
  - keine Java-Deserialisierung
  - nur erlaubte Klassen/Properties auswerten
- Prompt-Injection-Hardening:
  - Nutzertexte JSON-/Markdown-sicher escapen
  - harte Längenlimits pro Feld und Gesamt-Evidence
  - Truncation explizit markieren
- Datenschutz / Simulationsdaten:
  - keine Passwörter
  - E-Mail-Adressen und Mailkörper aus Filius gelten als Simulationsdaten und dürfen bounded in Evidence erscheinen
  - keine vollständigen Evidence-Reports in Logs
  - keine Netzwerkzugriffe aus Dateiinhalten oder URLs

## Relevante Implementierungsstellen

- OpenAPI: `api/openapi.yml`
- Teaching Task Service: `backend/teaching/services/tasks.py`
- Learning Upload Policy: `backend/storage/learning_policy.py`
- Learning API: `backend/web/routes/learning.py`
- Learning Repo Guards: `backend/learning/repo_db.py`
- Worker Evidence-Branch: `backend/learning/adapters/local_vision.py`
- Evidence Rendering UI: `backend/web/evidence_rendering.py`, `backend/web/main.py`
- Storage/DB Migrationen: `supabase/migrations/`, `supabase/config.toml`
- Neue Module:
  - `backend/storage/filius_validation.py`
  - `backend/filius/evidence_v1.py`
  - `backend/filius/__init__.py`
- Kleine zentrale Format-Policy/Helper:
  - in `backend/storage/learning_policy.py`
  - nur für Upload-/Submission-Regeln, nicht als Worker-/Parser-Registry

## Dokumentation

Die Umsetzung aktualisiert nicht nur den API-Vertrag, sondern auch die kanonischen Referenzdocs. Filius ändert öffentlich sichtbare Aufgabenformate, Upload-MIME-Regeln, Storage-Allowlists und die Learning-AI-Pipeline. Diese Dokumentationsänderungen gehören in denselben PR wie die Implementierung.

### Pflichtänderungen

- `docs/references/learning.md`:
  - Learning Upload-Intent und Submission-Regeln um `Task.kind=filius` und `application/x.filius.fls` ergänzen.
  - Scratch, Calliope und Filius als upload-only Formate mit deterministischer Evidence statt OCR beschreiben.
  - Filius-Fehlercodes dokumentieren: `invalid_filius_archive`, `missing_filius_configuration`, `invalid_filius_configuration`, `filius_configuration_too_large`, `filius_validation_unavailable`.
- `docs/references/learning_ai.md`:
  - Worker-/Vision-Pipeline ergänzen: Scratch, Calliope und Filius erzeugen deterministische Evidence und laufen danach durch die normale Text-Feedback-Pipeline.
  - Klarstellen: Filius nutzt keinen OCR-/Vision-Aufruf, keine Java-Deserialisierung und loggt keine Roh-Evidence.
- `docs/references/storage_and_gateway.md`:
  - `submissions`-Bucket-Allowlist um `application/x.filius.fls` ergänzen.
  - Learning-Upload-MIME-Liste aktualisieren: PDF, SB3, HEX, FLS plus Bilder für native/visual Pfade.
  - Hinweis auf bounded serverseitige Validierung von `.fls`-Archiven aufnehmen.
- `docs/references/teaching.md`:
  - Task-Dokumentation aktualisieren: `Task.kind = native|h5p|visual|scratch|calliope|filius`.
  - `FiliusTaskConfig` als leeres upload-only Config-Objekt dokumentieren.
  - bestehende veraltete Aussage `kind` sei aktuell stets `native` entfernen.
- `docs/database_schema.md`:
  - `public.unit_tasks.kind`-Check um vollständige Kind-Liste inklusive `filius` dokumentieren.
  - `public.learning_submissions` file-MIME-Check inklusive `.fls` dokumentieren.
  - festhalten: keine Filius-spezifischen Spalten.
- `docs/ARCHITECTURE.md`:
  - Teaching-Aufgabenabschnitt aktualisieren: Task-Kinds inklusive Scratch/Calliope/Filius.
  - Learning-AI-Überblick ergänzen: deterministische Evidence-Extractor als Vorstufe zur Feedback-Pipeline.
- `docs/references/LLM-Prompts.md`:
  - ergänzen, dass `student_text_md` bei Scratch/Calliope/Filius ein deterministischer Evidence-Report ist.
  - klarstellen: Das LLM bewertet nur Evidence, nicht Originaldateien.
- `docs/references/teaching_live.md`:
  - Teacher-Latest-Submission-Doku aktualisieren: `text_body`/Textrepräsentation kann bei Filius `filius.evidence.v1` enthalten.
  - Evidence-Rendering für Datei-/Spezialformate erwähnen.
- `docs/glossary.md`:
  - Begriffe ergänzen: `Evidence`, `Abgabeformat/Task.kind`, optional `Filius-Projektdatei`.
  - Begrifflich sauber trennen: `Abgabe` ist der persistierte Submission-Datensatz; `Evidence` ist die deterministische Textrepräsentation einer Datei-Abgabe.
- `docs/references/security_checklist.md`:
  - Untrusted Archive/XML-Regeln ergänzen: bounded ZIP-Lesen, keine Dateisystem-Extraktion, keine Java-Deserialisierung, keine Roh-Evidence in Logs.
- `docs/references/make_targets.md`:
  - Falls `make verify-preflight-db` den `unit_tasks_kind_check` prüft, Hinweis von `inkl. calliope` auf `inkl. filius` aktualisieren.
- `docs/CHANGELOG.md`:
  - Unter `Unreleased` Einträge für API, DB/Storage, AI/Evidence, Docs und Tests ergänzen.
- `README.md`:
  - Kurze Feature-Zeile ergänzen: GUSTAV unterstützt upload-only Aufgabenformate wie Scratch, Calliope und Filius mit deterministischer Evidence-Auswertung.

### Nicht notwendig

- `docs/ROADMAP.md`: bleibt Platzhalter, keine Änderung nötig.
- `.env.example` und `docs/references/config_matrix.md`: nur ändern, falls im Code neue Filius-spezifische ENV-Variablen eingeführt werden. Nach aktuellem Plan werden Limits als Modul-Konstanten umgesetzt, daher keine neue ENV-Doku.
- `docs/tests/storage_strategy.md`: keine Pflichtänderung, da es primär Teaching-Material-Storage beschreibt.

### Acceptance Criteria für Docs

- Keine kanonische Referenzdoc nennt nur `native|h5p|visual`, wenn sie Task-Kinds vollständig aufzählt.
- Keine Learning-/Storage-Referenz listet Upload-MIMEs ohne `application/x.filius.fls`.
- Keine AI-Doku beschreibt Filius als OCR-/Vision-Pfad.
- Keine Doku behauptet, simulierte Filius-Mailkörper würden grundsätzlich ausgeschlossen; sie sind bounded, escaped und ohne Passwörter erlaubt.

## Tests

### Contract Tests

- OpenAPI enthält `FiliusTaskConfig`.
- Alle relevanten `Task.kind`-Enums enthalten `filius`.
- Submission-file-MIME enthält `application/x.filius.fls`.
- Upload-Intent-Beschreibung nennt Filius/FLS.
- 400/503-Beschreibungen nennen Filius-Detailcodes.

### Parser Unit Tests

- gültige `.fls` mit minimalem Knoten/Link-Setup erzeugt Evidence.
- `.fls` mit Webserver-Dateien extrahiert nur erlaubte Webpfade.
- `.fls` mit DNS-Hosts extrahiert DNS-Evidence.
- `.fls` mit manuellen Routen extrahiert manuelle Routen und abgeleitete Netze getrennt.
- `.fls` mit Firewall-Regeln extrahiert Policies und Regeln normalisiert.
- `.fls` mit E-Mail-Konten und simulierten Nachrichten extrahiert Konten, Adressen, Betreff und bounded Mailkörper, aber nie Passwörter.
- `projekt/anwendungen/**` wird nur als Hash/Metadaten sichtbar.
- defektes ZIP, fehlende XML, zu große XML, Pfadtraversal, DTD/DOCTYPE und unbekannte gefährliche XML-Strukturen werden stabil abgelehnt.
- unbekannte passive Filius-Klassen werden als `unknown`/`ignored` in `Parser Notes` markiert und führen nicht zu `400`.

### Evidence Golden-File Tests

- Golden Files sichern byte-stabile `filius.evidence.v1`-Ausgabe für:
  - minimale Topologie
  - Web/DNS/VHosts
  - Routing und abgeleitete Netze
  - Firewall-Regeln
  - E-Mail-Simulationsdaten mit gekürztem Mailkörper
  - Dokumentation und eigene Anwendungen
- Golden Files prüfen Abschnittsreihenfolge, Sortierung, synthetische IDs, Escaping und Truncation-Hinweise.

### API / Integration Tests

- Teaching API erstellt und aktualisiert Filius-Tasks.
- Filius-Task akzeptiert Upload-Intent nur für `application/x.filius.fls`.
- Nicht-Filius-Tasks lehnen Filius-MIME ab.
- Filius-Submission akzeptiert gültige `.fls` und validiert früh.
- Filius-Submission lehnt Text/Bild/PDF/SB3/HEX ab.
- Storage-Policy und Bucket-Provisioning enthalten Filius-MIME.
- Zentrale Format-Policy wird von Upload-Intent, Submission-Finalisierung und Repo-Guard konsistent genutzt:
  - Scratch/Calliope-Verhalten bleibt unverändert.
  - Filius ergänzt die Matrix additiv.
  - Unsupported upload-only MIME-Typen werden bei falschem `Task.kind` abgelehnt.

### Worker / UI Tests

- `local_vision` erzeugt `# filius.evidence.v1` statt OCR/Vision aufzurufen.
- Evidence wird in Schüler- und Lehreransicht mit `filius-evidence`-Wrapper gerendert.
- Roh-XML und Passwörter erscheinen nicht in gerendertem HTML.
- Simulierte Mailkörper erscheinen nur escaped, bounded und mit Truncation-Hinweis, falls gekürzt.

## Quellen / Recherche

- Bestehende GUSTAV-Implementierung:
  - `docs/plan/2026-02-18-scratch-sb3-pipeline.md`
  - `docs/plan/2026-02-23-calliope-makecode-hex-upload-pipeline.md`
  - `backend/storage/sb3_validation.py`
  - `backend/storage/makecode_hex_validation.py`
  - `backend/scratch/sb3_evidence_v2.py`
  - `backend/makecode/hex_evidence_v1.py`
- Filius / inf-schule:
  - `https://inf-schule.de/rechnernetze/filius`
  - `https://inf-schule.de/rechnernetze/filius/internet/erkundung_www`
  - `https://inf-schule.de/rechnernetze/filius/vernetzungrechnernetze/erkundung_mehrerenetze`
  - `https://inf-schule.de/rechnernetze/filius/clientserver/erkundung_clientserver`
  - `https://inf-schule.de/rechnernetze/anwendung/email/filiusemail`
  - Beispiel `filius_webserver.fls`: ZIP mit `projekt/konfiguration.xml`, XMLDecoder-Struktur, Knoten/Kabel/Doku-Listen.
  - Limit-Stichprobe: `filius_webserver.fls`, `filius_mehrere_netze.fls`, `filius_ClientServer.fls`, `E-Mail_Netzwerk.fls`.
- Filius-Quellen:
  - `SzenarioVerwaltung.java`: Projekt-Speichern/Laden
  - `NetzwerkInterface.java`: IP, Subnetzmaske, Gateway, DNS, MAC, Wireless
  - `InternetKnotenBetriebssystem.java`: Dateisystem, installierte Anwendungen, Weiterleitungstabelle, DHCP/RIP
  - `Weiterleitungstabelle.java`: manuelle vs. automatisch abgeleitete Routen
  - `Firewall.java` und `FirewallRule.java`: Firewall-Policies und Regeln
  - `EmailKonto.java` und `EmailServer.java`: E-Mail-Konten enthalten Passwörter und müssen redigiert werden
