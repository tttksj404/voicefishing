const MAX_ASSISTANT_PROMPT_LENGTH = 700;
const MAX_FILE_CONTEXT_CHARS = 1000;
const MAX_WORKBENCH_PROMPT_LENGTH = 2000;

const elements = {
  root: document.querySelector(".workbench"),
  workspaceFiles: document.querySelector("#workspace-files"),
  fileListStatus: document.querySelector("#file-list-status"),
  editorTitle: document.querySelector("#editor-title"),
  activeFilePath: document.querySelector("#active-file-path"),
  fileEditor: document.querySelector("#file-editor"),
  lineNumbers: document.querySelector("#line-numbers"),
  fileLanguage: document.querySelector("#file-language"),
  fileSize: document.querySelector("#file-size"),
  fileStatus: document.querySelector("#file-status"),
  saveButton: document.querySelector("#save-button"),
  saveLabel: document.querySelector("#save-label"),
  editorFeedback: document.querySelector("#editor-feedback"),
  assistantForm: document.querySelector("#assistant-form"),
  assistantPrompt: document.querySelector("#assistant-prompt"),
  assistantCharacterCount: document.querySelector("#assistant-character-count"),
  includeFileContext: document.querySelector("#include-file-context"),
  askButton: document.querySelector("#ask-button"),
  askLabel: document.querySelector("#ask-label"),
  clearButton: document.querySelector("#clear-button"),
  copyButton: document.querySelector("#copy-button"),
  output: document.querySelector("#output"),
  outputStatus: document.querySelector("#output-status"),
  assistantFeedback: document.querySelector("#assistant-feedback"),
  headerStatus: document.querySelector("#header-status"),
  footerState: document.querySelector("#footer-state"),
  modelName: document.querySelector("#model-name"),
  modelSize: document.querySelector("#model-size"),
  runnerStatus: document.querySelector("#runner-status"),
  threadCount: document.querySelector("#thread-count"),
  receiptState: document.querySelector("#receipt-state"),
  receiptElapsed: document.querySelector("#receipt-elapsed"),
  receiptTokens: document.querySelector("#receipt-tokens"),
  receiptDigest: document.querySelector("#receipt-digest"),
};

let activeFile = null;
let fileDirty = false;
let fileSaving = false;
let requestRunning = false;
let runtimeReady = false;
let latestOutput = "";
let workspaceFiles = [];

function formatBytes(value) {
  if (value === null || value === undefined) {
    return "—";
  }

  const kibibytes = value / 1024;
  if (kibibytes < 1024) {
    return `${kibibytes.toFixed(1)} KiB`;
  }

  return `${(kibibytes / 1024).toFixed(1)} MiB`;
}

function setStatusMarker(element, label, tone = "") {
  element.textContent = label;
  element.className = `status-marker ${tone}`.trim();
}

function setOutput(label, tone, text) {
  setStatusMarker(elements.outputStatus, label, tone);
  elements.output.textContent = text;
}

function resetReceipt() {
  elements.receiptState.textContent = "아직 없음";
  elements.receiptElapsed.textContent = "—";
  elements.receiptTokens.textContent = "—";
  elements.receiptDigest.textContent = "—";
}

function setRunningReceipt() {
  elements.receiptState.textContent = "실행 중";
  elements.receiptElapsed.textContent = "계산 중";
  elements.receiptTokens.textContent = "—";
  elements.receiptDigest.textContent = "—";
}

function renderReceipt(receipt) {
  elements.receiptState.textContent = "완료";
  elements.receiptElapsed.textContent = `${receipt.elapsed_ms.toFixed(1)} ms`;
  elements.receiptTokens.textContent = `${receipt.output_tokens} tokens`;
  elements.receiptDigest.textContent = receipt.output_digest;
}

function setRequestState(state) {
  const running = state === "running";
  const labels = {
    ready: "Qwen에게 묻기",
    running: "Qwen 생성 중",
    complete: "응답 준비됨",
    blocked: "안전 차단됨",
    failed: "다시 요청하기",
  };

  requestRunning = running;
  elements.root.dataset.runState = state;
  elements.askButton.disabled = running || !runtimeReady;
  elements.askButton.classList.toggle("is-loading", running);
  elements.askButton.setAttribute("aria-busy", String(running));
  elements.askLabel.textContent = labels[state];
  elements.assistantPrompt.disabled = running;
  elements.includeFileContext.disabled = running;
  elements.clearButton.disabled = running;
}

function setFileState(state) {
  const loading = state === "loading";
  const saving = state === "saving";
  const active = activeFile !== null;
  const status = {
    empty: ["파일 없음", ""],
    loading: ["파일 여는 중", "is-running"],
    ready: ["저장됨", "is-ready"],
    dirty: ["수정됨", "is-warning"],
    saving: ["저장 중", "is-running"],
    saved: ["저장됨", "is-ready"],
    failed: ["저장 실패", "is-error"],
  };

  elements.root.dataset.fileState = state;
  elements.fileEditor.disabled = !active || loading || saving;
  elements.saveButton.disabled = !active || !fileDirty || saving || loading;
  elements.saveButton.classList.toggle("is-loading", saving);
  elements.saveButton.setAttribute("aria-busy", String(saving));
  elements.saveLabel.textContent = saving ? "저장 중" : state === "saved" ? "저장됨" : "저장";
  setStatusMarker(elements.fileStatus, status[state][0], status[state][1]);
}

function updateAssistantCharacterCount() {
  elements.assistantCharacterCount.textContent = `${elements.assistantPrompt.value.length} / ${MAX_ASSISTANT_PROMPT_LENGTH}`;
}

function syncLineNumbers() {
  elements.lineNumbers.style.transform = `translateY(${-elements.fileEditor.scrollTop}px)`;
}

function updateLineNumbers() {
  const count = Math.max(1, elements.fileEditor.value.split("\n").length);
  elements.lineNumbers.textContent = Array.from({ length: count }, (_, index) => String(index + 1)).join("\n");
  syncLineNumbers();
}

function describeFailure(code) {
  const messages = {
    runner_unavailable: "로컬 llama.cpp 실행 파일을 찾지 못했습니다.",
    model_unavailable: "번들 Qwen GGUF 파일을 찾지 못했습니다.",
    busy: "이미 다른 로컬 생성이 진행 중입니다. 완료된 뒤 다시 요청하세요.",
    timed_out: "로컬 모델 응답 시간이 제한을 넘었습니다. 요청을 짧게 줄여 다시 시도하세요.",
    runner_failed: "로컬 모델 실행이 완료되지 않았습니다. 런타임 상태를 다시 확인하세요.",
    empty_completion: "모델이 표시할 수 있는 응답을 반환하지 않았습니다. 다시 시도하세요.",
  };
  return messages[code] ?? "로컬 모델 실행 상태를 확인하지 못했습니다.";
}

function fileName(path) {
  const parts = path.split("/");
  return parts[parts.length - 1] || path;
}

function fileExtension(path) {
  const name = fileName(path);
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(dot + 1).toUpperCase() : "TEXT";
}

function renderFileList(files) {
  elements.workspaceFiles.replaceChildren();
  if (files.length === 0) {
    const empty = document.createElement("p");
    empty.className = "file-list-empty";
    empty.textContent = "열 수 있는 기존 프로젝트 텍스트 파일이 없습니다.";
    elements.workspaceFiles.append(empty);
    return;
  }

  for (const file of files) {
    const button = document.createElement("button");
    const extension = document.createElement("span");
    const label = document.createElement("span");
    const isActive = activeFile?.path === file.path;

    button.type = "button";
    button.className = `file-item${isActive ? " is-active" : ""}`;
    button.title = file.path;
    if (isActive) {
      button.setAttribute("aria-current", "page");
    }
    extension.className = "file-extension";
    extension.textContent = fileExtension(file.path);
    label.className = "file-item-label";
    label.textContent = file.path;
    button.append(extension, label);
    button.addEventListener("click", () => {
      void openFile(file.path);
    });
    elements.workspaceFiles.append(button);
  }
}

function resetEditorSurface() {
  activeFile = null;
  fileDirty = false;
  elements.editorTitle.textContent = "파일을 선택하세요";
  elements.activeFilePath.textContent = "열 수 있는 프로젝트 파일이 없습니다.";
  elements.fileEditor.value = "";
  elements.fileLanguage.textContent = "—";
  elements.fileSize.textContent = "—";
  elements.editorFeedback.textContent = "";
  updateLineNumbers();
  setFileState("empty");
}

function showLoadedFile(payload) {
  activeFile = payload;
  fileDirty = false;
  elements.editorTitle.textContent = fileName(payload.path);
  elements.activeFilePath.textContent = payload.path;
  elements.fileEditor.value = payload.content;
  elements.fileLanguage.textContent = payload.language;
  elements.fileSize.textContent = formatBytes(payload.bytes);
  elements.editorFeedback.textContent = "파일을 열었습니다. 저장은 명시적으로 요청할 때만 수행됩니다.";
  updateLineNumbers();
  renderFileList(workspaceFiles);
  setFileState("ready");
}

async function refreshStatus() {
  try {
    const response = await fetch("/api/status");
    if (!response.ok) {
      throw new Error("status_unavailable");
    }
    const status = await response.json();
    runtimeReady = Boolean(status.runner_available && status.model_available);
    elements.modelName.textContent = status.model_name;
    elements.modelSize.textContent = formatBytes(status.model_bytes);
    elements.runnerStatus.textContent = status.runner_available ? status.runner_name : "실행 파일 없음";
    elements.threadCount.textContent = `${status.threads} threads`;

    if (runtimeReady) {
      setStatusMarker(elements.headerStatus, "로컬 런타임 확인됨", "is-ready");
      elements.footerState.textContent = "Qwen3 실행 경로가 이 PC에서 준비되었습니다.";
    } else {
      setStatusMarker(elements.headerStatus, "로컬 경로를 확인하세요", "is-error");
      elements.footerState.textContent = "모델 또는 러너 경로가 준비되지 않았습니다.";
    }
  } catch {
    runtimeReady = false;
    setStatusMarker(elements.headerStatus, "상태를 읽지 못함", "is-error");
    elements.footerState.textContent = "로컬 IDE API에 연결하지 못했습니다.";
  }

  setRequestState(requestRunning ? "running" : "ready");
}

async function loadWorkspace() {
  setStatusMarker(elements.fileListStatus, "파일을 읽는 중", "is-running");
  try {
    const response = await fetch("/api/workspace/files");
    if (!response.ok) {
      throw new Error("workspace_unavailable");
    }
    const payload = await response.json();
    workspaceFiles = payload.files;
    renderFileList(workspaceFiles);

    if (payload.files.length === 0) {
      resetEditorSurface();
      setStatusMarker(elements.fileListStatus, "열 파일 없음", "is-warning");
      return;
    }

    setStatusMarker(elements.fileListStatus, `${payload.files.length}개 파일`, "is-ready");
    await openFile(payload.files[0].path, false);
  } catch {
    workspaceFiles = [];
    resetEditorSurface();
    setStatusMarker(elements.fileListStatus, "파일 목록 실패", "is-error");
    elements.editorFeedback.textContent = "프로젝트 파일 목록을 읽지 못했습니다.";
  }
}

async function openFile(path, confirmUnsaved = true) {
  if (fileDirty && activeFile?.path !== path && confirmUnsaved) {
    const discard = window.confirm("저장하지 않은 수정 내용이 있습니다. 다른 파일을 열까요?");
    if (!discard) {
      return;
    }
  }

  setFileState("loading");
  elements.editorFeedback.textContent = "선택한 파일을 읽는 중입니다.";
  try {
    const response = await fetch(`/api/workspace/file?path=${encodeURIComponent(path)}`);
    if (!response.ok) {
      throw new Error("file_unavailable");
    }
    showLoadedFile(await response.json());
  } catch {
    setFileState(activeFile ? "dirty" : "empty");
    elements.editorFeedback.textContent = "선택한 파일을 열지 못했습니다. 안전한 프로젝트 파일인지 확인하세요.";
  }
}

async function saveFile() {
  if (!activeFile || !fileDirty || fileSaving) {
    return;
  }

  fileSaving = true;
  setFileState("saving");
  elements.editorFeedback.textContent = "현재 파일을 저장하는 중입니다.";
  let saved = false;
  try {
    const response = await fetch("/api/workspace/file", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: activeFile.path, content: elements.fileEditor.value }),
    });
    if (!response.ok) {
      throw new Error("save_unavailable");
    }
    const payload = await response.json();
    activeFile = { ...activeFile, bytes: payload.bytes, content: elements.fileEditor.value };
    fileDirty = false;
    saved = true;
    elements.fileSize.textContent = formatBytes(payload.bytes);
    elements.editorFeedback.textContent = "현재 파일을 저장했습니다.";
  } catch {
    elements.editorFeedback.textContent = "파일을 저장하지 못했습니다. 선택한 기존 프로젝트 파일만 저장할 수 있습니다.";
  } finally {
    fileSaving = false;
    setFileState(saved ? "saved" : "failed");
  }
}

function buildAssistantPrompt(instruction) {
  if (!elements.includeFileContext.checked || !activeFile) {
    return { prompt: instruction, contextIncluded: false };
  }

  const selectedText = elements.fileEditor.value.slice(
    elements.fileEditor.selectionStart,
    elements.fileEditor.selectionEnd,
  );
  const sourceText = selectedText || elements.fileEditor.value;
  const header = `현재 프로젝트 파일: ${activeFile.path}\n코드 문맥:\n`;
  const requestSuffix = `\n\n요청:\n${instruction}`;
  const remaining = MAX_WORKBENCH_PROMPT_LENGTH - header.length - requestSuffix.length;
  const context = sourceText.slice(0, Math.min(MAX_FILE_CONTEXT_CHARS, Math.max(0, remaining)));

  if (!context) {
    return { prompt: instruction, contextIncluded: false };
  }

  return {
    prompt: `${header}${context}${requestSuffix}`,
    contextIncluded: true,
  };
}

async function askQwen() {
  const instruction = elements.assistantPrompt.value.trim();
  if (!instruction) {
    elements.assistantPrompt.focus();
    elements.assistantFeedback.textContent = "Qwen에게 보낼 요청을 입력하세요.";
    return;
  }

  const request = buildAssistantPrompt(instruction);
  setRequestState("running");
  latestOutput = "";
  elements.copyButton.disabled = true;
  elements.assistantFeedback.textContent = "로컬 Qwen3가 요청을 처리하고 있습니다.";
  setOutput("생성 중", "is-running", "로컬 Qwen이 응답을 생성하고 있습니다.");
  setRunningReceipt();

  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: request.prompt }),
    });
    const payload = await response.json();

    if (!response.ok) {
      setOutput("실패", "is-error", "요청 형식을 확인하지 못했습니다.");
      resetReceipt();
      elements.receiptState.textContent = "실행 실패";
      elements.assistantFeedback.textContent = "요청 길이와 형식을 확인한 뒤 다시 시도하세요.";
      setRequestState("failed");
      return;
    }

    if (payload.state === "complete") {
      latestOutput = payload.response;
      setOutput("완료", "is-ready", payload.response);
      renderReceipt(payload.receipt);
      elements.copyButton.disabled = false;
      elements.assistantFeedback.textContent = request.contextIncluded
        ? "선택한 파일 문맥을 함께 처리했습니다. 응답은 자동 적용되지 않습니다."
        : "요청만 로컬에서 처리했습니다. 응답은 자동 적용되지 않습니다.";
      setRequestState("complete");
      return;
    }

    latestOutput = "";
    elements.copyButton.disabled = true;
    if (payload.state === "blocked") {
      setOutput("차단됨", "is-error", "민감한 형태 또는 제어 시퀀스가 감지되어 실행하지 않았습니다.");
      resetReceipt();
      elements.receiptState.textContent = "안전 차단";
      elements.assistantFeedback.textContent = "차단된 요청은 화면이나 서버 로그에 다시 표시하지 않습니다.";
      setRequestState("blocked");
      return;
    }

    setOutput("실패", "is-error", describeFailure(payload.code));
    resetReceipt();
    elements.receiptState.textContent = "실행 실패";
    elements.assistantFeedback.textContent = "원본 요청과 러너 표준 오류는 저장하거나 표시하지 않습니다.";
    setRequestState("failed");
  } catch {
    latestOutput = "";
    elements.copyButton.disabled = true;
    setOutput("실패", "is-error", "로컬 IDE API와 통신하지 못했습니다.");
    resetReceipt();
    elements.receiptState.textContent = "실행 실패";
    elements.assistantFeedback.textContent = "서버가 실행 중인지 확인한 뒤 다시 시도하세요.";
    setRequestState("failed");
  }
}

function clearAssistantPrompt() {
  elements.assistantPrompt.value = "";
  updateAssistantCharacterCount();
  elements.assistantPrompt.focus();
  elements.assistantFeedback.textContent = "현재 탭의 Qwen 요청을 지웠습니다.";
  if (!requestRunning) {
    setRequestState("ready");
  }
}

async function copyOutput() {
  if (!latestOutput) {
    return;
  }

  try {
    await navigator.clipboard.writeText(latestOutput);
    elements.assistantFeedback.textContent = "현재 응답을 클립보드에 복사했습니다.";
  } catch {
    elements.assistantFeedback.textContent = "브라우저가 클립보드 복사를 허용하지 않았습니다.";
  }
}

function updateDirtyState() {
  if (!activeFile || fileSaving) {
    return;
  }

  fileDirty = elements.fileEditor.value !== activeFile.content;
  setFileState(fileDirty ? "dirty" : "ready");
  elements.editorFeedback.textContent = fileDirty ? "수정 내용이 있습니다. 저장하려면 Ctrl+S를 누르세요." : "저장된 내용과 같습니다.";
  updateLineNumbers();
}

function handleEditorKeydown(event) {
  if (event.key !== "Tab" || event.ctrlKey || event.altKey || event.metaKey) {
    return;
  }
  if (elements.fileEditor.selectionStart !== elements.fileEditor.selectionEnd) {
    return;
  }

  event.preventDefault();
  const cursor = elements.fileEditor.selectionStart;
  elements.fileEditor.setRangeText("  ", cursor, cursor, "end");
  updateDirtyState();
}

function initializeIDE() {
  if (!elements.assistantForm || !elements.fileEditor) {
    return;
  }

  elements.assistantForm.addEventListener("submit", (event) => {
    event.preventDefault();
    void askQwen();
  });
  elements.assistantPrompt.addEventListener("input", () => {
    updateAssistantCharacterCount();
    if (!requestRunning) {
      setRequestState("ready");
    }
  });
  elements.assistantPrompt.addEventListener("keydown", (event) => {
    if (event.ctrlKey && event.key === "Enter") {
      event.preventDefault();
      void askQwen();
    }
  });
  elements.clearButton.addEventListener("click", clearAssistantPrompt);
  elements.copyButton.addEventListener("click", () => {
    void copyOutput();
  });
  elements.saveButton.addEventListener("click", () => {
    void saveFile();
  });
  elements.fileEditor.addEventListener("input", updateDirtyState);
  elements.fileEditor.addEventListener("scroll", syncLineNumbers);
  elements.fileEditor.addEventListener("keydown", handleEditorKeydown);
  document.addEventListener("keydown", (event) => {
    if (event.ctrlKey && event.key.toLowerCase() === "s" && activeFile) {
      event.preventDefault();
      void saveFile();
    }
  });
  window.addEventListener("beforeunload", (event) => {
    if (fileDirty) {
      event.preventDefault();
      event.returnValue = "";
    }
  });

  updateAssistantCharacterCount();
  updateLineNumbers();
  resetReceipt();
  setFileState("empty");
  setRequestState("ready");
  void refreshStatus();
  void loadWorkspace();
}

initializeIDE();
