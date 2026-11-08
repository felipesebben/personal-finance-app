/**
 * A tiny hash router: "#/ours/month" → page "ours", tab "month". Hash-based
 * so nginx serves one index.html for every page and a reload keeps the page.
 * The password-reset link keeps its old shape (/?reset_token=…), read from
 * the query string by Home.
 */
export type Page = 'home' | 'add' | 'ours' | 'mine' | 'entries' | 'settings'

export const PAGES: { id: Page; label: string; short: string; icon: string }[] = [
  { id: 'home', label: 'Home', short: 'Home', icon: 'home' },
  { id: 'add', label: 'Add expense', short: 'Add', icon: 'add' },
  { id: 'ours', label: 'Our expenses', short: 'Ours', icon: 'ours' },
  { id: 'mine', label: 'My expenses', short: 'Mine', icon: 'mine' },
  { id: 'entries', label: 'Entries', short: 'Entries', icon: 'entries' },
  { id: 'settings', label: 'Settings', short: 'Settings', icon: 'settings' },
]

function parse(hash: string): { page: Page; tab: string } {
  const [page, tab] = hash.replace(/^#\/?/, '').split('/')
  const known = PAGES.some((p) => p.id === page)
  return { page: known ? (page as Page) : 'home', tab: tab ?? '' }
}

export const route = $state(parse(typeof location === 'undefined' ? '' : location.hash))

if (typeof window !== 'undefined') {
  window.addEventListener('hashchange', () => {
    const next = parse(location.hash)
    if (next.page !== route.page) window.scrollTo(0, 0)
    route.page = next.page
    route.tab = next.tab
  })
}

export function href(page: Page, tab = ''): string {
  return tab ? `#/${page}/${tab}` : `#/${page}`
}

export function go(page: Page, tab = '') {
  location.hash = href(page, tab)
}

/** Switch tab without adding a history entry per tab. */
export function setTab(tab: string) {
  route.tab = tab
  history.replaceState(null, '', href(route.page, tab))
}
