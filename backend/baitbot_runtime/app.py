from __future__ import annotations

import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

try:
    from .event_log import bind_event_context, get_log_path, log_event
    from .runtime import BaitbotRuntime
except ImportError:  # Vercel imports the configured entrypoint as a top-level module.
    from event_log import bind_event_context, get_log_path, log_event
    from runtime import BaitbotRuntime


class ChatRequest(BaseModel):
    message: str
    model: str | None = None
    reasoning: str | None = None
    session_snapshot: dict[str, Any]


def _safe_log_path() -> str | None:
    try:
        return str(get_log_path())
    except Exception:
        return None


@asynccontextmanager
async def lifespan(_: FastAPI):
    log_event(
        "server.started",
        status="started",
        outcome="success",
        process_id=os.getpid(),
        log_path=_safe_log_path(),
    )
    try:
        yield
    finally:
        log_event(
            "server.stopped",
            status="stopped",
            outcome="success",
            process_id=os.getpid(),
            log_path=_safe_log_path(),
        )


app = FastAPI(title="Aegis Baitbot Runtime", lifespan=lifespan)
runtime = BaitbotRuntime()
INDEX_PATH = Path(__file__).parent / "static" / "index.html"


def _chat_status_code(result: dict) -> int:
    errors = result.get("errors") or []
    if not errors:
        return 200
    failed_goals = {
        error.split(":", 1)[0].strip().lower()
        for error in errors
        if isinstance(error, str) and ":" in error
    }
    failures = failed_goals & {"responder", "extractor"}
    return 207 if len(failures) == 1 else 502


@app.middleware("http")
async def log_request(request: Request, call_next):
    request_id = f"request_{uuid.uuid4().hex[:12]}"
    started = time.perf_counter()
    with bind_event_context(request_id=request_id):
        log_event(
            "api.request.started",
            status="started",
            method=request.method,
            path=request.url.path,
        )
        try:
            response = await call_next(request)
        except Exception:
            log_event(
                "api.request.failed",
                level="ERROR",
                status="failed",
                status_code=500,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                method=request.method,
                path=request.url.path,
                cause="unhandled_exception",
            )
            raise

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        if response.status_code == 207:
            log_event(
                "api.request.completed",
                level="WARNING",
                status="partial",
                status_code=response.status_code,
                duration_ms=duration_ms,
                method=request.method,
                path=request.url.path,
                details={"outcome": "partial"},
            )
        elif response.status_code >= 400:
            log_event(
                "api.request.failed",
                level="ERROR" if response.status_code >= 500 else "WARNING",
                status="failed",
                status_code=response.status_code,
                duration_ms=duration_ms,
                method=request.method,
                path=request.url.path,
                cause=f"http_{response.status_code}",
            )
        else:
            log_event(
                "api.request.completed",
                status="completed",
                status_code=response.status_code,
                duration_ms=duration_ms,
                method=request.method,
                path=request.url.path,
            )
        return response


@app.get("/", response_class=FileResponse)
async def index() -> FileResponse:
    if not INDEX_PATH.is_file():
        raise HTTPException(status_code=404, detail="static index is not available")
    return FileResponse(INDEX_PATH, media_type="text/html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


@app.get("/api/config")
async def config() -> dict:
    return runtime.config()


@app.post("/api/chat")
async def chat(request: ChatRequest) -> dict:
    try:
        result = await runtime.process(
            request.message,
            model=request.model,
            reasoning=request.reasoning,
            session_snapshot=request.session_snapshot,
        )
        return JSONResponse(content=result, status_code=_chat_status_code(result))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/reset")
async def reset() -> JSONResponse:
    return JSONResponse(await runtime.reset())
