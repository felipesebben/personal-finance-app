<!--
  Add expense: one purchase at a time. The form itself is
  sections/EntryForm.svelte (shared with Entries, which edits what's logged here).
-->
<script lang="ts">
  import { get, session } from '../lib/session.svelte'
  import { href } from '../lib/router.svelte'
  import { myUserId, type HouseholdMember } from '../lib/household'
  import { recentTemplates, type Expense } from '../lib/entries'
  import { backfillLines } from '../lib/entryChecks'
  import PageHeader from '../lib/ui/PageHeader.svelte'
  import Lede from '../lib/ui/Lede.svelte'
  import Card from '../lib/ui/Card.svelte'
  import Message from '../lib/ui/Message.svelte'
  import Loading from '../lib/ui/Loading.svelte'
  import EntryForm from '../sections/EntryForm.svelte'

  let expenses = $state<Expense[]>([])
  let household = $state<HouseholdMember[]>([])
  let ready = $state<boolean | null>(null)
  let error = $state('')
  // Bumped after a save so the form starts afresh with the new templates.
  let formKey = $state(0)

  $effect(() => {
    void session.version
    Promise.all([
      get<Expense[]>('expenditures/'), get<HouseholdMember[]>('household_settings/'),
      get<unknown[]>('categories/'), get<unknown[]>('payment_methods/'),
    ]).then(([e, h, c, m]) => {
      expenses = e
      household = h
      ready = c.length > 0 && m.length > 0
    }).catch((e) => (error = e instanceof Error ? e.message : 'Could not load.'))
  })

  const me = $derived(myUserId(household, session.email))
  const templates = $derived(recentTemplates(expenses, me))
  const backfill = $derived(backfillLines(expenses, me))
  const ratio = $derived(household.map((m) => `${m.user.full_name || m.user.email} ${Math.round(Number(m.share_pct) * 100)}%`).join(' · '))
</script>

<PageHeader title="Add expense" purpose="Record one purchase. See how it's going on Our expenses and My expenses." />

<div class="stack">
  <Lede headline="Record one purchase."
    body={` Shared expenses are split between you by the household ratio${ratio ? ` (${ratio})` : ''}; personal ones stay private to you.`} />

  {#if error}
    <Message tone="error">{error}</Message>
  {:else if ready === null}
    <Loading />
  {:else if !ready}
    <Message tone="warn">Add at least one category and one payment method on the <a href={href('settings')}>Settings</a> page first.</Message>
  {:else}
    <Card>
      {#key formKey}
        <EntryForm {templates} onsaved={() => (formKey += 1)} />
      {/key}
    </Card>
    <details class="explain">
      <summary>What does "shared" change?</summary>
      <p>A <b>shared</b> expense is visible to both of you, and each of you bears your share of it by the household
        ratio (or by a custom split you set for that one expense). Turn <b>Shared</b> off for something only you pay
        for: your partner won't see it.</p>
    </details>
    {#if backfill.length}
      <div class="backfill">
        <span class="caption"><b>Where logging has got to</b></span>
        {#each backfill as line}<p class="caption">{line}</p>{/each}
      </div>
    {/if}
  {/if}
</div>

<style>
  .explain { background: var(--surface); border-radius: var(--radius); padding: 0.7rem 0.9rem; }
  .explain summary { cursor: pointer; font-weight: 500; }
  .explain p { margin-top: 0.5rem; color: var(--ink-2); font-size: 0.92rem; }
  .backfill { display: flex; flex-direction: column; gap: 0.3rem; }
</style>
