<!--
  The login briefing on Home: how this month is going, in a few sentences
  (lib/briefing.ts). Settle up and joint lines only for household members.
  Nothing drawn when there's nothing to say.
-->
<script lang="ts">
  import { get, session } from '../lib/session.svelte'
  import { monthName, thisMonth } from '../lib/dates'
  import { myUserId, type HouseholdMember } from '../lib/household'
  import { jointLines, mergeForMine, settleLine, spendingLine, type AnalyticsPayload } from '../lib/briefing'
  import type { JointStatus } from '../lib/joint'
  import type { BalanceReport } from '../lib/settle'
  import Card from '../lib/ui/Card.svelte'

  let lines = $state<string[]>([])

  const optional = <T,>(p: Promise<T>): Promise<T | null> => p.catch(() => null)

  $effect(() => {
    void session.version
    const month = thisMonth()
    // Four months: this one plus the three that make "usual".
    const query = `month=${month}&months=4`
    Promise.all([
      optional(get<AnalyticsPayload>(`analytics/shared?${query}`)),
      optional(get<AnalyticsPayload>(`analytics/personal?${query}`)),
      optional(get<HouseholdMember[]>('household_settings/')),
    ]).then(async ([shared, personal, household]) => {
      const me = myUserId(household, session.email)
      const inHousehold = (household ?? []).some((m) => m.user_id === me)
      const out: (string | null)[] = [
        spendingLine('Shared', shared, 'household', true),
        spendingLine('Yours', mergeForMine(shared, personal), 'mine'),
      ]
      if (inHousehold) {
        const [balances, joint] = await Promise.all([
          optional(get<BalanceReport>(`balances/?month=${month}`)),
          optional(get<JointStatus[]>('joint/status')),
        ])
        out.push(settleLine(balances, me, monthName(month)), ...jointLines(joint))
      }
      lines = out.filter((l): l is string => !!l)
    })
  })
</script>

{#if lines.length}
  <Card title="This month so far">
    <ul>
      {#each lines as line}<li>{line}</li>{/each}
    </ul>
    <p class="caption">Usual = the average of your last three months over the same days.</p>
  </Card>
{/if}

<style>
  ul { margin: 0; padding-left: 1.1rem; display: flex; flex-direction: column; gap: 0.35rem; }
</style>
