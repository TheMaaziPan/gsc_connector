import streamlit as st
import datetime
import base64
import json
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pandas as pd
import searchconsole

# Configuration: Set to True if running locally, False if running on Streamlit Cloud
IS_LOCAL = False

# Constants
SEARCH_TYPES = ["web", "image", "video", "news", "discover", "googleNews"]
DATE_RANGE_OPTIONS = ["Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months",
                      "Last 12 Months", "Last 16 Months", "Custom Range"]
DEVICE_OPTIONS = ["All Devices", "desktop", "mobile", "tablet"]
BASE_DIMENSIONS = ["page", "query", "country", "date"]
MAX_ROWS = 1_000_000
DF_PREVIEW_ROWS = 100


def setup_streamlit():
    """Configures Streamlit UI settings and layout."""
    st.set_page_config(page_title="✨ Google Search Console Connector", layout="wide")
    st.title("✨ Google Search Console Data Extractor")
    st.markdown(f"### Extract Google Search Console Data (Max {MAX_ROWS:,} Rows)")

    st.markdown(
        """
        <p>Created by <a href="https://twitter.com/LeeFootSEO" target="_blank">LeeFootSEO</a> |
        <a href="https://leefoot.co.uk" target="_blank">More Apps & Scripts</a></p>
        """,
        unsafe_allow_html=True
    )
    st.divider()


def init_session_state():
    """Initializes session state variables if not already set."""
    defaults = {
        "selected_property": None,
        "selected_search_type": "web",
        "selected_date_range": "Last 7 Days",
        "start_date": datetime.date.today() - datetime.timedelta(days=7),
        "end_date": datetime.date.today(),
        "selected_dimensions": ["page", "query"],
        "selected_device": "All Devices",
        "custom_start_date": datetime.date.today() - datetime.timedelta(days=7),
        "custom_end_date": datetime.date.today(),
        "credentials": None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def load_config():
    """Loads OAuth client configuration from Streamlit secrets."""
    try:
        client_config = {
            "installed": {
                "client_id": str(st.secrets["installed"]["client_id"]),
                "client_secret": str(st.secrets["installed"]["client_secret"]),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": st.secrets["installed"].get("redirect_uris", ["http://localhost:8501/"])
            }
        }
        return client_config
    except KeyError as e:
        st.error(f"Missing required secret: {e}. Please configure `secrets.toml` or Streamlit Cloud secrets correctly.")
        return None


def init_oauth_flow(client_config):
    """Initializes OAuth flow for authentication."""
    scopes = ["https://www.googleapis.com/auth/webmasters"]
    return Flow.from_client_config(
        client_config,
        scopes=scopes,
        redirect_uri=client_config["installed"]["redirect_uris"][0],
    )


def google_auth(client_config):
    """Starts Google authentication process."""
    flow = init_oauth_flow(client_config)
    auth_url, _ = flow.authorization_url(prompt="consent")
    return flow, auth_url


def refresh_credentials():
    """Refreshes expired credentials if needed."""
    if "credentials" in st.session_state and st.session_state.credentials.expired:
        st.session_state.credentials.refresh(Request())


def list_gsc_properties(credentials):
    """Lists all GSC properties for the authenticated user."""
    try:
        service = build('webmasters', 'v3', credentials=credentials)
        site_list = service.sites().list().execute()
        return [site['siteUrl'] for site in site_list.get('siteEntry', [])] or ["No properties found"]
    except Exception as e:
        st.error(f"Failed to retrieve properties: {str(e)}")
        return []


def fetch_gsc_data(webproperty, search_type, start_date, end_date, dimensions, device_type=None):
    """Fetches GSC data and handles errors."""
    query = webproperty.query.range(start_date, end_date).search_type(search_type).dimension(*dimensions)

    if 'device' in dimensions and device_type and device_type != 'All Devices':
        query = query.filter('device', 'equals', device_type.lower())

    try:
        return query.limit(MAX_ROWS).get().to_dataframe()
    except Exception as e:
        st.error(f"Error fetching GSC data: {str(e)}")
        return pd.DataFrame()


def main():
    """Main function for Streamlit app."""
    setup_streamlit()
    init_session_state()
    
    client_config = load_config()
    if not client_config:
        return

    # Initialize OAuth
    st.session_state.auth_flow, st.session_state.auth_url = google_auth(client_config)

    query_params = st.query_params
    auth_code = query_params.get("code", [None])[0]

    if auth_code and not st.session_state.get('credentials'):
        try:
            st.session_state.auth_flow.fetch_token(code=auth_code)
            st.session_state.credentials = st.session_state.auth_flow.credentials
        except Exception as e:
            st.error(f"Authentication failed. Please sign in again. Error: {str(e)}")
            st.session_state.credentials = None
            st.session_state.auth_flow, st.session_state.auth_url = google_auth(client_config)

    if not st.session_state.get('credentials'):
        with st.sidebar:
            if st.button("Sign in with Google"):
                st.write('Click the link below to authenticate:')
                st.markdown(f'[Google Sign-In]({st.session_state.auth_url})', unsafe_allow_html=True)
    else:
        # Fetch Search Console properties
        refresh_credentials()
        credentials = st.session_state.credentials
        service = build('webmasters', 'v3', credentials=credentials)

        # Get list of GSC properties
        properties = list_gsc_properties(credentials)

        if properties:
            selected_property = st.selectbox("Select a GSC Property:", properties)
            st.write(f"Selected: {selected_property}")

            # Fetch data
            if st.button("Fetch Data"):
                st.write("Fetching data from GSC...")
                report = fetch_gsc_data(service, "web", datetime.date.today() - datetime.timedelta(days=7), datetime.date.today(), ["page", "query"])
                
                if not report.empty:
                    st.dataframe(report.head(DF_PREVIEW_ROWS))
                    csv = report.to_csv(index=False, encoding='utf-8-sig')
                    b64_csv = base64.b64encode(csv.encode()).decode()
                    href = f'<a href="data:file/csv;base64,{b64_csv}" download="search_console_data.csv">Download CSV</a>'
                    st.markdown(href, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
