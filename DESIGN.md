# Local Qwen Workbench Design System

## 0. Research Log

- Embedded refs: shortlisted `warp.md`, `ollama.md`, and `cursor.md` for a local-model IDE; picked `minimalist-skill.md` + `warp.md` because the IDE needs a warm, low-noise terminal surface rather than a neon AI editor. Added `layout-skill.md` for the fixed app shell and `interaction-skill.md` for explicit async action states.
- Lazyweb: ran 2 desktop queries and viewed 2 shipped screens (Zed documentation and Termius Local Terminal); took the persistent left rail, readable central work area, and calm dark command framing, not their pixels or brand assets.
- Imagen drafts: generated two local concepts (kept outside this repository); picked the second for its quiet three-pane operational hierarchy.
- Open Design: attempted again on 2026-08-26; its local daemon at `127.0.0.1:7456` is unavailable, so the documented local design system remains the implementation source of truth.

## 1. Atmosphere & Identity

Local Qwen IDE is a quiet command center for the verified Qwen3 8B CUDA runtime. It should feel more like opening a carefully maintained developer utility than visiting an AI product: warm graphite, parchment text, clear evidence, and only one meaningful color cue at a time. Its signature is the **local execution receipt**: every Qwen request ends in a compact, readable runtime record instead of a history feed or decorative dashboard.

## 2. Color

| Role | Token | Value | Usage |
|---|---|---:|---|
| Canvas | `--canvas` | `#181816` | App background |
| Surface primary | `--surface-primary` | `#201f1d` | Main work area |
| Surface secondary | `--surface-secondary` | `#292824` | Rails and editor wells |
| Surface elevated | `--surface-elevated` | `#33312c` | Pressed or selected control |
| Text primary | `--text-primary` | `#faf9f6` | Headings and active values |
| Text secondary | `--text-secondary` | `#c5c2ba` | Body copy and output |
| Text tertiary | `--text-tertiary` | `#918e87` | Labels and metadata |
| Border default | `--border-default` | `rgba(226, 226, 226, 0.24)` | Pane division and controls |
| Border subtle | `--border-subtle` | `rgba(250, 249, 246, 0.08)` | Internal dividers |
| Accent | `--accent-primary` | `#73a9bf` | Run action, focus, neutral information |
| Accent hover | `--accent-hover` | `#8dbdcc` | Run action hover |
| Verified | `--status-success` | `#88b77a` | Local runner/model pass only |
| Caution | `--status-warning` | `#d5a35d` | Safe-mode limitation |
| Error | `--status-error` | `#d77368` | Blocked or failed execution |

Accent color is reserved for interaction and semantic status; it is never a decorative background. Purple, neon glow, gradients, and pure-white text are prohibited.

## 3. Typography

| Level | Token | Size / Line height | Usage |
|---|---|---:|---|
| Display | `--type-display` | `20px / 1.2` | Workbench name |
| Section | `--type-section` | `16px / 1.3` | Pane titles |
| Body | `--type-body` | `14px / 1.5` | Instructions and model output |
| Meta | `--type-meta` | `12px / 1.4` | Labels, paths, runtime receipts |
| Code | `--type-code` | `13px / 1.55` | Prompt, paths, log data |

Use `"Segoe UI Variable", "Noto Sans KR", sans-serif` for UI text: this is an intentional Windows-local utility choice. Use `"Cascadia Mono", "JetBrains Mono", monospace` only for prompts, paths, digests, and log values. No default Inter/Geist dependency is loaded.

## 4. Spacing & Layout

All intentional spacing uses the 4px scale: `--space-1: 4px`, `--space-2: 8px`, `--space-3: 12px`, `--space-4: 16px`, `--space-5: 20px`, `--space-6: 24px`, `--space-8: 32px`.

Desktop uses a `fixed-sidenav-shell`: a fixed header and footer, a narrow workspace-file rail, a fluid file editor, and a Qwen assistant inspector. The file list, editor, and assistant each have a named scroll responsibility; the page shell never becomes a competing desktop scroll container. At 1024px the assistant moves below the editor; at 768px the file rail becomes a compact overview; at 375px all regions become one readable column with no horizontal scroll. Long paths, source lines, and model output use `overflow-wrap: anywhere`.

## 5. Components

### IDE shell
- **Structure**: status header / workspace-file rail / file editor / Qwen assistant inspector / runtime footer.
- **Layout**: `fixed-sidenav-shell`; the file list, editor, and assistant own only their respective scroll regions.
- **States**: ready, unavailable, loading file, dirty file, saving, running Qwen, blocked, failed.
- **Accessibility**: semantic landmarks, visual status text in addition to color, logical tab order.

### Workspace file navigator
- **Structure**: text-file list, active-file label, and local-scope explanation.
- **Data boundary**: lists and opens only existing project-relative UTF-8 text files with an allowed extension; hidden tool, cache, virtual-environment, model, and Git directories are excluded.
- **States**: loading, empty, active, unavailable.
- **Accessibility**: each item is a native button with `aria-current` for the active file; long paths truncate visually but retain their full accessible name.

### File editor
- **Structure**: current project-relative path, dirty/save state, line-number gutter, editable code textarea, explicit Save action.
- **Data boundary**: the editor never executes code or commands. It writes only the active, pre-existing safe text file after the user activates Save.
- **States**: loading, clean, dirty, saving, saved, save failed.
- **Accessibility**: a labelled textarea, visible save status, `Ctrl+S` shortcut that supplements the button, and a stable focus target after save.

### Qwen assistant panel
- **Structure**: concise request editor, optional bounded active-file context, local response, copy control, and execution receipt.
- **Data boundary**: selected editor text is truncated before inclusion in the request; the assistant cannot apply or save its own response. The user reviews and saves any change explicitly.
- **States**: empty, running, complete, blocked, failed.
- **Accessibility**: the response and receipt use text labels and `aria-live`; a blocked request never echoes the submitted text.

### Status marker
- **Structure**: text label with a small non-decorative indicator.
- **Variants**: verified, caution, unavailable, running, blocked.
- **States**: status is always readable as text; color is secondary.
- **Accessibility**: `aria-live="polite"` for state changes.

### Command button
- **Structure**: SVG action glyph plus label and shortcut hint.
- **Variants**: primary Qwen request or save, quiet secondary, clear, and copy.
- **States**: default, hover, active, focus-visible, disabled, loading, success, error.
- **Motion**: adapts the beui StatefulButton mechanism: an action label changes only for a real state transition and uses 120ms opacity/background/transform feedback; reduced motion removes transform.
- **Accessibility**: native button semantics, minimum 40px target, keyboard reachable.

### Evidence row
- **Structure**: runner/model availability, elapsed time, and completion digest.
- **States**: absent before first execution, verified after a successful completion.
- **Accessibility**: no metric is color-only; long data wraps rather than truncates silently.

## 6. Motion & Interaction

`--motion-micro` is `120ms ease-out`; `--motion-standard` is `200ms cubic-bezier(0.16, 1, 0.3, 1)`. Save and Qwen actions follow the beui StatefulButton mechanism conceptually: they have explicit idle, loading, success, and error labels, and transition only when execution state changes. CSS animates only `transform` and `opacity`; no decorative card hovers, scroll reveals, or background motion are allowed. `prefers-reduced-motion: reduce` disables transform-based feedback.

## 7. Depth & Surface

Use a mixed tonal-shift and 1px-border strategy. Panes are separated through `--surface-*` shifts and `--border-*`; there are no drop shadows, glass blur, glow, or gradient surfaces. Radius is role-specific: 4px controls, 6px fields, 8px bounded editors/panes, never an indiscriminate pill treatment. Small status markers may be rounded because they are compact semantic labels.

## 8. Accessibility Constraints & Accepted Debt

- Target WCAG 2.2 AA: body contrast at least 4.5:1, visible keyboard focus, semantic landmarks, and text labels in addition to status color.
- Preserve Korean and English path/code readability; use a dedicated mono stack only where scanning data benefits.
- `Ctrl+Enter` and `Ctrl+S` supplement but never replace visible Qwen and Save buttons.
- The IDE permits no browser persistence, arbitrary shell, code execution, directory creation, or automatic assistant-to-file write.
- Reduced motion, 200% zoom, long unbroken paths, empty file list, dirty/save status, blocked Qwen output, and small-screen reflow are required QA states.

| Item | Location | Why accepted | Owner / Exit |
|---|---|---|---|
| None | — | No accessibility or design debt accepted for this initial surface. | — |
