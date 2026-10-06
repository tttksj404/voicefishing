"""FastAPI app assembly for the browser-local Qwen IDE."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from uvicorn import run as run_uvicorn

from voicefishing.ide_web_endpoints import (
    STATIC_DIRECTORY,
    LocalIDEEndpoints,
    WorkbenchGateway,
    WorkspaceGateway,
)
from voicefishing.ide_workspace import ProjectWorkspace
from voicefishing.workbench import LocalWorkbench, default_workbench_config


def create_app(
    workbench: WorkbenchGateway | None = None,
    workspace: WorkspaceGateway | None = None,
) -> FastAPI:
    """Create a loopback-only browser IDE with typed local APIs."""
    active_workbench = workbench or LocalWorkbench(default_workbench_config())
    active_workspace = workspace or ProjectWorkspace(
        Path(__file__).resolve().parents[2]
    )
    endpoints = LocalIDEEndpoints(active_workbench, active_workspace)
    app = FastAPI(title="Local Qwen IDE", version="0.2.0")
    app.mount("/assets", StaticFiles(directory=STATIC_DIRECTORY), name="assets")
    app.add_exception_handler(
        RequestValidationError,
        endpoints.request_validation_error,
    )
    app.add_api_route("/", endpoints.index, methods=["GET"], include_in_schema=False)
    app.add_api_route(
        "/components",
        endpoints.component_showcase,
        methods=["GET"],
        include_in_schema=False,
    )
    app.add_api_route("/api/status", endpoints.status, methods=["GET"])
    app.add_api_route("/api/generate", endpoints.generate, methods=["POST"])
    app.add_api_route(
        "/api/workspace/files",
        endpoints.list_workspace_files,
        methods=["GET"],
    )
    app.add_api_route(
        "/api/workspace/file",
        endpoints.read_workspace_file,
        methods=["GET"],
    )
    app.add_api_route(
        "/api/workspace/file",
        endpoints.write_workspace_file,
        methods=["PUT"],
    )
    return app


def run_workbench(port: int) -> None:
    """Start the IDE only on the local loopback interface."""
    run_uvicorn(create_app(), host="127.0.0.1", port=port)


app = create_app()
