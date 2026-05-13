<script lang="ts">
  import PageActionHead from "$lib/components/ui/PageActionHead.svelte";
  import ProfileEditor from "$lib/components/profile/ProfileEditor.svelte";

  let { data, form } = $props();

  function createdCliToken(): string | null {
    const result = form?.createCliToken;
    return result && "token" in result ? result.token : null;
  }

  function createCliTokenError(): string | null {
    const result = form?.createCliToken;
    return result && "error" in result ? result.error : null;
  }
</script>

<svelte:head>
  <title>Profil | GUSTAV</title>
</svelte:head>

<div class="profile-page">
  <PageActionHead title={data.pageTitle} copy={data.pageCopy} />

  <ProfileEditor
    profile={data.profile}
    cliTokens={data.cliTokens}
    createdCliToken={createdCliToken()}
    displayNameError={form?.displayName?.error ?? null}
    nameError={form?.name?.error ?? null}
    cliTokenError={createCliTokenError() ?? form?.revokeCliToken?.error ?? null}
    saved={data.saved}
  />
</div>
