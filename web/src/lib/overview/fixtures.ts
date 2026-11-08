/** Sample /analytics/shared responses for the overview and recap tests (port of frontend/tests/conftest.py). */
import { shiftMonth, type ApiRow, type Payload } from './shaping'

export function row(month: string, primary: string, sub: string, costType: string, household: string, mine: string,
  count = 1, householdToDay?: string, mineToDay?: string): ApiRow {
  return {
    month, primary_category: primary, sub_category: sub, cost_type: costType, household, mine, count,
    household_to_day: householdToDay ?? household, mine_to_day: mineToDay ?? mine,
  }
}

export function window(month = '2026-10', n = 12): string[] {
  return Array.from({ length: n }, (_, i) => shiftMonth(month, -(n - 1 - i)))
}

/**
 * Shared expenses over the four months up to `month` (default October 2026,
 * in progress at day 10). Food rises against the previous month's first ten
 * days; Housing is flat.
 */
export function samplePayload(month = '2026-10', isPartial = true, asOfDay = 10): Payload {
  const [m3, m2, m1] = [3, 2, 1].map((k) => shiftMonth(month, -k))
  return {
    month, months: window(month), is_partial: isPartial, as_of_day: asOfDay,
    rows: [
      row(m3, 'Housing', 'Rent', 'Fixed', '2000.00', '1200.00'),
      row(m3, 'Food', 'Groceries', 'Variable', '300.00', '180.00', 3, '100.00', '60.00'),
      row(m2, 'Housing', 'Rent', 'Fixed', '2000.00', '1200.00'),
      row(m2, 'Food', 'Groceries', 'Variable', '600.00', '360.00', 4, '200.00', '120.00'),
      row(m1, 'Housing', 'Rent', 'Fixed', '2000.00', '1200.00', 1, '2000.00', '1200.00'),
      row(m1, 'Food', 'Groceries', 'Variable', '900.00', '540.00', 6, '150.00', '90.00'),
      row(m1, 'Leisure', 'Cinema', 'Variable', '80.00', '48.00', 1, '0.00', '0.00'),
      row(month, 'Housing', 'Rent', 'Fixed', '2000.00', '1200.00'),
      row(month, 'Food', 'Groceries', 'Variable', '250.00', '150.00', 3),
      row(month, 'Food', 'Restaurants', 'Variable', '120.00', '72.00', 2),
    ],
  }
}

export function emptyPayload(month = '2026-10'): Payload {
  return { month, months: window(month), is_partial: true, as_of_day: 10, rows: [] }
}
