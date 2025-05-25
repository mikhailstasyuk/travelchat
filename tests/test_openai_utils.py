from unittest.mock import Mock, patch

import pytest

from app.utils.openai_utils import get_chat_completion, get_embedding


@pytest.fixture
def mock_openai_client():
    with patch("app.utils.openai_utils.client") as mock:
        yield mock


def test_get_embedding_success(mock_openai_client):
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]
    mock_openai_client.embeddings.create.return_value = mock_response

    result = get_embedding("test text")

    assert result == [0.1, 0.2, 0.3]
    mock_openai_client.embeddings.create.assert_called_once()


def test_get_chat_completion_with_context(mock_openai_client):
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Test response"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    result = get_chat_completion("test prompt", context="test context")

    assert result == "Test response"
    call_args = mock_openai_client.chat.completions.create.call_args
    assert len(call_args[1]["messages"]) == 2
    assert "context" in call_args[1]["messages"][0]["content"]


def test_get_chat_completion_without_context(mock_openai_client):
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Test response"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    result = get_chat_completion("test prompt")

    assert result == "Test response"
    call_args = mock_openai_client.chat.completions.create.call_args
    assert "context" not in call_args[1]["messages"][0]["content"]


def test_get_chat_completion_error_handling(mock_openai_client):
    mock_openai_client.chat.completions.create.side_effect = Exception(
        "API Error"
    )

    result = get_chat_completion("test prompt")

    assert "Sorry, I encountered an error" in result
