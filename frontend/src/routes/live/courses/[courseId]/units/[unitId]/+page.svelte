<script lang="ts">
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();

  const renderCellLabel = (submitted: boolean, averageScore: number | null | undefined) => {
    if (!submitted) {
      return "Offen";
    }
    if (typeof averageScore === "number") {
      return `Ø ${averageScore.toFixed(1)}`;
    }
    return "Eingereicht";
  };
</script>

<svelte:head>
  <title>{data.matrix?.unit?.title ?? "Live"} | GUSTAV</title>
</svelte:head>

<section class="panel">
  <div class="header-row">
    <div>
      <p class="kicker">Live</p>
      <h2>{data.matrix?.unit?.title ?? "Lerneinheit"}</h2>
      <p class="lead">
        Die Unterrichtsmatrix ist jetzt ein SvelteKit-Raum mit explizitem
        Read-Model statt einer HTMX-SSR-Strecke.
      </p>
    </div>
    {#if data.matrix?.course}
      <a class="ghost-link" href={data.matrix.course.href}>Zur Kursauswahl</a>
    {/if}
  </div>

  {#if data.matrix?.tasks?.length && data.matrix?.rows?.length}
    <div class="workspace">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Lernende</th>
              {#each data.matrix.tasks as task}
                <th>{task.position}. Aufgabe</th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each data.matrix.rows as row}
              <tr>
                <th scope="row">
                  <a href={row.student.href}>{row.student.name}</a>
                </th>
                {#each row.tasks as cell}
                  <td>
                    <a
                      class:cell-link={true}
                      class:is-active={data.studentSub === row.student.sub && data.taskId === cell.task_id}
                      href={cell.href}
                    >
                      <strong>{renderCellLabel(cell.has_submission, cell.average_score)}</strong>
                      <span>{cell.has_submission ? "Detail öffnen" : "Noch keine Abgabe"}</span>
                    </a>
                  </td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <aside class="detail-card">
        {#if data.detail}
          <p class="detail-kicker">Detail-Sheet</p>
          <h3>{data.detail.student.name}</h3>
          <p class="meta">Task: {data.detail.task.id}</p>

          {#if data.detail.submission}
            <article class="submission-card">
              <h4>Aufgabenstellung</h4>
              <pre>{data.detail.submission.instruction_md}</pre>

              {#if data.detail.submission.text_body}
                <h4>Einreichung</h4>
                <pre>{data.detail.submission.text_body}</pre>
              {/if}

              {#if data.detail.submission.feedback_md}
                <h4>Feedback</h4>
                <pre>{data.detail.submission.feedback_md}</pre>
              {/if}

              {#if data.detail.submission.files?.length}
                <h4>Dateien</h4>
                <ul>
                  {#each data.detail.submission.files as file}
                    <li>
                      <a href={file.url}>{file.mime ?? "Datei"} {#if file.size}({file.size} B){/if}</a>
                    </li>
                  {/each}
                </ul>
              {/if}
            </article>
          {:else}
            <p class="empty">Für diese Auswahl liegt noch keine Einreichung vor.</p>
          {/if}
        {:else}
          <p class="detail-kicker">Detail-Sheet</p>
          <h3>Keine Zelle ausgewählt</h3>
          <p class="empty">
            Wähle eine Matrixzelle aus, um die letzte Einreichung im Detailblatt
            zu sehen.
          </p>
        {/if}
      </aside>
    </div>
  {:else}
    <p class="empty">Noch keine Live-Daten für diese Lerneinheit verfügbar.</p>
  {/if}
</section>

<style>
  .panel {
    max-width: 86rem;
    background: rgba(255, 250, 243, 0.92);
    border: 1px solid #f2e9e1;
    border-radius: 1.5rem;
    padding: clamp(1.25rem, 3vw, 2rem);
    box-shadow: 0 1.5rem 3rem rgba(87, 82, 121, 0.08);
  }

  .header-row {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: start;
    flex-wrap: wrap;
  }

  .workspace {
    display: grid;
    grid-template-columns: minmax(0, 1.65fr) minmax(18rem, 26rem);
    gap: 1rem;
    margin-top: 1.5rem;
  }

  .kicker,
  .detail-kicker {
    margin: 0 0 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #286983;
    font-size: 0.85rem;
  }

  .lead,
  .empty,
  .meta {
    color: #5f5a79;
  }

  .ghost-link {
    align-self: start;
    text-decoration: none;
    color: #286983;
    border: 1px solid #cfe0e7;
    border-radius: 999px;
    padding: 0.6rem 0.9rem;
    background: rgba(255, 255, 255, 0.7);
  }

  .table-wrap {
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    min-width: 38rem;
  }

  th,
  td {
    padding: 0.8rem;
    border-bottom: 1px solid #ece2d8;
    text-align: left;
    vertical-align: top;
  }

  thead th {
    color: #286983;
    font-size: 0.9rem;
  }

  tbody th a,
  .cell-link {
    color: inherit;
    text-decoration: none;
  }

  .cell-link,
  .detail-card,
  .submission-card {
    display: grid;
    gap: 0.25rem;
    padding: 0.85rem;
    border-radius: 1rem;
    background: linear-gradient(160deg, #faf4ed 0%, #fef6eb 100%);
    border: 1px solid #f2e9e1;
  }

  .cell-link.is-active {
    border-color: #286983;
    box-shadow: 0 0 0 2px rgba(40, 105, 131, 0.12);
  }

  .cell-link span {
    font-size: 0.85rem;
    color: #797593;
  }

  .detail-card h3,
  .submission-card h4 {
    margin-bottom: 0;
  }

  pre {
    white-space: pre-wrap;
    margin: 0;
    font: inherit;
  }

  .submission-card ul {
    margin: 0;
    padding-left: 1rem;
  }

  @media (max-width: 960px) {
    .workspace {
      grid-template-columns: 1fr;
    }
  }
</style>
