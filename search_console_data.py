import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pandas as pd
from datetime import datetime, timedelta
import json

# Authenticate using Streamlit secrets
def authenticate_gsc():
    if 'gcp_credentials' not in st.secrets or 'gcp_credentials_json' not in st.secrets['gcp_credentials']:
        st.error("Google Cloud credentials not found or improperly structured in secrets.toml.")
        return None

    try:
        credentials_json = json.loads(st.secrets['gcp_credentials']['gcp_credentials_json'])
        credentials = service_account.Credentials.from_service_account_info(
            credentials_json, scopes=['https://www.googleapis.com/auth/webmasters.readonly']
        )
        service = build('searchconsole', 'v1', credentials=credentials)
        return service
    except Exception as e:
        st.error(f"Error authenticating with Google Search Console: {e}")
        return None

# Fetch data from GSC
def fetch_gsc_data(service, site_url, start_date, end_date, dimensions=['query', 'page']):
    request = {
        'startDate': start_date,
        'endDate': end_date,
        'dimensions': dimensions,
        'rowLimit': 1000
    }
    try:
        response = service.searchanalytics().query(siteUrl=site_url, body=request).execute()
        rows = response.get('rows', [])
        data = [
            {
                'query': row['keys'][0],
                'page': row['keys'][1],
                'clicks': row['clicks'],
                'impressions': row['impressions'],
                'ctr': row['ctr'],
                'position': row['position']
            } for row in rows
        ]
        return pd.DataFrame(data)
    except HttpError as e:
        st.error(f"An HTTP error occurred: {e.resp.status}, {e.reason}")
        return pd.DataFrame()  # Return an empty DataFrame on error

# Streamlit app
def main():
    st.title("Google Search Console Data Extractor")
    
    # Authenticate
    service = authenticate_gsc()
    if not service:
        st.stop()
    
    site_url = st.text_input("Enter your site URL (e.g., https://example.com):")
    
    if site_url:
        # Date selector
        date_options = {
            "1 Month": (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            "3 Months": (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'),
            "6 Months": (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d'),
            "12 Months": (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
            "Custom": None
        }
        selected_range = st.selectbox("Select date range:", list(date_options.keys()))
        
        if selected_range == "Custom":
            start_date = st.date_input("Start date:", datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            end_date = st.date_input("End date:", datetime.now()).strftime('%Y-%m-%d')
        else:
            start_date = date_options[selected_range]
            end_date = datetime.now().strftime('%Y-%m-%d')

        # Fetch data
        if st.button("Fetch Data"):
            data = fetch_gsc_data(service, site_url, start_date, end_date)
            if not data.empty:
                st.write("### Search Console Data")
                st.dataframe(data)

                # Add filters for queries and landing pages
                queries = data['query'].unique()
                selected_queries = st.multiselect("Filter by queries:", queries)
                if selected_queries:
                    data = data[data['query'].isin(selected_queries)]

                pages = data['page'].unique()
                selected_pages = st.multiselect("Filter by landing pages:", pages)
                if selected_pages:
                    data = data[data['page'].isin(selected_pages)]

                st.write("### Filtered Data")
                st.dataframe(data)
            else:
                st.warning("No data available for the selected period.")
        
        # Data comparison (optional)
        st.write("### Compare with Another Date Range")
        comparison_option = st.radio("Select comparison range:", ["Previous Period", "Custom"])
        
        if comparison_option == "Custom":
            compare_start_date = st.date_input("Compare start date:", datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
            compare_end_date = st.date_input("Compare end date:", datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        else:
            period_length = datetime.strptime(end_date, '%Y-%m-%d') - datetime.strptime(start_date, '%Y-%m-%d')
            compare_start_date = (datetime.strptime(start_date, '%Y-%m-%d') - period_length).strftime('%Y-%m-%d')
            compare_end_date = start_date
        
        if st.button("Compare"):
            compare_data = fetch_gsc_data(service, site_url, compare_start_date, compare_end_date)
            if not compare_data.empty:
                st.write("### Comparison Data")
                st.dataframe(compare_data)
            else:
                st.warning("No comparison data available.")

if __name__ == "__main__":
    main()
