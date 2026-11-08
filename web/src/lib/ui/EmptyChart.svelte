<!-- Holds a chart's place, at its height, when there's nothing to draw yet, so cards in a row match. -->
<script lang="ts">
  let { text, height = 120 }: { text: string; height?: number } = $props()
</script>

<div class="empty" style:height="{height}px">{text}</div>

<style>
  .empty { display: grid; place-items: center; text-align: center; background: var(--fill-2);
    border-radius: 10px; color: var(--muted); font-size: 0.8125rem; padding: 0 0.75rem; }
</style>
