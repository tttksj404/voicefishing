# Codex 스킬·지침 가이드 — voicefishing

> 생성일 2026-11-23. Codex 작업 폴더 `~/Documents/ChatGPT/voicefishing`에서 이 레포를 다룰 때 적용되는 지침과 자주 쓰는 스킬이다.
> 전체 목록(사용자 스킬 66개, 플러그인 스킬, 모든 작업 폴더 맵)은 `tttksj404/codex-global-skills`의 `docs/codex-skill-usage-guide.md`에 있다.

## 적용 지침

| 지침 | 언제 | 내용 |
|---|---|---|
| 전역 `~/.codex/AGENTS.md` | 모든 작업 | 한국어 답변, 직접 수행·검증, 결과/검증/남은 리스크 보고, 복잡한 작업은 `codex-fablize` 자동 승격 |

## 이 레포에서 주로 쓰는 스킬

"언제 쓰나"는 각 `SKILL.md`의 description 원문이다.

| 스킬 | 언제 쓰나 (SKILL.md description) |
|---|---|
| `codex-fablize` | Use when the user asks for fablize, codex-fablize, gpt55-fablize (legacy name), Fable-style, Fable5-style, or to make Codex work like Fable — on any Codex model, not only GPT-5.5. Applies only transferable workflow: inspect first, finish multi-step work, checkpoint evidence, investigate systematically, observe rendered artifacts, verify before done, and separate implementation from audit roles. Does not clone Clau... |
| `security-threat-model` | Repository-grounded threat modeling that enumerates trust boundaries, assets, attacker capabilities, abuse paths, and mitigations, and writes a concise Markdown threat model. Trigger only when the user explicitly asks to threat model a codebase or path, enumerate threats/abuse paths, or perform AppSec threat modeling. Do not trigger for general architecture summaries, code review, or non-security design work. |
| `security-best-practices` | Perform language and framework specific security best-practice reviews and suggest improvements. Trigger only when the user explicitly requests security best practices guidance, a security review/report, or secure-by-default coding help. Trigger only for supported languages (python, javascript/typescript, go). Do not trigger for general code review, debugging, or non-security tasks. |
| `top-down-project-learning` | Use whenever the user asks Codex to build, improve, organize, or portfolio-package a project, feature, AI/data artifact, backend/API, analysis report, or learning deliverable. Codex should implement a working draft first, then turn it into top-down study material the user can dissect, critique, modify, and explain in interviews. |
| `jupyter-notebook` | Use when the user asks to create, scaffold, or edit Jupyter notebooks (`.ipynb`) for experiments, explorations, or tutorials; prefer the bundled templates and run the helper script `new_notebook.py` to generate a clean starting notebook. |
