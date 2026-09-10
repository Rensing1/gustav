<script lang="ts">
  import type { PageData } from "./$types";
  let { data }: { data: PageData } = $props();
</script>

<svelte:head><title>{data.matrix?.course?.title ?? "Kursmatrix"} | GUSTAV</title></svelte:head>

<section class="workspace-panel workspace-panel--flat workspace-section diagnostics-panel">
  <div class="workspace-section-header">
    <div class="workspace-section-heading">
      <p class="workspace-kicker">Diagnostik</p>
      <h2>{data.matrix?.course?.title ?? "Kursmatrix"}</h2>
      <p class="workspace-note">Öffne einen Namen für das Lernendenprofil oder einen Aufgabenstand für die Live-Ansicht.</p>
    </div>
    <a class="workspace-link-action" href="/diagnostics">Anderen Kurs wählen</a>
  </div>
  {#if data.matrix?.units?.length && data.matrix?.rows?.length}
    <!-- svelte-ignore a11y_no_noninteractive_tabindex (The native scroll region must be keyboard reachable.) -->
    <div class="workspace-data-table-wrap diagnostics-table" role="region" aria-label="Kursmatrix" tabindex="0">
      <table class="workspace-data-table">
        <thead><tr>
          <th scope="col">Lernende</th>
          {#each data.matrix.units as unit}<th scope="col">{unit.position}. {unit.title}</th>{/each}
        </tr></thead>
        <tbody>
          {#each data.matrix.rows as row}
            <tr>
              <th scope="row"><a href={row.student.href}>{row.student.name}</a></th>
              {#each row.cells as cell}
                <td><a class="diagnostics-cell" href={cell.href}>
                  <strong>{cell.submitted_tasks}/{cell.total_tasks}</strong><span>Aufgaben mit Abgabe</span>
                </a></td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <p class="workspace-empty">Noch keine Diagnostikdaten für diesen Kurs verfügbar.</p>
  {/if}
</section>
