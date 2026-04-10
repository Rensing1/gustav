<script lang="ts">
  import PageActionHead from "$lib/components/ui/PageActionHead.svelte";
  import ProfileEditor from "$lib/components/profile/ProfileEditor.svelte";

  let { data, form } = $props();
</script>

<svelte:head>
  <title>Profil | GUSTAV</title>
</svelte:head>

<div class="profile-page">
  <PageActionHead title={data.pageTitle} copy={data.pageCopy} />

  <ProfileEditor
    profile={data.profile}
    displayNameError={form?.displayName?.error ?? null}
    nameError={form?.name?.error ?? null}
    saved={data.saved}
  />
</div>
