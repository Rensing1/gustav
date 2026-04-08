# Lernraum: freie Modulsektionen auf dem Seitenhintergrund

## Ziel

Der modulare Lernraum soll nicht mehr wie eine flache Sammlung einzelner Karten
oder eine große sichtbare Surface wirken. Stattdessen liegt die rechte
Inhaltsseite frei auf dem Seitenhintergrund. Jedes geöffnete Modul folgt
derselben Struktur:

1. Modulkopf
2. Materialien
3. Aufgaben

Materialien bleiben standardmäßig offen und einzeln zuklappbar. Aufgaben sind
klar von den Materialien getrennt und erscheinen als kompakte Arbeitszeilen.

## Entscheidungen

- Mehrere Module dürfen gleichzeitig geöffnet sein.
- Pro Pane bleibt genau eine aktive Aufgabe im Bearbeitungsmodus offen.
- Die rechte Spalte bekommt keine sichtbare Card-Hülle, auch nicht im Split-View.
- Auch das Inhaltsverzeichnis links verliert Border, Hintergrund und Schatten.
- Aufgaben in modularen Einheiten starten als kompakte Arbeits-Row.
- Die geschlossene Row zeigt Titel, Status und CTA, aber keinen sichtbaren Vorschautext.
- `Meine Abgabe` und die Inline-Bearbeitung bleiben unter der aktiven Aufgabe.
- Materialien haben nur eine Titelzeile mit Auf-/Zu-Icon und starten offen.
- Lineare Einheiten bleiben in dieser Iteration unverändert.

## Umsetzung

- `LearningUnitContentWorkspace` rendert modulare Gruppen als Modulblöcke mit
  getrennten Bereichen für Materialien und Aufgaben.
- `LearningTaskCard` rendert für modulare Einheiten eine kompakte Aufgabenzeile
  und klappt Review/Bearbeitung accordion-artig direkt darunter auf.
- `LearningMaterialCard` bleibt offen lesbar, wirkt aber wie Inhalt auf dem
  Seitenhintergrund statt wie eine innere Card.
- `WorkspaceOutline` bleibt funktional gleich, aber die TOC-Spalte wird
  stilistisch vollständig entrahmt und nur noch über Abstand vom Inhalt getrennt.
- Die Workspace-Surface wird visuell neutralisiert; Module trennen sich nur
  über Abstand und Linien.
- Die bestehende Lernlogik für Entwurf, Review, Upload und Finalize bleibt
  fachlich unverändert.

## Verifikation

- Vitest für modulare Workspace-Komposition
- Vitest für kompakte modulare Aufgaben-Row
- `cd frontend && npm run check`
- `docker compose up -d --build frontend`
