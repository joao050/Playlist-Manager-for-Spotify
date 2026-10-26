# PROJECT_TASKS.md — Registro Vivo de Tarefas

## 1. Fase Atual
- **Fase:** Conclusão Integral do Ciclo de Endurecimento de Segurança (Fases 0 a 9 — 100% Finalizadas).
- **Objetivo:** Todas as fases planejadas (Fail-fast, PKCE, Criptografia/LGPD, Proteção de APIs, CSP/Anti-XSS, Conformidade Spotify, Deploy/Infraestrutura, Threat Model STRIDE e Suíte Integrada com Pytest) foram concluídas com 100% de aprovação e documentadas.

## 2. Em Andamento
- **Tarefa:** Nenhuma (Ciclo concluído).
- **Status:** Estável e pronto para auditoria externa ou homologação final.

## 3. Planejadas (Backlog)
- *Nenhuma tarefa pendente no momento.* Todas as 9 fases foram executadas com sucesso.

## 4. Concluídas
- [x] `#SEC-00` | 2026-10-19 | Diagnóstico inicial e testes de base sem edição | `app.py`, `templates/`
- [x] `#SEC-01` | 2026-10-19 | Fail-fast de variáveis de ambiente, remoção de segredos hardcoded, redirect URI fixa e ProxyFix | `app.py`, `.env.example`, `requirements.txt`, `.gitignore`
- [x] `#SEC-02` | 2026-10-19 | OAuth 2.0 com PKCE S256, State anti-CSRF, logout via POST com validação de origem e rotação de sessão | `app.py`, `templates/index.html`, `templates/login.html`
- [x] `#SEC-03` | 2026-10-19 | Criptografia em repouso (MultiFernet), sessão 24h, tracks_cache com minimização e TTL, LGPD Art. 18 delete_my_data, suporte Redis | `app.py`, `templates/index.html`, `templates/login.html`, `requirements.txt`, `test_phase3.py`
- [x] `#SEC-04` | 2026-10-21 | Proteção API: Flask-Limiter por IP/sessão, CSRF via Origin check em POSTs, validação estrita de payload (JSON, tamanho, regex URI), backoff 429 Retry-After, MAX_CONTENT_LENGTH (1MB) e sanitização | `app.py`, `requirements.txt`, `test_phase4.py`
- [x] `#SEC-05` | 2026-10-21 | Frontend e Headers: Eliminação de DOM-XSS via DOM API (textContent), externalização de JS para static/js/app.js, remoção de inline handlers e headers HTTP (CSP com frame-ancestors: none, HSTS em prod, X-Content-Type-Options: nosniff, Cache-Control: no-store em APIs) | `templates/index.html`, `static/js/app.js`, `app.py`, `test_phase5.py`
- [x] `#SEC-06` | 2026-10-21 | Privacidade e Conformidade: Páginas públicas de Política de Privacidade (/privacy) e Termos de Uso (/terms), transparência de escopos na tela de login, e checklist formal SPOTIFY_POLICY_CHECKLIST.md | `templates/privacy.html`, `templates/terms.html`, `templates/login.html`, `app.py`, `SPOTIFY_POLICY_CHECKLIST.md`, `test_phase6.py`
- [x] `#SEC-07` | 2026-10-21 | Infraestrutura e Operação: Configuração WSGI Gunicorn (Procfile, render.yaml), pipeline de CI/CD com auditoria de vulnerabilidades (pip-audit), Dependabot semanal, guia completo de deploy com HTTPS e túnel seguro | `Procfile`, `render.yaml`, `.github/workflows/audit.yml`, `.github/dependabot.yml`, `README.md`, `test_phase7.py`
- [x] `#SEC-08` | 2026-10-21 | Governança e Threat Model: Modelagem STRIDE completa em THREAT_MODEL.md, política de divulgação responsável, runbook de rotação MultiFernet e IRP em SECURITY.md | `THREAT_MODEL.md`, `SECURITY.md`, `README.md`, `test_phase8.py`
- [x] `#SEC-09` | 2026-10-22 | Suíte Integrada com Pytest: Configuração pytest.ini, fixtures em tests/conftest.py, 32 testes cobrindo todas as fases e integração ao pipeline CI/CD | `pytest.ini`, `requirements.txt`, `tests/conftest.py`, `tests/test_security.py`, `.github/workflows/audit.yml`, `README.md`
- [x] `#CLEAN-01` | 2026-10-22 | Limpeza de raiz: remoção de scripts legados, utilitários e testes avulsos; organização do .gitignore com proteção de diretrizes de IA (.agent, GEMINI.md) | `.gitignore`, `PROJECT_MAP.md`, `PROJECT_TASKS.md`
- [x] `#GOV-01` | 2026-10-22 | Adição formal do arquivo de licença de código aberto MIT | `LICENSE`, `PROJECT_MAP.md`, `PROJECT_TASKS.md`
- [x] `#INT-01` | 2026-10-23 | Integração desacoplada com micro-servidor de testes Samsung Galaxy J6 (Termux/ADB) para homologação do BFF em ambiente físico | `PROJECT_MAP.md`, `PROJECT_TASKS.md`
- [x] `#BRAND-01` | 2026-10-26 | Adequação de marca para "Playlist Manager for Spotify" em conformidade com as Spotify Developer Branding Guidelines antes da publicação no GitHub | `templates/`, `static/js/app.js`, `app.py`, `render.yaml`, `.env.example`, `docs`
- [x] `#CI-01` | 2026-10-26 | Correção de variáveis de teste no CI/CD e conftest: chave Fernet válida (32 bytes url-safe), injeção padrão de envs de teste no conftest e remoção de scripts legados do workflow | `tests/conftest.py`, `.github/workflows/audit.yml`, `README.md`
- [x] `#DEP-01` | 2026-10-26 | Atualização de dependências auditadas pelo Dependabot: gunicorn para 26.2.0, actions/checkout para v7 e actions/setup-python para v7 | `requirements.txt`, `.github/workflows/audit.yml`
- [x] `#DEP-02` | 2026-10-26 | Guia de provisionamento e deploy em produção no Render via Blueprint com render.yaml e sincronização de credenciais | `render.yaml`, `Procfile`, `README.md`
- [x] `#FIX-REDIS-01` | 2026-10-26 | Resiliência defensiva de inicialização do Redis: validação de esquemas (redis://, rediss://, unix://), fallback seguro para filesystem e remoção de REDIS_URL obrigatório do render.yaml | `app.py`, `render.yaml`


## 5. Decisões Tomadas
- Padrão BFF (Backend-For-Frontend): Tokens do Spotify nunca chegam ao navegador do cliente; o navegador mantém apenas cookie de sessão seguro (`HttpOnly`, `SameSite=Lax`).
- PKCE com `client_secret` simultâneos: Testado empiricamente e aceito pela API do Spotify, garantindo defesa em profundidade (confidential client + PKCE RFC 7636).
- Criptografia simétrica com `MultiFernet`: Permite rotação futura de chave no `.env` sem derrubar sessões de usuários ou exigir migração em massa.
- Filesystem local como padrão com fallback pronto para Redis: Garante desenvolvimento local sem dependência de serviços externos, com suporte a nuvem via `REDIS_URL`.
- Expurgo físico de sessão no logout e delete: `session.clear()` não deleta o arquivo físico do Flask-Session; implementado `purge_session_file()` para remoção explícita no disco.
- Proteção CSRF por validação estrita de Origin/Referer: Em conformidade com OWASP CSRF Defense, cookies com `SameSite=Lax` somados à validação de `Origin`/`Referer` no backend protegem todos os métodos mutáveis (`POST`) sem sobrecarga desnecessária de tokens dinâmicos no BFF.
- Rate Limiting híbrido (sessão + IP): Identifica primeiro a chave `session.sid` e recorre ao endereço IP remoto, garantindo isolamento por usuário autenticado.
- Prevenção Rigorosa de DOM-XSS e Separação de Código: Substituição total de concatenações de HTML dinâmico por criação segura com DOM API (`createElement`/`textContent`); scripts totalmente externalizados em `static/js/app.js` e listeners associados programaticamente via `addEventListener`, sem handlers inline.
- Transparência Total e Acesso Público a Termos/Privacidade: As páginas `/privacy` e `/terms` são acessíveis sem autenticação prévia, cumprindo expressamente o Spotify Developer Policy e os artigos 6º e 9º da LGPD.
- Infraestrutura Declarativa e Auditoria Contínua: O provisionamento de produção é padronizado via `Procfile` e `render.yaml` (Gunicorn multi-worker), com varredura automática semanal de vulnerabilidades em dependências (`pip-audit` + Dependabot).
- Governança Formal e IRP: Adoção do modelo STRIDE para análise sistemática de vetores de ataque e estabelecimento de SLAs contratuais e técnicos para tratamento de vulnerabilidades e resposta a incidentes.
- Suíte Integrada com Pytest como Portão de Qualidade: Testes automatizados estruturados em classes temáticas desacopladas com fixtures independentes, reset automático do rate limiter e execução no CI/CD a cada push e pull request.
- Conformidade Estrita com Diretrizes de Marca do Spotify: Adoção do padrão oficial "[Nome do App] for Spotify" ("Playlist Manager for Spotify"), garantindo que o app não aparente ser um produto oficial operado pelo Spotify AB.
- Isolamento e Resiliência de Testes no CI: `conftest.py` define programaticamente fallbacks de credenciais e chaves Fernet válidas para testes, impedindo que runners limpos (sem `.env` local) falhem no fail-fast do `app.py`.
- Atualização e Alinhamento Proativo com Dependabot: Adoção do Gunicorn 26.2.0 (melhorias em HTTP/2 e gthread) e actions oficiais v7 (prevenção contra ataques pwn em checkout e runtime Node moderno em setup-python).
- Fallback Automático e Opcionalidade do Redis: Se a variável `REDIS_URL` estiver vazia, indefinida ou com formato inválido, a aplicação recorre automaticamente ao armazenamento de sessões em sistema de arquivos local (`.flask_session/`), eliminando travamentos de deploy.
