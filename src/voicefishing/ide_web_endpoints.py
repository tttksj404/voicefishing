"""Bound local IDE HTTP endpoints, kept separate from FastAPI app assembly."""

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from fastapi import HTTPException, Request, Response
from fastapi.responses import FileResponse

from voicefishing.ide_contracts import (
    WorkspaceFileList,
    WorkspaceFileRead,
    WorkspaceFileWriteRequest,
    WorkspaceFileWriteResult,
)
from voicefishing.ide_workspace import WorkspaceError, WorkspaceErrorCode
from voicefishing.workbench_contracts import (
    GenerationResult,
    WorkbenchRunRequest,
    WorkbenchStatus,
)

STATIC_DIRECTORY: Final[Path] = Path(__file__).with_name("static")


class WorkbenchGateway(Protocol):
    """The narrow browser-facing capability exposed by a local model service."""

    def status(self) -> WorkbenchStatus:
        """Return non-sensitive runtime readiness."""
        ...

    def run(self, request: WorkbenchRunRequest) -> GenerationResult:
        """Run one safe, unpersisted local completion."""
        ...


class WorkspaceGateway(Protocol):
    """The narrow project-file capability exposed to the browser-local IDE."""

    def list_files(self) -> WorkspaceFileList:
        """Return the safe, existing project text files available to edit."""
        ...

    def read_file(self, raw_path: str) -> WorkspaceFileRead:
        """Open one project-relative UTF-8 text file."""
        ...

    def write_file(
        self,
        request: WorkspaceFileWriteRequest,
    ) -> WorkspaceFileWriteResult:
        """Persist one explicit user save to the currently selected file."""
        ...


def _workspace_failure(error: WorkspaceError) -> HTTPException:
    """Map all local file failures to a generic, non-reflective response."""
    match error.code:
        case WorkspaceErrorCode.INVALID_PATH:
            return HTTPException(
                status_code=400,
                detail="workspace_file_unavailable",
            )
        case (
            WorkspaceErrorCode.NOT_FOUND
            | WorkspaceErrorCode.UNSUPPORTED_FILE
            | WorkspaceErrorCode.FILE_TOO_LARGE
            | WorkspaceErrorCode.READ_FAILED
            | WorkspaceErrorCode.WRITE_FAILED
        ):
            return HTTPException(
                status_code=404,
                detail="workspace_file_unavailable",
            )


@dataclass(frozen=True, slots=True)
class LocalIDEEndpoints:
    """Concrete HTTP handlers bound to one workbench and project workspace."""

    workbench: WorkbenchGateway
    workspace: WorkspaceGateway

    def request_validation_error(
        self,
        _request: Request,
        _error: Exception,
    ) -> Response:
        """Reject malformed input without reflecting its content to the browser."""
        return Response(
            content='{"detail":"invalid_workbench_request"}',
            media_type="application/json",
            status_code=422,
        )

    def index(self) -> FileResponse:
        """Serve the browser-local IDE surface."""
        return FileResponse(STATIC_DIRECTORY / "index.html")

    def component_showcase(self) -> FileResponse:
        """Serve the primitive state showcase used for visual QA."""
        return FileResponse(STATIC_DIRECTORY / "components.html")

    def status(self) -> WorkbenchStatus:
        """Expose safe readiness data without a filesystem directory listing."""
        return self.workbench.status()

    def generate(self, request: WorkbenchRunRequest) -> GenerationResult:
        """Run one local, safety-bounded completion."""
        return self.workbench.run(request)

    def list_workspace_files(self) -> WorkspaceFileList:
        """Expose the filtered project file list without directory traversal APIs."""
        try:
            return self.workspace.list_files()
        except WorkspaceError as error:
            raise _workspace_failure(error) from None

    def read_workspace_file(self, path: str) -> WorkspaceFileRead:
        """Open one selected project file through the bounded workspace gateway."""
        try:
            return self.workspace.read_file(path)
        except WorkspaceError as error:
            raise _workspace_failure(error) from None

    def write_workspace_file(
        self,
        request: WorkspaceFileWriteRequest,
    ) -> WorkspaceFileWriteResult:
        """Persist an explicit save through the bounded workspace gateway."""
        try:
            return self.workspace.write_file(request)
        except WorkspaceError as error:
            raise _workspace_failure(error) from None
