# Entwurfbeschriftung und mobile Dialog-Aufgabenstellung

## Ziel und Umsetzung
Schüler unterscheiden geprüfte Entwürfe von endgültigen Abgaben. Die Seitenleiste nutzt den vorhandenen endgültigen Abgabezeitpunkt beziehungsweise Intent; der Leser beschriftet die tatsächlich angezeigte Fassung. Keine API-/Datenänderung. Im mobilen Dialog erscheint die obere Aufgabenstellung nur im Aufgabenbereich; im Materialienbereich übernimmt sie die gemeinsame Seitenleiste.

## Prüffälle vor Umsetzung
- Nur Feedback-Entwurf vorhanden: Navigation „Mein Entwurf“, Leser „Geprüfter Entwurf · Noch nicht abgegeben“.
- Endgültige Abgabe vorhanden, gegebenenfalls neuerer Entwurf: Navigation bleibt „Meine Abgabe“; Leser priorisiert weiterhin die endgültige Abgabe.
- Mobile Dialogansicht Materialien: Aufgabenstellung genau einmal, aktive Aufgabe und frühere Abgabe erreichbar.
- Mobile Dialogansicht Aufgabe: Aufgabenstellung bleibt sichtbar. Desktop bleibt unverändert.

Spätere Testzuordnung: LearnerTaskContext und LearningReferenceDocument Komponentenprüfungen für Entwurf/finale Abgabe; authentifizierte learner-reference-workspace Feature-Spec für mobilen Bereichswechsel. Auf Nutzerwunsch jetzt ausschließlich manuelle Browserprüfung, keine automatisierten Tests.

## Manuelles Ergebnis
Frontend erfolgreich gebaut. Textentwurf auf Desktop: „Mein Entwurf“ in Navigation; geöffneter Leser zeigt „Eigener geprüfter Entwurf“ und „Noch nicht abgegeben“. Rückkehr funktioniert. Dialog bei 390 × 844: Materialienbereich zeigt Aufgabenstellung einmal, aktuelle Aufgabe und finale Abgabe sind sichtbar. Wechsel zur Aufgabe erhält die obere Aufgabenstellung. Vorhandene Dialogabgabe bleibt „Meine Abgabe“. Keine Antworten oder Abgaben verändert, keine automatisierten Tests ausgeführt. Screenshots: /tmp/text-entwurflabel-desktop.png und /tmp/dialog-mobil-aufgabenstellung-korrigiert.png.
