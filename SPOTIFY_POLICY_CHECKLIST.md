# SPOTIFY_POLICY_CHECKLIST.md — Checklist Formal de Conformidade

Este documento audita e atesta a conformidade técnica, jurídica e de design do **Playlist Manager for Spotify** com o [Spotify Developer Terms](https://developer.spotify.com/terms), [Spotify Developer Policy](https://developer.spotify.com/policy) e a Lei Geral de Proteção de Dados (LGPD — Lei nº 13.709/2018).

---

## 1. Princípios de Dados e Privacidade (LGPD & Spotify Policy)

| Requisito / Diretriz | Status | Implementação Técnica no Projeto |
| :--- | :---: | :--- |
| **Minimização de Dados (Data Minimization)** | Conforme | Apenas 3 escopos mínimos são solicitados (`user-library-read`, `playlist-modify-public`, `playlist-modify-private`). Nenhum dado de streaming, histórico, seguidores ou dados de perfil extendidos é requisitado. |
| **Transparência de Finalidade** | Conforme | Telas `/login-page`, `/privacy` e `/terms` detalham explicitamente por que cada permissão é exigida e como as faixas são processadas. |
| **Retenção Curta e Expiração Automática** | Conforme | Sessão (`PERMANENT_SESSION_LIFETIME = 24h`) e cache de músicas (`TRACKS_CACHE_TTL = 24h`) expiram em 24 horas, eliminando acúmulo desnecessário de dados. |
| **Criptografia em Repouso** | Conforme | Todos os tokens e dados de sessão são cifrados com chaves de 256 bits (`AES-Fernet / MultiFernet`) antes de qualquer gravação em disco (`.flask_session/`) ou Redis. |
| **Direito de Eliminação / Exclusão (LGPD Art. 18)** | Conforme | Botão no cabeçalho do app aciona `POST /api/delete_my_data`, expurgando fisicamente os arquivos de sessão no servidor. |
| **Revogação Fácil pelo Usuário** | Conforme | Instruções claras com link direto para `https://www.spotify.com/account/apps/` disponíveis na tela de login, após logout e nas políticas de privacidade. |
| **Não Comercialização de Dados** | Conforme | Cláusula explícita em `/privacy` atestando que nenhum dado é vendido, repassado ou utilizado para fins publicitários ou rastreamento. |

---

## 2. Autenticação e Segurança da API (OAuth 2.0 & RFC 7636)

| Requisito / Diretriz | Status | Implementação Técnica no Projeto |
| :--- | :---: | :--- |
| **OAuth 2.0 com PKCE S256** | Conforme | Implementado fluxo PKCE obrigatório (`code_verifier` + `code_challenge` SHA-256) com defesa em profundidade mantendo `client_secret` simultâneo. |
| **Proteção Anti-CSRF no OAuth (`state`)** | Conforme | Geração criptográfica com `secrets.token_urlsafe(32)` e verificação em tempo constante (`secrets.compare_digest`). State é descartado imediatamente após uso. |
| **Prevenção de Fixação de Sessão** | Conforme | `session.clear()` é executado no `/callback` antes de salvar as credenciais autenticadas. |
| **Arquitetura BFF (Backend-For-Frontend)** | Conforme | Tokens de acesso e refresh tokens nunca chegam ao navegador do cliente; o navegador mantém apenas cookies protegidos (`HttpOnly`, `SameSite=Lax`, `Secure` em prod). |
| **Respeito a Rate Limits do Spotify (HTTP 429)** | Conforme | Implementado `spotify_request()` com detecção de 429, extração de `Retry-After` e backoff exponencial com até 3 tentativas automáticas. |
| **Endpoints Modernos da API** | Conforme | Uso de `/playlists/{id}/items` para adição de faixas, garantindo compatibilidade com novas contas de desenvolvedor do Spotify. |

---

## 3. Diretrizes de Marca e Design (Spotify Branding Guidelines)

| Requisito / Diretriz | Status | Implementação Técnica no Projeto |
| :--- | :---: | :--- |
| **Identidade Visual Independente** | Conforme | O aplicativo adota nomenclatura conforme as diretrizes de marca do Spotify ("Playlist Manager for Spotify", sem iniciar com "Spotify") e deixa evidente em todas as páginas que é uma ferramenta independente e não operada pelo Spotify AB. |
| **Uso da Cor Spotify Green** | Conforme | Utiliza o tom oficial `#1DB954` em botões de ação e ícones de marca. |
| **Logotipos Oficiais** | Conforme | Ícones oficiais da marca Spotify (FontAwesome `fa-brands fa-spotify`) empregados sem distorção, respeitando contraste e espaçamento. |
| **Abertura de Links Externos** | Conforme | Links que levam ao Spotify utilizam `target="_blank"` e `rel="noopener noreferrer"`. |

---

## 4. Endurecimento Web e Frontend (OWASP ASVS)

| Requisito / Diretriz | Status | Implementação Técnica no Projeto |
| :--- | :---: | :--- |
| **Prevenção de DOM-XSS** | Conforme | Eliminação de `innerHTML` para injeção de dados; renderização 100% segura com DOM API (`createElement`/`textContent`) em `static/js/app.js`. |
| **Separação de Scripts** | Conforme | Código JavaScript totalmente desacoplado dos templates HTML; inclusão externa com `<script src="..." defer>` e remoção de manipuladores inline (`onclick`, `oninput`, etc.). |
| **Content Security Policy (CSP)** | Conforme | CSP estrita com `default-src 'self'`, fontes e estilos restritos a origens seguras, e `frame-ancestors 'none'`. |
| **Anti-Clickjacking** | Conforme | `X-Frame-Options: DENY` e CSP `frame-ancestors 'none'`. |
| **MIME Sniffing** | Conforme | `X-Content-Type-Options: nosniff`. |
| **Proteção de Cache em APIs** | Conforme | `Cache-Control: no-store, no-cache, must-revalidate, max-age=0` e `Pragma: no-cache` em `/api/*`. |

---

## 5. Declaração de Conformidade Final

O aplicativo **Playlist Manager for Spotify** atende plenamente aos critérios exigidos pelo Spotify para transição de modo de desenvolvimento para cota de produção e cumpre com as exigências da LGPD brasileira.
