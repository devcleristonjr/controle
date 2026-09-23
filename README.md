# 📦 Controle de Materiais

Sistema web para **controle e acompanhamento de materiais distribuídos pelos pontos**, desenvolvido em Flask e estruturado para atender operações com pontos, materiais, territórios e coleta de informações em campo.

O projeto está em desenvolvimento contínuo, com foco em uma interface simples, responsiva e adequada tanto para uso administrativo quanto para operações de coleta e atualização de informações dos pontos.

---

## 📌 Sobre o projeto

O **Controle de Materiais** foi desenvolvido para centralizar informações sobre materiais distribuídos pelos pontos, permitindo acompanhar onde estão, quantos existem, suas condições e as ocorrências registradas.

A aplicação possui uma área administrativa para acompanhamento dos materiais e dos pontos, além de uma área específica de **Coleta**, destinada ao cadastro e atualização de informações diretamente nos pontos.

O projeto utiliza uma arquitetura baseada em **Flask, Blueprints, SQLAlchemy, Flask-Migrate e templates Jinja2**, permitindo a evolução gradual da aplicação sem concentrar toda a lógica em um único arquivo.

---

## 🚧 Status atual

**Em desenvolvimento ativo.**

A estrutura principal da aplicação já está implementada e o sistema possui módulos funcionais para diferentes etapas do gerenciamento de estoque.

### Atualmente estruturado

* 🔐 Autenticação e controle de acesso
* 📊 Dashboard
* 🗺️ Mapa dos pontos
* 📍 Pontos
* 📦 Cadastro e gerenciamento de materiais
* 🔄 Registros, ocorrências e reposições
* 👥 Usuários
* 🧭 Territórios
* 🏙️ Municípios
* 📋 Coleta de informações dos pontos
* ➕ Cadastro de novos registros através da Coleta
* ✏️ Atualização de materiais através da Coleta
* 📷 Suporte a informações/fotos relacionadas à coleta
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

Cada ponto reúne localização, responsável, materiais, condições e registros operacionais.

---

## 📦 Materiais

Módulo responsável pelo cadastro e gerenciamento dos materiais controlados pelo sistema.

Entre as operações previstas estão:

* cadastro;
* consulta;
* atualização;
* organização dos materiais;
* utilização dos materiais nas operações de estoque.

---

## 🔄 Registros operacionais

Área destinada ao acompanhamento dos registros relacionados aos materiais nos pontos, incluindo ocorrências e reposições.

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

# 📋 Módulo de Coleta

A aplicação possui uma área específica denominada **Coleta**, destinada à utilização operacional para cadastro e atualização de informações dos pontos e materiais.

A Coleta possui seu próprio conjunto de templates, mas utiliza a estrutura principal de navegação da aplicação.

### Fluxos principais

### Coleta

```text
/coleta
```

Página inicial do módulo de Coleta.

### Novo registro

```text
/coleta/novo
```

Permite realizar o cadastro de informações relacionadas ao estoque.

### Atualização

```text
/coleta/atualizar
```

Permite localizar um ponto de estoque para atualização.

### Atualização de um ponto específico

```text
/coleta/atualizar/<ponto_id>
```

Permite realizar a atualização das informações de um ponto de estoque específico.

### Resultado da operação

Após determinadas operações, o sistema apresenta uma página de sucesso/resultado da coleta.

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
├── Movimentações
│
├── Usuários
│
├── Territórios
│
├── Municípios
│
└── Coleta
    ├── Início
    ├── Novo
    ├── Atualização
    ├── Atualização por ponto
    └── Sucesso
```

A camada visual utiliza templates Jinja2 com herança de templates.

A estrutura principal segue o conceito:

```text
base.html
    │
    └── coleta_public/base.html
            │
            ├── index.html
            ├── novo.html
            ├── atualizar.html
            ├── atualizar_busca.html
            └── sucesso.html
```

Dessa forma, o menu lateral e a navegação principal permanecem centralizados no layout principal da aplicação.

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
│   │   └── coleta_public/
│   │       ├── base.html
│   │       ├── index.html
│   │       ├── novo.html
│   │       ├── atualizar.html
│   │       ├── atualizar_busca.html
│   │       └── sucesso.html
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
* estoque;
* movimentações;
* coleta;
* permissões;
* regras de atualização de estoque.

---

# 🕐 Operações programadas

Operações que precisam ser executadas diariamente ou em horários específicos devem ser realizadas por mecanismos externos ao processo principal do Flask, como:

* Cron no Linux;
* Agendador de Tarefas do Windows;
* serviços de agendamento do ambiente de produção.

Isso evita manter processos contínuos dentro das requisições da aplicação web.

---

# 📱 Responsividade

A interface utiliza Bootstrap e foi estruturada para funcionar em:

* computadores;
* notebooks;
* tablets;
* smartphones.

A área de Coleta possui atenção especial ao uso em dispositivos móveis, considerando que sua finalidade inclui operações realizadas diretamente nos pontos de estoque.

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

A área de Coleta pode utilizar a API de geolocalização disponível no navegador para obter a localização do usuário durante uma operação.

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
* refinamento do fluxo de edição de estoque;
* histórico detalhado de movimentações;
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
