# 🎨 Interface Flet - Vorcaro

Nova interface moderna do Assistente Financeiro Vorcaro, construída com **Flet** (Flutter para Python).

## ✨ Características

- 🎯 **Dashboard** - Resumo de receitas, despesas, saldo e categorias
- 🤖 **Assistente** - Chat interativo com IA (Gemini, OpenRouter, Ollama)
- 💰 **Transações** - CRUD completo com filtros e paginação
- 📤 **Importação** - Suporta PDF, CSV, Excel, OFX
- ⚙️ **Configurações** - Gerenciamento de API e dados
- 📱 **Responsiva** - Adapta a layouts (mobile/desktop)
- 🌙 **Dark Mode** - Interface moderna e escura

## 🚀 Quick Start

### 1. Verificar Ambiente
```bash
cd assistente_financeiro
python deploy_check.py
```

### 2. Instalar Dependências
```bash
pip install -r requirements-flet.txt
```

### 3. Configurar API
A app espera uma API rodando em: `http://127.0.0.1:8000`

Em outro terminal, inicie a API:
```bash
python run_api.py
```

### 4. Rodar Interface Flet
```bash
python run_flet.py
```

A interface abre automaticamente no navegador padrão (ou em modo desktop se disponível).

## 📁 Estrutura

```
interface_flet/
├── app_flet.py           # App principal com todas as telas
├── __init__.py          # Package init
└── __pycache__/         # Cache Python

run_flet.py              # Launcher da interface
deploy_check.py          # Validador de ambiente
requirements-flet.txt    # Dependências Flet
```

## 🎭 Seções

### Dashboard
- Mostra resumo mensal (receitas/despesas/saldo/transações)
- Lista top 6 categorias com mais gastos
- Botão para atualizar dados

### Assistente
- Chat com Vorcaro (sua IA financeira)
- Mensagens formatadas (user = azul, bot = cinza)
- Status de qual provedor respondeu

### Transações
- Lista paginada (20 por página)
- Filtros: tipo (D/C), mês, ano, busca por descrição
- CRUD: criar, deletar transações
- Validação em tempo real

### Importador
- Dropdown para selecionar tipo (PDF Bancário/Fatura, CSV, Excel, OFX)
- Seletor de arquivo
- Campos opcionais: Conta e Cartão (muda conforme tipo)
- Resultado JSON da importação

### Configurações
- URL da API
- Exportar backup (em desenvolvimento)  
- Limpar cache local
- Dados sobre a app

## 🔧 API Esperada

A interface se conecta com estes endpoints:

```
GET  /dashboard/{mes}/{ano}         → Resumo do mês
POST /assistente/                   → Chat com IA
GET  /transacoes/                   → Listar (filtros: mes, ano, tipo, busca, limite, offset)
POST /transacoes/                   → Criar transação
DELETE /transacoes/{id}             → Deletar transação
GET  /categorias/                   → Listar categorias
GET  /contas/                       → Listar contas
GET  /cartoes/                      → Listar cartões
POST /importar/pdf                  → Upload PDF (tipo_extrato: bancario|fatura, conta_id?, cartao_id?)
POST /importar/csv                  → Upload CSV
POST /importar/excel                → Upload Excel
POST /importar/ofx                  → Upload OFX
```

## 🎨 Paleta de Cores

```
Primária:        #14B8A6  (Teal)
Secundária:      #1C2A43  (Azul escuro)
Fundo:           #090F1D  (Quase preto)
Card:            #0E172E  (Azul muito escuro)
Sucesso:         #22C55E  (Verde)
Perigo:          #F87171  (Vermelho)
Aviso:           #FBBF24  (Amarelo)
Texto:           #E6EDF7  (Branco suave)
Texto Suave:     #9FB3C8  (Cinza azulado)
```

## 🔄 Sincronização

- Cache local de categorias, contas e cartões
- Atualiza automaticamente ao navegar
- Paginação de transações (20 itens por página)
- Refresh manual via botão no header

## 📱 Responsividade

Layout compacto (< 1180px):
- Sidebar encolhe para ícones apenas
- Cards ajustam largura
- Mantém funcionalidade completa

## 🛠️ Desenvolvimento

### Adicionar Nova Seção
1. Criar método `_sua_view()` na classe `VorcaroFletApp`
2. Adicionar ao `_current_view()`
3. Adicionar ícone no NavigationRail

### Melhorar Styling
Cores estão definidas como constantes no topo do arquivo.

### Adicionar API Calls
Extend a classe `ApiClient` com novos métodos.

## 📝 Notas

- Status messages mostram estado das operações
- Erros em vermelho (#F87171)
- Sucesso em teal (#6FE6D9)
- Validação de inputs antes de enviar
- Scroll automático em listas

## 🐛 Troubleshooting

**Erro: ModuleNotFoundError: No module named 'flet'**
```bash
pip install flet==0.83.0
```

**Erro: Conexão recusada para API**
```bash
# Certifique que a API está rodando
python run_api.py
```

**Interface lenta?**
- Aumentar `transacoes_limite` em app_flet.py
- Verificar conexão com o servidor

## 📌 Roadmap

- [ ] Autenticação com múltiplos usuários
- [ ] Sincronização em nuvem
- [ ] Relatórios avançados
- [ ] Previsões/Projeções
- [ ] Integração com agregadores (Nubank, C6, etc)
- [ ] Build para iOS/Android

---

**Maintainer:** Vorcaro Finance Team | v2.0 | 2026
