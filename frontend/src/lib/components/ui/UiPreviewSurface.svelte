<script lang="ts">
  import LearnerContentWorkspace from "$lib/components/learning-unit/LearnerContentWorkspace.svelte";
  import LearningResponseGroup from "$lib/components/learning-unit/LearningResponseGroup.svelte";
  import type { ContentGroup } from "$lib/learning-unit/workspace";
  import type { LearningMaterial, LearningSubmission, LearningTask } from "$lib/types/learning";

  import AuthFrame from "./AuthFrame.svelte";
  import BreadcrumbBar from "./BreadcrumbBar.svelte";
  import GraphInspectorPanel from "./GraphInspectorPanel.svelte";
  import GraphStageFrame from "./GraphStageFrame.svelte";
  import ModeSwitch from "./ModeSwitch.svelte";
  import QuietList from "./QuietList.svelte";
  import QuietListEntry from "./QuietListEntry.svelte";
  import TeacherGraphWorkspaceFrame from "./TeacherGraphWorkspaceFrame.svelte";

  let { userName }: { userName: string } = $props();

  let previewTheme = $state<"light" | "dark">("light");

  const sampleSubmission: LearningSubmission = {
    id: "preview-submission-1",
    attempt_nr: 1,
    kind: "text",
    intent: "submit",
    created_at: "2026-04-05 10:00",
    analysis_status: "completed",
    text_body: "Meine Lösung in der Inhaltsansicht.",
    feedback_md: "## Rückmeldung\n\nRuhig, klar und direkt formuliert.",
    analysis_json: {
      schema: "learning.v1",
      score: 8,
      text: "Stabil",
      criteria_results: []
    }
  };

  const previewTask: LearningTask = {
    id: "preview-task-1",
    instruction_md: "## Arbeitsauftrag\n\nErkläre in zwei Sätzen, warum Module klar begrenzte Objekte bleiben sollen.",
    criteria: ["Klarheit"],
    kind: "native"
  };

  const previewMaterial: LearningMaterial = {
    id: "preview-material-1",
    title: "Einführung",
    kind: "markdown",
    position: 1,
    body_md: "## Material\n\nKlare Objektgrenzen schaffen Ruhe im Arbeitsraum."
  };

  const previewContentGroups: ContentGroup[] = [
    {
      id: "module-1",
      title: "Erkundung",
      items: [
        {
          key: "material:preview-material-1",
          kind: "material",
          title: "Was tut die Europäische Union für mich und wie verändert sie meinen Alltag?",
          position: 1,
          contextLabel: "Erkundung",
          moduleId: "module-1",
          material: previewMaterial
        },
        {
          key: "task:preview-task-1",
          kind: "task",
          title: "Aufgabe 1",
          position: 2,
          contextLabel: "Erkundung",
          moduleId: "module-1",
          task: previewTask
        }
      ]
    },
    {
      id: "module-2",
      title: "Motive und Werte",
      items: [
        {
          key: "material:preview-material-2",
          kind: "material",
          title: "Motive",
          position: 1,
          contextLabel: "Motive und Werte",
          moduleId: "module-2",
          material: {
            ...previewMaterial,
            id: "preview-material-2",
            title: "Motive"
          }
        },
        {
          key: "task:preview-task-2",
          kind: "task",
          title: "Aufgabe 1",
          position: 2,
          contextLabel: "Motive und Werte",
          moduleId: "module-2",
          task: {
            ...previewTask,
            id: "preview-task-2"
          }
        },
        {
          key: "material:preview-material-3",
          kind: "material",
          title: "Artikel 2 des Vertrages",
          position: 3,
          contextLabel: "Motive und Werte",
          moduleId: "module-2",
          material: {
            ...previewMaterial,
            id: "preview-material-3",
            title: "Artikel 2 des Vertrages"
          }
        },
        {
          key: "material:preview-material-4",
          kind: "material",
          title: "Werte der Union",
          position: 4,
          contextLabel: "Motive und Werte",
          moduleId: "module-2",
          material: {
            ...previewMaterial,
            id: "preview-material-4",
            title: "Werte der Union"
          }
        }
      ]
    }
  ];

</script>

<div class="workspace-page preview-page" data-theme={previewTheme}>
  <section class="preview-heading">
    <p class="workspace-label">Internal UI</p>
    <h1>Designsystem-Vorschau für GUSTAV</h1>
    <p>
      Diese interne Fläche zeigt Tokens, Shell-Bausteine und die erste
      Produktfamilie für Theme- und Strukturvergleiche.
    </p>
    <p class="preview-heading__meta">Angemeldet als {userName}</p>
    <div class="preview-reference-banner">
      <p class="workspace-label">Designreferenz</p>
      <strong>Taskfläche zuerst, Graph daraus abgeleitet.</strong>
    </div>
    <div class="preview-theme-toggle">
      <button data-current={previewTheme === "light"} type="button" onclick={() => (previewTheme = "light")}>Light</button>
      <button data-current={previewTheme === "dark"} type="button" onclick={() => (previewTheme = "dark")}>Dark</button>
    </div>
  </section>

  <section class="preview-showcase">
    <article class="preview-card">
      <p class="preview-card__eyebrow">Tokens</p>
      <h2>Startpalette</h2>
      <div class="preview-token-grid">
        <div class="preview-token-swatch" style="--swatch: var(--color-bg-surface)">Surface</div>
        <div class="preview-token-swatch" style="--swatch: var(--color-bg-muted)">Muted</div>
        <div class="preview-token-swatch" style="--swatch: var(--color-accent)">Accent</div>
        <div class="preview-token-swatch" style="--swatch: var(--color-success)">Success</div>
      </div>
    </article>

    <article class="preview-card">
      <p class="preview-card__eyebrow">Shell</p>
      <div class="preview-shell-sample">
        <div class="preview-shell-sample__topbar">
          <strong>GUSTAV</strong>
          <BreadcrumbBar
            items={[
              { label: "Lernraum", href: "/learning" },
              { label: "Programmieren mit Scratch", href: "/learning/courses/course-1" },
              { label: "Erste Schritte" }
            ]}
          />
        </div>
        <div class="preview-shell-sample__body">
          <ModeSwitch
            label="Lerneinheit"
            options={[
              { label: "Übersicht", current: true, href: "/ui-lab" },
              { label: "Inhalte", current: false, href: "/ui-lab?mode=content" }
            ]}
          />
        </div>
      </div>
    </article>

    <article class="preview-card">
      <p class="preview-card__eyebrow">Lehrkraft-Graph</p>
      {#snippet previewCommandPopovers()}
        <div class="workspace-unit-commandbar-popover" role="dialog" aria-label="Phase hinzufügen">
          <div class="workspace-unit-commandbar-popover__header">
            <div>
              <p class="workspace-label">Canvas</p>
              <h2>Phase hinzufügen</h2>
            </div>
            <a class="workspace-link-action workspace-link-action--subtle" href="/ui-lab">Schließen</a>
          </div>
          <form class="workspace-form workspace-form--compact">
            <label class="workspace-field">
              <span>Titel</span>
              <input name="title" type="text" value="Neue Phase" />
            </label>
            <div class="workspace-unit-commandbar-popover__actions">
              <button class="workspace-link-action" type="button">Anlegen</button>
            </div>
          </form>
        </div>
      {/snippet}
      <TeacherGraphWorkspaceFrame
        backHref="/teaching/units"
        backLabel="Zurück zu Lerneinheiten"
        title="Programmieren mit Scratch"
        copy="8 Phasen · 21 Module · dieselbe Graphansicht wie für Lernende"
        commandBarActions={[
          { label: "Phase hinzufügen", href: "/ui-lab", active: true },
          { label: "Modul hinzufügen", href: "/ui-lab", active: false }
        ]}
        commandBarPopovers={previewCommandPopovers}
        inspectorOpen={true}
      >
        {#snippet canvas()}
          <div class="preview-graph-reference">
            <div class="teacher-flow-status teacher-flow-status--success">Phase gespeichert.</div>

            <div class="preview-graph-sample teacher-flow-shell">
              <div class="preview-graph-sample__phase">
                <div class="teacher-flow-phase-band teacher-flow-phase-band--selected">
                  <div class="teacher-flow-phase-band__label">
                    <span class="teacher-flow-phase-band__kicker">PHASE 01</span>
                    <strong class="teacher-flow-phase-band__title">Erste Schritte</strong>
                  </div>
                </div>
              </div>

              <div class="preview-graph-sample__node teacher-flow-unit-node teacher-flow-unit-node--selected">
                <div class="teacher-flow-unit-node__copy">
                  <div class="teacher-flow-unit-node__header">
                    <div class="teacher-flow-unit-node__header-main">
                      <span aria-hidden="true" class="teacher-flow-unit-node__drag-handle"></span>
                      <span>Modul 1</span>
                    </div>
                    <span class="teacher-flow-unit-node__state">Module node</span>
                    <a class="teacher-flow-unit-node__editor" href="/ui-lab">Öffnen</a>
                  </div>
                  <strong>Fachbegriffe</strong>
                  <small>1 Material · 1 Aufgabe</small>
                </div>

                <div class="teacher-flow-unit-node__popover">
                  <a class="teacher-flow-unit-node__popover-action" href="/ui-lab">Inhalt bearbeiten</a>
                  <button class="teacher-flow-unit-node__popover-action teacher-flow-unit-node__popover-action--subtle" type="button">
                    Eigenschaften
                  </button>
                  <a class="teacher-flow-unit-node__popover-action teacher-flow-unit-node__popover-action--subtle" href="/ui-lab">
                    Aufgabe hinzufügen
                  </a>
                </div>
              </div>
            </div>
          </div>
        {/snippet}

        {#snippet inspector()}
          <GraphInspectorPanel eyebrow="Property inspector" title="Abschnitt bearbeiten" closeHref="/ui-lab">
            {#snippet children()}
              <form class="workspace-form workspace-form--compact">
                <label class="workspace-field">
                  <span>Name</span>
                  <input name="title" type="text" value="Einführung" />
                </label>
                <div class="workspace-unit-commandbar-popover__actions">
                  <button class="workspace-link-action" type="button">Speichern</button>
                  <a class="workspace-link-action workspace-link-action--subtle" href="/ui-lab">Inhalt bearbeiten</a>
                </div>
              </form>
            {/snippet}

            {#snippet footer()}
              <button class="workspace-link-action workspace-link-action--danger" type="button">Abschnitt löschen</button>
            {/snippet}
          </GraphInspectorPanel>
        {/snippet}
      </TeacherGraphWorkspaceFrame>
    </article>

    <article class="preview-card">
      <p class="preview-card__eyebrow">Lernraum · Orientieren</p>
      <LearnerContentWorkspace
        learnerSub="preview-student"
        courseId="course-1"
        unitTitle="Grundlagen der Europäischen Union"
        unitType="modular"
        contentGroups={previewContentGroups}
        mode="orienting"
        navigationVisible={true}
        historyByTask={{ [previewTask.id]: [sampleSubmission] }}
        onBeginTask={() => {}}
        onPauseTask={() => {}}
        onCloseModule={() => {}}
        onSetCompactSurface={() => {}}
        onToggleMaterial={() => {}}
      />
    </article>

    <article class="preview-card">
      <p class="preview-card__eyebrow">Lernraum · Bearbeiten</p>
      <LearnerContentWorkspace
        learnerSub="preview-student"
        courseId="course-1"
        unitTitle="Grundlagen der Europäischen Union"
        unitType="modular"
        contentGroups={previewContentGroups}
        mode="working"
        activeTaskKey="task:preview-task-1"
        activeEditorMode="text"
        compactSurface="task"
        contextModules={previewContentGroups.map((group) => ({
          id: group.id,
          title: group.title ?? "Modul",
          current: group.id === "module-1",
          loaded: true,
          loading: false,
          error: null,
          items: group.items
        }))}
        historyByTask={{ [previewTask.id]: [sampleSubmission] }}
        onBeginTask={() => {}}
        onPauseTask={() => {}}
        onCloseModule={() => {}}
        onSetCompactSurface={() => {}}
        onToggleMaterial={() => {}}
      />
    </article>

    <article class="preview-card" data-testid="preview-dialog-states">
      <p class="preview-card__eyebrow">Dialogarbeitsbereich</p>
      <div class="preview-dialog-stack">
        <section class="preview-dialog-state">
          <h2>KI-Dialog · Gespräch</h2>
          <div class="dialog-workspace" data-testid="preview-dialog-conversation">
            <nav class="dialog-workspace__switch" aria-label="Arbeitsbereich wählen">
              <button class="dialog-workspace__switch-button dialog-workspace__switch-button--active" type="button">Aufgabe</button>
              <button class="dialog-workspace__switch-button" type="button">Materialien</button>
            </nav>
            <div class="dialog-layout" data-compact-surface="task" data-phase="conversation">
              <aside class="dialog-sidebar" data-dialog-surface="materials" aria-label="Dialogpartner und Sitzungsaktionen">
                <header class="dialog-context">
                  <p class="workspace-label">KI-Dialogpartner</p>
                  <h5>Archivarin Ada</h5>
                  <div class="dialog-context__description markdown-prose">
                    <p>Eine sachkundige Gesprächspartnerin, die historische Quellen mit dir untersucht.</p>
                  </div>
                </header>
                <p class="dialog-context__meta" aria-label="Dialogstatus">
                  <span>KI</span>
                  <span>Mit Satzanfängen</span>
                  <span>Runde 1/3</span>
                </p>
                <div class="dialog-notice" role="note">
                  <strong>Hinweis zur KI</strong>
                  <span>Antworten können Fehler enthalten. Gib keine persönlichen oder vertraulichen Informationen ein.</span>
                </div>
                <nav class="dialog-session-actions" aria-label="Sitzungsaktionen">
                  <button class="workspace-top-action workspace-top-action--quiet" type="button">Pausieren</button>
                  <button class="workspace-top-action workspace-top-action--quiet" type="button">Dialog beenden</button>
                </nav>
              </aside>
              <div class="dialog-main" data-dialog-surface="task">
                <div class="dialog-transcript" role="log" aria-label="Beispielhafter Dialogverlauf">
                  <article class="dialog-message dialog-message--ai">
                    <p class="dialog-message__speaker">KI · Archivarin Ada</p>
                    <div class="markdown-prose"><p>Welche Perspektive erkennst du in der Quelle?</p></div>
                  </article>
                  <article class="dialog-message dialog-message--student">
                    <p class="dialog-message__speaker">Schüler · Du</p>
                    <div class="markdown-prose"><p>Die Quelle stellt vor allem die Sicht der Regierung dar.</p></div>
                    <small class="dialog-message__help">Hilfestellung: Satzanfang verwendet</small>
                  </article>
                  <article class="dialog-message dialog-message--ai">
                    <p class="dialog-message__speaker">KI · Archivarin Ada</p>
                    <div class="markdown-prose"><p>Woran machst du diese Perspektive sprachlich fest?</p></div>
                  </article>
                </div>
                <section class="dialog-composer" aria-label="Beispielhafte Dialogeingabe">
                  <div class="dialog-starters" aria-label="Satzanfang-Hilfen">
                    <p class="dialog-starters__label">Hilfestellung · Satzanfänge</p>
                    <button class="workspace-top-action workspace-top-action--quiet workspace-top-action--subtle dialog-starter" type="button">An der Wortwahl fällt mir auf …</button>
                    <button class="workspace-top-action workspace-top-action--quiet workspace-top-action--subtle dialog-starter" type="button">Ein Hinweis dafür ist …</button>
                  </div>
                  <label class="workspace-field">
                    <span>Deine Antwort (1/3)</span>
                    <textarea rows="3"></textarea>
                  </label>
                  <div class="dialog-actions dialog-composer__actions">
                    <button class="workspace-top-action workspace-top-action--accent" type="button">Antwort senden</button>
                  </div>
                </section>
              </div>
            </div>
          </div>
        </section>

        <section class="preview-dialog-state">
          <h2>KI-Dialog · Abschluss</h2>
          <div class="dialog-workspace" data-testid="preview-dialog-completion">
            <nav class="dialog-workspace__switch" aria-label="Arbeitsbereich wählen">
              <button class="dialog-workspace__switch-button dialog-workspace__switch-button--active" type="button">Aufgabe</button>
              <button class="dialog-workspace__switch-button" type="button">Materialien</button>
            </nav>
            <div class="dialog-layout" data-compact-surface="task" data-phase="closing">
              <aside class="dialog-sidebar" data-dialog-surface="materials" aria-label="Dialogpartner und Sitzungsaktionen">
                <header class="dialog-context">
                  <p class="workspace-label">KI-Dialogpartner</p>
                  <h5>Archivarin Ada</h5>
                  <div class="dialog-context__description markdown-prose">
                    <p>Der Verlauf bleibt sichtbar, während du deine Abgabe vorbereitest.</p>
                  </div>
                </header>
                <p class="dialog-context__meta" aria-label="Dialogstatus">
                  <span>KI</span>
                  <span>Mit Satzanfängen</span>
                  <span>Runde 1/3</span>
                </p>
                <div class="dialog-notice" role="note">
                  <strong>Hinweis zur KI</strong>
                  <span>Antworten können Fehler enthalten. Prüfe deine Schlussfolgerung selbst.</span>
                </div>
                <nav class="dialog-session-actions" aria-label="Sitzungsaktionen">
                  <button class="workspace-top-action workspace-top-action--quiet" type="button">Pausieren</button>
                </nav>
              </aside>
              <div class="dialog-main" data-dialog-surface="task">
                <div class="dialog-transcript" role="log" aria-label="Dialogverlauf vor dem Abschluss">
                  <article class="dialog-message dialog-message--ai">
                    <p class="dialog-message__speaker">KI · Archivarin Ada</p>
                    <div class="markdown-prose"><p>Woran machst du diese Perspektive sprachlich fest?</p></div>
                  </article>
                  <article class="dialog-message dialog-message--student">
                    <p class="dialog-message__speaker">Schüler · Du</p>
                    <div class="markdown-prose"><p>Wertende Begriffe lassen die Regierung besonders kompetent erscheinen.</p></div>
                  </article>
                </div>
                <section class="dialog-closing" aria-labelledby="preview-dialog-closing-title">
                  <header>
                    <p class="workspace-label">Abschluss</p>
                    <h6 id="preview-dialog-closing-title">Abschluss vorbereiten</h6>
                  </header>
                  <label class="workspace-field">
                    <span>Fasse deine wichtigste Erkenntnis zusammen.</span>
                    <textarea rows="4">Die Wortwahl zeigt, dass die Quelle keine neutrale Perspektive einnimmt.</textarea>
                  </label>
                  <div class="dialog-actions dialog-closing__actions">
                    <button class="workspace-top-action workspace-top-action--quiet" type="button">Zurück zum Dialog</button>
                    <button class="workspace-top-action workspace-top-action--accent" type="button">Endgültig abgeben</button>
                  </div>
                </section>
              </div>
            </div>
          </div>
        </section>
      </div>
    </article>

    <article class="preview-card">
      <p class="preview-card__eyebrow">Lernpfad</p>
      <QuietList>
        <QuietListEntry href="/learning" title="Klasse 10a" />
        <QuietListEntry href="/learning/courses/course-1" title="Programmieren mit Scratch" />
        <QuietListEntry href="/learning/courses/course-1/units/unit-1" title="Erste Schritte" />
      </QuietList>
    </article>

    <article class="preview-card">
      <p class="preview-card__eyebrow">Übersicht</p>
      <GraphStageFrame chromeless eyebrow="Graph-Stage" title="Lernpfad" copy="Taskfläche zuerst, Graph daraus abgeleitet.">
        {#snippet children()}
          <div class="preview-graph-sample teacher-flow-shell">
            <div class="preview-graph-sample__phase">
              <div class="teacher-flow-phase-band teacher-flow-phase-band--selected">
                <div class="teacher-flow-phase-band__label">
                  <span class="teacher-flow-phase-band__kicker">PHASE 01</span>
                  <strong class="teacher-flow-phase-band__title">Erste Schritte</strong>
                </div>
              </div>
            </div>

            <div class="preview-graph-sample__learner-grid">
              <div class="preview-graph-sample__node">
                <button
                  class="teacher-flow-unit-node teacher-flow-unit-node--learner teacher-flow-unit-node--learner-open teacher-flow-unit-node--selected"
                  type="button"
                >
                  <div class="teacher-flow-unit-node__copy">
                    <div class="teacher-flow-unit-node__header">
                      <div class="teacher-flow-unit-node__header-main">
                        <span>Modul 1</span>
                      </div>
                    </div>
                    <strong>Offenes Modul</strong>
                    <div class="teacher-flow-unit-node__meta">
                      <small>0/1 Aufgaben</small>
                      <small>1 Materialien</small>
                    </div>
                  </div>
                </button>
              </div>

              <div class="preview-graph-sample__node">
                <button
                  class="teacher-flow-unit-node teacher-flow-unit-node--learner teacher-flow-unit-node--learner-open teacher-flow-unit-node--selected"
                  type="button"
                >
                  <div class="teacher-flow-unit-node__copy">
                    <div class="teacher-flow-unit-node__header">
                      <div class="teacher-flow-unit-node__header-main">
                        <span>Modul 2</span>
                      </div>
                    </div>
                    <strong>Weiteres offenes Modul</strong>
                    <div class="teacher-flow-unit-node__meta">
                      <small>0/1 Aufgaben</small>
                      <small>1 Materialien</small>
                    </div>
                  </div>
                </button>
              </div>

              <div class="preview-graph-sample__node">
                <button
                  class="teacher-flow-unit-node teacher-flow-unit-node--learner teacher-flow-unit-node--learner-done"
                  type="button"
                >
                  <div class="teacher-flow-unit-node__copy">
                    <div class="teacher-flow-unit-node__header">
                      <div class="teacher-flow-unit-node__header-main">
                        <span>Modul 3</span>
                      </div>
                    </div>
                    <strong>Abgeschlossen</strong>
                    <div class="teacher-flow-unit-node__meta">
                      <small>1/1 Aufgaben</small>
                      <small>1 Materialien</small>
                    </div>
                  </div>
                </button>
              </div>

              <div class="preview-graph-sample__node">
                <button
                  class="teacher-flow-unit-node teacher-flow-unit-node--learner teacher-flow-unit-node--learner-locked"
                  type="button"
                  disabled
                >
                  <div class="teacher-flow-unit-node__copy">
                    <div class="teacher-flow-unit-node__header">
                      <div class="teacher-flow-unit-node__header-main">
                        <span>Modul 4</span>
                      </div>
                    </div>
                    <strong>Noch nicht offen</strong>
                    <div class="teacher-flow-unit-node__meta">
                      <small>0/1 Aufgaben</small>
                      <small>1 Materialien</small>
                    </div>
                  </div>
                </button>
              </div>
            </div>
          </div>
        {/snippet}
      </GraphStageFrame>
    </article>

    <article class="preview-card">
      <p class="preview-card__eyebrow">Lehrkraft-Knoten</p>
      <GraphStageFrame chromeless eyebrow="Graph-Stage" title="Teacher flow" copy="Gleiche Objektfamilie, andere Werkzeuge.">
        {#snippet children()}
          <div class="preview-graph-sample teacher-flow-shell">
            <div class="preview-graph-sample__phase">
              <div class="teacher-flow-phase-band teacher-flow-phase-band--selected">
                <div class="teacher-flow-phase-band__label">
                  <span class="teacher-flow-phase-band__kicker">PHASE 01</span>
                  <strong class="teacher-flow-phase-band__title">Erste Schritte</strong>
                </div>
              </div>
            </div>

            <div class="preview-graph-sample__node teacher-flow-unit-node teacher-flow-unit-node--selected">
              <div class="teacher-flow-unit-node__copy">
                <div class="teacher-flow-unit-node__header">
                  <div class="teacher-flow-unit-node__header-main">
                    <span aria-hidden="true" class="teacher-flow-unit-node__drag-handle"></span>
                    <span>Modul 1</span>
                  </div>
                  <span class="teacher-flow-unit-node__state">Module node</span>
                  <a class="teacher-flow-unit-node__editor" href="/ui-lab">Öffnen</a>
                </div>
                <strong>Fachbegriffe</strong>
                <small>1 Material · 1 Aufgabe</small>
              </div>

              <div class="teacher-flow-unit-node__popover">
                <a class="teacher-flow-unit-node__popover-action" href="/ui-lab">Inhalt bearbeiten</a>
                <button class="teacher-flow-unit-node__popover-action teacher-flow-unit-node__popover-action--subtle" type="button">
                  Eigenschaften
                </button>
                <a class="teacher-flow-unit-node__popover-action teacher-flow-unit-node__popover-action--subtle" href="/ui-lab">
                  Aufgabe hinzufügen
                </a>
              </div>
            </div>
          </div>
        {/snippet}
      </GraphStageFrame>
    </article>

    <article class="preview-card">
      <p class="preview-card__eyebrow">Inspector</p>
      <GraphInspectorPanel eyebrow="Property inspector" title="Phase bearbeiten" closeHref="/ui-lab">
        {#snippet children()}
          <form class="workspace-form workspace-form--compact">
            <label class="workspace-field">
              <span>Name</span>
              <input name="title" type="text" value="Erste Schritte" />
            </label>
            <div class="workspace-unit-commandbar-popover__actions">
              <button class="workspace-link-action" type="button">Speichern</button>
            </div>
          </form>
        {/snippet}
      </GraphInspectorPanel>
    </article>

    <article class="preview-card">
      <p class="preview-card__eyebrow">Rückmeldung</p>
      <h2>Feedback-Familie</h2>
      <LearningResponseGroup submission={sampleSubmission} />
    </article>

    <article class="preview-card">
      <p class="preview-card__eyebrow">Auth</p>
      <AuthFrame
        embedded={true}
        eyebrow="Session beendet"
        title="Erfolgreich abgemeldet"
        body={`Vorschau für ${userName}. Auth bleibt Teil derselben Produktsprache.`}
        actionHref="/auth/login"
        actionLabel="Erneut anmelden"
      />
    </article>
  </section>
</div>
