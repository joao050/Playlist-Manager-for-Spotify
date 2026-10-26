# Playlist Manager for Spotify

Aplicação web BFF (*Backend-For-Frontend*) em Flask desenvolvida para organizar músicas curtidas da biblioteca do Spotify com filtros avançados (década, artista, ano, popularidade) e criar playlists personalizadas diretamente na conta do usuário, com arquitetura endurecida segundo os padrões OWASP ASVS e em conformidade estrita com a LGPD (Lei 13.709/2018) e o Spotify Developer Policy.

---

## 1. Arquitetura e Recursos de Segurança

* **Padrão BFF (Backend-For-Frontend):** Tokens de acesso (`access_token` e `refresh_token`) residem unicamente na memória do servidor e em sessões cifradas; jamais são expostos ao JavaScript do navegador.
* **OAuth 2.0 com PKCE (RFC 7636) & State anti-CSRF:** Fluxo de autorização obrigatório com desafio criptográfico S256 (`code_challenge` / `code_verifier`) e verificação de `state` com `secrets.compare_digest`.
* **Criptografia em Repouso:** Tokens de sessão e caches de faixas são cifrados com chaves simétricas de 256 bits (`AES-Fernet` / `MultiFernet`) antes de qualquer gravação em disco (`.flask_session/`) ou Redis.
* **Prevenção de DOM-XSS:** Interface renderizada 100% via DOM API (`createElement`/`textContent`) em script estático isolado (`static/js/app.js`), sem concatenações de HTML via `innerHTML`.
* **Cabeçalhos HTTP Defensivos:** `@app.after_request` injeta Content-Security-Policy (CSP) com `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin` e `Cache-Control: no-store` em rotas de API.
* **Rate Limiting & Resiliência:** Proteção com `Flask-Limiter` por sessão/IP e tratamento automático de HTTP 429 (*Too Many Requests*) com backoff exponencial respeitando o cabeçalho `Retry-After` do Spotify.
* **Exclusão Definitiva (LGPD Art. 18):** Endpoint `/api/delete_my_data` com validação de origem que expurga fisicamente os arquivos de sessão no servidor.

---

## 2. Requisitos e Instalação

* **Python:** 3.11, 3.12, 3.13 ou 3.14.
* **Conta de Desenvolvedor no Spotify:** [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard).

### Instalação das Dependências

Clone ou acesse a pasta do projeto e instale as dependências pinadas:

```bash
pip install -r requirements.txt
```

---

## 3. Configuração de Variáveis de Ambiente

Copie o modelo `.env.example` para `.env`:

```bash
cp .env.example .env
```

Preencha os valores obrigatórios no `.env`:

| Variável | Descrição | Exemplo / Como Obter |
| :--- | :--- | :--- |
| `SPOTIPY_CLIENT_ID` | Client ID da sua aplicação registrada no Spotify | Obtido no Spotify Developer Dashboard |
| `SPOTIPY_CLIENT_SECRET` | Client Secret da aplicação no Spotify | Obtido no Spotify Developer Dashboard |
| `SPOTIPY_REDIRECT_URI` | URI exata cadastrada no Spotify Dashboard | `http://127.0.0.1:5000/callback` (local) ou `https://seu-app.onrender.com/callback` (produção) |
| `FLASK_SECRET_KEY` | Chave de integridade e assinatura das sessões (mínimo 32 bytes) | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ENCRYPTION_KEY` | Chave Fernet de 32 bytes em Base64URL para cifrar dados em repouso | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `FLASK_ENV` | Ambiente de execução (`development` ou `production`) | `development` (local) / `production` (deploy) |
| `REDIS_URL` | *(Opcional)* URL de conexão Redis para sessões distribuídas | `redis://usuario:senha@host:porta/0` |
| `ALLOW_LAN_ACCESS` | *(Opcional, Dev)* Permite escuta em `0.0.0.0` para testes locais | `false` (padrão seguro) |

---

## 4. Execução

### Modo de Desenvolvimento Local

```bash
python app.py
```

Acesse em seu navegador: [http://127.0.0.1:5000](http://127.0.0.1:5000).

### Modo de Produção com Servidor WSGI (Gunicorn)

```bash
gunicorn --workers 4 --threads 2 --bind 0.0.0.0:5000 --timeout 120 app:app
```

---

## 5. Guia de Deploy em Produção (Render / Fly.io)

### Passo 1: Cadastro no Spotify Developer Dashboard
1. Acesse [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) e clique no seu App.
2. Em **Settings**, localize o campo **Redirect URIs**.
3. Adicione a URL HTTPS fixa do seu deploy em produção:
   ```text
   https://seu-app.onrender.com/callback
   ```
4. Salve as alterações.

### Passo 2: Deploy no Render.com (via Blueprint ou Web Service)
1. Conecte seu repositório Git ao Render.
2. O arquivo [`render.yaml`](./render.yaml) incluído no repositório provisiona o serviço automaticamente com:
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn --workers 4 --threads 2 --bind 0.0.0.0:$PORT --timeout 120 app:app`
   - **ProxyFix:** Ativado automaticamente quando `FLASK_ENV=production`.
3. Configure as variáveis de ambiente secretas no painel do Render (`Environment`):
   - `SPOTIPY_CLIENT_ID`
   - `SPOTIPY_CLIENT_SECRET`
   - `SPOTIPY_REDIRECT_URI` (apontando para `https://seu-app.onrender.com/callback`)
   - `FLASK_SECRET_KEY`
   - `ENCRYPTION_KEY`
   - `FLASK_ENV` = `production`
   - *(Opcional)* `REDIS_URL` (para persistência de sessão multi-instância via Upstash Redis).

---

## 6. Testes em Dispositivos Móveis com Túnel Seguro

Para testar o fluxo de autenticação e navegação no celular sem expor portas diretamente na internet aberta ou depender de redes Wi-Fi públicas inseguras, utilize **Cloudflare Tunnel** ou **ngrok**:

### Opção A: Cloudflare Tunnel (Recomendado)
```bash
# Inicie o app localmente em 127.0.0.1:5000
python app.py

# Em outro terminal, inicialize o túnel temporário seguro com HTTPS
cloudflared tunnel --url http://127.0.0.1:5000
```
Copie a URL gerada (ex: `https://nome-aleatorio.trycloudflare.com`) e adicione `https://nome-aleatorio.trycloudflare.com/callback` temporariamente no painel do Spotify.

### Opção B: ngrok
```bash
ngrok http 5000
```

---

## 7. Procedimento de `git init` Seguro (Prevenção de Vazamento)

Antes de inicializar ou publicar seu repositório Git, certifique-se de que os arquivos de configuração local e segredos estão protegidos:

1. Inspecione o arquivo [`.gitignore`](./.gitignore) para confirmar que `.env`, `.flask_session/`, `.cache` e relatórios de log estão excluídos.
2. Inicialize o repositório e verifique os arquivos em staging:
   ```bash
   git init
   git add .
   git status
   ```
3. **Conferência Obrigatória:** Verifique se o arquivo `.env` **NÃO** aparece na lista de arquivos a serem comitados. Somente `.env.example` deve ser rastreado.
4. Execute o primeiro commit:
   ```bash
   git commit -m "feat: initial commit with hardened security architecture"
   ```

---

## 8. Auditoria Automatizada e CI/CD

O projeto conta com pipelines integrados de auditoria contínua de vulnerabilidades:

* **GitHub Actions ([`.github/workflows/audit.yml`](./.github/workflows/audit.yml)):**
  Executa a cada `push`, `pull_request` e semanalmente via agendamento cron:
  - Varredura de CVEs nas dependências via `pip-audit`.
  - Execução completa de todas as suítes de testes de regressão de segurança.
* **Dependabot ([`.github/dependabot.yml`](./.github/dependabot.yml)):**
  Monitoramento semanal de atualizações de segurança para pacotes Python e GitHub Actions.

Para rodar a auditoria de segurança localmente:

```bash
pip-audit -r requirements.txt
```

---

## 9. Suíte de Testes Automatizados

O projeto conta com suíte integrada unificada executada via `pytest`, cobrindo 100% dos controles OWASP ASVS e Spotify Developer Policy:

```bash
# Execução da suíte completa integrada com pytest
pytest
```

Você também pode executar classes de testes específicas por módulo:

```bash
pytest tests/test_security.py -k TestEnvironmentAndSecrets        # Fail-fast e segredos
pytest tests/test_security.py -k TestOAuthAndSession             # OAuth 2.0 PKCE e logout
pytest tests/test_security.py -k TestEncryptionAndLGPD           # Criptografia e LGPD Art. 18
pytest tests/test_security.py -k TestAPISecurityAndRateLimiting  # Limiter, CSRF e payload
pytest tests/test_security.py -k TestFrontendAndHeaders          # CSP e anti-DOM-XSS
pytest tests/test_security.py -k TestPrivacyAndCompliance        # Termos e conformidade Spotify
pytest tests/test_security.py -k TestInfrastructureAndDeployment # Gunicorn e audit
pytest tests/test_security.py -k TestGovernanceAndThreatModel    # STRIDE e runbooks
```

---

## 10. Governança, Threat Model e Resposta a Incidentes

A aplicação segue uma abordagem formal de governança e segurança por padrão:

* **Modelagem de Ameaças STRIDE ([`THREAT_MODEL.md`](./THREAT_MODEL.md)):** Análise completa de vetores de ataque (*Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege*), mapeamento de limites de confiança e matriz residual de risco.
* **Política de Segurança e Runbooks ([`SECURITY.md`](./SECURITY.md)):**
  - Procedimento para reporte responsável de vulnerabilidades (*Vulnerability Disclosure Policy*).
  - Procedimento Operacional Padrão para rotação de chaves sem downtime via `MultiFernet`.
  - Plano de Resposta a Incidentes (IRP) em 5 fases e diretrizes de notificação conforme a LGPD.

---

## 11. Licença e Conformidade

Este projeto é disponibilizado sob a licença MIT. O uso da API do Spotify está sujeito aos [Spotify Developer Terms of Service](https://developer.spotify.com/terms).
