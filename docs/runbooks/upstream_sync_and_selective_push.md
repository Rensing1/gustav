# Runbook: Selektive Änderungen pushen und Upstream-Updates sicher übernehmen

Ziel: Nur gewünschte Änderungen ins öffentliche Master-Repo geben (z. B. Docs/Tickets), während deploymentspezifische Anpassungen lokal bleiben – und umgekehrt Upstream-Änderungen punktgenau ziehen, ohne lokale Deploy-Files zu überschreiben.

## A) Nur bestimmte lokale Änderungen nach GitHub pushen

1) Branch vom sauberen GitHub-Master
- `git fetch origin`
- `git switch -c feature/docs-sync origin/master`

2) Nur gewünschte Commits/Dateien übernehmen
- Commits cherry-picken: `git cherry-pick <SHA>` (z. B. nur Docs/Tickets-Commit).
- Oder gezielt Dateien holen: `git checkout <SHA> -- docs/` (oder konkrete Pfade), dann neu committen.

3) Prüfen, dass nur freigegebene Pfade drin sind
- `git diff --stat origin/master...HEAD` (sollte nur z. B. `docs/**` zeigen).

4) Push/PR
- `git push origin feature/docs-sync`
- PR beschränken auf die gewünschten Dateien; keine deploy-spezifischen Änderungen (Compose, Caddy, Keycloak, lokale package.json) mitschicken.

Tipps:
- Deployment-Anpassungen in separatem lokalen Branch lassen; nicht cherry-picken.
- Patch-Export geht auch: `git format-patch <SHA> -o /tmp/patches` → im sauberen Branch `git am`.

## B) Upstream-Änderungen holen, ohne lokale Deploy-Anpassungen zu verlieren

1) Upstream holen
- `git fetch origin`

2) Upstream-Stand inspizieren
- `git switch -c upstream-sync origin/master` (separater Branch/Worktree zum Anschauen).

3) Selektiv übernehmen im Deploy-Branch
- Cherry-pick saubere Commits: `git cherry-pick <SHA>` auf deinem Deploy-Branch.
- Oder einzelne Dateien holen: `git checkout origin/master -- docs/ backend/...` (nur die Pfade, die du willst), dann committen.
- Bei Konflikten in Deploy-Files (docker-compose, Caddy, Keycloak, package.json): bewusst eigene Version behalten (`--ours`), weil sie deploymentspezifisch sind.

4) Diff-Kontrolle vor Merge
- `git diff --stat` sicherstellen, dass nur gewünschte Bereiche geändert sind.

5) Alternative Worktree
- `git worktree add ../gustav2-upstream origin/master` für sauberes Testen/Sichten; dann selektiv rüberkopieren oder cherry-picken.

Prinzip:
- Upstream-Änderungen nur dort einspielen, wo sie wirklich gebraucht werden (Code/Docs).
- Lokale Deploy-Konfigurationen bleiben in deinem privaten Branch; nicht blind mergen.
