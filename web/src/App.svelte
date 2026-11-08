<!--
  The app shell: a top bar with the pages on a wide screen, a bottom tab bar
  on a phone, the toast, and the page for the current route. Without a
  session (or arriving from a reset link) every route shows Home's login.
-->
<script lang="ts">
  import { PAGES, href, route } from './lib/router.svelte'
  import { endSession, session } from './lib/session.svelte'
  import Icon from './lib/ui/Icon.svelte'
  import Toast from './lib/ui/Toast.svelte'
  import Home from './pages/Home.svelte'
  import AddExpense from './pages/AddExpense.svelte'
  import OurExpenses from './pages/OurExpenses.svelte'
  import MyExpenses from './pages/MyExpenses.svelte'
  import Entries from './pages/Entries.svelte'
  import Settings from './pages/Settings.svelte'

  const resetting = typeof location !== 'undefined' && new URLSearchParams(location.search).has('reset_token')
  const loggedIn = $derived(!!session.token && !resetting)
</script>

{#if loggedIn}
  <header class="topbar">
    <a class="brand" href={href('home')}><img src="/icon.svg" alt="" width="28" height="28" /><span>Home Finances</span></a>
    <nav class="top-nav" aria-label="Pages">
      {#each PAGES.slice(1) as p}
        <a href={href(p.id)} class:active={route.page === p.id} aria-current={route.page === p.id ? 'page' : undefined}>{p.label}</a>
      {/each}
    </nav>
    <button type="button" class="logout" title="Log out ({session.email})" onclick={() => endSession(null)}>
      <Icon name="logout" size={20} /><span>Log out</span>
    </button>
  </header>
{/if}

<main class:with-nav={loggedIn}>
  {#if !loggedIn || route.page === 'home'}
    <Home />
  {:else if route.page === 'add'}
    <AddExpense />
  {:else if route.page === 'ours'}
    <OurExpenses />
  {:else if route.page === 'mine'}
    <MyExpenses />
  {:else if route.page === 'entries'}
    <Entries />
  {:else if route.page === 'settings'}
    <Settings />
  {/if}
</main>

{#if loggedIn}
  <nav class="bottom-nav" aria-label="Pages">
    {#each PAGES as p}
      <a href={href(p.id)} class:active={route.page === p.id} aria-current={route.page === p.id ? 'page' : undefined}>
        <Icon name={p.icon} /><span>{p.short}</span>
      </a>
    {/each}
  </nav>
{/if}

<Toast />

<style>
  /* Bars are a translucent material over the content, as on Apple platforms. */
  .topbar { position: sticky; top: 0; z-index: 20; display: flex; align-items: center; gap: 1.5rem;
    background: var(--material); -webkit-backdrop-filter: saturate(180%) blur(20px); backdrop-filter: saturate(180%) blur(20px);
    border-bottom: 0.5px solid var(--line);
    padding: env(safe-area-inset-top) max(var(--gutter), calc((100vw - 1200px) / 2)) 0; height: calc(52px + env(safe-area-inset-top)); }
  .brand { display: flex; align-items: center; gap: 0.55rem; font-weight: 600; font-size: 1.0625rem; color: var(--ink);
    text-decoration: none; flex: none; letter-spacing: -0.015em; }
  .brand:hover { text-decoration: none; }
  .brand img { border-radius: 7px; }
  .top-nav { display: flex; gap: 0.15rem; flex: 1; overflow-x: auto; scrollbar-width: none; }
  .top-nav a { color: var(--ink-2); text-decoration: none; padding: 0.4rem 0.8rem; border-radius: 999px;
    font-size: 0.9375rem; font-weight: 500; white-space: nowrap; transition: background 0.15s ease, color 0.15s ease; }
  .top-nav a:hover { color: var(--ink); background: var(--fill-2); }
  .top-nav a.active { color: var(--ink); background: var(--fill); font-weight: 600; }
  .logout { display: flex; align-items: center; gap: 0.35rem; border: none; background: none; color: var(--brand);
    cursor: pointer; padding: 0.4rem 0.6rem; border-radius: 999px; flex: none; font-size: 0.9375rem; }
  .logout:hover { background: var(--brand-soft); }

  main { max-width: 1200px; margin: 0 auto; padding: 1rem var(--gutter) 3rem; }

  .bottom-nav { display: none; }

  @media (max-width: 760px) {
    .top-nav { display: none; }
    .topbar { justify-content: space-between; height: calc(48px + env(safe-area-inset-top)); }
    .brand { font-size: 1rem; }
    .logout span { display: none; }
    main.with-nav { padding-bottom: calc(var(--nav-height) + 2rem + env(safe-area-inset-bottom)); }
    .bottom-nav { display: grid; grid-template-columns: repeat(6, 1fr); position: fixed; left: 0; right: 0; bottom: 0;
      z-index: 30; background: var(--material); -webkit-backdrop-filter: saturate(180%) blur(20px);
      backdrop-filter: saturate(180%) blur(20px); border-top: 0.5px solid var(--line);
      padding-bottom: env(safe-area-inset-bottom); height: calc(var(--nav-height) + env(safe-area-inset-bottom)); }
    .bottom-nav a { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px;
      color: var(--compare); text-decoration: none; font-size: 0.625rem; font-weight: 500; letter-spacing: 0.01em; }
    .bottom-nav a.active { color: var(--brand); }
  }
</style>
