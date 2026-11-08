<!-- Leads with the answer ("Lívia owes you", "R$ 247,90"), before what explains it. -->
<script lang="ts">
  let { label, amount = '', detail = '' }: { label: string; amount?: string; detail?: string } = $props()
</script>

<div class="callout">
  <div>
    <div class="label">{label}</div>
    {#if detail}<div class="detail">{detail}</div>{/if}
  </div>
  {#if amount}<div class="amount">{amount}</div>{/if}
</div>

<style>
  .callout { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 0.75rem;
    background: var(--owed-soft); border-radius: 14px; padding: 1rem 1.15rem; }
  .label { font-size: var(--t-headline); font-weight: 600; letter-spacing: -0.014em; }
  .detail { color: var(--muted); font-size: var(--t-subhead); margin-top: 0.1rem; }
  .amount { font-family: var(--font-display); font-size: 1.75rem; font-weight: 700; white-space: nowrap; letter-spacing: -0.02em; }
</style>
