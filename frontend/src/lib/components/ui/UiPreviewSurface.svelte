<script lang="ts">
  import LearningUnitContentWorkspace from "$lib/components/learning-unit/LearningUnitContentWorkspace.svelte";
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
      <p class="workspace-label">Mistral Referenz</p>
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
      <p class="preview-card__eyebrow">Taskfläche</p>
      <LearningUnitContentWorkspace
        titleLabel="Taskfläche"
        title="Erste Schritte"
        meta="1 Modul geöffnet · Fokus auf Inhalte"
        courseId="course-1"
        unitType="modular"
        moduleId="module-1"
        tocOpen={true}
        splitView={false}
        activePane="left"
        visiblePaneIds={["left"]}
        contentGroups={previewContentGroups}
        paneItems={{
          left: previewContentGroups[0].items.map((item) => ({
            item,
            expanded: item.kind === "task"
          })),
          right: []
        }}
        historyTaskId={previewTask.id}
        history={[sampleSubmission]}
        submittedTaskId={previewTask.id}
        submissionMessage="Aufgabe abgegeben."
        submissionErrorTaskId={null}
        submissionErrorMessage={null}
        submissionFocusByPane={{ left: null, right: null }}
        submissionModeByPane={{ left: null, right: null }}
        showSplitToggle={true}
        layoutMenuEnabled={true}
        tocWidth={16.25}
        workspaceWidth={72}
        splitRatio={50}
        tocGap={1.1}
        paneGap={1.1}
        fontScale={1}
        itemDomId={(paneId, itemKey) => `${paneId}-${itemKey}`}
        onToggleToc={() => {}}
        onToggleSplitView={() => {}}
        onResetLayout={() => {}}
        onUpdateTocWidth={() => {}}
        onPreviewWorkspaceWidth={() => {}}
        onCommitWorkspaceWidth={() => {}}
        onPreviewFontScale={() => {}}
        onCommitFontScale={() => {}}
        onUpdateSplitRatio={() => {}}
        onUpdateTocGap={() => {}}
        onUpdatePaneGap={() => {}}
        onSetActivePane={() => {}}
        onOpenItem={() => {}}
        onToggleItem={() => {}}
        onEnterSubmissionWorkspace={() => {}}
        onEnterUploadWorkspace={() => {}}
        onExitSubmissionWorkspace={() => {}}
      />
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

            <div class="preview-graph-sample__node teacher-flow-unit-node teacher-flow-unit-node--selected">
              <button
                class="teacher-flow-unit-node teacher-flow-unit-node--learner teacher-flow-unit-node--learner-open teacher-flow-unit-node--selected"
                type="button"
              >
                <div class="teacher-flow-unit-node__copy">
                  <div class="teacher-flow-unit-node__header">
                    <div class="teacher-flow-unit-node__header-main">
                      <span>Modul 1</span>
                    </div>
                    <span class="teacher-flow-unit-node__state teacher-flow-unit-node__state--open">Offen</span>
                  </div>
                  <strong>Fachbegriffe</strong>
                  <div class="teacher-flow-unit-node__meta">
                    <small>1/1 Aufgaben</small>
                    <small>1 Materialien</small>
                  </div>
                </div>
              </button>
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
