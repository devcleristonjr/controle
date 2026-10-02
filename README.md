# 📦 Controle de Materiais

Sistema web para **controle e acompanhamento de materiais alocados nos pontos**, desenvolvido em Flask e estruturado para atender operações com pontos, materiais e territórios.

O projeto está em desenvolvimento contínuo, com foco em uma interface simples, responsiva e adequada para cadastro de pontos, alocação de materiais e acompanhamento de ocorrências.

---

## 📌 Sobre o projeto

O **Controle de Materiais** centraliza informações sobre materiais alocados nos pontos, suas condições e as ocorrências registradas. O sistema não opera com entrada, saída ou zeramento diário dos materiais.

A aplicação possui uma área administrativa para acompanhamento dos materiais e dos pontos, com acesso rápido pelo menu ("+ Novo Ponto") para cadastrar um ponto e já alocar materiais existentes no mesmo formulário.

O projeto utiliza uma arquitetura baseada em **Flask, Blueprints, SQLAlchemy, Flask-Migrate e templates Jinja2**, permitindo a evolução gradual da aplicação sem concentrar toda a lógica em um único arquivo.

---

## 🚧 Status atual

**Em desenvolvimento ativo.**

A estrutura principal da aplicação já está implementada e o sistema possui módulos para acompanhar pontos, alocações de materiais e ocorrências.

### Atualmente estruturado

* 🔐 Autenticação e controle de acesso
* 📊 Dashboard
* 🗺️ Mapa dos pontos
* 📍 Pontos e responsáveis opcionais
* 📦 Cadastro e alocação de materiais
* 🔄 Ocorrências e reposições das alocações
* 👥 Usuários
* 🧭 Territórios
* 🏙️ Municípios
* ➕ Cadastro rápido de pontos já com materiais vinculados
* 📷 Suporte a informações/fotos relacionadas aos pontos
* 📍 Captura de localização através do navegador
* 🗄️ Banco de dados com SQLAlchemy
* 🔄 Controle de alterações do banco através de Flask-Migrate
* 📱 Interface responsiva para utilização em diferentes dispositivos

Alguns módulos administrativos e funcionalidades complementares continuam em evolução.

---

# 🛠️ Tecnologias

## Backend

* **Python**
* **Flask**
* **SQLAlchemy**
* **Flask-Migrate**
* **Flask-Login**
* **Flask-WTF**
* **Jinja2**

## Frontend

* **HTML5**
* **CSS3**
* **JavaScript**
* **Bootstrap 5**
* **Bootstrap Icons**

## Mapas

* **Leaflet**
* **OpenStreetMap**

## Banco de dados

A aplicação utiliza SQLAlchemy como camada de acesso ao banco e Flask-Migrate para gerenciamento das migrações.

O banco utilizado pode variar de acordo com a configuração do ambiente.

---

# 🧩 Principais módulos

## 📊 Dashboard

Área inicial do sistema destinada à visualização geral dos materiais e pontos.

---

## 🗺️ Mapa

Visualização dos pontos utilizando mapa interativo.

A aplicação utiliza Leaflet integrado ao OpenStreetMap para apresentação das informações geográficas.

---

## 📍 Pontos

Permite trabalhar com os locais onde os materiais estão distribuídos e acompanhados.

Cada ponto reúne localização, responsáveis opcionais e materiais alocados, com ocorrências e reposições acompanhadas para cada alocação. Não há fluxo de entrada e saída de materiais.

---

## 📦 Materiais

Módulo responsável pelo cadastro e gerenciamento dos materiais controlados pelo sistema.

Entre as operações previstas estão:

* cadastro;
* consulta;
* atualização;
* organização dos materiais;
* alocação de materiais aos pontos e acompanhamento de suas ocorrências.

---

## 🔄 Registros operacionais

Área destinada ao acompanhamento dos materiais alocados nos pontos, incluindo ocorrências e reposições.

---

## 👥 Usuários

Módulo destinado ao gerenciamento dos usuários que possuem acesso à área administrativa do sistema.

O controle de autenticação é realizado utilizando Flask-Login.

---

## 🧭 Territórios

Estrutura utilizada para organização territorial dos pontos de estoque.

---

## 🏙️ Municípios

Cadastro e organização dos municípios relacionados aos pontos e operações do sistema.

---

# ➕ Cadastro rápido de ponto com materiais

O menu principal possui o atalho **"+ Novo Ponto"**, disponível para usuários com permissão de cadastro, que leva diretamente ao formulário de criação de ponto.

```text
/estoques/novo
```

O mesmo formulário já inclui a seção **Materiais**, com todos os materiais ativos cadastrados no sistema. O usuário pode marcar os materiais desejados e informar a quantidade; ao salvar, o ponto e os vínculos de materiais são criados na mesma transação (se algum material falhar na validação, nada é salvo).

---

# 🏗️ Arquitetura

A aplicação utiliza **Blueprints do Flask** para separar os diferentes módulos.

Uma visão simplificada da arquitetura é:

```text
Flask Application
│
├── Autenticação
│
├── Dashboard
│
├── Mapa
│
├── Materiais
│
├── Pontos de estoque
│
├── Alocações e ocorrências
│
├── Usuários
│
├── Territórios
│
├── Municípios
│
└── Pontos de estoque (cadastro inclui vinculação de materiais)
```

A camada visual utiliza templates Jinja2 com herança de templates, centralizados em `base.html`.

---

# 📁 Estrutura do projeto

A estrutura geral segue uma organização semelhante a:

```text
estoque-bahia/
│
├── app/
│   ├── models/
│   ├── routes/
│   ├── forms/
│   ├── templates/
│   │   ├── base.html
│   │   └── estoques/
│   │
│   └── static/
│       ├── css/
│       ├── js/
│       └── ...
│
├── migrations/
│
├── scripts/
│
├── tests/
│
├── uploads/
│
├── config.py
├── run.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

A estrutura pode evoluir conforme novos módulos e serviços sejam incorporados ao projeto.

---

# ⚙️ Requisitos

Para executar o projeto localmente, recomenda-se ter instalado:

* Python 3.10 ou superior
* pip
* ambiente virtual Python
* banco de dados configurado conforme o ambiente

---

# 🚀 Instalação

## 1. Clonar o repositório

```bash
git clone https://github.com/devcleristonjr/estoque-bahia.git
```

Entrar no diretório:

```bash
cd estoque-bahia
```

---

## 2. Criar o ambiente virtual

### Windows

```bash
python -m venv .venv
```

Ativar:

```bash
.venv\Scripts\activate
```

### Linux/macOS

```bash
python3 -m venv .venv
```

Ativar:

```bash
source .venv/bin/activate
```

---

## 3. Instalar as dependências

```bash
pip install -r requirements.txt
```

---

# 🔐 Configuração do ambiente

Crie o arquivo `.env` a partir do exemplo disponível no projeto:

```bash
.env.example
```

Configure as variáveis necessárias para o ambiente local.

> O arquivo `.env` não deve ser versionado no Git.

---

# 🗄️ Banco de dados

O projeto utiliza **SQLAlchemy** para interação com o banco e **Flask-Migrate** para controle das alterações da estrutura do banco.

Após configurar o ambiente, execute as migrações disponíveis:

```bash
flask db upgrade
```

Quando forem criadas novas alterações estruturais no banco, uma nova migration deverá ser gerada e posteriormente aplicada.

---

# ▶️ Executando o projeto

Com o ambiente virtual ativado:

```bash
python run.py
```

ou, conforme a configuração do ambiente:

```bash
flask run
```

Depois, acesse a aplicação pelo endereço disponibilizado pelo servidor Flask.

Em ambiente local, normalmente:

```text
http://127.0.0.1:5000
```

---

# 🔄 Migrações

Para criar uma nova migration após alterações nos modelos:

```bash
flask db migrate -m "descricao da alteracao"
```

Depois:

```bash
flask db upgrade
```

Antes de aplicar migrations em produção, recomenda-se revisar o arquivo gerado.

---

# 🗓️ Histórico diário

O histórico é salvo como um snapshot independente antes do fechamento dos pontos. A migration `0012_daily_history` deve ser aplicada em produção:

```bash
flask db upgrade
```

Para gerar e consultar um snapshot manualmente:

```bash
flask create-daily-history
```

Para executar o fluxo completo (snapshot seguido do fechamento já existente):

```bash
flask close-daily-stock
```

O processo de fechamento usa o fuso `America/Bahia` (com fallback para `America/Sao_Paulo`) e falha sem limpar os pontos se não conseguir gravar o snapshot. Se um snapshot manual tiver sido criado e os pontos mudarem depois, o fechamento também é cancelado para evitar limpar dados que o snapshot não contém.

O arquivo [`render.yaml`](./render.yaml) define o Cron Job de produção para **02:00 UTC**, equivalente a **23:00 na Bahia (UTC−3)**. Ao criar/sincronizar esse serviço no Render, configure `DATABASE_URL` e `SECRET_KEY` com os mesmos valores do serviço web e use a mesma região do banco/aplicação. Antes do primeiro fechamento, aplique a migration com `flask db upgrade`. O comando também pode ser disparado manualmente pelo painel do Render para validar a integração.

Usuários autenticados podem consultar os snapshots em **Histórico diário** no menu. Eles são somente leitura e há no máximo um por data.

---

# 🧪 Testes

Os testes ficam organizados no diretório:

```text
tests/
```

Para executar os testes, utilize o framework configurado no projeto.

Exemplo:

```bash
pytest
```

A cobertura de testes deve continuar sendo ampliada principalmente nas áreas relacionadas a:

* autenticação;
* materiais;
* materiais alocados;
* ocorrências;
* permissões;
* responsáveis dos pontos.

---

# 📱 Responsividade

A interface utiliza Bootstrap e foi estruturada para funcionar em:

* computadores;
* notebooks;
* tablets;
* smartphones.

O cadastro de pontos possui atenção especial ao uso em dispositivos móveis, considerando que o cadastro pode ser feito diretamente em campo.

---

# 🔒 Segurança

O projeto utiliza recursos do ecossistema Flask para proteção e controle de acesso, incluindo:

* autenticação de usuários;
* gerenciamento de sessão;
* proteção de formulários;
* validação de dados;
* controle de acesso às áreas administrativas;
* utilização de variáveis de ambiente para configurações sensíveis.

Informações como senhas, chaves secretas e credenciais de banco de dados não devem ser armazenadas diretamente no código ou publicadas no repositório.

---

# 🗺️ Geolocalização

O cadastro de pontos pode utilizar a API de geolocalização disponível no navegador para obter a localização do usuário durante o preenchimento do formulário.

O funcionamento depende da autorização do usuário para compartilhamento da localização pelo navegador.

---

# 📷 Uploads

O sistema possui estrutura para armazenamento de arquivos enviados durante determinadas operações.

Arquivos enviados devem ser tratados com validação adequada de:

* extensão;
* tamanho;
* nome do arquivo;
* tipo de conteúdo;
* local de armazenamento.

---

# 📈 Próximas evoluções

O projeto continuará sendo desenvolvido de forma incremental.

Entre as áreas que podem receber evolução estão:

* aprimoramento da interface;
* refinamento da edição de pontos e responsáveis;
* histórico detalhado de ocorrências e reposições das alocações;
* aprimoramento dos módulos administrativos;
* gerenciamento de usuários;
* gerenciamento de territórios;
* gerenciamento de municípios;
* melhoria da experiência mobile;
* ampliação da cobertura de testes;
* relatórios e exportações;
* melhorias de desempenho;
* aperfeiçoamento das regras de segurança.

Novas funcionalidades devem ser incorporadas preservando a separação entre os módulos e a estrutura de navegação existente.

---

# 🧭 Princípios de desenvolvimento

O projeto segue alguns princípios para facilitar sua manutenção:

### 1. Evitar duplicação

Layouts, componentes e comportamentos compartilhados devem ser reutilizados sempre que possível.

### 2. Separação de responsabilidades

Rotas, modelos, formulários, templates e regras de negócio devem permanecer organizados em suas respectivas camadas.

### 3. Evolução incremental

Novas funcionalidades devem ser adicionadas sem comprometer os módulos que já estão funcionando.

### 4. Banco controlado por migrations

Alterações estruturais do banco devem ser realizadas através do Flask-Migrate.

### 5. Interface consistente

O menu, navegação e elementos visuais principais devem permanecer consistentes em todo o sistema.

---

# 🌐 Repositório

Código-fonte:

https://github.com/devcleristonjr/estoque-bahia

---

# 📄 Licença

A definição da licença deve seguir o que estiver estabelecido no repositório e nos termos definidos pelos responsáveis pelo projeto.

---

## 📌 Projeto em desenvolvimento

O **Controle de Materiais** é um projeto em evolução. A documentação será atualizada à medida que novos módulos, funcionalidades e melhorias forem incorporados ao sistema.
