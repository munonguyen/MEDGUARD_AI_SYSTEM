"""Bootstrap regression cases, without installing packages or contacting TTS."""
import hashlib
import subprocess
from types import SimpleNamespace

import pytest
from scripts import start_with_doctor_voice as bootstrap


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, 'ROOT', tmp_path)
    (tmp_path / 'requirements.txt').write_text('edge-tts==7.2.8\n')
    directory = tmp_path / '.venv'
    python = bootstrap.environment_python(directory)
    python.parent.mkdir(parents=True)
    python.touch()
    return directory


def stamp(directory):
    content = (bootstrap.ROOT / 'requirements.txt').read_bytes()
    (directory / '.medguard-requirements.sha256').write_text(hashlib.sha256(content).hexdigest())


def test_first_checkout_installs_and_validates(environment, monkeypatch):
    calls = []
    def run(python, args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout='profiles ready')
    monkeypatch.setattr(bootstrap, 'run_python', run)
    bootstrap.prepare_environment(environment)
    assert sum(args[:3] == ['-m', 'pip', 'install'] for args in calls) == 1
    assert (environment / '.medguard-requirements.sha256').exists()


def test_valid_environment_starts_without_pip(environment, monkeypatch):
    stamp(environment)
    calls = []
    def run(python, args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout='profiles ready')
    monkeypatch.setattr(bootstrap, 'run_python', run)
    bootstrap.prepare_environment(environment)
    assert len(calls) == 1


def test_missing_dependency_reinstalls_even_with_current_stamp(environment, monkeypatch):
    stamp(environment)
    calls = []
    def run(python, args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1 if len(calls) == 1 else 0, stdout='profiles ready')
    monkeypatch.setattr(bootstrap, 'run_python', run)
    bootstrap.prepare_environment(environment)
    assert any(args[:3] == ['-m', 'pip', 'install'] for args in calls)


def test_failed_install_does_not_mark_environment_ready(environment, monkeypatch):
    def run(python, args, **kwargs):
        if args[:3] == ['-m', 'pip', 'install']:
            raise subprocess.CalledProcessError(1, 'pip')
        return SimpleNamespace(returncode=1, stdout='')
    monkeypatch.setattr(bootstrap, 'run_python', run)
    with pytest.raises(subprocess.CalledProcessError):
        bootstrap.prepare_environment(environment)
    assert not (environment / '.medguard-requirements.sha256').exists()


def test_invalid_existing_environment_is_preserved(tmp_path):
    marker = tmp_path / 'keep-me'
    marker.write_text('existing data')
    with pytest.raises(RuntimeError):
        bootstrap.prepare_environment(tmp_path)
    assert marker.read_text() == 'existing data'


def test_check_does_not_start_server_or_send_live_text(environment, monkeypatch):
    monkeypatch.setattr(bootstrap, 'prepare_environment', lambda _: bootstrap.environment_python(environment))
    def forbidden(*args, **kwargs):
        pytest.fail('A local check must not start a server or contact the provider')
    monkeypatch.setattr(bootstrap, 'run_python', forbidden)
    assert bootstrap.main(['--check', '--venv', str(environment)]) == 0


def test_live_failure_is_nonzero_and_does_not_launch_backend(environment, monkeypatch):
    monkeypatch.setattr(bootstrap, 'prepare_environment', lambda _: bootstrap.environment_python(environment))
    calls = []
    def run(python, args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(bootstrap, 'run_python', run)
    assert bootstrap.main(['--check', '--live-check', '--venv', str(environment)]) == 1
    assert len(calls) == 1 and calls[0][1] == bootstrap.LIVE_CHECK
