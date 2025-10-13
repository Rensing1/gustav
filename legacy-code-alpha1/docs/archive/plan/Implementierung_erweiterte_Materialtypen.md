# Implementierungsplan: Erweiterte Materialtypen

**Status:** Phase 1 (Datei-Uploads) implementiert. Phase 2 (HTML-Applets) implementiert.
**Datum:** 2025-08-11

## 1. Übergeordnetes Ziel

Die Möglichkeiten für Lehrer zur Erstellung von Lernmaterialien erweitern, indem Datei-Uploads und interaktive HTML-Applets als neue Materialtypen hinzugefügt werden.

---

## 2. Grundsätzliches Vorgehen & Sicherheitsbetrachtungen

Aufgrund der unterschiedlichen Sicherheitsanforderungen werden die Features in zwei Phasen implementiert:
1.  **Phase 1: Datei-Uploads.** Sicherer Umgang mit Dateien und Zugriffskontrolle.
2.  **Phase 2: HTML/JS-Applets.** Isolierung von potenziell unsicherem Code.

Dieses Dokument hält die technischen und sicherheitsrelevanten Entscheidungen für beide Phasen fest.

---

## 3. Phase 1: Implementierung des Datei-Uploads (Bilder, PDFs, etc.)

### 3.1. Backend & Datenstruktur

- **Grundlage:** Genutzt wird die existierende `JSONB`-Spalte `materials` in der Tabelle `unit_section`.
- **Ablauf eines Uploads:**
  1.  Die App (Python-Backend) empfängt die Datei vom Frontend und **validiert die Dateigröße**.
  2.  Ein eindeutiger Storage-Pfad wird generiert. **Konvention:** `course_{course_id}/section_{section_id}/{uuid}_{original_filename}`.
  3.  Die Datei wird via `supabase_client.storage.from_('section_materials').upload(...)` in den **privaten** Storage-Bucket `section_materials` hochgeladen.
  4.  Nach erfolgreichem Upload wird das `materials`-JSON-Array in der `unit_section`-Tabelle aktualisiert:
      ```json
      {
        "type": "file",
        "path": "course_xyz/section_abc/some_uuid_filename.jpg",
        "filename": "original_filename.jpg",
        "mime_type": "image/jpeg"
      }
      ```

### 3.2. Frontend (UI)

- **Ort der Änderung:** `app/components/detail_editor.py`.
- **Editor für Lehrer:**
  - Neue Material-Option "Datei hochladen".
  - `st.file_uploader` mit einem **Limit für die Dateigröße** (z.B. 20 MB).
- **Anzeige für Schüler:**
  - Wenn `type: "file"`:
    - Bei `mime_type` `image/*`: Anzeige via `st.image` (mit signierter URL).
    - Sonst: Anzeige eines `st.download_button` (mit signierter URL).

### 3.3. Sicherheitsmaßnahmen (RLS & Ressourcen)

- **Ressourcen-Kontrolle:** Die Dateigröße wird im Frontend (`st.file_uploader`) und serverseitig vor dem Upload zu Supabase geprüft, um Missbrauch vorzubeugen.
- **Row-Level-Security (RLS) für Storage `section_materials`:** Dies ist **zwingend erforderlich**.
  - **`SELECT` (Lesen):** Ein Nutzer darf eine Datei lesen, wenn er im Kurs der Lerneinheit eingeschrieben ist. Die Policy extrahiert die `course_id` aus dem Dateipfad.
  - **`INSERT` (Schreiben):** Ein Nutzer darf eine Datei hochladen, wenn er die Rolle `teacher` hat und Lehrer im entsprechenden Kurs ist.
  - **`UPDATE`/`DELETE`:** Analog zur `INSERT`-Policy.
- **Risiko "Malware":** Das Risiko, dass schädliche Dateien (Viren etc.) hochgeladen und von anderen Nutzern heruntergeladen werden, wird für die erste Version bewusst in Kauf genommen. Ein serverseitiger Virenscan ist aktuell zu komplex.

---

## 4. Phase 2: Implementierung der HTML/JS-Applets

### 4.1. Backend & Datenstruktur

- **Grundlage:** `materials`-Spalte in `unit_section`.
- **Struktur:**
    ```json
    {
      "type": "html_applet",
      "content": "<html>...user-provided code...</html>",
      "height": 600
    }
    ```

### 4.2. Frontend (UI)

- **Ort der Änderung:** `app/components/detail_editor.py`.
- **Editor für Lehrer:**
  - Neue Material-Option "HTML-Applet".
  - `st.text_area` für den Code, `st.number_input` für die Höhe.
- **Anzeige für Schüler:**
  - Der `content` wird in einem **sandboxed iFrame** gerendert.
  - **Befehl:** `st.components.v1.iframe(material['content'], height=material['height'], sandbox="allow-scripts")`

### 4.3. Sicherheitsmaßnahmen (iFrame Sandbox)

- **iFrame-Härtung:** Das `sandbox`-Attribut ist die primäre Verteidigungslinie. Die Konfiguration `allow-scripts` ist für die Funktionalität notwendig. Wichtig ist, **keine weiteren Berechtigungen** wie `allow-same-origin`, `allow-top-navigation` oder `allow-popups` zu vergeben, um die Isolation so stark wie möglich zu machen.
- **Visuelle Kennzeichnung:** Der iFrame-Inhalt sollte für Schüler klar als interaktiver Block erkennbar sein, der von einer Lehrkraft erstellt wurde.
- **Akzeptiertes Restrisiko:** Trotz Sandbox verbleibt ein Restrisiko, dass ein Skript versucht, Nutzer via Phishing anzugreifen oder Daten an externe Server zu senden. Dieses Risiko wird bewusst akzeptiert, um die Funktionalität zu ermöglichen.
- **Alternative (verworfen für v1):** Die Nutzung kuratierter, geprüfter Applet-Typen (z.B. H5P) wäre sicherer, aber deutlich unflexibler und aufwändiger in der Implementierung.

---

## 5. Nächste Schritte

1.  **Phase 1:** Umsetzung der Datei-Uploads inkl. der RLS-Policies und Tests.
2.  **Phase 2:** Nach erfolgreichem Abschluss von Phase 1, Umsetzung der HTML-Applets mit gehärtetem iFrame und Sicherheitstests.
