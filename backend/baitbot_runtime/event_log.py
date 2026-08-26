"""Small, dependency-free JSONL event logger for the baitbot runtime."""

from __future__ import annotations

import contextvars
import json
import math
import os
import re
import sys
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterator, Mapping


COMMON_FIELDS = (
    "timestamp",
    "level",
    "event",
    "run_id",
    "request_id",
    "session_id",
    "turn_id",
    "operation",
    "status",
    "duration_ms",
    "model",
    "reasoning",
    "details",
)
_CONTEXT_FIELDS = COMMON_FIELDS[4:-1]
_SENSITIVE_NAMES = (
    "apikey",
    "authorization",
    "credential",
    "password",
    "passwd",
    "secret",
    "token",
    "openrouterapi",
)
_SECRET_ASSIGNMENT = re.compile(
    r"""(?ix)
    [\"']?(?:api[_\s-]?key|openrouter_api|authorization|credentials?|password|passwd|secret|token)[\"']?
    \s*[:=]\s*[\"']?(?:bearer\s+)?[^,\s;}\]\"']+
    """
)
_BEARER_TOKEN = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_API_TOKEN = re.compile(r"\b(?:sk-or-v1-[A-Za-z0-9_-]+|sk-[A-Za-z0-9_-]{8,})\b")
# ponytail: pattern-based PII masking keeps the deployment safe with no new
# dependency; add provider-specific formats or field markers when new schemas appear.
_PII_FIELD_MARKERS = {
    "account": "[REDACTED_ACCOUNT]",
    "accountnumber": "[REDACTED_ACCOUNT]",
    "bankaccount": "[REDACTED_ACCOUNT]",
    "bankaccountnumber": "[REDACTED_ACCOUNT]",
    "recipientaccount": "[REDACTED_ACCOUNT]",
    "destinationaccount": "[REDACTED_ACCOUNT]",
    "iban": "[REDACTED_ACCOUNT]",
    "phone": "[REDACTED_PHONE]",
    "phonenumber": "[REDACTED_PHONE]",
    "mobile": "[REDACTED_PHONE]",
    "mobilenumber": "[REDACTED_PHONE]",
    "telephone": "[REDACTED_PHONE]",
    "tel": "[REDACTED_PHONE]",
    "contactnumber": "[REDACTED_PHONE]",
    "url": "[REDACTED_URL]",
    "weburl": "[REDACTED_URL]",
    "website": "[REDACTED_URL]",
    "link": "[REDACTED_URL]",
    "email": "[REDACTED_EMAIL]",
    "emailaddress": "[REDACTED_EMAIL]",
    "residentid": "[REDACTED_RESIDENT_ID]",
    "residentregistrationnumber": "[REDACTED_RESIDENT_ID]",
    "rrn": "[REDACTED_RESIDENT_ID]",
    "jumin": "[REDACTED_RESIDENT_ID]",
    "cardnumber": "[REDACTED_CARD]",
    "creditcardnumber": "[REDACTED_CARD]",
    "debitcardnumber": "[REDACTED_CARD]",
}
_URL = re.compile(r"(?i)(?<![\w@])(?:https?://|www\.)[^\s<>\"'`]+")
_EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9._%+-])"
)
_RESIDENT_ID = re.compile(r"(?<!\d)\d{6}[- ]?[1-4]\d{6}(?!\d)")
_PHONE = re.compile(
    r"(?<!\d)(?:"
    r"\+?82[- .]?10[- .]?\d{4}[- .]?\d{4}|"
    r"01[016789][- .]?\d{3,4}[- .]?\d{4}|"
    r"0(?:2|[3-6]\d|70|80)[- .]?\d{3,4}[- .]?\d{4}|"
    r"1[568]\d{2}[- .]?\d{4}"
    r")(?!\d)"
)
_ACCOUNT_SEPARATED = re.compile(r"(?<!\d)\d{2,6}(?:-\d{2,6}){2,5}(?!\d)")
_ACCOUNT_CONTIGUOUS = re.compile(r"(?<!\d)\d{12,16}(?!\d)")
_LOG_CONTEXT: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "baitbot_event_context", default={}
)
_GLOBAL_LOGGER_LOCK = threading.Lock()
_MISSING = object()


def _is_sensitive_key(key: object) -> bool:
    if not isinstance(key, str):
        return True
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return normalized == "key" or any(name in normalized for name in _SENSITIVE_NAMES)


def _redact_inline_secret(value: str) -> str:
    value = _SECRET_ASSIGNMENT.sub("[REDACTED]", value)
    value = _BEARER_TOKEN.sub("[REDACTED]", value)
    return _API_TOKEN.sub("[REDACTED]", value)


def _pii_marker_for_key(key: object) -> str | None:
    if not isinstance(key, str):
        return None
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return _PII_FIELD_MARKERS.get(normalized)


def _redact_pii_text(value: str) -> str:
    value = _URL.sub("[REDACTED_URL]", value)
    value = _EMAIL.sub("[REDACTED_EMAIL]", value)
    value = _RESIDENT_ID.sub("[REDACTED_RESIDENT_ID]", value)
    value = _PHONE.sub("[REDACTED_PHONE]", value)

    def redact_account(match: re.Match[str]) -> str:
        return "[REDACTED_ACCOUNT]" if len(match.group(0).replace("-", "")) >= 10 else match.group(0)

    value = _ACCOUNT_SEPARATED.sub(redact_account, value)
    return _ACCOUNT_CONTIGUOUS.sub("[REDACTED_ACCOUNT]", value)


def _safe_value(value: Any, *, mask_pii: bool = False, field_name: object = None) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        safe = _redact_inline_secret(value)
        if mask_pii:
            marker = _pii_marker_for_key(field_name)
            if marker and safe.strip():
                return marker
            return _redact_pii_text(safe)
        return safe
    if isinstance(value, int):
        if mask_pii and _pii_marker_for_key(field_name):
            return _pii_marker_for_key(field_name)
        return value
    if isinstance(value, float):
        if mask_pii and _pii_marker_for_key(field_name):
            return _pii_marker_for_key(field_name)
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        safe_mapping: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or _is_sensitive_key(key):
                continue
            marker = _pii_marker_for_key(key) if mask_pii else None
            if marker and item is not None and not isinstance(item, (Mapping, list, tuple, set, frozenset)):
                safe_mapping[key] = marker
            else:
                safe_mapping[key] = _safe_value(item, mask_pii=mask_pii, field_name=key)
        return safe_mapping
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_safe_value(item, mask_pii=mask_pii) for item in value]
    return f"<{type(value).__name__}>"


@contextmanager
def bind_event_context(**fields: Any) -> Iterator[None]:
    """Temporarily bind correlation fields to events in this async context."""

    current = _LOG_CONTEXT.get()
    merged = {
        **current,
        **{name: value for name, value in fields.items() if name in _CONTEXT_FIELDS},
    }
    token = _LOG_CONTEXT.set(merged)
    try:
        yield
    finally:
        _LOG_CONTEXT.reset(token)


class JsonlEventLogger:
    """Append complete JSON objects under a lock so concurrent events never interleave."""

    def __init__(self, log_dir: str | Path | None = None, *, run_id: str | None = None) -> None:
        self._vercel = bool(os.getenv("VERCEL"))
        directory = Path(log_dir) if log_dir is not None else (
            Path("/tmp/baitbot_runtime/logs") if self._vercel else Path(__file__).with_name("logs")
        )
        directory.mkdir(parents=True, exist_ok=True)
        self._mirror_to_stdout = self._vercel
        self.run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        self.path = directory / f"runtime_{timestamp}_{self.run_id}.jsonl"
        self._file = self.path.open("a", encoding="utf-8", newline="\n")
        self._lock = threading.Lock()

    def log_event(self, event: str, *, level: str = "INFO", **fields: Any) -> None:
        context = _LOG_CONTEXT.get()
        details: dict[str, Any] = {}
        supplied_details = fields.pop("details", None)
        if isinstance(supplied_details, Mapping):
            details.update(_safe_value(supplied_details, mask_pii=self._vercel))
        elif supplied_details is not None:
            details["value"] = _safe_value(supplied_details, mask_pii=self._vercel)

        record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": level.upper() if isinstance(level, str) else "INFO",
            "event": _safe_value(
                event if isinstance(event, str) else type(event).__name__,
                mask_pii=self._vercel,
            ),
            "run_id": self.run_id,
        }
        for name in _CONTEXT_FIELDS:
            value = fields.pop(name, _MISSING)
            if value is _MISSING:
                value = context.get(name)
            record[name] = _safe_value(value, mask_pii=self._vercel, field_name=name)

        for name, value in fields.items():
            if not _is_sensitive_key(name):
                details[name] = _safe_value(value, mask_pii=self._vercel, field_name=name)
        record["details"] = details

        payload = json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        with self._lock:
            self._file.write(f"{payload}\n")
            self._file.flush()
            if self._mirror_to_stdout:
                stream = sys.stderr if record["level"] in {"ERROR", "FATAL"} else sys.stdout
                print(payload, file=stream, flush=True)

    def flush(self) -> None:
        with self._lock:
            self._file.flush()

    def close(self) -> None:
        with self._lock:
            self._file.close()


_GLOBAL_LOGGER: JsonlEventLogger | None = None


def _logger() -> JsonlEventLogger:
    global _GLOBAL_LOGGER
    if _GLOBAL_LOGGER is None:
        with _GLOBAL_LOGGER_LOCK:
            if _GLOBAL_LOGGER is None:
                _GLOBAL_LOGGER = JsonlEventLogger()
    return _GLOBAL_LOGGER


def log_event(event: str, *, level: str = "INFO", **fields: Any) -> None:
    """Write one safe event. Extra fields are kept below ``details``."""

    try:
        _logger().log_event(event, level=level, **fields)
    except Exception:
        # Logging must not change the caller's API or turn outcome.
        pass


def get_log_path() -> Path:
    """Return the active process log path, creating it on first use."""

    return _logger().path


def get_run_id() -> str:
    """Return the active process correlation id, creating it on first use."""

    return _logger().run_id


def flush_log() -> None:
    try:
        _logger().flush()
    except Exception:
        pass


def _self_check() -> None:
    with TemporaryDirectory() as temporary_directory:
        logger = JsonlEventLogger(temporary_directory, run_id="run_check")
        try:
            logger.log_event(
                "check.event",
                request_id="request_check",
                session_id="session_check",
                turn_id="turn_0001",
                operation="responder",
                status="completed",
                duration_ms=1.25,
                model="test/model",
                reasoning="low",
                method="POST",
                openrouter_api="must-not-appear",
                details={
                    "Authorization": "Bearer must-not-appear",
                    "nested": {"credential": "must-not-appear"},
                    "inline": "openrouter_api=must-not-appear",
                },
            )
            records = [json.loads(line) for line in logger.path.read_text(encoding="utf-8").splitlines()]
            assert len(records) == 1
            assert all(name in records[0] for name in COMMON_FIELDS)
            rendered = logger.path.read_text(encoding="utf-8")
            assert "openrouter_api" not in rendered
            assert "Authorization" not in rendered
            assert "must-not-appear" not in rendered
        finally:
            logger.close()


if __name__ == "__main__":
    _self_check()
    print("event_log self-check: PASS")
