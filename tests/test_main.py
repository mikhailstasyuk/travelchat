from unittest.mock import Mock, patch


def test_index_data_success(client, sample_csv_data):
    with patch("app.main.weaviate_client", Mock()), patch(
        "app.main.prepare_documents_from_df",
        return_value=[{"content": "test"}],
    ), patch("app.main.index_documents"):

        response = client.post(
            "/index-data/",
            files={"file": ("test.csv", sample_csv_data, "text/csv")},
        )
        assert response.status_code == 200
        assert "Successfully processed" in response.json()["message"]


def test_index_data_invalid_file(client):
    with patch("app.main.weaviate_client", Mock()):
        response = client.post(
            "/index-data/",
            files={"file": ("test.txt", b"invalid content", "text/plain")},
        )
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]


def test_query_success(client):
    mock_docs = [{"content": "test content", "original_df_index": 0}]

    with patch("app.main.weaviate_client", Mock()), patch(
        "app.main.search_weaviate", return_value=mock_docs
    ), patch("app.main.get_chat_completion", return_value="test answer"):

        response = client.post(
            "/query/", json={"query": "test query", "top_k": 3}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "test answer"
        assert len(data["retrieved_contexts"]) == 1


def test_query_no_context(client):
    with patch("app.main.weaviate_client", Mock()), patch(
        "app.main.search_weaviate", return_value=[]
    ), patch("app.main.get_chat_completion", return_value="fallback answer"):

        response = client.post("/query/", json={"query": "test query"})
        assert response.status_code == 200
        assert "No relevant context found" in response.json()["answer"]


def test_clear_index_success(client):
    with patch("app.main.weaviate_client", Mock()), patch(
        "app.main.clear_all_data"
    ):

        response = client.post("/clear-index/")
        assert response.status_code == 200
        assert "Successfully cleared" in response.json()["message"]


def test_weaviate_client_unavailable(client):
    with patch("app.main.weaviate_client", None):
        response = client.post("/query/", json={"query": "test"})
        assert response.status_code == 503
        assert "Weaviate client not available" in response.json()["detail"]
