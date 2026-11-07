<!--
  Month by month (Our expenses) / Over time (My expenses): spending across
  months, charts only. The filter row first, then three KPI cards, the
  monthly trend, whether the costs we control are changing, and two compact
  cards for fixed costs and one-offs (with the reserve to set aside).

  "Where is the money going?" and "What's inside a category?" live on This
  month only: it has the same cards for any month, so they aren't repeated
  here. With showView (My expenses) "Show" picks the expenses: shared
  (/analytics/shared), personal (/analytics/personal) or all (both, added
  together). `lens` picks the amount: Household (full prices) or My share.
  Shaping lives in lib/overview/shaping.ts; each card is in ./overview/.
-->
<script lang="ts" module>
  import { NO_FILTERS, type Filters } from '../lib/filtering'

  /** Each page's picks, kept while you move between tabs. */
  const memory: Record<string, { month: string; view: string; filters: Filters; billed: boolean; window: '6' | '12' }> = {}
</script>

<script lang="ts">
  import { filterRows, note } from '../lib/filtering'
  import { thisMonth } from '../lib/dates'
  import { get, session } from '../lib/session.svelte'
  import { href } from '../lib/router.svelte'
  import FilterRow from '../lib/ui/FilterRow.svelte'
  import Loading from '../lib/ui/Loading.svelte'
  import Message from '../lib/ui/Message.svelte'
  import {
    mergePayloads, monthLabel, monthOptions, partlyLoggedFrom, shiftMonth, toRows, trackedSince, type Lens, type Payload,
  } from '../lib/overview/shaping'
  import type { OverviewContext } from './overview/context'
  import Kpis from './overview/Kpis.svelte'
  import Trend from './overview/Trend.svelte'
  import Control from './overview/Control.svelte'
  import FixedAndOneOffs from './overview/FixedAndOneOffs.svelte'

  let { lens, key, showView = false }: { lens: string; key: string; showView?: boolean } = $props()

  const SCOPES: Record<string, { endpoints: string[]; noun: string }> = {
    shared: { endpoints: ['analytics/shared'], noun: 'shared expenses' },
    personal: { endpoints: ['analytics/personal'], noun: 'personal expenses' },
    all: { endpoints: ['analytics/shared', 'analytics/personal'], noun: 'expenses' },
  }

  const current = thisMonth()
  // `key` is fixed for a page's overview: read once to restore its picks.
  // svelte-ignore state_referenced_locally
  const saved = memory[key]
  let month = $state(saved?.month ?? current)
  let view = $state(saved?.view ?? 'all')
  let filters = $state<Filters>(saved?.filters ?? NO_FILTERS)
  let billed = $state(saved?.billed ?? false)
  let window = $state<'6' | '12'>(saved?.window ?? '12')
  $effect(() => {
    memory[key] = { month, view, filters, billed, window }
  })

  const scope = $derived(showView ? view : 'shared')
  const basis = $derived(billed ? 'billed' : 'bought')

  let data = $state<Payload | null>(null)
  let error = $state('')
  let loading = $state(true)
  let request = 0

  $effect(() => {
    void session.version
    const endpoints = SCOPES[scope].endpoints
    const query = `month=${month}&months=12&basis=${basis}`
    const id = ++request
    loading = true
    error = ''
    Promise.all(endpoints.map((e) => get<Payload>(`${e}?${query}`)))
      .then((payloads) => {
        if (id !== request) return
        data = mergePayloads(Object.fromEntries(payloads.map((p, i) => [endpoints[i], p])))
        loading = false
      })
      .catch((e: Error) => {
        if (id !== request) return
        error = e.message
        loading = false
      })
  })

  const all = $derived(toRows(data))
  const categories = $derived([...new Set(all.map((r) => r.primary_category))].sort())
  const rows = $derived(filterRows(all, filters))

  const ctx = $derived.by((): OverviewContext | null => {
    if (!data) return null
    const previous = shiftMonth(month, -1)
    const firstDate = data.first_date ?? null
    const earliest = all.length ? all.reduce((m, r) => (r.month < m ? r.month : m), all[0].month) : null
    const since = trackedSince(firstDate) ?? earliest
    const household = lens === 'Household'
    return {
      rows, months: data.months, selected: month, previous, isPartial: data.is_partial, asOfDay: data.as_of_day,
      lens: (household ? 'Household' : 'My share') as Lens,
      since,
      comparable: since !== null && since <= previous,
      partly: partlyLoggedFrom(previous, firstDate),
      partlyMonth: firstDate && partlyLoggedFrom(firstDate.slice(0, 7), firstDate) ? firstDate.slice(0, 7) : null,
      firstDate,
      previousTitle: data.is_partial
        ? `${monthLabel(previous, true)} (days 1–${data.as_of_day})` : monthLabel(previous, true),
      headline: ({ shared: household ? 'Shared total' : 'My share', personal: 'Personal', all: 'I spent' } as Record<string, string>)[scope],
      noun: SCOPES[scope].noun,
      filters,
    }
  })
  const counting = $derived(note(filters))
</script>

<FilterRow months={monthOptions(current, 12)} bind:month bind:filters {categories} bind:view {showView}
  bind:billed installments />

{#if error}
  <Message tone="error">Couldn't load the overview: {error}</Message>
{:else if loading && !data}
  <Loading />
{:else if ctx}
  {#if !all.length}
    <Message>
      No {ctx.noun} in the 12 months up to {monthLabel(month)}. <a href={href('add')}>Log one</a> to see this overview.
    </Message>
  {:else if !rows.length}
    <Message>Nothing matches these filters in the 12 months. Widen them to see more.</Message>
  {:else}
    <div class="stack" class:stale={loading}>
      {#if counting || billed}
        <p class="caption">
          {#if counting}Counting {counting}.{/if}
          {#if billed}Installments are counted in the month they're billed.{/if}
        </p>
      {/if}
      <Kpis {ctx} />
      <Trend {ctx} bind:window />
      <Control {ctx} />
      <FixedAndOneOffs {ctx} />
    </div>
  {/if}
{/if}

<style>
  .stale { opacity: 0.6; transition: opacity 0.2s; }
</style>
