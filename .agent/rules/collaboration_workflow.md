---
trigger: always_on
description: Diretrizes obrigatórias para colaboradores e assistentes Antigravity sobre fluxo Git, segurança e arquitetura do projeto.
---

# Regras de Colaboração e Fluxo de Trabalho (Google Antigravity)

Esta regra é de cumprimento obrigatório pelo assistente ao atuar em qualquer tarefa deste repositório.

## 1. Estratégia de Branches & Proteção de Código
- **NUNCA faça commit direto nas branches `main` ou `develop`:** O trabalho deve ser realizado obrigatoriamente em uma branch dedicada de funcionalidade (`feature/<nome-descritivo>`).
- Ao iniciar uma nova tarefa:
  1. Certifique-se de basear a nova branch a partir da `develop` mais recente:
     `git checkout develop && git pull origin develop`
  2. Crie a branch de trabalho:
     `git checkout -b feature/<nome-da-tarefa>`
- Pull Requests devem sempre ter como destino (**base branch**) a branch **`develop`**. A branch `main` é exclusiva para versões em produção estáveis.

## 2. Princípios Inegociáveis de Arquitetura e Segurança
Ao implementar qualquer funcionalidade ou melhoria de UI:
1. **Padrão BFF (Backend-For-Frontend):**
   - O frontend (`static/js/app.js` ou templates) **NUNCA** deve manipular ou receber `access_token` ou `refresh_token` do Spotify.
   - Toda comunicação com a API do Spotify deve passar pelas rotas do backend em Flask (`app.py`), utilizando as funções seguras `spotify_get()`, `spotify_post()`, etc.
2. **Prevenção Rigorosa de DOM-XSS:**
   - **JAMAIS** utilize `innerHTML` com variáveis concatenadas ou dados recebidos de APIs externas.
   - Utilize a DOM API segura (`document.createElement()`, `element.textContent`, etc.).
3. **Proteção de Segredos e Arquivos Locais:**
   - **NUNCA** comite, altere o tracking ou exponha o conteúdo do arquivo `.env` ou pastas de sessão (`.flask_session/`).
4. **Validação Obrigatória com Pytest:**
   - Antes de considerar qualquer tarefa pronta, execute a suíte de testes:
     `pytest`
   - Garanta que todos os testes passem com 100% de sucesso. Não quebre a suíte existente de segurança (Fases 0 a 9).

## 3. Gestão e Registro de Tarefas
- Consulte `PROJECT_TASKS.md` antes de começar para verificar as tarefas disponíveis e seus critérios de aceite.
- Ao assumir uma tarefa, marque seu status em `PROJECT_TASKS.md` como em andamento com o responsável.
- Ao concluir a tarefa, marque o checkbox correspondente em `PROJECT_TASKS.md` antes de abrir o Pull Request.
