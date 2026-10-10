"""
Reading and writing Brazilian reais, as people type and read them.

Pure functions with no Streamlit import, so they're unit-tested in
frontend/tests/test_money.py. Amounts are Decimal end to end: the API
stores Numeric(10, 2), and floats would drift by a cent.
"""
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

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
