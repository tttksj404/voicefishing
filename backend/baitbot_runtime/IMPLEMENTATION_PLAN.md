# Baitbot runtime logging, event UI, responder tone plan

## Scope

- Persist every server-run event as local JSONL from process start until shutdown.
- Replace raw event-schema JSON with an always-visible extraction table.
- Make the baitbot primarily hesitant, passive, and compliant-sounding so the scammer keeps talking.
- Keep the existing Safety, parallel Responder/Extractor, partial-failure, and API contracts intact.

## Logging design

### Destination and format

- Directory: `backend/baitbot_runtime/logs/`
- One file per server run: `runtime_<UTC timestamp>_<run id>.jsonl`
- UTF-8, one JSON object per line, append-only for that process.
- Common fields: `timestamp`, `level`, `event`, `run_id`, `request_id`, `session_id`, `turn_id`, `operation`, `status`, `duration_ms`, `model`, `reasoning`, `details`.
- Never record `openrouter_api`, `Authorization`, or other credential values.

### Events to record

| Event | Required details |
|---|---|
| `server.started` / `server.stopped` | process ID, log path, outcome |
| `api.request.started` | request ID, method, path |
| `api.request.completed` / `api.request.failed` | status code, duration, success/failure, safe cause |
| `session.created` / `session.reset` | previous/new session ID |
| `turn.received` | exact scammer text, turn sequence |
| `safety.completed` | PASS/DEFEND, matched rule, attack type, duration |
| `provider.request.started` | responder/extractor, model, reasoning, complete message payload without credentials |
| `provider.request.completed` / `provider.request.failed` | raw provider result or safe error, duration and HTTP error code |
| `responder.completed` / `responder.fallback` | exact baitbot text, intent, end-call flag, failure reason when applicable |
| `extractor.completed` / `extractor.failed` | raw patches, applied count, failure reason |
| `event_schema.updated` | extracted patch and resulting event schema |
| `attack.recorded` | DEFEND attack event |
| `turn.completed` / `turn.partial_failure` / `turn.failed` | goal results for Safety, Responder, Extractor and overall cause |

## Event-schema UI

- Always render these eight rows: impersonated organization, requested amount, account number, phone number, URL, app/install file, instruction, threat/pressure.
- Columns: field, extraction status, extracted value, normalized value, confidence, evidence turns.
- Show `not extracted` instead of `null` or raw JSON.
- Show schema status, extractor status, and extracted-count summary above the table.
- Use semantic `table`, `thead`, `tbody`, caption/accessible labels, and a responsive overflow wrapper.
- Continue using `textContent`; never render model content with `innerHTML`.

## Responder tone

- Default stance: hesitant, confused, passive, cooperative-sounding, and delay-oriented.
- Use short Korean acknowledgements and at most one natural follow-up question.
- Encourage the scammer to repeat or elaborate without sounding like an investigator.
- Never claim money was sent, an app was installed, or a real-world action was completed.
- Do not routinely demand identity, written notice, verification, or threaten to hang up.
- Direct challenge or call-ending language is exceptional, not the main stance.
- Apply the same passive tone to provider-failure and DEFEND fallback messages.

## Implementation checklist

- [x] Add a stdlib-only JSONL event logger with one file per server run.
- [x] Add FastAPI lifecycle and request success/failure logging.
- [x] Log exact scammer and baitbot messages without logging credentials.
- [x] Log Responder/Extractor request start, completion/failure, duration, and cause.
- [x] Log extractor patches, merge count, resulting event schema, and evidence turns.
- [x] Log Safety and final per-turn goal outcomes.
- [x] Add deterministic tests proving log creation, required events, failure cause, and secret exclusion.
- [x] Replace raw event-schema `<pre>` with the eight-row accessible table.
- [x] Display extracted count, schema status, extractor status, values, confidence, and evidence.
- [x] Preserve responsive layout, loading/error feedback, and XSS-safe rendering.
- [x] Rewrite Responder prompt and fallback texts to the passive stance.
- [x] Add regression checks that routine identity demands, written-notice demands, and hang-up threats are not the default prompt/fallback.
- [x] Keep existing runtime/API tests passing.
- [x] Restart the BAT server and verify the UI in a real browser.

## Review checklist

- [x] Every required log event is present and valid JSONL.
- [x] Logs correlate run, request, session, turn, and provider operation.
- [x] Exact conversation and extraction data are recorded.
- [x] Success, partial failure, failure, duration, and safe root cause are recorded.
- [x] API keys and Authorization values never appear in logs or responses.
- [x] Concurrent Responder/Extractor entries are not corrupted or interleaved as invalid JSON.
- [x] Reset and server restart produce understandable session/run boundaries.
- [x] Event table always shows all eight planned fields and readable empty states.
- [x] Event table remains usable on a narrow viewport and with keyboard/screen-reader navigation.
- [x] Dynamic content still uses `textContent`.
- [x] Responder prompt is passive by default and retains safety/non-compliance limits.
- [x] DEFEND and provider-failure fallbacks use the same passive persona.
- [x] Existing Safety, parallel calls, evidence filtering, and partial failure behavior do not regress.
- [x] Automated checks, API checks, JavaScript syntax, and browser verification pass.
