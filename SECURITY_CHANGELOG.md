# Registro de Mudanças de Segurança (SECURITY_CHANGELOG.md)

Este documento registra todas as alterações de segurança implementadas no **Playlist Manager for Spotify**, estruturado em fases auditáveis.

---

## [FASE 0] — Diagnóstico de Segurança (Linha de Base)
* **Data:** 19/10/2026
* **Status:** Concluído sem edições de código.
* **Achados Registrados:**
  1. Fallback inseguro de `FLASK_SECRET_KEY` hardcoded em `app.py`.
  2. Ausência de validação fail-fast de variáveis críticas (`SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, `SPOTIPY_REDIRECT_URI`).
  3. `get_current_redirect_uri()` com detecção dinâmica frágil por cabeçalhos e substrings.
  4. Ausência de `state` e PKCE no fluxo OAuth.
  5. Tokens e cache de músicas gravados em texto claro no disco (`.flask_session/`).
  6. `session.clear()` mantém resíduo de 9 bytes no disco (não expurga arquivos órfãos).
  7. Concatenação insegura em `innerHTML` e atributos `title` no frontend (`index.html`).
  8. `free_port()` utilizando `shell=True` com comandos do sistema operacional.

---

## [FASE 1] — Configuração e Gestão de Segredos
* **Data:** 19/10/2026
* **Status:** Concluído.

### Alterações Realizadas:

#### 1. `app.py`
* **O quê:**
  - Implementada função `validate_environment()` com fail-fast estrito: exige `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, `SPOTIPY_REDIRECT_URI` e `FLASK_SECRET_KEY`.
  - Validação de entropia mínima de 32 bytes para `FLASK_SECRET_KEY`.
  - Removido segredo hardcoded `spotify-multiuser-secret-2026-xZ9kLmP`.
  - Removida função `get_current_redirect_uri()` e inspeção de cabeçalhos arbitrários. O app agora consome exclusivamente `REDIRECT_URI` fixo por ambiente.
  - Integrado `werkzeug.middleware.proxy_fix.ProxyFix` ativado apenas em ambiente de produção (`FLASK_ENV=production`).
  - Reescrita a rotina `free_port()` sem `shell=True`, utilizando listas de argumentos e restrita a modo de desenvolvimento (`not IS_PRODUCTION`).
  - Configurado bind padrão em `127.0.0.1` (localhost). O bind em `0.0.0.0` é ativado apenas se `ALLOW_LAN_ACCESS=true` for explicitamente declarado em desenvolvimento, com alerta de segurança no console.
* **Por quê:** Eliminar credenciais padrão conhecidas, prevenir desvio de OAuth via *Host Header Poisoning*, bloquear injeção de comandos via shell e impedir exposição desnecessária em interfaces de rede públicas.
* **Como verificar:**
  - Teste automatizado de remoção de `FLASK_SECRET_KEY` do `.env` -> app aborta com `RuntimeError`.
  - Teste com chave menor que 32 bytes -> app aborta com `RuntimeError`.
  - Inicialização padrão -> escuta em `127.0.0.1:5000`.

#### 2. `.env.example`
* **O quê:** Criação de arquivo modelo sem nenhum valor real ou segredo, documentando cada variável necessária (`FLASK_SECRET_KEY`, `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, `SPOTIPY_REDIRECT_URI`, `ENCRYPTION_KEY`, `FLASK_ENV`, `ALLOW_LAN_ACCESS`).
* **Por quê:** Guiar novos deploys e desenvolvedores sem risco de vazamento de credenciais.
* **Como verificar:** Verificar existência de `.env.example` e ausência de segredos reais.

#### 3. `.gitignore`
* **O quê:** Adição explícita de `.env`, `.env.local`, `.cache`, `.flask_session/`, `test_flask_session_dir/`, `*.pyc`, `*.pyo`, `.pytest_cache/`, `.coverage`.
* **Por quê:** Garantir que nenhum arquivo temporário, de teste ou contendo segredos seja rastreado pelo Git.
* **Como verificar:** Inspecionar arquivo `.gitignore`.

#### 4. `requirements.txt`
* **O quê:** Fixação estrita (pinned) das versões de todas as dependências (`flask==3.1.3`, `flask-session==0.8.0`, `requests==2.34.2`, `python-dotenv==1.2.4`, `cachelib==0.17.0`, `gunicorn==23.0.0`, `spotipy==2.26.0`).
* **Por quê:** Evitar quebras e vulnerabilidades introduzidas por atualizações automáticas não testadas (segurança da cadeia de suprimentos / supply chain).
* **Como verificar:** Inspecionar `requirements.txt`.

---

## [FASE 2] — Endurecimento do Fluxo OAuth 2.0 / PKCE
* **Data:** 19/10/2026
* **Status:** Concluído.

### Alterações Realizadas:

#### 1. `app.py`
* **O quê:**
  - **Parâmetro `state` anti-CSRF:** Rota `/login` gera `secrets.token_urlsafe(32)` e salva na sessão. No `/callback`, validação estrita com `secrets.compare_digest(incoming, saved)`. Se ausente, vazio ou diferente, aborta com HTTP 403 (protegido contra condição `vazio == vazio`).
  - **PKCE (RFC 7636, S256):** Gera `code_verifier` (64 bytes / 86 caracteres urlsafe) e `code_challenge = Base64URL(SHA256(verifier))` sem padding. Envia `code_challenge` e `code_challenge_method=S256` no `/login`. Na troca de código (`/callback`), envia `code_verifier` junto com `client_secret` e credenciais.
  - **Prevenção de Fixação de Sessão:** No `/callback`, logo após validar o `state` e antes de salvar `token_info`, executa `session.clear()`, garantindo que nenhum identificador pré-autenticação persista.
  - **Sanitização de Erros:** Removido vazamento de `str(e)` na query string. Agora redireciona com códigos de erro pré-definidos (`access_denied`, `auth_failed`).
  - **Logout Seguro:** Rota `/logout` alterada para aceitar exclusivamente `POST` (requisições `GET` retornam HTTP 405). Adicionada validação de `Origin`/`Referer` contra o host do servidor. Executa `session.clear()` e expurgo físico dos arquivos de sessão no disco (`.flask_session/`).
  - **Timeouts e Logs Seguros:** Adicionado `timeout=10` em todas as chamadas `requests` de autenticação e logs que registram apenas a classe da exceção, sem dados sensíveis.
* **Por quê:** Eliminar vulnerabilidade de Login CSRF, impedir interceptação de códigos de autorização em trânsito (PKCE), bloquear ataques de fixação de sessão e garantir logout definitivo com expurgo de dados em repouso.
* **Como verificar:** Testes automatizados cobrindo `/login` (geração de `state` e `code_challenge`), `/callback` sem/com `state` inválido (HTTP 403), `/logout` por GET (HTTP 405) e por POST (HTTP 302 com limpeza de sessão).

#### 2. `templates/index.html`
* **O quê:** Botão de logout convertido de tag `<a>` simples para formulário `<form action="/logout" method="POST">` estilizado.
* **Por quê:** Prevenir ataques de logout CSRF disparados por navegação acidental ou pré-carregamento de links por navegadores/rastreadores.
* **Como verificar:** Inspecionar o botão de saída no cabeçalho de `index.html`.

#### 3. `templates/login.html`
* **O quê:** Mapeamento de mensagens fixas de erro (`access_denied`, `auth_failed`, etc.) sem uso de filtros inseguros `|safe`, e inclusão de aviso informativo com link oficial de revogação de permissões (`https://www.spotify.com/account/apps/`) quando o usuário encerra a sessão.
* **Por quê:** O Spotify Web API não disponibiliza endpoint de revogação programática de tokens; orientar o usuário onde revogar seu consentimento é exigência de privacidade e transparência (LGPD/GDPR e Políticas do Spotify).
* **Como verificar:** Testar acessos a `/login-page?error=access_denied` e `/login-page?logged_out=1`.

---

## [FASE 3] — Sessão, Tokens e Dados em Repouso (Criptografia & LGPD)
* **Data:** 19/10/2026
* **Status:** Concluído.

### Alterações Realizadas:

#### 1. Criptografia em Repouso com `MultiFernet` (`app.py`)
* **O quê:**
  - Integração da biblioteca padrão `cryptography.fernet` (`Fernet`, `MultiFernet`).
  - Validação da variável obrigatória `ENCRYPTION_KEY` na inicialização do app (`validate_environment()`).
  - Criação dos helpers `encrypt_data(dict)` e `decrypt_data(str)`: todo payload sensível salvo na sessão do Flask é serializado em JSON, cifrado com algoritmo Fernet (AES-128 em modo CBC com autenticação HMAC-SHA256) e armazenado cifrado.
  - `token_info` (access token, refresh token e tempo de expiração) e o cache `tracks_cache` são criptografados antes de tocar o disco. Se o servidor for desligado, roubado ou o diretório `.flask_session/` for inspecionado, os arquivos contêm apenas cifras ilegíveis.
  - Uso de `MultiFernet` para viabilizar rotação de chaves sem downtime.
* **Por quê:** Atender ao princípio de confidencialidade e segurança de dados pessoais em repouso exigido pela LGPD/GDPR e pelas diretrizes de segurança da Spotify Developer Policy.
* **Como verificar:**
  - `python test_phase3.py` testa que o texto cifrado gerado não contém nenhuma ocorrência de `access_token` ou `refresh_token` e que o dado é recuperado fielmente após descriptografia.

#### 2. Minimização de Dados e TTL de Cache de 24 Horas (`app.py`)
* **O quê:**
  - O cache de músicas curtidas `tracks_cache` agora adota estrita minimização de dados: remove metadados brutos e campos não utilizados pela UI, mantendo exclusivamente (`id`, `uri`, `name`, `artists`, `artists_str`, `album`, `release_year`, `decade`, `popularity`, `liked_year`).
  - Adicionado timestamp UTC `cached_at` e constante `TRACKS_CACHE_TTL = timedelta(hours=24)`.
  - O helper `get_cached_tracks()` verifica o TTL a cada leitura: dados com mais de 24 horas são expurgados da sessão automaticamente.
* **Por quê:** Cumprimento direto dos princípios de **Minimização de Dados** e **Limitação do Armazenamento** (LGPD Art. 6º, III e Spotify Developer Terms sobre expiração de caches).
* **Como verificar:**
  - Teste automatizado em `test_phase3.py` simulando payload gravado há 25h: `get_cached_tracks()` retorna `None` e descarta a chave da sessão.

#### 3. Parâmetros Estritos de Cookie e Sessão (`app.py`)
* **O quê:**
  - Declarados explicitamente `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SAMESITE = "Lax"`, `SESSION_COOKIE_SECURE = IS_PRODUCTION`.
  - Ativado `SESSION_PERMANENT = True` com `PERMANENT_SESSION_LIFETIME = timedelta(hours=24)`.
  - Configurado `SESSION_FILE_THRESHOLD = 100` no backend filesystem do Flask-Session para reciclagem automática de sessões antigas no disco.
  - Implementado suporte transparente e nativo a backend de sessão via **Redis** se a variável de ambiente `REDIS_URL` for informada (ideal para deploys em nuvem como Render ou Kubernetes).
* **Por quê:** Blindar cookies de sessão contra roubo via XSS (`HttpOnly`), mitigar CSRF (`SameSite=Lax`), forçar HTTPS em produção (`Secure`) e evitar acúmulo descontrolado de arquivos órfãos em disco.

#### 4. Direito de Exclusão — LGPD Art. 18 (`app.py`, `templates/index.html`, `templates/login.html`)
* **O quê:**
  - Criado o endpoint seguro `POST /api/delete_my_data` com validação de cabeçalhos de origem (`Origin`/`Referer`).
  - Quando chamado, a função `purge_session_file()` localiza e remove fisicamente o arquivo correspondente ao `session.sid` no disco (ou deleta a chave no Redis) e executa `session.clear()`.
  - Adicionado botão visível no cabeçalho do app: **"Excluir Dados"** com confirmação de segurança.
  - Criado alerta visual dedicado na tela de login informando que os dados foram totalmente destruídos conforme a LGPD.
* **Por quê:** Cumprimento do Art. 18 da LGPD (Direito do titular à eliminação de dados pessoais tratados com consentimento).
* **Como verificar:**
  - Chamar `POST /api/delete_my_data` com Origin inválido -> retorna 403.
  - Chamar autenticado com Origin válido -> retorna 200, destrói o arquivo em disco e zera a sessão.

#### 5. Dependências e Configuração (`requirements.txt`, `.env.example`)
* **O quê:**
  - Adicionada a dependência `cryptography==50.0.2` e documentado `redis==8.1.0` em `requirements.txt`.
  - Adicionados exemplos e instruções de geração de `ENCRYPTION_KEY` e suporte a `REDIS_URL` em `.env.example`.
* **Por quê:** Reprodutibilidade e documentação completa de ambiente.

---

## [FASE 4] — Proteção da API, Rate Limiting e Prevenção de Abuso
* **Data:** 21/10/2026
* **Status:** Concluído.

### Alterações Realizadas:

#### 1. Rate Limiting por Sessão e IP (`app.py`, `requirements.txt`)
* **O quê:**
  - Integração da biblioteca `flask-limiter==4.1.1` com chave de identificação híbrida inteligente (`get_rate_limit_key`): prioriza `session.sid` para usuários autenticados e recorre a `get_remote_address` para acessos anônimos.
  - Limites defensivos configurados por rota:
    - `/login` e `/callback`: 20 requisições por minuto.
    - `/api/tracks`: 15 requisições por minuto.
    - `/api/sync`: 10 requisições por minuto.
    - `/api/create_playlist` e `/api/delete_my_data`: 5 requisições por minuto.
  - Handler customizado para `RateLimitExceeded` devolvendo status HTTP 429, payload JSON amigável e cabeçalho padrão `Retry-After`.
* **Por quê:** Mitigar ataques de força bruta, spam de requisições, scraping excessivo e negação de serviço (DoS), protegendo as cotas da aplicação perante o Spotify.
* **Como verificar:** `python test_phase4.py` executa rajada de 15 requisições em rota limitada e valida retorno HTTP 429 com cabeçalho `Retry-After`.

#### 2. Limite Máximo de Payload (1MB) e Tratamento de 413 (`app.py`)
* **O quê:**
  - Declarado `app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024` (1MB).
  - Handler customizado `@app.errorhandler(413)` devolvendo JSON padronizado com mensagem clara em vez de encerramento abrupto da conexão.
* **Por quê:** Bloquear payloads gigantescos enviados por atacantes para exaustão de memória no servidor (Memory Exhaustion / DoS).
* **Como verificar:** `python test_phase4.py` envia payload de 1MB + 1KB e valida bloqueio com HTTP 413.

#### 3. Proteção CSRF Unificada em Métodos Mutáveis (`app.py`)
* **O quê:**
  - Criação do decorador `@require_same_origin` e helper `verify_same_origin()`: inspeciona cabeçalhos `Origin`, `Referer` e `Sec-Fetch-Site` contra o host do servidor.
  - Aplicado a todos os endpoints mutáveis (`POST`): `/logout`, `/api/delete_my_data`, `/api/sync` e `/api/create_playlist`. Rejeita origens externas/fraudulentas com HTTP 403.
* **Por quê:** Defesa em profundidade contra Cross-Site Request Forgery (CSRF), operando em conjunto com cookies de sessão `SameSite=Lax`.
* **Como verificar:** `python test_phase4.py` realiza disparos POST com `Origin: https://attacker-site.com` e comprova rejeição imediata com HTTP 403.

#### 4. Validação Estrita de Payload em `/api/create_playlist` (`app.py`)
* **O quê:**
  - Validação de cabeçalho `Content-Type: application/json` e desserialização estrita de objeto JSON.
  - Validação de tamanho e sanitização: `name` obrigatório (1 a 100 caracteres), `description` opcional (máximo 300 caracteres).
  - `track_uris` restrito a uma lista não-vazia contendo entre 1 e 1.000 itens.
  - Validação individual de cada URI via expressão regular estrita: `^spotify:track:[a-zA-Z0-9]{22}$`. Entradas fora do padrão são descartadas ou rejeitadas com HTTP 400.
  - Sanitização de respostas de erro na integração com o Spotify: detalhes internos de stack trace são retidos no logger e apenas mensagens amigáveis são retornadas ao cliente.
* **Por quê:** Impedir injeção de parâmetros maliciosos, estouro de timeouts da API do Spotify e vazamento de detalhes internos da infraestrutura.
* **Como verificar:** `python test_phase4.py` testa cenários de payload não-JSON, nome ausente/longo, descrição excessiva, lista vazia, excesso de faixas (>1000) e URIs malformadas, garantindo retorno 400 em todos os casos.

#### 5. Respeito ao `Retry-After` (HTTP 429) com Backoff Exponencial (`app.py`)
* **O quê:**
  - Implementada função centralizadora `spotify_request()` para requisições GET e POST na API do Spotify.
  - Em caso de resposta HTTP 429 (*Too Many Requests*), a função lê o cabeçalho `Retry-After`, aplica pausa síncrona defensiva (`time.sleep`) e retenta automaticamente até 3 vezes com backoff exponencial antes de falhar.
  - O fluxo de criação de playlists em lotes de 100 itens agora consome `spotify_request`, herdando a resiliência contra limitação de taxa.
* **Por quê:** Evitar suspensão da chave de API do Spotify por descumprimento de limites e garantir que lotes grandes de músicas sejam criados mesmo sob alta concorrência.
* **Como verificar:** Teste unitário em `test_phase4.py` com mock de resposta 429 contendo `Retry-After: 1` seguido de resposta 200 comprova repetição automática bem-sucedida.

---

## [FASE 5] — Frontend, CSP e Headers de Segurança
* **Data:** 21/10/2026
* **Status:** Concluído.

### Alterações Realizadas:

#### 1. Cabeçalhos HTTP de Segurança Defensivos (`app.py`)
* **O quê:**
  - Implementado hook global `@app.after_request` adicionando cabeçalhos de segurança padrão OWASP ASVS:
    - `Content-Security-Policy`: política com `default-src 'self'`, scripts restritos à aplicação e ao Tailwind CDN, fontes e estilos restritos a origens seguras (cdnjs FontAwesome) e diretiva anti-clickjacking `frame-ancestors 'none'`.
    - `X-Frame-Options: DENY`: bloqueio completo contra incorporação em iframes (anti-clickjacking em navegadores legados).
    - `X-Content-Type-Options: nosniff`: previne ataques de MIME sniffing.
    - `Referrer-Policy: strict-origin-when-cross-origin`: protege a privacidade do usuário em links externos.
    - `Permissions-Policy: geolocation=(), microphone=(), camera=()`: desativa recursos desnecessários do navegador.
    - `Strict-Transport-Security (HSTS)`: ativado condicionalmente com `max-age=31536000; includeSubDomains; preload` quando em ambiente de produção (`IS_PRODUCTION=True`).
* **Por quê:** Blindar a aplicação no nível de transporte HTTP contra injeção de scripts (XSS), sequestro de cliques (Clickjacking) e sequestro de canal não criptografado.
* **Como verificar:** `python test_phase5.py` inspeciona as respostas de `/login-page` e `/` e certifica a presença de todos os cabeçalhos.

#### 2. Anti-Caching em Rotas de Dados Pessoais (`app.py`)
* **O quê:**
  - Aplicação dos cabeçalhos `Cache-Control: no-store, no-cache, must-revalidate, max-age=0` e `Pragma: no-cache` em qualquer requisição iniciada com `/api/`.
* **Por quê:** Impedir que respostas JSON contendo nomes de músicas, perfil e listas do usuário fiquem retidas em caches intermediários, proxies reversos ou no histórico local do navegador.
* **Como verificar:** `python test_phase5.py` verifica cabeçalhos de resposta em `/api/stats`.

#### 3. Eliminação Total de DOM-XSS via DOM API (`static/js/app.js`)
* **O quê:**
  - Reescrita completa da renderização da tabela de músicas (`renderTable`), listagem de artistas e notificações de status:
    - Removidas todas as interpolações de strings com `innerHTML`.
    - Elementos HTML são construídos exclusivamente via `document.createElement()`.
    - Valores provenientes da API externa do Spotify (`t.name`, `t.artists_str`, `t.album`, `t.release_year`, etc.) são injetados exclusivamente através da propriedade `.textContent`.
    - Links dinâmicos (`playlist_url`) possuem validação explícita de protocolo seguro (`https://` ou `http://`) e atributo `rel="noopener noreferrer"`.
* **Por quê:** Eliminar vulnerabilidades de Cross-Site Scripting no Document Object Model (DOM-XSS), neutralizando qualquer tentativa de injeção de tags HTML maliciosas por meio de metadados manipulados de faixas do Spotify.
* **Como verificar:** `python test_phase5.py` realiza análise estática de código no arquivo JavaScript garantindo ausência de `tr.innerHTML =` e presença de atribuições seguras com `textContent`.

#### 4. Separação de Código e Remoção de Manipuladores Inline (`templates/index.html`, `static/js/app.js`)
* **O quê:**
  - Criação do diretório `static/js/` e migração de todo o script inline do template para `static/js/app.js`.
  - Inclusão do script via tag segura `<script src="{{ url_for('static', filename='js/app.js') }}" defer></script>`.
  - Remoção de todos os manipuladores de evento inline no HTML (`onclick=`, `oninput=`, `onchange=`); os listeners agora são registrados programaticamente via `addEventListener()` no evento `DOMContentLoaded`.
* **Por quê:** Cumprir o padrão ouro de isolamento de código frontend e viabilizar políticas de CSP estritas sem necessidade de permissão a scripts inline arbitrários.
* **Como verificar:** `python test_phase5.py` faz parsing do template HTML confirmando zero ocorrências de atributos `onclick=`, `oninput=` e `onchange=`.

---

## [FASE 6] — Privacidade, Transparência e Conformidade Spotify / LGPD
* **Data:** 21/10/2026
* **Status:** Concluído.

### Alterações Realizadas:

#### 1. Página Pública de Política de Privacidade (`templates/privacy.html`, `app.py`)
* **O quê:**
  - Criação da página `/privacy` acessível publicamente (sem exigir autenticação prévia).
  - Conteúdo estruturado em conformidade estrita com a LGPD (Lei nº 13.709/2018) e com as diretrizes do Spotify:
    - Identificação clara da finalidade e da arquitetura do aplicativo.
    - Minimização de dados: especificação detalhada dos escopos solicitados (`user-library-read`, `playlist-modify-public`, `playlist-modify-private`) e confirmação de não coleta de senhas ou dados financeiros.
    - Declaração de criptografia simétrica em repouso (`AES-Fernet`) e limitação de ciclo de vida das sessões a 24 horas.
    - Direitos do titular: explicação de autoatendimento para exclusão física de dados e instruções de revogação de acesso via `spotify.com/account/apps`.
    - Cláusula de não comercialização e não compartilhamento com terceiros.
* **Por quê:** Requisito mandatório para aprovação de aplicações em quota estendida (Developer Mode -> Production Mode) no Spotify e cumprimento legal dos artigos 6º e 9º da LGPD.
* **Como verificar:** `python test_phase6.py` acessa `GET /privacy` sem cookies de autenticação e valida resposta HTTP 200, cabeçalhos de segurança e menções obrigatórias à LGPD e escopos.

#### 2. Página Pública de Termos de Uso (`templates/terms.html`, `app.py`)
* **O quê:**
  - Criação da página `/terms` acessível publicamente (sem autenticação).
  - Estabelece as regras de utilização, esclarece a independência e ausência de vínculo formal societário com o Spotify AB, define regras de uso aceitável (proibição de abusos ou scripts maliciosos) e condições de rescisão voluntária.
* **Por quê:** Prover transparência jurídica e delimitar responsabilidades perante o usuário final e a plataforma Spotify.
* **Como verificar:** `python test_phase6.py` acessa `GET /terms` e valida status HTTP 200 e seções obrigatórias.

#### 3. Transparência de Permissões e Links na Tela de Login (`templates/login.html`)
* **O quê:**
  - Adicionado painel explicativo na interface de login detalhando que o login utiliza OAuth 2.0 com PKCE oficial e esclarecendo exatamente o que cada permissão solicitada faz.
  - Inserção de links institucionais visíveis no rodapé para `/privacy` e `/terms`.
* **Por quê:** Oferecer consentimento informado antes de qualquer redirecionamento ao Spotify, eliminando ambiguidades quanto aos acessos solicitados.
* **Como verificar:** `python test_phase6.py` inspeciona o HTML retornado por `/login-page` confirmando a presença dos links institucionais e do painel de transparência.

#### 4. Checklist Formal de Políticas do Spotify (`SPOTIFY_POLICY_CHECKLIST.md`)
* **O quê:**
  - Criação do documento formal de auditoria na raiz do projeto.
  - Mapeamento e ateste detalhado de conformidade com todos os itens do *Spotify Developer Terms of Service*, *Spotify Developer Policy*, *Branding Guidelines* e padrões de segurança OWASP.
* **Por quê:** Documentação necessária para auditoria pré-deploy e submissão formal de aprovação da aplicação junto à equipe de desenvolvedores do Spotify.
* **Como verificar:** `python test_phase6.py` valida a existência do documento e a presença de conformidade atestada em todas as categorias.

---

## [FASE 7] — Infraestrutura, Deploy e Operação Segura
* **Data:** 21/10/2026
* **Status:** Concluído.

### Alterações Realizadas:

#### 1. Configuração de Inicialização WSGI de Produção (`Procfile`, `render.yaml`)
* **O quê:**
  - Criação do `Procfile` com declaração do processo web executando Gunicorn em modo multi-worker assíncrono:
    `web: gunicorn --workers 4 --threads 2 --bind 0.0.0.0:$PORT --timeout 120 --access-logfile - --error-logfile - app:app`.
  - Criação do manifesto declarativo `render.yaml` (Blueprint do Render.com) especificando runtime Python, comandos de build/start e isolamento de variáveis de ambiente com segredos marcados como `sync: false` (não expostos no repositório).
  - Suporte automático a `ProxyFix` do Werkzeug em produção para preservação de IP real e esquema HTTPS vindo do balanceador de carga.
* **Por quê:** Substituir o servidor de desenvolvimento monoprócesso por um servidor WSGI robusto de nível industrial, capaz de absorver concorrência com timeouts adequados e sem risco de travamentos.
* **Como verificar:** `python test_phase7.py` valida presença, parâmetros de inicialização e sintaxe dos arquivos `Procfile` e `render.yaml`.

#### 2. Pipeline de Auditoria Automatizada de Vulnerabilidades (`.github/workflows/audit.yml`)
* **O quê:**
  - Criação do workflow de Integração Contínua (CI) no GitHub Actions que executa a cada `push`, `pull_request` e semanalmente via agendamento cron (`0 6 * * 1`).
  - Execução automatizada da ferramenta `pip-audit` contra o banco de dados OSV/PyPI de vulnerabilidades conhecidas (CVEs).
  - Execução sequencial de todas as suítes de testes de regressão de segurança do projeto (`test_phase3.py` a `test_phase7.py`).
* **Por quê:** Blindar a cadeia de suprimentos de software (*software supply chain security*), garantindo que nenhuma vulnerabilidade seja introduzida inadvertidamente em dependências ou atualizações futuras.
* **Como verificar:** `python -m pip_audit -r requirements.txt` executado localmente reporta zero vulnerabilidades conhecidas e o workflow está validado em `test_phase7.py`.

#### 3. Monitoramento Contínuo com Dependabot (`.github/dependabot.yml`)
* **O quê:**
  - Configuração do Dependabot para varredura semanal automática tanto das dependências Python (`pip`) quanto das ações do GitHub Actions (`github-actions`).
  - Aplicação de labels automáticos (`security`, `dependencies`, `ci`).
* **Por quê:** Automação de alertas e geração proativa de Pull Requests em caso de vulnerabilidades identificadas em pacotes de terceiros.
* **Como verificar:** `python test_phase7.py` valida a existência e a estrutura de `.github/dependabot.yml`.

#### 4. Guia Completo de Deploy, Operação e Túnel Seguro (`README.md`)
* **O quê:**
  - Reestruturação completa do `README.md` abrangendo:
    - Resumo executivo da arquitetura BFF e proteções OWASP ASVS implementadas.
    - Passo a passo de deploy no Render com HTTPS forçado e domínio fixo.
    - Guia de testes locais em dispositivos móveis via túneis seguros (Cloudflare Tunnel e ngrok), eliminando a necessidade de expor portas na rede local aberta.
    - Procedimento de `git init` seguro com conferência de exclusões no `.gitignore` antes do commit inicial para evitar vazamento acidental de chaves no histórico do Git.
    - Matriz detalhada de variáveis de ambiente de produção e desenvolvimento.
* **Por quê:** Garantir operabilidade sem atritos, reprodutibilidade e prevenção de erros humanos operacionais que possam comprometer a segurança da aplicação.
* **Como verificar:** `python test_phase7.py` valida se todas as seções mandatórias de infraestrutura e segurança estão presentes no `README.md`.

---

## [FASE 8] — Governança, Threat Model e Resposta a Incidentes
* **Data:** 21/10/2026
* **Status:** Concluído.

### Alterações Realizadas:

#### 1. Modelagem Formal de Ameaças STRIDE (`THREAT_MODEL.md`)
* **O quê:**
  - Criação do documento `THREAT_MODEL.md` com mapeamento detalhado da arquitetura em 3 limites de confiança (*Trust Boundaries*).
  - Análise sistemática cobrindo os 6 pilares da metodologia STRIDE:
    - **Spoofing:** Proteção de login e autorização contra Login CSRF e sequestro de código via PKCE S256 e state criptográfico.
    - **Tampering:** Proteção de integridade em repouso com autenticação HMAC-SHA256 do Fernet, validação regex estrita de URIs e `@require_same_origin`.
    - **Repudiation:** Rastreabilidade em logs auditáveis sem PII e confirmação explícita de exclusão.
    - **Information Disclosure:** Blindagem contra vazamento de tokens via padrão BFF, eliminação de DOM-XSS via DOM API (`textContent`), `Cache-Control: no-store` e CSP estrita.
    - **Denial of Service:** Mitigação de DoS e exaustão de recursos via `MAX_CONTENT_LENGTH = 1MB`, rate limiting por sessão/IP com `Flask-Limiter` e backoff exponencial com respeito ao cabeçalho `Retry-After`.
    - **Elevation of Privilege:** Isolamento estrito de tokens por sessão criptografada e menor privilégio de escopos.
  - Elaboração da Matriz Residual de Risco comprovando que todas as ameaças foram mitigadas para níveis Baixo ou Muito Baixo.
* **Por quê:** Documentar formalmente os riscos de segurança, a eficácia das contramedidas adotadas e embasar o processo de aprovação do aplicativo junto à equipe de segurança do Spotify.
* **Como verificar:** `python test_phase8.py` valida a estrutura do arquivo, cobertura dos 6 pilares STRIDE e presença da Matriz Residual de Risco.

#### 2. Governança, Divulgação de Vulnerabilidades e IRP (`SECURITY.md`)
* **O quê:**
  - Criação da política de divulgação de vulnerabilidades (*Vulnerability Disclosure Policy*) com canal seguro de reporte, regras claras de não realização de ataques destrutivos e tabela formal de SLAs por severidade CVSS (24h para críticas, 48h para altas).
  - Procedimento Operacional Padrão (Runbook) para rotação de segredos sem downtime:
    - Rotação de `ENCRYPTION_KEY` em duas etapas utilizando suporte a chaves múltiplas do `MultiFernet` (`ENCRYPTION_KEY=nova,antiga`), permitindo transição contínua sem quebrar sessões ativas.
    - Procedimentos para rotação de `FLASK_SECRET_KEY` e `SPOTIPY_CLIENT_SECRET`.
  - Plano de Resposta a Incidentes (IRP) em 5 fases (Identificação, Contenção, Erradicação, Recuperação e Lições Aprendidas), incluindo diretrizes de comunicação a usuários e à ANPD em conformidade com o Art. 48 da LGPD.
* **Por quê:** Estabelecer previsibilidade, compliance e capacidade de reação rápida a falhas de segurança durante a operação do serviço.
* **Como verificar:** `python test_phase8.py` valida o conteúdo do `SECURITY.md`, procedimentos de rotação, SLA de vulnerabilidades e plano de resposta a incidentes.

#### 3. Integração e Referências Cruzadas (`README.md`, `.github/workflows/audit.yml`)
* **O quê:**
  - Atualização do `README.md` com links para `THREAT_MODEL.md` e `SECURITY.md`.
  - Inclusão do teste `test_phase8.py` no pipeline automatizado de CI/CD do GitHub Actions.
* **Por quê:** Assegurar que as diretrizes de governança sejam facilmente localizadas por usuários, desenvolvedores e pesquisadores de segurança.
* **Como verificar:** `python test_phase8.py` valida as referências cruzadas no `README.md`.

---

## [FASE 9] — Suíte de Testes Automatizados Finais (pytest)
* **Data:** 22/10/2026
* **Status:** Concluído.

### Alterações Realizadas:

#### 1. Configuração Declarativa do Framework de Testes (`pytest.ini`, `requirements.txt`)
* **O quê:**
  - Adição da dependência `pytest==9.1.1` no arquivo `requirements.txt`.
  - Criação do arquivo de configuração `pytest.ini` na raiz do projeto com descoberta automática de testes em `tests/`, padronização de nomenclatura (`test_*.py`, `Test*`, `test_*`), saída concisa com traceback reduzido (`-v --tb=short`) e supressão de warnings externos obsoletos.
* **Por quê:** Padronizar a execução contínua de testes em conformidade com o padrão da comunidade Python, permitindo execução unificada e isolada com um único comando (`pytest`).
* **Como verificar:** Executar `pytest` no terminal reconhece automaticamente o arquivo de configuração e descobre os casos de teste.

#### 2. Infraestrutura e Fixtures de Teste (`tests/conftest.py`, `tests/__init__.py`)
* **O quê:**
  - Criação do pacote `tests/` contendo `__init__.py` e `conftest.py`.
  - Implementação de fixtures reutilizáveis:
    - `app`: Instância de aplicação configurada com flags de teste (`TESTING=True`, `DEBUG=False`).
    - `reset_limiter_and_state`: Fixture com execução automática (`autouse=True`) que reseta o estado interno de cotas do `Flask-Limiter` antes e após cada caso de teste, garantindo total isolamento e independência entre os cenários.
    - `client`: Test client HTTP padrão para chamadas públicas e não autenticadas.
    - `auth_client`: Test client com sessão autenticada mockada, provendo tokens do Spotify devidamente criptografados com Fernet e identificador de usuário injetado de forma segura na sessão.
* **Por quê:** Eliminar redundâncias e boilerplate na escrita de testes, assegurando que o estado de um teste nunca contamine ou interfira nos testes subsequentes.
* **Como verificar:** Execução dos testes modulares sem dependência de ordem de execução.

#### 3. Suíte Integrada Unificada de Segurança (`tests/test_security.py`)
* **O quê:**
  - Criação da suíte definitiva cobrindo 32 casos de teste estruturados em 7 classes especializadas:
    - **`TestEnvironmentAndSecrets` (Fases 0 e 1):** Validação fail-fast na ausência de variáveis obrigatórias, rejeição de `FLASK_SECRET_KEY` com baixa entropia (< 32 bytes), validação de `ENCRYPTION_KEY` Fernet e auditoria de flags de cookies (`HttpOnly`, `SameSite=Lax`, expiração de 24h).
    - **`TestOAuthPKCE` (Fase 2):** Validação do fluxo PKCE (geração de `code_verifier`, `code_challenge` S256 e `state`), rejeição estrita (HTTP 403) de callbacks com state ausente ou divergente (Anti-CSRF), tratamento gracioso de recusa de autorização (`error=access_denied`), encerramento de sessão seguro via POST com rotação de sessão e rejeição de requisições GET em `/logout` (HTTP 405).
    - **`TestDataAtRestAndLGPD` (Fase 3):** Roundtrip de criptografia simétrica com MultiFernet, suporte a rotação contínua de chaves sem downtime, exclusão física de arquivos de sessão do disco (`purge_session_file`), estrita minimização de dados no `tracks_cache`, expiração de cache por TTL (24 horas) e revogação definitiva de dados e sessão via LGPD Art. 18 (`/api/delete_my_data`).
    - **`TestApiProtection` (Fase 4):** Bloqueio por rate limiting híbrido (HTTP 429) com inclusão do cabeçalho `Retry-After`, rejeição de CSRF por validação de origem (`@require_same_origin` com HTTP 403 para origens externas), limitação estrita de payload a 1MB (HTTP 413), sanitização e validação de nome e regex de URIs do Spotify (`^spotify:track:[a-zA-Z0-9]{22}$`), e backoff do cliente com tratamento defensivo de respostas HTTP 429 externas.
    - **`TestFrontendAndHeaders` (Fase 5):** Cabeçalhos HTTP defensivos (CSP estrita com `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`), cabeçalho `Cache-Control: no-store` em todos os endpoints `/api/*`, ausência total de manipuladores inline nos templates HTML e validação estrita de manipulação do DOM em `static/js/app.js` usando `textContent` (prevenção total contra DOM-XSS).
    - **`TestPrivacyAndTerms` (Fase 6):** Disponibilidade pública e sem autenticação prévia das páginas `/privacy` e `/terms`, transparência de escopos e PKCE na tela de login (`/login-page`) e auditoria de integridade do arquivo `SPOTIFY_POLICY_CHECKLIST.md`.
    - **`TestInfrastructureAndGovernance` (Fases 7 e 8):** Validação das configurações de deploy para Gunicorn multi-worker (`Procfile`, `render.yaml`), verificação das automações de CI/CD (`audit.yml`) e Dependabot (`dependabot.yml`), auditoria de cobertura dos 6 pilares da modelagem STRIDE (`THREAT_MODEL.md`) e conformidade das políticas de governança, runbook de rotação e IRP (`SECURITY.md`).
* **Por quê:** Consolidar a garantia formal e permanente de não-regressão de todos os requisitos de segurança e conformidade através de uma suíte rápida, reprodutível e livre de dependências de rede externa.
* **Como verificar:** Executar `pytest` ou `python -m pytest`; todos os 32 testes executam e passam 100% em menos de 3 segundos.

#### 4. Integração Contínua e Documentação (`.github/workflows/audit.yml`, `README.md`)
* **O quê:**
  - Atualização do workflow do GitHub Actions (`.github/workflows/audit.yml`) para executar o comando `python -m pytest` antes dos scripts individuais de teste.
  - Atualização da Seção 9 do `README.md` destacando o comando `pytest` como o ponto central de teste do ecossistema.
* **Por quê:** Garantir que o pipeline de integração contínua rejeite automaticamente qualquer Pull Request ou commit que introduza regressão de segurança.
* **Como verificar:** Inspecionar `.github/workflows/audit.yml` e `README.md`.

