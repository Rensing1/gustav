# Verlässliche Rücknavigation im Lernraum

## User Story

Als lernende Person möchte ich, dass jeder sichtbare Rückweg genau zu dem bezeichneten Ziel führt, damit ich nach einer Aufgabe, einem Direktaufruf oder einem Neuladen zuverlässig im richtigen Modul beziehungsweise Lernpfad lande.

## Produktentscheidungen

- Sichtbare Rückwege haben ein fachliches Ziel: `module`, `learningPath` oder bei linearen Lerneinheiten `contents`.
- Beschriftung und Navigation werden gemeinsam aus diesem Ziel abgeleitet.
- Nach einer endgültig abgeschlossenen modularen Aufgabe führt der Rückweg zum Modul, solange dort eine andere, noch nicht endgültig abgegebene Aufgabe liegt. Andernfalls führt er zum Lernpfad.
- Eine Aufgabe mit formativer Rückmeldung, aber ohne endgültige Abgabe, gilt weiterhin als offen.
- Kann der Abschlussstatus einer anderen Aufgabe nicht sicher bestimmt werden, bleibt der Rückweg vorsichtshalber beim Modul.
- Sichtbare Rückwege verwenden den Browser-Verlauf nur, wenn der aktuelle, von GUSTAV angelegte Verlaufseintrag genau das erwartete Elternziel ausweist. Andernfalls wird die kanonische Ziel-URL direkt hergestellt.
- OpenAPI, Datenbankschema und RLS bleiben unverändert.

## BDD-Szenarien und Testzuordnung

| Szenario | Given | When | Then | Automatisierter Test |
|---|---|---|---|---|
| Weitere Aufgabe offen | Eine modulare Aufgabe wurde endgültig abgegeben und im selben Modul liegt eine andere nicht finalisierte Aufgabe | Der Abschlusszustand erscheint | Der einzige Rückknopf heißt „Zurück zum Modul“ und öffnet die Modulansicht | Unit-, Komponenten- und `learner-navigation.spec.ts`-Test |
| Modul vollständig | Eine modulare Aufgabe wurde endgültig abgegeben und alle anderen Aufgaben desselben Moduls sind finalisiert | Der Abschlusszustand erscheint | Der einzige Rückknopf heißt „Zurück zum Lernpfad“ und öffnet den Modulgraphen | Unit-, Komponenten- und `learner-navigation.spec.ts`-Test |
| Nur formative Rückmeldung | Eine andere Aufgabe im selben Modul besitzt Rückmeldung, aber keine endgültige Abgabe | Der Abschlusszustand der aktuellen Aufgabe erscheint | Die andere Aufgabe gilt als offen und der Rückweg führt zum Modul | Unit-Test |
| Lineare Einheit | Eine Aufgabe in einer linearen Lerneinheit ist geöffnet | Der sichtbare Rückweg wird betätigt | „Zurück zu den Inhalten“ öffnet die fortlaufende Inhaltsansicht | Komponenten- und Browser-Test |
| Hierarchischer Browser-Verlauf | Eine lernende Person öffnet Lernpfad, Modul und Aufgabe nacheinander | Browser-Zurück und Browser-Vorwärts werden verwendet | Modul und Aufgabe werden in der erwarteten Reihenfolge wiederhergestellt | `learner-navigation.spec.ts` (`@feature-acceptance`) |
| Direkter Aufgabenlink | Eine Aufgabe wurde direkt geöffnet oder neu geladen | Der sichtbare Rückweg wird betätigt | Die Person bleibt in der Lerneinheit und erreicht das fachlich bezeichnete Ziel | Navigations- und `learner-navigation.spec.ts`-Test |
| Direkter Modullink | Ein Modul wurde direkt geöffnet | „Zum Lernpfad“ wird betätigt | Der Modulgraph erscheint unabhängig von vorherigen Browserseiten | Navigations- und `learner-navigation.spec.ts`-Test |

## Umsetzung

1. Die Abschlussziel-Entscheidung als kleine, pure Frontend-Funktion mit Tests modellieren.
2. Komponenten erhalten ein ausdrückliches Abschlussziel statt eines mehrdeutigen Rück-Callbacks.
3. Verlaufseinträge um das geprüfte Elternziel ergänzen und sichtbare Rückwege über einen gemeinsamen Navigationshelfer ausführen.
4. Rückbeschriftungen für modulare und lineare Lerneinheiten vereinheitlichen.
5. Design-Dokument und Nutzerhandbuch an die verbindliche Abschlussregel anpassen.

## Abnahme

- Die betroffenen Vitest-Tests laufen zuerst rot und nach der Implementierung grün.
- Der authentifizierte Browserlauf prüft Ziel-URLs und sichtbare Zielansichten, nicht nur die erneute Erreichbarkeit einer Aufgabe.
- Vor der Fertigmeldung läuft `make verify-feature FEATURE=learner-navigation` erfolgreich.
