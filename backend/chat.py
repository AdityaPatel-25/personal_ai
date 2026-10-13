import json
import logging
import os
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional

from dotenv import find_dotenv, load_dotenv
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from groq import (
    APIConnectionError,
    APIStatusError,
    AsyncGroq,
    AuthenticationError,
    GroqError,
    RateLimitError,
)
from pydantic import BaseModel, Field, field_validator

# Enable flexible imports whether running from root or from within backend/
try:
    from backend import db, rag
except ImportError:
    import db, rag

from slowapi import Limiter
from slowapi.util import get_remote_address

# Load environment variables (.env in current directory or parent directories)
load_dotenv(find_dotenv(usecwd=True))

logger = logging.getLogger(__name__)

# Per-IP rate limiting configuration (configurable via environment variables)
# Defaults: 10 requests per minute and 100 requests per day per IP
DEFAULT_CHAT_RATE_LIMIT = "10/minute,100/day"
CHAT_RATE_LIMIT = os.getenv(
    "CHAT_RATE_LIMIT",
    os.getenv(
        "RATE_LIMIT_CHAT",
        f"{os.getenv('CHAT_RATE_LIMIT_PER_MINUTE', '10/minute')},{os.getenv('CHAT_RATE_LIMIT_PER_DAY', '100/day')}",
    ),
)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

SYSTEM_INSTRUCTION = """You are an expert AI coach for competitive programming and Data Structures & Algorithms (DSA).
Your mission is to guide students and engineers through problem-solving with algorithmic rigor, intuition, and encouragement.
When assisting:
1. Provide guiding questions or intuitive hints before giving away the full solution, promoting deep problem-solving skills.
2. When explaining solutions, detail intuition, step-by-step logic, edge cases, and time/space complexity (Big-O analysis).
3. If code is requested, provide clean, idiomatic code with clear explanatory comments.
4. Remember the student's prior questions and code within the conversation to provide coherent, contextual guidance.
5. If relevant DSA reference notes from the knowledge base are included in the prompt, prioritize and cite those specific patterns, rules, code templates, and complexity constraints.
6. Structure responses with clean Markdown: use standard Markdown tables (| Col 1 | Col 2 |) for decision matrices and comparisons, clear section headers (## / ###), bullet lists, and fenced code blocks with language identifiers (e.g. ```python). Format inline complexity or variables with single backticks (`O(V+E)`).
"""


# Number of recent messages to pass to LLM as context (10-15 messages)
CONTEXT_MESSAGE_LIMIT = 14


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        description="The user's prompt or DSA question",
        json_schema_extra={
            "example": "How do I choose between BFS and DFS for graph problems?"
        },
    )
    conversation_id: Optional[str] = Field(
        None,
        description="ID of the conversation to append to. Auto-generated if omitted.",
    )

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Message cannot be empty or contain only whitespace.")
        return v.strip()


class CreateConversationRequest(BaseModel):
    title: Optional[str] = Field(
        "New Chat",
        description="Title of the new conversation",
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> str:
        if not v or not v.strip():
            return "New Chat"
        return v.strip()


DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


def get_groq_client() -> AsyncGroq:
    """Instantiates and returns the Groq asynchronous client using the configured API key."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key.strip() in ("", "your_groq_api_key_here"):
        logger.error("Groq client requested but GROQ_API_KEY is not configured in environment.")
        raise HTTPException(
            status_code=500,
            detail=(
                "GROQ_API_KEY environment variable is not configured. "
                "Please configure GROQ_API_KEY in your .env file."
            ),
        )
    return AsyncGroq(api_key=api_key.strip())


def build_groq_messages(
    raw_messages: List[Dict[str, Any]],
    system_instruction: str = SYSTEM_INSTRUCTION,
) -> List[Dict[str, str]]:
    """Converts database messages into OpenAI/Groq compatible message dictionaries.

    Includes system prompt first, followed by sequential user and assistant turns.
    """
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_instruction}
    ]

    for msg in raw_messages:
        role = msg.get("role", "user")
        if role not in ("user", "assistant", "system"):
            role = "user"
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        messages.append({"role": role, "content": content})

    return messages


def derive_conversation_title(prompt: str) -> str:
    """Generates a concise, readable conversation title from the first prompt."""
    cleaned = " ".join(prompt.strip().split())
    if len(cleaned) <= 36:
        return cleaned
    truncated = cleaned[:36]
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return f"{truncated}..."


async def generate_groq_stream(
    messages: List[Dict[str, str]],
    conversation_id: str,
) -> AsyncIterator[str]:
    """Asynchronously calls Groq's chat completion with streaming, yields tokens, and saves assistant reply to DB."""
    full_response_chunks: List[str] = []
    stream_successful = False
    last_error: Optional[Exception] = None

    try:
        try:
            client = get_groq_client()
        except HTTPException as key_err:
            last_error = key_err
            error_msg = f"⚠️ **Configuration Error:** {key_err.detail}"
            full_response_chunks.append(error_msg)
            yield error_msg
            return

        configured_model = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL).strip()
        models_to_try = [configured_model]
        for fallback in ["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]:
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        for model_name in models_to_try:
            current_model_chunks: List[str] = []
            try:
                logger.info("Initiating Groq streaming completion with model '%s' (conv=%s)", model_name, conversation_id)
                response = await client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    stream=True,
                )
                async for chunk in response:
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        token = chunk.choices[0].delta.content
                        stream_successful = True
                        current_model_chunks.append(token)
                        full_response_chunks.append(token)
                        yield token

                if stream_successful:
                    break

            except AuthenticationError as auth_err:
                last_error = auth_err
                logger.error("Groq Authentication Error (401): %s", auth_err, exc_info=True)
                error_msg = (
                    "⚠️ **Authentication Error (401):** GROQ_API_KEY is invalid or expired. "
                    "Please check your `.env` configuration file."
                )
                full_response_chunks.append(error_msg)
                yield error_msg
                break

            except RateLimitError as rate_err:
                last_error = rate_err
                logger.error("Groq Rate Limit Error (429): %s", rate_err, exc_info=True)
                error_msg = (
                    "⚠️ **Rate Limit Exceeded (429):** Groq API rate limit reached. "
                    "Please wait a few seconds and try again."
                )
                full_response_chunks.append(error_msg)
                yield error_msg
                break

            except APIConnectionError as conn_err:
                last_error = conn_err
                logger.error("Groq API Connection Error (network unreachable): %s", conn_err, exc_info=True)
                error_msg = (
                    "⚠️ **Network Error:** Unable to reach Groq API servers. "
                    "Please check your internet connection or firewall."
                )
                full_response_chunks.append(error_msg)
                yield error_msg
                break

            except APIStatusError as status_err:
                last_error = status_err
                logger.warning("Groq model %s returned status %s: %s", model_name, status_err.status_code, status_err)
                err_text = str(status_err)
                if not current_model_chunks and ("model_not_found" in err_text.lower() or status_err.status_code == 404):
                    continue
                else:
                    break

            except Exception as exc:
                last_error = exc
                err_text = str(exc)
                logger.error("Groq model %s encountered exception: %s", model_name, exc, exc_info=True)
                if not current_model_chunks and ("model_not_found" in err_text.lower() or "404" in err_text):
                    continue
                else:
                    break

        if not stream_successful and last_error and not full_response_chunks:
            err_str = str(last_error)
            logger.error("All Groq models failed for conversation %s: %s", conversation_id, last_error)
            if "429" in err_str or "rate limit" in err_str.lower():
                error_msg = "⚠️ **Rate Limit Reached (429):** Groq API rate limit reached. Please wait a moment and try again."
            elif "401" in err_str or "invalid api key" in err_str.lower():
                error_msg = "⚠️ **Invalid API Key (401):** GROQ_API_KEY is invalid or expired. Please check your .env file."
            elif "model_not_found" in err_str.lower():
                error_msg = f"⚠️ **Model Not Found:** {err_str}"
            else:
                error_msg = f"⚠️ **Groq Service Notice:** {err_str}"

            full_response_chunks.append(error_msg)
            yield error_msg

    finally:
        # Persist full or partial generated assistant response to SQLite database
        accumulated_text = "".join(full_response_chunks).strip()
        if accumulated_text:
            try:
                db.add_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=accumulated_text,
                )
                logger.info(
                    "Persisted assistant response (%d chars) to conversation %s",
                    len(accumulated_text),
                    conversation_id,
                )
            except Exception as save_err:
                logger.error("Failed to persist assistant message to DB: %s", save_err)


async def sse_stream_generator(
    messages: List[Dict[str, str]],
    conversation_id: str,
) -> AsyncIterator[str]:
    """Wraps token chunks into standard Server-Sent Events (SSE) data frames."""
    async for token in generate_groq_stream(messages, conversation_id):
        payload = json.dumps({"text": token})
        yield f"data: {payload}\n\n"
    yield "data: [DONE]\n\n"


# ============================================================================
# Conversation Endpoints
# ============================================================================


@router.post("/conversations", status_code=201)
async def create_conversation_endpoint(body: Optional[CreateConversationRequest] = None):
    """Creates a new conversation record and returns its metadata."""
    title = (body.title if body and body.title else "New Chat").strip()
    try:
        conversation = db.create_conversation(title=title)
        return conversation
    except Exception as e:
        logger.error("Failed to create conversation: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Database error: Failed to create conversation.",
        )


@router.get("/conversations")
async def list_conversations_endpoint():
    """Lists all past conversations for the sidebar/history view."""
    try:
        return db.list_conversations()
    except Exception as e:
        logger.error("Failed to list conversations: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Database error: Failed to retrieve conversation history.",
        )


@router.get("/conversations/{conversation_id}")
async def get_conversation_endpoint(conversation_id: str):
    """Retrieves full conversation details including all saved messages in chronological order."""
    if not conversation_id or not conversation_id.strip():
        raise HTTPException(status_code=400, detail="Invalid conversation_id parameter.")

    try:
        conv = db.get_conversation_with_messages(conversation_id.strip())
        if not conv:
            raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found.")
        return conv
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get conversation %s: %s", conversation_id, e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Database error: Failed to retrieve conversation '{conversation_id}'.",
        )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation_endpoint(conversation_id: str):
    """Deletes a conversation and its messages."""
    if not conversation_id or not conversation_id.strip():
        raise HTTPException(status_code=400, detail="Invalid conversation_id parameter.")

    try:
        success = db.delete_conversation(conversation_id.strip())
        if not success:
            raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found.")
        return {"status": "deleted", "id": conversation_id.strip()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete conversation %s: %s", conversation_id, e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Database error: Failed to delete conversation '{conversation_id}'.",
        )


# ============================================================================
# Streaming Chat Endpoint
# ============================================================================


@router.post("/chat")
@limiter.limit(CHAT_RATE_LIMIT)
async def chat(request_body: ChatRequest, request: Request):
    """Streaming chat endpoint for DSA coaching with persistent memory & RAG retrieval.

    Accepts:
        {
            "message": "Explain 0/1 knapsack space optimization",
            "conversation_id": "optional-uuid"
        }
    """
    # 0. Request Validation: Reject empty or whitespace-only messages
    clean_message = (request_body.message or "").strip()
    if not clean_message:
        logger.warning("Rejected chat request: empty message")
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty or contain only whitespace.",
        )

    # Pre-flight check: verify API key before initiating response stream or saving to DB
    try:
        get_groq_client()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Pre-flight Groq client check failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"AI Client configuration error: {str(e)}",
        )

    # 1. Resolve or create conversation in SQLite
    conv_id = (request_body.conversation_id or "").strip()
    try:
        if conv_id:
            existing_conv = db.get_conversation(conv_id)
            if not existing_conv:
                conv_id = db.create_conversation(title="New Chat", conversation_id=conv_id)["id"]
        else:
            conv_id = db.create_conversation(title="New Chat")["id"]
    except Exception as db_err:
        logger.error("Failed to resolve or create conversation in SQLite: %s", db_err, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Database error while resolving conversation: {str(db_err)}",
        )

    # 2. Persist the user message to SQLite
    try:
        db.add_message(
            conversation_id=conv_id,
            role="user",
            content=clean_message,
        )
    except Exception as db_err:
        logger.error("Failed to persist user message in SQLite: %s", db_err, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Database error while saving user message: {str(db_err)}",
        )

    # 3. Update title if this conversation still has the default title
    try:
        current_conv = db.get_conversation(conv_id)
        if current_conv and current_conv.get("title") in ("New Chat", "New Conversation", ""):
            new_title = derive_conversation_title(clean_message)
            db.update_conversation_title(conv_id, new_title)
    except Exception as title_err:
        logger.warning("Failed to update conversation title (non-critical): %s", title_err)

    # 4. RAG Step: Retrieve relevant notes from ChromaDB vector store
    retrieved_chunks: List[Dict[str, Any]] = []
    rag_context = ""
    try:
        logger.info("Chat: RAG retrieval initiated for query: '%s'...", clean_message[:50])
        retrieved_chunks = rag.retrieve(clean_message, top_k=4)
        rag_context = rag.format_retrieved_context(retrieved_chunks)
        if retrieved_chunks:
            sources = sorted({c.get("source", "DSA Notes") for c in retrieved_chunks})
            logger.info(
                "Chat: RAG retrieval found %d chunk(s) from sources: %s for query: '%s'",
                len(retrieved_chunks),
                sources,
                clean_message[:45],
            )
        else:
            logger.info("Chat: RAG retrieval found 0 chunks for query: '%s'", clean_message[:45])
    except Exception as rag_err:
        logger.error("Chat: RAG retrieval failed (continuing without RAG context): %s", rag_err, exc_info=True)

    # 5. Fetch recent history (last 14 messages) for conversation memory
    try:
        raw_history = db.get_messages(conv_id, limit=CONTEXT_MESSAGE_LIMIT)
    except Exception as hist_err:
        logger.warning("Failed to fetch message history for conversation %s: %s", conv_id, hist_err)
        raw_history = []

    # 6. Build Groq messages: augment the latest user turn with the retrieved RAG notes
    if raw_history and raw_history[-1]["role"] == "user" and rag_context:
        augmented_prompt = (
            f"{rag_context}\n\n"
            f"=== Student Question ===\n"
            f"{clean_message}"
        )
        augmented_history = [dict(m) for m in raw_history]
        augmented_history[-1]["content"] = augmented_prompt
        groq_messages = build_groq_messages(augmented_history)
    else:
        groq_messages = build_groq_messages(raw_history)

    # Fallback to single message if formatted history somehow empty
    if len(groq_messages) <= 1:
        augmented_prompt = (
            f"{rag_context}\n\n=== Student Question ===\n{clean_message}"
            if rag_context
            else clean_message
        )
        groq_messages = [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": augmented_prompt},
        ]

    accept_header = request.headers.get("accept", "")
    response_headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "X-Conversation-Id": conv_id,
        "X-Rag-Chunks": str(len(retrieved_chunks)),
    }
    if retrieved_chunks:
        sources_str = ", ".join(sorted({c.get("source", "") for c in retrieved_chunks if c.get("source")}))
        response_headers["X-Rag-Sources"] = sources_str

    # 7. Check if client requested Server-Sent Events (SSE)
    if "text/event-stream" in accept_header:
        return StreamingResponse(
            sse_stream_generator(groq_messages, conv_id),
            media_type="text/event-stream",
            headers=response_headers,
        )

    # 8. Default: Chunked plain text stream
    return StreamingResponse(
        generate_groq_stream(groq_messages, conv_id),
        media_type="text/plain; charset=utf-8",
        headers=response_headers,
    )


# ============================================================================
# RAG Management Endpoints
# ============================================================================


@router.get("/rag/status")
async def rag_status():
    """Returns status of ChromaDB vector store and indexed DSA notes."""
    try:
        col = rag.get_or_create_collection()
        chunk_count = col.count()
        return {
            "status": "online",
            "collection_name": rag.CHROMA_COLLECTION_NAME,
            "total_chunks": chunk_count,
            "chroma_db_path": rag.CHROMA_DB_PATH,
            "embedding_model": rag.DEFAULT_EMBEDDING_MODEL,
        }
    except Exception as e:
        logger.error("RAG status check failed: %s", e, exc_info=True)
        return {
            "status": "error",
            "detail": str(e),
        }


@router.get("/rag/query")
async def rag_query(q: str, top_k: int = 4):
    """Directly query the RAG vector store for inspection and verification."""
    clean_q = (q or "").strip()
    if not clean_q:
        raise HTTPException(status_code=400, detail="Query parameter 'q' cannot be empty or whitespace.")

    try:
        chunks = rag.retrieve(query=clean_q, top_k=top_k)
        return {
            "query": clean_q,
            "top_k": top_k,
            "results_count": len(chunks),
            "results": chunks,
        }
    except Exception as e:
        logger.error("RAG query failed for '%s': %s", clean_q, e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"RAG query failed: {str(e)}",
        )


@router.post("/rag/index")
async def rag_reindex(chunk_size: Optional[int] = None, chunk_overlap: Optional[int] = None):
    """Triggers indexing of documents in /data folder into ChromaDB."""
    try:
        stats = rag.index_data(
            chunk_size=chunk_size or rag.DEFAULT_CHUNK_SIZE,
            chunk_overlap=chunk_overlap or rag.DEFAULT_CHUNK_OVERLAP,
            reset_collection=True,
        )
        return stats
    except Exception as e:
        logger.error("RAG re-indexing failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Indexing failed: {e}")


DEFAULT_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")


@router.post("/transcribe")
@router.post("/api/transcribe")
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio recording file (webm, wav, mp3, mp4, ogg)"),
):
    """Transcribes user recorded audio into text using Groq's high-speed Whisper model."""
    if not file:
        raise HTTPException(status_code=400, detail="No audio file provided.")

    logger.info(
        "Received audio transcription request: filename=%s, content_type=%s",
        file.filename,
        file.content_type,
    )

    try:
        audio_bytes = await file.read()
    except Exception as e:
        logger.error("Failed to read uploaded audio file: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to read audio file: {e}")

    if len(audio_bytes) < 100:
        raise HTTPException(
            status_code=400,
            detail="The audio recording is too short or empty. Please speak clearly into your microphone.",
        )

    try:
        client = get_groq_client()
        filename = file.filename or "recording.webm"
        content_type = file.content_type or "audio/webm"

        transcription = await client.audio.transcriptions.create(
            file=(filename, audio_bytes, content_type),
            model=DEFAULT_WHISPER_MODEL,
            response_format="json",
            prompt="Data Structures and Algorithms, LeetCode, competitive programming, BFS, DFS, Dijkstra, DP, Big-O, binary search, tree traversal, recursion, time complexity",
        )

        text = (transcription.text or "").strip()
        logger.info(
            "Successfully transcribed %d bytes of audio to: '%s'",
            len(audio_bytes),
            text[:100],
        )
        return {
            "text": text,
            "filename": filename,
            "bytes_received": len(audio_bytes),
        }
    except AuthenticationError as e:
        logger.error("Groq Whisper authentication error: %s", e)
        raise HTTPException(
            status_code=401,
            detail="Groq authentication failed. Please check your GROQ_API_KEY in .env.",
        )
    except RateLimitError as e:
        logger.error("Groq Whisper rate limit exceeded: %s", e)
        raise HTTPException(
            status_code=429,
            detail="Groq Whisper rate limit reached. Please wait a moment and try again.",
        )
    except APIConnectionError as e:
        logger.error("Groq Whisper connection error: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Failed to connect to Groq AI audio service. Please check your network connection.",
        )
    except GroqError as e:
        logger.error("Groq Whisper API error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=502,
            detail=f"Groq Whisper transcription failed: {e.message if hasattr(e, 'message') else str(e)}",
        )
    except Exception as e:
        logger.error("Unexpected error during audio transcription: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Audio transcription error: {str(e)}",
        )


