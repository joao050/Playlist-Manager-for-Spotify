# Guia de Contribuição — Playlist Manager for Spotify

Seja bem-vindo ao time de desenvolvimento do **Playlist Manager for Spotify**!  
Este guia foi feito para que qualquer pessoa consiga configurar o ambiente, entender o fluxo de trabalho e colaborar com código de forma segura, organizada e sem dores de cabeça com conflitos de versão.

---

## 1. Primeiros Passos: O Básico do Git e GitHub

Se você nunca usou o Git ou precisa de uma revisão rápida, aqui está o essencial:

* **Repositório:** É a "pasta" onde o código de todo o projeto vive no GitHub.
* **Clone:** Fazer uma cópia do repositório do GitHub para o seu computador.
* **Branch (Ramificação):** Uma cópia isolada da linha do tempo do projeto. Permite que você faça alterações sem estragar o que já está funcionando.
* **Commit:** Uma "foto" ou ponto de salvamento das alterações que você fez.
* **Push:** Enviar seus commits do seu computador para o GitHub.
* **Pull:** Baixar as novidades e atualizações que os outros fizeram no GitHub para o seu computador.
* **Pull Request (PR):** Um pedido formal no GitHub dizendo: *"Terminei minha funcionalidade na minha branch e gostaria que ela fosse integrada ao projeto principal"*.

---

## 2. Nossa Estratégia de Branches (Gitflow Simplificado)

Para mantermos o projeto organizado e seguro, trabalhamos com três níveis de branches:

```text
  main (Produção: Estável, espelho do deploy online)
    ▲
    │ (Apenas merges aprovados via PR de releases estáveis)
  develop (Integração: Onde as novas funcionalidades se encontram)
    ▲
    │ (Merges via Pull Request após passar nos testes)
  feature/nome-da-tarefa (Sua branch de trabalho pessoal)
```

1. **`main`:** É a versão em produção do app (deploy no Render). **Ninguém faz commits diretos nela.**
2. **`develop`:** É a branch de desenvolvimento central. Todas as novas funcionalidades são enviadas para cá via Pull Request.
3. **`feature/<nome>`:** A branch onde você programa sua tarefa isoladamente (ex: `feature/audio-preview` ou `feature/filtro-artista`).

---

## 3. Passo a Passo do Fluxo de Trabalho

### Passo 1: Clonar o Repositório
Abra o seu terminal na pasta onde guarda seus projetos e rode:
```bash
git clone https://github.com/joao050/Playlist-Manager-for-Spotify.git
cd Playlist-Manager-for-Spotify
```

### Passo 2: Sincronizar com a branch `develop`
Antes de começar qualquer tarefa, garanta que você está na branch `develop` atualizada:
```bash
git checkout develop
git pull origin develop
```

### Passo 3: Criar a sua Branch de Funcionalidade
Escolha um nome descritivo para a sua branch começando com `feature/`:
```bash
git checkout -b feature/minha-funcionalidade
```
*(Exemplo: `git checkout -b feature/filtro-busca-avancada`)*

### Passo 4: Configurar o Ambiente Local

1. **Crie e ative um ambiente virtual Python (opcional, mas recomendado):**
   ```bash
   python -m venv venv
   # No Windows (PowerShell):
   .\venv\Scripts\Activate.ps1
   # No Linux/Mac:
   source venv/bin/activate
   ```

2. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Crie seu arquivo `.env`:**
   Copie o modelo de exemplo:
   ```bash
   cp .env.example .env
   ```
   Abra o arquivo `.env` e preencha com suas credenciais do Spotify Developer Dashboard e chaves locais.  
   > ⚠️ **ATENÇÃO MÁXIMA:** O arquivo `.env` contém segredos locais e **JAMAIS** deve ser comitado no GitHub. O `.gitignore` já bloqueia esse arquivo, mas certifique-se de nunca forçar a inclusão dele.

4. **Inicie o servidor para testar:**
   ```bash
   python app.py
   ```
   Acesse no navegador: `http://127.0.0.1:5000`.

### Passo 5: Fazer Commits das suas Alterações
Conforme for desenvolvendo, salve seus progressos com commits claros:
```bash
git add .
git commit -m "feat: adiciona filtro por ano de lançamento"
```
*Dica:* Prefira commits pequenos e objetivos a um único commit gigante.

### Passo 6: Rodar os Testes Automatizados (Obrigatório)
Antes de enviar seu código, rode a suíte de testes de segurança e estabilidade:
```bash
pytest
```
Todos os testes devem passar com sucesso (`PASSED`). Se algum teste falhar, analise o motivo e ajuste o código antes de subir.

### Passo 7: Enviar para o GitHub e Abrir o Pull Request
1. Envie a sua branch para o repositório remoto:
   ```bash
   git push -u origin feature/minha-funcionalidade
   ```
2. Acesse o repositório no GitHub: `https://github.com/joao050/Playlist-Manager-for-Spotify`.
3. Você verá um botão verde **"Compare & pull request"**. Clique nele.
4. **IMPORTANTE:** Certifique-se de que a **base branch** do PR seja **`develop`** (e não `main`):
   - `base: develop` ◄ `compare: feature/minha-funcionalidade`.
5. Preencha o template do Pull Request descrevendo o que foi feito e marque os itens do checklist.
6. Envie o PR e avise o mantenedor para revisão!

---

## 4. Dicas para Trabalhar com o Google Antigravity

Como você está utilizando o **Google Antigravity**, você tem uma IA trabalhando lado a lado com você. Para tirar o melhor proveito dela:

1. **Deixe o Antigravity ler o contexto:**  
   No início da conversa, peça para ele:  
   *"Estou trabalhando no Playlist Manager for Spotify. Leia o PROJECT_TASKS.md e o PROJECT_MAP.md para entender a arquitetura antes de começarmos."*
2. **Peça para ele criar a branch com você:**  
   *"Crie uma branch `feature/nome-da-feature` a partir da develop para começarmos a tarefa #FEAT-0X."*
3. **Valide com testes sempre:**  
   Ao final da implementação, peça:  
   *"Rode o pytest para confirmar que nossa alteração não quebrou nenhum teste existente."*
4. **Respeite a arquitetura BFF:**  
   Tokens do Spotify nunca devem ir para o JavaScript do navegador; chamadas à API do Spotify devem ser sempre mediadas pelo backend Flask (`app.py`).

---

## 5. Dúvidas Frequentes

* **E se a `develop` avançou enquanto eu trabalhava na minha branch?**  
  Basta atualizar sua branch local:
  ```bash
  git checkout develop
  git pull origin develop
  git checkout feature/sua-feature
  git merge develop
  ```
  Resolva eventuais conflitos, teste com `pytest` e envie novamente com `git push`.

* **Posso propor uma ideia nova que não está no backlog?**  
  Com certeza! Abra uma conversa com o time, crie uma Issue no GitHub ou sugira no arquivo `PROJECT_TASKS.md`.
