import os
from typing import List, Optional

from dotenv import load_dotenv
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables.")

client = OpenAI(api_key=OPENAI_API_KEY)

EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL")
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL")


def get_embedding(
    text: str, model: str | None = EMBEDDING_MODEL
) -> List[float]:
    """Generates an embedding for the given text."""
    text = text.replace("\n", " ")  # OpenAI recommendation
    print(
        f"Attempting to get embedding with model: "
        f"'{model}' for text: '{text[:50]}...'"
    )  # DEBUG LINE

    # Provide default model if None
    embedding_model = model or "text-embedding-3-small"

    response = client.embeddings.create(input=[text], model=embedding_model)
    return response.data[0].embedding


def get_chat_completion(
    prompt: str, context: Optional[str] = None, model: str | None = CHAT_MODEL
) -> str:
    """Gets a chat completion from OpenAI."""
    messages: List[ChatCompletionMessageParam] = []
    if context:
        messages.append(
            {
                "role": "system",
                "content": f"You are a helpful assistant. Wrap up based"
                f" the following context and answer the user's question "
                f"in a detailed, nuanced and helpful way:\n\n{context}\n"
                f"\nIf the context doesn't provide an answer, say you "
                f"don't know. Reply in Russian.",
            }
        )
    else:
        messages.append(
            {
                "role": "system",
                "content": "You are a helpful assistant. " "Reply in Russian.",
            }
        )

    messages.append({"role": "user", "content": prompt})

    try:
        # Provide default model if None
        chat_model = model or "gpt-4o-mini"

        response = client.chat.completions.create(
            model=chat_model,
            messages=messages,
            temperature=0.0,  # Adjust for creativity vs. factuality
        )
        content = response.choices[0].message.content
        return content.strip() if content else "No response received."
    except Exception as e:
        print(f"Error in OpenAI chat completion: {e}")
        return "Sorry, I encountered an error while generating a response."


if __name__ == "__main__":
    sample_text = "This is a test sentence for embeddings."
    embedding = get_embedding(sample_text)
    print(
        f"Embedding for '{sample_text}': {embedding[:5]}... "
        f"(length: {len(embedding)})"
    )

    answer = get_chat_completion(
        "What is the capital of France?",
        context="France is a country in Europe.",
    )
    print(f"Chat completion answer: {answer}")

    answer_no_context = get_chat_completion("What is the capital of France?")
    print(f"Chat completion answer (no context): {answer_no_context}")
