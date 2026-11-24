# voicefishing

합성·비식별 데이터만 사용하는 보이스피싱 방어 시뮬레이터입니다. 실제 통화,
실제 전화번호, 계정·금융정보, 사용자 음성 복제, 은닉 봇 전환을 구현하거나 테스트하지
않습니다.

## 현재 구현 범위

- `start`: 처음부터 시작하는 공개형 합성 대화 세션
- `handoff`: 사용자가 넘긴 뒤 `CASE-…` 형식의 비식별 표식만 이어받는 중간 전환 세션
- 입력 PII 차단: 휴대전화·주민등록번호·계좌 형태 문자열은 대화 기록 전에 차단
- 출력 제한: 상대가 안다고 주장하는 정보의 **범주**만 남기고 실제 값·요청 문구는 출력하지 않음
- 감사용 해시: 발화 원문·표식과 독립된 모드/범주 기반 digest만 반환

이 저장소는 실제 사기 행위를 수행하는 ‘무검열’ 모델을 제공하지 않습니다. 미끼봇의
안전성은 합성 표식과 범주 수준의 주장으로 검증해야 하며, 실제 개인정보를 넣으면
세션을 실패 종료합니다.

## Notion 맥락과의 연결

Notion의 Sentinel-30 범위를 따라 실제 전화망·SIP·통신사·원격 계정과 연결하지 않고,
`FROM_START`와 `MID_CALL_HANDOFF`의 상태 계약만 재현합니다. Qwen2.5-0.5B-Instruct
Q8 GGUF는 해당 문서의 현재 CPU 기준선이지만, 이 저장소에서는 생성 모델을 사기 역할로
쓰지 않습니다.

## 실행

```powershell
uv sync --group dev
uv run voicefishing start --message "합성 훈련을 시작합니다." --category contact
uv run voicefishing handoff --message "이전 맥락을 이어갑니다." --category name --marker CASE-ALPHA-7
```

실제 형태의 개인정보를 전달하면 `blocked=sensitive_input`만 출력됩니다.

## 로컬 Qwen 워크벤치

이 체크아웃의 기본 실행 경로는 실제로 확인한 CUDA 실행기와 Qwen3 8B Q4 모델입니다.

```text
.tools\llama-b10621-bin-win-cuda-12.4-x64\llama-cli.exe
.tools\models\Qwen3-8B-Q4_K_M.gguf
```

두 파일이 함께 존재하면 워크벤치는 `-ngl 99`로 GPU 레이어를 오프로딩하고 Qwen3의
생각 토큰을 끕니다. CUDA 번들이 없거나 모델 파일이 없으면 기존 CPU 기준선
`qwen2.5-0.5b-instruct-q8_0.gguf`로 자동 폴백하므로, 경로가 깨진 상태로 실행하지
않습니다.

브라우저 기반 3패널 워크벤치를 시작하려면 다음을 실행한 뒤
`http://127.0.0.1:8765`를 여세요.

```powershell
uv sync --group dev
uv run voicefishing workbench
```

다른 포트가 필요하면 `uv run voicefishing workbench --port 8877`을 사용합니다.
서버는 `127.0.0.1`에만 바인딩하며, 프롬프트와 응답을 브라우저 저장소나 파일에
보관하지 않습니다. 각 실행은 확인된 `llama-cli.exe`로 GGUF를 직접 로드하므로, 첫
응답 전 로드 시간이 포함됩니다.

## 로컬 GGUF 상태 점검

Qwen GGUF와 `llama-cli.exe`가 이미 있는 경우, 아래 명령은 단 하나의 안전 토큰만
생성해 모델 로드부터 첫 응답까지의 시간을 측정합니다. 사기 문장·실제 기관명·개인정보는
프롬프트와 출력에 포함하지 않습니다.

```powershell
uv run python scripts/local_gguf_probe.py `
  --runner ".tools\llama-b10621-bin-win-cuda-12.4-x64\llama-cli.exe" `
  --model ".tools\models\Qwen3-8B-Q4_K_M.gguf" `
  --gpu-layers 99 `
  --no-thinking
```

성공 기준은 `LOCAL_GGUF_PROBE=PASS`입니다. 표준 출력에는 모델 원문을 남기지 않고,
성공 여부·첫 응답 시간·해시만 남깁니다. 이 결과는 모델이 사기 역할을 잘한다는 주장이
아니라, 안전한 합성 시뮬레이터의 로컬 추론 경로가 준비됐다는 신호입니다.

## 검증

```powershell
uv run pytest -q
uv run ruff format --check .
uv run ruff check .
uv run basedpyright
```

## 경험 기록

이 프로젝트를 왜 시작했는지, 무엇을 직접 판단했는지, 결과가 어땠는지는 [docs/experience-record.md](docs/experience-record.md)에 정리했습니다.
