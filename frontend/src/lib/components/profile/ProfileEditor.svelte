<script lang="ts">
  import type { AppProfileView } from "$lib/types/profile";

  let {
    profile,
    displayNameError = null,
    nameError = null,
    saved = null,
  }: {
    profile: AppProfileView;
    displayNameError?: string | null;
    nameError?: string | null;
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
        <p class="workspace-form-error">{displayNameError}</p>
      {/if}

      {#if saved === "display-name"}
        <p class="concern-box-composer__success">Der Anzeigename wurde gespeichert.</p>
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
        <p class="workspace-form-error">{nameError}</p>
      {/if}

      {#if saved === "name"}
        <p class="concern-box-composer__success">Vor- und Nachname wurden gespeichert.</p>
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
</section>
