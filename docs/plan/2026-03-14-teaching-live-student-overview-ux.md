# Plan: Teaching Live Student Overview UX-Optimierung

Status: geplant  
Datum: 2026-03-14

## Ziel
Die Lehreransicht fuer einen Schueler im Live-Unterricht soll von einer textlastigen Aufgabenliste zu einer kompakten Uebersicht werden. Lehrkraefte sollen auf einen Blick sehen:

- wie viele Aufgaben offen bzw. abgegeben sind
- welche Leistungen bereits bewertet sind
- wo sie Details zu einer Aufgabe direkt inline oeffnen koennen

## Produktentscheidungen
- Die Seite bleibt in Kursreihenfolge.
- Alle Lerneinheiten bleiben standardmaessig offen.
- Pro Aufgabe wird nur eine kompakte Zeile gezeigt; die volle Aufgabenstellung ist initial verborgen.
- Details werden inline pro Aufgabe geoeffnet, nicht mehr gesammelt am Seitenende.
- V1 nutzt den bestehenden Overview-Contract; es gibt keine OpenAPI-Aenderung.
- Die Detail-Route zeigt bei fehlender Einreichung trotzdem die Aufgabenstellung plus klaren Empty State.

## Umsetzung
1. SSR-Tests auf den gewuenschten Zielzustand umstellen:
   - Kennzahlenblock oben
   - kompakte Aufgabenzeilen
   - keine globale Detailflaeche am Seitenende
   - Inline-HTMX-Ziel pro Aufgabe
   - Aufgabenstellung auch im Empty State der Detailansicht
2. SSR-Rendering der Schueleransicht umbauen:
   - Summary-Block mit Aufgaben gesamt, mit Abgabe, offen, optionale Durchschnittsbewertung
   - kompakte `<details>`-Aufgabenzeilen mit Status-/Score-Chips
   - Kurztitel aus `instruction_md` als Plain-Text-Auszug
3. Detail-Partial fuer den Empty State erweitern:
   - Aufgabenstellung weiterhin sichtbar
   - darunter `Noch keine Einreichung vorhanden.`
4. CSS gezielt fuer die neue kompakte Lehreransicht ergaenzen.

## Tests
- `backend/tests/test_teaching_live_student_overview_ssr.py`
- `backend/tests/test_teaching_live_detail_ssr.py`
