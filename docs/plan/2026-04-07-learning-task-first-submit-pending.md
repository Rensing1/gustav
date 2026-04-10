# Lernaufgabe: sichtbarer Pending-Zustand beim Erstversuch

Status: abgeschlossen

## Ziel

Beim ersten Klick auf `Rückmeldung einholen` oder `Endgültig abgeben` soll die Aufgabenkarte sofort sichtbar reagieren.

Der aktuelle No-op-Eindruck entsteht, weil der Status bisher nur im Review-Bereich `Meine Abgabe` sichtbar wird, dieser beim Erstversuch aber noch nicht existiert.

## Entscheidungen

- Der Wartehinweis beim Erstversuch erscheint lokal im Editor.
- `Rückmeldung einholen` lässt den Editor offen und gesperrt.
- `Endgültig abgeben` schließt den Editor sofort.
- `Meine Abgabe` wird nicht künstlich vorab geöffnet, sondern erst mit echter Submission-Historie verwendet.

## Umsetzung

- `LearningTaskCard` erhält einen eigenen Pending-Block für den Erstversuch.
- Dieser Pending-Block ist unabhängig vom Review-Panel sichtbar.
- Bei laufendem `feedback` bleibt der Editor offen und zeigt dort den Status.
- Bei laufendem `submit` zeigt die Karte außerhalb des Editors einen lokalen Status, obwohl der Editor geschlossen ist.

## Tests

- `LearningTaskCard.test.ts`
  - Erstversuch + Feedback: Pending-Hinweis im offenen Editor sichtbar
  - Erstversuch + Submit: Editor geschlossen, lokaler Pending-Hinweis weiterhin sichtbar
