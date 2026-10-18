"""The Tableau Cloud dashboard: the long-term home for analysis, embedded as is."""
import streamlit.components.v1 as components

import ui

# Wide layout matters for the embed.
ui.setup("Tableau")

ui.page_header("Tableau", "The full dashboard on Tableau Cloud, for deeper analysis.")

base_url = "https://10ax.online.tableau.com/t/felipetabdev/views/ExpendituresControlCenter/Dashboard1"
params = "?:embed=yes&:showVizHome=no&:toolbar=top&:tabs=no"
final_url = base_url + params

html_code = f"""
    <div style="
        display: flex;
        justify-content: center;
        width: 100%;
    ">
        <iframe
            src="{final_url}"
            width="1000"
            height="1100"
            style="border: none; overflow: hidden;"
        ></iframe>
    </div>
"""

components.html(html_code, height=1150, scrolling=True)
