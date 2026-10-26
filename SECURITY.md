# Diretrizes de Segurança e Governança (SECURITY.md)

Este documento estabelece a política oficial de segurança, reporte responsável de vulnerabilidades, procedimento de rotação de credenciais e o plano de resposta a incidentes do **Playlist Manager for Spotify**.

---

## 1. Política de Divulgação de Vulnerabilidades (Vulnerability Disclosure Policy)

Encorajamos a comunidade e pesquisadores de segurança a reportar vulnerabilidades de forma responsável. Comprometemo-nos a analisar, validar e corrigir falhas com a máxima celeridade.

### Como Reportar uma Vulnerabilidade
* **Canal Seguro:** Envie um e-mail com o assunto `[SECURITY VULNERABILITY] Playlist Manager for Spotify` para o endereço do mantenedor do projeto ou abra um aviso de segurança confidencial (*Private Security Advisory*) na aba **Security** do repositório GitHub.
* **Informações Necessárias:**
  - Descrição detalhada da vulnerabilidade encontrada.
  - Passos reproduzíveis (PoC ou cenário conceitual de teste).
  - Impacto potencial estimado (confidencialidade, integridade, disponibilidade).
  - Versão ou commit do código testado.
* **Não Realize:**
  - Ataques de negação de serviço (DoS/DDoS) contra instâncias públicas ativas.
  - Testes que envolvam acesso ou exclusão de dados de terceiros.
  - Divulgação pública (*Zero-Day*) antes da aplicação da correção.

### Prazos e Níveis de Serviço (SLA)
| Severidade (CVSS) | Confirmação Inicial | Prazo Estimado de Correção |
| :--- | :--- | :--- |
| **Crítica (9.0 - 10.0)** | Em até 24 horas | Em até 7 dias úteis |
| **Alta (7.0 - 8.9)** | Em até 48 horas | Em até 14 dias úteis |
| **Média (4.0 - 6.9)** | Em até 72 horas | Em até 30 dias úteis |
| **Baixa (0.1 - 3.9)** | Em até 5 dias | Próxima versão agendada |

---

## 2. Procedimento Operacional Padrão: Rotação de Segredos (Runbook)

A rotação periódica ou emergencial de segredos é um pilar essencial para a segurança de longo prazo.

### 2.1 Rotação da `ENCRYPTION_KEY` (Sem Downtime via `MultiFernet`)
O sistema suporta nativamente rotação de chaves criptográficas sem invalidar as sessões ativas dos usuários:

1. **Gerar Nova Chave Fernet:**
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
2. **Atualizar a Variável no Ambiente:**
   Configure a variável `ENCRYPTION_KEY` mantendo a chave nova como primária (para escrita) e a chave anterior como secundária (para leitura/descriptografia), separadas por vírgula:
   ```env
   ENCRYPTION_KEY=NOVA_CHAVE_GERADA,CHAVE_ANTIGA_EM_USO
   ```
3. **Reiniciar o Serviço:** O `MultiFernet` descriptografará dados antigos usando a chave antiga e cifrará novos dados usando a nova.
4. **Desativação da Chave Antiga:** Após 24 horas (tempo máximo de expiração do TTL das sessões), remova a chave antiga do `.env`, deixando apenas a chave nova:
   ```env
   ENCRYPTION_KEY=NOVA_CHAVE_GERADA
   ```

### 2.2 Rotação da `FLASK_SECRET_KEY`
1. Gerar novo segredo de alta entropia (mínimo 32 bytes):
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
2. Atualizar `FLASK_SECRET_KEY` no `.env` ou no painel de produção (Render/Fly.io).
3. Reiniciar a aplicação. Todas as sessões existentes serão invalidadas de forma limpa, exigindo novo login dos usuários.

### 2.3 Rotação de Credenciais do Spotify (`SPOTIPY_CLIENT_SECRET`)
1. Acesse o [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Selecione o App, vá em **Settings** e acione **Rotate Client Secret** (o Spotify permite manter dois segredos ativos temporariamente para transição).
3. Atualize a variável `SPOTIPY_CLIENT_SECRET` no ambiente de produção.
4. Reinicie o serviço e revogue o segredo antigo no dashboard do Spotify.

---

## 3. Plano de Resposta a Incidentes (Incident Response Plan - IRP)

Em caso de suspeita ou confirmação de incidente de segurança (como vazamento de chave ou exploração de falha):

```text
[ IDENTIFICAÇÃO ] ──▶ [ CONTENÇÃO ] ──▶ [ ERRADICAÇÃO ] ──▶ [ RECUPERAÇÃO ] ──▶ [ LIÇÕES APRENDIDAS ]
```

### Fase 1: Identificação e Triagem
* Avaliar alertas de monitoramento, logs de erro anômalos ou comunicações de vulnerabilidade.
* Determinar o escopo do incidente: credenciais afetadas, dados expostos ou sistemas comprometidos.

### Fase 2: Contenção Imediata
* **Revogação Imediata de Credenciais:** Rotacionar imediatamente `SPOTIPY_CLIENT_SECRET`, `FLASK_SECRET_KEY` e `ENCRYPTION_KEY`.
* **Expurgo Emergencial de Sessões:** Excluir todos os arquivos de sessão em disco ou limpar as chaves no Redis:
  ```bash
  # Limpeza emergencial de sessões locais
  rm -rf .flask_session/*
  ```
* Se necessário, suspender temporariamente o tráfego pausando o serviço web no painel do Render/Fly.io.

### Fase 3: Erradicação
* Identificar e corrigir a causa raiz (ex: correção de código, atualização de dependência vulnerável via `pip-audit`).
* Auditar o histórico de commits do repositório para confirmar ausência de segredos commitados.

### Fase 4: Recuperação e Validação
* Realizar novo deploy da versão corrigida com as variáveis de ambiente renovadas.
* Executar a suíte completa de testes automatizados (`test_phase3.py` a `test_phase7.py`).
* Reativar o tráfego público e monitorar os logs de acesso por 48 horas.

### Fase 5: Lições Aprendidas e Comunicação
* Registrar o incidente no [`SECURITY_CHANGELOG.md`](./SECURITY_CHANGELOG.md) e na modelagem de ameaças.
* Conforme exigido pela LGPD (Art. 48), caso haja risco relevante aos titulares de dados pessoais, realizar a devida comunicação à Autoridade Nacional de Proteção de Dados (ANPD) e aos usuários impactados.
