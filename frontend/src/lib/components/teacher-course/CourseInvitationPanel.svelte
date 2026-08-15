<script lang="ts">
  import { onMount, tick } from "svelte";
  import QRCode from "qrcode";

  export type CourseInvitation = {
    id: string;
    course_id: string;
    invite_url: string;
    expires_at: string;
    created_at: string;
    redemption_count: number;
    email_status: { pending: number; sent: number; failed: number };
  };

  let {
    courseId,
    courseTitle,
    invitation = null,
    failedRecipients = []
  }: {
    courseId: string;
    courseTitle: string;
    invitation?: CourseInvitation | null;
    failedRecipients?: string[];
  } = $props();

  let canvas = $state<HTMLCanvasElement>();
  let fullscreenHost = $state<HTMLElement>();
  let fullscreenTrigger = $state<HTMLButtonElement>();
  let fullscreenCloseButton = $state<HTMLButtonElement>();
  let fullscreenOpen = $state(false);
  let fallbackFullscreen = $state(false);
  let copied = $state(false);
  let now = $state(Date.now());
  let fullscreenHistoryEntryActive = false;
  let inertBackground: Array<{ element: HTMLElement; wasInert: boolean }> = [];

  const expiresAt = $derived(invitation ? new Date(invitation.expires_at) : null);
  const expiryText = $derived(expiresAt
    ? new Intl.DateTimeFormat("de-DE", {
        dateStyle: "medium",
        timeStyle: "short"
      }).format(expiresAt)
    : "");
  const remainingText = $derived.by(() => {
    if (!expiresAt) return "";
    const minutes = Math.max(0, Math.ceil((expiresAt.getTime() - now) / 60_000));
    const hours = Math.floor(minutes / 60);
    const rest = minutes % 60;
    if (hours >= 1) return `noch ${hours} Std. ${rest} Min.`;
    return `noch ${rest} Min.`;
  });

  async function renderQr(): Promise<void> {
    if (!canvas || !invitation) return;
    await QRCode.toCanvas(canvas, invitation.invite_url, {
      errorCorrectionLevel: "H",
      margin: 4,
      width: 1024,
      color: { dark: "#000000", light: "#ffffff" }
    });
  }

  function restoreTriggerFocus(): void {
    void tick().then(() => fullscreenTrigger?.focus());
  }

  function isolateFallbackBackground(): void {
    restoreFallbackBackground();
    let current = fullscreenHost;
    while (current?.parentElement) {
      const parent = current.parentElement;
      for (const sibling of parent.children) {
        if (sibling === current || !(sibling instanceof HTMLElement)) continue;
        inertBackground.push({ element: sibling, wasInert: sibling.inert === true });
        sibling.inert = true;
      }
      current = parent;
      if (parent === document.body) break;
    }
  }

  function restoreFallbackBackground(): void {
    for (const { element, wasInert } of inertBackground) {
      element.inert = wasInert;
    }
    inertBackground = [];
  }

  async function focusFullscreenClose(): Promise<void> {
    await tick();
    fullscreenCloseButton?.focus();
  }

  async function closeFullscreen(
    exitNative = true,
    consumeHistoryEntry = true
  ): Promise<void> {
    if (!fullscreenOpen) return;
    fullscreenOpen = false;
    fallbackFullscreen = false;
    restoreFallbackBackground();
    if (exitNative && document.fullscreenElement && document.exitFullscreen) {
      await document.exitFullscreen().catch(() => undefined);
    }
    if (consumeHistoryEntry && fullscreenHistoryEntryActive) {
      fullscreenHistoryEntryActive = false;
      history.back();
    }
    restoreTriggerFocus();
  }

  async function openFullscreen(): Promise<void> {
    if (fullscreenOpen) return;
    fullscreenOpen = true;
    fallbackFullscreen = false;
    history.pushState({ ...history.state, courseInviteFullscreen: true }, "");
    fullscreenHistoryEntryActive = true;
    await tick();
    try {
      if (!fullscreenHost?.requestFullscreen) throw new Error("fullscreen_not_supported");
      await fullscreenHost.requestFullscreen();
    } catch {
      fallbackFullscreen = true;
      isolateFallbackBackground();
    }
    await focusFullscreenClose();
    await renderQr();
  }

  async function copyLink(): Promise<void> {
    if (!invitation) return;
    await navigator.clipboard.writeText(invitation.invite_url);
    copied = true;
    window.setTimeout(() => (copied = false), 2000);
  }

  async function downloadQr(): Promise<void> {
    if (!invitation) return;
    const dataUrl = await QRCode.toDataURL(invitation.invite_url, {
      errorCorrectionLevel: "H",
      margin: 4,
      width: 1600,
      color: { dark: "#000000", light: "#ffffff" }
    });
    const link = document.createElement("a");
    link.href = dataUrl;
    link.download = `gustav-kurseinladung-${courseId}.png`;
    link.click();
  }

  $effect(() => {
    invitation?.invite_url;
    void renderQr();
  });

  onMount(() => {
    const clock = window.setInterval(() => (now = Date.now()), 60_000);
    const resize = () => void renderQr();
    const keydown = (event: KeyboardEvent) => {
      if (!fullscreenOpen) return;
      if (event.key === "Escape") {
        event.preventDefault();
        void closeFullscreen();
      } else if (event.key === "Tab") {
        // The isolated view has exactly one action, so keep focus on it.
        event.preventDefault();
        fullscreenCloseButton?.focus();
      }
    };
    const fullscreenChange = () => {
      if (fullscreenOpen && !fallbackFullscreen && !document.fullscreenElement) {
        void closeFullscreen(false);
      }
    };
    const popstate = () => {
      if (fullscreenOpen) {
        fullscreenHistoryEntryActive = false;
        void closeFullscreen(true, false);
      }
    };
    window.addEventListener("resize", resize);
    window.addEventListener("orientationchange", resize);
    window.addEventListener("keydown", keydown);
    window.addEventListener("popstate", popstate);
    document.addEventListener("fullscreenchange", fullscreenChange);
    return () => {
      window.clearInterval(clock);
      window.removeEventListener("resize", resize);
      window.removeEventListener("orientationchange", resize);
      window.removeEventListener("keydown", keydown);
      window.removeEventListener("popstate", popstate);
      document.removeEventListener("fullscreenchange", fullscreenChange);
      restoreFallbackBackground();
    };
  });
</script>

<section class="course-invite-panel" aria-labelledby="course-invite-heading">
  <div>
    <p class="workspace-modal-eyebrow">Selbstständiger Kursbeitritt</p>
    <h3 id="course-invite-heading">Klasse einladen</h3>
    <p class="workspace-note">Der gemeinsame Link ist 24 Stunden gültig und kann jederzeit widerrufen werden.</p>
  </div>

  {#if invitation}
    <section
      bind:this={fullscreenHost}
      class:course-invite-fullscreen--open={fullscreenOpen}
      class:course-invite-fullscreen--fallback={fullscreenOpen && fallbackFullscreen}
      class="course-invite-fullscreen"
      role={fullscreenOpen ? "dialog" : undefined}
      aria-modal={fullscreenOpen ? "true" : undefined}
      aria-label={fullscreenOpen ? "QR-Code im Vollbild" : undefined}
    >
      <h2>{courseTitle}</h2>
      <div class="course-invite-qr" aria-label="QR-Code mit Klassenlink">
        <canvas bind:this={canvas}></canvas>
      </div>
      <p>Gültig bis {expiryText} · {remainingText}</p>
      {#if fullscreenOpen}
        <button
          bind:this={fullscreenCloseButton}
          class="course-invite-close"
          type="button"
          onclick={() => void closeFullscreen()}
        >
          Vollbild schließen
        </button>
      {/if}
    </section>

    <label class="workspace-field">
      <span>Klassenlink</span>
      <input type="text" value={invitation.invite_url} readonly />
    </label>

    <div class="workspace-inline-actions">
      <button class="workspace-link-action" type="button" onclick={() => void copyLink()}>
        {copied ? "Link kopiert" : "Link kopieren"}
      </button>
      <button class="workspace-link-action" type="button" onclick={() => void downloadQr()}>
        QR-Code herunterladen
      </button>
      <button
        bind:this={fullscreenTrigger}
        class="workspace-link-action"
        type="button"
        onclick={() => void openFullscreen()}
      >
        Im Vollbild anzeigen
      </button>
    </div>

    <p class="workspace-note">{invitation.redemption_count} {invitation.redemption_count === 1 ? "Einlösung" : "Einlösungen"}</p>

    <form method="POST" action="?/sendInvitationEmails" class="workspace-form">
      <input name="invitation_id" type="hidden" value={invitation.id} />
      <label class="workspace-field">
        <span>Schul-E-Mail-Adressen</span>
        <textarea name="recipients" rows="5" placeholder="name@schule.example&#10;weitere@schule.example" required></textarea>
        <small>Trenne Adressen durch Zeilenumbrüche, Kommas oder Semikolons. Maximal 100.</small>
      </label>
      <button class="workspace-link-action" type="submit">Einladungen senden</button>
    </form>

    <section class="course-invite-status" aria-label="Versandstatus">
      <p>{invitation.email_status.pending} ausstehend · {invitation.email_status.sent} gesendet · {invitation.email_status.failed} fehlgeschlagen</p>
      {#if failedRecipients.length}
        <ul>
          {#each failedRecipients as recipient}<li>{recipient}</li>{/each}
        </ul>
        <form method="POST" action="?/retryInvitationEmails">
          <input name="invitation_id" type="hidden" value={invitation.id} />
          <button class="workspace-link-action" type="submit">Fehlgeschlagene erneut senden</button>
        </form>
      {/if}
    </section>

    <div class="workspace-inline-actions course-invite-danger-actions">
      <form method="POST" action="?/createInvitation">
        <button class="workspace-text-button" type="submit">Neuen Link erzeugen</button>
      </form>
      <form method="POST" action="?/revokeInvitation">
        <input name="invitation_id" type="hidden" value={invitation.id} />
        <button class="workspace-text-button workspace-text-button--danger" type="submit">Link widerrufen</button>
      </form>
    </div>
  {:else}
    <p class="workspace-empty">Für diesen Kurs ist derzeit kein gültiger Klassenlink aktiv.</p>
    <form method="POST" action="?/createInvitation">
      <button class="workspace-link-action" type="submit">Klassenlink erstellen</button>
    </form>
  {/if}
</section>

<style>
  .course-invite-panel { display: grid; gap: 1.25rem; }
  .course-invite-panel h3 { margin: 0; }
  .course-invite-fullscreen {
    align-items: center;
    background: #fff;
    color: #000;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    justify-content: center;
    padding: 1.25rem;
    text-align: center;
  }
  .course-invite-fullscreen h2,
  .course-invite-fullscreen p { color: #000; margin: 0; }
  .course-invite-qr { background: #fff; padding: 0.5rem; }
  .course-invite-qr canvas { display: block; height: min(18rem, 60vw); width: min(18rem, 60vw); }
  .course-invite-fullscreen--open,
  .course-invite-fullscreen:fullscreen {
    background: #fff;
    box-sizing: border-box;
    height: 100%;
    inset: 0;
    padding: max(1rem, 3vmin);
    width: 100%;
    z-index: 10000;
  }
  .course-invite-fullscreen--fallback { position: fixed; }
  .course-invite-fullscreen--open .course-invite-qr canvas,
  .course-invite-fullscreen:fullscreen .course-invite-qr canvas {
    height: min(70vmin, 72rem);
    width: min(70vmin, 72rem);
  }
  .course-invite-close {
    background: #111;
    border: 0;
    border-radius: 999px;
    color: #fff;
    cursor: pointer;
    font: inherit;
    font-weight: 700;
    padding: 0.75rem 1.25rem;
  }
  .course-invite-status { border-block: 1px solid var(--color-border, #d5d5d5); padding-block: 1rem; }
  .course-invite-status p { margin: 0 0 0.5rem; }
  .course-invite-danger-actions { justify-content: space-between; }
  textarea { resize: vertical; }
</style>
