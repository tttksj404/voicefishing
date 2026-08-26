# Baitbot runtime

PowerShell에서 실행합니다.

```powershell
Set-Location C:\Users\SSAFY\Desktop\VoicePhishing
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\baitbot_runtime\requirements.txt
python -m uvicorn backend.baitbot_runtime.app:app --reload
```

브라우저에서 `http://127.0.0.1:8000/`을 엽니다. 서버는
`C:\Users\SSAFY\Desktop\.env`의 `openrouter_api`를 읽고, 기본 모델은
`openrouter/stealth-ox-alpha`, 추론 수준은 `low`입니다. 기본값은
`OPENROUTER_MODEL`, `OPENROUTER_REASONING_EFFORT`로 바꿀 수 있습니다.

서버 실행마다 `backend\baitbot_runtime\logs\runtime_<UTC timestamp>_<run id>.jsonl`에
JSONL 이벤트 로그가 생성됩니다. 로그에는 API 키, Authorization 헤더, 자격증명 값을
넣지 마세요. 요청 본문은 미들웨어가 기록하지 않습니다.

실제 API 호출 없이 최소 점검을 실행하려면 다음을 사용합니다.

```powershell
python backend\baitbot_runtime\event_log.py
python backend\baitbot_runtime\test_runtime.py
```
