Title: Learning Markdown Editor: Entwürfe gehen bei Auth-Recovery, iPad-App-Wechsel oder finaler Abgabe verloren

Status: Open

Problem:
- Schüler:innen berichten sporadisch, dass im Markdowneditor eingegebene Lösungen bei der Abgabe oder beim Wechsel aus dem Browser heraus verschwinden.
- Besonders kritisch ist der iPad-Unterrichtsfall: Browser bleibt offen, Lernende wechseln kurz in eine andere App oder senden nach längerer Bearbeitung ab, danach ist der Editor leer oder der Stand entspricht nicht der zuletzt getippten Lösung.
- Das Ticket enthält bewusst keine Namen, E-Mail-Adressen, User-IDs, IPs, Session-IDs oder Lösungstexte.

Anonymisierte Prod-Beobachtung (2026-06-05):
- In einem repräsentativen iPad-Fall gab es um 06:10:49 UTC einen Lernseiten-POST, direkt danach Auth-Continuation, Session-Sync und einen Reload zurück auf dieselbe Lernseite.
- Für diesen Zeitpunkt wurde keine neue Learning-Submission persistiert.
- Wenige Minuten später wurden Feedback- und finale Text-Submissions erfolgreich gespeichert; die Textlängen der Feedback- und Final-Version waren identisch.
- Die Datenlage spricht deshalb nicht für einen allgemeinen DB- oder Worker-Persistenzfehler, sondern für verlorenen Frontend-State während Auth-Recovery oder Page-Remount.

Technischer Kontext:
- Der aktuelle Inline-Editorpfad in `frontend/src/lib/components/learning-unit/LearningTaskCard.svelte` hält `draftText` nur im Svelte-State. Es gibt dort keine tab-scoped Draft-Persistenz und keinen Restore nach Remount oder Reload.
- `frontend/src/lib/components/learning-unit/MarkdownWysiwygEditor.svelte` synchronisiert den Toast-UI-Inhalt nur über das `change`-Event in den Hidden-Input `text_body`. Ein expliziter Flush vor `submit`, `pagehide`, `visibilitychange` oder Blur fehlt.
- Die alte SSR/HTMX-Strecke hatte Draft-Sicherung in `backend/web/static/js/gustav.js`: Speicherung in `sessionStorage`, Restore beim Laden und ein zusätzlicher Save direkt vor Submit. Diese Schutzwirkung fehlt im aktuellen Svelte-Inline-Pfad.
- Die finale Abgabe in `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.server.ts` sendet nicht den aktuellen Editorinhalt, sondern finalisiert den letzten abgeschlossenen Feedback-Draft. Änderungen nach dem letzten Feedback können dadurch stillschweigend unberücksichtigt bleiben.
- Auth-Recovery ist ein Trigger: `frontend/src/lib/server/api.ts` kann bei Backend-`401` refreshen oder nach `/auth/continue?redirect=...` weiterleiten. Wenn dadurch die Lernseite remountet und der Editorstand nur im Speicher lag, geht der Entwurf verloren.

Wahrscheinliche Ursachen:
1. Volatiler Editor-State im aktuellen Inline-Task-Pfad ohne `sessionStorage`/`localStorage`-Backup.
2. Fehlender Editor-Flush vor Submit und Browser-Lifecycle-Events, besonders relevant auf iOS.
3. Final-Submit-Semantik finalisiert den letzten Feedback-Draft statt zwingend den aktuell sichtbaren Editorinhalt.
4. Häufige Auth-Continuations und abgelaufene Access-Token erhöhen die Wahrscheinlichkeit, dass genau während der Bearbeitung ein Remount passiert.

Impact:
- Lernende müssen längere Antworten erneut tippen.
- Lehrkräfte können schwer unterscheiden, ob eine Abgabe nicht gespeichert wurde, ob nur der UI-Entwurf verloren ging oder ob final eine ältere Feedback-Version abgegeben wurde.
- Das Symptom untergräbt Vertrauen in die Lernplattform, auch wenn Backend-Persistenz und Worker grundsätzlich funktionieren.

Proposed Fix:
1. Draft-Persistenz im Inline-Editorpfad ergänzen.
   - Tab-scoped bevorzugen, z. B. `sessionStorage`, um stale Drafts auf geteilten Geräten zu vermeiden.
   - Key mindestens aus `courseId`, `task.id` und Antwortmodus bilden.
   - Bei Eingabe speichern, beim Mount/Taskwechsel wiederherstellen und erst nach erfolgreichem Feedback- oder Final-Submit löschen.
2. Editor-Flush robust machen.
   - Toast-UI-Markdown vor Form-Submit und bei `pagehide`, `visibilitychange` und Blur in `currentValue`/Hidden-Input synchronisieren.
   - Parent-Callback mit dem letzten Editorwert auslösen, damit Svelte-State und FormData übereinstimmen.
3. Final-Submit gegen ungespeicherte Änderungen absichern.
   - Entweder aktuelle Editoränderungen vor finaler Abgabe speichern und finalisieren.
   - Oder den finalen Button sperren bzw. deutlich machen, wenn der sichtbare Editorinhalt vom zuletzt abgeschlossenen Feedback-Draft abweicht.
4. Auth-Recovery-Flow als Regression abdecken.
   - Vor enhanced form submit immer Draft persistieren.
   - Nach `/auth/continue`-Rückkehr muss der Editor den Draft automatisch wieder anzeigen.

Akzeptanzkriterien:
- Eine getippte Textlösung bleibt nach Auth-Continuation, iPad-App-Wechsel, Browser-Reload oder Svelte-Remount erhalten.
- Ein Submit verwendet den zuletzt sichtbaren Editorinhalt oder verhindert die Abgabe mit klarer UI, wenn dieser Stand noch nicht gespeichert werden kann.
- Final-Submit kann keine neu getippten Änderungen stillschweigend ignorieren.
- Tests decken Remount, Auth-Recovery, Submit-Flush und Draft-Cleanup ab.
- Ticket, Logs und Tests bleiben PII-frei.

Testideen:
- Unit-Test für `LearningTaskCard`: Draft wird bei Eingabe gespeichert, nach Remount wiederhergestellt und nach erfolgreichem Submit gelöscht.
- Unit-Test für `MarkdownWysiwygEditor`: Hidden-Input und Parent-State werden vor Submit und bei Page-Lifecycle-Events synchronisiert.
- E2E- oder Component-Test: Text tippen, Auth-Continuation/Reload simulieren, zurückkehren, Text ist weiterhin im Editor.
- Regression für Final-Submit: sichtbarer Editorinhalt und finalisierte Submission dürfen nicht auseinanderlaufen.

Related:
- `docs/tickets/learning-task-submit-401-session-expired-textverlust-2026-01-08.md`
- `docs/tickets/session-expired-on-submit-students-logout-2026-01-13.md`
- `docs/tickets/auth-session-continuity-classroom-regression-2026-05-11.md`
