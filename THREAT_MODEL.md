# THREAT_MODEL.md — Modelagem de Ameaças (Metodologia STRIDE)

Este documento estabelece a modelagem formal de ameaças para o **Playlist Manager for Spotify**, mapeando a arquitetura do sistema, os limites de confiança (*Trust Boundaries*) e as contramedidas técnicas implementadas com base na metodologia **STRIDE** da Microsoft e nas diretrizes do OWASP.

---

## 1. Visão Geral da Arquitetura e Limites de Confiança (Trust Boundaries)

```text
[ NAVEGADOR DO CLIENTE ]
       │
       │  (1) HTTPS / Cookie de Sessão (HttpOnly, SameSite=Lax, Secure)
       ▼
═════════════════════════════════════════════════════════════════════════ [ LIMITE DE CONFIANÇA 1 ]
[ BACKEND FLASK (BFF) ]
   ├── Limiter (Taxa por IP/Sessão)
   ├── CSRF Validator (Origin / Referer / Host)
   ├── Criptografia Fernet (AES-128-CBC + HMAC-SHA256)
   └── Spotify Request Handler (Retry-After & Backoff)
       │                        │
       │ (2) MultiFernet Cifrado│ (3) Chamadas HTTPS Autenticadas (Bearer Token)
       ▼                        ▼
[ PERSISTÊNCIA ]          ══════════════════════════════════════════════ [ LIMITE DE CONFIANÇA 2 ]
(.flask_session / Redis)  [ SPOTIFY WEB API ]
```

### Limites Identificados:
1. **Limite 1 (Navegador ⇄ Backend Flask):** Fronteira entre o ambiente não confiável do usuário (browser) e a infraestrutura do servidor. Comunicação protegida por cookies de sessão seguros, mitigação CSRF e cabeçalhos de segurança HTTP.
2. **Limite 2 (Backend Flask ⇄ Spotify Web API):** Fronteira entre o servidor da aplicação e os servidores de nuvem do Spotify. Comunicação protegida por TLS 1.3, tokens Bearer de ciclo curto e autenticação OAuth 2.0 PKCE.
3. **Limite 3 (Backend Flask ⇄ Armazenamento em Disco/Redis):** Fronteira interna de persistência. Protegida por criptografia simétrica com chave mestra isolada em variáveis de ambiente.

---

## 2. Análise de Ameaças por Categoria STRIDE

### S — Spoofing (Falsificação de Identidade)
| ID | Cenário de Ameaça | Impacto | Contramedida Implementada no Projeto |
| :--- | :--- | :--- | :--- |
| **S-01** | Atacante forja o redirecionamento OAuth para interceptar o código de autorização de outro usuário (Login CSRF). | Alto | Geração de parâmetro `state` criptográfico de 32 bytes (`secrets.token_urlsafe(32)`) armazenado na sessão e validado com comparação em tempo constante (`secrets.compare_digest`). |
| **S-02** | Atacante intercepta o código de autorização em trânsito e tenta trocá-lo por tokens de acesso. | Crítico | Implementação mandatória de **PKCE (RFC 7636, S256)**: o Spotify só entrega os tokens para quem apresentar o `code_verifier` original que gerou o `code_challenge`. |
| **S-03** | Atacante tenta sequestrar ou fixar a sessão de um usuário antes da autenticação (Session Fixation). | Alto | Execução de `session.clear()` no `/callback` logo antes da emissão de credenciais autenticadas, descartando o ID de sessão pré-login. |

---

### T — Tampering (Adulteração de Dados)
| ID | Cenário de Ameaça | Impacto | Contramedida Implementada no Projeto |
| :--- | :--- | :--- | :--- |
| **T-01** | Atacante com acesso local ao servidor ou a um dump de backup tenta adulterar tokens de acesso ou faixas em cache. | Crítico | Criptografia simétrica com autenticação integrada (`Fernet` / `HMAC-SHA256`). Qualquer alteração de um único bit no arquivo de sessão invalida a assinatura criptográfica, descartando os dados corrompidos sem executá-los. |
| **T-02** | Atacante adultera o payload na criação de playlist (injetando URIs de outros tipos, como podcasts, episódios ou URLs maliciosas). | Médio | Validação estrita via expressão regular em `/api/create_playlist` (`^spotify:track:[a-zA-Z0-9]{22}$`), garantindo que apenas identificadores válidos de músicas sejam encaminhados ao Spotify. |
| **T-03** | Ataques de Cross-Site Request Forgery (CSRF) forçando exclusão de dados ou sincronização não autorizada. | Alto | Decorador `@require_same_origin` em todos os métodos `POST`, validando cabeçalhos `Origin` e `Referer` contra o Host legítimo, em conjunto com cookies `SameSite=Lax`. |

---

### R — Repudiation (Não-Repúdio)
| ID | Cenário de Ameaça | Impacto | Contramedida Implementada no Projeto |
| :--- | :--- | :--- | :--- |
| **R-01** | Usuário alega que dados foram excluídos sem sua solicitação voluntária. | Baixo | Endpoint `/api/delete_my_data` requer confirmação explícita na UI (`confirm()`) e chamada autenticada via POST com validação de origem. |
| **R-02** | Falhas na API externa ou na criação de playlists sem rastreabilidade. | Médio | Registro em logger estruturado (`app.logger.warning` / `app.logger.error`) contendo a classe da exceção, timestamps e status codes, sem registrar credenciais ou tokens em texto claro. |

---

### I — Information Disclosure (Vazamento de Informações)
| ID | Cenário de Ameaça | Impacto | Contramedida Implementada no Projeto |
| :--- | :--- | :--- | :--- |
| **I-01** | Tokens de acesso do Spotify vazam para scripts de terceiros ou extensões do navegador. | Crítico | **Padrão BFF:** O navegador do usuário nunca recebe o `access_token` nem o `refresh_token`. Apenas cookies de sessão protegidos com flags `HttpOnly`, `SameSite=Lax` e `Secure` trafegam entre o cliente e o servidor. |
| **I-02** | Ataques de Cross-Site Scripting no cliente (DOM-XSS) roubam informações da tela ou manipulam ações. | Alto | Reescrita de toda a interface para utilizar a DOM API (`createElement`/`textContent`). Eliminação completa de interpolação insegura via `innerHTML`. Injeção de Content-Security-Policy (CSP) estrita. |
| **I-03** | Dados sensíveis de músicas ou do perfil do usuário ficam salvos em caches públicos de proxies ou histórico. | Médio | Injeção global dos cabeçalhos `Cache-Control: no-store, no-cache, must-revalidate, max-age=0` e `Pragma: no-cache` em todos os endpoints `/api/*`. |
| **I-04** | Vazamento de credenciais do Spotify ou segredos do Flask no histórico do Git. | Crítico | Exclusão explícita no `.gitignore`, fail-fast no início da aplicação (`validate_environment`) e auditoria contínua de segredos via `pip-audit`. |

---

### D — Denial of Service (Negação de Serviço)
| ID | Cenário de Ameaça | Impacto | Contramedida Implementada no Projeto |
| :--- | :--- | :--- | :--- |
| **D-01** | Atacante envia payloads gigantescos para exaurir a memória RAM do servidor (Memory Exhaustion). | Alto | Configuração de `MAX_CONTENT_LENGTH = 1 * 1024 * 1024` (1MB), rejeitando requisições excessivas imediatamente com código HTTP 413. |
| **D-02** | Inundação de requisições às rotas de sincronização, autenticação ou criação de playlist. | Alto | Rate limiting granular via `Flask-Limiter` com limites por minuto e por dia baseados em sessão autenticada e IP remoto. Resposta padronizada com HTTP 429 e `Retry-After`. |
| **D-03** | A API do Spotify retorna erro 429 e o app entra em loop, derrubando o serviço ou sendo bloqueado pelo Spotify. | Alto | Implementação de `spotify_request` com leitura do cabeçalho `Retry-After`, pausa síncrona defensiva e backoff exponencial limitado a 3 tentativas. |

---

### E — Elevation of Privilege (Elevação de Privilégios)
| ID | Cenário de Ameaça | Impacto | Contramedida Implementada no Projeto |
| :--- | :--- | :--- | :--- |
| **E-01** | Usuário tenta criar playlists na conta de outro usuário manipulando identificadores de sessão. | Crítico | O token descriptografado em memória pertence exclusivamente ao `session.sid` do usuário autenticado no cookie daquela conexão; o Spotify valida a titularidade do token em cada chamada. |
| **E-02** | O aplicativo solicita permissões excessivas que não utiliza, aumentando a superfície de ataque em caso de comprometimento. | Médio | Princípio do Menor Privilégio: a aplicação solicita estritamente 3 escopos (`user-library-read`, `playlist-modify-public`, `playlist-modify-private`). Não tem acesso a streaming, e-mail ou dados de pagamento. |

---

## 3. Matriz Residual de Risco

| Ameaça STRIDE | Severidade Bruta | Contramedida Implementada | Risco Residual |
| :--- | :---: | :--- | :---: |
| **Spoofing (OAuth/Sessão)** | Crítico | PKCE S256 + State Criptográfico + Rotação de Sessão | **Baixo** |
| **Tampering (Sessão/Payload)** | Alto | MultiFernet (HMAC-SHA256) + Validação Regex + CSRF Origin Check | **Baixo** |
| **Repudiation (Ações de Dados)** | Baixo | Logs sem PII + Confirmação Explícita de Exclusão | **Muito Baixo** |
| **Information Disclosure (Tokens/XSS)** | Crítico | BFF + Cookies HttpOnly + DOM API (textContent) + CSP | **Muito Baixo** |
| **Denial of Service (DoS/API)** | Alto | MAX_CONTENT_LENGTH (1MB) + Flask-Limiter + 429 Backoff | **Baixo** |
| **Elevation of Privilege (Scopes)** | Médio | Menor Privilégio de Escopos + Tokens Isolados por Sessão | **Muito Baixo** |

---

## 4. Auditoria e Revisão Periódica

A modelagem de ameaças deste documento deve ser revisada:
1. Sempre que novos escopos do Spotify forem solicitados.
2. Quando houver alteração na stack tecnológica (ex: migração para novo banco de sessão).
3. Semestralmente, como parte da governança de segurança do projeto.
