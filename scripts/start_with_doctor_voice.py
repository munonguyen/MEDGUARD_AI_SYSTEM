"""Bootstrap the checkout's backend and built-in doctor voices (no API key).

Run: python3 scripts/start_with_doctor_voice.py
No passwords, Origin settings or TLS verification settings are modified.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = """
import importlib.metadata, json
from pathlib import Path
for line in Path("requirements.txt").read_text().splitlines():
    name, separator, pinned = line.strip().partition("==")
    if separator:
        assert importlib.metadata.version(name.split("[")[0]) == pinned.strip(), name
import fastapi, uvicorn, edge_tts
from app.services.doctor_voice import VOICE_PROFILES, VOICE_PROFILE_REVISION
assert VOICE_PROFILES['dr_tuan']['voice'] != VOICE_PROFILES['dr_mai']['voice']
print(json.dumps({'revision':VOICE_PROFILE_REVISION, 'profiles':VOICE_PROFILES,
                 'edge_tts':importlib.metadata.version('edge-tts')}, ensure_ascii=False))
"""
LIVE_CHECK = """
import asyncio
from app.services.doctor_voice import DoctorSpeechRequest, synthesize_doctor_speech
async def check():
    failed = False
    for persona in ('dr_tuan', 'dr_mai'):
        try:
            audio = await synthesize_doctor_speech(DoctorSpeechRequest(
                text='Xin chào bạn. Tôi sẽ lắng nghe và giải thích rõ ràng.', persona=persona))
            print(persona + ': OK (' + str(len(audio)) + ' bytes)')
        except Exception as error:
            failed = True
            # Only an exception class is printed; no clinical text or credentials.
            print(persona + ': unavailable (' + type(error).__name__ + ')')
    return 1 if failed else 0
raise SystemExit(asyncio.run(check()))
"""


def environment_python(directory: Path) -> Path:
    return directory / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def run_python(python: Path, args: list[str], **kwargs):
    return subprocess.run([str(python), *args], cwd=ROOT, **kwargs)


def prepare_environment(directory: Path) -> Path:
    python = environment_python(directory)
    if not directory.exists():
        print('Đang tạo môi trường Python cho MedGuard…', flush=True)
        venv.EnvBuilder(with_pip=True).create(directory)
    if not python.is_file():
        raise RuntimeError(f'Môi trường Python không hợp lệ: {directory}. Hãy chọn một --venv mới.')
    requirements = ROOT / 'requirements.txt'
    fingerprint = hashlib.sha256(requirements.read_bytes()).hexdigest()
    stamp = directory / '.medguard-requirements.sha256'
    current = stamp.read_text().strip() if stamp.exists() else ''
    # A copied/deleted dependency or changed requirements invalidates the cache.
    ready = run_python(python, ['-c', PREFLIGHT], capture_output=True, text=True)
    if current != fingerprint or ready.returncode != 0:
        print('Đang cài/cập nhật dependency, gồm giọng nói edge-tts…', flush=True)
        run_python(python, ['-m', 'pip', 'install', '-r', str(requirements)], check=True)
        ready = run_python(python, ['-c', PREFLIGHT], capture_output=True, text=True)
        if ready.returncode:
            raise RuntimeError('Kiểm tra dependency/cấu hình giọng thất bại. Hãy kiểm tra môi trường Python.')
        stamp.write_text(fingerprint + '\n')
    print('Cấu hình giọng đang chạy: ' + ready.stdout.strip(), flush=True)
    return python


def main(argv=None):
    if sys.version_info < (3, 10):
        print('MedGuard cần Python 3.10 trở lên. Hãy chọn bản Python mới trên MacBook.', file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--venv', type=Path, default=ROOT / '.venv')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--chat-config', type=Path, default=ROOT / '.env.doctor', help='Cấu hình AI riêng tư do configure_doctor_chat.py tạo')
    parser.add_argument('--check', action='store_true', help='Cài đặt và kiểm tra, không chạy server')
    parser.add_argument('--live-check', action='store_true', help='Thử tạo âm thanh thật cho cả hai giọng bằng câu mẫu')
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error('port phải nằm trong khoảng 1–65535')
    if args.live_check and not args.check:
        parser.error('--live-check cần đi cùng --check')
    try:
        python = prepare_environment(args.venv.resolve())
        if args.live_check:
            result = run_python(python, ['-c', LIVE_CHECK])
            if result.returncode:
                print('Dịch vụ giọng chưa sẵn sàng. Kiểm tra Internet/chứng chỉ CA; không tắt kiểm tra TLS.', file=sys.stderr)
                return 1
        if args.check:
            return 0
        if args.chat_config.exists():
            print('Đang dùng cấu hình AI từ ' + args.chat_config.name + ' (biến môi trường đang đặt vẫn có ưu tiên).', flush=True)
        else:
            print('Chưa có .env.doctor. Nếu chưa cấu hình gateway trong .env, AI chỉ trả lời theo quy tắc. Chạy python3 scripts/configure_doctor_chat.py.', flush=True)
        print(f'Mở http://localhost:{args.port}/?view=companion → Cài đặt → Nghe thử giọng bác sĩ.', flush=True)
        os.chdir(ROOT)
        # Replace the launcher so Ctrl+C/termination reaches the backend itself.
        command = [str(python), '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(args.port)]
        if args.chat_config.exists(): command += ['--env-file', str(args.chat_config.resolve())]
        os.execv(str(python), command)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'Không khởi động được: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
