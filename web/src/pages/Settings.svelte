<!--
  Settings, in order: Household (each account's share, you first, 0% = not
  in the household), Categories, Monthly targets, Payment methods, Pets,
  Publish to Tableau and Delete my account. Lists are edited in place and
  saved together after a plan in sentences (lib/settings.ts).
-->
<script lang="ts">
  import { del, endSession, get, post, put, session, showToast } from '../lib/session.svelte'
  import { addMonths, monthLabel, thisMonth } from '../lib/dates'
  import {
    CATEGORIES, PAYMENT_METHODS, PETS, fillRest, householdPayload, suggestTargets, targetRows, targetsPayload,
    type Row,
  } from '../lib/settings'
  import type { TargetRow } from '../lib/targets'
  import type { HouseholdMember } from '../lib/household'
  import type { AnalyticsPayload } from '../lib/briefing'
  import Card from '../lib/ui/Card.svelte'
  import Lede from '../lib/ui/Lede.svelte'
  import Loading from '../lib/ui/Loading.svelte'
  import Message from '../lib/ui/Message.svelte'
  import PageHeader from '../lib/ui/PageHeader.svelte'
  import EditableList from '../sections/settings/EditableList.svelte'

  interface User { user_id: number; email: string; full_name: string | null }

  let users = $state<User[]>([])
  let household = $state<HouseholdMember[]>([])
  let categories = $state<Row[]>([])
  let methods = $state<Row[]>([])
  let pets = $state<Row[]>([])
  let targetSet = $state<TargetRow[]>([])
  let history = $state<AnalyticsPayload | null>(null)
  let loaded = $state(false)
  let loadError = $state('')

  $effect(() => {
    void session.version
    const lastMonth = addMonths(thisMonth(), -1)
    Promise.all([
      get<User[]>('users/'), get<HouseholdMember[]>('household_settings/'), get<Row[]>('categories/'),
      get<Row[]>('payment_methods/'), get<Row[]>('pets/'), get<TargetRow[]>('category_targets/'),
      get<AnalyticsPayload>(`analytics/shared?month=${lastMonth}&months=12`).catch(() => null),
    ]).then(([u, h, c, m, p, t, a]) => {
      users = u; household = h; categories = c; methods = m; pets = p; targetSet = t; history = a
      loaded = true
      loadError = ''
    }).catch((e) => (loadError = e.message))
  })

  const me = $derived(session.email.trim().toLowerCase())
  const mine = $derived(users.find((u) => u.email.toLowerCase() === me) ?? null)

  // --- Household -------------------------------------------------------------
  const people = $derived([...users].sort((a, b) =>
    Number(a.email.toLowerCase() !== me) - Number(b.email.toLowerCase() !== me) ||
    (a.full_name ?? '').localeCompare(b.full_name ?? '')))
  let shares = $state<Record<number, number | string>>({})
  $effect(() => {
    const current = new Map(household.map((s) => [s.user_id, Number(s.share_pct) * 100]))
    shares = Object.fromEntries(users.map((u) => [u.user_id, String(Number((current.get(u.user_id) ?? 0).toFixed(2)))]))
  })
  const shareMap = $derived(new Map(Object.entries(shares).map(([id, v]) => [Number(id), Number(String(v).replace(',', '.')) || 0])))
  const split = $derived(householdPayload(shareMap))
  const splitChanged = $derived.by(() => {
    const now = new Map(split[0].map((s) => [s.user_id, s.share_pct]))
    const before = new Map(household.map((s) => [s.user_id, Number(Number(s.share_pct).toFixed(4))]))
    return now.size !== before.size || [...now].some(([id, v]) => before.get(id) !== v)
  })
  function shareChanged(id: number) {
    const filled = fillRest(shareMap, id)
    shares = Object.fromEntries([...filled].map(([k, v]) => [k, String(Number(v.toFixed(2)))]))
  }
  async function saveSplit() {
    try {
      await put('household_settings/', { settings: split[0] })
      showToast('Household split saved.')
    } catch (e) {
      showToast((e as Error).message, 'error')
    }
  }

  // --- Monthly targets ---------------------------------------------------------
  const suggestion = $derived(suggestTargets(history))
  let fillBlanks = $state(false)
  let targetTexts = $state<Record<string, string>>({})
  const targetView = $derived(targetRows(categories as { primary_category: string; sub_category?: string | null }[],
    targetSet, suggestion[0], fillBlanks))
  $effect(() => {
    targetTexts = Object.fromEntries(targetView.map((r) => [r.name, r.target]))
  })
  const averaged = $derived(suggestion[1])
  let targetError = $state('')
  async function saveTargets() {
    const [found, problems] = targetsPayload(targetView.map((r) => ({ name: r.name, target: targetTexts[r.name] ?? '' })))
    if (problems.length) { targetError = `Not saved: ${problems.join(' ')}`; return }
    targetError = ''
    try {
      await put('category_targets/', { targets: found })
      fillBlanks = false
      showToast(`Targets saved: ${found.length} categor${found.length === 1 ? 'y' : 'ies'}.`)
    } catch (e) {
      targetError = (e as Error).message
    }
  }

  // --- Tableau and account -------------------------------------------------------
  let etl = $state<{ busy: boolean; message: string; tone: 'ok' | 'error' }>({ busy: false, message: '', tone: 'ok' })
  async function runEtl() {
    etl = { busy: true, message: '', tone: 'ok' }
    try {
      const r = await post<{ message?: string }>('refresh')
      etl = { busy: false, message: r?.message ?? 'Published to Tableau.', tone: 'ok' }
    } catch (e) {
      etl = { busy: false, message: `Publishing failed: ${(e as Error).message}`, tone: 'error' }
    }
  }

  let deleteError = $state('')
  async function deleteMe() {
    if (!mine || !confirm('Delete your account? This cannot be undone.')) return
    try {
      await del(`users/${mine.user_id}`)
      endSession(null)
    } catch (e) {
      deleteError = (e as Error).message
    }
  }
</script>

<PageHeader title="Settings" purpose="Who shares expenses and how, and the lists Add expense offers." />

{#if loadError}
  <Message tone="error">Couldn't load the settings: {loadError}</Message>
{:else if !loaded}
  <Loading />
{:else}
  <div class="stack">
    <Card title="Household">
      <Lede headline="Who shares expenses, and in what proportion."
        body=" Set each person's share from your incomes, e.g. 60/40. It applies to expenses saved from now on; earlier ones keep the split they were saved with. Leave someone at 0% to keep them out." />
      {#each people as person (person.user_id)}
        <div class="person">
          <div>
            <b>{person.full_name || person.email}</b>{#if person.email.toLowerCase() === me}<span class="muted"> (you)</span>{/if}
            <div class="caption">{person.email}</div>
          </div>
          <label class="field share" title="Change one and the other person's share becomes the rest.">
            <span>Share (%)</span>
            <input type="number" min="0" max="100" step="1" inputmode="decimal" bind:value={shares[person.user_id]}
              oninput={() => shareChanged(person.user_id)} />
          </label>
        </div>
      {/each}
      {#if people.length < 2}
        <p class="caption">Adding your partner: they open this app's login page and choose <b>Sign up</b> with their email. Once they have, they appear here and you can give them a share.</p>
      {/if}
      {#if split[1]}<Message tone="warn">{split[1]}</Message>{/if}
      <div><button class="btn primary" type="button" disabled={!!split[1] || !splitChanged} onclick={saveSplit}>Save split</button></div>
    </Card>

    <Card title="Categories">
      <Lede headline="Edit right in the list."
        body=" Type over a name to rename it, add a row at the bottom, or remove one. Renaming also relabels past expenses. Tick Pets for pet costs: Add expense then asks which pet." />
      <EditableList original={categories} table={CATEGORIES} endpoint="categories" columns={[
        { field: 'primary_category', label: 'Category', kind: 'text' },
        { field: 'sub_category', label: 'Sub-category', kind: 'text' },
        { field: 'cost_type', label: 'Cost type', kind: 'select', options: ['Variable', 'Fixed'], default: 'Variable',
          help: "Fixed costs repeat every month (rent, internet); variable ones don't." },
        { field: 'for_pets', label: 'Pets', kind: 'check', help: 'Add expense asks which pet it was for.' },
      ]} />
    </Card>

    <Card title="Monthly targets">
      <Lede headline="What you mean to spend a month, per category."
        body=" Our expenses draws it as a dark tick on each category's bar, next to last month's grey one. For shared spending, at full price. Leave blank for no target. A sub-category (Pets › Grooming) can have its own, to follow a decision like fewer sessions." />
      {#if !targetView.length}
        <p class="caption">Add a category first.</p>
      {:else}
        {#if averaged.length}
          <div class="row between">
            <p class="caption">Suggested: the average of {monthLabel(averaged[0])}{averaged.length > 1 ? ` to ${monthLabel(averaged.at(-1)!)}` : ''}, rounded up to R$ 50. A starting point; change it freely.</p>
            <button type="button" class="btn small" onclick={() => (fillBlanks = true)}>Fill blank targets with the suggestions</button>
          </div>
        {/if}
        <div class="table-wrap">
          <table class="data targets">
            <thead><tr><th>Category</th><th>Target (R$ a month)</th><th class="num">Suggested</th></tr></thead>
            <tbody>
              {#each targetView as r (r.name)}
                <tr class:sub={r.sub}>
                  <td>{r.sub ? r.name.split(' › ')[1] : r.name}</td>
                  <td><input type="text" inputmode="decimal" placeholder="e.g. 3.000,00" aria-label="Target for {r.name}"
                    bind:value={targetTexts[r.name]} /></td>
                  <td class="num muted">{r.suggested}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        {#if targetError}<Message tone="error">{targetError}</Message>{/if}
        <div><button type="button" class="btn primary" onclick={saveTargets}>Save targets</button></div>
      {/if}
    </Card>

    <Card title="Payment methods">
      <Lede headline="One row per way you pay, e.g. Pix · Nubank."
        body=" Add expense asks for the bank whenever a method has one. Tick Credit for credit cards so it offers installments, and Joint for an account you both fund (name it apart from a personal card at the same bank, e.g. Nubank Conjunta)." />
      <EditableList original={methods} table={PAYMENT_METHODS} endpoint="payment_methods" columns={[
        { field: 'method_name', label: 'Method', kind: 'text', placeholder: 'e.g. Pix' },
        { field: 'institution', label: 'Bank / account', kind: 'text', placeholder: 'blank for Cash' },
        { field: 'is_credit', label: 'Credit', kind: 'check', help: 'Credit cards offer installments.' },
        { field: 'is_joint', label: 'Joint', kind: 'check',
          help: 'An account you both top up in advance: what it pays for never makes either of you owe the other.' },
      ]} />
    </Card>

    <Card title="Pets">
      <Lede headline="Who the pet expenses are for."
        body=" For a category ticked Pets, Add expense asks which pet it was, or Both for one expense shared by all of them." />
      <EditableList original={pets} table={PETS} endpoint="pets" columns={[
        { field: 'name', label: 'Name', kind: 'text' },
      ]} />
    </Card>

    <Card title="Publish to Tableau"
      subtitle="Sends the latest data to the Tableau dashboard. Only needed when you want Tableau up to date; the app's own pages are always live.">
      <div><button type="button" class="btn" disabled={etl.busy} onclick={runEtl}>{etl.busy ? 'Publishing… (this may take a moment)' : 'Publish now'}</button></div>
      {#if etl.message}<Message tone={etl.tone}>{etl.message}</Message>{/if}
    </Card>

    {#if mine}
      <details class="danger-zone">
        <summary>Delete my account</summary>
        <p class="caption">Only possible while no expenses or settlements are recorded under your name.</p>
        {#if deleteError}<Message tone="error">{deleteError}</Message>{/if}
        <div><button type="button" class="btn danger" onclick={deleteMe}>Delete my account</button></div>
      </details>
    {/if}
  </div>
{/if}

<style>
  .person { display: flex; justify-content: space-between; align-items: center; gap: 1rem; padding: 0.4rem 0;
    border-bottom: 1px solid var(--hairline); }
  .share { width: 7.5rem; flex: none; }
  .between { justify-content: space-between; align-items: center; }
  table.targets td { vertical-align: middle; padding: 0.3rem 0.5rem; }
  table.targets input { min-height: 2.2rem; padding: 0.3rem 0.5rem; max-width: 12rem; }
  tr.sub td:first-child { padding-left: 1.5rem; color: var(--ink-2); }
  tr.sub td:first-child::before { content: '› '; color: var(--muted); }
  .danger-zone { background: var(--surface); border-radius: var(--radius); box-shadow: var(--shadow-card); padding: 0.8rem 1rem;
    display: flex; flex-direction: column; gap: 0.6rem; }
  .danger-zone summary { cursor: pointer; font-weight: 500; }
  .danger-zone[open] summary { margin-bottom: 0.6rem; }
</style>
