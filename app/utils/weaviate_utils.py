import os
from typing import Any, Dict, List

import weaviate  # type: ignore
from dotenv import load_dotenv

from app.utils.openai_utils import get_embedding

load_dotenv()

WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_CLASS_NAME = os.getenv("WEAVIATE_CLASS_NAME", "ChatThread")
DF_ROW_INDEX_COL = "original_df_index"  # Must match data_processor

# Global client instance
_client = None


def get_weaviate_client():
    global _client
    if _client is None:
        try:
            _client = weaviate.Client(WEAVIATE_URL)
            if not _client.is_ready():
                raise ConnectionError("Weaviate is not ready.")
            print("Weaviate client initialized and ready.")
        except Exception as e:
            print(f"Failed to connect to Weaviate at {WEAVIATE_URL}: {e}")
            _client = None  # Reset on failure
            raise
    return _client


def create_schema_if_not_exists(client: weaviate.Client):
    """Creates the ChatThread schema in Weaviate if it doesn't exist."""
    try:
        client.schema.get(WEAVIATE_CLASS_NAME)
        print(f"Schema '{WEAVIATE_CLASS_NAME}' already exists.")
    except weaviate.exceptions.UnexpectedStatusCodeException as e:
        if e.status_code == 404:  # Not found, so create it
            class_obj = {
                "class": WEAVIATE_CLASS_NAME,
                "vectorizer": "none",  # We provide our own vectors
                "properties": [
                    {
                        "name": "content",
                        "dataType": ["text"],
                        "description": (
                            "The concatenated text of the chat thread"
                        ),
                    },
                    {
                        "name": DF_ROW_INDEX_COL,
                        "dataType": ["int"],
                        "description": (
                            "Original index from the input DataFrame"
                        ),
                    },
                    {
                        "name": "start_time",
                        "dataType": ["int"],  # Store as unixtime
                        "description": (
                            "Unixtime of the first message in the thread"
                        ),
                    },
                    {
                        "name": "end_time",
                        "dataType": ["int"],
                        "description": (
                            "Unixtime of the last message in the thread"
                        ),
                    },
                    {
                        "name": "message_ids",
                        "dataType": ["text"],  # Storing as JSON string
                        "description": (
                            "JSON string of message IDs in the thread"
                        ),
                    },
                ],
            }
            client.schema.create_class(class_obj)
            print(f"Schema '{WEAVIATE_CLASS_NAME}' created.")
        else:
            raise  # Re-raise other unexpected errors


def clear_all_data(
    client: weaviate.Client, class_name: str = WEAVIATE_CLASS_NAME
):
    """Deletes all objects from the specified class. Use with caution!"""
    try:
        if client.schema.exists(class_name):
            client.schema.delete_class(class_name)
            print(f"Class '{class_name}' and all its data deleted.")
        else:
            print(f"Class '{class_name}' does not exist, nothing to delete.")
    except Exception as e:
        print(f"Error deleting class '{class_name}': {e}")


def index_documents(client: weaviate.Client, documents: List[Dict[str, Any]]):
    """Indexes documents into Weaviate with OpenAI embeddings."""
    create_schema_if_not_exists(client)  # Ensure schema exists

    with client.batch as batch:
        batch.batch_size = 100  # Adjust as needed
        for i, doc_properties in enumerate(documents):
            if not doc_properties.get("content"):
                print(f"Skipping document {i} due to empty content.")
                continue

            try:
                # Generate embedding for the 'content' field
                embedding = get_embedding(doc_properties["content"])

                batch.add_data_object(
                    data_object=doc_properties,
                    class_name=WEAVIATE_CLASS_NAME,
                    vector=embedding,  # Add the externally generated embedding
                )
                if (i + 1) % 20 == 0:
                    print(
                        f"Prepared {i+1}/{len(documents)} documents "
                        f"for batching..."
                    )
            except Exception as e:
                print(
                    f"Error processing document {i} "
                    f"('{doc_properties.get('content', '')[:50]}...'): {e}"
                )
    n_failed_objects = len(client.batch.get_failed_objects())
    print(
        f"Successfully indexed "
        f"{n_failed_objects == 0 and len(documents) > 0} "
        f"documents."
    )
    if client.batch.get_failed_objects():
        print(
            f"Failed to index "
            f"{len(client.batch.get_failed_objects())} documents."
        )
        for failed in client.batch.get_failed_objects():
            print(f"Failed object: {failed.message} - {failed.object_}")


def search_weaviate(
    client: weaviate.Client, query_text: str, top_k: int = 3
) -> List[Dict[str, Any]]:
    """Searches Weaviate for documents similar to the query_text."""
    query_embedding = get_embedding(query_text)

    # Define the fields to retrieve
    properties_to_retrieve = [
        "content",
        DF_ROW_INDEX_COL,
        "start_time",
        "end_time",
        "message_ids",
        "_additional {distance}",
    ]

    try:
        result = (
            client.query.get(WEAVIATE_CLASS_NAME, properties_to_retrieve)
            .with_near_vector({"vector": query_embedding})
            .with_limit(top_k)
            .do()
        )

        # Extract relevant data from the Weaviate response
        hits = (
            result.get("data", {}).get("Get", {}).get(WEAVIATE_CLASS_NAME, [])
        )
        return hits
    except Exception as e:
        print(f"Error during Weaviate search: {e}")
        return []


if __name__ == "__main__":
    # Example Usage (requires Weaviate running and OpenAI API key)
    try:
        client = get_weaviate_client()
        print("Connected to Weaviate.")

        # 1. (Optional) Clear existing data and schema for a fresh start
        # clear_all_data(client, WEAVIATE_CLASS_NAME) # Be careful with this!

        # 2. Ensure schema exists
        create_schema_if_not_exists(client)

        # 3. Prepare some sample documents (using data_processor structure)
        import pandas as pd
        from data_processor import prepare_documents_from_df  # type: ignore

        sample_data = {
            "messages_json": [
                """
                [{"id": 223,
                "date_unixtime": 1648808078,
                "text": "Привет! Кто-нибудь знает, за сколько можно в "
                "Тбилиси снять 1-комнатную квартиру на месяц? "
                "Желательно не совсем потрепанную.",
                "reply_to_message_id": null},
                {"id": 239,
                "date_unixtime": 1648817374,
                "text": "Привет 👋 \\nЗнакомые недавно сняли за 400$."
                "\\nЗа 300$, говорят, уже нереально что-то найти даже "
                "на окраине… \\nВ центре цены от 600-1000$.",
                "reply_to_message_id": 223}]
                """,
                '[{"id": 1, "text": "Ищу хороший итальянский ресторан "'
                '"поблизости."}]',
                '[{"id": 2, "text": "Порекомендуйте, пожалуйста, "'
                '"сантехника."}]',
            ]
        }
        df = pd.DataFrame(sample_data)
        documents_to_index = prepare_documents_from_df(df)

        if documents_to_index:
            print(f"\nIndexing {len(documents_to_index)} documents...")
            index_documents(client, documents_to_index)
            print("Indexing complete.")
        else:
            print("No documents to index.")

        # 4. Perform a search
        query = "cost of renting an apartment in Tbilisi"
        print(f"\nSearching for: '{query}'")
        search_results = search_weaviate(client, query, top_k=2)

        if search_results:
            print("\nSearch Results:")
            for res in search_results:
                print(f"  Content: {res['content'][:100]}...")
                print(f"  Original DF Index: {res[DF_ROW_INDEX_COL]}")
                print(f"  Distance: {res['_additional']['distance']:.4f}")
                print("-" * 10)
        else:
            print("No results found.")

    except ConnectionError as ce:
        print(
            f"Connection Error: {ce}. Is Weaviate running and "
            f"accessible at {WEAVIATE_URL}?"
        )
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
