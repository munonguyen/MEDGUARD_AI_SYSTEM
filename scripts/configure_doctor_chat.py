"""Configure an existing LiteLLM gateway for doctor chat (macOS/Linux/Windows).

No key is needed for the separate built-in voice service. An AI gateway and its
own provider credentials are required for generated, reviewed medical answers.
"""
import argparse
import getpass
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[1]


def profile(url, key, style):
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('URL không được chứa mật khẩu, query hoặc fragment.')
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in {'localhost','127.0.0.1','::1'}):
        raise ValueError('Gateway ở máy khác cần HTTPS; HTTP chỉ dùng cho localhost.')
    if not key.strip() or any(c in key for c in '\r\n') or key.startswith(('replace-', '<')):
        raise ValueError('Cần API key hợp lệ của gateway, không dùng placeholder.')
    if style not in {'responses', 'chat_completions'}:
        raise ValueError('API style không hợp lệ.')
    return {
        'MEDGUARD_LLM_GATEWAY_URL': url.rstrip('/'),
        'MEDGUARD_LLM_GATEWAY_API_KEY': key.strip(),
        'MEDGUARD_LLM_GATEWAY_API_STYLE': style,
        'MEDGUARD_AGENT_MODE': 'enforced',
        'MEDGUARD_AGENT_COVERAGE_SCOPE': 'all',
        'MEDGUARD_AGENT_SYNC_ENABLED': 'true',
        'MEDGUARD_AGENT_BACKGROUND_ENABLED': 'false',
        'MEDGUARD_AGENT_TIMEOUT_SECONDS': '12',
        'MEDGUARD_AGENT_TOTAL_TIMEOUT_SECONDS': '30',
        'MEDGUARD_AGENT_MAX_ITERATIONS': '0',
        'MEDGUARD_RESEARCH_AGENT_MODEL': 'medguard-answer',
        'MEDGUARD_VERIFIER_AGENT_MODEL': 'medguard-verifier',
        # Grounding and Reviewer gates remain enabled. No bypass for latency.
        'MEDGUARD_AGENT_WEB_SEARCH_ENABLED': 'true',
        'MEDGUARD_AGENT_WEB_SEARCH_REQUIRED': 'true',
        'MEDGUARD_VERIFIER_WEB_SEARCH_ENABLED': 'true',
        'MEDGUARD_VERIFIER_WEB_SEARCH_REQUIRED': 'true',
    }


def write_profile(path, values, force=False):
    if path.exists() and not force:
        raise ValueError(f'{path.name} đã tồn tại. Dùng --force nếu muốn thay cấu hình này.')
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.doctor-config-', dir=path.parent)
    try:
        os.chmod(name, 0o600)
        with os.fdopen(fd, 'w') as file:
            file.write('# Local gateway configuration. Never commit this file.\n')
            for key, value in values.items():
                file.write(f'{key}={json.dumps(value)}\n')
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


def check_models(url, key, style='chat_completions'):
    request = Request(url.rstrip('/') + '/models', headers={'Authorization': 'Bearer ' + key})
    # Do not forward a gateway credential through redirects to another host.
    from urllib.request import HTTPRedirectHandler, build_opener
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs): return None
    opener = build_opener(NoRedirect)
    with opener.open(request, timeout=5) as response:
        data = json.loads(response.read(1024 * 1024))
    ids = {m.get('id') for m in data.get('data', [])}
    required = {'medguard-answer', 'medguard-verifier', 'medguard-clinical-answer',
                'medguard-clinical-verifier', 'medguard-pharma-answer', 'medguard-pharma-verifier'}
    if not required <= ids:
        raise ValueError('Gateway thiếu alias: ' + ', '.join(sorted(required - ids)))
    # Registration alone is not proof that upstream provider credentials work.
    # Probe every domain path with a tiny synthetic, non-clinical message.
    for alias in sorted(required):
        body = ({'model':alias, 'messages':[{'role':'user','content':'Reply with OK.'}], 'max_tokens':32}
                if style == 'chat_completions' else {'model':alias, 'input':'Reply with OK.', 'max_output_tokens':32})
        endpoint = '/chat/completions' if style == 'chat_completions' else '/responses'
        probe = Request(url.rstrip('/') + endpoint, data=json.dumps(body).encode(),
                        headers={'Authorization':'Bearer ' + key, 'Content-Type':'application/json'})
        with opener.open(probe, timeout=20) as response:
            result = json.loads(response.read(1024 * 1024))
        if not (result.get('choices') or result.get('output') or result.get('output_text')):
            raise ValueError('Gateway chưa trả được nội dung thử cho ' + alias)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gateway-url', default='http://127.0.0.1:4000/v1')
    parser.add_argument('--api-style', choices=['responses','chat_completions'], default='chat_completions')
    parser.add_argument('--output', type=Path, default=ROOT / '.env.doctor')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args(argv)
    try:
        key = getpass.getpass('API key của LiteLLM gateway (ẩn khi nhập): ')
        values = profile(args.gateway_url, key, args.api_style)
        check_models(args.gateway_url, key, args.api_style)
        write_profile(args.output.resolve(), values, args.force)
    except Exception as error:
        # Network exceptions can contain URLs/credentials; never echo details.
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        print('Chưa cấu hình được: ' + message)
        return 1
    print('Đã lưu cấu hình riêng tư, kiểm tra đủ alias và nhận phản hồi thử từ Writer/Reviewer.')
    print('Phép thử kết nối không chứng minh chất lượng hay độ chính xác y khoa.')
    print('Chạy python3 scripts/start_with_doctor_voice.py rồi thử một câu hỏi trong trang bác sĩ.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
