# Plan: Upload-Submit blockiert durch HTML5 `required`

Kontext: Nach der Umstellung auf den Upload-Flow (Upload-Intent → Proxy-PUT → SSR‑Submit) meldeten Nutzer:
„Datei auswählen“ zeigt oben rechts einen Erfolgshinweis, aber beim Klick auf „Abgeben“ passiert nichts.

Hypothese: Der Browser blockiert den Formular‑Submit wegen eines versteckten Pflichtfeldes.

Beobachtungen (Logs):
- `POST /api/learning/.../upload-intents` → 200 OK
- `PUT /api/learning/internal/upload-proxy?...` → 200 OK
- Anschließend kein `POST /learning/.../submit` sichtbar → Client‑seitige Blockade wahrscheinlich.

Ursache: In der SSR‑Form ist das Textfeld `<textarea name="text_body" required>` immer als `required` markiert.
Wechselt der Nutzer auf „Upload“, wird das Textfeld per CSS/JS versteckt, bleibt aber `required`. Browser verhindern dann den Submit komplett (kein Netz‑Request), was für den Nutzer wie „nichts passiert“ wirkt.

TDD (Red → Green):
1) Neuer Test `test_ui_text_field_is_not_required_to_allow_upload_mode` in `backend/tests/test_learning_ui_student_submissions.py`, der sicherstellt,
   dass das Textfeld im SSR‑Markup NICHT als `required` markiert ist.
2) Implementierung: `required` aus dem SSR‑Markup in `backend/web/main.py` entfernen; Server‑Validierung für Text bleibt bestehen (`_validate_submission_payload`).

Akzeptanzkriterien:
- Upload‑Flow: Nach Auswahl einer Datei und Erfolg beim Intent/Upload löst „Abgeben“ einen `POST /learning/.../submit` aus (PRG → Erfolg).
- Text‑Flow: Leere Textabgabe wird serverseitig als `invalid_input` abgelehnt; der Browser muss dafür nicht mehr clientseitig blockieren.

Weiteres (optional):
- In `learning_upload.js` bei Fehlern im Submit‑Intercept eine Nutzer‑Meldung anzeigen (statt still zu verhindern).
- JS kann zusätzlich `required` dynamisch toggeln (defense‑in‑depth), ist nach dieser Änderung aber nicht zwingend.

