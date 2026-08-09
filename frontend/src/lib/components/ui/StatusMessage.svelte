<script lang="ts">
  import { onMount } from "svelte";

  import { focusActionError } from "./status-message-focus";

  export type StatusMessageTone = "success" | "error" | "warning" | "info" | "progress";
  export type StatusMessageAnnouncement = "polite" | "assertive" | "off";

  let {
    tone,
    title,
    description = null,
    actionLabel = null,
    onAction = null,
    onDismiss = null,
    dismissible,
    autoDismissMs,
    announcement,
    focusOnMount = false,
    invalidField = null
  }: {
    tone: StatusMessageTone;
    title: string;
    description?: string | null;
    actionLabel?: string | null;
    onAction?: (() => void) | null;
    onDismiss?: (() => void) | null;
    dismissible?: boolean;
    autoDismissMs?: number | null;
    announcement?: StatusMessageAnnouncement;
    focusOnMount?: boolean;
    invalidField?: HTMLElement | null;
  } = $props();

  let root = $state<HTMLElement | null>(null);
  let visible = $state(true);
  let mounted = false;
  let hovered = false;
  let focusWithin = false;
  let remainingMs = 0;
  let startedAt = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let timerSignature = "";

  const effectiveAnnouncement = $derived<StatusMessageAnnouncement>(
    announcement ?? (tone === "error" ? "assertive" : "polite")
  );
  const role = $derived(effectiveAnnouncement === "off" ? undefined : effectiveAnnouncement === "assertive" ? "alert" : "status");
  const effectiveAutoDismissMs = $derived(autoDismissMs === undefined ? (tone === "success" ? 6_000 : null) : autoDismissMs);
  const canDismiss = $derived(dismissible ?? tone === "error");

  function clearTimer(): void {
    if (timer !== null) {
      clearTimeout(timer);
      timer = null;
    }
  }

  function isPaused(): boolean {
    return hovered || focusWithin || document.hidden;
  }

  function dismiss(): void {
    clearTimer();
    visible = false;
    onDismiss?.();
  }

  function pauseTimer(): void {
    if (timer === null) {
      return;
    }
    remainingMs = Math.max(0, remainingMs - (Date.now() - startedAt));
    clearTimer();
  }

  function resumeTimer(): void {
    if (!mounted || !visible || effectiveAutoDismissMs === null || isPaused() || timer !== null) {
      return;
    }
    if (remainingMs <= 0) {
      dismiss();
      return;
    }
    startedAt = Date.now();
    timer = setTimeout(dismiss, remainingMs);
  }

  function resetTimer(): void {
    clearTimer();
    visible = true;
    remainingMs = effectiveAutoDismissMs ?? 0;
    resumeTimer();
  }

  function handleVisibilityChange(): void {
    if (document.hidden) {
      pauseTimer();
    } else {
      resumeTimer();
    }
  }

  function handleMouseEnter(): void {
    hovered = true;
    pauseTimer();
  }

  function handleMouseLeave(): void {
    hovered = false;
    resumeTimer();
  }

  function handleFocusIn(): void {
    focusWithin = true;
    pauseTimer();
  }

  function handleFocusOut(event: FocusEvent): void {
    if (event.relatedTarget instanceof Node && root?.contains(event.relatedTarget)) {
      return;
    }
    focusWithin = false;
    resumeTimer();
  }

  $effect(() => {
    const nextSignature = `${tone}:${title}:${effectiveAutoDismissMs ?? "persistent"}`;
    if (!mounted || timerSignature === nextSignature) {
      return;
    }
    timerSignature = nextSignature;
    resetTimer();
  });

  onMount(() => {
    mounted = true;
    timerSignature = `${tone}:${title}:${effectiveAutoDismissMs ?? "persistent"}`;
    document.addEventListener("visibilitychange", handleVisibilityChange);
    resetTimer();
    if (focusOnMount && tone === "error" && root) {
      focusActionError(root, invalidField);
    }

    return () => {
      mounted = false;
      clearTimer();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  });
</script>

{#if visible}
  <section
    bind:this={root}
    class={`status-message status-message--${tone}`}
    {role}
    aria-live={effectiveAnnouncement === "off" ? undefined : effectiveAnnouncement}
    aria-atomic="true"
    aria-busy={tone === "progress" ? "true" : undefined}
    tabindex="-1"
    onmouseenter={handleMouseEnter}
    onmouseleave={handleMouseLeave}
    onfocusin={handleFocusIn}
    onfocusout={handleFocusOut}
  >
    <span class:status-message__icon--progress={tone === "progress"} class="status-message__icon" aria-hidden="true">
      {#if tone === "success"}
        <svg viewBox="0 0 24 24"><path d="m5 12 4 4L19 6" /></svg>
      {:else if tone === "error"}
        <svg viewBox="0 0 24 24"><path d="M12 8v5m0 3.5v.5M12 3 2.8 20h18.4L12 3Z" /></svg>
      {:else if tone === "warning"}
        <svg viewBox="0 0 24 24"><path d="M12 8v5m0 3.5v.5M12 3 2.8 20h18.4L12 3Z" /></svg>
      {:else if tone === "progress"}
        <svg viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-8-8" /></svg>
      {:else}
        <svg viewBox="0 0 24 24"><path d="M12 10v7m0-10V6m9 6a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" /></svg>
      {/if}
    </span>

    <div class="status-message__copy">
      <strong class="status-message__title">{title}</strong>
      {#if description}<p class="status-message__description">{description}</p>{/if}
    </div>

    {#if actionLabel && onAction}
      <button class="status-message__action" type="button" onclick={onAction}>{actionLabel}</button>
    {/if}

    {#if canDismiss}
      <button class="status-message__dismiss" type="button" aria-label="Meldung schließen" onclick={dismiss}>×</button>
    {/if}
  </section>
{/if}
