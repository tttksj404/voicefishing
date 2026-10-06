from pathlib import Path
from subprocess import run
from sys import executable

import pytest

from voicefishing.local_probe import (
    EXPECTED_MARKER,
    LocalProbeConfig,
    ProbeConfigurationError,
    build_llama_cli_command,
    extract_completion,
)


def test_probe_command_routes_model_and_thread_count_to_portable_runner() -> None:
    # Given: an explicitly selected local runner and GGUF model
    config = LocalProbeConfig(
        runner=Path("llama-cli.exe"),
        model=Path("qwen.gguf"),
        threads=4,
    )

    # When: the health-check command is assembled
    command = build_llama_cli_command(config)

    # Then: execution uses only the intended local runner settings
    assert command[0] == "llama-cli.exe"
    assert command[command.index("-m") + 1] == "qwen.gguf"
    assert command[command.index("-t") + 1] == "4"
    assert "--simple-io" in command


def test_probe_command_offloads_configured_cuda_layers() -> None:
    # Given: a health-check configuration that selects CUDA layer offloading
    config = LocalProbeConfig(
        runner=Path("llama-cli.exe"),
        model=Path("qwen.gguf"),
        threads=4,
        gpu_layers=99,
    )

    # When: the health-check command is assembled
    command = build_llama_cli_command(config)

    # Then: the portable runner receives the explicit GPU-layer count
    assert command[command.index("-ngl") + 1] == "99"


def test_probe_command_disables_qwen3_thinking_when_configured() -> None:
    # Given: a Qwen3 health-check configuration with thinking disabled
    config = LocalProbeConfig(
        runner=Path("llama-cli.exe"),
        model=Path("qwen.gguf"),
        threads=4,
        thinking_enabled=False,
    )

    # When: the health-check command is assembled
    command = build_llama_cli_command(config)

    # Then: the Qwen3 runtime control token is part of the user turn
    assert "\n/no_think\n" in command[command.index("-p") + 1]


def test_probe_config_rejects_out_of_range_gpu_layers() -> None:
    # Given: an otherwise valid local readiness configuration
    # When: a caller requests more GPU layers than the local contract permits
    with pytest.raises(ProbeConfigurationError) as captured:
        _ = LocalProbeConfig(
            runner=Path("llama-cli.exe"),
            model=Path("qwen.gguf"),
            threads=4,
            gpu_layers=100,
        )

    # Then: the typed configuration error preserves the rejected setting
    assert captured.value.gpu_layers == 100


def test_probe_script_invokes_its_typer_app_when_run_directly() -> None:
    # Given: the script's real Python entry point
    workspace = Path(__file__).parents[1]

    # When: it is invoked as a normal command-line program
    result = run(
        (executable, "scripts/local_gguf_probe.py", "--help"),
        capture_output=True,
        check=False,
        cwd=workspace,
        encoding="utf-8",
        text=True,
    )

    # Then: Typer exposes the command instead of silently exiting
    assert result.returncode == 0
    assert "Verify one local" in result.stdout


def test_extract_completion_discards_runner_banner_prompt_and_timing() -> None:
    # Given: the observed non-content shell wrapped around a safe completion
    runner_stdout = (
        "Loading model...\n"
        "> <|im_start|>assistant\n\n"
        f"{EXPECTED_MARKER}\n\n"
        "[ Prompt: 346.4 t/s | Generation: 60.5 t/s ]\n"
    )

    # When: the readiness probe isolates the completion segment
    completion = extract_completion(runner_stdout)

    # Then: only the marker is left for contract verification and hashing
    assert completion == EXPECTED_MARKER


def test_extract_completion_uses_runner_truncation_boundary_without_assistant_marker(
) -> None:
    # Given: llama-cli omitted the assistant prefix while truncating a displayed prompt
    runner_stdout = (
        "Loading model...\n"
        "> <|im_start|>system\n"
        "safe system prompt\n"
        "<|im_end|>\n"
        "<|im_start|>user\n"
        "context and request ... (truncated)\n"
        "A bounded model response.\n\n"
        "[ Prompt: 346.4 t/s | Generation: 60.5 t/s ]\n"
    )

    # When: the completion parser receives the observed local runner envelope
    completion = extract_completion(runner_stdout)

    # Then: only generated text after the runner truncation marker is retained
    assert completion == "A bounded model response."
