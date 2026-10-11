"""Real UI and API smoke test. Seeded transcript is not a speech-recognition test."""
import io
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix='voice-archive-browser-') as directory:
        data = Path(directory)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        environment = {**os.environ, 'VOICE_ARCHIVE_DATA': str(data)}
        process = subprocess.Popen([sys.executable, 'scripts/run.py', '--no-browser', '--port', str(port)],
                                   cwd=ROOT, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            for _ in range(80):
                try:
                    if httpx.get(base, trust_env=False).status_code == 200:
                        break
                except httpx.ConnectError:
                    pass
                time.sleep(.1)
            else:
                raise RuntimeError('App failed to start: ' + process.stderr.read(4000).decode())
            audio = data / 'fixture.wav'
            with wave.open(str(audio), 'wb') as file:
                file.setnchannels(1)
                file.setsampwidth(2)
                file.setframerate(16000)
                file.writeframes(b'\0\0' * 16000 * 3)
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH', '/usr/bin/chromium'),
                                             args=['--no-sandbox'], headless=True)
                context = browser.new_context(viewport={'width':1440,'height':1050}, accept_downloads=True)
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(base)
                page.get_by_role('heading', name='말의 순간을, 기록의 자산으로.').wait_for()
                output = ROOT / 'test-results'
                output.mkdir(exist_ok=True)
                page.screenshot(path=str(output / 'library.png'), full_page=True)
                page.get_by_role('button', name='새 녹음 추가', exact=True).click()
                page.locator('#upload-file').set_input_files(audio)
                page.locator('#upload-title').fill('브라우저 검증용 타운홀')
                page.get_by_role('button', name='기록실에 추가').click()
                page.get_by_role('heading', name='브라우저 검증용 타운홀').wait_for()
                project_id = page.url.split('project/')[1]
                page.locator('#reference').fill('[8. 음성인식용 압축 용어 목록]\n도시재생, 김시장')
                page.get_by_role('button', name='8번 구역에서 가져오기').click()
                assert page.locator('#terms').input_value() == '도시재생, 김시장'
                page.get_by_role('button', name='참고정보 저장', exact=True).click()
                page.get_by_text('참고정보를 저장했습니다.', exact=False).wait_for()
                page.get_by_role('button', name='음성인식 시작').click()
                page.get_by_text('Whisper 모델이 없습니다.', exact=False).wait_for()
                page.locator('#reference').fill('탭 이동 중 유지해야 하는 임시 참고정보')
                page.get_by_role('button', name='화자 관리', exact=True).click()
                page.get_by_role('button', name='사전 참고정보', exact=True).click()
                assert page.locator('#reference').input_value() == '탭 이동 중 유지해야 하는 임시 참고정보'
                page.get_by_role('button', name='참고정보 저장', exact=True).click()
                page.get_by_text('참고정보를 저장했습니다.', exact=False).wait_for()
                # Seed explicitly marked transcript fixture for editor/export integration.
                with sqlite3.connect(data / 'archive.sqlite3') as db:
                    db.execute("UPDATE projects SET status='completed',progress=1 WHERE id=?", (project_id,))
                    db.execute('INSERT INTO segments(project_id,start,end,original_text,text) VALUES(?,?,?,?,?)',
                               (project_id, 0, 2.5, '검증용 원문: 사업 예산은 13억입니다.', '검증용 원문: 사업 예산은 13억입니다.'))
                page.reload()
                editor = page.locator('[data-segment]')
                editor.wait_for()
                editor.fill('검증용 편집: 사업 예산은 30억입니다.')
                page.get_by_role('heading', name='전체 녹취록', exact=False).click()
                page.get_by_text('저장됨', exact=True).wait_for()
                page.get_by_role('button', name='검토 완료 표시', exact=True).click()
                page.get_by_role('button', name='검토 완료', exact=True).wait_for()
                page.get_by_text('자동 녹취 원문', exact=True).click()
                page.locator('.original p').get_by_text('검증용 원문: 사업 예산은 13억입니다.', exact=True).wait_for()
                page.get_by_role('button', name='화자 관리', exact=True).click()
                page.locator('[data-speaker-name]').fill('시장님')
                page.get_by_role('button', name='이름 저장').click()
                page.get_by_text('화자 이름을 저장했습니다.', exact=True).wait_for()
                page.get_by_role('button', name='발언·초안', exact=True).click()
                assert not page.locator('#mayor-field').is_visible()
                page.locator('#draft-kind').select_option('mayor')
                assert page.locator('#mayor-field').is_visible()
                page.locator('#draft-kind').select_option('summary')
                page.screenshot(path=str(output / 'workspace.png'), full_page=True)
                page.get_by_role('button', name='내보내기', exact=True).click()
                page.locator('#export-format').select_option('pdf')
                with page.expect_download() as download:
                    page.locator('#export-form').get_by_role('button', name='내보내기', exact=True).click()
                path = download.value.path()
                assert Path(path).read_bytes().startswith(b'%PDF')
                response = httpx.get(f'{base}/api/projects/{project_id}', trust_env=False).json()
                assert response['segments'][0]['reviewed'] == 1
                assert response['segments'][0]['original_text'].endswith('13억입니다.')
                assert response['segments'][0]['text'].endswith('30억입니다.')
                # An unavailable save must not discard the user's edited text on navigation.
                page.route('**/api/segments/*', lambda route: route.fulfill(status=503, json={'detail':'테스트 연결 중단'}))
                editor = page.locator('[data-segment]')
                editor.fill('연결이 끊겨도 보존해야 하는 편집')
                page.get_by_role('heading', name='전체 녹취록', exact=False).click()
                page.get_by_text('저장 실패', exact=True).wait_for()
                page.get_by_role('button', name='사전 참고정보', exact=True).click()
                assert page.locator('[data-segment]').input_value() == '연결이 끊겨도 보존해야 하는 편집'
                page.unroute('**/api/segments/*')
                page.get_by_role('button', name='사전 참고정보', exact=True).click()
                page.locator('#reference').wait_for()
                response = httpx.get(f'{base}/api/projects/{project_id}', trust_env=False).json()
                assert response['segments'][0]['text'] == '연결이 끊겨도 보존해야 하는 편집'
                assert response['segments'][0]['reviewed'] == 0
                # No horizontal overflow at phone width, on both workspace and library.
                page.set_viewport_size({'width':390,'height':844})
                page.reload()
                page.locator('#segments').wait_for()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Workspace overflows mobile viewport'
                page.goto(base + '/#library')
                page.get_by_role('heading', name='말의 순간을, 기록의 자산으로.').wait_for()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Library overflows mobile viewport'
                page.screenshot(path=str(output / 'mobile.png'), full_page=True)
                assert not errors, errors
                browser.close()
                print('Browser smoke PASS: upload, reference, missing-model handling, edit/history preservation, review, speakers, PDF, mobile layout; no page errors.')
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == '__main__':
    main()
