"""Every expense I can see (mine plus the shared ones), newest first, with delete."""
from __future__ import annotations

import pandas as pd
import requests
import streamlit as st

import ui
from common import SAO_PAULO, auth_headers, get_data, saved
from config import API_BASE_URL
from money import format_brl

# A pet-category expense with no pet_id was for all the pets.
ALL_PETS = "Both"


def render(token: str) -> None:
    ui.lede(
        "Every expense you can see, newest first.",
        " That's yours plus the shared ones. To fix a mistake, delete it and add it again.",
    )
    expenditure_data = get_data("expenditures", token)
    if not expenditure_data:
        st.info("Nothing logged yet.")
        st.page_link("pages/1_Add_expense.py", label="Add your first expense", icon=":material/edit_note:")
        return

    df = pd.json_normalize(expenditure_data)
    # Money arrives as JSON strings (the API uses Decimal); convert once.
    for col in ("price", "my_share"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col])
    ts = pd.to_datetime(df["transaction_timestamp"])
    if ts.dt.tz is None:
        ts = ts.dt.tz_localize("UTC")
    df["transaction_timestamp"] = ts.dt.tz_convert(SAO_PAULO)
    df = df.sort_values(by="transaction_timestamp", ascending=False)

    def kind(row) -> str:
        text = "Shared" if row.get("is_shared") else "Personal"
        if row.get("is_treat") is True:
            text += " · treat"
        total = row.get("total_installments")
        return f"{text} · {int(total)}x" if pd.notna(total) and int(total) > 1 else text

    def column(name: str, default="—"):
        return df[name] if name in df else pd.Series(default, index=df.index)

    pet = column("pet.name", None).where(column("pet.name", None).notna(), ALL_PETS)
    for_pets = column("category.for_pets", False).eq(True)
    what = column("category.primary_category").fillna("—") + " · " + column("category.sub_category").fillna("—")

    display_df = pd.DataFrame({
        "When": df["transaction_timestamp"].dt.strftime("%d/%m/%Y %H:%M"),
        "What": what.where(~for_pets, what + " · " + pet),
        "Paid by": column("user.full_name"),
        "Type": df.apply(kind, axis=1),
        "Paid with": column("payment_method.method_name"),
        "Price": df["price"].map(format_brl),
        "Your part": column("my_share", 0).map(format_brl),
    })
    st.caption("**Price** is the full amount; **Your part** is what you bear of it.")
    st.dataframe(display_df, width="stretch", hide_index=True)

    with st.expander("Delete an entry"):
        delete_options = {
            row["expenditure_id"]: f"{row['transaction_timestamp'].strftime('%d/%m %H:%M')} – {format_brl(row['price'])}"
            for _, row in df.iterrows()
        }
        target_id = st.selectbox("Select entry to remove:", options=delete_options.keys(),
                                 format_func=lambda x: delete_options[x], index=None)

        if st.button("Confirm delete", type="primary") and target_id:
            try:
                res = requests.delete(f"{API_BASE_URL}/expenditures/{target_id}", headers=auth_headers(token))
            except Exception as e:
                st.error(f"Connection error: {e}")
                return
            if res.status_code == 200:
                saved(f"Entry removed: {delete_options[target_id]}")
            else:
                st.error("Error deleting entry.")
