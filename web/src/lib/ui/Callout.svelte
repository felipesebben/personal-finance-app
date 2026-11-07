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
    background: var(--owed-soft); border-left: 4px solid var(--brand); border-radius: var(--radius);
    padding: 0.9rem 1rem; }
  .label { font-size: 1.15rem; font-weight: 700; }
  .detail { color: var(--ink-2); font-size: 0.85rem; }
  .amount { font-size: 1.6rem; font-weight: 700; white-space: nowrap; }
</style>
