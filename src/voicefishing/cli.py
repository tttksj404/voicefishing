"""CLI entry points for the synthetic-only simulator."""

from typing import Annotated, NoReturn, assert_never

import typer
from pydantic import ValidationError

from voicefishing.contracts import ConversationMode, IncomingTurn, KnowledgeCategory
from voicefishing.simulator import BlockedTurn, SafeScenarioSimulator, SimulatedTurn
from voicefishing.web import run_workbench

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def start(
    message: Annotated[str, typer.Option("--message", help="합성 훈련용 발화")],
    category: Annotated[
        list[KnowledgeCategory],
        typer.Option("--category", help="상대가 안다고 주장하는 정보 범주"),
    ],
) -> None:
    """Start a disclosed synthetic session."""
    try:
        incoming = IncomingTurn(
            mode=ConversationMode.FROM_START,
            message=message,
            claimed_categories=tuple(category),
        )
    except ValidationError:
        _emit_invalid_contract()
    _emit(SafeScenarioSimulator.reply(incoming))


@app.command()
def handoff(
    message: Annotated[str, typer.Option("--message", help="합성 훈련용 발화")],
    category: Annotated[
        list[KnowledgeCategory],
        typer.Option("--category", help="상대가 안다고 주장하는 정보 범주"),
    ],
    marker: Annotated[str, typer.Option("--marker", help="비식별 연속성 표식")],
) -> None:
    """Continue from a bounded, opaque handoff marker."""
    try:
        incoming = IncomingTurn(
            mode=ConversationMode.MID_CALL_HANDOFF,
            message=message,
            claimed_categories=tuple(category),
            handoff_marker=marker,
        )
    except ValidationError:
        _emit_invalid_contract()
    _emit(SafeScenarioSimulator.reply(incoming))


@app.command()
def workbench(
    port: Annotated[
        int,
        typer.Option(
            "--port",
            min=1024,
            max=65535,
            help="로컬 브라우저 워크벤치 포트",
        ),
    ] = 8765,
) -> None:
    """Run the browser-local Qwen GGUF workbench on 127.0.0.1."""
    run_workbench(port=port)


def _emit_invalid_contract() -> NoReturn:
    """Fail without rendering a rejected input value."""
    typer.echo("blocked=invalid_synthetic_contract")
    raise typer.Exit(code=2)


def _emit(result: SimulatedTurn | BlockedTurn) -> None:
    """Print only the safe observable contract, never an input transcript."""
    match result:
        case SimulatedTurn(
            message=message,
            claimed_categories=claimed_categories,
            handoff_marker=handoff_marker,
            trace_digest=trace_digest,
        ):
            typer.echo(message)
            category_values = ",".join(
                category.value for category in claimed_categories
            )
            typer.echo(f"claimed_categories={category_values}")
            typer.echo(f"handoff_marker={handoff_marker or '-'}")
            typer.echo(f"trace_digest={trace_digest}")
            return
        case BlockedTurn(reason=reason):
            typer.echo(f"blocked={reason}")
            return
        case _:
            assert_never(result)
