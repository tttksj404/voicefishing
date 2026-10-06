# ─── How to run ───
# uv run python scripts/local_gguf_probe.py --runner "<path-to-llama-cli>" \
#   --model "<path-to-qwen-gguf>"
"""Measure only a harmless local GGUF readiness contract."""

from pathlib import Path
from typing import Annotated

import typer

from voicefishing.local_probe import LocalProbeConfig, run_local_probe

app = typer.Typer(add_completion=False)


@app.command()
def probe(
    runner: Annotated[
        Path,
        typer.Option("--runner", exists=True, readable=True, resolve_path=True),
    ],
    model: Annotated[
        Path,
        typer.Option("--model", exists=True, readable=True, resolve_path=True),
    ],
    threads: Annotated[int, typer.Option("--threads", min=1, max=32)] = 4,
    gpu_layers: Annotated[int, typer.Option("--gpu-layers", min=0, max=99)] = 0,
    thinking_enabled: Annotated[
        bool,
        typer.Option("--thinking/--no-thinking"),
    ] = True,
) -> None:
    """Verify one local, synthetic-only model completion without retaining text."""
    observation = run_local_probe(
        LocalProbeConfig(
            runner=runner,
            model=model,
            threads=threads,
            gpu_layers=gpu_layers,
            thinking_enabled=thinking_enabled,
        )
    )
    if not observation.passed:
        typer.echo("LOCAL_GGUF_PROBE=FAIL")
        typer.echo(f"EXIT_CODE={observation.exit_code}")
        raise typer.Exit(code=1)

    typer.echo("LOCAL_GGUF_PROBE=PASS")
    typer.echo(f"COLD_START_MS={observation.elapsed_ms:.1f}")
    typer.echo(f"OUTPUT_SHA256={observation.output_digest}")


if __name__ == "__main__":
    app()
