import streamlit as st
import streamlit.components.v1 as components

# 1. Force Wide Mode (important for Tableau)
st.set_page_config(page_title="Analytics", layout="wide")

st.title("📈 Financial Analytics")

# Tableau Link
base_url = "https://10ax.online.tableau.com/t/felipetabdev/views/ExpendituresControlCenter/Dashboard1"
params= "?:embed=yes&:showVizHome=no&:toolbar=top&:tabs=no"
final_url = base_url + params

# Embed the code
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

# Render
components.html(html_code, height=1150,scrolling=True)