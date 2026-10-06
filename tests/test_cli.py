from typer.testing import CliRunner

from voicefishing.cli import app


def test_simulate_command_reports_a_disclosed_synthetic_turn() -> None:
    # Given: the public command line entry point
    runner = CliRunner()

    # When: a synthetic session starts without private values
    result = runner.invoke(
        app,
        [
            "start",
            "--message",
            "합성 훈련을 시작합니다.",
            "--category",
            "contact",
        ],
    )

    # Then: the observable output stays in the synthetic safety boundary
    assert result.exit_code == 0
    assert "합성 훈련" in result.stdout
    assert "개인정보를 제공하지 마세요" in result.stdout


def test_handoff_rejects_an_invalid_marker_without_echoing_it() -> None:
    # Given: an opaque-marker violation at the public command line
    runner = CliRunner()
    raw_marker = "plain-readable-marker"

    # When: a caller tries to pass the marker through the handoff command
    result = runner.invoke(
        app,
        [
            "handoff",
            "--message",
            "continue synthetic context",
            "--category",
            "name",
            "--marker",
            raw_marker,
        ],
    )

    # Then: the CLI exposes a fixed safety code, never the rejected value
    assert result.exit_code == 2
    assert result.stdout == "blocked=invalid_synthetic_contract\n"
    assert raw_marker not in result.stdout
