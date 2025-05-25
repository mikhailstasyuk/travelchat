import io
from unittest.mock import Mock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_weaviate_client():
    return Mock()


@pytest.fixture
def app():
    with patch("app.main.get_weaviate_client") as mock_client:
        mock_client.return_value = Mock()
        from app.main import app

        app.dependency_overrides = {}
        yield app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def sample_csv_data():
    df = pd.DataFrame(
        {
            "messages_json": [
                '{"role": "user", "content": "test message"}',
                '{"role": "assistant", "content": "test response"}',
            ]
        }
    )
    csv_buffer = io.BytesIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    return csv_buffer.getvalue()
