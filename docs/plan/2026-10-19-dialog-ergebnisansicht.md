# Kompakte Dialog-Ergebnisansicht

## User Story und Umsetzung
Nach der Abgabe möchte ich meinen gespeicherten Text, den zugehörigen Auftrag und die Rückmeldung gemeinsam sehen und zum Modul zurückkehren können. Die Ergebnisansicht verwendet LearningSubmissionPreview aus der Modulansicht; Rückmeldung ist dort zunächst geöffnet. Der Gesprächsverlauf bleibt aufklappbar. Ohne geladene Abgabe zeigt die vorhandene Sitzungskomponente bereits Auftrag und Antwort. Keine API- oder Schemaänderung. Rundenzähler und auf Gesprächseingabe ausgelegte Vollhöhe entfallen im Ergebniszustand. Ein neuer Versuch bleibt über die bestehende Modulansicht mit ihren Berechtigungsregeln erreichbar.

## Vorab entworfene Prüffälle
- Abgeschlossene Sitzung: gespeicherte Abschlussantwort und Auftrag sichtbar, Verlauf geschlossen, fertige Rückmeldung offen (DialogWorkspace und SubmissionPreview-Komponentenprüfungen).
- Rückmeldung pending/failed: Antwort bleibt sichtbar, bestehender Status bleibt erhalten.
- Keine Abschlussantwort: kein leerer Antwortblock, Verlauf weiterhin erreichbar.
- Rückkehr: bestehender Exit-Callback führt ins Modul, keine neue Sitzung oder Abgabe.
- Desktop/390px: inhaltsabhängige Höhe, 16px Bereichsabstände, Abgabe und Aktion im normalen Lesefluss.
Keine Tests ausführen; erst eigene Browser-Sichtprüfung und Felix' Sichtprüfung.

Bei der Sichtprüfung festgestellt: `panel=result` wurde bisher nicht an die Dialogkomponente als Lesemodus samt abgegebener Sitzungs-ID weitergereicht. Neuladen startete dadurch eine neue aktive Sitzung. Korrektur: Ergebnis bindet die Sitzung der geladenen Abgabe explizit und schreibgeschützt ein; bis die ID vorhanden ist, erscheint der Ladezustand. Zusätzlicher entworfener Prüffall: Neuladen einer Ergebnisadresse lädt die abgegebene Sitzung, ohne POST zum Sitzungsstart. Die durch die Prüfung bereits entstandene leere aktive Dev-Sitzung wurde nicht gelöscht.

## Sichtprüfung abgeschlossen
Die am 19.10. abgegebene Abschlussantwort wird aus der gespeicherten Sitzung angezeigt. Desktop und 390px geprüft: kompakte Höhe, sichtbare Antwort, offene Rückmeldung, geschlossener Verlauf und Auswertung. Rückkehraktion führt zur Modulansicht. Ergebnisadresse anschließend erneut geöffnet. Frontend gebaut, keine automatisierten Tests ausgeführt; kein Commit.

## Iteration: zusammenhängende Ergebnisgruppen
Vor der Änderung: Die Ergebnisansicht erhält zwei gleichrangige Bereiche „Deine Bearbeitung“ und „Deine Rückmeldung“. Auftrag, Antwort und optionaler Gesprächsverlauf gehören zur Bearbeitung; Kriterien und Auswertungsstatus zur Rückmeldung. Datum steht bei der Bearbeitung, Abgabestatus im Seitenkopf. Der normale Modul-Vorschaumodus bleibt erhalten.

Vorab entworfene Prüffälle: Ergebnis mit Abschlussantwort zeigt Auftrag und Antwort offen und Gespräch optional; ohne Abschlussantwort bleibt das Gespräch offen. Kriterien stehen innerhalb der Rückmeldung. Pending/failed bleiben sichtbar. Desktop und schmale Ansicht zeigen dieselbe Lesereihenfolge, ohne horizontales Überlaufen. Zuordnung: SubmissionPreview-/Transcript-Komponentenprüfungen und bestehende authentifizierte learner-reference-workspace-Spec. Ausführung weiterhin erst nach Sichtfreigabe; jetzt ausschließlich Browser-Sichtprüfung. Keine API-/Schemaänderungen.

Iteration umgesetzt und am echten lokalen Frontend visuell bei Desktopbreite und 390px geprüft: gespeicherte Antwort sichtbar, zwei getrennte Inhaltsgruppen, Gespräch bei Bearbeitung und Kriterien bei Rückmeldung, Rückkehraktion darunter. Frontend-Build erfolgreich. Keine automatisierten Tests ausgeführt; Sichtfreigabe steht aus.

## Iteration: chronologische Bearbeitung
Vor der Änderung: Gespräch vor Abschlussantwort anzeigen, auch in der kompakten Modulvorschau. Gespräch mit Partnernamen benennen; Abschlussauftrag und Antwort bleiben offen. Ergebnis-Rückmeldung erhält einen knappen Hinweis auf die eigenen Beiträge als Bewertungsgrundlage. Laut repo_dialog_queries.complete_session und DialogAssessmentSignature werden Schülernachrichten und optionale Abschlussantwort ausgewertet; KI-Nachrichten sind ausschließlich Kontext.
Vorab entworfene Prüffälle (Transcript-/SubmissionPreview-Komponentenprüfungen): Mit Abschlussantwort steht die Gesprächsdisclosure davor; ohne Abschlussantwort bleibt der Verlauf in der Ergebnisansicht offen; Aufklappen erhält sämtliche Nachrichten und die sichtbare Antwort. Laufender Dialog bleibt unverändert. Desktop/390px visuell prüfen. Keine Tests vor Sichtfreigabe ausführen.

Chronologische Darstellung implementiert und im Browser bei 1280px sowie 390px visuell geprüft. Gespräch steht vor dem offenen Abschlussblock; gespeicherte Antwort bleibt sichtbar. Bewertungsbezug anhand des bestehenden Queue-Payloads und DSPy-Vertrags überprüft, Auswertungslogik unverändert. Frontend gebaut; keine automatisierten Tests ausgeführt.
