# 검증 내역

검증 날짜: 2026-10-11. 환경: Linux, Python 3.12, Chromium, FFmpeg. 사용자 Windows PC에 원격 접속해 검증한 결과가 아닙니다.

## 통과

- `bash scripts/setup.sh`: 의존성 설치와 테스트 실행 성공. 기존 가상환경에서 다시 실행 가능함을 확인.
- `python -m pytest -q`: **23개 통과**.
- `python scripts/browser_smoke.py`: 실제 Chromium 브라우저 검증 통과, JavaScript 페이지 오류 없음.
- `node --check app/static/app.js`: JavaScript 문법 검사 통과.
- 실제 서버 시작, 홈페이지 HTTP 200, 상태 API, 비어 있는 실제 녹음 보관함 확인.
- `faster-whisper==1.2.1`, `ctranslate2==4.6.0` 실제 import와 CPU 연산 방식 조회 성공. 로컬 모델 전용 로딩 인자와 VAD 설정 호환성 확인.
- NVIDIA cuBLAS/cuDNN과 CTranslate2 고정 버전의 Windows x64/Python 3.12용 배포 파일 존재 확인. 설치 실행 성공을 뜻하지는 않음.

## 검증한 기능

- 실제 WAV 업로드·FFprobe 검사, 잘못된 오디오 거부와 정리, 오디오 부분 요청(HTTP Range).
- 사전 참고정보 저장·용어 추출, 저장 전 탭 이동에서 입력 보존.
- 녹취 수정, 자동 원문 보존, 수정 이력, 동시 편집 충돌 방지.
- 검토 상태·화자 이름 저장, 저장 실패 시 편집 내용 유지와 재시도.
- TXT 내보내기, PDF 생성과 한글 글꼴 임베딩.
- 데이터베이스 스냅샷·오디오 백업, 녹음 삭제의 범위.
- 중단한 구간 재개와 중복 삽입 방지. 이 검사는 **가짜 추론 결과를 주입한 처리 흐름 테스트**이며 실제 음성인식 정확도 검사가 아님.
- 생성 모델에 검토한 발언만 전달, 원문 ID 검증, 녹취 변경 시 이전 초안 내보내기 차단. 모델 응답은 테스트 대역으로 검증.
- 같은 출처 변경 요청, 로컬 Host 제한, 모델 누락 시 구체적 오류 표시.
- Windows 실행 파일의 ASCII·CRLF 형식과 배포 ZIP 안의 바이트 보존. Windows cmd.exe 자체의 실행 검증은 별도 대상.
- `setuptools==80.9.0`에서 `pkg_resources`와 Whisper를 새 Python 프로세스에서 불러오는 검사 통과. Windows CTranslate2 의존 모듈 누락의 재발 방지를 위한 검사이며 Windows GPU 추론 검사는 아님.
- PyAV 19.0.1에서 `metadata_errors` 오류 재현. PyAV 16.0.1로 고정한 뒤 실제 Whisper 디코더의 WAV·MP3 디코딩 및 16kHz 변환, 내장 ONNX VAD의 무음 처리 검사 통과. 대형 Whisper 모델 추론 없이 실행한 오디오 입력 계층 검사.
- 작업 처리기를 PCM 배열 직접 입력으로 변경. PyAV `open`에 해당 오류를 강제로 발생시켜도 실제 Whisper 입력·VAD 경로가 이를 호출하지 않고 특징 추출 직전까지 진행하는 것을 확인. PCM 진폭·극성 보존 및 구간 재개 검사도 통과. 특징 추출 이후 대형 모델 추론은 이 검사 범위에 포함하지 않음.
- 1440px 데스크톱과 390px 모바일 레이아웃, 가로 넘침 없음.

## 아직 검증하지 않은 항목

- Windows 11/RTX 2070 SUPER에서의 실제 설치·GPU 추론.
- Whisper large-v3의 실제 한국어 녹취 정확도와 1시간 이상 녹음의 성능·메모리.
- 실제 Ollama qwen3:8b의 문서 생성 품질.
- pyannote 자동 화자 구분 모델의 실제 설치·추론. 수동 화자 지정은 검증됨.
- 사용자 녹음으로 Whisper와 Qwen3-ASR 비교. Qwen3-ASR 엔진은 구현하지 않음.
- 클라우드 환경 게시 및 새로운 태스크에서의 복원.

현재 클라우드에는 NVIDIA GPU와 모델 가중치, Ollama 서비스가 없습니다. 웹앱의 개발·편집·내보내기 기능과 모델 연결 코드를 검증했으며, 실제 AI 결과의 품질을 검증했다고 주장하지 않습니다. 첫 Windows 실행에서 짧은 실제 녹음으로 모델 동작을 확인한 뒤, 대표 녹음 10~15분을 사람이 확인한 정답과 대조하는 과정이 필요합니다.

브라우저 검증의 스크린샷은 `test-results/`에 생성되며, 그 안의 녹취는 ‘검증용’으로 표시된 fixture입니다. 사용자 데이터나 실제 인식 결과가 아닙니다.
