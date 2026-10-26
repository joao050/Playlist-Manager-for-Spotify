import os
import sys
import time
import pytest

# Assegura que o diretório raiz esteja no sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Injeta variáveis de ambiente padrão para testes automatizados
os.environ.setdefault("SPOTIPY_CLIENT_ID", "mock_client_id_for_testing_purposes")
os.environ.setdefault("SPOTIPY_CLIENT_SECRET", "mock_client_secret_for_testing_purposes")
os.environ.setdefault("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:5000/callback")
os.environ.setdefault("FLASK_SECRET_KEY", "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef")
os.environ.setdefault("FLASK_ENV", "development")

# Chave Fernet mock válida (32 bytes em Base64 URL-safe) para testes
VALID_TEST_FERNET_KEY = "MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDE="
from cryptography.fernet import Fernet
try:
    Fernet(os.environ.get("ENCRYPTION_KEY", "").encode())
except Exception:
    os.environ["ENCRYPTION_KEY"] = VALID_TEST_FERNET_KEY

import app as spotify_app

@pytest.fixture(scope="session")
def app():
    """Retorna a instância do Flask app configurada para testes."""
    spotify_app.app.config.update({
        "TESTING": True,
        "DEBUG": False,
    })
    return spotify_app.app

@pytest.fixture(autouse=True)
def reset_limiter_and_state():
    """Reseta o rate limiter antes de cada teste para isolamento de testes."""
    spotify_app.limiter.reset()
    yield
    spotify_app.limiter.reset()

@pytest.fixture
def client(app):
    """Cliente de teste Flask sem autenticação."""
    return app.test_client()

@pytest.fixture
def auth_client(app):
    """Cliente de teste Flask com sessão autenticada mockada."""
    client = app.test_client()
    dummy_token = {
        "access_token": "mock_access_token_12345",
        "refresh_token": "mock_refresh_token_67890",
        "expires_at": int(time.time()) + 3600
    }
    with client.session_transaction() as sess:
        sess["token_info"] = spotify_app.encrypt_data(dummy_token)
        sess["user_id"] = "test_user_spotify_id"
    return client
