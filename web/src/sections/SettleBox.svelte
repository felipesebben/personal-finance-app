<!--
  Who owes whom for `period` ("YYYY-MM" or "All time") and, for each debt,
  the action in the viewer's own voice: one button for the whole amount
  (paid today) and a field for a different one. Shared by Settle up and
  the monthly recap. `onreport` hands the balance report to the parent.
-->
<script lang="ts">
  import { get, post, session, showToast } from '../lib/session.svelte'
  import { myUserId, type HouseholdMember } from '../lib/household'
  import { cents, formatBrl, parseBrl, toApi } from '../lib/money'
  import { nowTime, saoPauloTimestamp, todayIso } from '../lib/dates'
  import { ALL_TIME, actionLabels, periodLabel, type BalanceReport } from '../lib/settle'
  import Callout from '../lib/ui/Callout.svelte'
  import Loading from '../lib/ui/Loading.svelte'
  import Message from '../lib/ui/Message.svelte'

  let { period, key, onreport }: {
    period: string
    key: string
    onreport?: (report: BalanceReport | null) => void
  } = $props()

  let report = $state<BalanceReport | null>(null)
  let me = $state<number | null>(null)
  let loading = $state(true)
  let error = $state('')
  let others = $state<Record<number, string>>({})
  let fieldErrors = $state<Record<number, string>>({})
  let busy = $state(false)

  const label = $derived(periodLabel(period))
  const month = $derived(period === ALL_TIME ? null : period)

  $effect(() => {
    void session.version
    const path = period === ALL_TIME ? 'balances/' : `balances/?month=${period}`
    loading = true
    Promise.all([get<BalanceReport>(path), get<HouseholdMember[]>('household_settings/')])
      .then(([r, household]) => {
        report = r
        me = myUserId(household, session.email)
        error = ''
        onreport?.(r)
      })
      .catch((e) => {
        report = null
        error = e.message
        onreport?.(null)
      })
      .finally(() => (loading = false))
  })

  async function record(fromId: number, toId: number, amount: number) {
    busy = true
    try {
      await post('settlements/', {
        settled_at: saoPauloTimestamp(todayIso(), nowTime()),
        from_user_id: fromId,
        to_user_id: toId,
        amount: toApi(amount),
        month,
        note: null,
      })
      showToast(`Payment recorded: ${formatBrl(amount)}. Made a mistake? Remove it under Payments recorded.`)
      others = {}
    } catch (e) {
      showToast((e as Error).message, 'error')
    } finally {
      busy = false
    }
  }

  function recordOther(i: number, fromId: number, toId: number) {
    try {
      const amount = parseBrl(others[i] ?? '')
      fieldErrors = { ...fieldErrors, [i]: '' }
      void record(fromId, toId, amount)
    } catch (e) {
      fieldErrors = { ...fieldErrors, [i]: (e as Error).message }
    }
  }
</script>

{#if loading && !report}
  <Loading height={90} />
{:else if error}
  <Message tone="error">Couldn't load the balance: {error}</Message>
{:else if report}
  {#if !report.transfers.length}
    <Callout label="All square" detail="Nobody owes anything for {label}." />
  {:else}
    {#each report.transfers as t, i (`${key}-${i}`)}
      {@const words = actionLabels(t, me)}
      <div class="debt">
        <Callout label="{t.from_name} owes {t.to_name}" amount={formatBrl(cents(t.amount))}
          detail="for {label} · after payments already recorded" />
        <button type="button" class="btn primary wide" disabled={busy}
          title="Records it as paid today, squaring up {label}."
          onclick={() => record(t.from_user_id, t.to_user_id, cents(t.amount))}>✓ {words.all}</button>
        <div class="other">
          <label class="field">
            <span>Amount (R$)</span>
            <input type="text" inputmode="decimal" placeholder="0,00" bind:value={others[i]} />
            {#if fieldErrors[i]}<span class="error">Amount: {fieldErrors[i]}</span>{/if}
          </label>
          <button type="button" class="btn" disabled={busy} onclick={() => recordOther(i, t.from_user_id, t.to_user_id)}>
            {words.other}
          </button>
        </div>
      </div>
    {/each}
  {/if}
{/if}

<style>
  .debt { display: flex; flex-direction: column; gap: 0.6rem; margin-bottom: 0.75rem; }
  .wide { width: 100%; }
  .other { display: grid; grid-template-columns: 2fr 3fr; gap: 0.75rem; align-items: end; }
  @media (max-width: 560px) {
    .other { grid-template-columns: 1fr; }
  }
</style>
