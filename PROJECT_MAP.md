# PROJECT_MAP.md — Playlist Manager for Spotify

## 1. Visão Geral
Aplicação web BFF (Backend-For-Frontend) em Flask que autentica usuários via Spotify OAuth 2.0 + PKCE, carrega músicas curtidas com cache criptografado em repouso e permite filtrar (década, artista, popularidade, ano) e criar playlists diretamente na conta do Spotify.
- **Stack:** Python 3.14, Flask 3.1, Flask-Session (filesystem/redis), Requests, Cryptography (Fernet), Tailwind CSS (CDN), Vanilla JS.
- **Como Rodar:** `python app.py` (desenvolvimento local em `http://127.0.0.1:5000`) ou `gunicorn -w 4 -b 0.0.0.0:$PORT app:app` (produção).

## 2. Árvore Comentada
```text
playlist-manager-for-spotify/
├── .agent/rules/                # Regras automáticas do workspace para o Antigravity
├── .flask_session/              # Sessões locais no disco (arquivos cifrados, NUNCA ler manualmente)
├── templates/
│   ├── index.html               # UI principal: tabela de músicas, filtros, modal de criação, LGPD delete
│   ├── login.html               # UI de autenticação: login OAuth, banners de erro e alertas pós-logout/LGPD
│   ├── privacy.html             # Política de Privacidade pública (LGPD Art. 18 / Spotify Developer Policy)
│   └── terms.html               # Termos de Uso públicos do serviço
├── static/
│   └── js/app.js                # Frontend Vanilla JS isolado (DOM API, zero inline handlers, anti-DOM-XSS)
├── tests/
│   ├── conftest.py              # Fixtures reutilizáveis do pytest (app, client, auth_client, reset_limiter)
│   └── test_security.py         # Suíte integrada consolidada (Fase 9 — 32 testes de regressão de segurança)
├── .github/
│   ├── workflows/audit.yml      # CI/CD: auditoria pip-audit e suíte de testes automatizados (pytest)
│   └── dependabot.yml           # Dependabot: monitoramento semanal de segurança de dependências
├── Procfile                     # Declaração do processo WSGI Gunicorn multi-worker para produção
├── render.yaml                  # Especificação declarativa de infraestrutura (Render Blueprint)
├── pytest.ini                   # Configuração declarativa do pytest
├── app.py                       # Ponto de entrada backend: rotas, OAuth, BFF, criptografia e integração Spotify
├── requirements.txt             # Dependências Python pinadas (versões fixas)
├── LICENSE                      # Licença oficial MIT do projeto
├── .env                         # Segredos e configuração do ambiente local (NUNCA versionar/ler valores)
├── .env.example                 # Modelo de configuração sem credenciais
├── .gitignore                   # Exclusão de segredos, caches e arquivos de sessão
├── PROJECT_MAP.md               # [Este arquivo] Mapa de navegação e arquitetura para IA
├── PROJECT_TASKS.md             # Registro vivo de tarefas, backlog e decisões
├── SECURITY_CHANGELOG.md        # Histórico detalhado de endurecimento de segurança (Fases 0 a 9)
├── SPOTIFY_POLICY_CHECKLIST.md  # Checklist formal de conformidade com as diretrizes do Spotify
├── THREAT_MODEL.md              # Modelagem formal de ameaças STRIDE e limites de confiança
├── SECURITY.md                  # Governança, política de divulgação, runbook de rotação e IRP
└── tests/test_security.py       # Suíte integrada consolidada (Fase 9 — 32 testes de regressão de segurança)
```

## 3. Mapa por Funcionalidade
| Funcionalidade | Arquivo : Função / Trecho |
| :--- | :--- |
| Validação de ambiente & fail-fast | `app.py:validate_environment()` |
| Headers de segurança HTTP (CSP, HSTS, etc.) | `app.py:set_security_headers()` |
| Proteção de payload (1MB) & 413 | `app.py:request_entity_too_large()`, `app.config[MAX_CONTENT_LENGTH]` |
| Rate Limiting por sessão/IP | `app.py:limiter`, `app.py:get_rate_limit_key()`, `app.py:ratelimit_handler()` |
| Proteção CSRF / Origem em POSTs | `app.py:verify_same_origin()`, `app.py:require_same_origin()` |
| Backoff 429 Retry-After Spotify | `app.py:spotify_request()` |
| Criptografia de dados em repouso | `app.py:encrypt_data()`, `app.py:decrypt_data()` |
| Expulso físico de arquivos de sessão | `app.py:purge_session_file()` |
| Cache de faixas curtidas (TTL 24h) | `app.py:get_cached_tracks()`, `app.py:set_cached_tracks()` |
| Gestão e renovação de tokens | `app.py:get_token_from_session()`, `app.py:refresh_token()` |
| Requisições autenticadas Spotify | `app.py:spotify_get()`, `app.py:spotify_post()` |
| Início login OAuth (State + PKCE) | `app.py:login()` |
| Callback OAuth (Validação + Troca) | `app.py:callback()` |
| Encerramento de sessão seguro (POST) | `app.py:logout()` |
| Exclusão definitiva de dados (LGPD) | `app.py:api_delete_my_data()`, `static/js/app.js:deleteMyData()` |
| Perfil do usuário logado | `app.py:api_user()`, `static/js/app.js:loadUser()` |
| Carregamento e minimização de faixas| `app.py:api_tracks()`, `static/js/app.js:loadTracksAndStats()` |
| Estatísticas para filtros | `app.py:api_stats()`, `static/js/app.js:loadStats()` |
| Limpeza forçada de cache | `app.py:api_sync()`, `static/js/app.js:syncLibrary()` |
| Criação de playlist no Spotify | `app.py:api_create_playlist()`, `static/js/app.js:confirmCreatePlaylist()` |
| Interface e filtros dinâmicos (DOM API) | `static/js/app.js:applyFilters()`, `static/js/app.js:renderTable()` |
| Página e avisos de login/logout/LGPD | `templates/login.html` |
| Política de Privacidade (pública) | `app.py:privacy_page()`, `templates/privacy.html` |
| Termos de Uso (públicos) | `app.py:terms_page()`, `templates/terms.html` |
| Suíte Integrada com Pytest | `tests/test_security.py`, `tests/conftest.py`, `pytest.ini` |

## 4. Fluxo de Dados
1. **Login:** Usuário acessa `/login` → Gera `state` e PKCE (`code_verifier` + `code_challenge`) salvos na sessão → Redireciona para `accounts.spotify.com/authorize`.
2. **Autorização:** Spotify redireciona para `/callback` → Valida `state` via `compare_digest` → Troca código por tokens usando `code_verifier` + `client_secret` → `session.clear()` (anti-fixação) → Criptografa `token_info` com Fernet → Salva na sessão → Redireciona para `/`.
3. **Consulta de Faixas:** Frontend chama `GET /api/tracks` → Backend valida access token (renova via refresh token se faltar <60s) → Checa `get_cached_tracks()`:
   - Se em cache válido (<24h): Descriptografa e retorna faixas minimizadas.
   - Se expirado/inexistente: Pagina `/v1/me/tracks` na API do Spotify → Minimiza campos → Criptografa com timestamp UTC em `tracks_cache` → Retorna JSON.
4. **Criação de Playlist:** Frontend envia POST `/api/create_playlist` (nome, desc, público/privado, lista de URIs) → Backend cria playlist via POST `/v1/me/playlists` (fallback `/users/{id}/playlists`) → Adiciona faixas em lotes de 100 via POST `/v1/playlists/{id}/items` (fallback `/tracks`).
5. **Eliminação de Dados:** POST `/api/delete_my_data` → Valida `Origin`/`Referer` → `session.clear()` → Remove fisicamente arquivo em `.flask_session/` (ou chave no Redis).

## 5. Dependências Entre Módulos
- `app.py` ⇄ `.env`: Inicialização lê segredos via `python-dotenv`.
- `app.py` ⇄ `templates/*.html`: Renderiza views Jinja2 e serve como API JSON para chamadas fetch do front.
- `app.py` ⇄ Spotify Web API: Comunicação HTTPS síncrona com `requests` (timeout=10s).
- `app.py` ⇄ Flask-Session: Persistência de sessão em filesystem local ou Redis.

## 6. Pontos Sensíveis
- **Segredos (`.env`):** `SPOTIPY_CLIENT_SECRET`, `FLASK_SECRET_KEY`, `ENCRYPTION_KEY`. NUNCA logar, imprimir ou comitar.
- **Endpoints do Spotify:** `/playlists/{id}/items` é o endpoint moderno obrigatório; o antigo `/tracks` retorna 403 Forbidden para novos apps registrados.
- **Session ID (`session.sid`):** Usado para limpeza física de arquivo em disco; deve ser manipulado com cautela.
- **Criptografia:** `ENCRYPTION_KEY` deve ser chave válida Fernet base64url de 32 bytes. Se alterada sem `MultiFernet`, invalida sessões anteriores.

## 7. Guia "Se for X, mexa em Y"
| Se a tarefa for... | Mexa em... | Detalhes / Cuidados |
| :--- | :--- | :--- |
| Adicionar/alterar rota de API | `app.py` | Validar token via `get_token_from_session()`, sanitizar inputs, tratar erros sem vazar traces |
| Alterar filtros ou paginação na UI | `templates/index.html` | Funções `applyFilters()`, `renderTable()`, `changePage()` |
| Ajustar criação de playlist no Spotify | `app.py:api_create_playlist()` | Manter chunking de 100 itens e endpoint `/items` |
| Modificar regras de expiração ou sessão| `app.py` (config do app e helpers) | `PERMANENT_SESSION_LIFETIME`, `TRACKS_CACHE_TTL` |
| Alterar aparência/estilo | `templates/index.html` ou `login.html` | Classes Tailwind CSS e tags FontAwesome |
| Configurar deploy / produção | `.env.example`, `requirements.txt` | ProxyFix, gunicorn, `REDIS_URL`, `IS_PRODUCTION` |
| Adicionar testes de segurança | `tests/test_security.py` ou `test_phase*.py` | Usar `pytest` com fixtures de `tests/conftest.py` simulando cenários sem bater na API externa |

## 8. Arquivos a NUNCA Ler Sem Necessidade
- `.flask_session/*`: Arquivos binários/cifrados temporários de sessão de usuário.
- `__pycache__/*`: Bytecode compilado do Python.
- `.env`: Segredos e chaves locais reais (nunca expor).

## 9. Ambiente de Homologação e Testes Físico (Samsung Galaxy J6 Server)
- **Localização da Infraestrutura:** `C:\Users\ADM\.gemini\antigravity\scratch\galaxy-j6-server`
- **Dispositivo:** Samsung Galaxy J6 (Exynos 7870 / Termux Linux ARMv7 / Python 3.14).
- **Finalidade:** Servir como micro-servidor local e staging físico para testar o site e o fluxo BFF em um dispositivo Linux dedicado.
- **Conectividade:**
  - **Cabo USB (ADB Forward):** O comando `adb forward tcp:5000 tcp:5000` permite acessar o app rodando no celular via `http://127.0.0.1:5000` no PC, preservando a `SPOTIPY_REDIRECT_URI` padrão sem necessidade de alterar o painel do Spotify.
  - **Rede Wi-Fi (LAN):** Acesso simultâneo via IP local na porta `5000` (com `ALLOW_LAN_ACCESS=true`).
- **Automação Desacoplada:** Os scripts de sincronização e controle (`deploy-spotify.ps1`, `logs-spotify.ps1`, `parar-spotify.ps1`) residem exclusivamente no projeto do servidor, mantendo o repositório do Playlist Manager for Spotify 100% puro para versionamento no GitHub.

