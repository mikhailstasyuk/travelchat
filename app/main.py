import io
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List

import httpx
import pandas as pd
from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.utils.data_processor import prepare_documents_from_df
from app.utils.openai_utils import get_chat_completion
from app.utils.weaviate_utils import (
    WEAVIATE_CLASS_NAME,
    clear_all_data,
    get_weaviate_client,
    index_documents,
    search_weaviate,
)

# Global variable to store Weaviate client
weaviate_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global weaviate_client
    try:
        weaviate_client = get_weaviate_client()
        print("FastAPI started. Weaviate client initialized.")
    except Exception as e:
        print(f"FastAPI startup: Failed to initialize Weaviate client: {e}")
        # You might want to prevent app startup if Weaviate is critical
        # For now, it will allow startup but endpoints might fail.

    yield

    # Shutdown (optional cleanup)
    if weaviate_client:
        try:
            # Add any cleanup logic here if needed
            print("Shutting down Weaviate client...")
        except Exception as e:
            print(f"Error during shutdown: {e}")


app = FastAPI(title="Chat RAG API", lifespan=lifespan)

# CORS (Cross-Origin Resource Sharing) for local development
# Allows Streamlit (e.g., on port 8501) to talk to FastAPI (e.g., on port 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],  # Allow all origins for simplicity, restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration"""
    health_status = {"status": "healthy", "services": {}}

    # Check Weaviate connection
    weaviate_url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{weaviate_url}/v1/.well-known/ready", timeout=5
            )
            health_status["services"]["weaviate"] = (
                "healthy" if response.status_code == 200 else "unhealthy"
            )
    except Exception:
        health_status["services"]["weaviate"] = "unhealthy"
        health_status["status"] = "degraded"

    # Add other service checks as needed

    status_code = (
        200 if health_status["status"] in ["healthy", "degraded"] else 503
    )
    return JSONResponse(content=health_status, status_code=status_code)


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "API is running", "docs": "/docs"}


@app.post("/index-data/")
async def index_data_endpoint(file: UploadFile = File(...)):
    global weaviate_client
    if not weaviate_client:
        raise HTTPException(
            status_code=503,
            detail="Weaviate client not available. Check server logs.",
        )

    try:
        contents = await file.read()
        # Check if filename exists and determine file type
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="File must have a filename.",
            )

        # Assuming CSV for simplicity, add support for Parquet if needed
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
        elif file.filename.endswith(".parquet"):
            df = pd.read_parquet(io.BytesIO(contents))
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Please upload CSV or Parquet.",
            )

        if "messages_json" not in df.columns:
            raise HTTPException(
                status_code=400,
                detail="DataFrame must contain 'messages_json' column.",
            )

        # Optional: Clear existing data before indexing new data
        # Be careful with this in a production environment
        # clear_all_data(weaviate_client, WEAVIATE_CLASS_NAME)
        # print(f"Cleared existing data from '{WEAVIATE_CLASS_NAME}'.")

        documents = prepare_documents_from_df(df)
        if not documents:
            return {
                "message": (
                    "No processable documents found in the uploaded file."
                )
            }

        index_documents(weaviate_client, documents)
        return {
            "message": f"Successfully processed and initiated indexing "
            f"for {len(documents)} documents."
        }
    except HTTPException as e:
        raise e  # Re-raise FastAPI's HTTP exceptions
    except Exception as e:
        print(f"Error during indexing: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error processing file: {str(e)}"
        )


class QueryRequest(BaseModel):
    query: str
    top_k: int = 3


class QueryResponse(BaseModel):
    answer: str
    retrieved_contexts: List[Dict[str, Any]]


@app.post("/query/", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest = Body(...)):
    global weaviate_client
    if not weaviate_client:
        raise HTTPException(
            status_code=503,
            detail="Weaviate client not available. Check server logs.",
        )

    try:
        retrieved_docs = search_weaviate(
            weaviate_client, request.query, top_k=request.top_k
        )

        if not retrieved_docs:
            # Fallback: try to answer without context
            # or state no context found
            answer = get_chat_completion(prompt=request.query, context=None)
            return QueryResponse(
                answer=f"No relevant context found. "
                f"General knowledge answer: {answer}",
                retrieved_contexts=[],
            )

        context_str = "\n\n---\n\n".join(
            [doc["content"] for doc in retrieved_docs]
        )

        # Prepare a simplified list of contexts for the response
        simplified_contexts = []
        for doc in retrieved_docs:
            simplified_contexts.append(
                {
                    "content_preview": doc["content"][:200] + "...",  # Preview
                    "original_df_index": doc.get("original_df_index", "N/A"),
                    "distance": doc.get("_additional", {}).get(
                        "distance", "N/A"
                    ),
                }
            )

        answer = get_chat_completion(prompt=request.query, context=context_str)

        return QueryResponse(
            answer=answer, retrieved_contexts=simplified_contexts
        )
    except Exception as e:
        print(f"Error during query: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error processing query: {str(e)}"
        )


@app.post("/clear-index/")
async def clear_index_endpoint():
    global weaviate_client
    if not weaviate_client:
        raise HTTPException(
            status_code=503,
            detail="Weaviate client not available. Check server logs.",
        )
    try:
        clear_all_data(weaviate_client, WEAVIATE_CLASS_NAME)
        return {
            "message": f"Successfully cleared all data from Weaviate "
            f"class '{WEAVIATE_CLASS_NAME}'."
        }
    except Exception as e:
        print(f"Error clearing index: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error clearing index: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    # Make sure .env is loaded if running directly for weaviate_utils etc.
    from dotenv import load_dotenv

    load_dotenv()
    uvicorn.run(app, host="0.0.0.0", port=8000)
