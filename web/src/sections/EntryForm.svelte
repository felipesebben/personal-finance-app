<!--
  The expense form, shared by Add expense (a new expense, POST) and Entries
  (an existing one, PATCH, its fields filled in). One form, so an edit
  follows exactly the rules of an entry: cascading selects, credit-only
  installments, the joint-account lock, "it's on me", a pet for a pet
  category, a custom split and the live price preview.

  Without `expense` it adds one, asking first about a likely duplicate (the
  API's 409); `templates` adds a "Log again" row that fills the form in from
  a recent expense, dated now and with no price. With `expense` it edits that
  one, sending only what changed. The request bodies are built in
  lib/entryPayload.ts.
-->
<script lang="ts">
  import { onMount } from 'svelte'
  import { ApiError, get, keepAlive, patch, post, session, showToast } from '../lib/session.svelte'
  import { nowTime, todayIso } from '../lib/dates'
  import { myUserId, type HouseholdMember } from '../lib/household'
  import { entryPreview, formatBrl, parseBrl } from '../lib/money'
  import {
    ALL_PETS, NO_INSTITUTION, formValues, type CategoryRef, type Expense, type FormValues, type MethodRef, type PetRef,
  } from '../lib/entries'
  import { duplicateLines, type Duplicate } from '../lib/entryChecks'
  import { createPayload, editPayload, findMethod, missingFields, type FormState, type Payload } from '../lib/entryPayload'
  import { fillRest } from '../lib/shares'
  import Segmented from '../lib/ui/Segmented.svelte'
  import Message from '../lib/ui/Message.svelte'
  import Loading from '../lib/ui/Loading.svelte'

  let { expense = null, templates = [], onsaved, submitLabel = '' }: {
    expense?: Expense | null
    templates?: [string, Expense][]
    onsaved?: () => void
    submitLabel?: string
  } = $props()

  const INSTALLMENT_PICKS = ['1', '2', '3', '6', '10', '12', 'Other']
  const INSTALLMENT_LABELS: Record<string, string> = Object.fromEntries(
    INSTALLMENT_PICKS.map((p) => [p, p === 'Other' ? 'Other' : `${p}x`]))
  const NATURES = ['Normal', 'Extraordinary', 'Recurring', 'Annual']
  const NATURE_HELP = 'Normal: everyday · Extraordinary: unplanned or an emergency · Recurring: a monthly bill or '
    + 'subscription · Annual: once a year (IPVA, IPTU)'

  // --- What the form picks from ---
  let categories = $state<CategoryRef[]>([])
  let methods = $state<MethodRef[]>([])
  let household = $state<HouseholdMember[]>([])
  let pets = $state<PetRef[]>([])
  let loaded = $state(false)
  let loadError = $state('')

  const me = $derived(myUserId(household, session.email))
  const names = $derived(Object.fromEntries(household.map((m) => [m.user_id, m.user.full_name || m.user.email])))

  // --- The form's values ---
  let priceText = $state('')
  let method = $state('')
  let institution = $state('')
  let instPick = $state('1')
  let instOther = $state(2)
  let currentInst = $state(1)
  let primary = $state('')
  let sub = $state('')
  let pet = $state('')
  let shared = $state(true)
  let treat = $state(false)
  let custom = $state(false)
  let customShares = $state<Record<number, number>>({})
  let nature = $state('Normal')
  let date = $state(todayIso())
  let time = $state(nowTime())

  let original = $state<FormValues | null>(null)
  let pickedTemplate = $state('')
  let pending = $state<{ payload: Payload; duplicates: Duplicate[] } | null>(null)
  let errors = $state<string[]>([])
  let busy = $state(false)
  let priceInput = $state<HTMLInputElement | null>(null)

  onMount(async () => {
    try {
      ;[categories, methods, household, pets] = await Promise.all([
        get<CategoryRef[]>('categories/'), get<MethodRef[]>('payment_methods/'),
        get<HouseholdMember[]>('household_settings/'), get<PetRef[]>('pets/'),
      ])
      if (expense) {
        original = formValues(expense, pets, names)
        fill(original)
      } else {
        fill(null)
      }
    } catch (e) {
      loadError = e instanceof Error ? e.message : 'Could not load the form.'
    } finally {
      loaded = true
    }
  })

  /** Sets every field: from an expense's values, or empty and dated now. */
  function fill(v: FormValues | null) {
    priceText = v?.priceText ?? ''
    method = v?.method ?? ''
    institution = v ? v.institution : ''
    const total = v?.totalInstallments ?? 1
    instPick = INSTALLMENT_PICKS.includes(String(total)) ? String(total) : 'Other'
    instOther = INSTALLMENT_PICKS.includes(String(total)) ? 2 : total
    currentInst = v?.currentInstallment ?? 1
    primary = v?.primary ?? ''
    sub = v?.sub ?? ''
    pet = v?.pet ?? ''
    shared = v ? v.shared : true
    treat = v?.treat ?? false
    custom = !!v?.custom
    customShares = v?.custom ? { ...v.custom } : {}
    nature = v?.nature ?? 'Normal'
    date = v?.date ?? todayIso()
    time = v?.time ?? nowTime()
    errors = []
    pending = null
  }

  function useTemplate(label: string) {
    const t = templates.find(([l]) => l === label)?.[1]
    if (!t) return
    pickedTemplate = label
    fill({ ...formValues(t, pets, names), priceText: '', date: todayIso(), time: nowTime() })
    priceInput?.focus()
  }

  // --- Cascading choices ---
  const methodNames = $derived([...new Set(methods.map((m) => m.method_name))].sort((a, b) => a.localeCompare(b)))
  const institutions = $derived.by(() => {
    if (!method) return { options: [] as string[], locked: true }
    const rows = methods.filter((m) => m.method_name === method)
    const named = [...new Set(rows.map((m) => m.institution).filter((x): x is string => !!x))].sort()
    const blank = rows.some((m) => !m.institution)
    return { options: [...named, ...(blank ? [NO_INSTITUTION] : [])], locked: !named.length }
  })
  const primaries = $derived([...new Set(categories.map((c) => c.primary_category))].sort((a, b) => a.localeCompare(b)))
  const subs = $derived(primary
    ? [...new Set(categories.filter((c) => c.primary_category === primary).map((c) => c.sub_category))].sort()
    : [])

  function pickMethod(value: string) {
    method = value
    const rows = methods.filter((m) => m.method_name === value)
    const named = rows.filter((m) => m.institution)
    institution = !named.length && rows.length ? NO_INSTITUTION : named.length === 1 && !rows.some((m) => !m.institution)
      ? named[0].institution! : ''
  }
  function pickPrimary(value: string) {
    primary = value
    const options = categories.filter((c) => c.primary_category === value)
    sub = options.length === 1 ? options[0].sub_category : ''
  }

  // --- What follows from the choices ---
  const isCredit = $derived(!!methods.find((m) => m.method_name === method)?.is_credit)
  const totalInst = $derived(!isCredit ? 1 : instPick === 'Other' ? Math.max(2, Math.floor(instOther || 2)) : Number(instPick))
  const currentClamped = $derived(totalInst > 1 ? Math.min(Math.max(1, Math.floor(currentInst || 1)), totalInst) : 1)
  const isJoint = $derived(!!(method && institution && findMethod(methods, method, institution)?.is_joint))
  const isShared = $derived(isJoint || shared)
  const isPetCategory = $derived(!!categories.find((c) => c.primary_category === primary && c.sub_category === sub)?.for_pets)
  const sortedPets = $derived([...pets].sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase())))
  const petId = $derived.by(() => {
    if (!isPetCategory || !pets.length) return null
    if (pets.length === 1) return pets[0].pet_id
    return pets.find((p) => p.name === pet)?.pet_id ?? null
  })
  const petMissing = $derived(isPetCategory && pets.length > 1 && !pet)
  const others = $derived(household.filter((m) => m.user_id !== me).map((m) => m.user.full_name || m.user.email))
  const members = $derived([...household].sort((a, b) => Number(a.user_id !== me) - Number(b.user_id !== me)))
  const customTotal = $derived(members.reduce((t, m) => t + (customShares[m.user_id] ?? 0), 0))

  function toggleCustom(on: boolean) {
    custom = on
    if (on && !Object.keys(customShares).length) {
      customShares = Object.fromEntries(household.map((m) => [m.user_id, Math.round(Number(m.share_pct) * 100)]))
    }
  }
  function setShare(uid: number, value: number) {
    const v = Math.min(100, Math.max(0, Math.round(Number.isFinite(value) ? value : 0)))
    customShares = fillRest({ ...customShares, [uid]: v }, uid)
  }

  const price = $derived.by(() => {
    if (!priceText.trim()) return { cents: null as number | null, error: '' }
    try {
      return { cents: parseBrl(priceText), error: '' }
    } catch (e) {
      return { cents: null, error: (e as Error).message }
    }
  })

  const preview = $derived.by(() => {
    if (price.cents === null) return ''
    let shares: [number, number][] | null = null
    if (isShared) {
      if (custom && household.length) shares = members.map((m) => [m.user_id, (customShares[m.user_id] ?? 0) / 100])
      else if (original?.wasShared) shares = original.split
      else shares = household.map((m) => [m.user_id, Number(m.share_pct)])
    }
    return entryPreview(price.cents, totalInst, shares, me)
  })

  function formState(): FormState {
    return {
      price: price.cents, priceError: price.error, method, institution, totalInstallments: totalInst,
      currentInstallment: currentClamped, primary, sub, petId, petMissing, shared: isShared,
      treat: !isJoint && treat, nature, date, time,
      customShares: isShared && custom && household.length ? members.map((m) => [m.user_id, customShares[m.user_id] ?? 0]) : null,
    }
  }

  function done(message: string) {
    showToast(message)
    pickedTemplate = ''
    if (!expense) fill(null)
    onsaved?.()
  }

  async function send(payload: Payload) {
    busy = true
    try {
      await post('expenditures/', payload)
      pending = null
      done(`Expense saved: ${formatBrl(price.cents ?? 0)}`)
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const detail = e.detail as { duplicates?: Duplicate[] } | null
        pending = { payload, duplicates: detail?.duplicates ?? [] }
      } else {
        errors = [e instanceof Error ? e.message : 'Could not save.']
      }
    } finally {
      busy = false
    }
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault()
    void keepAlive()
    const s = formState()
    errors = missingFields(s).length ? [`Please fill in: ${missingFields(s).join(', ')}`] : []
    if (errors.length) return
    try {
      if (!expense || !original) {
        await send(createPayload(s, categories, methods))
        return
      }
      const body = editPayload(s, expense, original, categories, methods)
      if (!Object.keys(body).length) {
        errors = ['Nothing changed.']
        return
      }
      busy = true
      await patch(`expenditures/${expense.expenditure_id}`, body)
      done(`Expense updated: ${formatBrl(price.cents ?? 0)}`)
    } catch (e) {
      errors = [e instanceof Error ? e.message : 'Could not save.']
    } finally {
      busy = false
    }
  }
</script>

{#if !loaded}
  <Loading text="Loading the form…" />
{:else if loadError}
  <Message tone="error">{loadError}</Message>
{:else}
  <form class="form" onsubmit={submit} novalidate>
    {#if templates.length && !expense}
      <div class="field">
        <span>Log again</span>
        <div class="chips">
          {#each templates as [label]}
            <button type="button" class="chip" class:active={pickedTemplate === label} onclick={() => useTemplate(label)}>{label}</button>
          {/each}
        </div>
        {#if pickedTemplate}<span class="hint">Filled in from {pickedTemplate}. Type the price.</span>
        {:else}<span class="hint">Your recent expenses: pick one to fill the form in, then type the price.</span>{/if}
      </div>
    {/if}

    <label class="field price">
      <span>Price (R$)</span>
      <input bind:this={priceInput} type="text" inputmode="decimal" autocomplete="off" placeholder="0,00"
        bind:value={priceText} aria-invalid={!!price.error} />
      {#if price.error}<span class="error">{price.error}</span>
      {:else if preview}<span class="preview">{preview}</span>
      {:else}<span class="hint">Type it the Brazilian way, e.g. 1.234,56. For installments, the full price.</span>{/if}
    </label>

    <div class="pair">
      <label class="field">
        <span>Payment method</span>
        <select value={method} onchange={(e) => pickMethod(e.currentTarget.value)}>
          <option value="" disabled>Select…</option>
          {#each methodNames as m}<option value={m}>{m}</option>{/each}
        </select>
      </label>
      <label class="field">
        <span>Institution</span>
        <select bind:value={institution} disabled={institutions.locked}>
          <option value="" disabled>Select…</option>
          {#each institutions.options as i}<option value={i}>{i}</option>{/each}
        </select>
      </label>
    </div>
    {#if institution === NO_INSTITUTION && method && method !== 'Cash'}
      <p class="hint">Want to record which account paid? Add e.g. {method} · Nubank in Settings → Payment methods.</p>
    {/if}

    {#if isCredit}
      <div class="pair">
        <Segmented label="Installments" options={INSTALLMENT_PICKS} labels={INSTALLMENT_LABELS} bind:value={instPick} />
        {#if instPick === 'Other'}
          <label class="field">
            <span>Number of installments</span>
            <input type="number" min="2" step="1" inputmode="numeric" bind:value={instOther} />
          </label>
        {/if}
      </div>
      {#if totalInst > 1}
        <label class="field narrow">
          <span>Installment billed this month</span>
          <input type="number" min="1" max={totalInst} step="1" inputmode="numeric" bind:value={currentInst} />
          <span class="hint">1 if you bought it today; e.g. 4 if you're already paying installment 4 of {totalInst}.</span>
        </label>
      {/if}
    {/if}

    <div class="pair">
      <label class="field">
        <span>Category</span>
        <select value={primary} onchange={(e) => pickPrimary(e.currentTarget.value)}>
          <option value="" disabled>Select…</option>
          {#each primaries as p}<option value={p}>{p}</option>{/each}
        </select>
      </label>
      <label class="field">
        <span>Sub-category</span>
        <select bind:value={sub} disabled={!primary}>
          <option value="" disabled>Select…</option>
          {#each subs as s}<option value={s}>{s}</option>{/each}
        </select>
      </label>
    </div>

    {#if isPetCategory}
      {#if !pets.length}
        <p class="hint">Want to know what each pet costs? Add them in Settings → Pets.</p>
      {:else if pets.length === 1}
        <p class="hint">For {pets[0].name}.</p>
      {:else}
        <Segmented label="Which pet?" options={[...sortedPets.map((p) => p.name), ALL_PETS]} bind:value={pet} />
        <p class="hint">{ALL_PETS}: one expense for all of them, e.g. a bag of food they share.</p>
      {/if}
    {/if}

    <div class="who">
      {#if isJoint}
        <label class="check"><input type="checkbox" checked disabled /> Shared household expense</label>
        <p class="hint">Paid from the joint account, so nobody owes anything for this. It still counts towards each person's share of spending.</p>
      {:else}
        <label class="check"><input type="checkbox" bind:checked={shared} /> Shared household expense</label>
        <p class="hint">On: split between you by the household ratio and visible to both. Off: only yours, private to you.</p>
        {#if shared}
          <label class="check"><input type="checkbox" bind:checked={treat} />
            It's on me: {others.join(' and ') || 'your partner'} doesn't pay their share back</label>
        {/if}
      {/if}

      {#if isShared && household.length}
        <label class="check"><input type="checkbox" checked={custom} onchange={(e) => toggleCustom(e.currentTarget.checked)} />
          Custom split for this expense</label>
        {#if custom}
          <div class="shares">
            {#each members as m (m.user_id)}
              <label class="field">
                <span>{m.user.full_name || m.user.email} %</span>
                <input type="number" min="0" max="100" step="5" inputmode="numeric" value={customShares[m.user_id] ?? 0}
                  oninput={(e) => setShare(m.user_id, e.currentTarget.valueAsNumber)} />
              </label>
            {/each}
          </div>
          {#if customTotal !== 100}<p class="error">Shares add up to {customTotal}%, not 100%.</p>{/if}
        {:else if original?.wasShared && original.custom === null}
          <p class="hint">Split as when it was logged: {original.splitText}.</p>
        {/if}
      {/if}
      {#if !household.length && isShared}
        <Message tone="warn">No household split is set yet, so a shared expense can't be saved. Set it in Settings.</Message>
      {/if}
    </div>

    <div>
      <Segmented label="Nature" options={NATURES} bind:value={nature} />
      <p class="hint nature">{NATURE_HELP}</p>
    </div>

    <div class="pair">
      <label class="field"><span>Date</span><input type="date" bind:value={date} required /></label>
      <label class="field"><span>Time</span><input type="time" bind:value={time} required /></label>
    </div>

    {#each errors as e}<Message tone="error">{e}</Message>{/each}

    {#if pending}
      <div class="duplicate">
        <Message tone="warn">This looks like an expense that's already logged.</Message>
        <ul>{#each duplicateLines(pending.duplicates) as line}<li>{line}</li>{/each}</ul>
        <div class="pair">
          <button type="button" class="btn" disabled={busy}
            onclick={() => pending && send({ ...pending.payload, allow_duplicate: true })}>Save anyway</button>
          <button type="button" class="btn primary" onclick={() => (pending = null)}>Don't save</button>
        </div>
      </div>
    {:else}
      <button type="submit" class="btn primary submit" disabled={busy}>
        {busy ? 'Saving…' : submitLabel || (expense ? 'Save changes' : 'Save expense')}
      </button>
    {/if}
  </form>
{/if}

<style>
  .form { display: flex; flex-direction: column; gap: 1rem; }
  .pair { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.75rem; align-items: end; }
  .price { max-width: 24rem; }
  .price input { font-size: 1.35rem; font-weight: 600; min-height: 3rem; }
  .narrow { max-width: 16rem; }
  .preview { font-size: 0.88rem; color: var(--brand-strong); font-weight: 500; }
  .hint { font-size: 0.82rem; color: var(--muted); }
  .nature { margin-top: 0.3rem; }
  .error { font-size: 0.85rem; color: var(--more); }
  .who { display: flex; flex-direction: column; gap: 0.5rem; }
  .who .check { min-height: 2.2rem; }
  .shares { display: grid; grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr)); gap: 0.75rem; max-width: 24rem; }
  .chips { display: flex; flex-wrap: wrap; gap: 0.35rem; }
  .chip { border: 1px solid var(--line); background: var(--surface); border-radius: 999px; padding: 0.4rem 0.8rem;
    min-height: 2.3rem; cursor: pointer; font-size: 0.88rem; text-align: left; }
  .chip:hover { border-color: var(--brand); }
  .chip.active { background: var(--brand-soft); border-color: var(--brand); color: var(--brand-strong); }
  .duplicate { display: flex; flex-direction: column; gap: 0.6rem; border: 1px solid var(--line);
    border-radius: var(--radius); padding: 0.8rem; }
  .duplicate ul { margin: 0; padding-left: 1.2rem; font-size: 0.9rem; }
  .submit { min-height: 3rem; font-size: 1.05rem; align-self: flex-start; min-width: 12rem; }
  @media (max-width: 560px) {
    .pair { grid-template-columns: minmax(0, 1fr); }
    .submit { align-self: stretch; }
  }
</style>
