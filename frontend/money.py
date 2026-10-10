"""
Reading and writing Brazilian reais, as people type and read them.

Pure functions with no Streamlit import, so they're unit-tested in
frontend/tests/test_money.py. Amounts are Decimal end to end: the API
stores Numeric(10, 2), and floats would drift by a cent.
"""
import re
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
# The API's price is Numeric(10, 2): at most 8 digits before the comma.
MAX_INTEGER_DIGITS = 8

_GROUPED = re.compile(r"\d{1,3}(\.\d{3})+")


def parse_brl(text: str) -> Decimal:
    """
    Parses what someone typed as an amount in reais into a positive Decimal
    with two places.

    Accepts "45", "45,9", "1.234,56", "1234,56", "1234.56", "R$ 12,50" and
    ",50". When both "." and "," appear, the comma is the decimal separator
    and the dots must group thousands. With only a dot, it's a decimal point
    when 1–2 digits follow it ("12.5"), and thousands grouping otherwise
    ("1.234" is one thousand two hundred and thirty-four, as written in Brazil).

    :raises ValueError: with a message fit to show the person.
    """
    s = (text or "").replace(" ", " ").strip()
    s = re.sub(r"^R\$\s*", "", s, flags=re.IGNORECASE).replace(" ", "")
    if not s:
        raise ValueError("Enter an amount, e.g. 45,90")
    if s.startswith("-"):
        raise ValueError("The amount must be positive")
    if not re.fullmatch(r"[\d.,]+", s):
        raise ValueError("Use only digits, with a comma for cents, e.g. 1.234,56")

    if "," in s:
        if s.count(",") > 1:
            raise ValueError("Use one comma for the cents, e.g. 1.234,56")
        integer, cents = s.split(",")
        if "." in integer and not _GROUPED.fullmatch(integer):
            raise ValueError("Dots separate thousands, e.g. 1.234,56")
        integer = integer.replace(".", "")
    elif "." in s:
        integer, _, cents = s.rpartition(".")
        if len(cents) in (1, 2) and s.count(".") == 1:
            pass  # "12.5" / "1234.56": a decimal point
        elif _GROUPED.fullmatch(s):
            integer, cents = s.replace(".", ""), ""
        else:
            raise ValueError("Use a comma for cents, e.g. 1.234,56")
    else:
        integer, cents = s, ""

    if len(cents) > 2:
        raise ValueError("Use at most two digits for cents")
    integer = integer or "0"
    if len(integer.lstrip("0")) > MAX_INTEGER_DIGITS:
        raise ValueError("That amount is too large")

    try:
        value = Decimal(f"{integer}.{cents or '0'}").quantize(CENT)
    except InvalidOperation:
        raise ValueError("Use only digits, with a comma for cents, e.g. 1.234,56") from None
    if value <= 0:
        raise ValueError("The amount must be greater than zero")
    return value


def format_brl(value, symbol: bool = True) -> str:
    """
    Formats an amount the Brazilian way: 1234.5 -> "R$ 1.234,50".

    Accepts Decimal, int, float or a numeric string (the API sends strings).
    Negative amounts keep their sign: "-R$ 12,00".
    """
    amount = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    sign = "-" if amount < 0 else ""
    text = f"{abs(amount):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{sign}R$ {text}" if symbol else f"{sign}{text}"


def format_brl_delta(value) -> str:
    """
    A signed amount for st.metric's delta: "+R$ 12,00", "-R$ 3,50", "R$ 0,00".

    st.metric colours the arrow from the leading sign, so positives get an
    explicit "+".
    """
    text = format_brl(value)
    return text if text.startswith("-") or Decimal(str(value)) == 0 else f"+{text}"


def installment_amounts(total: Decimal, count: int) -> tuple[Decimal, Decimal]:
    """
    The first and last installment of `total` paid in `count` parts, by the
    rule the ETL's cashflow datasource uses: every installment but the last
    is rounded down to the cent, and the last takes the remainder.

    installment_amounts(Decimal("40"), 3) -> (13.33, 13.34)
    """
    if count < 1:
        raise ValueError("count must be at least 1")
    each = (total / count).quantize(CENT, rounding=ROUND_DOWN)
    return each, total - each * (count - 1)


def split_like_backend(total: Decimal, shares: list[tuple[int, Decimal]]) -> dict[int, Decimal]:
    """
    How the API will split `total` across (user_id, fraction) pairs, mirroring
    backend/split_logic.split_amount: pairs are ordered by user_id (as the
    backend orders household rows and manual shares), each share but the last
    is rounded half up to the cent, and the last absorbs the remainder.
    Pairs with a zero fraction are dropped, as the page never sends them.
    """
    pairs = sorted((uid, Decimal(str(pct))) for uid, pct in shares if Decimal(str(pct)) > 0)
    if not pairs:
        return {}
    amounts = {uid: (total * pct).quantize(CENT, rounding=ROUND_HALF_UP) for uid, pct in pairs[:-1]}
    amounts[pairs[-1][0]] = (total - sum(amounts.values(), Decimal("0"))).quantize(CENT, rounding=ROUND_HALF_UP)
    return amounts


def entry_preview(price: Decimal, installments: int = 1,
                  shares: list[tuple[int, Decimal]] | None = None, me: int | None = None) -> str:
    """
    One line read back under the price field, so a typo is caught before
    saving: "R$ 1.200,00 · 10x R$ 120,00 · your share 60% = R$ 720,00".

    The installment part appears only above 1x, and names the last
    installment when it differs ("3x R$ 13,33 (last R$ 13,34)"). The share
    part appears only when `shares` (user_id, fraction) names `me` (even at
    0%); pass None for a personal expense.
    """
    parts = [format_brl(price)]
    if installments > 1:
        first, last = installment_amounts(price, installments)
        text = f"{installments}x {format_brl(first)}"
        if last != first:
            text += f" (last {format_brl(last)})"
        parts.append(text)
    if shares and me is not None:
        mine = dict(shares)
        if me in mine:
            amount = split_like_backend(price, shares).get(me, Decimal("0.00"))
            pct_text = f"{(Decimal(str(mine[me])) * 100).normalize():f}".replace(".", ",")
            parts.append(f"your share {pct_text}% = {format_brl(amount)}")
    return " · ".join(parts)
