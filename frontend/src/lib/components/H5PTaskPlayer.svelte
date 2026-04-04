<script lang="ts">
  import { onMount } from "svelte";

  let {
    courseId,
    taskId,
    contentId
  }: {
    courseId: string;
    taskId: string;
    contentId: string;
  } = $props();

  let root: HTMLDivElement | undefined;
  let status = $state("Lade H5P …");
  const h5pWebcomponentsEntry = "/h5p/webcomponents/index.js";

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
      status = "Kein H5P-Inhalt verknuepft.";
      return;
    }

    let disposed = false;
    const submittedStatementIds = new Set<string>();

    async function submitAttempt(statementId: string, scoreRaw: number, scoreMax: number): Promise<void> {
      const safeKey = /^[A-Za-z0-9_-]{1,64}$/.test(statementId)
        ? statementId
        : (crypto.randomUUID?.() || `h5p_${Date.now()}`);
      if (submittedStatementIds.has(safeKey)) {
        return;
      }
      submittedStatementIds.add(safeKey);

      const response = await fetch(
        `/bff/h5p/submissions?course_id=${encodeURIComponent(courseId)}&task_id=${encodeURIComponent(taskId)}`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "content-type": "application/json",
            "idempotency-key": safeKey
          },
          body: JSON.stringify({ kind: "h5p", score_raw: scoreRaw, score_max: scoreMax })
        }
      );

      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string; error?: string };
        throw new Error(payload.detail || payload.error || `HTTP ${response.status}`);
      }
    }

    async function install(): Promise<void> {
      status = "Lade H5P …";
      // Vite must not try to bundle this module because the H5P sidecar serves it at runtime.
      const wcModule = (await import(/* @vite-ignore */ h5pWebcomponentsEntry)) as {
        defineElements?: (names: string[]) => void;
      };
      wcModule.defineElements?.(["h5p-player"]);

      if (disposed || !root) {
        return;
      }

      const player = document.createElement("h5p-player") as HTMLElement & {
        loadContentCallback?: (
          contentIdArg: string,
          contextId?: string,
          _ignoredUserId?: string,
          readOnlyState?: boolean
        ) => Promise<unknown>;
      };
      player.id = `h5p-player-${taskId}`;
      player.setAttribute("content-id", contentId);
      player.setAttribute("context-id", taskId);
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
        url.searchParams.set("context_id", taskId || contextId || "");
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

      player.addEventListener("xAPI", async (event: Event) => {
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
          await submitAttempt(statementId, score.raw, score.max);
          status = `Gespeichert (${score.raw}/${score.max}).`;
        } catch (error) {
          status = error instanceof Error ? error.message : "Abgabe fehlgeschlagen.";
        }
      });

      status = "Bereit.";
    }

    void install().catch((error: unknown) => {
      status = error instanceof Error ? error.message : "H5P konnte nicht geladen werden.";
    });

    return () => {
      disposed = true;
    };
  });
</script>

<div class="h5p-task-player">
  <div bind:this={root}></div>
  <p class="h5p-status">{status}</p>
</div>
