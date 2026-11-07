<!--
  This month, day by day: is this month running ahead of last month and the
  usual month, by the same day, and where does the money go?

  Top to bottom, from the whole month down to single days:
  - one row of controls (FilterRow);
  - in-app notices (a target passed or close, a recurring bill late);
  - the answer: "Are we on track this month?" — the spent-so-far KPI over
    its running total against one comparison at a time (and the target's
    steady pace) — beside this month's calendar;
  - three KPI cards: last month, the usual month, what's left per day;
  - what's still to come (bills not logged yet, card installments);
  - where the money goes and what's inside a category (Where.svelte);
  - what went on the biggest days, and a picked day's purchases.

  On Our expenses it reads the shared endpoints; on My expenses (showView)
  "Show" picks shared, personal or both. Shaping lives in lib/daily.
-->
<script lang="ts" module>
  import { NO_FILTERS, type Filters } from '../lib/filtering'
  // Picks remembered per view while the app is open, so switching tabs keeps them.
  const memory = new Map<string, { month: string; filters: Filters; view: string; compare: string | null }>()
</script>

<script lang="ts">
  import { untrack } from 'svelte'
  import { get, session } from '../lib/session.svelte'
  import { href } from '../lib/router.svelte'
  import { monthName, ordinal, recentMonths, thisMonth, todayIso } from '../lib/dates'
  import { formatBrl, shortBrl } from '../lib/money'
  import { filterRows, isActive, note } from '../lib/filtering'
  import { label as targetLabel, subs, whole, type TargetRow } from '../lib/targets'
  import {
    againstLastMonth, biggestDays, byDay, calendarDays, calendarScaleMax, cards, dayItems, headline, history,
    loggingStarted, mergePayloads, pace, ranked, readRows, targetTotal, trackedSince, trackSeries,
    type DailyPayload, type DayExpense, type Lens, type Role, type Row, type TrackSeries,
  } from '../lib/daily/shaping'
  import { notices as noticeLines } from '../lib/daily/notices'
  import { installmentsDue, LOOKBACK, recurringDue, type Expense } from '../lib/daily/upcoming'
  import type { WhereItem } from '../lib/daily/where'
  import { BRAND, INK, SPARK_HEIGHT } from '../lib/charts/palette'
  import FilterRow from '../lib/ui/FilterRow.svelte'
  import Card from '../lib/ui/Card.svelte'
  import Kpi from '../lib/ui/Kpi.svelte'
  import Notices from '../lib/ui/Notices.svelte'
  import EmptyChart from '../lib/ui/EmptyChart.svelte'
  import Loading from '../lib/ui/Loading.svelte'
  import Message from '../lib/ui/Message.svelte'
  import Segmented from '../lib/ui/Segmented.svelte'
  import LineChart, { type Series } from '../lib/charts/LineChart.svelte'
  import SparkBars from '../lib/charts/SparkBars.svelte'
  import RankedBars from '../lib/charts/RankedBars.svelte'
  import Calendar from './daily/Calendar.svelte'
  import Progress from './daily/Progress.svelte'
  import Where from './Where.svelte'

  let { lens, key, showView = false }: { lens: string; key: string; showView?: boolean } = $props()

  const ENDPOINTS: Record<string, [string, string]> = {
    shared: ['analytics/shared/daily', 'analytics/shared/expenses'],
    personal: ['analytics/personal/daily', 'analytics/personal/expenses'],
  }
  const VIEW_SOURCES: Record<string, string[]> = { all: ['shared', 'personal'], personal: ['personal'], shared: ['shared'] }
  const NOUNS: Record<string, string> = { all: 'expenses', personal: 'personal expenses', shared: 'shared expenses' }
  /** The month and twelve before: last month, usual, the 12-month average, the same month last year. */
  const MONTHS = 13
  const TOP_HEIGHT = 380
  const CARD_HEIGHT = 230
  // This month brand green and thick; comparisons greys told apart by their dash; the target ink, dotted.
  const STYLE: Record<Role, { color: string; width: number; dash?: string }> = {
    this: { color: BRAND, width: 3 },
    last: { color: '#7d8780', width: 2 },
    usual: { color: '#8f9892', width: 2, dash: '6 4' },
    year: { color: '#8f9892', width: 2, dash: '2 3' },
    last_year: { color: '#8f9892', width: 2, dash: '9 3 2 3' },
    target: { color: INK, width: 1.5, dash: '1 3' },
  }

  const L = $derived(lens as Lens)
  const remembered = untrack(() => memory.get(key))
  const months = recentMonths(12)
  let month = $state(remembered?.month ?? thisMonth())
  let filters = $state<Filters>(remembered?.filters ?? NO_FILTERS)
  let view = $state(remembered?.view ?? 'all')
  let compareChoice = $state<string | null>(remembered?.compare ?? null)
  let pickedDay = $state<string | null>(null)

  $effect(() => {
    memory.set(key, { month, filters, view, compare: compareChoice })
  })

  const viewName = $derived(showView ? view : 'shared')
  const sources = $derived(VIEW_SOURCES[viewName])
  const noun = $derived(NOUNS[viewName])

  // --- data -------------------------------------------------------------------
  let data = $state<DailyPayload | null>(null)
  let error = $state('')
  let loading = $state(true)
  let targetRows = $state<TargetRow[]>([])
  let expenses = $state<Expense[]>([])

  $effect(() => {
    void session.version
    const query = `month=${month}&months=${MONTHS}`
    const wanted = sources
    let stale = false
    loading = true
    error = ''
    Promise.all(wanted.map((s) => get<DailyPayload>(`${ENDPOINTS[s][0]}?${query}`)))
      .then((payloads) => {
        if (!stale) data = mergePayloads(Object.fromEntries(wanted.map((s, i) => [s, payloads[i]])))
      })
      .catch((e) => { if (!stale) error = e instanceof Error ? e.message : 'Could not load this month.' })
      .finally(() => { if (!stale) loading = false })
    return () => { stale = true }
  })

  $effect(() => {
    void session.version
    if (L !== 'Household') { targetRows = []; return }
    get<TargetRow[]>('category_targets/').then((t) => (targetRows = t)).catch(() => (targetRows = []))
  })

  // --- shaping -------------------------------------------------------------------
  const rows = $derived(readRows(data))
  const categories = $derived([...new Set(rows.map((r) => r.primary_category))].sort())
  const since = $derived(trackedSince(rows)) // before any filter: earlier months weren't logged in full
  const started = $derived(loggingStarted(rows))
  const picked = $derived(filterRows(rows, filters))
  const days = $derived(byDay(picked))
  const ready = $derived(!!data && picked.length > 0)
  const p = $derived(data ? pace(days, data, L, since, started) : null)
  const today = $derived(data?.today?.slice(0, 10) ?? todayIso())
  const hist = $derived(data ? history(days, data, L, since) : [])
  const cal = $derived(calendarDays(days, month, L, today))
  const calTop = $derived(calendarScaleMax(cal.map((d) => d.amount)))
  const wholeTargets = $derived(whole(targetRows))
  const target = $derived(targetTotal(wholeTargets, picked, isActive(filters)))
  const monthRows = $derived(picked.filter((r) => r.month === month))
  const spent = $derived(sumBy(monthRows, (r) => r.primary_category))
  const subSpent = $derived(sumBy(monthRows, (r) => targetLabel(r.primary_category, r.sub_category)))
  const topCategory = $derived([...spent].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null)

  function sumBy(list: Row[], name: (r: Row) => string): Map<string, number> {
    const out = new Map<string, number>()
    const c = L === 'Household' ? 'household' : 'mine'
    for (const r of list) out.set(name(r), (out.get(name(r)) ?? 0) + r[c])
    return out
  }

  // What's still to come: only for the month in progress.
  $effect(() => {
    void session.version
    if (!data?.is_partial) { expenses = []; return }
    get<Expense[]>('expenditures/').then((e) => (expenses = e)).catch(() => (expenses = []))
  })
  const bills = $derived(data?.is_partial ? filterRows(recurringDue(expenses, month, viewName, L), filters) : [])
  const installments = $derived(data?.is_partial ? filterRows(installmentsDue(expenses, month, viewName, L), filters) : [])
  const total = (list: { amount: number }[]) => list.reduce((a, b) => a + b.amount, 0)

  const notices = $derived.by(() => {
    if (!p?.is_partial) return []
    const active = isActive(filters)
    const followed = new Map<string, number>()
    for (const [c, v] of wholeTargets) if (spent.has(c) || !active) followed.set(c, v)
    for (const [s, v] of subs(targetRows)) if (subSpent.has(s) || !active) followed.set(s, v)
    return noticeLines(followed, new Map([...spent, ...subSpent]), bills, p.day, p.days)
  })

  // --- the running total: this month against one comparison at a time --------------
  const track = $derived<TrackSeries[]>(data ? trackSeries(days, data, L, since, started, target) : [])
  const comparisons = $derived(track.filter((s) => s.role !== 'this' && s.role !== 'target'))
  const compare = $derived(
    comparisons.find((s) => s.name === compareChoice)?.name
      ?? comparisons.find((s) => s.role === 'usual')?.name ?? comparisons[0]?.name ?? null)
  const shown = $derived<Series[]>(track
    .filter((s) => s.role === 'this' || s.role === 'target' || s.name === compare)
    .map((s) => ({ name: s.name, points: s.values.map((y, i) => ({ x: i + 1, y })), ...STYLE[s.role], dot: s.role === 'this' }))
    .reverse()) // comparisons first, so this month is drawn on top
  const hero = $derived(p ? headline(p, note(filters), started) : null)
  const kpis = $derived(p ? cards(p) : [])
  const trackNote = $derived.by(() => {
    if (!p) return ''
    const parts = [comparisons.length ? 'Hover or tap the chart to compare a day.'
      : 'Comparisons appear as whole months are logged.']
    if (p.last_partly_from) parts.push(`${monthName(p.previous)} was logged from the ${ordinal(p.last_partly_from)} only, so its line starts late.`)
    if (target > 0) parts.push('The dotted line is the target at a steady pace.')
    return parts.join(' ')
  })
  const lastCal = $derived(p ? calendarDays(days, p.previous, L, today) : [])

  // --- where the money goes --------------------------------------------------------------
  const lastBy = $derived(p ? monthName(p.previous) + (p.is_partial ? ` by the ${ordinal(p.day)}` : '') : '')

  function whereItems(list: Row[], by: 'primary_category' | 'sub_category', targets: Map<string, number>): WhereItem[] {
    const mix = ranked(list, L, by, { month })
    // Last month by the same day, once it was logged in full (a partial month would mislead).
    const withPrev = p?.has_last ? againstLastMonth(mix, list, L, by, month, p.day) : null
    return mix.map((m, i) => ({ name: m.name, amount: m.amount, previous: withPrev ? withPrev[i].previous : null,
      target: targets.get(m.name) ?? null }))
  }
  const categoryItems = $derived(ready ? whereItems(picked, 'primary_category', wholeTargets) : [])
  const whereNote = $derived([
    p?.has_last ? `Grey tick and change: against ${lastBy}.` : '',
    categoryItems.some((i) => i.target) ? 'Dark tick: the monthly target.' : '',
  ].filter(Boolean).join(' '))
  const inside = (category: string) =>
    whereItems(picked.filter((r) => r.primary_category === category), 'sub_category', subs(targetRows, category))
  const insideNote = (_: string, items: WhereItem[]) =>
    items.some((i) => i.target) ? "Dark tick: the sub-category's own target (Settings)." : ''

  // --- the biggest days --------------------------------------------------------------------
  const big = $derived(ready ? biggestDays(days, month, L) : [])
  const dayOptions = $derived.by(() => {
    const opts = big.map((d) => ({ key: d.key, name: d.name }))
    const c = pickedDay ? cal.find((d) => d.date === pickedDay) : undefined
    if (c && !opts.some((o) => o.key === c.date)) {
      opts.push({ key: c.date, name: `${c.label.slice(0, 3)} ${c.day} ${monthName(month).slice(0, 3)}` })
    }
    return opts
  })
  const day = $derived(dayOptions.some((o) => o.key === pickedDay) ? pickedDay : (dayOptions[0]?.key ?? null))
  const averageDay = $derived(p && p.day ? Math.round(p.so_far / p.day) : null)

  let items = $state<DayExpense[] | null>(null)
  $effect(() => {
    void session.version
    const d = day
    const wanted = sources
    if (!d) { items = []; return }
    let stale = false
    items = null
    Promise.all(wanted.map((s) => get<DayExpense[]>(`${ENDPOINTS[s][1]}?day=${d}`)))
      .then((lists) => { if (!stale) items = lists.flat() })
      .catch(() => { if (!stale) items = [] })
    return () => { stale = true }
  })
  const dayBars = $derived(items ? dayItems(filterRows(items, filters), L) : [])

  function pickCalendarDay(date: string) {
    pickedDay = date
    document.getElementById(`${key}-biggest`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
</script>

<FilterRow {months} bind:month bind:filters bind:view {categories} {showView} />

{#if loading && !data}
  <Loading />
{:else if error}
  <Message tone="error">Could not load this month: {error}</Message>
{:else if !rows.length}
  <Message>
    No {noun} in {monthName(month)} or the months before it yet. As you log expenses, this page compares each
    month with the ones before, day by day. <a href={href('add')}>Add an expense</a>
  </Message>
{:else if !ready || !p || !hero}
  <Message>Nothing matches these filters in this window. Widen them to see more.</Message>
{:else}
  <div class="daily" class:dim={loading}>
    <Notices lines={notices} />

    <div class="top">
      <Card title="Are we on track this month?" minHeight={TOP_HEIGHT}>
        <Kpi label={hero.label} value={hero.amount} lines={hero.lines} hero
          help="Everything counted so far this month, against the same days of earlier months." />
        {#if comparisons.length > 1}
          <Segmented label="Compare with" options={comparisons.map((s) => s.name)} value={compare ?? ''}
            onchange={(v) => (compareChoice = v)} />
        {/if}
        <LineChart series={shown} xMax={p.days} height={230} xTicks={[1, 5, 10, 15, 20, 25, p.days]}
          xTitle="Day of the month" yTitle="Spent so far" readoutLabel={(d) => `Day ${d}`} />
        <p class="caption">{trackNote}</p>
      </Card>
      <Card minHeight={TOP_HEIGHT}>
        <div class="cal-label">{monthName(month)} · {p.is_partial ? `day ${p.day} of ${p.days}` : `all ${p.days} days`}</div>
        <Calendar days={cal} top={calTop} picked={pickedDay} onpick={pickCalendarDay} />
        <p class="caption">{topCategory ? `Mostly ${topCategory}. ` : ''}Darker days cost more; tap one to see what it held.</p>
      </Card>
    </div>

    <div class="grid cols-3">
      {#each kpis as card (card.key)}
        <Card minHeight={CARD_HEIGHT} compact>
          <Kpi label={card.label} value={card.value} lines={card.lines} help={card.help}>
            {#if card.key === 'last'}
              {@const past = hist.filter((h) => h.month !== month)}
              {#if p.has_last && past.length}
                <SparkBars values={past.map((h) => h.total)} labels={past.map((h) => `${h.label}: ${formatBrl(h.total)}`)}
                  highlight={past.findIndex((h) => h.month === p.previous)} />
              {:else if p.last_partly_from}
                <SparkBars values={lastCal.map((d) => d.amount)} labels={lastCal.map((d) => `${d.label}: ${formatBrl(d.amount)}`)}
                  highlight={null} />
              {:else}
                <EmptyChart text="Appears once a whole month before this one has been logged." height={SPARK_HEIGHT} />
              {/if}
            {:else if card.key === 'usual'}
              {@const usual = hist.filter((h) => p.usual_of.includes(h.month))}
              {#if usual.length}
                <SparkBars values={usual.map((h) => h.total)} labels={usual.map((h) => `${h.label}: ${formatBrl(h.total)}`)}
                  highlight={null} />
              {:else}
                <EmptyChart text="Appears after three whole months of history." height={SPARK_HEIGHT} />
              {/if}
            {:else if card.key === 'allowance'}
              <Progress spent={p.reference ? p.so_far / p.reference : 0} time={p.day / p.days} />
            {:else}
              <SparkBars values={cal.map((d) => d.amount)} labels={cal.map((d) => `${d.label}: ${formatBrl(d.amount)}`)}
                highlight={p.day - 1} />
            {/if}
          </Kpi>
        </Card>
      {/each}
    </div>

    {#if bills.length || installments.length}
      {@const parts = [
        bills.length ? `about ${formatBrl(total(bills))} in bills not logged yet` : '',
        installments.length ? `${formatBrl(total(installments))} in card installments of earlier purchases` : '',
      ].filter(Boolean)}
      <Card title="What's still to come this month?"
        subtitle="Still to come: {parts.join(' and ')}. Bills are recurring expenses from the last {LOOKBACK} months, at their latest amount.">
        <div class="grid cols-2">
          {#if bills.length}
            <div>
              <div class="sub-head">Bills not logged yet</div>
              <RankedBars rows={bills.map((b) => ({ label: b.name, value: b.amount, text: b.text }))} maxLabel={26} />
            </div>
          {/if}
          {#if installments.length}
            <div>
              <div class="sub-head">Card installments billed this month</div>
              <RankedBars rows={installments.map((b) => ({ label: b.name, value: b.amount, text: b.text }))} maxLabel={28} />
            </div>
          {/if}
        </div>
      </Card>
    {/if}

    <Where title="Where is the money going in {monthName(month)}?" items={categoryItems} note={whereNote}
      changeTitle="Change vs {monthName(p.previous)}" {inside} {insideNote} memoryKey="{key}-daily" />

    <div id="{key}-biggest">
      <Card title="What went on the biggest days of {monthName(month)}?"
        subtitle={averageDay ? `The dashed line is the month's average day, ${formatBrl(averageDay)}, quiet days included.` : ''}>
        {#if !big.length}
          <p class="caption">Nothing spent yet this month.</p>
        {:else}
          <div class="grid cols-2">
            <RankedBars rows={big.map((d) => ({ label: d.name, value: d.amount, text: d.text, picked: d.key === day,
              title: `${d.name}: ${formatBrl(d.amount)} · ${d.count} expense${d.count === 1 ? '' : 's'}` }))}
              reference={averageDay} referenceLabel="average day {shortBrl(averageDay ?? 0)}"
              onpick={(name) => (pickedDay = big.find((d) => d.name === name)?.key ?? pickedDay)} />
            <div class="stack day-items">
              <label class="field">
                <span>Look inside</span>
                <select value={day} onchange={(e) => (pickedDay = e.currentTarget.value)}>
                  {#each dayOptions as o}<option value={o.key}>{o.name}</option>{/each}
                </select>
              </label>
              {#if items === null}
                <Loading height={80} />
              {:else if !dayBars.length}
                <p class="caption">Nothing among what's being counted.</p>
              {:else}
                <RankedBars rows={dayBars.map((i) => ({ label: i.name, value: i.amount, text: i.text,
                  title: `${i.name}: ${formatBrl(i.amount)} · ${i.detail}` }))} maxLabel={28} />
              {/if}
            </div>
          </div>
        {/if}
      </Card>
    </div>
  </div>
{/if}

<style>
  .daily { display: flex; flex-direction: column; gap: 1rem; transition: opacity 0.15s; }
  .daily.dim { opacity: 0.6; }
  .top { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); gap: 1rem; }
  .cal-label { color: var(--ink-2); font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; }
  .sub-head { font-weight: 600; font-size: 0.9rem; margin-bottom: 0.4rem; }
  .day-items { gap: 0.6rem; }
  .day-items .field { max-width: 14rem; }
  @media (max-width: 900px) {
    .top { grid-template-columns: minmax(0, 1fr); }
  }
</style>
