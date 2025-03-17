# Standard library imports
import datetime
import base64

# Related third-party imports
import streamlit as st
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pandas as pd
import searchconsole

# Configuration: Set to True if running locally, False if running on Streamlit Cloud
IS_LOCAL = False

# Constants
SEARCH_TYPES = ["web", "image", "video", "news", "discover", "googleNews"]
DATE_RANGE_OPTIONS = [
    "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months",
    "Last 12 Months", "Last 16 Months", "Custom Range"
]
DEVICE_OPTIONS = ["All Devices", "desktop", "mobile", "tablet"]
BASE_DIMENSIONS = ["page", "query", "country", "date"]
MAX_ROWS = 1_000_000
DF_PREVIEW_ROWS = 100


# -------------
# Streamlit App Configuration
# -------------

def setup_streamlit():
    """ Configures Streamlit UI settings and layout. """
    st.set_page_config(page_title="✨ Simple Google Search Console Data", layout="wide")
    st.title("✨ Simple Google Search Console Data Extractor")
    st.markdown(f"### Lightweight GSC Data Extractor (Max {MAX_ROWS:,} Rows)")

    st.markdown(
        """
        <p>
            Created by <a href="https://twitter.com/LeeFootSEO" target="_blank">LeeFootSEO</a> |
            <a href="https://leefoot.co.uk" target="_blank">More Apps & Scripts on my Website</a>
        </p>
        """,
        unsafe_allow_html=True
    )
    st.divider()


def init_session_state():
    """ Initializes session state variables if not already set. """
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


# -------------
# Google Authentication Functions
# -------------

def load_config():
    """ Loads the Google API client configuration from Streamlit secrets. """
    return {
        "installed": {
            "client_id": str(st.secrets["installed"]["client_id"]),
            "client_secret": str(st.secrets["installed"]["client_secret"]),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://accounts.google.com/o/oauth2/token",
            "redirect_uris": ["http://localhost:8501"] if IS_LOCAL else [str(st.secrets["installed"]["redirect_uris"][0])]
        }
    }


def init_oauth_flow(client_config):
    """ Initializes the OAuth flow for Google authentication. """
    scopes = ["https://www.googleapis.com/auth/webmasters"]
    return Flow.from_client_config(
        client_config,
        scopes=scopes,
        redirect_uri=client_config["installed"]["redirect_uris"][0],
    )


def google_auth(client_config):
    """ Starts Google OAuth authentication flow and returns the authorization URL. """
    flow = init_oauth_flow(client_config)
    auth_url, _ = flow.authorization_url(prompt="consent")
    return flow, auth_url


def refresh_credentials():
    """ Refreshes expired credentials if needed. """
    if "credentials" in st.session_state and st.session_state.credentials.expired:
        st.session_state.credentials.refresh(Request())


# -------------
# Data Fetching Functions
# -------------

def list_gsc_properties(credentials):
    """ Lists all GSC properties for the authenticated user. """
    try:
        service = build('webmasters', 'v3', credentials=credentials)
        site_list = service.sites().list().execute()
        return [site['siteUrl'] for site in site_list.get('siteEntry', [])] or ["No properties found"]
    except Exception as e:
        st.error(f"Failed to retrieve properties: {str(e)}")
        return []


def fetch_gsc_data(webproperty, search_type, start_date, end_date, dimensions, device_type=None):
    """ Fetches GSC data and handles errors. """
    query = webproperty.query.range(start_date, end_date).search_type(search_type).dimension(*dimensions)

    if 'device' in dimensions and device_type and device_type != 'All Devices':
        query = query.filter('device', 'equals', device_type.lower())

    try:
        return query.limit(MAX_ROWS).get().to_dataframe()
    except Exception as e:
        st.error(f"Error fetching GSC data: {str(e)}")
        return pd.DataFrame()


# -------------
# Utility Functions
# -------------

def calc_date_range(selection, custom_start=None, custom_end=None):
    """ Returns the start and end date based on the selection. """
    range_map = {
        'Last 7 Days': 7, 'Last 30 Days': 30, 'Last 3 Months': 90,
        'Last 6 Months': 180, 'Last 12 Months': 365, 'Last 16 Months': 480
    }
    today = datetime.date.today()
    
    if selection == 'Custom Range':
        if custom_start and custom_end and custom_start <= custom_end:
            return custom_start, custom_end
        else:
            st.error("Invalid custom date range. Ensure start date is before the end date.")
            return today - datetime.timedelta(days=7), today

    return today - datetime.timedelta(days=range_map.get(selection, 7)), today


# -------------
# UI Components
# -------------

def show_google_sign_in(auth_url):
    """ Displays the Google Sign-in button. """
    with st.sidebar:
        if st.button("Sign in with Google"):
            st.write('Please click the link below to authenticate:')
            st.markdown(f'[Google Sign-In]({auth_url})', unsafe_allow_html=True)


def show_fetch_data_button(webproperty, search_type, start_date, end_date, selected_dimensions):
    """ Displays the 'Fetch Data' button and handles data retrieval. """
    if st.button("Fetch Data"):
        report = fetch_gsc_data(webproperty, search_type, start_date, end_date, selected_dimensions)
        if not report.empty:
            st.dataframe(report.head(DF_PREVIEW_ROWS))
            csv = report.to_csv(index=False, encoding='utf-8-sig')
            b64_csv = base64.b64encode(csv.encode()).decode()
            href = f'<a href="data:file/csv;base64,{b64_csv}" download="search_console_data.csv">Download CSV</a>'
            st.markdown(href, unsafe_allow_html=True)


# -------------
# Main Streamlit App Function
# -------------

def main():
    """ The main function for the Streamlit app. """
    setup_streamlit()
    init_session_state()
    
    client_config = load_config()
    st.session_state.auth_flow, st.session_state.auth_url = google_auth(client_config)

    query_params = st.query_params
    auth_code = query_params.get("code", [None])[0]

    if auth_code and not st.session_state.get('credentials'):
        st.session_state.auth_flow.fetch_token(code=auth_code)
        st.session_state.credentials = st.session_state.auth_flow.credentials

    if not st.session_state.get('credentials'):
        show_google_sign_in(st.session_state.auth_url)
    else:
        refresh_credentials()
        properties = list_gsc_properties(st.session_state.credentials)
        if properties:
            webproperty = properties[0]  # Default to first property
            show_fetch_data_button(webproperty, "web", datetime.date.today() - datetime.timedelta(days=7), datetime.date.today(), ["page", "query"])


if __name__ == "__main__":
    main()
