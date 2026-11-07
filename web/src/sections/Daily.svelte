<script lang="ts">
  let { lens, key, showView = false }: { lens: string; key: string; showView?: boolean } = $props()
</script>

<p>{lens} {key} {showView}</p>
