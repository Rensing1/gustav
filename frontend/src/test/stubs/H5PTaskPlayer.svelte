<script lang="ts">
  let {
    courseId = "",
    taskId = "",
    contentId = ""
  }: {
    courseId?: string;
    taskId?: string;
    contentId?: string;
  } = $props();
</script>

<div data-testid="h5p-task-player-stub">
  {courseId}:{taskId}:{contentId}
</div>
