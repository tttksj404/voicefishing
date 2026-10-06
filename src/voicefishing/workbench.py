"""Execute the bundled Qwen GGUF through a local-only llama.cpp process."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from subprocess import TimeoutExpired, run
from threading import Lock
from time import perf_counter
from typing import Final, final, override

from voicefishing.local_probe import extract_completion
from voicefishing.safety import find_sensitive_input
from voicefishing.workbench_contracts import (
    GenerationBlocked,
    GenerationFailed,
    GenerationReceipt,
    GenerationResult,
    GenerationSuccess,
    WorkbenchRunRequest,
    WorkbenchStatus,
)

MAX_WORKBENCH_THREADS: Final[int] = 32
MAX_GPU_LAYERS: Final[int] = 99
_CONTEXT_TOKENS: Final[int] = 2_048
_MODEL_TIMEOUT_SECONDS: Final[int] = 120
_CHAT_CONTROL_SEQUENCES: Final[tuple[str, ...]] = (
    "<|im_start|>",
    "<|im_end|>",
)
_WORKBENCH_SYSTEM_PROMPT: Final[str] = (
    "You are Local Qwen Workbench, a local defensive assistant. "
    "Never request, infer, or reproduce private, financial, or authentication "
    "information. Do not help with impersonation or social engineering. "
    "Respond to the user's safe task directly and concisely.\n"
)


@dataclass(frozen=True, slots=True)
class WorkbenchConfigurationError(ValueError):
    """Raised when a caller supplies an unsupported local configuration."""

    threads: int
    gpu_layers: int

    @override
    def __str__(self) -> str:
        """Describe the rejected setting without exposing a filesystem path."""
        if not 1 <= self.threads <= MAX_WORKBENCH_THREADS:
            return "workbench threads must be between 1 and 32"
        return "workbench GPU layers must be between 0 and 99"


@dataclass(frozen=True, slots=True)
class LocalModelConfig:
    """Paths and bounded inference settings for the bundled local model."""

    runner: Path
    model: Path
    threads: int
    gpu_layers: int = 0
    thinking_enabled: bool = True

    def __post_init__(self) -> None:
        """Reject inference settings that are unsupported by the local contract."""
        if not 1 <= self.threads <= MAX_WORKBENCH_THREADS:
            raise WorkbenchConfigurationError(
                threads=self.threads,
                gpu_layers=self.gpu_layers,
            )
        if not 0 <= self.gpu_layers <= MAX_GPU_LAYERS:
            raise WorkbenchConfigurationError(
                threads=self.threads,
                gpu_layers=self.gpu_layers,
            )


def default_workbench_config(project_root: Path | None = None) -> LocalModelConfig:
    """Return the verified runner and Qwen GGUF paths bundled with this checkout."""
    resolved_root = project_root or Path(__file__).resolve().parents[2]
    cuda_runner = (
        resolved_root
        / ".tools"
        / "llama-b10621-bin-win-cuda-12.4-x64"
        / "llama-cli.exe"
    )
    cuda_model = resolved_root / ".tools" / "models" / "Qwen3-8B-Q4_K_M.gguf"
    if cuda_runner.is_file() and cuda_model.is_file():
        return LocalModelConfig(
            runner=cuda_runner,
            model=cuda_model,
            threads=4,
            gpu_layers=MAX_GPU_LAYERS,
            thinking_enabled=False,
        )
    return LocalModelConfig(
        runner=(
            resolved_root / ".tools" / "llama-b10621-bin-win-cpu-x64" / "llama-cli.exe"
        ),
        model=resolved_root / ".tools" / "models" / "qwen2.5-0.5b-instruct-q8_0.gguf",
        threads=4,
    )


def build_workbench_command(
    config: LocalModelConfig,
    prompt: str,
    output_tokens: int,
) -> tuple[str, ...]:
    """Build a direct process invocation for one local Qwen completion."""
    user_prompt = f"{prompt}\n/no_think" if not config.thinking_enabled else prompt
    qwen_prompt = (
        "<|im_start|>system\n"
        f"{_WORKBENCH_SYSTEM_PROMPT}"
        "<|im_end|>\n"
        "<|im_start|>user\n"
        f"{user_prompt}\n"
        "<|im_end|>\n"
        "<|im_start|>assistant\n"
    )
    gpu_arguments = ("-ngl", str(config.gpu_layers)) if config.gpu_layers > 0 else ()
    return (
        str(config.runner),
        "-m",
        str(config.model),
        "-p",
        qwen_prompt,
        "-n",
        str(output_tokens),
        "-c",
        str(_CONTEXT_TOKENS),
        "-t",
        str(config.threads),
        *gpu_arguments,
        "--temp",
        "0.2",
        "--seed",
        "42",
        "--no-display-prompt",
        "--no-warmup",
        "--simple-io",
        "--log-disable",
        "--single-turn",
    )


@final
class LocalWorkbench:
    """Run one bounded local completion at a time without persistent transcripts."""

    def __init__(self, config: LocalModelConfig) -> None:
        """Bind one model configuration to an in-process concurrency gate."""
        self._config = config
        self._run_lock = Lock()

    def status(self) -> WorkbenchStatus:
        """Return only path readiness and non-sensitive model metadata."""
        model_available = self._config.model.is_file()
        return WorkbenchStatus(
            runner_available=self._config.runner.is_file(),
            model_available=model_available,
            runner_name=self._config.runner.name,
            runner_path=str(self._config.runner),
            model_name=self._config.model.name,
            model_path=str(self._config.model),
            model_bytes=self._config.model.stat().st_size if model_available else None,
            threads=self._config.threads,
        )

    def run(self, request: WorkbenchRunRequest) -> GenerationResult:
        """Validate and execute a single unpersisted, safe local completion."""
        if find_sensitive_input(request.prompt, None) is not None:
            return GenerationBlocked(code="sensitive_input")
        if any(token in request.prompt for token in _CHAT_CONTROL_SEQUENCES):
            return GenerationBlocked(code="unsafe_control_sequence")
        if not self._config.runner.is_file():
            return GenerationFailed(code="runner_unavailable")
        if not self._config.model.is_file():
            return GenerationFailed(code="model_unavailable")
        if not self._run_lock.acquire(blocking=False):
            return GenerationFailed(code="busy")

        try:
            return self._invoke(request)
        finally:
            self._run_lock.release()

    def _invoke(self, request: WorkbenchRunRequest) -> GenerationResult:
        """Call llama.cpp and return a response without retaining runner logs."""
        started_at = perf_counter()
        try:
            completed = run(  # noqa: S603
                build_workbench_command(
                    self._config,
                    prompt=request.prompt,
                    output_tokens=request.output_tokens,
                ),
                capture_output=True,
                check=False,
                encoding="utf-8",
                errors="replace",
                text=True,
                timeout=_MODEL_TIMEOUT_SECONDS,
            )
        except TimeoutExpired:
            return GenerationFailed(code="timed_out")
        except OSError:
            return GenerationFailed(code="runner_failed")

        if completed.returncode != 0:
            return GenerationFailed(code="runner_failed")

        completion = extract_completion(completed.stdout)
        if not completion:
            return GenerationFailed(code="empty_completion")

        return GenerationSuccess(
            response=completion,
            receipt=GenerationReceipt(
                elapsed_ms=(perf_counter() - started_at) * 1_000,
                output_digest=sha256(completion.encode("utf-8")).hexdigest(),
                output_tokens=request.output_tokens,
            ),
        )
