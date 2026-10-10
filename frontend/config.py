"""
Frontend settings, in one place. The Streamlit pages are pure HTTP clients,
so the API's address is the only setting they need.
"""
import os

# docker-compose.yml sets http://backend:8000; outside Docker the API runs on localhost.
API_BASE_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
