"""Start only on loopback; opening a browser is optional for development."""
import argparse
import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    os.chdir(ROOT)
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1', args.port)) == 0:
            print(f'Port {args.port} is already in use. Close the existing app or select --port.')
            return 1
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(f'http://127.0.0.1:{args.port}')).start()
    import uvicorn
    uvicorn.run('app.main:app', host='127.0.0.1', port=args.port, log_level='info')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
