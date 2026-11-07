<!--
  One dimension (categories, payment methods, pets) as an editable list:
  edit a cell to rename, "Add a row" to add, Remove to drop one. Nothing is
  written until Save changes, which first lists exactly what will change in
  sentences (planChanges) and is blocked, with the reason, on blank required
  cells, duplicates or removing a row in use. Deletes go first, then edits,
  then adds, so a rename can free up a name an add reuses.
-->
<script lang="ts" module>
  export interface Column {
    field: string
    label: string
    kind: 'text' | 'select' | 'check'
    options?: string[]
    placeholder?: string
    help?: string
    width?: string
    default?: unknown
  }
</script>

<script lang="ts">
  import { del, patch, post, showToast } from '../../lib/session.svelte'
  import { isEmptyPlan, planChanges, type Row, type Table } from '../../lib/settings'
  import Message from '../../lib/ui/Message.svelte'

  let { original, table, endpoint, columns }: {
    original: Row[]
    table: Table
    endpoint: string
    columns: Column[]
  } = $props()

  type Editable = Row & { _key: number }
  let nextKey = 0
  let rows = $state<Editable[]>([])
  let failures = $state<string[]>([])
  let busy = $state(false)

  const sortKey = (r: Row) => table.fields.slice(0, 2).map((f) => String(r[f] ?? '').toLowerCase()).join('\u0000')

  function reset() {
    rows = [...original].sort((a, b) => sortKey(a).localeCompare(sortKey(b))).map((r) => ({ ...r, _key: nextKey++ }))
  }
  $effect(() => {
    void original
    reset()
  })

  function addRow() {
    const blank: Editable = { [table.key]: null, expense_count: 0, _key: nextKey++ }
    for (const c of columns) blank[c.field] = c.default ?? (c.kind === 'check' ? false : '')
    rows = [...rows, blank]
  }

  function removeRow(key: number) {
    rows = rows.filter((r) => r._key !== key)
  }

  const plan = $derived(planChanges(original, rows.map(({ _key, ...r }) => r), table))
  const dirty = $derived(!isEmptyPlan(plan) || plan.errors.length > 0)

  async function apply() {
    busy = true
    const errs: string[] = []
    const run = async (call: () => Promise<unknown>) => {
      try { await call() } catch (e) { errs.push((e as Error).message) }
    }
    const count = plan.lines.length
    const { deletes, updates, adds } = plan
    for (const id of deletes) await run(() => del(`${endpoint}/${id}`))
    for (const [id, changes] of updates) await run(() => patch(`${endpoint}/${id}`, changes))
    for (const payload of adds) await run(() => post(`${endpoint}/`, payload))
    busy = false
    failures = errs
    if (!errs.length) showToast(`Saved ${count} change${count !== 1 ? 's' : ''}.`)
  }
</script>

<div class="table-wrap">
  <table class="data edit">
    <thead>
      <tr>
        {#each columns as c}<th title={c.help} style:width={c.width}>{c.label}</th>{/each}
        <th class="num" title="How many expenses use it. Rows in use can't be removed.">Used by</th>
        <th><span class="sr-only">Remove</span></th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row (row._key)}
        <tr>
          {#each columns as c}
            <td class:center={c.kind === 'check'}>
              {#if c.kind === 'check'}
                <input type="checkbox" aria-label={c.label} checked={!!row[c.field]}
                  onchange={(e) => (row[c.field] = e.currentTarget.checked)} />
              {:else if c.kind === 'select'}
                <select aria-label={c.label} value={row[c.field] ?? ''} onchange={(e) => (row[c.field] = e.currentTarget.value)}>
                  <option value="" disabled>Pick…</option>
                  {#each c.options ?? [] as o}<option value={o}>{o}</option>{/each}
                </select>
              {:else}
                <input type="text" aria-label={c.label} placeholder={c.placeholder} value={row[c.field] ?? ''}
                  oninput={(e) => (row[c.field] = e.currentTarget.value)} />
              {/if}
            </td>
          {/each}
          <td class="num">{row[table.key] === null ? 'new' : Number(row.expense_count ?? 0)}</td>
          <td>
            <button type="button" class="btn small danger" aria-label="Remove this row"
              title={Number(row.expense_count ?? 0) ? 'In use: removing it will be blocked' : 'Remove'}
              onclick={() => removeRow(row._key)}>✕</button>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>
<div><button type="button" class="btn small" onclick={addRow}>+ Add a row</button></div>

{#if dirty}
  <div class="plan">
    {#if plan.lines.length}
      <b>Will save:</b>
      <ul>{#each plan.lines as line}<li>{line}</li>{/each}</ul>
    {/if}
    {#each plan.errors as e}<Message tone="warn">{e}</Message>{/each}
    <div class="row">
      <button type="button" class="btn primary" disabled={busy || plan.errors.length > 0 || isEmptyPlan(plan)} onclick={apply}>
        Save changes
      </button>
      <button type="button" class="btn" disabled={busy} onclick={() => { reset(); failures = [] }}>Discard</button>
    </div>
  </div>
{/if}
{#if failures.length}
  {#each failures as f}<Message tone="error">{f}</Message>{/each}
  <Message>The other changes were saved.</Message>
{/if}

<style>
  table.edit td { padding: 0.3rem 0.35rem; vertical-align: middle; }
  table.edit input[type='text'], table.edit select { min-height: 2.2rem; padding: 0.3rem 0.5rem; min-width: 7rem; }
  td.center { text-align: center; }
  td.center input { width: 1.1rem; height: 1.1rem; accent-color: var(--brand); }
  .plan { background: var(--brand-soft); border-radius: var(--radius); padding: 0.8rem 1rem; display: flex;
    flex-direction: column; gap: 0.5rem; }
  .plan ul { margin: 0; padding-left: 1.1rem; }
</style>
