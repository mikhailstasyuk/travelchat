import json

import pandas as pd
import pytest

from app.utils.data_processor import (
    parse_messages_json,
    prepare_documents_from_df,
)


def test_parse_messages_json_string():
    json_str = '[{"id": 1, "text": "test"}]'
    result = parse_messages_json(json_str)
    assert result == [{"id": 1, "text": "test"}]


def test_parse_messages_json_list():
    json_list = [{"id": 1, "text": "test"}]
    result = parse_messages_json(json_list)
    assert result == [{"id": 1, "text": "test"}]


def test_parse_messages_json_invalid():
    invalid_json = "invalid json"
    result = parse_messages_json(invalid_json)
    assert result == []


def test_parse_messages_json_other_type():
    result = parse_messages_json(123)
    assert result == []


def test_prepare_documents_success():
    data = {
        "messages_json": [
            '[{"id": 1, "date_unixtime": 1648800000, "text": "test message"}]'
        ]
    }
    df = pd.DataFrame(data)

    result = prepare_documents_from_df(df)

    assert len(result) == 1
    assert result[0]["content"] == "test message"
    assert result[0]["original_df_index"] == 0
    assert result[0]["start_time"] == 1648800000
    assert result[0]["message_ids"] == "[1]"


def test_prepare_documents_no_messages_column():
    df = pd.DataFrame({"other_col": ["test"]})

    with pytest.raises(
        ValueError, match="DataFrame must contain a 'messages_json' column"
    ):
        prepare_documents_from_df(df)


def test_prepare_documents_empty_messages():
    data = {"messages_json": ["[]", "invalid json"]}
    df = pd.DataFrame(data)

    result = prepare_documents_from_df(df)
    assert len(result) == 0


def test_prepare_documents_complex_text():
    data = {
        "messages_json": ['[{"id": 1, "text": [{"text": "Hello"}, " world"]}]']
    }
    df = pd.DataFrame(data)

    result = prepare_documents_from_df(df)
    assert result[0]["content"] == "Hello  world"


def test_prepare_documents_multiple_messages():
    data = {
        "messages_json": [
            '[{"id": 1, "date_unixtime": 100, "text": "msg1"}, '
            '{"id": 2, "date_unixtime": 200, "text": "msg2"}]'
        ]
    }
    df = pd.DataFrame(data)

    result = prepare_documents_from_df(df)
    assert result[0]["content"] == "msg1\nmsg2"
    assert result[0]["start_time"] == 100
    assert result[0]["end_time"] == 200
    assert json.loads(result[0]["message_ids"]) == [1, 2]


def test_prepare_documents_no_timestamps():
    data = {"messages_json": ['[{"id": 1, "text": "test"}]']}
    df = pd.DataFrame(data)

    result = prepare_documents_from_df(df)
    assert result[0]["start_time"] is None
    assert result[0]["end_time"] is None
