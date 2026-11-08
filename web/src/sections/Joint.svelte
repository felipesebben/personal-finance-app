<!--
  The joint account: what's left, the spending pace against the usual month,
  deposits and balance checks, and the recent entries. Shapes come from
  lib/joint.ts.
-->
<script lang="ts">
  import { del, get, post, session, showToast } from '../lib/session.svelte'
  import { cents, formatBrl, parseBrl, toApi } from '../lib/money'
  import { nowTime, saoPauloTimestamp, todayIso } from '../lib/dates'
  import {
    THIS_MONTH, brDate, jointCards, paceSentence, paceSeries, type JointEntry, type JointStatus,
  } from '../lib/joint'
  import { BRAND, MUTED } from '../lib/charts/palette'
  import LineChart, { type Series } from '../lib/charts/LineChart.svelte'
  import Card from '../lib/ui/Card.svelte'
  import Kpi from '../lib/ui/Kpi.svelte'
  import Lede from '../lib/ui/Lede.svelte'
  import Loading from '../lib/ui/Loading.svelte'
  import Message from '../lib/ui/Message.svelte'
  import Segmented from '../lib/ui/Segmented.svelte'

  let statuses = $state<JointStatus[] | null>(null)
  let error = $state('')
  let picked = $state<number | null>(null)
  let entries = $state<JointEntry[]>([])

  const status = $derived(statuses?.find((s) => s.payment_method_id === picked) ?? statuses?.[0] ?? null)

  $effect(() => {
    void session.version
    get<JointStatus[]>('joint/status')
      .then((s) => {
        statuses = s
        error = ''
        // The select needs a value to show: the first account until one is picked.
        if (!s.some((x) => x.payment_method_id === picked)) picked = s[0]?.payment_method_id ?? null
      })
      .catch((e) => { statuses = []; error = e.message })
  })

  $effect(() => {
    void session.version
    if (!status) return
    get<JointEntry[]>(`joint/entries?payment_method_id=${status.payment_method_id}`)
      .then((e) => (entries = e)).catch(() => (entries = []))
  })

  const series = $derived.by((): Series[] => {
    if (!status) return []
    const { thisMonth, usual } = paceSeries(status)
    return [
      ...(usual.length ? [{ name: 'Usual', points: usual, color: MUTED, dash: '6 4', width: 2 }] : []),
      ...(thisMonth.length ? [{ name: THIS_MONTH, points: thisMonth, color: BRAND, width: 2.75, dot: true, area: true }] : []),
    ]
  })

  // The entry form.
  let kind = $state<'deposit' | 'balance'>('deposit')
  let amountText = $state('')
  let onDay = $state(todayIso())
  let note = $state('')
  let formError = $state('')
  let busy = $state(false)

  async function save(e: SubmitEvent) {
    e.preventDefault()
    if (!status) return
    formError = ''
    let amount: number
    try {
      amount = parseBrl(amountText)
    } catch (err) {
      formError = (err as Error).message
      return
    }
    busy = true
    try {
      await post('joint/entries', {
        payment_method_id: status.payment_method_id, kind, amount: toApi(amount),
        entry_at: saoPauloTimestamp(onDay, nowTime()), note: note.trim() || null,
      })
      amountText = ''
      note = ''
      showToast(`${kind === 'deposit' ? 'Deposit recorded' : 'Balance updated'}: ${formatBrl(amount)}`)
    } catch (err) {
      formError = (err as Error).message
    } finally {
      busy = false
    }
  }

  async function remove(entry: JointEntry) {
    if (!confirm(`Remove this ${entry.kind === 'deposit' ? 'deposit' : 'balance check'} of ${formatBrl(cents(entry.amount))}?`)) return
    try {
      await del(`joint/entries/${entry.joint_entry_id}`)
      showToast('Entry removed')
    } catch (err) {
      showToast((err as Error).message, 'error')
    }
  }
</script>

<div class="stack">
  <Lede headline="What's left in the account you both top up, and whether it's going faster than usual."
    body=" Spending is whatever you log with the joint card; add money here when you top it up." />

  {#if statuses === null}
    <Loading />
  {:else if error}
    <Message tone="error">Couldn't load the joint account: {error}</Message>
  {:else if status}
    {#if statuses.length > 1}
      <label class="field account">
        <span>Account</span>
        <select bind:value={picked}>
          {#each statuses as s}<option value={s.payment_method_id}>{s.label}</option>{/each}
        </select>
      </label>
    {/if}

    <div class="grid cols-3">
      {#each jointCards(status) as [label, value, lines]}
        <Card minHeight={140}><Kpi {label} {value} {lines} /></Card>
      {/each}
    </div>

    <Card title="Is the account going faster than usual?" subtitle={paceSentence(status)}>
      {#if series.length}
        <LineChart {series} xMax={status.days_in_month} height={300} yTitle="Spent so far" xTitle="Day of the month"
          readoutLabel={(d) => `Day ${d}`} xTicks={[1, 5, 10, 15, 20, 25, status.days_in_month]} />
        {#if !series.some((s) => s.name === 'Usual')}
          <p class="caption">The usual line appears after a full month of spending on this account.</p>
        {:else}
          <p class="caption">Usual = the average of the last three full months on this account, by the same day.</p>
        {/if}
      {/if}
    </Card>

    <Card title="Add money or correct the balance">
      <form class="stack" onsubmit={save}>
        <Segmented label="What happened?" options={['deposit', 'balance'] as ('deposit' | 'balance')[]} bind:value={kind}
          labels={{ deposit: 'Money went in', balance: 'The bank shows this balance' }} />
        <p class="caption">Use the balance option the first time, and whenever the app drifts from what your bank shows (e.g. a purchase nobody logged).</p>
        <div class="grid cols-2">
          <label class="field"><span>Amount (R$)</span>
            <input type="text" inputmode="decimal" placeholder="e.g. 1.500,00" bind:value={amountText} />
          </label>
          <label class="field"><span>Date</span><input type="date" bind:value={onDay} max={todayIso()} /></label>
        </div>
        <label class="field"><span>Note (optional)</span><input type="text" bind:value={note} /></label>
        {#if formError}<Message tone="error">{formError}</Message>{/if}
        <div><button class="btn primary" type="submit" disabled={busy}>Save</button></div>
      </form>
    </Card>

    {#if entries.length}
      <Card title="Recent entries">
        <div class="table-wrap">
          <table class="data">
            <thead><tr><th>Date</th><th>What</th><th class="num">Amount</th><th>Note</th><th></th></tr></thead>
            <tbody>
              {#each entries.slice(0, 20) as e (e.joint_entry_id)}
                <tr>
                  <td>{brDate(e.entry_at)}</td>
                  <td>{e.kind === 'deposit' ? 'Deposit' : 'Balance check'}</td>
                  <td class="num">{formatBrl(cents(e.amount))}</td>
                  <td>{e.note ?? ''}</td>
                  <td><button type="button" class="btn small danger" onclick={() => remove(e)}>Remove</button></td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </Card>
    {/if}
  {:else}
    <Message>No joint account yet: tick Joint on a payment method in Settings.</Message>
  {/if}
</div>

<style>
  .account { max-width: 20rem; }
</style>
