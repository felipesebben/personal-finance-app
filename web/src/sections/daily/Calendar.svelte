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

  let { days, top, picked = null, onpick, small = false }: {
    days: CalDay[]
    top: number
    picked?: string | null
    onpick?: (date: string) => void
    /** A widget: tighter squares and smaller numbers. */
    small?: boolean
  } = $props()
</script>

<div class="cal" class:small role="grid" aria-label="Spending per day">
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
  .head { color: var(--muted); font-weight: 400; font-size: var(--t-caption); text-align: center; padding-bottom: 2px; }
  .day { aspect-ratio: 1; border-radius: 8px; display: grid; place-items: center; font-size: var(--t-caption); border: none;
    padding: 0; font: inherit; font-size: var(--t-caption); cursor: pointer; }
  .day:disabled { cursor: default; }
  .day.future { background: none; box-shadow: inset 0 0 0 1px var(--hairline); color: var(--compare-2); }
  .day.today { outline: 2px solid var(--ink); outline-offset: -2px; font-weight: 600; }
  .day.picked { box-shadow: 0 0 0 2px var(--surface), 0 0 0 4px var(--brand); }
  .small { gap: 3px; max-width: none; }
  .small .head { font-size: 0.62rem; padding-bottom: 0; }
  .small .day { border-radius: 5px; font-size: 0.66rem; }
  /* Days to come are quiet blanks in the widget, not outlined boxes. */
  .small .day.future { box-shadow: none; background: var(--fill-2); color: var(--compare-2); }
  .small .day.today { outline-width: 1.5px; outline-offset: -1.5px; }
  .small .day.picked { box-shadow: 0 0 0 1.5px var(--surface), 0 0 0 3px var(--brand); }
  @media (max-width: 560px) { .small { gap: 2px; } .small .day { font-size: 0.56rem; border-radius: 4px; } }
</style>
