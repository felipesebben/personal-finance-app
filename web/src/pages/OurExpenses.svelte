<!--
  Our expenses: how the household's shared spending is doing. This month day
  by day against earlier months, month by month, a monthly recap to review
  together, the joint account (when there is one and you're in the
  household) and who owes whom.
-->
<script lang="ts">
  import { get, session } from '../lib/session.svelte'
  import { route } from '../lib/router.svelte'
  import { myUserId, type HouseholdMember } from '../lib/household'
  import PageHeader from '../lib/ui/PageHeader.svelte'
  import Tabs from '../lib/ui/Tabs.svelte'
  import Daily from '../sections/Daily.svelte'
  import Overview from '../sections/Overview.svelte'
  import Recap from '../sections/Recap.svelte'
  import Joint from '../sections/Joint.svelte'
  import Settle from '../sections/Settle.svelte'

  let hasJoint = $state(false)

  $effect(() => {
    void session.version
    Promise.all([
      get<{ is_joint?: boolean }[]>('payment_methods/'),
      get<HouseholdMember[]>('household_settings/'),
    ]).then(([methods, household]) => {
      hasJoint = methods.some((m) => m.is_joint) && myUserId(household, session.email) !== null
    }).catch(() => (hasJoint = false))
  })

  const tabs = $derived([
    { id: 'month', label: 'This month' },
    { id: 'trend', label: 'Month by month' },
    { id: 'recap', label: 'Monthly recap' },
    ...(hasJoint ? [{ id: 'joint', label: 'Joint account' }] : []),
    { id: 'settle', label: 'Settle up' },
  ])
  const active = $derived(tabs.some((t) => t.id === route.tab) ? route.tab : 'month')
</script>

<PageHeader title="Our expenses" purpose="How our shared spending is doing this month, against earlier months." />
<Tabs {tabs} />

{#if active === 'month'}
  <Daily lens="Household" key="our" />
{:else if active === 'trend'}
  <Overview lens="Household" key="our" />
{:else if active === 'recap'}
  <Recap />
{:else if active === 'joint'}
  <Joint />
{:else if active === 'settle'}
  <Settle />
{/if}
