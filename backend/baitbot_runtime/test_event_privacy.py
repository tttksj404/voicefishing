from __future__ import annotations

import contextlib
import io
import json
import os
from tempfile import TemporaryDirectory
from unittest.mock import patch

from event_log import JsonlEventLogger, _redact_pii_text


URL = "https://phish.example/login"
EMAIL = "victim@example.com"
PHONE = "010-1234-5678"
ACCOUNT = "123-456-789012"
RESIDENT_ID = "900101-1234567"
SECRET = "sk-or-v1-test-secret-value"


def _records(logger: JsonlEventLogger) -> tuple[list[dict], str]:
    rendered = logger.path.read_text(encoding="utf-8")
    return [json.loads(line) for line in rendered.splitlines()], rendered


def check_vercel_masks_nested_pii_and_streams_by_level() -> None:
    assert _redact_pii_text(f"연락 {EMAIL}로") == "연락 [REDACTED_EMAIL]로"
    details = {
        "scammer_text": f"링크 {URL}, {EMAIL}로 연락, 전화 {PHONE}, 계좌 {ACCOUNT}, 주민번호 {RESIDENT_ID}",
        "messages": [{"role": "user", "content": f"{PHONE} {EMAIL} {URL} {ACCOUNT} {RESIDENT_ID}"}],
        "event_schema": {
            "account_number": ACCOUNT,
            "phone_number": PHONE,
            "url": URL,
            "email": EMAIL,
            "resident_id": RESIDENT_ID,
            "requested_amount": "5,000,000원",
        },
        "Authorization": f"Bearer {SECRET}",
        "provider_error": f"openrouter_api={SECRET}",
    }

    with patch.dict(os.environ, {"VERCEL": "1"}, clear=False), TemporaryDirectory() as directory:
        logger = JsonlEventLogger(directory, run_id="run_privacy_check")
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                logger.log_event("provider.completed", status="completed", details=details)
                logger.log_event("provider.failed", level="ERROR", status="failed", details=details)
            records, rendered = _records(logger)
        finally:
            logger.close()

    assert len(records) == 2
    assert [record["level"] for record in records] == ["INFO", "ERROR"]
    assert len(stdout.getvalue().splitlines()) == 1
    assert len(stderr.getvalue().splitlines()) == 1
    for raw in (URL, EMAIL, PHONE, ACCOUNT, RESIDENT_ID, SECRET):
        assert raw not in rendered
    for marker in (
        "[REDACTED_URL]",
        "[REDACTED_EMAIL]",
        "[REDACTED_PHONE]",
        "[REDACTED_ACCOUNT]",
        "[REDACTED_RESIDENT_ID]",
        "[REDACTED]",
    ):
        assert marker in rendered, marker
    assert records[0]["details"]["event_schema"]["requested_amount"] == "5,000,000원"


def check_local_keeps_pii_but_redacts_secrets() -> None:
    details = {
        "scammer_text": f"{URL} {EMAIL} {PHONE} {ACCOUNT} {RESIDENT_ID}",
        "event_schema": {"account_number": ACCOUNT, "phone_number": PHONE, "url": URL},
        "Authorization": f"Bearer {SECRET}",
        "provider_error": f"openrouter_api={SECRET}",
    }

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("VERCEL", None)
        with TemporaryDirectory() as directory:
            logger = JsonlEventLogger(directory, run_id="run_local_privacy_check")
            try:
                logger.log_event("provider.completed", details=details)
                records, rendered = _records(logger)
            finally:
                logger.close()

    assert len(records) == 1
    for raw in (URL, EMAIL, PHONE, ACCOUNT, RESIDENT_ID):
        assert raw in rendered
    assert SECRET not in rendered
    assert "[REDACTED]" in rendered


def main() -> None:
    check_vercel_masks_nested_pii_and_streams_by_level()
    check_local_keeps_pii_but_redacts_secrets()
    print("test_event_privacy: PASS")


if __name__ == "__main__":
    main()
