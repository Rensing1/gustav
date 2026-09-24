<script lang="ts">
  import { onMount } from "svelte";
  import StatusMessage, { type StatusMessageTone } from "$lib/components/ui/StatusMessage.svelte";
  import { loadH5PWebcomponentsModule } from "$lib/runtime/h5p-webcomponents";
  import type { H5PPersistedResult } from "$lib/types/h5p";
  import type { LearningSubmission } from "$lib/types/learning";
  import { createReadableViewport } from "./h5p-readable-viewport";

  let {
    courseId,
    taskId,
    contentId,
    practiceContext = null,
    onProgressPersisted = null
  }: {
    courseId: string;
    taskId: string;
    contentId: string;
    practiceContext?: {
      sessionId: string;
      itemId: string;
      completionToken: string;
      contextId: string;
    } | null;
    onProgressPersisted?: ((result: H5PPersistedResult) => void | Promise<void>) | null;
  } = $props();

  let root: HTMLDivElement | undefined;
  let region: HTMLDivElement | undefined;
  let dragReady = $state(false);
  let viewMode = $state("readable");
  let viewport: ReturnType<typeof createReadableViewport> | undefined;

  function chooseView(mode: "readable" | "overview") {
    viewMode = mode;
    viewport?.choose(mode);
  }

  function zoom(factor: number) {
    viewMode = "zoom";
    viewport?.zoom(factor);
  }
  let status = $state("Lade H5P …");
  const expiredSessionMessage = "Deine Sitzung ist abgelaufen. Bitte lade die Seite neu und melde dich bei Bedarf erneut an.";

  function toDisplayMessage(error: unknown): string {
    const raw = error instanceof Error ? error.message : String(error || "");
    if (raw === "unauthenticated") {
      return expiredSessionMessage;
    }
    return raw || "H5P konnte nicht geladen werden.";
  }

  function statusTone(message: string): StatusMessageTone {
    if (message.startsWith("Lade")) return "progress";
    if (/^(Bereit|Gespeichert)/.test(message)) return "success";
    if (message.startsWith("Kein H5P-Inhalt")) return "warning";
    return "error";
  }

  function extractScore(statement: unknown): { raw: number; max: number } | null {
    const record = statement as {
      result?: { score?: { raw?: number; max?: number } };
    };
    const raw = Number(record.result?.score?.raw);
    const max = Number(record.result?.score?.max);
    if (!Number.isFinite(raw) || !Number.isFinite(max)) {
      return null;
    }
    const rawInt = Math.max(0, Math.trunc(raw));
    const maxInt = Math.max(0, Math.trunc(max));
    if (rawInt > maxInt) {
      return null;
    }
    return { raw: rawInt, max: maxInt };
  }

  function shouldPersistAttempt(statement: unknown): boolean {
    const record = statement as {
      verb?: { id?: string };
      result?: { completion?: boolean; success?: boolean };
    };
    const verbId = String(record.verb?.id || "");
    return (
      verbId.endsWith("/answered") ||
      verbId.endsWith("/completed") ||
      record.result?.completion === true ||
      record.result?.success === true
    );
  }

  onMount(() => {
    if (!root || !contentId) {
      status = "Kein H5P-Inhalt verknüpft.";
      return;
    }

    let disposed = false;
    const submittedStatementIds = new Set<string>();
    let practiceAttemptLocked = false;
    let player:
      | (HTMLElement & {
          loadContentCallback?: (
            contentIdArg: string,
            contextId?: string,
            _ignoredUserId?: string,
            readOnlyState?: boolean
          ) => Promise<unknown>;
        })
      | undefined;
    let detachPlayerListeners: (() => void) | undefined;

    async function submitAttempt(
      statementId: string,
      scoreRaw: number,
      scoreMax: number
    ): Promise<H5PPersistedResult | null> {
      const safeKey = /^[A-Za-z0-9_-]{1,64}$/.test(statementId)
        ? statementId
        : (crypto.randomUUID?.() || `h5p_${Date.now()}`);
      if (submittedStatementIds.has(safeKey) || (practiceContext && practiceAttemptLocked)) {
        return null;
      }
      submittedStatementIds.add(safeKey);
      if (practiceContext) {
        // One practice presentation represents exactly one spaced-repetition result.
        practiceAttemptLocked = true;
      }

      const target = practiceContext
        ? `/api/learning/practice/sessions/${encodeURIComponent(practiceContext.sessionId)}/items/${encodeURIComponent(practiceContext.itemId)}/attempts`
        : `/bff/h5p/submissions?course_id=${encodeURIComponent(courseId)}&task_id=${encodeURIComponent(taskId)}`;
      try {
        const response = await fetch(target, {
          method: "POST",
          credentials: "include",
          headers: {
            "content-type": "application/json",
            "idempotency-key": safeKey
          },
          body: JSON.stringify(
            practiceContext
              ? {
                  score_raw: scoreRaw,
                  score_max: scoreMax,
                  practice_completion_token: practiceContext.completionToken
                }
              : { kind: "h5p", score_raw: scoreRaw, score_max: scoreMax }
          )
        });

        const payload = (await response.json().catch(() => ({}))) as Record<string, unknown>;
        if (!response.ok) {
          throw new Error(String(payload.detail || payload.error || `HTTP ${response.status}`));
        }
        if (practiceContext) {
          const attemptId = String(payload.attempt_id || "");
          if (!attemptId) {
            throw new Error("Gespeicherte Übungsbearbeitung konnte nicht zugeordnet werden.");
          }
          return {
            kind: "practice",
            attemptId,
            status: String(payload.status || "completed")
          };
        }
        return { kind: "learning", submission: payload as LearningSubmission };
      } catch (error) {
        submittedStatementIds.delete(safeKey);
        if (practiceContext) {
          practiceAttemptLocked = false;
        }
        throw error;
      }
    }

    async function install(): Promise<void> {
      status = "Lade H5P …";
      const wcModule = await loadH5PWebcomponentsModule();
      wcModule.defineElements?.(["h5p-player"]);

      if (disposed || !root) {
        return;
      }

      player = document.createElement("h5p-player") as HTMLElement & {
        loadContentCallback?: (
          contentIdArg: string,
          contextId?: string,
          _ignoredUserId?: string,
          readOnlyState?: boolean
        ) => Promise<unknown>;
      };
      player.id = `h5p-player-${taskId}`;
      player.setAttribute("content-id", contentId);
      player.setAttribute("context-id", practiceContext?.contextId || taskId);
      root.innerHTML = "";
      root.appendChild(player);

      player.loadContentCallback = async (
        contentIdArg: string,
        contextId?: string,
        _ignoredUserId?: string,
        readOnlyState?: boolean
      ) => {
        const url = new URL("/h5p/player/model", window.location.origin);
        url.searchParams.set("content_id", contentIdArg);
        url.searchParams.set("course_id", courseId);
        url.searchParams.set("context_id", practiceContext?.contextId || taskId || contextId || "");
        url.searchParams.set("task_id", taskId);
        if (practiceContext) {
          url.searchParams.set("practice_session_id", practiceContext.sessionId);
          url.searchParams.set("practice_item_id", practiceContext.itemId);
          url.searchParams.set("practice_completion_token", practiceContext.completionToken);
        }
        if (readOnlyState) {
          url.searchParams.set("read_only_state", "true");
        }
        const response = await fetch(url.toString(), { credentials: "include" });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error((payload as { error?: string }).error || `HTTP ${response.status}`);
        }
        return payload;
      };

      const handleXApi = async (event: Event) => {
        try {
          const detail = (event as CustomEvent<{ statement?: unknown }>).detail;
          const statement = detail?.statement;
          if (!statement || !shouldPersistAttempt(statement)) {
            return;
          }
          const score = extractScore(statement);
          if (!score) {
            return;
          }
          const statementId = String((statement as { id?: string }).id || "");
          const result = await submitAttempt(statementId, score.raw, score.max);
          if (!result) {
            return;
          }
          await onProgressPersisted?.(result);
          status = practiceContext
            ? `Gespeichert (${score.raw}/${score.max}). Lies die H5P-Rückmeldung in Ruhe.`
            : `Gespeichert (${score.raw}/${score.max}).`;
        } catch (error) {
          status = toDisplayMessage(error) || "Abgabe fehlgeschlagen.";
        }
      };

      player.addEventListener("xAPI", handleXApi);
      const handleInitialized = () => {
        if (!root || !region || !player?.querySelector(".h5p-dragquestion")) return;
        dragReady = true;
        viewport?.destroy();
        viewport = createReadableViewport(root, region, () => {
          (player as HTMLElement & { resize?: () => void })?.resize?.();
        });
      };
      player.addEventListener("initialized", handleInitialized);
      detachPlayerListeners = () => {
        player?.removeEventListener("xAPI", handleXApi);
        player?.removeEventListener("initialized", handleInitialized);
        viewport?.destroy();
        viewport = undefined;
      };

      status = "Bereit.";
    }

    void install().catch((error: unknown) => {
      status = toDisplayMessage(error);
    });

    return () => {
      disposed = true;
      detachPlayerListeners?.();
      detachPlayerListeners = undefined;
      player = undefined;
      root?.replaceChildren();
    };
  });
</script>

<div class="h5p-task-player">
  {#if dragReady}
    <div class="h5p-view-controls" role="group" aria-label="H5P-Ansicht">
      <button type="button" class="workspace-button workspace-button--ghost" aria-pressed={viewMode === "readable"} onclick={() => chooseView("readable")}>Lesbare Ansicht</button>
      <button type="button" class="workspace-button workspace-button--ghost" aria-pressed={viewMode === "overview"} onclick={() => chooseView("overview")}>Gesamtansicht</button>
      <button type="button" class="workspace-button workspace-button--ghost" onclick={() => zoom(1.25)}>Vergrößern</button>
      <button type="button" class="workspace-button workspace-button--ghost" onclick={() => zoom(0.8)}>Verkleinern</button>
    </div>
    <p class="h5p-view-hint">Die Aufgabenfläche lässt sich seitlich und nach unten scrollen. Die Gesamtansicht zeigt alle Zuordnungen auf einmal.</p>
  {/if}
  <!-- svelte-ignore a11y_no_noninteractive_tabindex (The labeled scroll region must support native keyboard scrolling.) -->
  <div bind:this={region} class="h5p-task-viewport" class:h5p-task-viewport--scrollable={dragReady} role="region" aria-label="H5P-Aufgabenfläche" tabindex={dragReady ? 0 : undefined}>
    <div bind:this={root}></div>
  </div>
  <div class="h5p-status"><StatusMessage tone={statusTone(status)} title={status} dismissible={false} /></div>
</div>
