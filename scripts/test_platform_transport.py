"""Synthetic deployment smoke test. TLS verification is disabled ONLY for the CI self-signed certificate."""
import argparse
import json
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
import statistics

import httpx

BASE = 'https://localhost:8443'
ORIGIN = {'Origin': BASE}
STATE = Path('/tmp/medguard-platform-state.json')
PASSWORD = 'platform-synthetic-passphrase!'


def register(client):
    email = f'{uuid4().hex}@example.test'
    response = client.post('/v1/auth/register', headers=ORIGIN, json={'email':email,'password':PASSWORD,'display_name':'Synthetic platform test','consent':True})
    assert response.status_code == 201, f'registration HTTP {response.status_code}'
    response = client.post('/v1/auth/login', headers=ORIGIN, json={'email':email,'password':PASSWORD})
    assert response.status_code == 200, f'login HTTP {response.status_code}'
    assert all(flag in response.headers['set-cookie'] for flag in ['Secure','HttpOnly','SameSite=strict'])
    return response.json()


def main(phase):
    with httpx.Client(base_url=BASE, verify=False, timeout=20) as client:
        if phase == 'before':
            session = register(client)
            headers = ORIGIN | {'X-CSRF-Token':session['csrf_token']}
            response = client.put('/v1/auth/profile',headers=headers,json={'age':44,'conditions':['Synthetic platform fixture']})
            assert response.status_code == 200, f'profile HTTP {response.status_code}'
            instances = set()
            for _ in range(12):
                response = client.get('/v1/auth/me')
                assert response.status_code == 200
                assert response.json()['account']['profile']['age'] == 44
                instances.add(response.headers.get('x-medguard-instance'))
            assert instances == {'app1','app2'}, f'load balancing not observed: {instances}'
            cookie = client.cookies.get('medguard_session')
            def concurrent_read(_):
                start = perf_counter()
                with httpx.Client(base_url=BASE, verify=False, timeout=10, cookies={'medguard_session':cookie}) as worker:
                    result = worker.get('/v1/auth/me')
                    assert result.status_code == 200
                    assert result.json()['account']['profile']['age'] == 44
                    return perf_counter() - start
            with ThreadPoolExecutor(max_workers=8) as pool:
                latencies = sorted(pool.map(concurrent_read, range(64)))
            print(f'Synthetic load: 64 authenticated reads, concurrency 8, p95={latencies[int(len(latencies)*.95)-1]:.3f}s; not a production capacity benchmark')
            assert client.put('/v1/auth/profile',json={'age':45}).status_code == 403
            assert client.put('/v1/auth/profile',headers=headers | {'Origin':'https://evil.test'},json={'age':45}).status_code == 403
            for path in ['/metrics','/docs','/openapi.json','/v1/health/readiness']:
                assert client.get(path).status_code == 403
            STATE.write_text(json.dumps({'cookie':client.cookies.get('medguard_session'),'csrf':session['csrf_token']}))
            STATE.chmod(0o600)
            print('PASS TLS cookie, shared profile/session, CSRF, least_conn distribution, private operational endpoints')
        else:
            state = json.loads(STATE.read_text())
            client.cookies.set('medguard_session',state['cookie'])
            response = client.get('/v1/auth/me')
            assert response.status_code == 200, f'failover session HTTP {response.status_code}'
            assert response.headers.get('x-medguard-instance') == 'app1'
            assert response.json()['account']['profile']['age'] == 44
            assert client.post('/v1/auth/logout',headers=ORIGIN | {'X-CSRF-Token':state['csrf']}).status_code == 204
            client.cookies.set('medguard_session',state['cookie'])
            assert client.get('/v1/auth/me').status_code == 401
            STATE.unlink()
            print('PASS profile/session persistence after replica restart, failover, token revocation')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase',choices=['before','after'])
    main(parser.parse_args().phase)
