"""Project-scoped UTF-8 text file access for the browser-local IDE."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Final, final

from voicefishing.ide_contracts import (
    WorkspaceFileList,
    WorkspaceFileRead,
    WorkspaceFileSummary,
    WorkspaceFileWriteRequest,
    WorkspaceFileWriteResult,
)

MAX_WORKSPACE_FILE_BYTES: Final[int] = 256 * 1024
_ALLOWED_SUFFIXES: Final[frozenset[str]] = frozenset(
    {
        ".css",
        ".html",
        ".js",
        ".json",
        ".md",
        ".ps1",
        ".py",
        ".sh",
        ".toml",
        ".txt",
        ".yaml",
        ".yml",
    }
)
_EXCLUDED_DIRECTORIES: Final[frozenset[str]] = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tools",
        ".venv",
        "__pycache__",
        "node_modules",
        "output",
    }
)
_LANGUAGE_BY_SUFFIX: Final[dict[str, str]] = {
    ".css": "css",
    ".html": "html",
    ".js": "javascript",
    ".json": "json",
    ".md": "markdown",
    ".ps1": "powershell",
    ".py": "python",
    ".sh": "shell",
    ".toml": "toml",
    ".txt": "text",
    ".yaml": "yaml",
    ".yml": "yaml",
}


class WorkspaceErrorCode(StrEnum):
    """Stable failure classes that never include a user-supplied path."""

    INVALID_PATH = "invalid_path"
    NOT_FOUND = "not_found"
    UNSUPPORTED_FILE = "unsupported_file"
    FILE_TOO_LARGE = "file_too_large"
    READ_FAILED = "read_failed"
    WRITE_FAILED = "write_failed"


@dataclass(frozen=True, slots=True)
class WorkspaceError(Exception):
    """A safe workspace failure that can be mapped to a generic HTTP response."""

    code: WorkspaceErrorCode


def language_for_path(path: Path) -> str:
    """Return the editor mode for one already-approved workspace file."""
    return _LANGUAGE_BY_SUFFIX[path.suffix.lower()]


@final
class ProjectWorkspace:
    """Expose only existing, bounded, project-relative UTF-8 text files."""

    def __init__(self, root: Path) -> None:
        """Bind the workspace to one resolved project root."""
        self._root = root.resolve()

    def list_files(self) -> WorkspaceFileList:
        """List safe project text files without exposing excluded directories."""
        files: list[WorkspaceFileSummary] = []
        for candidate in self._root.rglob("*"):
            try:
                if not candidate.is_file() or candidate.is_symlink():
                    continue
                relative = candidate.resolve().relative_to(self._root)
                if not self._is_allowed_relative_path(relative):
                    continue
                byte_count = candidate.stat().st_size
            except (OSError, ValueError):
                continue
            if byte_count > MAX_WORKSPACE_FILE_BYTES:
                continue
            files.append(
                WorkspaceFileSummary(
                    path=relative.as_posix(),
                    language=language_for_path(relative),
                    bytes=byte_count,
                )
            )
        files.sort(key=lambda item: item.path.casefold())
        return WorkspaceFileList(files=tuple(files))

    def read_file(self, raw_path: str) -> WorkspaceFileRead:
        """Read one existing safe file after enforcing project containment."""
        target = self._resolve_openable_file(raw_path)
        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise WorkspaceError(WorkspaceErrorCode.UNSUPPORTED_FILE) from None
        except OSError:
            raise WorkspaceError(WorkspaceErrorCode.READ_FAILED) from None
        byte_count = len(content.encode("utf-8"))
        if byte_count > MAX_WORKSPACE_FILE_BYTES:
            raise WorkspaceError(WorkspaceErrorCode.FILE_TOO_LARGE)
        return WorkspaceFileRead(
            path=target.relative_to(self._root).as_posix(),
            language=language_for_path(target),
            bytes=byte_count,
            content=content,
        )

    def write_file(
        self, request: WorkspaceFileWriteRequest
    ) -> WorkspaceFileWriteResult:
        """Save user-reviewed text to the selected existing safe file only."""
        target = self._resolve_openable_file(request.path)
        byte_count = len(request.content.encode("utf-8"))
        if byte_count > MAX_WORKSPACE_FILE_BYTES:
            raise WorkspaceError(WorkspaceErrorCode.FILE_TOO_LARGE)
        try:
            with target.open("w", encoding="utf-8", newline="") as destination:
                _ = destination.write(request.content)
        except OSError:
            raise WorkspaceError(WorkspaceErrorCode.WRITE_FAILED) from None
        return WorkspaceFileWriteResult(
            path=target.relative_to(self._root).as_posix(),
            language=language_for_path(target),
            bytes=byte_count,
        )

    def _resolve_openable_file(self, raw_path: str) -> Path:
        """Parse an external path once and ensure it names an allowed file."""
        if "\\" in raw_path or ":" in raw_path:
            raise WorkspaceError(WorkspaceErrorCode.INVALID_PATH)
        path = PurePosixPath(raw_path)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise WorkspaceError(WorkspaceErrorCode.INVALID_PATH)
        try:
            target = self._root.joinpath(*path.parts).resolve()
            relative = target.relative_to(self._root)
        except ValueError:
            raise WorkspaceError(WorkspaceErrorCode.INVALID_PATH) from None
        try:
            exists = target.is_file() and not target.is_symlink()
        except OSError:
            raise WorkspaceError(WorkspaceErrorCode.NOT_FOUND) from None
        if not exists:
            raise WorkspaceError(WorkspaceErrorCode.NOT_FOUND)
        if not self._is_allowed_relative_path(relative):
            raise WorkspaceError(WorkspaceErrorCode.UNSUPPORTED_FILE)
        return target

    def _is_allowed_relative_path(self, relative: Path) -> bool:
        """Keep internal tooling, hidden files, and non-text formats out of the IDE."""
        directories = relative.parts[:-1]
        if any(
            directory in _EXCLUDED_DIRECTORIES or directory.startswith(".")
            for directory in directories
        ):
            return False
        return (
            not relative.name.startswith(".")
            and relative.suffix.lower() in _ALLOWED_SUFFIXES
        )
