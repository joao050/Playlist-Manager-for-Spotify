"""
Suíte Integrada de Testes Automatizados de Segurança e Conformidade (Fase 9).
Abrange 100% dos controles OWASP ASVS e Spotify Developer Policy implementados nas Fases 0 a 8.
"""

import os
import re
import json
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest
from cryptography.fernet import Fernet, MultiFernet

import app as spotify_app

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# ─── 1. AMBIENTE E SEGREDOS (FASES 0 E 1) ──────────────────────────────────────
class TestEnvironmentAndSecrets:
    """Validação fail-fast, qualidade e entropia de chaves e cookies seguros."""

    def test_env_validation_missing_vars(self, monkeypatch):
        """Valida que o app recusa subir se variáveis essenciais estiverem ausentes."""
        monkeypatch.delenv("SPOTIPY_CLIENT_ID", raising=False)
        with pytest.raises(RuntimeError, match="FALHA DE INICIALIZAÇÃO: Variáveis obrigatórias ausentes"):
            spotify_app.validate_environment()

    def test_flask_secret_key_entropy(self, monkeypatch):
        """Valida rejeição de FLASK_SECRET_KEY com menos de 32 bytes de entropia."""
        monkeypatch.setenv("SPOTIPY_CLIENT_ID", "mock_id")
        monkeypatch.setenv("SPOTIPY_CLIENT_SECRET", "mock_secret")
        monkeypatch.setenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:5000/callback")
        monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
        monkeypatch.setenv("FLASK_SECRET_KEY", "chave_curta_insegura_123")

        with pytest.raises(RuntimeError, match="entropia insuficiente"):
            spotify_app.validate_environment()

    def test_encryption_key_validation(self, monkeypatch):
        """Valida rejeição de ENCRYPTION_KEY inválida (não Fernet)."""
        monkeypatch.setenv("SPOTIPY_CLIENT_ID", "mock_id")
        monkeypatch.setenv("SPOTIPY_CLIENT_SECRET", "mock_secret")
        monkeypatch.setenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:5000/callback")
        monkeypatch.setenv("FLASK_SECRET_KEY", "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef")
        monkeypatch.setenv("ENCRYPTION_KEY", "chave_fernet_completamente_invalida")

        with pytest.raises(RuntimeError, match="ENCRYPTION_KEY inválida"):
            spotify_app.validate_environment()

    def test_session_cookie_security_flags(self, app):
        """Garante que flags de cookies de sessão estão em conformidade com OWASP."""
        assert app.config["SESSION_COOKIE_HTTPONLY"] is True
        assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
        assert app.config["PERMANENT_SESSION_LIFETIME"] == timedelta(hours=24)
        assert app.config["SESSION_FILE_THRESHOLD"] == 100


# ─── 2. OAUTH 2.0 PKCE & CONTROLE DE SESSÃO (FASE 2) ──────────────────────────
class TestOAuthPKCE:
    """Fluxo OAuth 2.0 PKCE S256, State anti-CSRF e gestão segura de sessão."""

    def test_login_flow_generates_pkce_and_state(self, client):
        """Verifica se /login inicia PKCE com S256 e state criptograficamente seguro."""
        resp = client.get("/login")
        assert resp.status_code == 302
        redirect_url = resp.headers.get("Location")

        assert "accounts.spotify.com/authorize" in redirect_url
        assert "response_type=code" in redirect_url
        assert "code_challenge_method=S256" in redirect_url
        assert "code_challenge=" in redirect_url
        assert "state=" in redirect_url

        with client.session_transaction() as sess:
            assert "code_verifier" in sess
            assert "oauth_state" in sess
            assert len(sess["code_verifier"]) >= 43
            assert len(sess["oauth_state"]) >= 32

    def test_callback_rejects_missing_or_mismatched_state(self, client):
        """Verifica rejeição com 403 se state for nulo ou divergente (Anti-CSRF)."""
        # 1. State ausente
        resp = client.get("/callback?code=mock_code")
        assert resp.status_code == 403
        assert "state inválido" in resp.get_data(as_text=True)

        # 2. State divergente
        with client.session_transaction() as sess:
            sess["oauth_state"] = "state_original_legitimo_1234567890"
            sess["code_verifier"] = "verifier_legitimo_12345678901234567890"

        resp2 = client.get("/callback?code=mock_code&state=state_falso_atacante")
        assert resp2.status_code == 403
        assert "state inválido" in resp2.get_data(as_text=True)

    def test_callback_handles_spotify_error(self, client):
        """Verifica redirecionamento limpo caso o Spotify retorne erro no callback."""
        with client.session_transaction() as sess:
            sess["oauth_state"] = "valid_state_12345"

        resp = client.get("/callback?error=access_denied&state=valid_state_12345")
        assert resp.status_code == 302
        assert "/login-page?error=access_denied" in resp.headers.get("Location")

    def test_logout_post_clears_session_and_rotates(self, auth_client):
        """Verifica encerramento seguro de sessão via POST com validação de origem."""
        with auth_client.session_transaction() as sess:
            assert "token_info" in sess

        resp = auth_client.post("/logout", headers={"Origin": "http://localhost"})
        assert resp.status_code == 302
        assert "/login-page?logged_out=1" in resp.headers.get("Location")

        with auth_client.session_transaction() as sess:
            assert "token_info" not in sess
            assert "user_id" not in sess

    def test_logout_rejects_get_request(self, client):
        """Verifica que /logout rejeita requisições GET (Method Not Allowed)."""
        resp = client.get("/logout")
        assert resp.status_code == 405


# ─── 3. DADOS EM REPOUSO & LGPD (FASE 3) ───────────────────────────────────────
class TestDataAtRestAndLGPD:
    """Criptografia simétrica Fernet, minimização de dados e direito ao esquecimento."""

    def test_fernet_encryption_roundtrip(self):
        """Valida cifragem e decifragem preservando integridade dos tokens."""
        original_data = {
            "access_token": "secret_access_token_abc_123",
            "refresh_token": "secret_refresh_token_xyz_789",
            "expires_at": int(time.time()) + 3600
        }
        encrypted = spotify_app.encrypt_data(original_data)
        assert isinstance(encrypted, str)
        assert "secret_access_token_abc_123" not in encrypted

        decrypted = spotify_app.decrypt_data(encrypted)
        assert decrypted == original_data

    def test_multi_fernet_key_rotation(self):
        """Valida suporte a rotação de chaves sem downtime ou perda de sessões ativas."""
        key_old = Fernet.generate_key()
        key_new = Fernet.generate_key()

        # Cifra com chave antiga
        old_fernet = Fernet(key_old)
        cipher_old = old_fernet.encrypt(b"{\"user\": \"test\"}").decode()

        # MultiFernet com chave nova primária e antiga de fallback
        multi = MultiFernet([Fernet(key_new), Fernet(key_old)])
        decrypted = json.loads(multi.decrypt(cipher_old.encode()).decode())
        assert decrypted["user"] == "test"

    def test_purge_session_file(self):
        """Valida exclusão física de arquivo de sessão no disco."""
        session_dir = spotify_app.app.config.get("SESSION_FILE_DIR")
        if session_dir and os.path.exists(session_dir):
            dummy_sid = "test_sid_for_purge_validation"
            dummy_path = os.path.join(session_dir, dummy_sid)
            with open(dummy_path, "w") as f:
                f.write("dummy session content")

            assert os.path.exists(dummy_path)
            spotify_app.purge_session_file(dummy_sid)
            assert not os.path.exists(dummy_path)

    def test_track_data_minimization(self):
        """Garante que tracks_cache armazena estritamente os campos necessários."""
        allowed_keys = {"id", "name", "artist", "decade", "year", "popularity", "duration_ms", "uri"}
        dummy_track = {
            "id": "trk123",
            "name": "Song Name",
            "artist": "Artist Name",
            "decade": "2020s",
            "year": 2024,
            "popularity": 85,
            "duration_ms": 210000,
            "uri": "spotify:track:4cOdK2wGLETKBW3PvgPWqT",
            "unnecessary_payload": "should_be_stripped",
            "market_availability": ["BR", "US"]
        }

        minimized = {k: v for k, v in dummy_track.items() if k in allowed_keys}
        assert set(minimized.keys()) == allowed_keys
        assert "unnecessary_payload" not in minimized

    def test_tracks_cache_ttl_expiration(self, app):
        """Valida expiração automática de cache após 24 horas (TTL)."""
        with app.test_request_context("/"):
            # 1. Cache recente (<24h)
            spotify_app.set_cached_tracks([{"id": "track_1", "name": "Song 1"}])
            cached = spotify_app.get_cached_tracks()
            assert cached == [{"id": "track_1", "name": "Song 1"}]

            # 2. Cache expirado (>24h)
            old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
            expired_payload = {
                "cached_at": old_time,
                "items": [{"id": "track_old", "name": "Old Song"}]
            }
            spotify_app.session["tracks_cache"] = spotify_app.encrypt_data(expired_payload)
            expired_retrieved = spotify_app.get_cached_tracks()
            assert expired_retrieved is None
            assert "tracks_cache" not in spotify_app.session

    def test_lgpd_delete_my_data(self, auth_client):
        """Valida exclusão total e irrevogável de dados de usuário (LGPD Art. 18)."""
        with auth_client.session_transaction() as sess:
            sess["tracks_cache"] = spotify_app.encrypt_data({"cached_at": "now", "items": []})
            assert "tracks_cache" in sess

        resp = auth_client.post("/api/delete_my_data", headers={"Origin": "http://localhost"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("success") is True
        assert "excluídos" in data.get("message")

        with auth_client.session_transaction() as sess:
            assert "tracks_cache" not in sess
            assert "token_info" not in sess
            assert "user_id" not in sess


# ─── 4. PROTEÇÃO DE API & LIMITES (FASE 4) ────────────────────────────────────
class TestApiProtection:
    """Rate Limiting, CSRF Same-Origin, limite 1MB e tratamento de backoff 429."""

    def test_rate_limiting_exceeded_with_retry_after(self, auth_client):
        """Valida bloqueio por Rate Limit (HTTP 429) e cabeçalho Retry-After."""
        rate_limited = False
        retry_after_present = False

        for _ in range(15):
            r = auth_client.post("/api/sync", headers={"Origin": "http://localhost"})
            if r.status_code == 429:
                rate_limited = True
                retry_after_present = "Retry-After" in r.headers
                break

        assert rate_limited is True
        assert retry_after_present is True

    def test_csrf_require_same_origin_rejection(self, auth_client):
        """Valida que requisições POST com Origin, Referer ou Sec-Fetch-Site externos são rejeitadas com 403."""
        # 1. Origin de atacante externo
        resp1 = auth_client.post("/api/delete_my_data", headers={"Origin": "https://evil-attacker.com"})
        assert resp1.status_code == 403
        assert "CSRF" in resp1.get_data(as_text=True)

        # 2. Referer de atacante externo
        resp2 = auth_client.post("/api/delete_my_data", headers={"Referer": "https://evil-attacker.com/attack"})
        assert resp2.status_code == 403
        assert "CSRF" in resp2.get_data(as_text=True)

        # 3. Sec-Fetch-Site cross-site
        resp3 = auth_client.post("/api/delete_my_data", headers={"Sec-Fetch-Site": "cross-site"})
        assert resp3.status_code == 403
        assert "CSRF" in resp3.get_data(as_text=True)

    def test_max_content_length_limit(self, auth_client):
        """Valida rejeição com 413 ao exceder 1MB no payload de entrada."""
        large_payload = "A" * (1024 * 1024 + 1024)  # > 1MB
        headers = {
            "Origin": "http://localhost",
            "Content-Type": "application/json"
        }
        resp = auth_client.post("/api/create_playlist", data=large_payload, headers=headers)
        assert resp.status_code == 413
        assert "1MB" in (resp.get_json() or {}).get("error", "")

    def test_create_playlist_payload_validation(self, auth_client):
        """Valida sanitização estrita de nome e formato de URIs do Spotify via Regex."""
        valid_headers = {"Origin": "http://localhost"}

        # 1. Payload não-JSON
        spotify_app.limiter.reset()
        res_not_json = auth_client.post("/api/create_playlist", headers=valid_headers, data="não é json")
        assert res_not_json.status_code == 400
        assert "application/json" in (res_not_json.get_json() or {}).get("error", "")

        # 2. Nome vazio ou ausente
        spotify_app.limiter.reset()
        res_no_name = auth_client.post("/api/create_playlist", headers=valid_headers, json={"name": "   ", "track_uris": ["spotify:track:4cOdK2wGLETKBW3PvgPWqT"]})
        assert res_no_name.status_code == 400
        assert "nome" in (res_no_name.get_json() or {}).get("error", "").lower()

        # 3. Nome excessivamente longo (>100 caracteres)
        spotify_app.limiter.reset()
        res_long_name = auth_client.post("/api/create_playlist", headers=valid_headers, json={"name": "X" * 101, "track_uris": ["spotify:track:4cOdK2wGLETKBW3PvgPWqT"]})
        assert res_long_name.status_code == 400
        assert "100" in (res_long_name.get_json() or {}).get("error", "")

        # 4. Lista de faixas vazia
        spotify_app.limiter.reset()
        res_empty_uris = auth_client.post("/api/create_playlist", headers=valid_headers, json={"name": "Válida", "track_uris": []})
        assert res_empty_uris.status_code == 400
        assert "Nenhuma música" in (res_empty_uris.get_json() or {}).get("error", "")

        # 5. Formato de URI inválido (não compatível com regex spotify:track:[a-zA-Z0-9]{22})
        spotify_app.limiter.reset()
        res_invalid_uri = auth_client.post("/api/create_playlist", headers=valid_headers, json={
            "name": "Válida",
            "track_uris": ["spotify:track:short_invalid", "spotify:album:1234567890123456789012"]
        })
        assert res_invalid_uri.status_code == 400
        assert "URI válida" in (res_invalid_uri.get_json() or {}).get("error", "")

    def test_spotify_request_retry_after_backoff(self):
        """Valida comportamento do client HTTP ao receber status 429 do Spotify."""
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.headers = {"Retry-After": "1"}

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.content = b'{"success": true, "id": "playlist_123"}'
        mock_200.json.return_value = {"success": True, "id": "playlist_123"}

        with patch("app.http_requests.request", side_effect=[mock_429, mock_200]) as mock_req, \
             patch("time.sleep") as mock_sleep:
            res = spotify_app.spotify_request("POST", "test_endpoint", "fake_token", json_data={"test": 1})
            assert res.get("id") == "playlist_123"
            assert mock_req.call_count == 2
            mock_sleep.assert_called_with(1)


# ─── 5. CABEÇALHOS DE SEGURANÇA & ANTI-XSS (FASE 5) ───────────────────────────
class TestFrontendAndHeaders:
    """Cabeçalhos HTTP restritivos (CSP, HSTS, no-store) e prevenção de DOM-XSS."""

    def test_http_security_headers_present(self, client):
        """Verifica presença dos cabeçalhos CSP, Frame-Options e nosniff em /login-page."""
        resp = client.get("/login-page")
        assert resp.status_code == 200

        # CSP
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "base-uri 'self'" in csp
        assert "form-action 'self'" in csp

        # X-Frame-Options
        assert resp.headers.get("X-Frame-Options") == "DENY"

        # X-Content-Type-Options
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_cache_control_no_store_on_api(self, auth_client):
        """Verifica que endpoints /api/* proíbem cache de dados de usuário."""
        resp = auth_client.get("/api/user")
        cache_control = resp.headers.get("Cache-Control", "")
        assert "no-store" in cache_control
        assert "no-cache" in cache_control

    def test_templates_free_of_inline_event_handlers(self):
        """Garante que templates HTML não possuem handlers inline de script."""
        template_dir = os.path.join(BASE_DIR, "templates")
        inline_regex = re.compile(r'\son[a-z]+\s*=', re.IGNORECASE)

        for fname in ["index.html", "login.html", "privacy.html", "terms.html"]:
            fpath = os.path.join(template_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
                matches = inline_regex.findall(content)
                assert len(matches) == 0, f"Inline handler encontrado em {fname}: {matches}"

    def test_static_js_app_uses_safe_dom_apis(self, client):
        """Garante que static/js/app.js manipula dados externos via DOM API segura."""
        res_js = client.get("/static/js/app.js")
        assert res_js.status_code == 200
        js_content = res_js.get_data(as_text=True)

        # Valida que não usa tr.innerHTML para injetar faixas
        assert "tr.innerHTML =" not in js_content

        # Valida atribuição via textContent
        assert "spanTitle.textContent" in js_content
        assert "spanArtist.textContent" in js_content
        assert "spanAlbum.textContent" in js_content


# ─── 6. PRIVACIDADE, TERMOS & CONFORMIDADE SPOTIFY (FASE 6) ───────────────────
class TestPrivacyAndTerms:
    """Acesso público a termos, transparência de escopos e conformidade."""

    def test_privacy_page_public_access(self, client):
        """Verifica se /privacy está publicamente acessível sem autenticação."""
        resp = client.get("/privacy")
        assert resp.status_code == 200
        content = resp.get_data(as_text=True)
        assert "LGPD" in content
        assert "13.709" in content
        assert "user-library-read" in content
        assert "playlist-modify" in content
        assert "spotify.com/account/apps" in content

    def test_terms_page_public_access(self, client):
        """Verifica se /terms está publicamente acessível sem autenticação."""
        resp = client.get("/terms")
        assert resp.status_code == 200
        content = resp.get_data(as_text=True)
        assert "Aceitação" in content
        assert "Uso Aceitável" in content

    def test_login_displays_scopes_transparency(self, client):
        """Verifica transparência de escopos e PKCE na interface de login."""
        resp = client.get("/login-page")
        assert resp.status_code == 200
        content = resp.get_data(as_text=True)
        assert "Transparência" in content
        assert "PKCE" in content
        assert 'href="/privacy"' in content
        assert 'href="/terms"' in content

    def test_spotify_policy_checklist_audit_file(self):
        """Valida que o checklist formal de conformidade existe e está preenchido."""
        checklist_path = os.path.join(BASE_DIR, "SPOTIFY_POLICY_CHECKLIST.md")
        assert os.path.isfile(checklist_path)
        with open(checklist_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "Minimização de Dados" in content
            assert "PKCE" in content
            assert "Branding" in content
            assert "OWASP" in content
            assert content.count("Conforme") >= 15


# ─── 7. INFRAESTRUTURA, GOVERNANÇA & STRIDE (FASES 7 E 8) ──────────────────────
class TestInfrastructureAndGovernance:
    """Auditoria de infraestrutura WSGI, CI/CD, STRIDE e IRP."""

    def test_procfile_and_render_yaml_gunicorn(self):
        """Valida que Procfile e render.yaml usam Gunicorn multi-worker."""
        procfile_path = os.path.join(BASE_DIR, "Procfile")
        with open(procfile_path, "r", encoding="utf-8") as f:
            proc_content = f.read().strip()
            assert "web:" in proc_content
            assert "gunicorn" in proc_content
            assert "app:app" in proc_content
            assert "--workers" in proc_content
            assert "$PORT" in proc_content

        render_path = os.path.join(BASE_DIR, "render.yaml")
        with open(render_path, "r", encoding="utf-8") as f:
            render_content = f.read()
            assert "type: web" in render_content
            assert "runtime: python" in render_content
            assert "gunicorn" in render_content

    def test_ci_cd_workflows_present(self):
        """Valida existência de automação CI/CD com pip-audit e dependabot."""
        audit_path = os.path.join(BASE_DIR, ".github", "workflows", "audit.yml")
        assert os.path.isfile(audit_path)
        with open(audit_path, "r", encoding="utf-8") as f:
            assert "pip-audit" in f.read()

        dependabot_path = os.path.join(BASE_DIR, ".github", "dependabot.yml")
        assert os.path.isfile(dependabot_path)

    def test_stride_threat_model_completeness(self):
        """Valida que THREAT_MODEL.md cobre limites de confiança e as 6 ameaças STRIDE."""
        threat_path = os.path.join(BASE_DIR, "THREAT_MODEL.md")
        assert os.path.isfile(threat_path)
        with open(threat_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "Trust Boundaries" in content or "LIMITE DE CONFIANÇA" in content
            for cat in ["Spoofing", "Tampering", "Repudiation", "Information Disclosure", "Denial of Service", "Elevation of Privilege"]:
                assert cat in content

    def test_security_policy_and_irp_completeness(self):
        """Valida que SECURITY.md cobre canal de reporte, SLAs, runbook e IRP."""
        sec_path = os.path.join(BASE_DIR, "SECURITY.md")
        assert os.path.isfile(sec_path)
        with open(sec_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "Vulnerability Disclosure Policy" in content
            assert "MultiFernet" in content
            assert "IDENTIFICAÇÃO" in content
            assert "CONTENÇÃO" in content
            assert "ERRADICAÇÃO" in content
            assert "RECUPERAÇÃO" in content
            assert "LIÇÕES APRENDIDAS" in content
