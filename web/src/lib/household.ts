/**
 * Who's who: the household's shares (GET /household_settings/) and the
 * logged-in person's id, matched by the email kept at login.
 */
export interface HouseholdMember {
  user_id: number
  share_pct: string
  user: { user_id: number; full_name: string; email: string }
}

export function myUserId(household: HouseholdMember[] | null | undefined, email: string): number | null {
  const e = email.trim().toLowerCase()
  return (household ?? []).find((m) => (m.user?.email ?? '').toLowerCase() === e)?.user_id ?? null
}

/** First name for sentences: "Felipe Sebben" → "Felipe". */
export function firstName(fullName: string | null | undefined): string {
  return (fullName ?? '').trim().split(/\s+/)[0] || 'Someone'
}
