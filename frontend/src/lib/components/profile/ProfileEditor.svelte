<script lang="ts">
  import type { AppProfileCliToken, AppProfileView } from "$lib/types/profile";
  import StatusMessage from "$lib/components/ui/StatusMessage.svelte";

  let {
    profile,
    cliTokens = [],
    createdCliToken = null,
    displayNameError = null,
    nameError = null,
    cliTokenError = null,
    saved = null,
  }: {
    profile: AppProfileView;
    cliTokens?: AppProfileCliToken[];
    createdCliToken?: string | null;
    displayNameError?: string | null;
    nameError?: string | null;
    cliTokenError?: string | null;
    saved?: string | null;
  } = $props();

  function formatLockTimestamp(value: string | null): string {
    if (!value) {
      return "";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return new Intl.DateTimeFormat("de-DE", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Europe/Berlin"
    }).format(date);
  }

  function formatDateTime(value: string | null): string {
    if (!value) {
      return "Nie";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return new Intl.DateTimeFormat("de-DE", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Europe/Berlin"
    }).format(date);
  }
</script>

<section class="profile-editor">
  <section class="profile-editor__section">
    <p class="workspace-label">Profil</p>
    <form method="POST" action="?/displayName" class="workspace-form">
      <label class="workspace-field">
        <span>Anzeigename</span>
        <input name="display_name" type="text" value={profile.display_name} maxlength="80" required />
      </label>

      {#if displayNameError}
        <StatusMessage tone="error" title="Anzeigename nicht gespeichert" description={displayNameError} focusOnMount={true} />
      {/if}

      {#if saved === "display-name"}
        <StatusMessage tone="success" title="Der Anzeigename wurde gespeichert." />
      {/if}

      <div class="workspace-inline-actions">
        <button class="workspace-button" type="submit">Anzeigename speichern</button>
      </div>
    </form>
  </section>

  <section class="profile-editor__section">
    <p class="workspace-label">Name</p>
    <form method="POST" action="?/name" class="workspace-form">
      <div class="profile-editor__grid">
        <label class="workspace-field">
          <span>Vorname</span>
          <input
            name="first_name"
            type="text"
            value={profile.first_name}
            maxlength="80"
            required={!profile.last_name}
            disabled={!profile.name_can_edit}
          />
        </label>

        <label class="workspace-field">
          <span>Nachname</span>
          <input
            name="last_name"
            type="text"
            value={profile.last_name}
            maxlength="80"
            required={!profile.first_name}
            disabled={!profile.name_can_edit}
          />
        </label>
      </div>

      {#if !profile.name_can_edit && profile.name_locked_until}
        <p class="workspace-note">Vor- und Nachname können wieder ab {formatLockTimestamp(profile.name_locked_until)} geändert werden.</p>
      {/if}

      {#if nameError}
        <StatusMessage tone="error" title="Name nicht gespeichert" description={nameError} focusOnMount={true} />
      {/if}

      {#if saved === "name"}
        <StatusMessage tone="success" title="Vor- und Nachname wurden gespeichert." />
      {/if}

      <div class="workspace-inline-actions">
        <button class="workspace-button" type="submit" disabled={!profile.name_can_edit}>Vor- und Nachname speichern</button>
      </div>
    </form>
  </section>

  <section class="profile-editor__section">
    <p class="workspace-label">Konto</p>
    <div class="workspace-form">
      <label class="workspace-field">
        <span>E-Mail</span>
        <input type="email" value={profile.email} disabled />
      </label>

      <div class="workspace-inline-actions">
        <a class="workspace-button" href={profile.password_change_href}>Passwort ändern</a>
      </div>
    </div>
  </section>

  {#if profile.user.roles.includes("teacher")}
    <section class="profile-editor__section">
      <p class="workspace-label">CLI-Tokens</p>

      {#if createdCliToken}
        <div class="workspace-form">
          <StatusMessage tone="warning" title="Token jetzt sicher kopieren" description="Dieses Token wird nur jetzt angezeigt." announcement="off" dismissible={false} />
          <code>{createdCliToken}</code>
        </div>
      {/if}

      <form method="POST" action="?/createCliToken" class="workspace-form">
        <label class="workspace-field">
          <span>Tokenname</span>
          <input name="label" type="text" maxlength="80" required />
        </label>

        <div class="profile-editor__grid">
          <label class="workspace-field">
            <span>read</span>
            <input name="scopes" type="checkbox" value="read" checked />
          </label>
          <label class="workspace-field">
            <span>write</span>
            <input name="scopes" type="checkbox" value="write" />
          </label>
          <label class="workspace-field">
            <span>delete</span>
            <input name="scopes" type="checkbox" value="delete" />
          </label>
        </div>

        {#if cliTokenError}
          <StatusMessage tone="error" title="CLI-Token nicht geändert" description={cliTokenError} focusOnMount={true} />
        {/if}

        {#if saved === "cli-token-revoked"}
          <StatusMessage tone="success" title="Das CLI-Token wurde widerrufen." />
        {/if}

        <div class="workspace-inline-actions">
          <button class="workspace-button" type="submit">CLI-Token erstellen</button>
        </div>
      </form>

      <div class="workspace-form">
        {#if cliTokens.length === 0}
          <p class="workspace-note">Es gibt noch keine CLI-Tokens.</p>
        {:else}
          {#each cliTokens as token}
            <form method="POST" action="?/revokeCliToken" class="workspace-inline-actions">
              <input type="hidden" name="token_id" value={token.id} />
              <span>{token.label}</span>
              <span>{token.scopes.join(", ")}</span>
              <span>Ablauf: {formatDateTime(token.expires_at)}</span>
              <span>Letzte Nutzung: {formatDateTime(token.last_used_at)}</span>
              {#if token.revoked_at}
                <span>Widerrufen: {formatDateTime(token.revoked_at)}</span>
              {:else}
                <button class="workspace-button" type="submit">CLI-Token widerrufen</button>
              {/if}
            </form>
          {/each}
        {/if}
      </div>
    </section>
  {/if}
</section>
