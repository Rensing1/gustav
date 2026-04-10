<script lang="ts">
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>{data.matrix?.course?.title ?? "Diagnostik"} | GUSTAV</title>
</svelte:head>

<section class="panel">
  <div class="header-row">
    <div>
      <p class="kicker">Diagnostik</p>
      <h2>{data.matrix?.course?.title ?? "Kursmatrix"}</h2>
      <p class="lead">
        Erste kursbezogene Matrix mit klarem Klickschnitt: Namen fuehren zum
        Lernendenprofil, Zellen in den jeweiligen Detailkontext.
      </p>
    </div>
    {#if data.matrix?.course?.href}
      <a class="ghost-link" href={data.matrix.course.href}>Neu laden</a>
    {/if}
  </div>

  {#if data.matrix?.units?.length && data.matrix?.rows?.length}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Lernende</th>
            {#each data.matrix.units as unit}
              <th>{unit.position}. {unit.title}</th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each data.matrix.rows as row}
            <tr>
              <th scope="row">
                <a href={row.student.href}>{row.student.name}</a>
              </th>
              {#each row.cells as cell}
                <td>
                  <a class="cell-link" href={cell.href}>
                    <strong>{cell.submitted_tasks}/{cell.total_tasks}</strong>
                    <span>Aufgaben</span>
                  </a>
                </td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <p class="empty">Noch keine Diagnostikdaten fuer diesen Kurs verfuegbar.</p>
  {/if}
</section>

<style>
  .panel {
    max-width: 78rem;
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

  .kicker {
    margin: 0 0 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #286983;
    font-size: 0.85rem;
  }

  .lead,
  .empty {
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
    margin-top: 1.5rem;
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    min-width: 44rem;
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

  .cell-link {
    display: grid;
    gap: 0.2rem;
    padding: 0.75rem 0.85rem;
    border-radius: 1rem;
    background: linear-gradient(160deg, #faf4ed 0%, #fef6eb 100%);
    border: 1px solid #f2e9e1;
  }

  .cell-link span {
    font-size: 0.85rem;
    color: #797593;
  }
</style>
