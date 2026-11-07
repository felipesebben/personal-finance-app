<!--
  Monthly recap: the month you review together, short — the total and how it
  compares, what drove it, the targets, then settling up. Last month by
  default (reviewed once a month ends); this month to look early. The
  sentences come from lib/recap.ts; settling up is SettleBox.
-->
<script lang="ts" module>
  let remembered: string | null = null
</script>

<script lang="ts">
  import { thisMonth } from '../lib/dates'
  import { get, session } from '../lib/session.svelte'
  import { whole, type TargetRow } from '../lib/targets'
  import { monthLabel, monthOptions, toRows, type Payload } from '../lib/overview/shaping'
  import { monthRecap } from '../lib/recap'
  import Card from '../lib/ui/Card.svelte'
  import Kpi from '../lib/ui/Kpi.svelte'
  import Loading from '../lib/ui/Loading.svelte'
  import Message from '../lib/ui/Message.svelte'
  import Lines from './overview/Lines.svelte'
  import SettleBox from './SettleBox.svelte'

  const options = monthOptions(thisMonth(), 12)
  let month = $state(remembered ?? options[1])
  $effect(() => {
    remembered = month
  })

  let data = $state<Payload | null>(null)
  let targets = $state<TargetRow[]>([])
  let error = $state('')
  let request = 0

  $effect(() => {
    void session.version
    const id = ++request
    error = ''
    Promise.all([
      get<Payload>(`analytics/shared?month=${month}&months=13`),
      get<TargetRow[]>('category_targets/').catch(() => [] as TargetRow[]),
    ]).then(([payload, t]) => {
      if (id !== request) return
      data = payload
      targets = t
    }).catch((e: Error) => {
      if (id === request) error = e.message
    })
  })

  const rows = $derived(toRows(data))
  const summary = $derived(data && data.month === month
    ? monthRecap(rows, data.months, month, data.is_partial, data.first_date, whole(targets)) : null)
  const empty = $derived(!rows.some((r) => r.month === month))
  const waiting = 'Shown once there\'s a whole month to compare with.'
</script>

<div class="stack">
  <label class="field picker">
    <span>Month to review</span>
    <select bind:value={month}>
      {#each options as m}<option value={m}>{monthLabel(m)}</option>{/each}
    </select>
  </label>

  {#if error}
    <Message tone="error">Couldn't load the recap: {error}</Message>
  {:else if !summary}
    <Loading />
  {:else}
    {#if empty}
      <Message>Nothing shared in {monthLabel(month)} yet.</Message>
    {:else}
      <Card>
        <Kpi hero label="{summary.label}: shared spending" value={summary.total} lines={summary.lines}
          help="Everything shared in the month, at full price." />
      </Card>
      <div class="grid cols-2">
        <Card title="What drove it?" minHeight={200}>
          <Lines title="Day-to-day or fixed" lines={summary.causes} empty={waiting} />
          <Lines title="Biggest moves" lines={summary.moves} empty={waiting} />
        </Card>
        <Card title="Are we on target?" minHeight={200}>
          <Lines lines={summary.targets} empty="No targets yet: set them in Settings → Monthly targets." />
        </Card>
      </div>
    {/if}
    <Card title="Settling up">
      <SettleBox period={month} key="recap" />
    </Card>
  {/if}
</div>

<style>
  .picker { max-width: 14rem; }
</style>
