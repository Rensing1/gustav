<script lang="ts">
  import type { TeacherConcernBoxEntry } from "$lib/types/home";

  let { entry }: { entry: TeacherConcernBoxEntry } = $props();

  function formatCreatedAt(value: string): string {
    try {
      return new Intl.DateTimeFormat("de-DE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
        timeZone: "Europe/Berlin"
      }).format(new Date(value));
    } catch {
      return value;
    }
  }
</script>

<li>
  <article class="concern-box-entry">
    <div class="concern-box-entry__copy">
      <strong>{entry.course_title}</strong>
      <p class="workspace-note">{entry.student_name ?? "Anonym"}</p>
      <p>{entry.message_text}</p>
      <span class="concern-box-entry__meta">{formatCreatedAt(entry.created_at)}</span>
    </div>

    <form method="POST" action={entry.archived_at ? "?/restore" : "?/archive"}>
      <input type="hidden" name="entry_id" value={entry.id} />
      <button class="workspace-button workspace-button--ghost" type="submit">
        {entry.archived_at ? "Wiederherstellen" : "Archivieren"}
      </button>
    </form>
  </article>
</li>
