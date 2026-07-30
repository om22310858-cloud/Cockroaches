"""
FastAPI backend that talks to a locally running Ollama server
and streams responses back to the Streamlit frontend.

Run with:
    uvicorn backend:app --reload --port 8000

Requires Ollama running locally (default: http://localhost:11434)
and at least one model pulled, e.g.:
    ollama pull llama3.2
"""

import json
from typing import List, Dict

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

OLLAMA_BASE_URL = "http://localhost:11434"

app = FastAPI(title="Ollama Chat Backend")

# Allow the Streamlit app (usually on a different port) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Message(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class ChatRequest(BaseModel):
    model: str = "llama3.2"
    messages: List[Message]
    temperature: float = 0.7


@app.get("/models")
async def list_models():
    """Return the list of models currently pulled in Ollama."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return {"models": [m["name"] for m in data.get("models", [])]}
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Cannot reach Ollama. Is it running? Try: ollama serve",
        )


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Stream a chat completion from Ollama back to the client as
    newline-delimited plain text chunks (Server-Sent style streaming).
    """
    payload = {
        "model": req.model,
        "messages": [m.model_dump() for m in req.messages],
        "stream": True,
        "options": {"temperature": req.temperature},
    }

    async def event_generator():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST", f"{OLLAMA_BASE_URL}/api/chat", json=payload
                ) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        yield f"[ERROR] Ollama returned {response.status_code}: {body.decode()}"
                        return
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        chunk = json.loads(line)
                        if chunk.get("done"):
                            break
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
        except httpx.ConnectError:
            yield "[ERROR] Cannot reach Ollama. Is it running? Try: ollama serve"

    return StreamingResponse(event_generator(), media_type="text/plain")


@app.get("/health")
async def health():
    return {"status": "ok"}