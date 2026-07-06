# Supply Chain

Status: Active
Owner: Produktverantwortlicher
Local checks: `make supply-chain-check`
CI status: `make verify` führt `make supply-chain-check` aus
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich

## Zweck
Dieses Dokument beschreibt das reproduzierbare Supply-Chain-Gate für GUSTAV. Das Gate soll FOSS- und Lizenzrisiken sichtbar machen, ohne lokale Entwicklung von Netzwerkzugriffen auf Paketregistries oder Vulnerability-Datenbanken abhängig zu machen.

## Harte lokale Regel
`make supply-chain-check` prüft offline:

- `backend/web/requirements.txt`
- `frontend/package-lock.json`
- `h5p-service/package-lock.json`
- `docs/harness/SUPPLY_CHAIN_INVENTORY.json`

Das maschinenlesbare Inventory wird mit `python -m backend.tools.supply_chain_check --write` erzeugt und mit `python -m backend.tools.supply_chain_check --check` geprüft. Der Check ist Teil von `make verify`.

## Lizenzpolicy
Node-Abhängigkeiten aus den Lockfiles müssen eine erlaubte Lizenz oder eine explizite lokale Ausnahme besitzen. Fehlende Lizenzfelder sind Fehler, außer das Paket ist in der lokalen Override-Liste des Checkers mit einer bekannten Lizenz dokumentiert.

Erlaubte Node-Lizenzformen sind die im Inventory unter `policy.allowed_licenses` dokumentierten FOSS-Lizenzen, darunter MIT, BSD, Apache-2.0, ISC, MPL-2.0, EPL-2.0, GPL-3.0-or-later, OFL-1.1, CC0-1.0 und kompatible Kurzformen.

Python-Abhängigkeiten werden aus der bestehenden `backend/web/requirements.txt` und der installierten Paket-Metadatenbank inventarisiert. Diese Metadaten sind oft nicht SPDX-normalisiert; deshalb ist Python in v1.2 zunächst als `metadata-recorded` klassifiziert. Eine spätere Verschärfung darf erst hart werden, wenn sie ohne falsche Befunde grün ist.

## Vendored Assets
Vendored Assets bleiben in `THIRD_PARTY_NOTICES.md` dokumentiert. Das Supply-Chain-Gate ersetzt diese Hinweise nicht, sondern ergänzt sie um Paketmanager-Abhängigkeiten. Wenn vendored Dateien aktualisiert werden, müssen Herkunft, Revision und Lizenzhinweis weiterhin in `THIRD_PARTY_NOTICES.md` gepflegt werden.

## Keine Netzwerkpflicht
Das harte Gate ruft keine externen Registries, CVE-Datenbanken oder Lizenzdienste auf. Netzwerkabhängige Audit-Werkzeuge können zusätzlich in Release- oder CI-Profilen laufen, dürfen aber nicht die lokale `make verify`-Reproduzierbarkeit ersetzen.
