# Bestätigte Feedbackprompts integrieren

## Auftrag und Ausgangslage

Als Lehrkraft möchte ich, dass GUSTAV die gezeigte Schülerleistung anhand der verlangten Kriterien bewertet und daraus eine verständliche, bedarfsgerechte Rückmeldung erstellt. Die beiden am 01.11.2026 übergebenen Hauptprompts und der Reparaturzusatz sind die maßgebliche Fassung. Die fachliche Modellprüfung ist laut Produktverantwortlichem bereits erfolgt; zusätzliche inhaltliche Modellvergleiche sind nicht beauftragt. Technische Integration und fachliche Wirksamkeit werden nicht gleichgesetzt.

Ausgangsstand: `389b8db8` auf `master`, zwei lokale Commits vor `origin/master`. Bereits vorhandene Änderungen an Markdown-/Diagrammverarbeitung, Frontend, Compose und OpenAPI gehören nicht zu diesem Auftrag und bleiben erhalten. Kein Push ohne ausdrücklichen Auftrag.

## Umsetzung

1. Tests zuerst: neue Promptverträge, Feldbeschreibungen, Reparaturzusatz und Dialog-Kontextweitergabe absichern (Red).
2. Die Text-Hauptprompts wörtlich in den DSPy-Signaturen ersetzen; Bildfassungen auf sichtbare Inhalte übertragen; kriterienlose Rückmeldungen ohne Analyse- oder Punkteannahme formulieren. Lehrkraftvorgaben zu Schwerpunkt, Länge und Aufbau bleiben innerhalb der Bewertungs-, Anrede- und Schutzregeln möglich. JSONAdapter, Ergebnisfelder und serverseitige Zuordnung bleiben erhalten.
3. Nur die Unsicherheit-gleich-null-Regel aus der Reparatur entfernen. Einmalige Reparatur und Fehlerpfade bleiben erhalten.
4. Dialog-Abschluss als gemeinsamen Analyse-/Feedbackaufruf behalten; eigene Promptfassung mit Trennung von Schülerleistung, Hilfen und KI-Kontext. Optionales `teacher_context_md` vom bereits geladenen Aufgaben-Kontext über Worker, Adaptervertrag, Adapter und Programm zur Signatur weitergeben. Keine Ablage im Queue-Payload und keine Ausgabe im Lernenden-DTO.
5. Dokumentation und Changelog aktualisieren, Tests grün machen und kritisch prüfen (Green/Refactor). Browsergate erst nach erfolgreichem CA-Preflight ausschließlich im lokalen Stack ausführen.

Öffentliche API und Datenbankschema ändern sich nicht; OpenAPI beschreibt den internen Lehrkraftkontext bereits passend. Deshalb keine Vertragsänderung oder Migration. Modell, Reasoning, Temperaturen, Preise, Dialogpartner, Satzanfänge, OCR, Wiederholungsplanung und bestehende Ergebnisse bleiben unverändert. Native Übungen nutzen dieselbe Auswertung einschließlich Musterlösung und zulässiger Varianten.

## BDD und Testzuordnung

| Given | When | Then | Test |
| --- | --- | --- | --- |
| Bestätigte Prompttexte | Signaturen werden geladen | Neue Texte und Feldverträge gelten; alte Pflichtstruktur fehlt | `test_feedback_program_dspy_prompt.py`, `test_signature_docstrings_match_prompt_reference.py` |
| Ungültige Analyse | Einmalige Reparatur | Bestätigter Zusatz, unveränderter Kontext, keine erzwungene Nullwertung | Text-/Bild-Reparaturtests und Zusatzprüfung |
| Dialog mit internem Lehrkraftkontext | Abschlussauswertung | Kontext erreicht das Modell getrennt von Leistungsbelegen | Dialogprogramm-, Adapter-, Worker- und lokale DB-Integrationstests |
| Fehlende Kriterien oder leerer Kontext | Verarbeitung | Keine Punkte ohne Kriterien; `None` bleibt kompatibel | Parametrisierte Programm-/Adaptertests |
| Interner Kontext | Lernendenzugriff auf Aufgabe/Ergebnis | Kein Kontext in DTO oder Queue-Payload | API-/Worker-Tests mit lokaler Datenbank |
| Angemeldete Lernende | Textfeedback bzw. Dialogabschluss über Oberfläche | Auswertung und Rückmeldung erscheinen und bleiben nach Neuladen erhalten | `llm-feedback-prompts.spec.ts`, `@feature-acceptance` |

Die Browserprüfung verwendet echte Anmeldung, Server und lokale Datenhaltung mit kontrollierten externen KI-Testantworten. Prompt- und Kontextübergabe werden separat im Backend geprüft; daraus folgt kein erneuter fachlicher Modellvergleich.

## Dokumentation und Abnahme

`docs/references/LLM-Prompts.md` enthält sämtliche geänderten Signaturtexte wörtlich, den Reparaturzusatz, Feldverträge, Lehrkraftprioritäten und die Unterschiede zwischen den Pfaden. Der bestehende Dokumentationsabgleich wird um den Reparaturzusatz ergänzt. Die ausführbaren Signaturen bleiben die einzige Laufzeitquelle.

Erforderlich: gezielte Pytest-Prüfungen einschließlich lokaler DB, `make local-ca-status`, anschließend `make verify-feature FEATURE=llm-feedback-prompts`. Ergebnisse, etwaige Hindernisse und abgeschlossene Schritte werden unten nachgeführt. Kein Fertig-Nachweis ohne erfolgreiches Featuregate.

## Verlauf

- Plan vor Implementierungsänderungen angelegt.
- Red: 12 erwartete Fehler bei 27 erfolgreichen Tests belegten die alten Hauptprompts, den alten Reparaturzusatz und die fehlenden Dialogparameter. Weitere Vertragstests erkannten die noch fehlende Dokumentation und Feldbeschreibungen.
- Green: 195 gezielte Tests einschließlich lokaler Datenbank, Prompt-/Dokumentationsabgleich, Text-/Bildadapter, Reparatur und Datenschutz erfolgreich. Die beiden Text-Hauptprompts werden vollständig gegen unabhängige genehmigte Testvorlagen verglichen; der ausgeführte Reparaturzusatz ebenfalls.
- Lokale Caddy-CA ist in System, Chromium/Codex und Firefox vertraut; Zertifikatsprüfung blieb unverändert.
- Browserabnahme: beide neuen authentifizierten Chromium-Abläufe erfolgreich (Text mit Kriterien und Dialog ohne Kriterien). Testabläufe berücksichtigen das reguläre Aufklappen der Rückmeldung nach Neuladen und warten vor der Dialog-Testantwort auf die abgeschlossene Sitzungseröffnung. Alle laufbezogenen Testdaten wurden durch das Harness bereinigt.
- Das erste Gesamtgate im gemeinsam genutzten Arbeitsbaum stoppte an der veralteten Supply-Chain-Inventarisierung der parallelen Diagramm-/Paketänderungen. Für einen unabhängigen Nachweis wurde eine separate Prüfkopie von `389b8db8` mit ausschließlich den 19 Auftragsdateien angelegt. Fremde Änderungen wurden weder zurückgesetzt noch in diesen Stand übernommen. Das vollständige Gate wurde dort gegen den freigegebenen lokalen Stack erfolgreich ausgeführt.
- Die Gesamtsuite deckte zwei Probleme in der neuen Testvorbereitung auf: Pro Spec ist genau ein `@feature-acceptance`-Hauptablauf erlaubt; Text- und Dialogprüfung laufen deshalb gemeinsam. Außerdem muss der DB-Test nach App-Neuladungen durch andere Tests dieselbe aktuelle App-Instanz wie sein API-Client verwenden. Beide Korrekturen betreffen ausschließlich Tests; die Prompttexte blieben unverändert.
- Vollständige Backend-Suite in der Prüfkopie: 3.210 erfolgreich, 48 vorgesehene Auslassungen. Frontend: 181 Testdateien mit 923 erfolgreichen Tests, Typprüfung ohne Fehler/Warnungen, Produktionsbuild erfolgreich. H5P: 80 erfolgreiche Tests. Für die Frontendprüfung benötigt die separate Arbeitskopie eigene Bibliotheksdateien statt eines Verweises auf den Bibliotheksordner des Hauptarbeitsbaums.
- Abschluss: `make verify-feature FEATURE=llm-feedback-prompts` erfolgreich (Exit 0). Das Gate umfasst Architektur-/API-/Inventarprüfungen, Containerprüfung, vollständige Backend- und Frontendprüfungen, Build, H5P und den gemeinsamen authentifizierten Chromium-Ablauf für Text und Dialog. Die Abnahmedaten wurden vollständig bereinigt. Der abschließende Volltextvergleich bestätigt die genehmigten beiden Hauptprompts und den Reparaturzusatz; Bild-, kriterienlose und Dialogfassungen sind als vereinbarte Ableitungen dokumentiert. Keine zusätzlichen fachlichen Modellprüfungen und kein Push.
