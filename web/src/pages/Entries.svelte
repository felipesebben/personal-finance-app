<!--
  Entries: every expense you can see (yours, plus the shared ones), to audit
  what was logged and fix it. Filter the list, pick a row, and the same form
  as Add expense opens with that expense filled in: Save changes edits it
  (PATCH, which leaves a trace of who changed it and when), or delete it.
  Shaping lives in lib/entries.ts, the form in sections/EntryForm.svelte.
  A table on a wide screen, a list of compact cards on a phone.
-->
<script lang="ts">
  import { tick } from 'svelte'
  import { del, get, session, showToast } from '../lib/session.svelte'
  import { href } from '../lib/router.svelte'
  import { monthLabel, thisMonth } from '../lib/dates'
  import { cents, formatBrl } from '../lib/money'
  import { KINDS, entryRows, filterEntries, summary, traceText, whatText, type Expense } from '../lib/entries'
  import PageHeader from '../lib/ui/PageHeader.svelte'
  import Card from '../lib/ui/Card.svelte'
  import Message from '../lib/ui/Message.svelte'
  import Loading from '../lib/ui/Loading.svelte'
  import EntryForm from '../sections/EntryForm.svelte'

  let expenses = $state<Expense[] | null>(null)
  let error = $state('')

  let month = $state<string>(thisMonth())
  let kind = $state('all')
  let loggedBy = $state('')
  let categories = $state<string[]>([])
  let search = $state('')
  let selectedId = $state<number | null>(null)
  let confirmDelete = $state(false)
  let deleting = $state(false)
  let editCard = $state<HTMLElement | null>(null)

  $effect(() => {
    void session.version
    get<Expense[]>('expenditures/')
      .then((e) => (expenses = e))
      .catch((e) => (error = e instanceof Error ? e.message : 'Could not load the entries.'))
  })

  const rows = $derived(entryRows(expenses))
  const byId = $derived(new Map((expenses ?? []).map((e) => [e.expenditure_id, e])))
  const months = $derived([...new Set([...rows.map((r) => r.month), thisMonth()])].sort().reverse())
  const people = $derived([...new Set(rows.map((r) => r.loggedBy))].sort())
  const primaries = $derived([...new Set(rows.map((r) => r.primary))].sort())
  const shown = $derived(filterEntries(rows, { month: month || null, kind, loggedBy: loggedBy || null, categories, search }))
  const selected = $derived(selectedId !== null ? byId.get(selectedId) ?? null : null)

  async function pick(id: number) {
    selectedId = selectedId === id ? null : id
    confirmDelete = false
    if (selectedId !== null) {
      await tick()
      editCard?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  function toggleCategory(c: string) {
    categories = categories.includes(c) ? categories.filter((x) => x !== c) : [...categories, c]
  }

  async function remove(e: Expense) {
    deleting = true
    try {
      await del(`expenditures/${e.expenditure_id}`)
      showToast(`Deleted: ${whatText(e)} · ${formatBrl(cents(e.price))}`)
      selectedId = null
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Could not delete.', 'error')
    } finally {
      deleting = false
      confirmDelete = false
    }
  }
</script>

<PageHeader title="Entries" purpose="Every expense you can see: check what was logged, fix a mistake, or delete it." />

{#if error}
  <Message tone="error">{error}</Message>
{:else if expenses === null}
  <Loading />
{:else if !expenses.length}
  <Message tone="info">Nothing logged yet. <a href={href('add')}>Add your first expense</a>.</Message>
{:else}
  <div class="stack">
    <div class="filters">
      <label class="field">
        <span>Month</span>
        <select bind:value={month}>
          <option value="">All months</option>
          {#each months as m}<option value={m}>{monthLabel(m)}</option>{/each}
        </select>
      </label>
      <label class="field">
        <span>Show</span>
        <select bind:value={kind}>
          {#each Object.entries(KINDS) as [id, text]}<option value={id}>{text}</option>{/each}
        </select>
      </label>
      <label class="field">
        <span>Logged by</span>
        <select bind:value={loggedBy}>
          <option value="">Anyone</option>
          {#each people as p}<option value={p}>{p}</option>{/each}
        </select>
      </label>
      <label class="field search">
        <span>Search</span>
        <input type="search" bind:value={search} placeholder="e.g. groceries, Nubank, 45,90" />
      </label>
    </div>
    <div class="field">
      <span>Categories</span>
      <div class="chips">
        {#each primaries as c}
          <button type="button" class="chip" class:active={categories.includes(c)} aria-pressed={categories.includes(c)}
            onclick={() => toggleCategory(c)}>{c}</button>
        {/each}
      </div>
    </div>

    <Card title="What was logged?">
      {#if !shown.length}
        <p class="caption">Nothing matches these filters.</p>
      {:else}
        <p class="caption">{summary(shown)}. Pick a row to fix or delete it.</p>
        <div class="table-wrap wide">
          <table class="data">
            <thead>
              <tr><th>When</th><th>What</th><th class="num">Price</th><th class="num">Your part</th><th>Paid with</th>
                <th>Type</th><th>Logged by</th><th>Last edit</th></tr>
            </thead>
            <tbody>
              {#each shown as r (r.id)}
                <tr class="selectable" class:selected={selectedId === r.id} tabindex="0" aria-selected={selectedId === r.id}
                  onclick={() => pick(r.id)}
                  onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(r.id) } }}>
                  <td class="nowrap">{r.when}</td><td>{r.what}</td><td class="num">{r.price}</td>
                  <td class="num">{r.yourPart}</td><td>{r.paidWith}</td><td>{r.type}</td><td>{r.loggedBy}</td>
                  <td class="muted">{r.lastEdit}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        <ul class="cards narrow">
          {#each shown as r (r.id)}
            <li>
              <button type="button" class="entry" class:selected={selectedId === r.id} onclick={() => pick(r.id)}>
                <span class="top"><span class="what">{r.what}</span><span class="amount">{r.price}</span></span>
                <span class="meta">{r.when} · {r.paidWith}</span>
                <span class="meta">{r.type} · your part {r.yourPart} · by {r.loggedBy}{r.lastEdit ? ` · edited ${r.lastEdit}` : ''}</span>
              </button>
            </li>
          {/each}
        </ul>
      {/if}
    </Card>

    {#if selected}
      <div bind:this={editCard} class="edit">
        <Card title={`Fix ${whatText(selected)} · ${formatBrl(cents(selected.price))}`} subtitle={traceText(selected)}>
          {#snippet actions()}
            <button type="button" class="btn small" onclick={() => (selectedId = null)}>Close</button>
          {/snippet}
          {#key selected.expenditure_id}
            <EntryForm expense={selected} submitLabel="Save changes" onsaved={() => (selectedId = null)} />
          {/key}
          <div class="delete">
            {#if !confirmDelete}
              <button type="button" class="btn danger" onclick={() => (confirmDelete = true)}>Delete this expense</button>
            {:else}
              <Message tone="warn">It goes for good, with its split{selected.is_shared ? ' (for both of you)' : ''}.</Message>
              <div class="row">
                <button type="button" class="btn danger" disabled={deleting} onclick={() => remove(selected)}>
                  {deleting ? 'Deleting…' : 'Delete it'}</button>
                <button type="button" class="btn" onclick={() => (confirmDelete = false)}>Keep it</button>
              </div>
            {/if}
          </div>
        </Card>
      </div>
    {/if}
  </div>
{/if}

<style>
  .filters { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.75rem; align-items: end; }
  .chips { display: flex; flex-wrap: wrap; gap: 0.35rem; }
  .chip { border: 1px solid var(--line); background: var(--surface); border-radius: 999px; padding: 0.3rem 0.75rem;
    cursor: pointer; font-size: 0.88rem; }
  .chip.active { background: var(--brand-soft); border-color: var(--brand); color: var(--brand-strong); font-weight: 500; }
  .nowrap { white-space: nowrap; }
  .cards { display: none; list-style: none; margin: 0; padding: 0; }
  .entry { display: flex; flex-direction: column; gap: 0.15rem; width: 100%; text-align: left; background: none;
    border: none; border-bottom: 1px solid var(--hairline); padding: 0.65rem 0.25rem; cursor: pointer; }
  .entry.selected { background: var(--brand-soft); border-radius: 0.5rem; }
  .top { display: flex; justify-content: space-between; gap: 0.75rem; }
  .what { font-weight: 500; }
  .amount { font-weight: 600; white-space: nowrap; }
  .meta { font-size: 0.8rem; color: var(--ink-2); }
  .edit { scroll-margin-top: 70px; }
  .delete { border-top: 1px solid var(--hairline); padding-top: 1rem; margin-top: 0.5rem; display: flex;
    flex-direction: column; gap: 0.6rem; }
  @media (max-width: 900px) {
    .filters { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }
  @media (max-width: 600px) {
    .wide { display: none; }
    .cards { display: block; }
  }
</style>
