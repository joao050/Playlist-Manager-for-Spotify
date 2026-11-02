## 📝 Descrição da Alteração
Descreva de forma clara e resumida o que este Pull Request implementa, corrige ou aprimora:
> Exemplo: Implementa o filtro de busca por nome de música e artista no frontend sem recarregar a página (#FEAT-01).

---

## 🎯 Tarefa Relacionada
- ID da Tarefa em `PROJECT_TASKS.md`: `#FEAT-0`

---

## 🛡️ Checklist de Qualidade e Segurança (Obrigatório)

Antes de solicitar a revisão, marque com [x] todos os itens verificados:

- [ ] **Branch Base Correta:** O Pull Request está apontando para a branch `develop` (e NÃO para a `main`).
- [ ] **Testes Automatizados:** Executei `pytest` localmente e todos os testes passaram com sucesso (0 falhas).
- [ ] **Zero Vazamento de Segredos:** Confirmei que o arquivo `.env`, credenciais reais ou chaves de API NÃO estão incluídos neste commit.
- [ ] **Arquitetura BFF Respeitada:** Tokens de autenticação do Spotify residem apenas no servidor e não foram expostos ao código JavaScript do cliente.
- [ ] **Prevenção de XSS:** A renderização dinâmica no frontend utiliza DOM API segura (`textContent`, `createElement`) ou templates protegidos, sem `innerHTML` vulnerável.
- [ ] **Diretrizes de Marca Spotify:** A interface mantém a conformidade de marca (nome oficial "Playlist Manager for Spotify", uso correto do verde `#1DB954` e ícones oficiais).
- [ ] **Documentação Atualizada:** Se necessário, registrei alterações ou atualizei o status da tarefa em `PROJECT_TASKS.md`.

---

## 📸 Demonstração Visual (Opcional para mudanças de UI)
*(Se você alterou elementos visuais ou de design, anexe um print ou gif da tela no computador ou celular).*
