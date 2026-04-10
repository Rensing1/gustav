<script lang="ts">
  import type { ConcernBoxCourseOption } from "$lib/types/home";

  export type ConcernBoxComposerValues = {
    courseId: string;
    messageText: string;
    anonymous: boolean;
  };

  let {
    courses,
    values,
    error = null,
    sent = false
  }: {
    courses: ConcernBoxCourseOption[];
    values: ConcernBoxComposerValues;
    error?: string | null;
    sent?: boolean;
  } = $props();
</script>

<section class="concern-box-composer">
  <p class="workspace-label">Rückmeldung</p>
  <p class="workspace-lead">
    Hier kannst du Rückmeldungen und Kritik zur Plattform, zum Unterricht oder zum Lehrer mitteilen. Deine Beiträge bleiben auf Wunsch anonym.
  </p>

  <form method="POST" class="workspace-form">
    <label class="workspace-field">
      <span>Kurs</span>
      <select name="course_id" required value={values.courseId}>
        <option value="">Bitte auswählen</option>
        {#each courses as course}
          <option value={course.id}>{course.title}</option>
        {/each}
      </select>
    </label>

    <label class="workspace-field">
      <span>Beitrag</span>
      <textarea
        aria-label="Beitrag"
        name="message_text"
        rows="8"
        maxlength="4000"
        placeholder="Was sollte besser werden?"
      >{values.messageText}</textarea>
    </label>

    <label class="concern-box-composer__toggle">
      <input
        type="checkbox"
        name="anonymous"
        checked={values.anonymous}
      />
      <span>Anonym bleiben</span>
    </label>

    {#if error}
      <p class="workspace-form-error">{error}</p>
    {/if}

    {#if sent}
      <p class="concern-box-composer__success">Dein Beitrag wurde gesendet.</p>
    {/if}

    <div class="workspace-inline-actions">
      <button class="workspace-button" type="submit">Beitrag senden</button>
    </div>
  </form>
</section>
