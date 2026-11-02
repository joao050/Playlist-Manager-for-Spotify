---
trigger: always_on
description: Diretrizes mandatórias de economia de contexto, navegação por mapa e persistência de tarefas entre conversas.
---

# Regra Permanente: Economia de Contexto e Navegação (Playlist Manager for Spotify)

Esta regra é de cumprimento obrigatório pelo assistente em qualquer conversa neste workspace.

## 1. Inicialização e Retomada de Contexto
- **Sempre no início de cada conversa** e antes de qualquer ação ou resposta sobre tarefas do projeto:
  1. Leia primeiramente `PROJECT_TASKS.md` para identificar a fase atual, a tarefa em andamento e as decisões tomadas.
  2. Em seguida, consulte o `PROJECT_MAP.md` para localizar com precisão onde o código relevante reside.
- **Não faça varredura geral:** Se a solicitação do usuário corresponder a uma tarefa já catalogada no backlog ou em andamento, assuma imediatamente o trabalho utilizando o `#ID` e os arquivos indicados no mapa, **sem reexplorar a árvore de diretórios ou reler arquivos desnecessários**.
- Se a solicitação do usuário for uma demanda nova não prevista, registre-a no backlog de `PROJECT_TASKS.md` antes de começar a codificar.

## 2. Leitura Cirúrgica e Proteção de Tokens
- **Consulte o mapa antes de ler arquivos:** Use o `PROJECT_MAP.md` (seção *Se for X, mexa em Y*) para decidir quais arquivos abrir.
- **Leitura parcial por trechos:** Nunca leia arquivos inteiros quando apenas uma função ou bloco for necessário; utilize limites de linhas (`StartLine`/`EndLine`).
- **Arquivos proibidos:** NUNCA abra sem solicitação explícita os arquivos listados na seção 8 do `PROJECT_MAP.md` (como `liked_songs.json`, `liked_songs.csv`, `.flask_session/*` e scripts legados).
- Nunca execute buscas cegas ou varreduras recursivas no projeto sem pedir confirmação prévia do usuário.

## 3. Manutenção da Memória de Trabalho
Ao concluir qualquer tarefa:
1. **Atualize `PROJECT_TASKS.md`:**
   - Mova a tarefa de *Em andamento* para *Concluídas*, registrando no formato compacto `[x] #ID | data | o que mudou | arquivos`.
   - Se a seção *Concluídas* ultrapassar ~40 itens, condense as tarefas mais antigas em um breve resumo temático de 2 a 3 linhas.
   - Registre eventuais novas decisões de arquitetura e bugs ou pendências conhecidos nas seções correspondentes.
2. **Atualize `PROJECT_MAP.md` apenas se necessário:**
   - Modifique o mapa SOMENTE se houver alteração estrutural relevante (novos arquivos, arquivos renomeados/removidos, ou novas rotas e funções públicas). Atualize cirurgicamente apenas as linhas afetadas.

## 4. Estilo de Comunicação
- **Respostas objetivas e curtas:** Evite imprimir arquivos completos no chat. Mostre apenas o diff ou o trecho modificado.
- Mantenha comentários em português e forneça explicações conceituais concisas e didáticas sobre as alterações efetuadas.
