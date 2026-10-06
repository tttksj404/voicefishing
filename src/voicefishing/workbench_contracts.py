"""Typed boundary contracts for the browser-local Qwen workbench."""

from typing import ClassVar, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_WORKBENCH_PROMPT_LENGTH: Final[int] = 2_000
DEFAULT_OUTPUT_TOKENS: Final[int] = 192
MAX_OUTPUT_TOKENS: Final[int] = 256


class WorkbenchRunRequest(BaseModel):
    """One unpersisted prompt submitted from the local browser surface."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    prompt: str = Field(min_length=1, max_length=MAX_WORKBENCH_PROMPT_LENGTH)
    output_tokens: int = Field(
        default=DEFAULT_OUTPUT_TOKENS,
        ge=1,
        le=MAX_OUTPUT_TOKENS,
    )


class WorkbenchStatus(BaseModel):
    """Non-sensitive readiness data for the bundled local runtime."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    runner_available: bool
    model_available: bool
    runner_name: str
    runner_path: str
    model_name: str
    model_path: str
    model_bytes: int | None
    threads: int


class GenerationReceipt(BaseModel):
    """Metadata retained for the current browser response only."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    elapsed_ms: float
    output_digest: str
    output_tokens: int


class GenerationSuccess(BaseModel):
    """A completed local model response."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    state: Literal["complete"] = "complete"
    response: str
    receipt: GenerationReceipt


class GenerationBlocked(BaseModel):
    """A request declined before any local process is started."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    state: Literal["blocked"] = "blocked"
    code: Literal["sensitive_input", "unsafe_control_sequence"]


class GenerationFailed(BaseModel):
    """A generic local-runtime failure that excludes raw runner output."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    state: Literal["failed"] = "failed"
    code: Literal[
        "runner_unavailable",
        "model_unavailable",
        "busy",
        "timed_out",
        "runner_failed",
        "empty_completion",
    ]


type GenerationResult = GenerationSuccess | GenerationBlocked | GenerationFailed
