# Plan: Tabs für Text‑/Datei‑/Auswertung‑Ansicht in der Live‑Detailansicht

**Datum:** 2025‑12‑03  

## Ausgangssituation und Problem

In der Lehrkraft‑Ansicht **„Unterricht › Live“** zeigt die Matrix (Schüler × Aufgaben) per Klick auf eine Zelle ein Detail‑Panel unterhalb der Tabelle.  
Dieses Panel wird von der Route

- **UI (SSR):** `GET /teaching/courses/{course_id}/units/{unit_id}/live/detail?student_sub=…&task_id=…` → ruft intern  
- **API (JSON, Teaching):** `GET /api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub}/submissions/latest`

versorgt.

* **Text‑Einreichungen:** `TeachingLatestSubmission.text_body` wird angezeigt.  
* **Datei‑/Bild‑Einreichungen:** Der extrahierte Text wird in `public.learning_submissions.text_body` gespeichert, **nicht** aber in der Teaching‑Detail‑API (`kind != "text"`). Das SSR‑Fragment rendert ausschließlich `data["text_body"]`.  

Resultat: Lehrkräfte sehen bei Datei‑Einreichungen keinen Text.

Das OpenAPI‑Schema `TeachingLatestSubmission` enthält bereits:

| Feld | Beschreibung |
|------|--------------|
| `kind` | `text \| image \| pdf \| file` |
| `text_body` | optional (ggf. gekürzt) |
| `files[]` | Liste mit `mime`, `size`, `url` (signierte URL) |

Aus UX‑Sicht sollen Lehrkräfte zwischen **„extrahierter Text“**, **„Originaldatei“** und (neu) **„Auswertung/Rückmeldung“** wechseln können.

## User Story

> **Als Lehrkraft** möchte ich in der Live‑Detailansicht einer Einreichung zwischen einer Textansicht (extrahierter Text) und der Originaldatei umschalten können, damit ich bei Bedarf sowohl den automatisch extrahierten Text als auch die ursprüngliche Darstellung (z. B. handschriftliche Notizen, Diagramme, Mindmaps) sehen kann.

## Rahmenbedingungen aus UI‑UX‑Leitfaden

* **Konsistenz:** Tabs müssen ins bestehende Card‑Layout passen (Typografie, Abstände, Buttons).  
* **Lesbarkeit:** Text fließt innerhalb fester Max‑Breite, keine horizontale Scroll‑Leiste.  
* **Barrierefreiheit:** ARIA‑Rollen (`tablist`, `tab`, `tabpanel`) oder semantisch klare Buttons mit eindeutiger Zustandsanzeige.  
* **Reduktion visueller Komplexität:** Standard‑View = Text; Originaldatei nur auf Wunsch.

## Geplante Lösung (Variante 1: Tabs „Text“ / „Datei“ / „Auswertung“)

### UI‑Konzept (SSR‑Detailpanel)

- **Detailkarte (bestehend)**
  - Titel: `Einreichung von {Name}`
  - Metadaten: `Typ: {kind} · erstellt: {created_at}`
  - Inhalt: bisher nur Text‑Snippet aus `text_body`.

- **Erweiterung: Tab‑Leiste**
  - **Tab „Text“** – extrahierter Text.  
  - **Tab „Datei“** – Bild‑/PDF‑Vorschau oder Download‑Link (PDF inline mit bestehendem Viewer, nicht nur „neuer Tab“).  
  - **Tab „Auswertung“/„Rückmeldung“** – zeigt KI‑Feedback (`feedback_md`) bzw. strukturierte Analyse (`analysis_json` → gerenderte Markdown/Abschnitte).  
  - **Sichtbarkeit**
    - `kind == "text"` → nur „Text“ (+ „Auswertung“, wenn Feedback vorliegt).  
    - `kind ∈ {"image","file","pdf"}` → „Text“ + „Datei“ (+ „Auswertung“, wenn Feedback vorliegt).  
  - **Default:** Tab „Text“ aktiv.

- **Inhaltspanel**
  - `view="text"`  
    - Nutzt `TeachingLatestSubmission.text_body` (Fallback: `analysis_json.text`).  
    - Markdown‑Rendering, feste Max‑Breite, automatischer Zeilenumbruch (`overflow-wrap: anywhere`).  
  - `view="file"`  
    - Nutzt `TeachingLatestSubmission.files[]`.  
    - **Bilder:** `<img>` mit `max-width: 100%`.  
    - **PDF:** eingebetteter PDF‑Viewer wie in der Lerneinheiten-/Material‑Ansicht (gleiches Partial), mit Fallback „In neuem Tab öffnen“.  
    - **Fallback:** „Datei‑Vorschau derzeit nicht verfügbar“.
  - `view="auswertung"`  
    - Zeigt `feedback_md` (Markdown) und ggf. kompaktes Rendering von `analysis_json` (Kriterien‑Tabelle).  
    - Nur sichtbar, wenn Feedback vorliegt (analysis_status=completed, Daten vorhanden).

### Contract‑First: `TeachingLatestSubmission`

- `kind` unverändert.  
- `text_body` wird für **alle** `kind` befüllt, sobald die Vision‑Pipeline `analysis_status="completed"` ist (Best‑Effort‑Auszug).  
- `files[]` enthält mindestens einen Eintrag (`mime`, `size`, `url`).  
- Neu: optionale Felder für `feedback_md` (Markdown) und eine kompakte `analysis`‑Struktur (oder Reuse `analysis_json` als read‑only Ausschnitt) zur Darstellung im „Auswertung“‑Tab.  
- Keine neuen Endpunkte nötig – Tabs arbeiten ausschließlich mit diesem Schema.

### Backend‑Verhalten (Teaching‑Detail‑API)

| Änderung | Beschreibung |
|---------|--------------|
| **Payload‑Erweiterung** | `text_body` wird gesetzt, wenn ein sinnvoller Text existiert, unabhängig von `kind`. |
| **Fallback‑Logik** | Leeres `text_body` → prüfe `analysis_json.text`. |
| **Files‑Array** | Für Datei‑/Bild‑Einreichungen wird `files[]` mit signierten URLs befüllt (Learning‑Storage‑Adapter, Submissions‑Bucket). |
| **Auswertung** | Liefert `feedback_md` und ggf. kompaktes `analysis`‑Snippet für den Auswertungstab. |
| **Sicherheit** | Route bleibt auf Kurs‑Owner beschränkt; URLs sind kurzlebig, `private, no‑store`. |

### UI‑Verhalten (Tabs & Textumbruch)

- **Implementierung:**  
  - CSS/HTML‑Tabs (radio + label) **oder** minimaler JS/HTMX‑Ansatz.  
  - ARIA‑Rollen für Screenreader.  
  - Tastatur‑fokussierbar, visuell hervorgehoben.  

- **Textumbruch:**  
  - `max-width` wie bestehende Cards.  
  - `overflow-wrap: anywhere;` / `word-break: break-word;` → keine horizontale Scroll‑Leiste.  
  - Vertikales Scrollen innerhalb der Card erlaubt bei sehr langem Text.

## Zukunftssicherheit (komplexe Vision‑Aufgaben)

- Zusätzliche Tabs (z. B. „Auswertung“, „Kriterien“) können später ergänzt werden.  
- API kann weitere strukturierte Felder (z. B. `analysis_json`, `feedback_md`) bereitstellen, ohne das Grundmodell zu brechen.  
- Die Live‑Detailansicht bleibt zentraler Umschaltpunkt zwischen Text, Originaldatei und Analyse.

## Offene Fragen / Entscheidungen

1. **PDF‑Vorschau** – Inline‑Viewer wie in Materialien? → Ja, reuse bestehenden Viewer mit Fallback „Neuer Tab“.  
2. **Fallback‑Text** – Bei leerem `text_body` einfach leer lassen.  
3. **Fehlerdarstellung** – Vorerst ignorieren.  
4. **Mehrfach‑Submissions** – Später: Umschalter (Dropdown/Stepper) zwischen Versuchen im Detail‑Panel; API bräuchte History‑Endpoint oder limitierte Liste der letzten N Submissions.

--- 

*Hinweis: Alle Änderungen basieren auf dem bestehenden OpenAPI‑Schema und erfordern keine neuen Endpunkte.*
