from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from voicefishing.ide_contracts import WorkspaceFileWriteRequest
from voicefishing.ide_workspace import (
    ProjectWorkspace,
    WorkspaceError,
    WorkspaceErrorCode,
)
from voicefishing.web import create_app
from voicefishing.workbench_contracts import (
    GenerationReceipt,
    GenerationSuccess,
    WorkbenchRunRequest,
    WorkbenchStatus,
)


class ReadyWorkbench:
    def status(self) -> WorkbenchStatus:
        return WorkbenchStatus(
            runner_available=True,
            model_available=True,
            runner_name="llama-cli.exe",
            runner_path="C:/workspace/llama-cli.exe",
            model_name="Qwen3-8B-Q4_K_M.gguf",
            model_path="C:/workspace/Qwen3-8B-Q4_K_M.gguf",
            model_bytes=1_024,
            threads=4,
        )

    def run(self, request: WorkbenchRunRequest) -> GenerationSuccess:
        return GenerationSuccess(
            response="SAFE_LOCAL_RESPONSE",
            receipt=GenerationReceipt(
                elapsed_ms=12.5,
                output_digest="a" * 64,
                output_tokens=request.output_tokens,
            ),
        )


def test_workspace_lists_only_existing_allowed_project_text_files(
    tmp_path: Path,
) -> None:
    # Given: a project with both an editable source file and hidden runtime material
    source = tmp_path / "src" / "example.py"
    source.parent.mkdir()
    _ = source.write_text("print('safe')\n", encoding="utf-8")
    _ = (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")
    model = tmp_path / ".tools" / "models" / "model.gguf"
    model.parent.mkdir(parents=True)
    _ = model.write_bytes(b"model")

    # When: the IDE lists its workspace
    listing = ProjectWorkspace(tmp_path).list_files()

    # Then: only existing project-relative safe text files are exposed
    assert [item.path for item in listing.files] == ["README.md", "src/example.py"]


def test_workspace_rejects_parent_path_before_reading_a_file(tmp_path: Path) -> None:
    # Given: a scoped project workspace
    workspace = ProjectWorkspace(tmp_path)

    # When: a caller tries to escape through a parent path
    with pytest.raises(WorkspaceError) as captured:
        _ = workspace.read_file("../README.md")

    # Then: the request is rejected before filesystem access outside the workspace
    assert captured.value.code is WorkspaceErrorCode.INVALID_PATH


def test_workspace_writes_only_the_active_existing_safe_text_file(
    tmp_path: Path,
) -> None:
    # Given: a project source file opened by the workspace
    source = tmp_path / "src" / "example.py"
    source.parent.mkdir()
    _ = source.write_text("before\n", encoding="utf-8")
    workspace = ProjectWorkspace(tmp_path)

    # When: the user explicitly saves new source text to that existing file
    result = workspace.write_file(
        WorkspaceFileWriteRequest(path="src/example.py", content="after\n")
    )

    # Then: the saved file and returned IDE receipt identify only the safe relative path
    assert source.read_text(encoding="utf-8") == "after\n"
    assert result.path == "src/example.py"
    assert result.bytes == len(b"after\n")


def test_workspace_api_opens_and_saves_the_selected_file_without_path_escape(
    tmp_path: Path,
) -> None:
    # Given: a local app wired to an isolated project workspace
    source = tmp_path / "src" / "example.py"
    source.parent.mkdir()
    _ = source.write_text("before\n", encoding="utf-8")
    client = TestClient(create_app(ReadyWorkbench(), ProjectWorkspace(tmp_path)))

    # When: the browser lists, opens, and saves the selected file
    listing = client.get("/api/workspace/files")
    opened = client.get("/api/workspace/file", params={"path": "src/example.py"})
    saved = client.put(
        "/api/workspace/file",
        json={"path": "src/example.py", "content": "after\n"},
    )
    escaped = client.get("/api/workspace/file", params={"path": "../README.md"})

    # Then: the API uses structured workspace data and rejects escape attempts
    # generically.
    assert listing.status_code == 200
    assert listing.json()["files"][0]["path"] == "src/example.py"
    assert opened.status_code == 200
    assert opened.json()["content"] == "before\n"
    assert saved.status_code == 200
    assert saved.json()["path"] == "src/example.py"
    assert source.read_text(encoding="utf-8") == "after\n"
    assert escaped.status_code == 400
    assert escaped.json() == {"detail": "workspace_file_unavailable"}
