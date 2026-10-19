# Einheitliche Kopfleiste und Kontextnavigation

## User Story
Als Schüler möchte ich globale Ziele und meinen aktuellen Ort auf jeder Seite an derselben Stelle finden, ohne dass Navigation auf kleinen Bildschirmen den Lerninhalt verdrängt.

## Umsetzung
Gemeinsame AppHeader-Komponente mit 64px Desktop- und 56px Mobilhöhe. Globale Ziele bleiben auf allen Seiten verfügbar; mobil in einem beschrifteten Menü einschließlich Kummerkasten. Theme-Auswahl im Kontomenü. Gemeinsame ContextNavigation unter der App-Leiste: vollständiger Breadcrumb auf Desktop, direkter Elternlink und aufklappbare Hierarchie mobil. Modulkontext aus bestehenden Graphdaten und URL ableiten. Redundanten Rücklink der Kursseite entfernen. Keine API-, Schema- oder Datenänderung.

## Prüffälle vor Implementierung
- Given Lernraum, Kurs, Einheit oder Aufgabe, when Seitenwechsel, then globale Leiste und Aktionen behalten Position und Größe. Später: Komponentenprüfung AppHeader und authentifizierter Feature-Test learner-reference-workspace.
- Given Üben, when Navigation angezeigt, then nur Üben ist aktiv, nicht zusätzlich Lernraum. Später: AppHeader-Komponentenprüfung.
- Given schmaler Bildschirm, when Menü geöffnet, then Lernraum, Üben und Kummerkasten erreichbar; Auswahl und Escape schließen das Menü. Später: Komponentenprüfung und Feature-Test.
- Given Aufgabe innerhalb eines Moduls, when Elternlink gewählt, then Modulansicht ohne Aufgabenparameter öffnet; vollständige Hierarchie bleibt erreichbar. Später: Feature-Test learner-reference-workspace.
- Given lange Namen, when 390px/320px Breite, then keine horizontal abgeschnittene Hierarchie; Menüs bleiben im Bildschirm. Sichtprüfung und später Feature-Test.
- Given Konto geöffnet, when Theme gewählt, then bestehende Speicherung bleibt unverändert. Sichtprüfung beider Themes; später Komponentenprüfung.

## Reihenfolge
Implementierung und Build, dann manuelle Browser-Sichtprüfung. Auf ausdrücklichen Nutzerwunsch keine automatisierten Tests und kein Commit vor Sichtfreigabe. Authentifizierte Feature-Verifikation bleibt offen. Vorhandene Abgaben und Entwürfe nicht verändern.

## Umgesetzt und manuell geprüft
Gemeinsame Komponenten `AppHeader` und `ContextNavigation`; BreadcrumbBar unterstützt explizites Neuladen beim Ebenenwechsel. Der Lernarbeitsbereich verwaltet native Browser-History selbst: Ein reaktiver, pro Layout erzeugter Svelte-Kontext hält die globale Orientierung bei internen Modul-/Aufgabenwechseln aktuell. Breadcrumb-Ziele laden die gewählte Ebene vollständig, damit die URL und der bereits gemountete Arbeitsbereich nicht auseinanderlaufen. Doppelte Rücksprünge im Kurs- und Aufgabenkopf entfallen; Tastaturfokus beim Aufgabenstart liegt auf der Aufgabenüberschrift.

Sichtgeprüft: Lernraum und Kurs auf Desktop; Aufgabenraum und Üben auf Desktop (1280px) und schmal (390px); mobile Menüauswahl, Hierarchiemenü und Escape; tatsächlicher Rücksprung Aufgabe → Modul; gespeicherter Entwurf bleibt sichtbar. Dunkelmodus bei 320px geprüft und anschließend Hellmodus wiederhergestellt. Kollision des lokalen Layoutmenüs mit dem Aufgabenstatus korrigiert. Frontend-Build erfolgreich. Keine automatisierten Tests ausgeführt. Lehrkraftseiten und andere Rollen sind noch nicht separat visuell freigegeben. Bestehende Komponenten-/Vertragstests müssen nach Sichtfreigabe an die neue Fokus-ID und Navigation angepasst und gezielt ausgeführt werden.
