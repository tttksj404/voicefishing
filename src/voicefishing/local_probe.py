"""Run a local-only, content-safe GGUF readiness check."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from subprocess import TimeoutExpired, run
from time import perf_counter
from typing import Final, override

EXPECTED_MARKER: Final[str] = "SAFE_SIMULATOR_READY"
_CHAT_END_MARKER: Final[str] = "<|im_end|>"
_ASSISTANT_BOUNDARY: Final[str] = "<|im_start|>assistant\n"
_TRUNCATED_PROMPT_BOUNDARY: Final[str] = "... (truncated)\n"
_TIMING_BOUNDARY: Final[str] = "\n\n[ Prompt:"
_PROBE_TIMEOUT_SECONDS: Final[int] = 120
_MAX_THREADS: Final[int] = 32
_MAX_GPU_LAYERS: Final[int] = 99
_SAFE_PROMPT_PREFIX: Final[str] = (
    "<|im_start|>system\n"
    "You are running a defensive local-model health check. Never request or "
    "reproduce private or financial information.\n"
    "<|im_end|>\n"
    "<|im_start|>user\n"
    "Reply with exactly SAFE_SIMULATOR_READY and nothing else.\n"
)
_SAFE_PROMPT_SUFFIX: Final[str] = "<|im_end|>\n<|im_start|>assistant\n"


@dataclass(frozen=True, slots=True)
class ProbeConfigurationError(ValueError):
    """Raised when a readiness probe receives unsupported inference settings."""

    threads: int
    gpu_layers: int

    @override
    def __str__(self) -> str:
        """Describe the rejected resource bound without exposing local paths."""
        if not 1 <= self.threads <= _MAX_THREADS:
            return "probe threads must be between 1 and 32"
        return "probe GPU layers must be between 0 and 99"


@dataclass(frozen=True, slots=True)
class LocalProbeConfig:
    """Validated local paths and inference limits for a readiness probe."""

    runner: Path
    model: Path
    threads: int
    context_tokens: int = 512
    output_tokens: int = 12
    gpu_layers: int = 0
    thinking_enabled: bool = True

    def __post_init__(self) -> None:
        """Reject unsupported resource settings before process invocation."""
        if not 1 <= self.threads <= _MAX_THREADS:
            raise ProbeConfigurationError(
                threads=self.threads,
                gpu_layers=self.gpu_layers,
            )
        if not 0 <= self.gpu_layers <= _MAX_GPU_LAYERS:
            raise ProbeConfigurationError(
                threads=self.threads,
                gpu_layers=self.gpu_layers,
            )


@dataclass(frozen=True, slots=True)
class ProbeObservation:
    """Non-content result of a single local inference invocation."""

    elapsed_ms: float
    exit_code: int | None
    output_digest: str | None
    passed: bool


def build_llama_cli_command(config: LocalProbeConfig) -> tuple[str, ...]:
    """Build an argument vector without invoking a shell."""
    thinking_control = "" if config.thinking_enabled else "/no_think\n"
    safe_prompt = f"{_SAFE_PROMPT_PREFIX}{thinking_control}{_SAFE_PROMPT_SUFFIX}"
    gpu_arguments = ("-ngl", str(config.gpu_layers)) if config.gpu_layers > 0 else ()
    return (
        str(config.runner),
        "-m",
        str(config.model),
        "-p",
        safe_prompt,
        "-n",
        str(config.output_tokens),
        "-c",
        str(config.context_tokens),
        "-t",
        str(config.threads),
        *gpu_arguments,
        "--temp",
        "0",
        "--seed",
        "42",
        "--no-display-prompt",
        "--no-warmup",
        "--simple-io",
        "--log-disable",
        "--single-turn",
    )


def extract_completion(stdout: str) -> str:
    """Return only the completion segment from a known local-runner envelope."""
    _, boundary, after_assistant = stdout.rpartition(_ASSISTANT_BOUNDARY)
    if boundary:
        return _normalize_completion(after_assistant)

    # llama-cli b10621 can omit the assistant prefix when it abbreviates a
    # displayed contextual prompt. Its own truncation marker is then the only
    # reliable boundary between the echoed prompt and generated text.
    _, truncation, after_truncation = stdout.rpartition(_TRUNCATED_PROMPT_BOUNDARY)
    if truncation:
        return _normalize_completion(after_truncation)

    return ""


def _normalize_completion(output: str) -> str:
    """Discard runner framing without exposing the echoed prompt."""
    completion, _, _ = output.partition(_TIMING_BOUNDARY)
    return (
        completion.replace(_CHAT_END_MARKER, "")
        .replace(_ASSISTANT_BOUNDARY, "")
        .strip()
    )


def run_local_probe(config: LocalProbeConfig) -> ProbeObservation:
    """Invoke the local runner and retain only a digest of its completion."""
    started_at = perf_counter()
    try:
        completed = run(  # noqa: S603
            build_llama_cli_command(config),
            capture_output=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            text=True,
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
    except TimeoutExpired:
        return ProbeObservation(
            elapsed_ms=(perf_counter() - started_at) * 1_000,
            exit_code=None,
            output_digest=None,
            passed=False,
        )

    normalized = extract_completion(completed.stdout)
    output_digest = sha256(normalized.encode("utf-8")).hexdigest()
    return ProbeObservation(
        elapsed_ms=(perf_counter() - started_at) * 1_000,
        exit_code=completed.returncode,
        output_digest=output_digest,
        passed=completed.returncode == 0 and normalized == EXPECTED_MARKER,
    )
