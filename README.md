# 목소리 기록실 · Voice Archive

타운홀 미팅, 회의, 현장 발언을 위한 **개인용 로컬 웹앱**입니다. Windows PC에서 실행하고 브라우저로 사용합니다. 파일·데이터베이스와 AI 추론은 로컬에 남습니다. ChatGPT를 통한 사전 자료 분석은 사용자가 별도로 수행하는 선택 단계입니다.

## 제공하는 기능

- MP3/WAV 및 M4A·FLAC·OGG·MP4 업로드, 실제 오디오 검사 (파일당 최대 4GB·24시간)
- ChatGPT 분석 프롬프트 복사 → 분석 결과 붙여넣기 → 인식용 용어 확인·저장
- 로컬 `large-v3` + `faster-whisper`, 한국어·FP16·beam size 5 기본값
- 5분 단위 체크포인트, 앞뒤 2초 문맥, 단어 중간 시점 기준 구간 배정, 재시작 시 중단 구간부터 재개
- 원본 음성 재생, 발언 시간 탐색, 배속·구간 반복, 실제 음성에서 계산한 파형
- 자동 녹취 원문 보존, 편집본·검토 상태·수정 이력, 화자 이름·발언별 화자 지정
- 선택적 로컬 pyannote 화자 구분 어댑터 (별도 설치 필요)
- 로컬 Ollama를 통한 요약·시장님 주요 발언·정리본·기사·보고서 초안. 기본값은 검토 완료 발언만 사용
- 생성 결과의 원문 시간 연결, 변경된 녹취에 기반한 오래된 초안 표시·내보내기 차단
- UTF-8 TXT, 한글 글꼴을 포함한 PDF, 원본·SQLite 데이터 전체 백업 ZIP

## Windows 11 설치

권장 대상: Ryzen 7 3700X, RAM 16GB, RTX 2070 SUPER 8GB. GPU 메모리를 줄이기 위해 음성인식·화자 구분·문서 생성 작업은 한 작업 처리기에서 순차 실행합니다. 그래픽 드라이버와 다른 실행 프로그램에 따라 실제 사용 가능한 메모리가 달라집니다.

1. 최신 NVIDIA 드라이버와 **Python 3.12 (64비트)**를 설치합니다. Python Launcher(`py`)도 설치하세요.
2. FFmpeg를 설치합니다. `winget install --id Gyan.FFmpeg --exact` 또는 신뢰할 수 있는 FFmpeg 배포본을 사용합니다. 새 터미널에서 `ffmpeg -version`, `ffprobe -version`을 확인합니다.
3. 문서 생성을 위해 [Ollama Windows](https://ollama.com/download/windows)를 설치하고 실행합니다.
4. 프로젝트 폴더에서 PowerShell을 열어 실행합니다.

```powershell
.\scripts\install.ps1
.\.venv\Scripts\python.exe scripts\download_model.py
ollama pull qwen3:8b
.\start.bat
```

PowerShell 실행 정책으로 스크립트를 실행할 수 없다면 정책 변경 없이 다음 개별 명령을 사용해도 됩니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-ai.txt
.\.venv\Scripts\python.exe scripts\download_model.py
ollama pull qwen3:8b
.\start.bat
```

모델 설치는 수 GB를 다운로드하므로 인터넷과 디스크 여유 공간이 필요합니다. Whisper 모델은 Hugging Face의 `Systran/faster-whisper-large-v3`에서 TLS 검증을 유지해 받습니다. 특정 검증된 버전으로 고정하려면 `download_model.py --revision <커밋 SHA>`를 사용하세요. 다운로드한 파일은 이후 재사용됩니다. Ollama `qwen3:8b`는 초기 평가용 기본값이며, 최종 한국어 품질을 보장하는 모델 선정 결과는 아닙니다.

앱은 **127.0.0.1:8765**에만 바인딩하며 브라우저가 자동으로 열립니다. 공유기 포트 개방이나 별도 서버 장비는 필요하지 않습니다. 종료하려면 실행 창에서 `Ctrl+C`를 누르세요. 실행 창을 닫으면 진행 중인 작업이 중단되며 완료한 구간은 보존됩니다. 브라우저만 닫으면 앱 프로세스는 계속 실행됩니다.

### start.bat 실행 오류

ZIP 전체를 먼저 압축 해제한 뒤, `start.bat`과 `scripts` 폴더가 함께 있는 위치에서 실행하세요. ZIP 안에서 배치 파일만 바로 실행하면 필요한 파일을 찾을 수 없습니다.

배치 파일에서 `'f' is not recognized` 같은 잘린 명령 오류가 발생했던 구버전은 최신 `start.bat`으로 교체하세요. 현재 실행 파일은 영문 ASCII와 Windows CRLF 줄바꿈을 사용하며, GitHub ZIP에도 같은 바이트가 보존되도록 설정했습니다. `Python environment not found` 메시지가 나오면 위의 최초 설치를 먼저 진행해야 합니다.

배치 파일을 거치지 않으려면 압축 해제한 프로젝트 폴더에서 PowerShell을 열고 직접 실행할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe .\scripts\run.py
```

## 처음 사용할 때

1. 환경 설정에서 FFmpeg, Whisper 패키지·모델, Ollama 연결·선택 모델 상태를 확인합니다.
2. 1~2분의 실제 녹음 파일로 음성인식과 재생을 먼저 시험합니다.
3. ChatGPT 새 대화에 사전 자료와 앱의 프롬프트를 제공합니다. HWP를 읽지 못하면 PDF로 변환해 첨부합니다.
4. ChatGPT 답변을 확인한 뒤 앱의 사전 참고정보에 붙여넣습니다. ‘8번 구역에서 가져오기’로 용어를 추출하고 편집·저장합니다.
5. 음성인식을 실행합니다. 이름·숫자·부정 표현·겹치는 발언을 우선 확인하고 화자를 지정합니다.
6. 편집란에서 다른 곳으로 이동하면 자동 저장됩니다. 저장됨 표시를 확인하고 검토 완료로 표시하세요.
7. Ollama를 실행한 상태에서 발언·초안 탭을 사용합니다. 결과물은 편집 녹취를 변경하지 않습니다.

음성인식 이후 사전 자료를 수정해도 이미 만들어진 녹취는 바뀌지 않습니다. 전체 재인식이 필요하면 같은 원본을 새로운 녹음으로 추가하세요. 일시 중지 후 용어를 바꾸면 **아직 처리하지 않은 구간부터** 적용됩니다.

## 화자 구분의 범위

기본 설치에는 수동 화자 지정이 포함됩니다. 자동 화자 구분은 **설치·검증이 필요한 선택 기능**입니다. 공개 모델마다 이용 조건 및 최초 다운로드 접근 권한이 다를 수 있으므로, 자동 다운로드하거나 토큰을 파일에 저장하지 않습니다.

사용하려면 다음처럼 선택 의존성과 모델을 준비합니다. 먼저 Hugging Face의 `pyannote/speaker-diarization-community-1` 모델 페이지에서 이용 조건에 동의하고, **본인 PC 터미널에서만** Hugging Face 로그인을 진행합니다. 토큰을 채팅이나 앱의 참고정보에 붙여넣지 마세요.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-diarization.txt
.\.venv\Scripts\hf.exe auth login
.\.venv\Scripts\python.exe scripts\download_diarization.py
```

환경 설정의 화자 구분 모델에 다운로드된 `models/speaker-diarization-community-1`의 전체 경로를 지정하세요. 선택한 파이프라인과 하위 모델의 모든 가중치가 로컬에 있어야 합니다. 코드는 `HF_HUB_OFFLINE=1`과 원격 측정 비활성화 상태에서 파이프라인을 불러옵니다. 필수 캐시가 없으면 화자 구분 실패를 표시하고 이미 추출한 녹취는 보존합니다. pyannote 3.x/4.x의 출력 형태를 처리하는 어댑터가 있지만, **특정 모델·Windows 조합의 실행은 별도 검증 대상**입니다. 관련 패키지의 Torch 호환성을 확인하세요. 파이프라인은 CPU에서 실행하며, 미리 디코딩한 PCM을 전달해 Windows 오디오 디코더 문제를 줄입니다.

화자 식별 결과는 익명 화자이며 실제 인물을 자동 인증하지 않습니다. 동시에 여러 명이 말하는 구간은 수동 검토해야 합니다. 검토 완료했거나 이미 편집한 발언의 화자 지정은 자동 구분이 덮어쓰지 않습니다.

## 품질과 현재 한계

- 실제 사용자 녹음으로 Whisper와 Qwen3-ASR을 비교하지 않았습니다. 현재 구현된 인식 엔진은 Whisper이며, Qwen3-ASR은 검토 후보입니다.
- 자동 녹취는 완전한 축어록을 보장하지 않으며 추임새·반복을 생략하거나 없는 문장을 만들 수 있습니다. 원본 음성을 최종 근거로 확인하세요.
- 구간 경계는 단어 시점을 이용해 중복을 줄이지만 경계 인식 차이로 누락·중복이 발생할 수 있어 별도로 표시합니다. 품질 평가는 사람의 정답과 대조해야 합니다.
- 추론 신뢰도 기반 표시는 검토 우선순위 힌트이며 정확도 백분율이 아닙니다.
- 로컬 언어 모델은 입력 분량 제한으로 긴 녹취를 구간별로 정리합니다. 긴 기사의 일관성과 중복은 최종 편집이 필요합니다. 참고정보는 앞 6,000자를 모델에 제공하므로 중요한 내용을 앞쪽에 두세요.
- 원문 ID의 유효성을 검증하지만, ID가 유효하다고 내용의 사실성이 보장되지는 않습니다. 생성된 문장은 원문과 대조해야 합니다.
- 클라우드의 API·UI·FFmpeg·PDF 검증과 사용자 Windows/GPU에서의 실제 대형 모델 추론 검증은 별개입니다. 실행되지 않은 모델 검사를 통과로 간주하지 않습니다.

## 데이터·백업·복원

기본 저장 위치는 프로젝트의 `data/`입니다. 변경하려면 시작 전에 `VOICE_ARCHIVE_DATA` 환경 변수를 설정하세요. 모델 경로는 앱 설정에서 별도로 지정합니다. 원본 파일·참고정보·녹취·수정 이력은 Git에 포함되지 않습니다.

환경 설정의 ‘녹음·기록 전체 백업’은 원본과 일관된 SQLite 스냅샷을 포함합니다. 진행 중인 음성인식은 멈춘 뒤 백업하세요. 모델과 임시 오디오는 제외됩니다. 큰 백업은 브라우저 메모리를 사용하므로 여러 GB의 자료는 앱을 종료한 후 `data/` 폴더를 파일 탐색기로 다른 디스크에 복사하는 방법을 권장합니다.

복원은 앱을 종료하고 기존 `data/`를 먼저 별도 보관한 뒤, ZIP의 `data/` 폴더를 복사합니다. 저장 위치가 바뀌었다면 다음을 실행하고 모델 경로도 확인하세요.

```powershell
.\.venv\Scripts\python.exe scripts\restore_paths.py
```

## 개발·검증 (Linux/cloud)

```bash
bash scripts/setup.sh
.venv/bin/python scripts/run.py --no-browser
```

FFmpeg와 FFprobe가 필요합니다. 개발 의존성에는 음성인식 실행 패키지가 포함되지만, 대형 음성 모델 가중치와 NVIDIA GPU 라이브러리는 포함하지 않습니다. 프런트엔드는 외부 CDN이나 빌드 없이 제공하는 HTML/CSS/JavaScript이며 모든 글꼴은 로컬 파일입니다.

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/browser_smoke.py
```

브라우저 스모크 테스트는 `chromium` 실행 파일 또는 `CHROMIUM_PATH`를 사용합니다. 실제 WAV 업로드·편집·원문 보존·내보내기·모바일 레이아웃을 확인합니다. 테스트용 녹취는 명시적 fixture이며 음성인식 성공으로 계산하지 않습니다.

## 외부 의존성과 라이선스

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [Whisper](https://github.com/openai/whisper)
- [Ollama](https://ollama.com), 선택하는 각 모델의 이용 조건 확인 필요
- Nanum Gothic: SIL Open Font License, `app/static/fonts/OFL.txt`. PDF에 글꼴을 포함합니다.

앱 자체는 외부 API나 원격 모델 서버에 연결하지 않습니다. 설치·모델 다운로드는 명시적 별도 단계입니다. 로컬 앱의 요청은 같은 출처로 제한하고 변경 요청에 전용 헤더를 요구합니다. 이 앱은 공개 인터넷에 배포하기 위한 인증·다중 사용자 서비스가 아닙니다.
