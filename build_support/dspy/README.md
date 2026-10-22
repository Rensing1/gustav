# Überprüfte DSPy-Variante

GUSTAV verwendet DSPy 3.4.1+gustav.1 auf Basis des veröffentlichten DSPy-3.4.1-Wheels. Der SHA-256-Wert und die unveränderliche Downloadadresse stehen in `../build_dspy_wheel.py`. Das ursprüngliche Wheel enthält die MIT-Lizenz; diese bleibt im erzeugten Artefakt unverändert erhalten. Es wird kein fremder Paketname zur Umgehung von Advisories verwendet: Der Audit prüft zusätzlich explizit DSPy 3.4.1.

## Warum ein Patch?

DSPy 3.4.1 verlangt diskcache, dessen letzte Veröffentlichung 5.6.3 durch CVE-2025-69872 betroffen ist. diskcache-community 5.8.1 ist ein gepflegter Ersatz, behebt das Problem aber nur bei bewusst aktivierter SafeDisk-Konfiguration. Sein Standard-Disk ist weiterhin ungeeignet. Der GUSTAV-Patch ersetzt deshalb die Paketabhängigkeit und erzwingt SafeDisk in jedem DSPy-Cache, auch bei der verzögerten Standardinitialisierung. Eine nachträgliche Erweiterung der Typfreigabe wird abgewiesen.

Die freigegebenen Klassen in `gustav_safe_disk.py` sind reine Antwort-Datenmodelle für die von GUSTAV verwendeten Chat-Completions einschließlich Verbrauchsangaben und Tool-Call-Daten. Ganze Module oder NumPy-Rekonstruktionsfunktionen werden nicht freigegeben. Unbekannte Antworttypen werden nicht auf Festplatte gespeichert. Das ist bewusst ein Cache-Miss, keine unsichere Ersatzserialisierung.

## Reproduzierbarer Build

`python build_support/build_dspy_wheel.py` prüft die Upstream-Bytes, wendet exakt gezählte Ersetzungen an und erzeugt ein Wheel mit stabiler Dateireihenfolge, Zeitstempeln und neu berechnetem RECORD. Es erhält alle übrigen Paketabhängigkeiten. `make lock-python` führt diesen Schritt vor beiden Hash-Locks aus. Docker baut dasselbe Artefakt in einer eigenen Stufe.

Eine frische lokale Testumgebung installiert anschließend mit `.venv/bin/python -m pip install --require-hashes --find-links .tmp/security-wheels -r backend/requirements-harness.lock`. Mit `.venv/bin/python -m piptools sync backend/requirements-harness.lock --pip-args='--require-hashes --find-links .tmp/security-wheels'` werden auch abgelöste Pakete entfernt. `pip check` muss danach erfolgreich sein. Niemals das Original-diskcache zusätzlich installieren.

## Cache-Wechsel und Wartung

Unter dem bestehenden `DSPY_CACHEDIR` wird ausschließlich `gustav-safe-v1` geöffnet. Alte Dateien bleiben unberührt und werden nicht migriert. Manipulierte beziehungsweise nicht mehr lesbare Einträge werden verworfen; Ergebnisse werden erneut berechnet. Ein Cache ist kein fachlicher Datenspeicher.

Bei jeder Änderung der Upstream-Version oder der freigegebenen Modellklassen sind die Cache-Sicherheits-, KI-Vertrags- und Reproduzierbarkeitstests erneut erforderlich. Nach Veröffentlichung einer geeigneten Upstream-Lösung wird der lokale Patch entfernt und durch diese ersetzt. Alle Änderungen an einem bereits veröffentlichten lokalen Wheel erhalten eine neue lokale Versionsnummer.

Quellen: https://pypi.org/project/dspy/3.4.1/ ; https://github.com/secondwindoss/diskcache-community/blob/master/SECURITY.md ; https://github.com/advisories/GHSA-w8v5-vhqr-4h9v
