<script lang="ts">
  let { id, message }: { id: string; message: string } = $props();
</script>

<p {id} class="field-error">{message}</p>
