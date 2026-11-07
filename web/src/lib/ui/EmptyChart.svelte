<!-- Holds a chart's place, at its height, when there's nothing to draw yet, so cards in a row match. -->
<script lang="ts">
  let { text, height = 120 }: { text: string; height?: number } = $props()
</script>

<div class="empty" style:height="{height}px">{text}</div>

<style>
  .empty { display: grid; place-items: center; text-align: center; border: 1px dashed var(--line);
    border-radius: 0.5rem; color: var(--ink-2); font-size: 0.82rem; padding: 0 0.75rem; }
</style>
