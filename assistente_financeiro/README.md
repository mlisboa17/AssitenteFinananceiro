# 💰 Assistente Financeiro Pessoal Inteligente

> Sistema completo de gestão financeira pessoal com leitura de extratos bancários brasileiros, classificação automática de despesas, metas, orçamentos, relatórios e interface gráfica leve para PC.

---

## 🚀 Recursos

| Funcionalidade | Descrição |
|---|---|
| **OCR de Extratos PDF** | Lê PDFs digitais e escaneados com Tesseract |
| **Bancos Suportados** | Itaú, Bradesco, Santander, BB, Caixa, Nubank, Inter + genérico |
| **Importação Multi-formato** | PDF, CSV, Excel (.xlsx), OFX/QFX |
| **Classificação Automática** | 200+ palavras-chave em 13 categorias |
| **Detecção de Parcelas** | Identifica compras parceladas automaticamente |
| **Metas Financeiras** | Crie e acompanhe objetivos de economia |
| **Orçamentos Mensais** | Defina limites por categoria com alertas |
| **Insights Inteligentes** | Detecta aumentos, anomalias e oportunidades |
| **Histórico & Tendências** | Compare meses e analise evolução dos gastos |
| **Relatórios** | Exporte para CSV, Excel formatado e PDF |
| **API REST** | Swagger completo em http://localhost:8000/docs |
| **Interface Gráfica** | UI moderna e leve com CustomTkinter |
| **Telegram** | Integração preparada (adicione o token para ativar) |
| **Transcrição de Voz** | Whisper/OpenAI preparado (adicione a chave) |

---

## 📁 Estrutura do Projeto

```
assistente_financeiro/
│
├── app/                          # Backend principal
│   ├── __init__.py
│   ├── main.py                   # API FastAPI (35+ endpoints)
│   ├── database.py               # SQLAlchemy + SQLite/PostgreSQL
│   ├── models.py                 # Modelos ORM (7 tabelas)
│   ├── schemas.py                # Schemas Pydantic
│   │
│   ├── services/                 # Camada de negócio
│   │   ├── ocr_service.py        # Extração de texto de PDFs
│   │   ├── parser_service.py     # Parser de extratos bancários
│   │   ├── classifier_service.py # Classificação por palavras-chave
│   │   ├── insights_service.py   # Insights e alertas financeiros
│   │   ├── metas_service.py      # Metas e orçamentos
│   │   ├── import_service.py     # Importação (PDF/CSV/Excel/OFX)
│   │   ├── export_service.py     # Exportação (CSV/Excel/PDF)
│   │   ├── historico_service.py  # Histórico e tendências
│   │   └── notificacoes/
│   │       ├── telegram_service.py  # Bot Telegram (preparado)
│   │       └── voice_processor.py   # Voz via Whisper (preparado)
│   │
│   └── utils/
│       ├── regex_patterns.py     # Padrões para extratos BR
│       └── helpers.py            # Funções auxiliares
│
├── interface/                    # Interface Gráfica PC
│   └── app_gui.py                # CustomTkinter UI
│
├── uploads/                      # Arquivos enviados
│
├── run_api.py                    # Inicia servidor FastAPI
├── run_gui.py                    # Inicia interface gráfica
├── requirements.txt              # Dependências Python
├── .env.example                  # Variáveis de ambiente
└── README.md
```

---

## ⚙️ Instalação

### 1. Pré-requisitos

- **Python 3.10+**
- **Tesseract OCR** (para leitura de PDFs escaneados):
  - Windows: Baixe em https://github.com/UB-Mannheim/tesseract/wiki
  - Instale em `C:\Program Files\Tesseract-OCR\`
  - Adicione ao PATH do sistema

### 2. Clone e configure o ambiente

```bash
# Crie um ambiente virtual
python -m venv venv

# Ative o ambiente (Windows)
venv\Scripts\activate

# Ative o ambiente (Linux/Mac)
source venv/bin/activate

# Instale as dependências
pip install -r requirements.txt
```

### 3. Configure as variáveis de ambiente

```bash
# Copie o arquivo de exemplo
copy .env.example .env

# Edite o .env com seus dados (opcional para uso básico)
notepad .env
```

---

## ▶️ Como Usar

### Interface Gráfica (recomendada)

```bash
python run_gui.py
```

A interface abre com 8 seções na barra lateral:

| Seção | O que faz |
|---|---|
| 🏠 **Dashboard** | Resumo do mês com gráficos de pizza e barras |
| 💳 **Transações** | Lista, filtra e gerencia todas as transações |
| 📤 **Importar** | Importa extratos em PDF, CSV, Excel ou OFX |
| 🎯 **Metas** | Cria e acompanha objetivos financeiros |
| 💸 **Orçamentos** | Define limites mensais por categoria |
| 📊 **Relatórios** | Exporta dados para CSV, Excel ou PDF |
| 🤖 **Assistente** | Faz perguntas em linguagem natural |
| ⚙️ **Configurações** | Tema, banco de dados, integrações |

### API REST

```bash
python run_api.py
```

Acesse a documentação em: **http://localhost:8000/docs**

Principais rotas:

```
POST   /transacoes/              Criar transação manualmente
GET    /transacoes/              Listar transações (com filtros)
POST   /importar/pdf             Importar extrato PDF
POST   /importar/csv             Importar extrato CSV
POST   /importar/excel           Importar planilha Excel
POST   /importar/ofx             Importar arquivo OFX
GET    /dashboard/{mes}/{ano}    Resumo do dashboard
GET    /insights/{mes}/{ano}     Insights financeiros
GET    /exportar/csv             Exportar CSV
GET    /exportar/excel           Exportar Excel
GET    /exportar/pdf             Exportar PDF
POST   /metas/                   Criar meta financeira
GET    /metas/                   Listar metas
POST   /orcamentos/              Criar orçamento
POST   /assistente/              Perguntar ao assistente
```

---

## 📲 Como Importar um Extrato

### Via Interface Gráfica
1. Clique em **📤 Importar** na sidebar
2. Escolha o formato (PDF, CSV, Excel, OFX)
3. Selecione o arquivo do seu banco
4. Aguarde a importação

### Formatos suportados

| Formato | Como obter no banco |
|---|---|
| **PDF** | Baixe o extrato/fatura como PDF no app ou site do banco |
| **CSV** | Itaú, Bradesco e outros oferecem exportação CSV |
| **Excel** | Importação de planilhas personalizadas |
| **OFX** | Disponível no BB, Bradesco e outros com padrão OFX |

---

## 🤖 Assistente Conversacional

Perguntas que você pode fazer:

```
"Quanto gastei com Alimentação este mês?"
"Qual foi minha maior despesa?"
"Estou gastando mais que no mês passado?"
"Qual o total de gastos em Transporte?"
"Tenho metas vencendo?"
```

---

## 📱 Integração Telegram (Opcional)

1. Crie um bot com @BotFather: `/newbot`
2. Copie o token gerado
3. Adicione no `.env`:
   ```
   TELEGRAM_BOT_TOKEN=seu_token_aqui
   TELEGRAM_CHAT_ID=seu_chat_id
   ```
4. Reinicie a aplicação

**Comandos via Telegram:**
```
gastei 50 mercado
registrar despesa 120 farmácia
gasto 35 uber
```

### 💬 Conversa humana com contexto (sem custos)

Para o bot conversar como humano e lembrar do contexto da conversa, use IA local com **Ollama** (open-source):

GitHub oficial: https://github.com/ollama/ollama

1. Instale o Ollama
2. Baixe um modelo leve (exemplo recomendado):
   ```bash
   ollama pull qwen2.5:3b
   ```
3. No arquivo `.env`, adicione:
   ```env
   TELEGRAM_AI_ENABLED=true
   OLLAMA_BASE_URL=http://127.0.0.1:11434
   OLLAMA_MODEL=qwen2.5:3b
   OLLAMA_TIMEOUT_SECONDS=45
   TELEGRAM_AI_MAX_CONTEXT=12
   ```
4. Reinicie a API (`python run_api.py`)

Depois disso, mensagens que não forem comando de despesa passam a ser respondidas de forma conversacional com contexto.
Para reiniciar o histórico da conversa em um chat, envie: `limpar contexto`

---

## 🗣️ Transcrição de Voz (Opcional)

1. Crie uma conta em https://platform.openai.com
2. Gere uma API key
3. Adicione no `.env`:
   ```
   OPENAI_API_KEY=sk-sua_chave_aqui
   ```

---

## 🗄️ Banco de Dados

Por padrão usa **SQLite** (zero configuração). Para PostgreSQL em produção:

```env
DATABASE_URL=postgresql://usuario:senha@localhost:5432/assistente_financeiro
```

---

## 📊 Categorias Automáticas

O sistema classifica automaticamente em 13 categorias:

| Categoria | Exemplos |
|---|---|
| Alimentação | Mercado, Supermercado, Padaria |
| Restaurante | iFood, McDonald's, Lanchonete |
| Transporte | Uber, Gasolina, Estacionamento |
| Saúde | Farmácia, Médico, Hospital |
| Educação | Faculdade, Cursos, Udemy |
| Lazer | Netflix, Cinema, Spotify |
| Vestuário | Renner, C&A, Zara |
| Casa | Aluguel, Energia, Água, Gás |
| Telecomunicações | Tim, Vivo, Internet |
| Investimento | Tesouro Direto, CDB, Ações |
| Serviços | Seguro, Salão, Lavanderia |
| Pets | Petshop, Veterinário, Ração |
| Outros | Demais transações |

---

## 🛠️ Tecnologias

| Tecnologia | Uso |
|---|---|
| **Python 3.10+** | Linguagem principal |
| **FastAPI** | API REST com docs automáticas |
| **SQLAlchemy** | ORM para banco de dados |
| **SQLite** | Banco de dados padrão (zero config) |
| **Pydantic** | Validação de dados |
| **pytesseract** | OCR de PDFs escaneados |
| **pandas** | Análise de dados e importação |
| **CustomTkinter** | Interface gráfica moderna |
| **matplotlib** | Gráficos e charts |
| **reportlab** | Geração de PDFs |
| **ofxparse** | Leitura de arquivos OFX |

---

## 📝 Licença

MIT License — use livremente para fins pessoais e educacionais.
