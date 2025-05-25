import json
import os

import pandas as pd
import requests  # To call FastAPI
import streamlit as st

FASTAPI_URL = os.getenv(
    "API_URL", "http://localhost:8000"
)  # Make sure this matches your FastAPI server

st.set_page_config(layout="wide")
st.title("📄 Chat Data RAG Explorer")


# --- Helper function to call FastAPI ---
def call_fastapi(endpoint, method="post", data=None, files=None, params=None):
    try:
        if method == "post":
            response = requests.post(
                f"{FASTAPI_URL}{endpoint}",
                data=data,
                files=files,
                params=params,
                timeout=120,
            )  # Increased timeout
        elif method == "get":
            response = requests.get(
                f"{FASTAPI_URL}{endpoint}", params=params, timeout=30
            )
        else:
            st.error(f"Unsupported method: {method}")
            return None

        response.raise_for_status()  # HTTPError for bad responses (4XX or 5XX)
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error(
            f"Connection Error: Could not connect to FastAPI at "
            f"{FASTAPI_URL}. Is the backend server running?"
        )
        return None
    except requests.exceptions.Timeout:
        st.error(
            "Request timed out. The server might be busy or the "
            "operation is taking too long."
        )
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP Error: {e.response.status_code} - {e.response.text}")
        try:
            # Try to parse error detail if JSON
            error_detail = e.response.json().get("detail", e.response.text)
            st.error(f"Detail: {error_detail}")
        except json.JSONDecodeError:
            pass  # If not JSON, text is already shown
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
        return None


# --- Sidebar for Data Ingestion ---
st.sidebar.header("⚙️ Data Management")

uploaded_file = st.sidebar.file_uploader(
    "Upload DataFrame (CSV or Parquet with 'messages_json' column)",
    type=["csv", "parquet"],
)

if uploaded_file:
    st.sidebar.write(
        f"Uploaded: `{uploaded_file.name}` ({uploaded_file.type})"
    )

    # Display a preview of the DataFrame
    try:
        if uploaded_file.name.endswith(".csv"):
            df_preview = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(".parquet"):
            # Need to reset pointer for parquet after type check
            uploaded_file.seek(0)
            df_preview = pd.read_parquet(uploaded_file)

        st.sidebar.subheader("DataFrame Preview (first 5 rows):")
        st.sidebar.dataframe(df_preview.head())

        # Check for 'messages_json' column
        if "messages_json" not in df_preview.columns:
            st.sidebar.error(
                "The uploaded file MUST contain a 'messages_json' column."
            )
            st.stop()  # Stop further processing if column is missing
        else:
            st.sidebar.success("'messages_json' column found!")

    except Exception as e:
        st.sidebar.error(f"Error reading file: {e}")
        st.stop()

    # Reset file pointer before sending to FastAPI
    uploaded_file.seek(0)

    if st.sidebar.button("🚀 Index Uploaded Data", key="index_data_button"):
        with st.spinner(
            "Processing and indexing data... This may take a while."
        ):
            files = {
                "file": (
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                    uploaded_file.type,
                )
            }
            response_json = call_fastapi("/index-data/", files=files)
            if response_json:
                st.sidebar.success(
                    response_json.get("message", "Indexing initiated!")
                )
                st.balloons()

if st.sidebar.button(
    "⚠️ Clear Entire Index (DANGER!)", key="clear_index_button"
):
    if st.sidebar.checkbox(
        "Confirm clearing ALL data from Weaviate? This cannot be undone.",
        value=False,
        key="confirm_clear",
    ):
        with st.spinner("Clearing index..."):
            response_json = call_fastapi(
                "/clear-index/", method="post"
            )  # No data/files needed
            if response_json:
                st.sidebar.success(
                    response_json.get("message", "Index cleared!")
                )
                st.rerun()  # Rerun to reflect changes
            else:
                st.sidebar.error("Failed to clear index.")
    else:
        st.sidebar.warning("Clear operation not confirmed.")


# --- Main Area for RAG Querying ---
st.header("💬 Ask Questions About Your Chat Data")

user_query = st.text_area(
    "Enter your question:",
    height=100,
    key="user_query_input",
    placeholder="e.g., What are people saying about Tbilisi apartment prices?",
)
top_k_retrieval = st.slider(
    "Number of relevant contexts to retrieve (top_k):",
    1,
    10,
    3,
    key="top_k_slider",
)

if st.button("💡 Get Answer", key="get_answer_button"):
    if not user_query:
        st.warning("Please enter a question.")
    else:
        with st.spinner(
            "Searching for relevant chats and generating an answer..."
        ):
            payload = {"query": user_query, "top_k": top_k_retrieval}

            # Using requests.post directly with json payload
            try:
                response = requests.post(
                    f"{FASTAPI_URL}/query/", json=payload, timeout=120
                )
                response.raise_for_status()
                response_json = response.json()

                if response_json:
                    st.subheader("🤖 Answer:")
                    st.markdown(
                        response_json.get("answer", "No answer received.")
                    )

                    st.subheader("📚 Retrieved Contexts:")
                    contexts = response_json.get("retrieved_contexts", [])
                    if contexts:
                        for i, ctx in enumerate(contexts):
                            with st.expander(
                                f"Context {i+1} (DF Index: "
                                f"{ctx.get('original_df_index', 'N/A')}, "
                                f"Distance: {ctx.get('distance', 'N/A'):.4f})"
                            ):
                                st.text(
                                    ctx.get(
                                        "content_preview",
                                        "No content preview.",
                                    )
                                )
                    else:
                        st.info(
                            "No specific contexts were retrieved "
                            "for this query."
                        )
                else:
                    st.error("Failed to get an answer from the RAG system.")

            except requests.exceptions.ConnectionError:
                st.error(
                    f"Connection Error: "
                    f"Could not connect to FastAPI at {FASTAPI_URL}."
                )
            except requests.exceptions.Timeout:
                st.error(
                    "Request timed out. The server might be busy "
                    "or the operation is taking too long."
                )
            except requests.exceptions.HTTPError as e:
                st.error(f"HTTP Error: {e.response.status_code}")
                try:
                    error_detail = e.response.json().get(
                        "detail", e.response.text
                    )
                    st.error(f"Detail: {error_detail}")
                except json.JSONDecodeError:
                    st.error(f"Detail: {e.response.text}")  # If not JSON
            except Exception as e:
                st.error(f"An unexpected error occurred: {str(e)}")

st.markdown("---")
st.markdown("Built with FastAPI, Weaviate, OpenAI, and Streamlit.")
