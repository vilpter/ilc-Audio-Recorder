"""Route-level smoke tests: auth protection and basic page rendering."""
import pytest

import app as app_module

PUBLIC_ENDPOINTS = {'static', 'login', 'setup'}


def _protected_rules():
    for rule in app_module.app.url_map.iter_rules():
        if rule.endpoint in PUBLIC_ENDPOINTS:
            continue
        yield rule


def _url_for_rule(rule):
    # Fill path parameters with dummy values; the auth check runs before the view.
    return rule.build({arg: '1' for arg in rule.arguments}, append_unknown=False)[1]


@pytest.mark.parametrize('rule', list(_protected_rules()), ids=lambda r: f'{sorted(r.methods - {"HEAD", "OPTIONS"})}{r.rule}')
def test_routes_require_login(client, rule):
    method = sorted(rule.methods - {'HEAD', 'OPTIONS'})[0]
    resp = client.open(_url_for_rule(rule), method=method)
    assert resp.status_code in (302, 401), f'{method} {rule.rule} returned {resp.status_code} without login'
    if resp.status_code == 302:
        assert '/login' in resp.headers['Location']


def test_login_page_renders(client):
    resp = client.get('/login')
    assert resp.status_code == 200


def test_bad_password_rejected(client):
    resp = client.post('/login', data={'username': 'admin', 'password': 'wrong'})
    assert resp.status_code == 200  # re-renders login form
    assert client.get('/').status_code == 302


@pytest.mark.parametrize('path', ['/', '/recordings', '/settings', '/camera', '/change-password'])
def test_pages_render_when_logged_in(logged_in, path):
    resp = logged_in.get(path)
    assert resp.status_code == 200, resp.data[:500]


def test_calendar_redirects_to_index(logged_in):
    resp = logged_in.get('/calendar')
    assert resp.status_code == 302


def test_status_api(logged_in, monkeypatch):
    monkeypatch.setattr(app_module.recorder, 'is_recording', lambda: False)
    resp = logged_in.get('/api/status')
    assert resp.status_code == 200
    assert resp.get_json()['is_recording'] is False


def test_logout(logged_in):
    assert logged_in.get('/logout').status_code == 302
    assert logged_in.get('/').status_code == 302


def test_directory_browser_lists(logged_in, _storage_dir):
    (_storage_dir / 'sub').mkdir(exist_ok=True)
    resp = logged_in.post('/api/directories/list', json={'path': str(_storage_dir)})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()['success'] is True


def test_directory_browser_creates(logged_in, _storage_dir):
    resp = logged_in.post('/api/directories/create',
                          json={'parent_path': str(_storage_dir), 'folder_name': 'new_folder'})
    assert resp.status_code in (200, 409), resp.get_json()
    assert (_storage_dir / 'new_folder').is_dir()
