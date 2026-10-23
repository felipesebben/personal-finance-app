"""recap_shaping: the month you review together, in a few sentences."""
import analytics_shaping as shape
import recap_shaping
from conftest import sample_payload


def recap_of(payload, first_date=None, targets=None):
    df = shape.to_frame(payload)
    return recap_shaping.month_recap(df, payload["months"], payload["month"], payload["is_partial"],
                                     first_date, targets)


def test_a_month_against_last_month_the_usual_and_its_causes():
    r = recap_of(sample_payload("2026-10"), targets={"Food": 300.0, "Housing": 2500.0})
    assert (r["label"], r["total"]) == ("Oct 2026 so far", "R$ 2.370,00")
    # By the 10th: September had rent and R$ 150 of food; the usual month is July–September.
    assert r["lines"] == [("▲ R$ 220,00 (10%) more than September by the same day", "more"),
                          ("▲ R$ 220,00 (10%) more than the usual month by the same day", "more")]
    assert r["causes"] == [("Day-to-day: ▲ R$ 220,00, now R$ 370,00", "more")]  # fixed costs didn't move
    assert r["moves"] == [("Food ▲ R$ 220,00 (147%)", "more")]
    # Over target first, then the rest with how much of it is used.
    assert r["targets"] == [("Food: R$ 370,00 of R$ 300,00, ▲ R$ 70,00 over", "more"),
                            ("Housing: R$ 2.000,00 of R$ 2.500,00 (80%)", None)]


def test_a_partly_logged_last_month_is_named_not_compared():
    r = recap_of(sample_payload("2026-10"), first_date="2026-09-26")
    assert r["lines"] == [("September was logged from the 26th only, so not compared yet.", None)]
    assert r["causes"] == [] and r["moves"] == []


def test_no_targets_no_target_lines():
    assert recap_of(sample_payload("2026-10"))["targets"] == []
