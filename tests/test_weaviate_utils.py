from unittest.mock import MagicMock, Mock, patch

import pytest
from weaviate.exceptions import UnexpectedStatusCodeException  # type: ignore

from app.utils.weaviate_utils import (
    clear_all_data,
    create_schema_if_not_exists,
    get_weaviate_client,
    index_documents,
    search_weaviate,
)


@pytest.fixture
def mock_weaviate_client():
    client = Mock()
    client.is_ready.return_value = True
    client.schema.exists.return_value = True
    client.batch = MagicMock()
    client.batch.get_failed_objects.return_value = []
    return client


def test_get_weaviate_client_success():
    with patch(
        "app.utils.weaviate_utils.weaviate.Client"
    ) as mock_client_class:
        mock_client = Mock()
        mock_client.is_ready.return_value = True
        mock_client_class.return_value = mock_client

        client = get_weaviate_client()
        assert client == mock_client


def test_get_weaviate_client_not_ready():
    with patch(
        "app.utils.weaviate_utils.weaviate.Client"
    ) as mock_client_class, patch("app.utils.weaviate_utils._client", None):
        mock_client = Mock()
        mock_client.is_ready.return_value = False
        mock_client_class.return_value = mock_client

        with pytest.raises(ConnectionError):
            get_weaviate_client()


def test_create_schema_exists(mock_weaviate_client):
    mock_weaviate_client.schema.get.return_value = {"class": "ChatThread"}

    create_schema_if_not_exists(mock_weaviate_client)
    mock_weaviate_client.schema.create_class.assert_not_called()


def test_create_schema_not_exists(mock_weaviate_client):
    mock_response = Mock()
    mock_response.status_code = 404
    mock_weaviate_client.schema.get.side_effect = (
        UnexpectedStatusCodeException("", mock_response)
    )

    create_schema_if_not_exists(mock_weaviate_client)
    mock_weaviate_client.schema.create_class.assert_called_once()


def test_clear_all_data_success(mock_weaviate_client):
    clear_all_data(mock_weaviate_client)
    mock_weaviate_client.schema.delete_class.assert_called_once()


def test_index_documents_success(mock_weaviate_client):
    documents = [{"content": "test content", "original_df_index": 0}]

    # Mock the batch context manager properly
    batch_context = MagicMock()
    mock_weaviate_client.batch.__enter__ = Mock(return_value=batch_context)
    mock_weaviate_client.batch.__exit__ = Mock(return_value=None)

    with patch(
        "app.utils.weaviate_utils.get_embedding", return_value=[0.1, 0.2]
    ), patch("app.utils.weaviate_utils.create_schema_if_not_exists"):

        index_documents(mock_weaviate_client, documents)
        batch_context.add_data_object.assert_called_once()


def test_index_documents_empty_content(mock_weaviate_client):
    documents = [{"content": "", "original_df_index": 0}]

    with patch("app.utils.weaviate_utils.create_schema_if_not_exists"):
        index_documents(mock_weaviate_client, documents)
        mock_weaviate_client.batch.add_data_object.assert_not_called()


def test_search_weaviate_success(mock_weaviate_client):
    mock_result = {
        "data": {
            "Get": {
                "ChatThread": [
                    {"content": "test", "_additional": {"distance": 0.1}}
                ]
            }
        }
    }

    mock_query = mock_weaviate_client.query.get.return_value
    mock_near_vector = mock_query.with_near_vector.return_value
    mock_with_limit = mock_near_vector.with_limit.return_value
    mock_with_limit.do.return_value = mock_result

    with patch(
        "app.utils.weaviate_utils.get_embedding", return_value=[0.1, 0.2]
    ):
        results = search_weaviate(mock_weaviate_client, "test query")

    assert len(results) == 1
    assert results[0]["content"] == "test"


def test_search_weaviate_error(mock_weaviate_client):
    mock_weaviate_client.query.get.side_effect = Exception("Search error")

    with patch(
        "app.utils.weaviate_utils.get_embedding", return_value=[0.1, 0.2]
    ):
        results = search_weaviate(mock_weaviate_client, "test query")
        assert results == []
