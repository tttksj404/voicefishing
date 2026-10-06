"""Typed browser contracts for the bounded local IDE workspace."""

from typing import ClassVar, Final

from pydantic import BaseModel, ConfigDict, Field

MAX_WORKSPACE_CONTENT_CHARS: Final[int] = 80_000
MAX_WORKSPACE_PATH_LENGTH: Final[int] = 240


class WorkspaceFileSummary(BaseModel):
    """One safe text file available in the local project workspace."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    path: str
    language: str
    bytes: int


class WorkspaceFileList(BaseModel):
    """A deterministic, project-relative list of editable files."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    files: tuple[WorkspaceFileSummary, ...]


class WorkspaceFileRead(BaseModel):
    """The visible contents of one existing project text file."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    path: str
    language: str
    bytes: int
    content: str


class WorkspaceFileWriteRequest(BaseModel):
    """A user-initiated save for the currently selected existing text file."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1, max_length=MAX_WORKSPACE_PATH_LENGTH)
    content: str = Field(max_length=MAX_WORKSPACE_CONTENT_CHARS)


class WorkspaceFileWriteResult(BaseModel):
    """Non-sensitive acknowledgement of an explicit local file save."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    path: str
    language: str
    bytes: int
