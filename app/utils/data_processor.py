import json
from typing import Any, Dict, List, Union

import pandas as pd


def parse_messages_json(
    messages_data: Union[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    Parses the messages_json column,
    which can be a string or already a list.
    """
    if isinstance(messages_data, str):
        try:
            return json.loads(messages_data)
        except json.JSONDecodeError:
            return []  # Or raise an error
    elif isinstance(messages_data, list):
        return messages_data
    return []


def prepare_documents_from_df(
    df: pd.DataFrame, df_row_index_col: str = "original_df_index"
) -> List[Dict[str, Any]]:
    """
    Processes a DataFrame to extract chat threads for indexing.
    Each document will represent a full chat thread.
    """
    documents = []
    if "messages_json" not in df.columns:
        raise ValueError("DataFrame must contain a 'messages_json' column.")

    for index, row in df.iterrows():
        messages = parse_messages_json(row["messages_json"])
        if not messages:
            continue

        thread_content = []
        min_timestamp = float("inf")
        max_timestamp = float("-inf")
        message_ids = []

        for msg in messages:
            text = msg.get("text", "")
            if isinstance(
                text, list
            ):  # Handle cases where text might be a list of segments
                text = " ".join(
                    t.get("text", "") if isinstance(t, dict) else str(t)
                    for t in text
                )
            elif not isinstance(text, str):
                text = str(text)  # Ensure text is a string

            thread_content.append(text.strip())
            if msg.get("date_unixtime"):
                min_timestamp = min(min_timestamp, msg["date_unixtime"])
                max_timestamp = max(max_timestamp, msg["date_unixtime"])
            if msg.get("id"):
                message_ids.append(msg["id"])

        full_thread_text = "\n".join(filter(None, thread_content))

        if full_thread_text:
            doc = {
                "content": full_thread_text,
                df_row_index_col: index,  # Store original df index
                "start_time": (
                    int(min_timestamp)
                    if min_timestamp != float("inf")
                    else None
                ),
                "end_time": (
                    int(max_timestamp)
                    if max_timestamp != float("-inf")
                    else None
                ),
                "message_ids": json.dumps(message_ids),
            }
            documents.append(doc)
    return documents


if __name__ == "__main__":
    # Example Usage:
    sample_data = {
        "messages_json": [
            """
            [
            {
                "id": 223,
                "date_unixtime": 1648808078,
                "text": "Привет! Кто-нибудь знает, за сколько можно в "
                       "Тбилиси снять 1-комнатную квартиру на месяц? "
                       "Желательно не совсем потрепанную.",
                "reply_to_message_id": null
            },
                {
                "id": 239,
                "date_unixtime": 1648817374,
                "text": "Привет 👋 \\nЗнакомые недавно сняли за 400$."
                       "\\nЗа 300$, говорят, уже нереально что-то "
                       "найти даже на окраине… \\n"
                       "В центре цены от 600-1000$.",
                "reply_to_message_id": 223
                }
            ]
            """,
            [
                {
                    "id": 1,
                    "date_unixtime": 1648800000,
                    "text": "Second thread message 1",
                },
                {
                    "id": 2,
                    "date_unixtime": 1648800001,
                    "text": "Second thread message 2",
                },
            ],
            '[{"id": 10, "text": [{"type": "bold", "text": '
            '"Important:"}, " call me ASAP"]}]',
        ]
    }
    df = pd.DataFrame(sample_data)
    processed_docs = prepare_documents_from_df(df)
    for d in processed_docs:
        print(d)
        print("-" * 20)
