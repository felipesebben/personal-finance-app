<!--
  Home. Arriving from a reset email (/?reset_token=…): set a new password.
  Logged out: log in, sign up, or ask for a reset link, with the one-time
  "you were logged out" message. Logged in: the briefing and a card per page.
-->
<script lang="ts">
  import { login, post, session } from '../lib/session.svelte'
  import { href, type Page } from '../lib/router.svelte'
  import Briefing from '../sections/Briefing.svelte'
  import Card from '../lib/ui/Card.svelte'
  import Icon from '../lib/ui/Icon.svelte'
  import Message from '../lib/ui/Message.svelte'
  import PageHeader from '../lib/ui/PageHeader.svelte'
  import Segmented from '../lib/ui/Segmented.svelte'

  const PASSWORD_MIN_LENGTH = 8

  let resetToken = $state(typeof location === 'undefined' ? null : new URLSearchParams(location.search).get('reset_token'))
  let resetDone = $state(false)
  // Shown once on the login form, then forgotten.
  const logoutMessage = session.logoutMessage
  session.logoutMessage = ''

  let mode = $state<'login' | 'signup'>('login')
  let busy = $state(false)
  let error = $state('')
  let notice = $state('')

  // Log in
  let email = $state('')
  let password = $state('')
  async function submitLogin(e: SubmitEvent) {
    e.preventDefault()
    error = ''
    if (!email || !password) { error = 'Please enter both email and password.'; return }
    busy = true
    const problem = await login(email, password)
    busy = false
    if (problem) error = problem
  }

  // Forgot password
  let forgotOpen = $state(false)
  let resetEmail = $state('')
  let forgotNotice = $state('')
  let forgotError = $state('')
  async function submitForgot(e: SubmitEvent) {
    e.preventDefault()
    forgotError = ''
    forgotNotice = ''
    if (!resetEmail) { forgotError = 'Please enter your email.'; return }
    try {
      await post('password-reset/request', { email: resetEmail })
      forgotNotice = "If that account exists, we've sent a reset link."
      resetEmail = ''
    } catch (err) {
      forgotError = (err as Error).message
    }
  }

  // Sign up
  let newName = $state('')
  let newEmail = $state('')
  let newPassword = $state('')
  async function submitSignup(e: SubmitEvent) {
    e.preventDefault()
    error = ''
    notice = ''
    if (!newName || !newEmail || !newPassword) { error = 'Please fill in all fields.'; return }
    busy = true
    try {
      await post('users/', { full_name: newName, email: newEmail, password: newPassword })
      notice = 'Account created! You can now log in.'
      email = newEmail
      newName = newEmail = newPassword = ''
      mode = 'login'
    } catch (err) {
      error = `Registration failed: ${(err as Error).message}`
    } finally {
      busy = false
    }
  }

  // Set a new password
  let pw1 = $state('')
  let pw2 = $state('')
  function leaveReset() {
    history.replaceState(null, '', location.pathname + location.hash)
    resetToken = null
    // App.svelte read the token once at start: reload so it shows the login form.
    location.reload()
  }
  async function submitReset(e: SubmitEvent) {
    e.preventDefault()
    error = ''
    if (pw1.length < PASSWORD_MIN_LENGTH) { error = `The password must be at least ${PASSWORD_MIN_LENGTH} characters.`; return }
    if (pw1 !== pw2) { error = "The passwords don't match."; return }
    busy = true
    try {
      await post('password-reset/confirm', { token: resetToken, new_password: pw1 })
      resetDone = true
      history.replaceState(null, '', location.pathname + location.hash)
      resetToken = null
    } catch (err) {
      error = (err as Error).message || 'This reset link is invalid or has expired.'
    } finally {
      busy = false
    }
  }

  const cards: { page: Page; title: string; text: string; icon: string }[] = [
    { page: 'add', title: 'Add expense', text: 'Record a purchase in a few taps.', icon: 'add' },
    { page: 'ours', title: 'Our expenses', text: 'How our shared spending is doing: this month against earlier ones, the joint account, and who owes whom.', icon: 'ours' },
    { page: 'mine', title: 'My expenses', text: "How your own spending is doing: your part of what you share, plus what's only yours.", icon: 'mine' },
    { page: 'entries', title: 'Entries', text: 'Everything logged, to check it and fix a mistake.', icon: 'entries' },
    { page: 'settings', title: 'Settings', text: 'Categories, payment methods, pets, and the household split between you.', icon: 'settings' },
  ]
</script>

{#if resetToken}
  <div class="narrow">
    <PageHeader title="Set a new password" purpose="Choose a new password for your account. The link works once." />
    <Card>
      <form class="stack" onsubmit={submitReset}>
        <label class="field"><span>New password</span>
          <input type="password" autocomplete="new-password" bind:value={pw1} />
          <span class="hint">At least {PASSWORD_MIN_LENGTH} characters.</span>
        </label>
        <label class="field"><span>Repeat new password</span>
          <input type="password" autocomplete="new-password" bind:value={pw2} />
        </label>
        {#if error}<Message tone="error">{error}</Message>{/if}
        <div class="row">
          <button class="btn primary" type="submit" disabled={busy}>Set password</button>
          <button class="btn" type="button" onclick={leaveReset}>Back to log in</button>
        </div>
      </form>
    </Card>
  </div>
{:else if !session.token}
  <div class="narrow">
    <PageHeader title="Home Finances"
      purpose="Your household's shared spending, split fairly by income. Log in, or create an account if you're new." />
    <div class="stack">
      {#if resetDone}<Message tone="ok">Password updated. You can now log in with the new one.</Message>{/if}
      {#if logoutMessage}<Message>{logoutMessage}</Message>{/if}
      {#if notice}<Message tone="ok">{notice}</Message>{/if}
      <Card>
        <Segmented options={['login', 'signup'] as ('login' | 'signup')[]} bind:value={mode}
          labels={{ login: 'Log in', signup: 'Sign up' }} onchange={() => (error = '')} />
        {#if mode === 'login'}
          <form class="stack" onsubmit={submitLogin}>
            <label class="field"><span>Email</span><input type="email" autocomplete="username" bind:value={email} /></label>
            <label class="field"><span>Password</span>
              <input type="password" autocomplete="current-password" bind:value={password} />
            </label>
            {#if error}<Message tone="error">{error}</Message>{/if}
            <div><button class="btn primary" type="submit" disabled={busy}>Log in</button></div>
          </form>
          <details bind:open={forgotOpen}>
            <summary>Forgot password?</summary>
            <form class="stack" onsubmit={submitForgot}>
              <label class="field"><span>Your account's email</span><input type="email" bind:value={resetEmail} /></label>
              {#if forgotError}<Message tone="error">{forgotError}</Message>{/if}
              {#if forgotNotice}<Message tone="ok">{forgotNotice}</Message>{/if}
              <div><button class="btn" type="submit">Email me a reset link</button></div>
            </form>
          </details>
        {:else}
          <p class="caption">New here? Create an account.</p>
          <form class="stack" onsubmit={submitSignup}>
            <label class="field"><span>Full name</span><input type="text" autocomplete="name" bind:value={newName} /></label>
            <label class="field"><span>Email</span><input type="email" autocomplete="email" bind:value={newEmail} /></label>
            <label class="field"><span>Password</span>
              <input type="password" autocomplete="new-password" bind:value={newPassword} />
            </label>
            {#if error}<Message tone="error">{error}</Message>{/if}
            <div><button class="btn primary" type="submit" disabled={busy}>Create account</button></div>
          </form>
        {/if}
      </Card>
    </div>
  </div>
{:else}
  <PageHeader title="Home Finances" purpose="What would you like to do?" />
  <div class="stack">
    <Briefing />
    <div class="cards">
      {#each cards as c}
        <a class="link-card" href={href(c.page)}>
          <span class="icon"><Icon name={c.icon} /></span>
          <h3>{c.title}</h3>
          <p>{c.text}</p>
        </a>
      {/each}
    </div>
    <p class="caption">Logged in as {session.email}.</p>
  </div>
{/if}

<style>
  .narrow { max-width: 30rem; margin: 0 auto; }
  details summary { cursor: pointer; color: var(--brand); font-size: 0.92rem; }
  details[open] summary { margin-bottom: 0.75rem; }
  .cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1rem; }
  .link-card { display: flex; flex-direction: column; gap: 0.4rem; background: var(--surface); border-radius: var(--radius-card);
    box-shadow: var(--shadow-card); padding: 1.1rem 1.2rem; color: var(--ink); text-decoration: none;
    border: 1px solid transparent; transition: border-color 0.15s; }
  .link-card:hover { border-color: var(--brand); }
  .link-card p { color: var(--ink-2); font-size: 0.9rem; }
  .icon { width: 2.4rem; height: 2.4rem; border-radius: 0.7rem; background: var(--brand-soft); color: var(--brand);
    display: grid; place-items: center; }
</style>
