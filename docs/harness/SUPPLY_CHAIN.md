# Supply Chain

Status: Active
Owner: Produktverantwortlicher
Local checks: `make supply-chain-check`; online zusätzlich `make dependency-audit`
CI status: Keine anbietergebundene CI erforderlich; `make verify` prüft das Offline-Inventar und `make dependency-audit` ergänzt lokal den aktuellen Online-Stand
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich

## Zweck
Dieses Dokument beschreibt das reproduzierbare Supply-Chain-Gate für GUSTAV. Das Gate soll FOSS- und Lizenzrisiken sichtbar machen, ohne lokale Entwicklung von Netzwerkzugriffen auf Paketregistries oder Vulnerability-Datenbanken abhängig zu machen.

## Harte lokale Regel
`make supply-chain-check` prüft offline:

- `backend/web/requirements.txt`
- `backend/web/requirements.lock` und `backend/requirements-harness.lock` mit vollständigen transitiven Pins und Hashes
- `backend/requirements-harness.txt` einschließlich rekursiver `-r`-Verweise sowie `backend/constraints-ai.txt`
- `frontend/package-lock.json`
- `h5p-service/package-lock.json`
- `docs/harness/SUPPLY_CHAIN_INVENTORY.json`

Das maschinenlesbare Inventory wird mit `python -m backend.tools.supply_chain_check --write` erzeugt und mit `python -m backend.tools.supply_chain_check --check` geprüft. Der Check ist Teil von `make verify`.

## Lizenzpolicy
Node-Abhängigkeiten aus den Lockfiles müssen eine erlaubte Lizenz oder eine explizite lokale Ausnahme besitzen. Fehlende Lizenzfelder sind Fehler, außer das Paket ist in der lokalen Override-Liste des Checkers mit einer bekannten Lizenz dokumentiert.

Erlaubte Node-Lizenzformen sind die im Inventory unter `policy.allowed_licenses` dokumentierten FOSS-Lizenzen, darunter MIT, BSD, Apache-2.0, ISC, MPL-2.0, EPL-2.0, GPL-3.0-or-later, OFL-1.1, CC0-1.0 und kompatible Kurzformen.

Python-Paketnamen und Versionen stammen vollständig aus dem Harness-Lock, der den Runtime-Lock einschließt. Die direkten Requirements werden für die Herkunftszuordnung rekursiv gelesen. Lizenzangaben stammen weiterhin aus installierten Paket-Metadaten; vor einer Inventaraktualisierung muss deshalb der Harness-Lock installiert sein. Die Paket-Metadaten sind oft nicht SPDX-normalisiert; Python bleibt als `metadata-recorded` klassifiziert. Das ist eine dokumentierte Grenze der Lizenzprüfung, keine bestätigte SPDX-Konformität.

## Python-Locks und DSPy-Baseline

Unter Python 3.11 erzeugt `make lock-python` zuerst den Runtime-Lock und anschließend den durch diesen eingeschränkten Harness-Lock. Beide enthalten SHA-256-Hashes; auch die Buildwerkzeuge des Harness werden explizit gepinnt. Die zweite offizielle PyPI-Adresse dient der JSON-Hashabfrage durch pip-tools, nicht als zusätzliche Paketquelle eines Drittanbieters.

Docker installiert `backend/web/requirements.lock` mit `--require-hashes`. Die lokale Testumgebung wird mit `.venv/bin/pip install --require-hashes -r backend/requirements-harness.lock` aktualisiert. Anschließend wird das Inventar mit `.venv/bin/python -m backend.tools.supply_chain_check --write` erzeugt und geprüft. Fehlgeschlagene Installationen brechen den Image-Build ab; die Compilerbereinigung läuft erst danach.

`docs/harness/DSPY_BASELINE.json` dokumentiert die vorläufig fixierte, tatsächlich eingesetzte DSPy-Version 3.3.1 samt 59 Abhängigkeiten. `backend/constraints-ai.txt` erzwingt diese Pins. Die Fixierung ist ausdrücklich keine Sicherheitsfreigabe. Sicherheitsmeldungen in gemeinsam genutzten eingefrorenen Paketen erfordern eine separate Entscheidung; DSPy-Upgrade und Optimizing gehören nicht zu dieser Bereinigung.

FastAPI bleibt vorläufig bei 0.136.3: Die neue Routerstruktur ab 0.137 verändert die von GUSTAV verwendete flache Route-Inventarisierung. Der Versuch mit 0.141.1 hat dazu Regressionstests verletzt. Eine spätere Migration muss die Inventarisierung und die App-Verdrahtung zusammen prüfen; siehe [FastAPI Release Notes](https://fastapi.tiangolo.com/release-notes/#01370).

## Vendored Assets
Vendored Assets bleiben in `THIRD_PARTY_NOTICES.md` dokumentiert. Das Supply-Chain-Gate ersetzt diese Hinweise nicht, sondern ergänzt sie um Paketmanager-Abhängigkeiten. Wenn vendored Dateien aktualisiert werden, müssen Herkunft, Revision und Lizenzhinweis weiterhin in `THIRD_PARTY_NOTICES.md` gepflegt werden.

## Offline-Reproduzierbarkeit und Online-Advisories
Das harte `make verify`-Gate ruft keine externen Registries, CVE-Datenbanken oder Lizenzdienste auf. Dadurch bleibt es auch ohne Netzwerk reproduzierbar.

`make dependency-audit` ergänzt dieses Inventar bewusst als separates lokales Online-Gate. Es führt im Frontend `npm audit --audit-level=low`, im H5P-Service `npm audit --omit=dev --audit-level=low` und für Python `.venv/bin/python -m pip_audit -r backend/requirements-harness.lock` aus. Alle drei Prüfungen laufen auch dann, wenn eine vorherige fehlschlägt; ihr Fehlerstatus wird zusammengefasst. Bei Node schlägt jeder bekannte Befund ab `low` fehl, bei Python jeder gemeldete Befund. Fehlende Werkzeuge sind ebenfalls Fehler. Der Befehl wird vor einem Release und nach jeder Lockfile-Aktualisierung ausgeführt.

Die Node-Projekte deklarieren Node 22.13.0 als unterstützte Untergrenze. Docker-Images verwenden reproduzierbar Node 24.18.0. Direkte sicherheitsrelevante Abhängigkeiten sind exakt gepinnt; gezielte Overrides müssen durch Vertrags- und Regressionstests begründet bleiben.
