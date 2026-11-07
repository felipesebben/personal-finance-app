<!--
  The one row of controls every analysis view opens with, so the answer
  comes right after it: the month, on My expenses "Show" (everything I spent,
  personal only or my share of shared, which decides what's fetched), what to
  count, and a Filters panel holding the rest (categories, leave out
  one-offs, and on Month by month count installments when billed), whose
  label says how many are on. filtering.ts does the narrowing.
  Everything is bindable; the parent owns the state.
-->
<script lang="ts" module>
  /** What My expenses can show: everything I spent, or one half of it. */
  export const VIEWS: Record<string, string> = {
    all: 'Everything I spent',
    personal: 'Personal only',
    shared: 'My share of shared',
  }
</script>

<script lang="ts">
  import { FOCUSES, countOn, type Filters } from '../filtering'
  import { monthLabel } from '../dates'
  import Segmented from './Segmented.svelte'
  import Icon from './Icon.svelte'

  let {
    months,
    month = $bindable(),
    filters = $bindable(),
    categories = [],
    view = $bindable('all'),
    showView = false,
    billed = $bindable(false),
    installments = false,
  }: {
    months: string[]
    month: string
    filters: Filters
    categories?: string[]
    view?: string
    showView?: boolean
    billed?: boolean
    installments?: boolean
  } = $props()

  let open = $state(false)
  const on = $derived(countOn(filters, installments && billed))

  function toggleCategory(c: string) {
    const has = filters.categories.includes(c)
    filters = { ...filters, categories: has ? filters.categories.filter((x) => x !== c) : [...filters.categories, c] }
  }

  // A pick from another month's categories would hide everything: drop it.
  $effect(() => {
    const kept = filters.categories.filter((c) => categories.includes(c))
    if (categories.length && kept.length !== filters.categories.length) filters = { ...filters, categories: kept }
  })
</script>

<div class="filter-row">
  <label class="field month">
    <span>Month</span>
    <select bind:value={month}>
      {#each months as m}<option value={m}>{monthLabel(m)}</option>{/each}
    </select>
  </label>
  {#if showView}
    <label class="field view">
      <span>Show</span>
      <select bind:value={view} title="Everything I spent = my share of shared expenses + my personal ones.">
        {#each Object.entries(VIEWS) as [id, text]}<option value={id}>{text}</option>{/each}
      </select>
    </label>
  {/if}
  <div class="focus">
    <Segmented label="What to count" options={[...FOCUSES]} value={filters.focus}
      onchange={(v) => (filters = { ...filters, focus: v })} />
  </div>
  <div class="more">
    <button type="button" class="btn" class:on={on > 0} aria-expanded={open} onclick={() => (open = !open)}>
      <Icon name="filter" size={18} />{on ? `Filters · ${on}` : 'Filters'}
    </button>
  </div>
</div>

{#if open}
  <div class="panel">
    <div class="field">
      <span>Categories</span>
      {#if categories.length}
        <div class="chips">
          {#each categories as c}
            <button type="button" class="chip" class:active={filters.categories.includes(c)}
              aria-pressed={filters.categories.includes(c)} onclick={() => toggleCategory(c)}>{c}</button>
          {/each}
        </div>
        <span class="hint">{filters.categories.length ? 'Only the picked categories count.' : 'All categories count.'}</span>
      {:else}
        <span class="hint">No categories this month.</span>
      {/if}
    </div>
    <label class="check" title="Expenses marked Annual or Extraordinary, like IPVA or a repair, which would make one month look expensive.">
      <input type="checkbox" checked={filters.withoutOneOffs}
        onchange={(e) => (filters = { ...filters, withoutOneOffs: e.currentTarget.checked })} />
      Leave out one-offs <span class="hint">(Annual or Extraordinary, e.g. IPVA, a repair)</span>
    </label>
    {#if installments}
      <label class="check">
        <input type="checkbox" bind:checked={billed} />
        Count installments when billed
        <span class="hint">(off: in full in the month bought; on: each part in the month it's billed)</span>
      </label>
    {/if}
  </div>
{/if}

<style>
  .filter-row { display: flex; flex-wrap: wrap; gap: 0.75rem 1rem; align-items: flex-end; margin-bottom: 0.75rem; }
  .month { width: 11.5rem; }
  .view { width: 12.5rem; }
  .focus { flex: 1 1 auto; }
  .btn.on { border-color: var(--brand); color: var(--brand); }
  .panel { background: var(--surface); border-radius: var(--radius); box-shadow: var(--shadow-card);
    padding: 1rem; display: flex; flex-direction: column; gap: 0.85rem; margin-bottom: 1rem; }
  .chips { display: flex; flex-wrap: wrap; gap: 0.35rem; }
  .chip { border: 1px solid var(--line); background: var(--surface); border-radius: 999px; padding: 0.3rem 0.75rem;
    cursor: pointer; font-size: 0.88rem; }
  .chip.active { background: var(--brand-soft); border-color: var(--brand); color: var(--brand-strong); font-weight: 500; }
  .hint { font-size: 0.8rem; color: var(--muted); }
  @media (max-width: 560px) {
    .month, .view { width: calc(50% - 0.5rem); }
  }
</style>
