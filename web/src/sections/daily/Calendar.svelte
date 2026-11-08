<!--
  This month's calendar: a CSS grid of square days (weeks down, Monday
  first), each shaded by what was spent, capped at a typical big day so one
  large payment doesn't wash the rest out. Today is outlined, days to come
  are blank. Hover (or tap) a day for what it held; tapping a day with
  spending also picks it in "What went on the biggest days?".
-->
<script lang="ts">
  import { dayTitle, isDark, shade, WEEKDAY_LETTERS } from '../../lib/daily/calendar'
  import type { CalDay } from '../../lib/daily/shaping'

  let { days, top, picked = null, onpick }: {
    days: CalDay[]
    top: number
    picked?: string | null
    onpick?: (date: string) => void
  } = $props()
</script>

<div class="cal" role="grid" aria-label="Spending per day">
  {#each WEEKDAY_LETTERS as letter}<div class="head" aria-hidden="true">{letter}</div>{/each}
  {#each days as d}
    {@const spent = d.state !== 'future' && d.amount > 0}
    <button type="button" class="day {d.state}" class:picked={picked === d.date} disabled={!spent}
      style:grid-column={d.day === 1 ? d.weekday + 1 : undefined}
      style:background={d.state === 'future' ? undefined : shade(d.amount, top)}
      style:color={d.state === 'future' ? undefined : isDark(d.amount, top) ? 'var(--on-brand)' : 'var(--ink)'}
      title={dayTitle(d)} aria-label={dayTitle(d)} onclick={() => onpick?.(d.date)}>{d.day}</button>
  {/each}
</div>

<style>
  .cal { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 4px; max-width: 22rem; width: 100%; }
  .head { color: var(--muted); font-weight: 600; font-size: 0.7rem; text-align: center; padding-bottom: 2px; }
  .day { aspect-ratio: 1; border-radius: 8px; display: grid; place-items: center; font-size: 0.75rem; border: none;
    padding: 0; font: inherit; font-size: 0.75rem; cursor: pointer; }
  .day:disabled { cursor: default; }
  .day.future { background: none; box-shadow: inset 0 0 0 1px var(--hairline); color: var(--compare-2); }
  .day.today { outline: 2px solid var(--ink); outline-offset: -2px; font-weight: 700; }
  .day.picked { box-shadow: 0 0 0 2px var(--surface), 0 0 0 4px var(--brand); }
</style>
