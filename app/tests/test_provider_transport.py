import httpx

from app.services.provider_transport import close_provider_clients, provider_client


def test_pool_reuses_connections_without_credentials_or_cookies(monkeypatch):
    close_provider_clients()
    real_client = httpx.Client
    calls = []
    clients = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, headers={"set-cookie": "session=secret; Path=/"}, json={})

    def factory(**kwargs):
        client = real_client(transport=httpx.MockTransport(respond), **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr('app.services.provider_transport.httpx.Client', factory)
    with provider_client(4) as first:
        first.post('https://provider.example/responses', headers={"Authorization": "Bearer tenant-a"})
    assert not first.is_closed
    with provider_client(4) as second:
        assert second is first
        second.post('https://provider.example/responses', headers={"Authorization": "Bearer tenant-b"})
    assert calls[0].headers['authorization'] == 'Bearer tenant-a'
    assert calls[1].headers['authorization'] == 'Bearer tenant-b'
    assert 'cookie' not in calls[1].headers
    assert 'authorization' not in second.headers
    with provider_client(8) as other:
        assert other is not first
    close_provider_clients()
    assert all(c.is_closed for c in clients)
