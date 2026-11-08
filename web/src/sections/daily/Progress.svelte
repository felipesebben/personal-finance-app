<!--
  How much of the reference month is spent (a bar: orange when ahead of the
  month, brand green otherwise) against how much of the month has gone (an
  ink tick), each named under the bar.
-->
<script lang="ts">
  let { spent, time }: { spent: number; time: number } = $props()
  const ahead = $derived(spent > time)
  const pct = (x: number) => `${Math.round(x * 100)}%`
</script>

<div class="progress" title="Spent {pct(spent)} · month gone {pct(time)}">
  <div class="track">
    <div class="fill" class:ahead style:width="{Math.min(Math.max(spent, 0), 1) * 100}%"></div>
    <div class="tick" style:left="{Math.min(time, 1) * 100}%"></div>
  </div>
  <div class="labels">
    <span class:ahead>Spent {pct(spent)}{ahead ? ' ▲' : ''}</span>
    <span>Month gone {pct(time)}</span>
  </div>
</div>

<style>
  .progress { margin-top: 0.75rem; }
  .track { position: relative; height: 12px; border-radius: 6px; background: var(--fill); }
  .fill { height: 100%; border-radius: 6px; background: var(--brand); }
  .fill.ahead { background: var(--more); }
  .tick { position: absolute; top: -5px; width: 2px; height: 22px; background: var(--ink); transform: translateX(-1px); }
  .labels { display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--ink-2); margin-top: 0.45rem; }
  .labels .ahead { color: var(--more); font-weight: 600; }
</style>
