import os
import re
import json
import time
import socket
import subprocess
import urllib.parse
import secrets
import hashlib
import base64
import functools
from datetime import datetime, timezone, timedelta

from cryptography.fernet import Fernet, MultiFernet
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.errors import RateLimitExceeded
import requests as http_requests
from dotenv import load_dotenv

load_dotenv(override=True)

# ─── CONFIG & FAIL-FAST ────────────────────────────────────────────────────────
def validate_environment():
    """Valida a presença e a qualidade dos segredos essenciais antes de subir o app."""
    required_vars = [
        "SPOTIPY_CLIENT_ID",
        "SPOTIPY_CLIENT_SECRET",
        "SPOTIPY_REDIRECT_URI",
        "FLASK_SECRET_KEY",
        "ENCRYPTION_KEY",
    ]
    missing = [var for var in required_vars if not os.environ.get(var)]
    if missing:
        raise RuntimeError(
            f"FALHA DE INICIALIZAÇÃO: Variáveis obrigatórias ausentes no ambiente: {', '.join(missing)}. "
            "Consulte o arquivo .env.example para o modelo de configuração."
        )

    secret_key = os.environ["FLASK_SECRET_KEY"]
    if len(secret_key.encode("utf-8")) < 32:
        raise RuntimeError(
            "FALHA DE INICIALIZAÇÃO: FLASK_SECRET_KEY possui entropia insuficiente (mínimo de 32 bytes). "
            "Gere uma nova chave criptográfica segura com: python -c 'import secrets; print(secrets.token_hex(32))'"
        )

    # Valida que ENCRYPTION_KEY é uma chave Fernet válida (base64url de 32 bytes)
    try:
        Fernet(os.environ["ENCRYPTION_KEY"].encode())
    except Exception:
        raise RuntimeError(
            "FALHA DE INICIALIZAÇÃO: ENCRYPTION_KEY inválida. "
            "Gere com: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )

validate_environment()

CLIENT_ID     = os.environ["SPOTIPY_CLIENT_ID"]
CLIENT_SECRET = os.environ["SPOTIPY_CLIENT_SECRET"]
REDIRECT_URI  = os.environ["SPOTIPY_REDIRECT_URI"]
FLASK_ENV     = os.environ.get("FLASK_ENV", "development").lower()
IS_PRODUCTION = FLASK_ENV == "production"

# Inicializa MultiFernet com a chave do ambiente.
# MultiFernet permite rotação de chave: basta adicionar uma segunda chave ao env
# no formato "ENCRYPTION_KEY=nova,antiga" e o app descriptografa ambas, mas
# só criptografa com a nova. Quando a migração for completa, remova a chave antiga.
_fernet = MultiFernet([Fernet(os.environ["ENCRYPTION_KEY"].encode())])

# Duração máxima do cache de músicas curtidas (24 horas)
TRACKS_CACHE_TTL = timedelta(hours=24)


SCOPES = "user-library-read playlist-modify-public playlist-modify-private"

SPOTIFY_AUTH_URL  = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE  = "https://api.spotify.com/v1"

# ─── APP SETUP ────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]
app.config["SESSION_COOKIE_SAMESITE"]       = "Lax"
app.config["SESSION_COOKIE_SECURE"]         = IS_PRODUCTION   # True quando em HTTPS de produção
app.config["SESSION_COOKIE_HTTPONLY"]       = True
app.config["SESSION_PERMANENT"]             = True
app.config["PERMANENT_SESSION_LIFETIME"]    = timedelta(hours=24)  # Sessão expira em 24h

# Armazenamento de sessão: Redis se configurado com URL válida, senão filesystem
raw_redis_url = (os.environ.get("REDIS_URL") or "").strip()
VALID_REDIS_SCHEMES = ("redis://", "rediss://", "unix://")

if raw_redis_url and any(raw_redis_url.startswith(scheme) for scheme in VALID_REDIS_SCHEMES):
    try:
        import redis
        app.config["SESSION_TYPE"] = "redis"
        app.config["SESSION_REDIS"] = redis.from_url(raw_redis_url)
    except Exception as e:
        app.logger.warning("Falha ao conectar no Redis (%s). Recorrendo a sessões em filesystem.", e)
        app.config["SESSION_TYPE"] = "filesystem"
        app.config["SESSION_FILE_DIR"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".flask_session")
        app.config["SESSION_FILE_THRESHOLD"] = 100
else:
    app.config["SESSION_TYPE"] = "filesystem"
    app.config["SESSION_FILE_DIR"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".flask_session")
    app.config["SESSION_FILE_THRESHOLD"] = 100   # Mantém no máximo 100 arquivos no disco
Session(app)

# Configuração de Proxy Reverso confiável em produção (ex: Render, Gunicorn + Nginx)
if IS_PRODUCTION:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Limite máximo para payload de requisição: 1MB (Prevenção DoS / Memory exhaustion)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024


# ─── RATE LIMITING (FLASK-LIMITER) ─────────────────────────────────────────────
def get_rate_limit_key():
    """Identifica o cliente para limitação de taxa: usa o ID da sessão se logado, senão IP remoto."""
    sid = getattr(session, "sid", None)
    if sid:
        return f"sess:{sid}"
    return get_remote_address()

limiter = Limiter(
    key_func=get_rate_limit_key,
    app=app,
    default_limits=["300 per day", "60 per minute"],
    storage_uri=REDIS_URL or "memory://",
    strategy="fixed-window",
)


# ─── ERROR HANDLERS DE SEGURANÇA ───────────────────────────────────────────────
@app.errorhandler(413)
def request_entity_too_large(e):
    return jsonify({
        "success": False,
        "error": "O payload da requisição excede o limite máximo permitido de 1MB."
    }), 413


@app.errorhandler(RateLimitExceeded)
def ratelimit_handler(e):
    retry_after = getattr(e, "retry_after", 60)
    response = jsonify({
        "success": False,
        "error": "Muitas requisições. Limite de taxa excedido. Tente novamente em instantes.",
        "retry_after": retry_after
    })
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    return response


# ─── PROTEÇÃO CSRF / VALIDAÇÃO DE ORIGEM ──────────────────────────────────────
def verify_same_origin():
    """Valida se a requisição provém da mesma origem (Origin ou Referer bate com o Host).
    Protege endpoints mutáveis (POST) contra ataques Cross-Site Request Forgery."""
    origin = request.headers.get("Origin")
    referer = request.headers.get("Referer")
    host = request.host

    if origin:
        parsed_origin = urllib.parse.urlparse(origin).netloc
        if parsed_origin != host:
            return False
    elif referer:
        parsed_referer = urllib.parse.urlparse(referer).netloc
        if parsed_referer != host:
            return False
    else:
        sec_fetch_site = request.headers.get("Sec-Fetch-Site")
        if sec_fetch_site and sec_fetch_site not in ("same-origin", "same-site", "none"):
            return False

    return True


def require_same_origin(f):
    """Decorador para proteger rotas mutáveis (POST/DELETE) contra CSRF."""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not verify_same_origin():
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Requisição rejeitada por validação de segurança de origem (CSRF mismatch)."}), 403
            return "Origem da requisição inválida.", 403
        return f(*args, **kwargs)
    return decorated_function


# ─── CABEÇALHOS HTTP DE SEGURANÇA (OWASP ASVS) ────────────────────────────────
@app.after_request
def set_security_headers(response):
    """Aplica cabeçalhos HTTP defensivos para mitigar XSS, clickjacking e vazamento de dados."""
    csp = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.tailwindcss.com; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "font-src 'self' https://cdnjs.cloudflare.com; "
        "img-src 'self' data: https://*.scdn.co https://*.spotifycdn.com; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
    response.headers["Content-Security-Policy"] = csp
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

    # Proteção de cache em endpoints de API (evita retenção de dados sensíveis em caches intermediários/histórico)
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"

    # Strict-Transport-Security (HSTS) apenas em ambiente de produção com HTTPS ativo
    if IS_PRODUCTION:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

    return response


# ─── HELPERS: CRIPTOGRAFIA EM REPOUSO ─────────────────────────────────────────
def encrypt_data(data: dict) -> str:
    """Serializa um dict para JSON e criptografa com Fernet. Retorna string base64 segura para sessão."""
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return _fernet.encrypt(raw).decode("ascii")


def decrypt_data(token: str) -> dict | None:
    """Descriptografa e desserializa dados criptografados pelo encrypt_data. Retorna None em falha."""
    if not token:
        return None
    try:
        raw = _fernet.decrypt(token.encode("ascii"))
        return json.loads(raw.decode("utf-8"))
    except Exception:
        app.logger.warning("Falha ao descriptografar dado da sessão — dado descartado.")
        return None


def purge_session_file(session_id: str | None):
    """Remove fisicamente o arquivo de sessão do disco ou a chave do Redis correspondente ao session_id."""
    if not session_id:
        return
    if app.config.get("SESSION_TYPE") == "redis" and app.config.get("SESSION_REDIS"):
        try:
            r = app.config["SESSION_REDIS"]
            prefix = app.config.get("SESSION_KEY_PREFIX", "session:")
            r.delete(f"{prefix}{session_id}")
        except Exception as e:
            app.logger.warning("Falha ao expurgar sessão no Redis: %s", type(e).__name__)
        return

    session_dir = app.config.get("SESSION_FILE_DIR")
    if session_dir and os.path.isdir(session_dir):
        for fname in os.listdir(session_dir):
            if session_id in fname:
                try:
                    os.remove(os.path.join(session_dir, fname))
                except OSError:
                    pass


def get_cached_tracks() -> list[dict] | None:
    """Recupera e descriptografa as faixas do cache da sessão, validando o TTL de 24h."""
    encrypted = session.get("tracks_cache")
    if not encrypted:
        return None
    cache_payload = decrypt_data(encrypted)
    if not cache_payload or not isinstance(cache_payload, dict):
        session.pop("tracks_cache", None)
        return None

    cached_at_str = cache_payload.get("cached_at")
    if not cached_at_str:
        session.pop("tracks_cache", None)
        return None

    try:
        cached_at = datetime.fromisoformat(cached_at_str)
        if datetime.now(timezone.utc) - cached_at > TRACKS_CACHE_TTL:
            session.pop("tracks_cache", None)
            return None
    except Exception:
        session.pop("tracks_cache", None)
        return None

    return cache_payload.get("items")


def set_cached_tracks(tracks: list[dict]):
    """Criptografa e armazena as faixas minimizadas com timestamp UTC na sessão."""
    cache_payload = {
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "items": tracks,
    }
    session["tracks_cache"] = encrypt_data(cache_payload)
    session.modified = True



# ─── HELPERS: TOKEN ────────────────────────────────────────────────────────────
def get_token_from_session():
    """Retorna o access token válido da sessão, renovando se necessário.
    Os dados são descriptografados em memória e nunca ficam em texto claro no disco."""
    encrypted = session.get("token_info")
    if not encrypted:
        return None

    token_info = decrypt_data(encrypted)
    if not token_info:
        # Dado corrompido ou chave rotacionada sem fallback — encerra sessão
        session.clear()
        return None

    # Renovar se expirar nos próximos 60 segundos
    if token_info.get("expires_at", 0) - time.time() < 60:
        refreshed = refresh_token(token_info.get("refresh_token"))
        if refreshed:
            session["token_info"] = encrypt_data(refreshed)
            session.modified = True
        else:
            session.clear()
            return None
        return refreshed.get("access_token")

    return token_info.get("access_token")


def refresh_token(refresh_tok):
    """Renova o access token usando o refresh token, preservando o anterior caso não venha novo."""
    if not refresh_tok:
        return None
    try:
        response = http_requests.post(
            SPOTIFY_TOKEN_URL,
            data={
                "grant_type":    "refresh_token",
                "refresh_token": refresh_tok,
                "client_id":     CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        data["expires_at"] = int(time.time()) + data.get("expires_in", 3600)
        # Mantém refresh_token anterior se a resposta não devolver um novo
        if "refresh_token" not in data:
            data["refresh_token"] = refresh_tok
        return data
    except Exception as e:
        app.logger.error("Falha ao renovar token com Spotify: %s", type(e).__name__)
        return None


def spotify_request(method, endpoint, token, params=None, json_data=None, max_retries=3):
    """Executa requisições na Spotify Web API com tratamento de HTTP 429 (Retry-After) e backoff exponencial."""
    headers = {
        "Authorization": f"Bearer {token}",
    }
    if json_data is not None:
        headers["Content-Type"] = "application/json"

    url = f"{SPOTIFY_API_BASE}/{endpoint}" if not endpoint.startswith("http") else endpoint

    retries = 0
    backoff = 1
    while True:
        resp = http_requests.request(
            method,
            url,
            headers=headers,
            params=params or {},
            json=json_data,
            timeout=15,
        )

        if resp.status_code == 429 and retries < max_retries:
            retry_after_hdr = resp.headers.get("Retry-After")
            try:
                wait_time = int(retry_after_hdr) if retry_after_hdr else backoff
            except (ValueError, TypeError):
                wait_time = backoff
            wait_time = min(wait_time, 10)  # Teto defensivo de espera em chamadas síncronas
            app.logger.warning(
                "Spotify API 429 Too Many Requests em %s. Respeitando Retry-After: %ds (tentativa %d/%d)...",
                endpoint, wait_time, retries + 1, max_retries
            )
            time.sleep(wait_time)
            retries += 1
            backoff *= 2
            continue

        resp.raise_for_status()
        if resp.content:
            return resp.json()
        return {}


def spotify_get(endpoint, token, params=None):
    """Faz GET na Spotify Web API com o token da sessão e suporte a 429 Retry-After."""
    return spotify_request("GET", endpoint, token, params=params)


def spotify_post(endpoint, token, payload):
    """Faz POST na Spotify Web API com o token da sessão e suporte a 429 Retry-After."""
    return spotify_request("POST", endpoint, token, json_data=payload)


# ─── ROTAS DE AUTENTICAÇÃO ────────────────────────────────────────────────────
@app.route("/login")
@limiter.limit("20 per minute")
def login():
    """Redireciona o usuário para o Spotify com state anti-CSRF e PKCE S256."""
    # 1. State anti-CSRF criptograficamente seguro
    oauth_state = secrets.token_urlsafe(32)
    session["oauth_state"] = oauth_state

    # 2. PKCE (RFC 7636, S256)
    code_verifier = secrets.token_urlsafe(64)
    session["code_verifier"] = code_verifier

    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    session.modified = True

    params = {
        "client_id":             CLIENT_ID,
        "response_type":         "code",
        "redirect_uri":          REDIRECT_URI,
        "scope":                 SCOPES,
        "state":                 oauth_state,
        "code_challenge_method": "S256",
        "code_challenge":        code_challenge,
        "show_dialog":           "true",
    }
    auth_url = f"{SPOTIFY_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return redirect(auth_url)


@app.route("/callback")
@limiter.limit("20 per minute")
def callback():
    """Recebe o callback do Spotify, valida estritamente o state e troca o código via PKCE."""
    incoming_state = request.args.get("state")
    saved_state = session.get("oauth_state")

    # Validação estrita do state: rejeita se nulo, vazio ou diferente
    if not incoming_state or not saved_state or not secrets.compare_digest(incoming_state, saved_state):
        session.clear()
        return "Acesso negado: parâmetro state inválido ou expirado (CSRF mismatch).", 403

    # State válido: remove da sessão imediatamente
    session.pop("oauth_state", None)

    error = request.args.get("error")
    code  = request.args.get("code")

    if error == "access_denied":
        session.clear()
        return redirect(url_for("login_page", error="access_denied"))

    if error or not code:
        session.clear()
        return redirect(url_for("login_page", error="auth_failed"))

    code_verifier = session.pop("code_verifier", None)
    if not code_verifier:
        session.clear()
        return "Requisição inválida: code_verifier ausente.", 403

    # Troca o code por access_token + refresh_token usando PKCE e client_secret
    try:
        response = http_requests.post(
            SPOTIFY_TOKEN_URL,
            data={
                "grant_type":    "authorization_code",
                "code":          code,
                "redirect_uri":  REDIRECT_URI,
                "client_id":     CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code_verifier": code_verifier,
            },
            timeout=10,
        )
        response.raise_for_status()
        token_info = response.json()
        token_info["expires_at"] = int(time.time()) + token_info.get("expires_in", 3600)

        # Prevenção contra fixação de sessão: limpa resíduos pré-login antes de gravar credenciais
        session.clear()
        session["token_info"] = encrypt_data(token_info)
        session.modified = True
        return redirect(url_for("index"))
    except Exception as e:
        app.logger.error("Erro na troca de código OAuth: %s", type(e).__name__)
        session.clear()
        return redirect(url_for("login_page", error="auth_failed"))


@app.route("/logout", methods=["POST"])
@require_same_origin
def logout():
    """Encerra a sessão via POST, validando origem e expurgando arquivos de sessão no disco."""
    session_id = getattr(session, "sid", None)
    session.clear()
    purge_session_file(session_id)

    return redirect(url_for("login_page", logged_out="1"))


@app.route("/api/delete_my_data", methods=["POST"])
@limiter.limit("5 per minute")
@require_same_origin
def api_delete_my_data():
    """LGPD Art. 18: Exclui permanentemente todos os dados do usuário em sessão e no disco."""
    session_id = getattr(session, "sid", None)
    session.clear()
    purge_session_file(session_id)

    return jsonify({
        "success": True,
        "message": "Todos os seus dados de sessão e cache foram excluídos permanentemente."
    })


# ─── PÁGINAS HTML ─────────────────────────────────────────────────────────────
@app.route("/login-page")
def login_page():
    error = request.args.get("error")
    return render_template("login.html", error=error)


@app.route("/privacy")
def privacy_page():
    """Página pública de Política de Privacidade (LGPD Art. 18 / Spotify Developer Policy)."""
    return render_template("privacy.html")


@app.route("/terms")
def terms_page():
    """Página pública de Termos de Uso do serviço."""
    return render_template("terms.html")


@app.route("/")
def index():
    token = get_token_from_session()
    if not token:
        return redirect(url_for("login_page"))
    local_ip = get_local_ip()
    return render_template("index.html", local_ip=local_ip, port=5000)


# ─── API: USUÁRIO ──────────────────────────────────────────────────────────────
@app.route("/api/user")
def api_user():
    token = get_token_from_session()
    if not token:
        return jsonify({"authenticated": False}), 401
    try:
        user = spotify_get("me", token)
        return jsonify({
            "authenticated":  True,
            "display_name":   user.get("display_name"),
            "id":             user.get("id"),
            "images":         user.get("images", []),
            "product":        user.get("product"),
        })
    except Exception as e:
        return jsonify({"authenticated": False, "error": str(e)}), 500


# ─── API: CARREGAR MÚSICAS CURTIDAS ───────────────────────────────────────────
@app.route("/api/tracks")
@limiter.limit("15 per minute")
def api_tracks():
    token = get_token_from_session()
    if not token:
        return jsonify({"authenticated": False}), 401

    try:
        # Verificar se já temos cache válido e descriptografado na sessão
        cached_tracks = get_cached_tracks()
        if cached_tracks is not None:
            return jsonify({"total": len(cached_tracks), "tracks": cached_tracks})

        # Buscar todas as músicas curtidas (paginação)
        all_items = []
        first = spotify_get("me/tracks", token, {"limit": 50, "offset": 0})
        total = first.get("total", 0)
        all_items.extend(first.get("items", []))

        offset = 50
        while offset < total:
            page = spotify_get("me/tracks", token, {"limit": 50, "offset": offset})
            items = page.get("items", [])
            if not items:
                break
            all_items.extend(items)
            offset += len(items)

        # Processar e formatar com minimização estrita de dados (LGPD)
        tracks = []
        for item in all_items:
            track = item.get("track")
            if not track:
                continue
            added_at     = item.get("added_at", "")
            release_date = track.get("album", {}).get("release_date", "")
            release_year = release_date[:4] if release_date else "Desconhecido"

            decade = "Desconhecido"
            if release_year.isdigit():
                dec_num = (int(release_year) // 10) * 10
                decade  = f"Anos {dec_num}"

            artists = [a.get("name", "") for a in track.get("artists", []) if a.get("name")]
            tracks.append({
                "id":          track.get("id"),
                "uri":         track.get("uri"),
                "name":        track.get("name"),
                "artists":     artists,
                "artists_str": ", ".join(artists),
                "album":       track.get("album", {}).get("name", ""),
                "release_year": release_year,
                "decade":      decade,
                "popularity":  track.get("popularity", 0),
                "liked_year":  added_at[:4] if added_at else "",
            })

        # Criptografa e salva em cache na sessão com timestamp de 24h
        set_cached_tracks(tracks)

        return jsonify({"total": len(tracks), "tracks": tracks})

    except Exception as e:
        app.logger.error("Falha ao obter músicas da biblioteca Spotify: %s", type(e).__name__)
        return jsonify({"error": "Falha ao obter músicas da sua biblioteca do Spotify. Tente novamente em instantes."}), 500


# ─── API: ESTATÍSTICAS ────────────────────────────────────────────────────────
@app.route("/api/stats")
def api_stats():
    token = get_token_from_session()
    if not token:
        return jsonify({"authenticated": False}), 401

    tracks = get_cached_tracks() or []
    if not tracks:
        return jsonify({"total_tracks": 0, "decades": [], "top_artists": []})

    from collections import Counter
    decades = Counter(t.get("decade", "Desconhecido") for t in tracks)
    artists = Counter()
    for t in tracks:
        for a in t.get("artists", []):
            if a:
                artists[a] += 1

    ordered_decades = [
        {"decade": d, "count": c}
        for d, c in sorted(decades.items())
        if d != "Desconhecido"
    ]
    top_artists = [{"artist": a, "count": c} for a, c in artists.most_common(30)]

    return jsonify({
        "total_tracks": len(tracks),
        "decades":      ordered_decades,
        "top_artists":  top_artists,
    })


# ─── API: SINCRONIZAR ─────────────────────────────────────────────────────────
@app.route("/api/sync", methods=["POST"])
@limiter.limit("10 per minute")
@require_same_origin
def api_sync():
    """Remove o cache de músicas da sessão e força recarregar da API do Spotify."""
    token = get_token_from_session()
    if not token:
        return jsonify({"authenticated": False}), 401

    session.pop("tracks_cache", None)
    session.modified = True
    return jsonify({"success": True, "message": "Cache limpo! Recarregue as músicas."})


# ─── API: CRIAR PLAYLIST ──────────────────────────────────────────────────────
_TRACK_URI_REGEX = re.compile(r"^spotify:track:[a-zA-Z0-9]{22}$")

@app.route("/api/create_playlist", methods=["POST"])
@limiter.limit("5 per minute")
@require_same_origin
def api_create_playlist():
    token = get_token_from_session()
    if not token:
        return jsonify({"authenticated": False}), 401

    if not request.is_json:
        return jsonify({"success": False, "error": "Requisição deve ser enviada como application/json."}), 400

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Corpo da requisição deve ser um objeto JSON válido."}), 400

    raw_name = data.get("name")
    if not isinstance(raw_name, str) or not raw_name.strip():
        return jsonify({"success": False, "error": "O nome da playlist é obrigatório."}), 400
    name = raw_name.strip()
    if len(name) > 100:
        return jsonify({"success": False, "error": "O nome da playlist não pode exceder 100 caracteres."}), 400

    raw_desc = data.get("description", "Criada via Playlist Manager for Spotify")
    description = str(raw_desc).strip() if raw_desc is not None else ""
    if len(description) > 300:
        return jsonify({"success": False, "error": "A descrição não pode exceder 300 caracteres."}), 400

    is_public = bool(data.get("is_public", False))
    track_uris = data.get("track_uris")

    if not isinstance(track_uris, list) or len(track_uris) == 0:
        return jsonify({"success": False, "error": "Nenhuma música selecionada para a playlist."}), 400

    if len(track_uris) > 1000:
        return jsonify({"success": False, "error": "Limite máximo de 1.000 músicas por criação excedido."}), 400

    # Filtrar apenas URIs estritamente válidas de faixas do Spotify
    valid_uris = [u for u in track_uris if isinstance(u, str) and _TRACK_URI_REGEX.match(u)]

    if not valid_uris:
        return jsonify({"success": False, "error": "Nenhuma música com URI válida do Spotify foi fornecida."}), 400

    try:
        user_info = spotify_get("me", token)
        user_id   = user_info.get("id")

        payload = {
            "name":        name,
            "public":      is_public,
            "description": description,
        }

        # Tentativa 1: Endpoint moderno /me/playlists
        playlist = None
        try:
            playlist = spotify_post("me/playlists", token, payload)
        except Exception as e1:
            app.logger.warning("Tentativa em me/playlists falhou: %s. Tentando alternativas...", type(e1).__name__)
            # Tentativa 2: Tentar como privada se pública foi rejeitada por falta de scope
            if is_public:
                try:
                    payload["public"] = False
                    playlist = spotify_post("me/playlists", token, payload)
                except Exception:
                    pass
            # Tentativa 3: Endpoint /users/{user_id}/playlists
            if not playlist and user_id:
                playlist = spotify_post(f"users/{user_id}/playlists", token, payload)

        if not playlist or "id" not in playlist:
            raise RuntimeError("Não foi possível criar a playlist no Spotify.")

        playlist_id  = playlist["id"]
        playlist_url = playlist.get("external_urls", {}).get("spotify", "")

        # Adicionar faixas em lotes de 100 com suporte a 429 Retry-After e backoff
        for i in range(0, len(valid_uris), 100):
            chunk = valid_uris[i:i + 100]
            try:
                spotify_post(f"playlists/{playlist_id}/items", token, {"uris": chunk})
            except Exception as ep_err:
                # Fallback caso endpoint legado /tracks seja exigido
                if hasattr(ep_err, "response") and ep_err.response is not None and ep_err.response.status_code == 404:
                    spotify_post(f"playlists/{playlist_id}/tracks", token, {"uris": chunk})
                else:
                    raise ep_err

        return jsonify({
            "success":      True,
            "playlist_id":  playlist_id,
            "playlist_url": playlist_url,
            "total_added":  len(valid_uris),
        })

    except Exception as e:
        app.logger.error("Falha ao criar playlist no Spotify: %s", type(e).__name__)
        # Sanitizar mensagem: se a exceção contém resposta da API Spotify com mensagem amigável, exibir de forma limpa
        user_msg = "Não foi possível criar a playlist no Spotify. Tente novamente mais tarde."
        if hasattr(e, "response") and e.response is not None:
            try:
                err_data = e.response.json()
                api_msg = err_data.get("error", {}).get("message")
                if api_msg:
                    user_msg = f"Spotify: {api_msg}"
            except Exception:
                pass
        return jsonify({"success": False, "error": user_msg}), 500


# ─── UTILITÁRIOS ──────────────────────────────────────────────────────────────
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def free_port(port=5000):
    """Encerra com segurança processos locais antigos ocupando a porta em modo de desenvolvimento."""
    if IS_PRODUCTION:
        return
    try:
        proc = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, check=False)
        port_pattern = f":{port}"
        for line in proc.stdout.splitlines():
            if "LISTENING" in line and port_pattern in line:
                parts = line.strip().split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    if pid.isdigit() and int(pid) != os.getpid():
                        print(f"[DEV] Porta {port} ocupada pelo PID {pid}. Encerrando...")
                        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, check=False)
                        time.sleep(1)
    except Exception as e:
        print(f"[AVISO] Não foi possível verificar liberação da porta {port}: {e}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────
# Em produção (ex: Render/Linux), use um servidor WSGI real:
# gunicorn -w 4 -b 0.0.0.0:$PORT app:app
if __name__ == "__main__":
    free_port(5000)
    
    allow_lan = os.environ.get("ALLOW_LAN_ACCESS", "false").lower() == "true"
    host = "0.0.0.0" if (allow_lan and not IS_PRODUCTION) else "127.0.0.1"
    
    print("=" * 60)
    print(" SERVIDOR MULTI-USUÁRIO INICIADO (DESENVOLVIMENTO)")
    print(f" Ambiente: {'PRODUÇÃO' if IS_PRODUCTION else 'DESENVOLVIMENTO'}")
    print(f" Interface de escuta: {host}:5000")
    print(f" Acesso no computador: http://127.0.0.1:5000")
    
    if host == "0.0.0.0":
        local_ip = get_local_ip()
        print(f" Acesso LAN (celular no mesmo Wi-Fi): http://{local_ip}:5000")
        print(" [AVISO DE SEGURANÇA] Escuta 0.0.0.0 ativada via ALLOW_LAN_ACCESS=true.")
    else:
        print(" [INFO] Escuta restrita a localhost (127.0.0.1) para máxima segurança.")
    print("=" * 60)
    
    app.run(host=host, port=5000, debug=False)
