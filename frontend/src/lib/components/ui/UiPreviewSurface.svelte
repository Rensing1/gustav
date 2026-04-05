<script lang="ts">
  import TeacherGraphCommandBar from "$lib/components/teacher-unit-graph/TeacherGraphCommandBar.svelte";
  import LearningTaskCard from "$lib/components/learning-unit/LearningTaskCard.svelte";
  import LearningResponseGroup from "$lib/components/learning-unit/LearningResponseGroup.svelte";
  import type { LearningSubmission, LearningTask } from "$lib/types/learning";

  import AuthFrame from "./AuthFrame.svelte";
  import BreadcrumbBar from "./BreadcrumbBar.svelte";
  import ModeSwitch from "./ModeSwitch.svelte";
  import PageActionHead from "./PageActionHead.svelte";
  import QuietList from "./QuietList.svelte";
  import QuietListEntry from "./QuietListEntry.svelte";

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

</script>

<div class="workspace-page preview-page" data-theme={previewTheme}>
  <section class="preview-heading">
    <p class="workspace-label">Internal UI</p>
    <h1>Designsystem-Vorschau für GUSTAV</h1>
    <p>
      Diese interne Fläche zeigt Tokens, Shell-Bausteine und die erste
      Produktfamilie für Theme- und Strukturvergleiche.
    </p>
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
      <p class="preview-card__eyebrow">Lehrkraft-Kopf</p>
      <PageActionHead
        backHref="/teaching/units"
        backLabel="Zurück zu Lerneinheiten"
        title="Programmieren mit Scratch"
        copy="8 Phasen · 21 Module · dieselbe Graphansicht wie für Lernende"
      />
    </article>

    <article class="preview-card">
      <p class="preview-card__eyebrow">Commandbar</p>
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
      <TeacherGraphCommandBar
        actions={[
          { label: "Phase hinzufügen", href: "/ui-lab", active: true },
          { label: "Modul hinzufügen", href: "/ui-lab", active: false }
        ]}
        popovers={previewCommandPopovers}
      />
    </article>

    <article class="preview-card">
      <p class="preview-card__eyebrow">Taskfläche</p>
      <LearningTaskCard
        courseId="course-1"
        task={previewTask}
        taskTitle="Begriffe präzisieren"
        contextLabel="Modul Graphen"
        unitType="linear"
        expanded={true}
        submitted={true}
        history={[sampleSubmission]}
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
      <p class="preview-card__eyebrow">Graph-Knoten</p>
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
