<!--
  Settle up: who owes whom for a period, and recording the payment. The
  answer and the action first (SettleBox); how it was worked out, another
  payment (other direction, another day, a note) and the payments recorded
  after.
-->
<script lang="ts">
  import { del, get, post, session, showToast } from '../lib/session.svelte'
  import { cents, formatBrl, parseBrl, toApi } from '../lib/money'
  import { nowTime, recentMonths, saoPauloTimestamp, todayIso } from '../lib/dates'
  import { brDate } from '../lib/joint'
  import { ALL_TIME, netText, periodLabel, personLines, type BalanceReport, type Settlement } from '../lib/settle'
  import Card from '../lib/ui/Card.svelte'
  import Kpi from '../lib/ui/Kpi.svelte'
  import Lede from '../lib/ui/Lede.svelte'
  import Message from '../lib/ui/Message.svelte'
  import SettleBox from './SettleBox.svelte'

  const periods = [...recentMonths(12), ALL_TIME]
  let period = $state(periods[0])
  let report = $state<BalanceReport | null>(null)
  let settlements = $state<Settlement[]>([])

  const label = $derived(periodLabel(period))
  const month = $derived(period === ALL_TIME ? null : period)
  const suggestion = $derived(report?.transfers[0] ?? null)

  // The "another payment" form, prefilled from the suggested transfer.
  let fromId = $state<number | null>(null)
  let toId = $state<number | null>(null)
  let amountText = $state('')
  let paidOn = $state(todayIso())
  let note = $state('')
  let formError = $state('')
  let busy = $state(false)

  $effect(() => {
    if (suggestion) {
      fromId = suggestion.from_user_id
      toId = suggestion.to_user_id
      amountText = formatBrl(cents(suggestion.amount), false)
    } else if (report && report.members.length >= 2) {
      fromId = report.members[0].user_id
      toId = report.members[1].user_id
      amountText = ''
    }
  })

  $effect(() => {
    void session.version
    const path = period === ALL_TIME ? 'settlements/' : `settlements/?month=${period}`
    get<Settlement[]>(path).then((s) => (settlements = s)).catch(() => (settlements = []))
  })

  async function recordPayment(e: SubmitEvent) {
    e.preventDefault()
    formError = ''
    let amount: number
    try {
      amount = parseBrl(amountText)
    } catch (err) {
      formError = `Amount: ${(err as Error).message}`
      return
    }
    if (fromId === toId) {
      formError = 'From and To must be different people.'
      return
    }
    busy = true
    try {
      await post('settlements/', {
        settled_at: saoPauloTimestamp(paidOn, nowTime()),
        from_user_id: fromId, to_user_id: toId, amount: toApi(amount), month, note: note.trim() || null,
      })
      note = ''
      showToast(`Payment recorded: ${formatBrl(amount)}. Made a mistake? Remove it under Payments recorded.`)
    } catch (err) {
      formError = (err as Error).message
    } finally {
      busy = false
    }
  }

  async function remove(s: Settlement) {
    if (!confirm(`Remove the payment of ${formatBrl(cents(s.amount))} from ${s.from_name} to ${s.to_name}?`)) return
    try {
      await del(`settlements/${s.settlement_id}`)
      showToast('Payment removed.')
    } catch (err) {
      showToast((err as Error).message, 'error')
    }
  }
</script>

<div class="stack">
  <Lede headline="Who owes whom, and recording the payment."
    body=" Compares what each of you paid for shared expenses with what the household ratio says you should have paid, minus payments already recorded. The joint account never counts: you've both already paid into it." />

  <div class="toolbar">
    <label class="field" title="Usually the month you're squaring up. “All time” is the running balance across every month.">
      <span class="sr-only">Period</span>
      <select class="compact" bind:value={period}>
        {#each periods as p}<option value={p}>{periodLabel(p)}</option>{/each}
      </select>
    </label>
  </div>

  <SettleBox {period} key="settle" onreport={(r) => (report = r)} />

  {#if report && report.members.length}
    <h3>How we got there</h3>
    <div class="grid cols-2">
      {#each report.members as m (m.user_id)}
        <Card compact>
          <Kpi label={m.full_name || '—'} value={netText(m.net)} lines={personLines(m)}
            help="Paid: what went out of their account for shared expenses. Their share: what the household ratio puts on them. The difference, after payments, is what they're owed (or owe)." />
        </Card>
      {/each}
    </div>
  {/if}

  {#if report && report.members.length >= 2}
    <details class="expander">
      <summary>Another payment (other direction, another day, a note)</summary>
      <form class="stack" onsubmit={recordPayment}>
        <p class="caption">Squares up <b>{period === ALL_TIME ? 'the running all-time balance' : label}</b>.</p>
        <div class="grid cols-2">
          <label class="field"><span>From</span>
            <select bind:value={fromId}>
              {#each report.members as m}<option value={m.user_id}>{m.full_name}</option>{/each}
            </select>
          </label>
          <label class="field"><span>To</span>
            <select bind:value={toId}>
              {#each report.members as m}<option value={m.user_id}>{m.full_name}</option>{/each}
            </select>
          </label>
          <label class="field"><span>Amount (R$)</span>
            <input type="text" inputmode="decimal" placeholder="0,00" bind:value={amountText} />
          </label>
          <label class="field"><span>Paid on</span><input type="date" bind:value={paidOn} max={todayIso()} /></label>
        </div>
        <label class="field"><span>Note (optional)</span>
          <input type="text" placeholder="e.g. Pix transfer" bind:value={note} />
        </label>
        {#if formError}<Message tone="error">{formError}</Message>{/if}
        <div><button class="btn primary" type="submit" disabled={busy}>Record payment</button></div>
      </form>
    </details>
  {/if}

  {#if settlements.length}
    <details class="expander">
      <summary>Payments recorded for {label} ({settlements.length})</summary>
      <div class="table-wrap">
        <table class="data">
          <thead><tr><th>Paid on</th><th>From → To</th><th class="num">Amount</th><th>For month</th><th>Note</th><th></th></tr></thead>
          <tbody>
            {#each settlements as s (s.settlement_id)}
              <tr>
                <td>{brDate(s.settled_at)}</td>
                <td>{s.from_name} → {s.to_name}</td>
                <td class="num">{formatBrl(cents(s.amount))}</td>
                <td>{s.month ?? 'All time'}</td>
                <td>{s.note ?? ''}</td>
                <td><button type="button" class="btn small danger" onclick={() => remove(s)}>Remove</button></td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </details>
  {/if}
</div>

<style>
  .expander { background: var(--surface); border-radius: var(--radius); box-shadow: var(--shadow-card); padding: 0.8rem 1rem; }
  .expander summary { cursor: pointer; font-weight: 500; }
  .expander[open] summary { margin-bottom: 0.75rem; }
</style>
