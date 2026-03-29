import datetime as dt
import asyncio
import json
import os
import random
from typing import Any, Dict, List, Optional

import flet as ft
import requests
from dotenv import load_dotenv


load_dotenv()

_MEMES_FINANCEIROS = [
    "Abrir o app do banco no fim do mes e perguntar quem sabotou a minha vida financeira.",
    "Receber salario de manha e a noite ele ja estar em modo lenda urbana.",
    "Prometer economia na segunda e pedir delivery premium na sexta.",
    "Entrar no mercado para comprar pao e voltar com um rombo existencial.",
    "Falar 'foi so um cafezinho' 17 vezes no mesmo mes.",
    "Conferir o saldo com a mesma coragem de quem abre resultado de prova.",
    "Fazer planilha de gastos e usar ela como ficcao cientifica.",
    "Ver cashback de 2 reais e gastar 200 para nao perder a oportunidade.",
    "Fazer meta de guardar dinheiro e tratar como sugestao artistica.",
    "Dizer que vai cortar gastos e assinar mais um streaming por pesquisa academica.",
    "Passar no shopping para resolver uma coisa e sair com tres parcelas e zero respostas.",
    "Jurar que o cartao esta sob controle enquanto ele monta carreira solo.",
    "Transformar cupom de desconto em justificativa oficial para comprar o que nao precisava.",
    "Abrir a fatura e sentir que fui convidado para uma aventura que nao lembro de aceitar.",
    "Falar 'agora vai' para a planilha pela quarta semana consecutiva.",
    "Quando o saldo entra no chat so para avisar que foi embora.",
    "Meu metodo financeiro e simples: otimismo, cafe e renegociacao.",
    "A economia do mes foi tao boa que ja estou pensando em como gastar ela inteira.",
]

_PIADAS_FINANCEIRAS = [
    "Qual o esporte oficial da vida adulta? Corrida contra o vencimento da fatura.",
    "Meu saldo e tao discreto que quando aparece ja pede desculpa pelo incomodo.",
    "A carteira nao esta vazia. Esta praticando minimalismo financeiro.",
    "Nao estou gastando demais, estou movimentando a economia local com entusiasmo.",
    "Meu planejamento financeiro e tipo serie longa: muita promessa e varios plot twists.",
    "O dinheiro nao traz felicidade, mas quando cai na conta eu sorrio por reflexo.",
    "Sou organizado: cada boleto tem sua categoria de susto.",
    "Meu extrato bancario virou podcast de suspense em episodios diarios.",
    "Economizei tanto hoje que ate abrir o app do banco foi em modo aviao.",
    "Nao e impulsividade, e decisao rapida com consequencias demoradas.",
]

_SARCASMO_ABERTURA = [
    "Comentario sarcastico do sistema:",
    "Analise tecnica do caos:",
    "Parecer financeiro premium:",
]

_SARCASMO_MEIO = [
    "sua estrategia esta no modo 'emocao acima de orcamento'",
    "o cartao esta trabalhando em turno extra",
    "o planejamento foi aprovado, a execucao nao compareceu",
    "a meta de economia entrou em home office permanente",
]

_SARCASMO_FIM = [
    "mas segue firme que amanha a planilha te perdoa.",
    "com sorte o futuro eu paga esse presente eu.",
    "pelo menos ta rendendo historia boa.",
    "respira fundo e finge que foi investimento em felicidade.",
]


def _api_base_url() -> str:
    raw = os.getenv("FLET_API_BASE_URL", "").strip()
    if raw:
        return raw.rstrip("/")

    assistente_url = os.getenv("ASSISTENTE_API_URL", "http://127.0.0.1:8000/assistente/").strip()
    if "/assistente" in assistente_url:
        assistente_url = assistente_url.split("/assistente", 1)[0]
    return assistente_url.rstrip("/")


class ApiClient:
    def __init__(self) -> None:
        self.base = _api_base_url()
        self.timeout = 25

    def resumo_dashboard(self, mes: int, ano: int) -> Dict[str, Any]:
        url = f"{self.base}/dashboard/{mes}/{ano}"
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def enviar_pergunta(self, pergunta: str) -> Dict[str, Any]:
        url = f"{self.base}/assistente/"
        response = requests.post(url, json={"pergunta": pergunta}, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def listar_categorias(self) -> List[Dict[str, Any]]:
        url = f"{self.base}/categorias/"
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def listar_transacoes(self, *, mes: Optional[int], ano: Optional[int], tipo: Optional[str], busca: str, limite: int, offset: int) -> List[Dict[str, Any]]:
        url = f"{self.base}/transacoes/"
        params: Dict[str, Any] = {"limite": limite, "offset": offset}
        if mes:
            params["mes"] = mes
        if ano:
            params["ano"] = ano
        if tipo:
            params["tipo"] = tipo
        if busca.strip():
            params["busca"] = busca.strip()
        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def criar_transacao(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base}/transacoes/"
        response = requests.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def excluir_transacao(self, transacao_id: int) -> Dict[str, Any]:
        url = f"{self.base}/transacoes/{transacao_id}"
        response = requests.delete(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def listar_contas(self) -> List[Dict[str, Any]]:
        url = f"{self.base}/contas/"
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def listar_cartoes(self) -> List[Dict[str, Any]]:
        url = f"{self.base}/cartoes/"
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def importar_arquivo(self, *, caminho_arquivo: str, tipo_importacao: str, conta_id: Optional[int], cartao_id: Optional[int]) -> Dict[str, Any]:
        mapa_endpoint = {
            "pdf_bancario": ("/importar/pdf", {"tipo_extrato": "bancario"}),
            "pdf_fatura": ("/importar/pdf", {"tipo_extrato": "fatura"}),
            "csv": ("/importar/csv", {}),
            "excel": ("/importar/excel", {}),
            "ofx": ("/importar/ofx", {}),
        }
        endpoint, dados = mapa_endpoint[tipo_importacao]
        if conta_id:
            dados["conta_id"] = str(conta_id)
        if cartao_id:
            dados["cartao_id"] = str(cartao_id)

        with open(caminho_arquivo, "rb") as fp:
            files = {"arquivo": (os.path.basename(caminho_arquivo), fp)}
            response = requests.post(f"{self.base}{endpoint}", data=dados, files=files, timeout=120)
            response.raise_for_status()
            return response.json()

    def obter_pontuacao_planner(self) -> Dict[str, Any]:
        url = f"{self.base}/planner/pontuacao/"
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def obter_timeline_planner(self, data_ref: str) -> Dict[str, Any]:
        url = f"{self.base}/planner/timeline/{data_ref}"
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def obter_smartplanner(self, data_ref: str) -> Dict[str, Any]:
        url = f"{self.base}/planner/smartplanner/{data_ref}"
        response = requests.get(url, timeout=self.timeout)
        if response.status_code == 404:
            # Compatibilidade: quando smartplanner nao existe no backend,
            # usamos a timeline como fonte de sugestoes.
            return self.obter_timeline_planner(data_ref)
        response.raise_for_status()
        return response.json()

    def obter_kanban_planner(self, data_ref: str) -> Dict[str, Any]:
        url = f"{self.base}/planner/kanban/{data_ref}"
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def organizar_tarefas_planner(self, *, texto: str, data_ref: str) -> Dict[str, Any]:
        url = f"{self.base}/planner/organize/"
        payload = {
            # Formato antigo (app/main.py)
            "texto": texto,
            "data": data_ref,
            "organizacao_id": 1,
            # Formato novo (planner_routes.py)
            "tarefas_texto": texto,
            "data_inicio": data_ref,
            "area": "pessoal",
        }
        response = requests.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def completar_tarefa_planner(self, tarefa_id: int) -> Dict[str, Any]:
        url = f"{self.base}/planner/tarefas/{tarefa_id}/completar"
        response = requests.patch(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def atualizar_tarefa_planner(self, tarefa_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base}/planner/tarefas/{tarefa_id}"
        response = requests.put(url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def excluir_tarefa_planner(self, tarefa_id: int, organizacao_id: int = 1) -> Dict[str, Any]:
        url = f"{self.base}/planner/tarefas/{tarefa_id}"
        response = requests.delete(url, params={"organizacao_id": organizacao_id}, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def diagnostico_ambiente(self) -> Dict[str, Any]:
        url = f"{self.base}/diagnostico/ambiente"
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def obter_agenda_financeira(self, data_ref: str) -> Dict[str, Any]:
        url = f"{self.base}/agenda/financeira/{data_ref}"
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def obter_compromissos(self, data_ref: str) -> Dict[str, Any]:
        url = f"{self.base}/agenda/compromissos/{data_ref}"
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()


def _currency_br(valor: float) -> str:
    txt = f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {txt}"


class VorcaroFletApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.api = ApiClient()
        self._memes_rotacao: List[str] = []
        self._ultimo_meme: Optional[str] = None
        self._piadas_rotacao: List[str] = []
        self._ultima_piada: Optional[str] = None
        self._sarcasmo_chance = max(0.0, min(1.0, float(os.getenv("GUI_MEME_AUTO_CHANCE", "0.45"))))
        self._humor_auto_habilitado = os.getenv("GUI_HUMOR_AUTO_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
        self._humor_auto_chance = max(0.0, min(1.0, float(os.getenv("GUI_HUMOR_AUTO_CHANCE", "0.70"))))
        self._humor_auto_min_s = max(20, int(os.getenv("GUI_HUMOR_AUTO_MIN_SECONDS", "55")))
        self._humor_auto_max_s = max(self._humor_auto_min_s, int(os.getenv("GUI_HUMOR_AUTO_MAX_SECONDS", "130")))
        self._humor_auto_task_iniciada = False

        self._menu_idx = 0
        self._is_compact = False
        self._tema_visual = "oceano"
        self._paletas: Dict[str, Dict[str, str]] = {
            "oceano": {
                "bg": "#0D1117",
                "panel": "#161B22",
                "panel_alt": "#111827",
                "border": "#2B3442",
                "border_alt": "#273244",
                "muted": "#9FB0C3",
                "text": "#E6EEF8",
                "accent": "#0EA5A4",
                "accent_alt": "#0EA5E9",
                "accent_text": "#042F2E",
                "accent_alt_text": "#E6F7FF",
                "ok": "#22C55E",
                "ok_text": "#F0FFF4",
                "danger": "#FB7185",
                "warning": "#FBBF24",
                "input_bg": "#0F172A",
                "input_border": "#23324A",
                "menu_grad_a": "#0F172A",
                "menu_grad_b": "#111827",
            },
            "claro": {
                "bg": "#F3F5F7",
                "panel": "#FFFFFF",
                "panel_alt": "#F8FAFC",
                "border": "#D9E0E8",
                "border_alt": "#CBD5E1",
                "muted": "#64748B",
                "text": "#0F172A",
                "accent": "#0F766E",
                "accent_alt": "#0369A1",
                "accent_text": "#ECFEFF",
                "accent_alt_text": "#F8FAFC",
                "ok": "#15803D",
                "ok_text": "#F0FFF4",
                "danger": "#BE123C",
                "warning": "#B45309",
                "input_bg": "#FFFFFF",
                "input_border": "#CBD5E1",
                "menu_grad_a": "#F8FAFC",
                "menu_grad_b": "#EEF2F7",
            },
            "contraste": {
                "bg": "#050505",
                "panel": "#0D0D0D",
                "panel_alt": "#111111",
                "border": "#3A3A3A",
                "border_alt": "#4A4A4A",
                "muted": "#D1D5DB",
                "text": "#FAFAFA",
                "accent": "#F59E0B",
                "accent_alt": "#38BDF8",
                "accent_text": "#111111",
                "accent_alt_text": "#04131C",
                "ok": "#22C55E",
                "ok_text": "#F0FFF4",
                "danger": "#FB7185",
                "warning": "#FACC15",
                "input_bg": "#121212",
                "input_border": "#4A4A4A",
                "menu_grad_a": "#0B0B0B",
                "menu_grad_b": "#111111",
            },
            "aurora": {
                "bg": "#08121A",
                "panel": "#10202B",
                "panel_alt": "#0C1922",
                "border": "#274152",
                "border_alt": "#2D4E61",
                "muted": "#9BC3CC",
                "text": "#E9F7F8",
                "accent": "#14B8A6",
                "accent_alt": "#7C3AED",
                "accent_text": "#06231F",
                "accent_alt_text": "#F3EEFF",
                "ok": "#22C55E",
                "ok_text": "#F0FFF4",
                "danger": "#F43F5E",
                "warning": "#F59E0B",
                "input_bg": "#0C1A24",
                "input_border": "#2B4A5C",
                "menu_grad_a": "#0A1822",
                "menu_grad_b": "#0F2230",
            },
            "sunset": {
                "bg": "#1A0F0A",
                "panel": "#2A1711",
                "panel_alt": "#22130F",
                "border": "#4E2D22",
                "border_alt": "#5A362A",
                "muted": "#D2B4A6",
                "text": "#FFF1EA",
                "accent": "#F97316",
                "accent_alt": "#EF4444",
                "accent_text": "#2A1207",
                "accent_alt_text": "#FFF1F2",
                "ok": "#84CC16",
                "ok_text": "#F7FEE7",
                "danger": "#FB7185",
                "warning": "#F59E0B",
                "input_bg": "#241611",
                "input_border": "#5A362A",
                "menu_grad_a": "#1B100C",
                "menu_grad_b": "#2A1711",
            },
            "floresta": {
                "bg": "#0A140F",
                "panel": "#112019",
                "panel_alt": "#0E1A14",
                "border": "#294336",
                "border_alt": "#345643",
                "muted": "#A8C7B5",
                "text": "#ECF7F0",
                "accent": "#22C55E",
                "accent_alt": "#10B981",
                "accent_text": "#072313",
                "accent_alt_text": "#E7FFF5",
                "ok": "#84CC16",
                "ok_text": "#F7FEE7",
                "danger": "#F43F5E",
                "warning": "#EAB308",
                "input_bg": "#0E1A14",
                "input_border": "#355744",
                "menu_grad_a": "#0B1711",
                "menu_grad_b": "#112019",
            },
            "areia": {
                "bg": "#F9F4EB",
                "panel": "#FFFDF8",
                "panel_alt": "#F3EBDD",
                "border": "#E2D3BC",
                "border_alt": "#D9C6AB",
                "muted": "#7A6C56",
                "text": "#2F2518",
                "accent": "#C26D2D",
                "accent_alt": "#5B8C5A",
                "accent_text": "#FFF7EF",
                "accent_alt_text": "#F4FFF2",
                "ok": "#2F855A",
                "ok_text": "#ECFDF5",
                "danger": "#C53030",
                "warning": "#B7791F",
                "input_bg": "#FFFAF0",
                "input_border": "#D9C6AB",
                "menu_grad_a": "#F8EFE2",
                "menu_grad_b": "#F2E6D4",
            },
            "lavanda": {
                "bg": "#F6F3FF",
                "panel": "#FFFFFF",
                "panel_alt": "#EFE9FF",
                "border": "#DDD3FF",
                "border_alt": "#D2C5FF",
                "muted": "#6C638A",
                "text": "#241F3A",
                "accent": "#6D28D9",
                "accent_alt": "#0EA5E9",
                "accent_text": "#F7F0FF",
                "accent_alt_text": "#F0FAFF",
                "ok": "#15803D",
                "ok_text": "#F0FFF4",
                "danger": "#BE123C",
                "warning": "#A16207",
                "input_bg": "#FFFFFF",
                "input_border": "#D2C5FF",
                "menu_grad_a": "#F3EEFF",
                "menu_grad_b": "#ECE5FF",
            },
        }

        # Dashboard controls
        self.lbl_receitas = ft.Text("R$ 0,00", size=22, weight=ft.FontWeight.W_700)
        self.lbl_despesas = ft.Text("R$ 0,00", size=22, weight=ft.FontWeight.W_700)
        self.lbl_saldo = ft.Text("R$ 0,00", size=22, weight=ft.FontWeight.W_700)
        self.lbl_total = ft.Text("0", size=22, weight=ft.FontWeight.W_700)
        self.lbl_ref = ft.Text("Período atual", size=12, color=self._cor("muted"))

        self.categorias_col = ft.Column(spacing=10)
        self.dashboard_status = ft.Text("Carregando dashboard...", size=12, color=self._cor("muted"), max_lines=3, overflow=ft.TextOverflow.ELLIPSIS)
        self.dashboard_diag_status = ft.Text("Ambiente: sem leitura", size=12, color=self._cor("muted"), max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)
        self.dashboard_diag_pendencias = ft.Text("Pendências: --", size=12, color=self._cor("muted"), max_lines=3, overflow=ft.TextOverflow.ELLIPSIS)
        self.dashboard_diag_payload: Dict[str, Any] = {}

        # Assistente controls
        self.chat_list = ft.ListView(expand=True, spacing=8, auto_scroll=True)
        self.inp_pergunta = ft.TextField(
            hint_text="Pergunte algo ao Vorcaro...",
            border_radius=14,
            expand=True,
            bgcolor=self._cor("input_bg"),
            border_color=self._cor("input_border"),
            text_style=ft.TextStyle(color=self._cor("text")),
        )
        self.assistente_status = ft.Text("", size=12, color=self._cor("muted"), max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)

        # Transações controls
        self.transacoes_status = ft.Text("", size=12, color=self._cor("muted"), max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)
        self.transacoes_col = ft.Column(spacing=8)
        self.inp_busca_transacao = ft.TextField(
            hint_text="Buscar por descrição...",
            expand=True,
            border_radius=12,
            bgcolor=self._cor("input_bg"),
            border_color=self._cor("input_border"),
            text_style=ft.TextStyle(color=self._cor("text")),
        )
        self.filtro_tipo = ft.Dropdown(
            width=160,
            value="",
            options=[
                ft.dropdown.Option("", "Todos"),
                ft.dropdown.Option("debito", "Débito"),
                ft.dropdown.Option("credito", "Crédito"),
            ],
            border_radius=10,
            bgcolor=self._cor("input_bg"),
            border_color=self._cor("input_border"),
        )
        self.filtro_mes = ft.Dropdown(
            width=120,
            value=str(dt.date.today().month),
            options=[ft.dropdown.Option("", "Todos")] + [ft.dropdown.Option(str(m), f"{m:02d}") for m in range(1, 13)],
            border_radius=10,
            bgcolor=self._cor("input_bg"),
            border_color=self._cor("input_border"),
        )
        ano_atual = dt.date.today().year
        self.filtro_ano = ft.Dropdown(
            width=140,
            value=str(ano_atual),
            options=[ft.dropdown.Option("", "Todos")] + [ft.dropdown.Option(str(y), str(y)) for y in range(ano_atual - 4, ano_atual + 2)],
            border_radius=10,
            bgcolor=self._cor("input_bg"),
            border_color=self._cor("input_border"),
        )

        self.transacoes_limite = 20
        self.transacoes_offset = 0
        self.transacoes_ultimo_count = 0
        self.categorias_cache: List[Dict[str, Any]] = []
        self.categoria_por_nome: Dict[str, int] = {}

        # Importação controls
        self.importar_status = ft.Text("Selecione um arquivo para importar.", size=12, color=self._cor("muted"), max_lines=3, overflow=ft.TextOverflow.ELLIPSIS)
        self.importar_resultado = ft.Text("", size=12, selectable=True)
        self.importar_tipo = ft.Dropdown(
            width=220,
            value="pdf_bancario",
            options=[
                ft.dropdown.Option("pdf_bancario", "PDF - Extrato Bancário"),
                ft.dropdown.Option("pdf_fatura", "PDF - Fatura Cartão"),
                ft.dropdown.Option("csv", "CSV"),
                ft.dropdown.Option("excel", "Excel (.xlsx)"),
                ft.dropdown.Option("ofx", "OFX"),
            ],
            border_radius=10,
            bgcolor=self._cor("input_bg"),
            border_color=self._cor("input_border"),
        )
        self.importar_tipo.on_change = lambda _e: self._atualizar_campos_importacao()
        self.importar_conta = ft.Dropdown(
            width=260,
            options=[ft.dropdown.Option("", "Conta (opcional)")],
            value="",
            bgcolor=self._cor("input_bg"),
            border_color=self._cor("input_border"),
        )
        self.importar_cartao = ft.Dropdown(
            width=260,
            options=[ft.dropdown.Option("", "Cartão (opcional)")],
            value="",
            bgcolor=self._cor("input_bg"),
            border_color=self._cor("input_border"),
        )
        self.contas_cache: List[Dict[str, Any]] = []
        self.cartoes_cache: List[Dict[str, Any]] = []

        # Planner controls
        self.planner_status = ft.Text("Use o Planner para organizar seu dia.", size=12, color=self._cor("muted"), max_lines=3, overflow=ft.TextOverflow.ELLIPSIS)
        self.planner_data = ft.TextField(
            label="Data (AAAA-MM-DD)",
            value=str(dt.date.today()),
            width=180,
            border_radius=10,
            bgcolor=self._cor("input_bg"),
            border_color=self._cor("input_border"),
            text_style=ft.TextStyle(color=self._cor("text")),
        )
        self.planner_texto_livre = ft.TextField(
            hint_text="Ex: Academia 08:00-09:30, reunião 14h, estudar Python 2h",
            multiline=True,
            min_lines=2,
            max_lines=4,
            border_radius=12,
            bgcolor=self._cor("input_bg"),
            border_color=self._cor("input_border"),
            text_style=ft.TextStyle(color=self._cor("text")),
        )
        self.lbl_planner_pontos = ft.Text("0", size=24, weight=ft.FontWeight.W_700)
        self.lbl_planner_nivel = ft.Text("Nível 1", size=24, weight=ft.FontWeight.W_700)
        self.lbl_planner_xp = ft.Text("0 XP", size=22, weight=ft.FontWeight.W_700)
        self.lbl_planner_badges = ft.Text("0", size=22, weight=ft.FontWeight.W_700)

        self.planner_timeline_col = ft.Column(spacing=8)
        self.planner_smart_col = ft.Column(spacing=8)
        self.planner_kanban_todo_col = ft.Column(spacing=8)
        self.planner_kanban_doing_col = ft.Column(spacing=8)
        self.planner_kanban_done_col = ft.Column(spacing=8)
        self.planner_badges_col = ft.Column(spacing=6)
        self.planner_agenda_financeira_col = ft.Column(spacing=8)
        self.planner_compromissos_col = ft.Column(spacing=8)

        self._configurar_pagina()
        self._montar_layout()
        self._carregar_dashboard()
        self._iniciar_humor_automatico()

    def _menu_items(self) -> List[Dict[str, Any]]:
        return [
            {"label": "Dashboard", "icon": ft.Icons.DASHBOARD_OUTLINED, "active_icon": ft.Icons.DASHBOARD},
            {"label": "Assistente", "icon": ft.Icons.SMART_TOY_OUTLINED, "active_icon": ft.Icons.SMART_TOY},
            {"label": "Transações", "icon": ft.Icons.RECEIPT_LONG_OUTLINED, "active_icon": ft.Icons.RECEIPT_LONG},
            {"label": "Importar", "icon": ft.Icons.UPLOAD_FILE_OUTLINED, "active_icon": ft.Icons.UPLOAD_FILE},
            {"label": "Planner", "icon": ft.Icons.VIEW_TIMELINE_OUTLINED, "active_icon": ft.Icons.VIEW_TIMELINE},
            {"label": "Configurações", "icon": ft.Icons.SETTINGS_OUTLINED, "active_icon": ft.Icons.SETTINGS},
        ]

    def _cor(self, chave: str) -> str:
        return self._paletas[self._tema_visual][chave]

    def _mensagem_erro_api(self, exc: Exception, contexto: str) -> str:
        msg = str(exc)
        sinais_offline = [
            "Max retries exceeded",
            "Failed to establish a new connection",
            "Connection refused",
            "WinError 10061",
            "ConnectionError",
        ]
        if any(s in msg for s in sinais_offline):
            return (
                f"{contexto}: API offline em {self.api.base}. "
                "Inicie o backend com: .venv/Scripts/python assistente_financeiro/run_api.py"
            )
        return f"{contexto}: {msg}"

    def _button_primary(self) -> ft.ButtonStyle:
        return ft.ButtonStyle(bgcolor=self._cor("accent"), color=self._cor("accent_text"))

    def _button_secondary(self) -> ft.ButtonStyle:
        return ft.ButtonStyle(bgcolor=self._cor("accent_alt"), color=self._cor("accent_alt_text"))

    def _button_success(self) -> ft.ButtonStyle:
        return ft.ButtonStyle(bgcolor=self._cor("ok"), color=self._cor("ok_text"))

    def _sincronizar_cores_controles(self) -> None:
        input_bg = self._cor("input_bg")
        input_border = self._cor("input_border")
        text_color = self._cor("text")
        muted = self._cor("muted")

        textfields = [
            self.inp_pergunta,
            self.inp_busca_transacao,
            self.planner_data,
            self.planner_texto_livre,
        ]
        for ctrl in textfields:
            ctrl.bgcolor = input_bg
            ctrl.border_color = input_border
            ctrl.text_style = ft.TextStyle(color=text_color)

        dropdowns = [
            self.filtro_tipo,
            self.filtro_mes,
            self.filtro_ano,
            self.importar_tipo,
            self.importar_conta,
            self.importar_cartao,
        ]
        for ctrl in dropdowns:
            ctrl.bgcolor = input_bg
            ctrl.border_color = input_border

        self.lbl_ref.color = muted
        self.dashboard_status.color = muted
        self.assistente_status.color = muted
        self.transacoes_status.color = muted
        self.importar_status.color = muted
        self.planner_status.color = muted
        self.dashboard_diag_status.color = muted
        self.dashboard_diag_pendencias.color = muted
        self.lbl_receitas.color = text_color
        self.lbl_despesas.color = text_color
        self.lbl_total.color = text_color
        self.lbl_planner_pontos.color = text_color
        self.lbl_planner_nivel.color = text_color
        self.lbl_planner_xp.color = text_color
        self.lbl_planner_badges.color = text_color

    def _aplicar_tema_visual(self, tema: str, *, rerender: bool = True) -> None:
        if tema not in self._paletas:
            tema = "oceano"
        self._tema_visual = tema

        temas_claros = {"claro", "areia", "lavanda"}
        self.page.theme_mode = ft.ThemeMode.LIGHT if tema in temas_claros else ft.ThemeMode.DARK
        self.page.bgcolor = self._cor("bg")
        self.page.theme = ft.Theme(
            color_scheme_seed=self._cor("accent"),
            font_family="Segoe UI",
            visual_density=ft.VisualDensity.COMFORTABLE,
        )
        self._sincronizar_cores_controles()

        if rerender and hasattr(self, "content_area"):
            self._render_content()

    def _configurar_pagina(self) -> None:
        self.page.title = "Vorcaro | Nova Interface Flet"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 0
        self.page.window_min_width = 860
        self.page.window_min_height = 620
        self.page.window_maximized = True
        self._aplicar_tema_visual(self._tema_visual, rerender=False)

        self.page.on_resize = self._on_resize

    def _on_resize(self, _e: ft.ControlEvent) -> None:
        was_compact = self._is_compact
        self._is_compact = self.page.width < 1360
        if was_compact != self._is_compact:
            self._render_content()

    def _menu_change(self, e: ft.ControlEvent) -> None:
        self._menu_idx = int(e.control.selected_index)
        if self._menu_idx == 2:
            self._carregar_transacoes(reset=True)
        if self._menu_idx == 3:
            self._carregar_fontes_importacao()
        if self._menu_idx == 4:
            self._carregar_planner()
        self._render_content()

    def _ir_para_menu(self, idx: int) -> None:
        self._menu_idx = idx
        if self._menu_idx == 2:
            self._carregar_transacoes(reset=True)
        if self._menu_idx == 3:
            self._carregar_fontes_importacao()
        if self._menu_idx == 4:
            self._carregar_planner()
        self._render_content()

    def _menu(self) -> ft.Control:
        menu_items: List[ft.Control] = []
        for idx, item in enumerate(self._menu_items()):
            ativo = idx == self._menu_idx
            icon = item["active_icon"] if ativo else item["icon"]
            if self._is_compact:
                menu_items.append(
                    ft.Container(
                        margin=ft.margin.symmetric(horizontal=8, vertical=4),
                        border_radius=12,
                        bgcolor=self._cor("accent") if ativo else ft.Colors.TRANSPARENT,
                        content=ft.IconButton(
                            icon=icon,
                            icon_color=self._cor("accent_text") if ativo else self._cor("muted"),
                            tooltip=str(item["label"]),
                            on_click=lambda _e, i=idx: self._ir_para_menu(i),
                        ),
                    )
                )
            else:
                menu_items.append(
                    ft.Container(
                        margin=ft.margin.symmetric(horizontal=10, vertical=3),
                        border_radius=12,
                        bgcolor=self._cor("accent") if ativo else ft.Colors.TRANSPARENT,
                        content=ft.ListTile(
                            dense=True,
                            leading=ft.Icon(icon, color=self._cor("accent_text") if ativo else self._cor("muted")),
                            title=ft.Text(
                                str(item["label"]),
                                color=self._cor("accent_text") if ativo else self._cor("text"),
                                weight=ft.FontWeight.W_600 if ativo else ft.FontWeight.W_400,
                            ),
                            on_click=lambda _e, i=idx: self._ir_para_menu(i),
                        ),
                    )
                )

        logo = ft.Container(
            padding=ft.padding.only(left=16, right=16, top=20, bottom=8),
            content=ft.Column(
                spacing=2,
                controls=[
                    ft.Text("VORCARO", size=20, weight=ft.FontWeight.W_700, color=self._cor("text")),
                    ft.Text("Finance | Flet UI", size=11, color=self._cor("accent")),
                ],
            ),
        )

        return ft.Container(
            width=86 if self._is_compact else 250,
            gradient=ft.LinearGradient([self._cor("menu_grad_a"), self._cor("menu_grad_b")]),
            border=ft.border.only(right=ft.BorderSide(1, self._cor("border_alt"))),
            content=ft.Column(
                expand=True,
                spacing=0,
                controls=[
                    logo,
                    ft.Divider(height=1, color=self._cor("border_alt")),
                    ft.Container(
                        expand=True,
                        content=ft.Column(
                            expand=True,
                            scroll=ft.ScrollMode.AUTO,
                            spacing=2,
                            controls=menu_items,
                        ),
                    ),
                    self._menu_legenda(),
                ],
            ),
        )

    def _menu_legenda(self) -> ft.Control:
        if self._is_compact:
            return ft.Container(height=0)

        itens = [
            (ft.Icons.DASHBOARD_OUTLINED, "Dashboard"),
            (ft.Icons.SMART_TOY_OUTLINED, "Assistente"),
            (ft.Icons.RECEIPT_LONG_OUTLINED, "Transações"),
            (ft.Icons.UPLOAD_FILE_OUTLINED, "Importar"),
            (ft.Icons.VIEW_TIMELINE_OUTLINED, "Planner"),
            (ft.Icons.SETTINGS_OUTLINED, "Configurações"),
        ]

        linhas: List[ft.Control] = [
            ft.Text("Legenda de ícones", size=11, color=self._cor("muted"), weight=ft.FontWeight.W_600),
        ]

        for icon, texto in itens:
            linhas.append(
                ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(icon, size=14, color=self._cor("accent")),
                        ft.Text(texto, size=11, color=self._cor("muted")),
                    ],
                )
            )

        return ft.Container(
            margin=ft.margin.only(left=12, right=12, bottom=12),
            padding=10,
            border_radius=12,
            bgcolor=self._cor("panel"),
            border=ft.border.all(1, self._cor("border")),
            content=ft.Column(spacing=6, controls=linhas),
        )

    def _card(self, titulo: str, valor_ctrl: ft.Control, accent: str) -> ft.Control:
        return ft.Container(
            expand=True,
            height=120,
            border_radius=18,
            padding=16,
            bgcolor=self._cor("panel"),
            border=ft.border.all(1, self._cor("border")),
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Text(titulo, size=12, color=self._cor("muted")),
                    valor_ctrl,
                    ft.Container(width=54, height=4, border_radius=4, bgcolor=accent),
                ],
            ),
        )

    def _dashboard_view(self) -> ft.Control:
        cards_top = ft.Row(
            controls=[
                self._card("Receitas", self.lbl_receitas, self._cor("ok")),
                self._card("Despesas", self.lbl_despesas, self._cor("danger")),
            ],
            spacing=14,
        )

        ambiente = ft.Container(
            border_radius=18,
            bgcolor=self._cor("panel"),
            border=ft.border.all(1, self._cor("border")),
            padding=16,
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("Saúde do Ambiente", size=16, weight=ft.FontWeight.W_600),
                            ft.OutlinedButton(
                                "Atualizar",
                                icon=ft.Icons.REFRESH,
                                on_click=lambda _e: self._carregar_dashboard(),
                            ),
                        ],
                    ),
                    self.dashboard_diag_status,
                    self.dashboard_diag_pendencias,
                ],
            ),
        )
        cards_bottom = ft.Row(
            controls=[
                self._card("Saldo", self.lbl_saldo, self._cor("accent_alt")),
                self._card("Transações", self.lbl_total, self._cor("warning")),
            ],
            spacing=14,
        )

        categorias = ft.Container(
            border_radius=18,
            bgcolor=self._cor("panel"),
            border=ft.border.all(1, self._cor("border")),
            padding=18,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("Categorias com mais gastos", size=16, weight=ft.FontWeight.W_600),
                            self.lbl_ref,
                        ],
                    ),
                    self.dashboard_status,
                    self.categorias_col,
                ],
            ),
        )

        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=[cards_top, cards_bottom, ambiente, categorias],
        )

    def _chat_bubble(self, texto: str, origem: str) -> ft.Control:
        is_user = origem == "user"
        return ft.Row(
            alignment=ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START,
            controls=[
                ft.Container(
                    padding=12,
                    border_radius=14,
                    bgcolor=self._cor("accent_alt") if is_user else self._cor("panel"),
                    border=ft.border.all(1, self._cor("border_alt")),
                    content=ft.Text(texto, color=self._cor("text"), selectable=True),
                    width=min(740, int(self.page.width * 0.68) or 480),
                )
            ],
        )

    def _assistente_view(self) -> ft.Control:
        input_row = ft.Row(
            controls=[
                self.inp_pergunta,
                ft.OutlinedButton(
                    "Meme",
                    icon=ft.Icons.MOOD,
                    on_click=self._on_enviar_meme,
                ),
                ft.OutlinedButton(
                    "Piada",
                    icon=ft.Icons.CELEBRATION,
                    on_click=self._on_enviar_piada,
                ),
                ft.ElevatedButton(
                    "Enviar",
                    icon=ft.Icons.SEND_ROUNDED,
                    on_click=self._on_enviar_pergunta,
                    style=self._button_primary(),
                ),
            ],
        )

        return ft.Column(
            expand=True,
            spacing=12,
            controls=[
                ft.Container(
                    expand=True,
                    bgcolor=self._cor("panel_alt"),
                    border_radius=16,
                    padding=12,
                    border=ft.border.all(1, self._cor("border")),
                    content=self.chat_list,
                ),
                self.assistente_status,
                input_row,
            ],
        )

    def _transacao_row(self, item: Dict[str, Any]) -> ft.Control:
        transacao_id = int(item.get("id") or 0)
        data_raw = str(item.get("data") or "")
        data_fmt = data_raw
        if len(data_raw) >= 10 and data_raw[4] == "-":
            data_fmt = f"{data_raw[8:10]}/{data_raw[5:7]}/{data_raw[:4]}"

        descricao = str(item.get("descricao") or "Sem descrição")
        tipo = str(item.get("tipo") or "debito")
        valor = float(item.get("valor") or 0.0)
        categoria = (item.get("categoria") or {}).get("nome") if isinstance(item.get("categoria"), dict) else None
        categoria = categoria or "Outros"

        valor_txt = _currency_br(valor)
        valor_color = self._cor("ok") if tipo == "credito" else self._cor("danger")
        tipo_txt = "Crédito" if tipo == "credito" else "Débito"

        return ft.Container(
            border_radius=12,
            bgcolor=self._cor("panel_alt"),
            border=ft.border.all(1, self._cor("border_alt")),
            padding=10,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    ft.Column(
                        expand=True,
                        spacing=4,
                        controls=[
                            ft.Text(descricao, weight=ft.FontWeight.W_600, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(f"{data_fmt} - {categoria} - {tipo_txt}", color=self._cor("muted"), size=12),
                        ],
                    ),
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.Text(valor_txt, color=valor_color, weight=ft.FontWeight.W_700),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                icon_color=self._cor("danger"),
                                tooltip="Excluir transação",
                                on_click=lambda _e, tid=transacao_id: self._confirmar_exclusao_transacao(tid),
                            ),
                        ],
                    ),
                ],
            ),
        )

    def _transacoes_view(self) -> ft.Control:
        filtros = ft.Row(
            wrap=True,
            spacing=10,
            run_spacing=10,
            controls=[
                self.inp_busca_transacao,
                self.filtro_tipo,
                self.filtro_mes,
                self.filtro_ano,
                ft.ElevatedButton(
                    "Filtrar",
                    icon=ft.Icons.FILTER_ALT,
                    on_click=lambda _e: self._carregar_transacoes(reset=True),
                    style=self._button_primary(),
                ),
                ft.OutlinedButton(
                    "Limpar",
                    icon=ft.Icons.CLEAR,
                    on_click=self._limpar_filtros_transacoes,
                ),
                ft.ElevatedButton(
                    "Nova transação",
                    icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                    on_click=self._abrir_modal_nova_transacao,
                    style=self._button_secondary(),
                ),
            ],
        )

        navegacao = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.TextButton("< Página anterior", on_click=self._pagina_anterior_transacoes),
                ft.TextButton("Próxima página >", on_click=self._proxima_pagina_transacoes),
            ],
        )

        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=12,
            controls=[
                filtros,
                self.transacoes_status,
                ft.Container(
                    border_radius=16,
                    bgcolor=self._cor("panel"),
                    border=ft.border.all(1, self._cor("border")),
                    padding=12,
                    content=self.transacoes_col,
                ),
                navegacao,
            ],
        )

    def _carregar_categorias(self) -> None:
        if self.categorias_cache:
            return
        try:
            self.categorias_cache = self.api.listar_categorias()
            self.categoria_por_nome = {
                str(item.get("nome") or ""): int(item.get("id") or 0)
                for item in self.categorias_cache
                if item.get("nome") and item.get("id")
            }
        except Exception:
            self.categorias_cache = []
            self.categoria_por_nome = {}

    def _carregar_transacoes(self, *, reset: bool = False) -> None:
        if reset:
            self.transacoes_offset = 0

        self.transacoes_status.value = "Carregando transações..."
        self.transacoes_status.color = self._cor("muted")
        self.page.update()

        mes = int(self.filtro_mes.value) if (self.filtro_mes.value or "").isdigit() else None
        ano = int(self.filtro_ano.value) if (self.filtro_ano.value or "").isdigit() else None
        tipo = self.filtro_tipo.value or None
        busca = self.inp_busca_transacao.value or ""

        try:
            itens = self.api.listar_transacoes(
                mes=mes,
                ano=ano,
                tipo=tipo,
                busca=busca,
                limite=self.transacoes_limite,
                offset=self.transacoes_offset,
            )
        except Exception as exc:
            self.transacoes_status.value = self._mensagem_erro_api(exc, "Falha ao carregar transações")
            self.transacoes_status.color = self._cor("danger")
            self.page.update()
            return

        self.transacoes_ultimo_count = len(itens)
        self.transacoes_col.controls.clear()
        if not itens:
            self.transacoes_col.controls.append(ft.Text("Nenhuma transação encontrada.", color=self._cor("muted")))
        else:
            for item in itens:
                self.transacoes_col.controls.append(self._transacao_row(item))

        ini = self.transacoes_offset + 1 if self.transacoes_ultimo_count else 0
        fim = self.transacoes_offset + self.transacoes_ultimo_count
        self.transacoes_status.value = f"Mostrando {ini}-{fim}"
        self.transacoes_status.color = self._cor("accent")
        self.page.update()

    def _limpar_filtros_transacoes(self, _e: ft.ControlEvent) -> None:
        self.inp_busca_transacao.value = ""
        self.filtro_tipo.value = ""
        self.filtro_mes.value = str(dt.date.today().month)
        self.filtro_ano.value = str(dt.date.today().year)
        self._carregar_transacoes(reset=True)

    def _pagina_anterior_transacoes(self, _e: ft.ControlEvent) -> None:
        if self.transacoes_offset <= 0:
            return
        self.transacoes_offset = max(0, self.transacoes_offset - self.transacoes_limite)
        self._carregar_transacoes(reset=False)

    def _proxima_pagina_transacoes(self, _e: ft.ControlEvent) -> None:
        if self.transacoes_ultimo_count < self.transacoes_limite:
            return
        self.transacoes_offset += self.transacoes_limite
        self._carregar_transacoes(reset=False)

    def _confirmar_exclusao_transacao(self, transacao_id: int) -> None:
        def _excluir(_e: ft.ControlEvent) -> None:
            self.page.close(dialog)
            try:
                self.api.excluir_transacao(transacao_id)
                self.transacoes_status.value = "Transação excluída com sucesso."
                self.transacoes_status.color = self._cor("accent")
                self._carregar_transacoes(reset=False)
            except Exception as exc:
                self.transacoes_status.value = self._mensagem_erro_api(exc, "Falha ao excluir transação")
                self.transacoes_status.color = self._cor("danger")
                self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Excluir transação"),
            content=ft.Text("Confirma a exclusão desta transação?"),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _e: self.page.close(dialog)),
                ft.TextButton("Excluir", on_click=_excluir),
            ],
        )
        self.page.open(dialog)

    def _abrir_modal_nova_transacao(self, _e: ft.ControlEvent) -> None:
        self._carregar_categorias()

        inp_data = ft.TextField(value=str(dt.date.today()), label="Data (AAAA-MM-DD)", width=180)
        inp_desc = ft.TextField(label="Descrição", expand=True)
        inp_valor = ft.TextField(label="Valor", width=140, hint_text="Ex: 59,90")
        dd_tipo = ft.Dropdown(
            width=140,
            value="debito",
            options=[ft.dropdown.Option("debito", "Débito"), ft.dropdown.Option("credito", "Crédito")],
        )
        dd_categoria = ft.Dropdown(
            width=220,
            options=[ft.dropdown.Option("", "Sem categoria")]
            + [ft.dropdown.Option(str(item.get("id")), str(item.get("nome"))) for item in self.categorias_cache],
            value="",
        )
        info = ft.Text("", size=12, color=self._cor("danger"))

        def _salvar(_ev: ft.ControlEvent) -> None:
            descricao = (inp_desc.value or "").strip()
            valor_txt = (inp_valor.value or "").strip().replace(".", "").replace(",", ".")
            if not descricao:
                info.value = "Informe a descrição."
                self.page.update()
                return

            try:
                valor = float(valor_txt)
                if valor <= 0:
                    raise ValueError("Valor deve ser positivo")
            except Exception:
                info.value = "Valor inválido. Exemplo: 59,90"
                self.page.update()
                return

            payload: Dict[str, Any] = {
                "data": (inp_data.value or str(dt.date.today())).strip(),
                "descricao": descricao,
                "valor": valor,
                "tipo": dd_tipo.value or "debito",
            }
            if dd_categoria.value:
                payload["categoria_id"] = int(dd_categoria.value)

            try:
                self.api.criar_transacao(payload)
            except Exception as exc:
                info.value = self._mensagem_erro_api(exc, "Falha ao salvar transação")
                self.page.update()
                return

            self.page.close(dialog)
            self.transacoes_status.value = "Transação criada com sucesso."
            self.transacoes_status.color = self._cor("accent")
            self._carregar_transacoes(reset=True)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Nova transação"),
            content=ft.Container(
                width=720,
                content=ft.Column(
                    tight=True,
                    spacing=12,
                    controls=[
                        ft.Row(wrap=True, controls=[inp_data, dd_tipo, inp_valor]),
                        inp_desc,
                        dd_categoria,
                        info,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _ev: self.page.close(dialog)),
                ft.ElevatedButton("Salvar", icon=ft.Icons.SAVE_OUTLINED, on_click=_salvar),
            ],
        )
        self.page.open(dialog)

    def _carregar_fontes_importacao(self) -> None:
        if not self.contas_cache:
            try:
                self.contas_cache = self.api.listar_contas()
            except Exception:
                self.contas_cache = []

        if not self.cartoes_cache:
            try:
                self.cartoes_cache = self.api.listar_cartoes()
            except Exception:
                self.cartoes_cache = []

        self.importar_conta.options = [ft.dropdown.Option("", "Conta (opcional)")] + [
            ft.dropdown.Option(str(item.get("id")), str(item.get("nome") or f"Conta {item.get('id')}"))
            for item in self.contas_cache
        ]
        self.importar_cartao.options = [ft.dropdown.Option("", "Cartão (opcional)")] + [
            ft.dropdown.Option(str(item.get("id")), str(item.get("nome") or f"Cartão {item.get('id')}"))
            for item in self.cartoes_cache
        ]
        self._atualizar_campos_importacao()

    def _atualizar_campos_importacao(self) -> None:
        tipo = self.importar_tipo.value or "pdf_bancario"
        usa_cartao = tipo == "pdf_fatura"
        self.importar_cartao.visible = usa_cartao
        self.importar_conta.visible = not usa_cartao
        self.page.update()

    def _on_file_picker_result(self, e: Any) -> None:
        """Callback para quando arquivo é selecionado (não usado em Flet)."""
        pass

    def _selecionar_arquivo_importacao(self, _e: ft.ControlEvent) -> None:
        """Placeholder para seleção de arquivo."""
        self.importar_status.value = "Funcionalidade de file picker em desenvolvimento para Flet."
        self.importar_status.color = self._cor("danger")
        self.page.update()

    def _importar_arquivo_agora(self, _e: ft.ControlEvent) -> None:
        """Placeholder removido - use a view simplificada."""
        pass

    def _importar_view(self) -> ft.Control:
        """View para importação de arquivos."""
        # Input para caminho do arquivo
        inp_arquivo = ft.TextField(
            label="Caminho do arquivo",
            hint_text="Ex: C:\\Downloads\\extrato.pdf",
            expand=True,
            border_radius=12,
            bgcolor=self._cor("input_bg"),
            border_color=self._cor("input_border"),
            text_style=ft.TextStyle(color=self._cor("text")),
        )

        box_resultado = ft.Container(
            border_radius=12,
            bgcolor=self._cor("panel_alt"),
            border=ft.border.all(1, self._cor("border_alt")),
            padding=10,
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Text("Resultado da importação", weight=ft.FontWeight.W_600),
                    self.importar_resultado,
                ],
            ),
        )

        def _importar_com_path(_e: ft.ControlEvent) -> None:
            """Realiza importação com caminho fornecido."""
            arquivo_path = (inp_arquivo.value or "").strip()
            if not arquivo_path:
                self.importar_status.value = "Informe o caminho do arquivo."
                self.importar_status.color = self._cor("danger")
                self.page.update()
                return

            tipo = self.importar_tipo.value or "pdf_bancario"
            conta_id = int(self.importar_conta.value) if (self.importar_conta.value or "").isdigit() else None
            cartao_id = int(self.importar_cartao.value) if (self.importar_cartao.value or "").isdigit() else None

            self.importar_status.value = "Importando arquivo..."
            self.importar_status.color = self._cor("muted")
            self.importar_resultado.value = ""
            self.page.update()

            try:
                resultado = self.api.importar_arquivo(
                    caminho_arquivo=arquivo_path,
                    tipo_importacao=tipo,
                    conta_id=conta_id,
                    cartao_id=cartao_id,
                )
            except Exception as exc:
                self.importar_status.value = self._mensagem_erro_api(exc, "Falha na importação")
                self.importar_status.color = self._cor("danger")
                self.page.update()
                return

            self.importar_status.value = "Importação concluída com sucesso."
            self.importar_status.color = self._cor("accent")
            self.importar_resultado.value = json.dumps(resultado, ensure_ascii=False, indent=2)
            inp_arquivo.value = ""
            self.page.update()

        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=12,
            controls=[
                ft.Container(
                    border_radius=16,
                    bgcolor=self._cor("panel"),
                    border=ft.border.all(1, self._cor("border")),
                    padding=14,
                    content=ft.Column(
                        spacing=12,
                        controls=[
                            ft.Text("Importação de extratos e planilhas", size=18, weight=ft.FontWeight.W_700),
                            ft.Row(wrap=True, spacing=10, run_spacing=10, controls=[self.importar_tipo, self.importar_conta, self.importar_cartao]),
                            ft.Row(
                                wrap=True,
                                spacing=10,
                                run_spacing=10,
                                controls=[
                                    inp_arquivo,
                                    ft.ElevatedButton(
                                        "Importar",
                                        icon=ft.Icons.UPLOAD_FILE,
                                        on_click=_importar_com_path,
                                        style=self._button_primary(),
                                    ),
                                ],
                            ),
                            ft.Text("Informe o caminho completo do arquivo na sua máquina.", size=11, color=self._cor("muted")),
                            self.importar_status,
                        ],
                    ),
                ),
                box_resultado,
            ],
        )

    def _placeholder_view(self, titulo: str, subtitulo: str) -> ft.Control:
        return ft.Container(
            expand=True,
            border_radius=16,
            bgcolor=self._cor("panel"),
            border=ft.border.all(1, self._cor("border")),
            alignment=ft.alignment.center,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.CONSTRUCTION, size=38, color=self._cor("accent")),
                    ft.Text(titulo, size=20, weight=ft.FontWeight.W_600),
                    ft.Text(subtitulo, size=13, color=self._cor("muted")),
                ],
            ),
        )

    def _configuracoes_view(self) -> ft.Control:
        """Tela de configurações da aplicação."""

        def _linha_diagnostico(nome: str, ok: bool, mensagem: str, detalhe: str = "") -> ft.Control:
            cor = self._cor("ok") if ok else self._cor("danger")
            icone = ft.Icons.CHECK_CIRCLE_OUTLINE if ok else ft.Icons.ERROR_OUTLINE
            texto_detalhe = f" ({detalhe})" if detalhe else ""
            return ft.Container(
                border_radius=12,
                bgcolor=self._cor("panel_alt"),
                border=ft.border.all(1, self._cor("border_alt")),
                padding=10,
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(icone, size=16, color=cor),
                                ft.Text(f"{nome}{texto_detalhe}", weight=ft.FontWeight.W_600),
                            ],
                        ),
                        ft.Text(mensagem, size=11, color=self._cor("muted"), expand=True, text_align=ft.TextAlign.RIGHT, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ],
                ),
            )
        
        def _save_api_url(_e: ft.ControlEvent) -> None:
            """Salva URL da API nas preferências."""
            url = (inp_api_url.value or "").strip()
            if not url:
                status_info.value = "URL não pode estar vazia."
                status_info.color = self._cor("danger")
                self.page.update()
                return
            # Aqui você pode salvar em um arquivo de config ou env
            status_info.value = f"API URL atualizada para: {url}"
            status_info.color = self._cor("accent")
            self.page.update()

        def _exportar_backup(_e: ft.ControlEvent) -> None:
            """Inicia exportação de backup dos dados."""
            status_info.value = "Exportação iniciada... (em desenvolvimento)"
            status_info.color = self._cor("muted")
            self.page.update()

        def _limpar_cache(_e: ft.ControlEvent) -> None:
            """Limpa cache da aplicação."""
            self.categorias_cache.clear()
            self.categoria_por_nome.clear()
            self.contas_cache.clear()
            self.cartoes_cache.clear()
            status_info.value = "Cache limpo com sucesso."
            status_info.color = self._cor("accent")
            self.page.update()

        def _aplicar_tema(_e: ft.ControlEvent) -> None:
            tema = dd_tema.value or "oceano"
            self._aplicar_tema_visual(tema)
            status_info.value = "Tema visual atualizado."
            status_info.color = self._cor("accent")
            self.page.update()

        def _atualizar_diagnostico(_e: ft.ControlEvent) -> None:
            diag_status.value = "Atualizando diagnóstico de ambiente..."
            diag_status.color = self._cor("muted")
            self.page.update()

            try:
                payload = self.api.diagnostico_ambiente()
                self.dashboard_diag_payload = payload
                servicos = payload.get("servicos") or {}
                pendencias = payload.get("pendencias") or []

                diag_col.controls.clear()
                mapa = [
                    ("Gemini", "gemini"),
                    ("OpenRouter", "openrouter"),
                    ("IA Local (Ollama)", "local_ai"),
                    ("Telegram", "telegram"),
                    ("Voz (OpenAI)", "voz"),
                ]
                for rotulo, chave in mapa:
                    item = servicos.get(chave) or {}
                    ok = bool(item.get("ok"))
                    msg = str(item.get("mensagem") or "Sem informações.")
                    detalhe = str(item.get("model") or "")
                    diag_col.controls.append(_linha_diagnostico(rotulo, ok, msg, detalhe))

                if pendencias:
                    diag_status.value = f"Diagnóstico concluído: {len(pendencias)} pendência(s)."
                    diag_status.color = self._cor("danger")
                else:
                    diag_status.value = "Diagnóstico concluído: ambiente pronto."
                    diag_status.color = self._cor("ok")
            except Exception as exc:
                diag_status.value = f"Falha ao carregar diagnóstico: {exc}"
                diag_status.color = self._cor("danger")

            self.page.update()

        def _copiar_diagnostico(_e: ft.ControlEvent) -> None:
            if not self.dashboard_diag_payload:
                diag_status.value = "Atualize o diagnóstico antes de copiar."
                diag_status.color = self._cor("warning")
                self.page.update()
                return
            try:
                texto = json.dumps(self.dashboard_diag_payload, ensure_ascii=False, indent=2)
                self.page.set_clipboard(texto)
                diag_status.value = "Diagnóstico copiado para a área de transferência."
                diag_status.color = self._cor("ok")
            except Exception as exc:
                diag_status.value = f"Falha ao copiar diagnóstico: {exc}"
                diag_status.color = self._cor("danger")
            self.page.update()

        # Controles
        inp_api_url = ft.TextField(
            label="URL da API",
            value=self.api.base or "http://127.0.0.1:8000",
            expand=True,
            border_radius=12,
            bgcolor=self._cor("input_bg"),
            border_color=self._cor("input_border"),
            text_style=ft.TextStyle(color=self._cor("text")),
        )

        dd_tema = ft.Dropdown(
            width=240,
            value=self._tema_visual,
            options=[
                ft.dropdown.Option("oceano", "Oceano Escuro"),
                ft.dropdown.Option("claro", "Claro Neutro"),
                ft.dropdown.Option("contraste", "Alto Contraste"),
                ft.dropdown.Option("aurora", "Aurora Neon"),
                ft.dropdown.Option("sunset", "Sunset Quente"),
                ft.dropdown.Option("floresta", "Floresta Profunda"),
                ft.dropdown.Option("areia", "Areia Suave"),
                ft.dropdown.Option("lavanda", "Lavanda Pastel"),
            ],
            border_radius=10,
            bgcolor=self._cor("input_bg"),
            border_color=self._cor("input_border"),
        )
        
        status_info = ft.Text("", size=12, color=self._cor("muted"))
        diag_status = ft.Text("Clique em 'Atualizar diagnóstico' para verificar as integrações.", size=12, color=self._cor("muted"))
        diag_col = ft.Column(spacing=8)

        seção_api = ft.Container(
            border_radius=16,
            bgcolor=self._cor("panel"),
            border=ft.border.all(1, self._cor("border")),
            padding=16,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Text("Configurações da API", size=14, weight=ft.FontWeight.W_600),
                    inp_api_url,
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.ElevatedButton(
                                "Salvar URL",
                                icon=ft.Icons.SAVE_OUTLINED,
                                on_click=_save_api_url,
                                style=self._button_primary(),
                            ),
                        ],
                    ),
                    ft.Divider(height=1, color=self._cor("border")),
                    ft.Text("Tema visual", size=14, weight=ft.FontWeight.W_600),
                    ft.Row(
                        wrap=True,
                        spacing=8,
                        run_spacing=8,
                        controls=[
                            dd_tema,
                            ft.ElevatedButton(
                                "Aplicar tema",
                                icon=ft.Icons.PALETTE_OUTLINED,
                                on_click=_aplicar_tema,
                                style=self._button_primary(),
                            ),
                        ],
                    ),
                ],
            ),
        )

        seção_dados = ft.Container(
            border_radius=16,
            bgcolor=self._cor("panel"),
            border=ft.border.all(1, self._cor("border")),
            padding=16,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Text("Gerenciamento de Dados", size=14, weight=ft.FontWeight.W_600),
                    ft.Row(
                        wrap=True,
                        spacing=8,
                        run_spacing=8,
                        controls=[
                            ft.ElevatedButton(
                                "Exportar Backup",
                                icon=ft.Icons.DOWNLOAD_OUTLINED,
                                on_click=_exportar_backup,
                                style=self._button_secondary(),
                            ),
                            ft.OutlinedButton(
                                "Limpar Cache",
                                icon=ft.Icons.DELETE_OUTLINE,
                                on_click=_limpar_cache,
                            ),
                        ],
                    ),
                    ft.Text("Cache local de categorias, contas e cartões será apagado.", size=11, color=self._cor("muted")),
                ],
            ),
        )

        seção_diagnostico = ft.Container(
            border_radius=16,
            bgcolor=self._cor("panel"),
            border=ft.border.all(1, self._cor("border")),
            padding=16,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Text("Diagnóstico de Ambiente", size=14, weight=ft.FontWeight.W_600),
                    ft.Row(
                        wrap=True,
                        spacing=8,
                        run_spacing=8,
                        controls=[
                            ft.ElevatedButton(
                                "Atualizar diagnóstico",
                                icon=ft.Icons.REFRESH,
                                on_click=_atualizar_diagnostico,
                                style=self._button_secondary(),
                            ),
                            ft.OutlinedButton(
                                "Copiar diagnóstico",
                                icon=ft.Icons.CONTENT_COPY,
                                on_click=_copiar_diagnostico,
                            ),
                        ],
                    ),
                    diag_status,
                    diag_col,
                ],
            ),
        )

        seção_sobre = ft.Container(
            border_radius=16,
            bgcolor=self._cor("panel"),
            border=ft.border.all(1, self._cor("border")),
            padding=16,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Text("Sobre", size=14, weight=ft.FontWeight.W_600),
                    ft.Column(
                        spacing=4,
                        controls=[
                            ft.Text("Vorcaro - Assistente Financeiro", weight=ft.FontWeight.W_500),
                            ft.Text("Versão 2.0 - Flet UI (Flutter)", size=11, color=self._cor("muted")),
                            ft.Text("© 2026 - Todos os direitos reservados", size=10, color=self._cor("muted")),
                        ],
                    ),
                ],
            ),
        )

        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=[
                status_info,
                seção_api,
                seção_diagnostico,
                seção_dados,
                seção_sobre,
            ],
        )

    def _planner_data_ref(self) -> str:
        bruto = (self.planner_data.value or "").strip()
        try:
            data_ref = dt.date.fromisoformat(bruto)
            return str(data_ref)
        except Exception:
            hoje = dt.date.today()
            self.planner_data.value = str(hoje)
            return str(hoje)

    def _planner_tarefa_card(self, item: Dict[str, Any]) -> ft.Control:
        tarefa_id = int(item.get("id") or 0)
        titulo = str(item.get("titulo") or "Sem título")
        descricao = str(item.get("descricao") or "")
        data_ref = str(item.get("data") or self._planner_data_ref())
        prioridade = str(item.get("prioridade") or "media").capitalize()
        area = str(item.get("area") or "pessoal").capitalize()
        status = str(item.get("status") or "a_fazer")
        hora_inicio = str(item.get("hora_inicio") or "").strip()
        hora_fim = str(item.get("hora_fim") or "").strip()
        duracao = item.get("duracao_min")
        pontos_base = int(item.get("pontos_base") or 0)

        if hora_inicio and hora_fim:
            horario_txt = f"{hora_inicio} - {hora_fim}"
        elif hora_inicio:
            horario_txt = f"Início: {hora_inicio}"
        elif duracao:
            horario_txt = f"Duração: {int(duracao)} min"
        else:
            horario_txt = "Horário livre"

        is_done = status == "concluido"
        btn = ft.ElevatedButton(
            "Concluir",
            icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
            on_click=lambda _e, tid=tarefa_id: self._completar_tarefa_planner(tid),
            style=self._button_success(),
            visible=not is_done,
        )

        btn_editar = ft.OutlinedButton(
            "Editar",
            icon=ft.Icons.EDIT_OUTLINED,
            on_click=lambda _e, item_data=dict(item): self._abrir_edicao_tarefa_planner(item_data),
        )

        btn_excluir = ft.OutlinedButton(
            "Excluir",
            icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
            style=ft.ButtonStyle(color=self._cor("danger")),
            on_click=lambda _e, tid=tarefa_id, tt=titulo: self._confirmar_exclusao_tarefa_planner(tid, tt),
        )

        return ft.Container(
            border_radius=12,
            bgcolor=self._cor("panel_alt"),
            border=ft.border.all(1, self._cor("border_alt")),
            padding=10,
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(titulo, weight=ft.FontWeight.W_600, expand=True),
                            ft.Text(f"+{pontos_base} pts", color=self._cor("accent"), size=11),
                        ],
                    ),
                    ft.Text(descricao or "Sem descrição", size=12, color=self._cor("muted")),
                    ft.Text(f"{data_ref} - {horario_txt} - {area} - {prioridade}", size=11, color=self._cor("muted")),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(status.replace("_", " ").title(), size=11, color=self._cor("muted")),
                            ft.Row(spacing=6, wrap=True, controls=[btn_editar, btn_excluir, btn]),
                        ],
                    ),
                ],
            ),
        )

    def _confirmar_exclusao_tarefa_planner(self, tarefa_id: int, titulo: str) -> None:
        def _excluir(_e: ft.ControlEvent) -> None:
            self.page.close(dialog)
            try:
                self.api.excluir_tarefa_planner(tarefa_id)
                self.planner_status.value = f"Tarefa '{titulo}' excluída com sucesso."
                self.planner_status.color = self._cor("accent")
                self._carregar_planner()
            except Exception as exc:
                self.planner_status.value = self._mensagem_erro_api(exc, "Falha ao excluir tarefa")
                self.planner_status.color = self._cor("danger")
                self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Excluir tarefa"),
            content=ft.Text(f"Confirma excluir a tarefa '{titulo}'?"),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _e: self.page.close(dialog)),
                ft.TextButton("Excluir", on_click=_excluir),
            ],
        )
        self.page.open(dialog)

    def _abrir_edicao_tarefa_planner(self, item: Dict[str, Any]) -> None:
        tarefa_id = int(item.get("id") or 0)
        inp_titulo = ft.TextField(label="Título", value=str(item.get("titulo") or ""), expand=True)
        inp_descricao = ft.TextField(label="Descrição", value=str(item.get("descricao") or ""), multiline=True, min_lines=2, max_lines=4)
        inp_data = ft.TextField(label="Data (AAAA-MM-DD)", value=str(item.get("data") or self._planner_data_ref()), width=170)
        inp_hora_inicio = ft.TextField(label="Início (HH:MM)", value=str(item.get("hora_inicio") or ""), width=140)
        inp_hora_fim = ft.TextField(label="Fim (HH:MM)", value=str(item.get("hora_fim") or ""), width=140)

        dd_prioridade = ft.Dropdown(
            label="Prioridade",
            width=150,
            value=str(item.get("prioridade") or "media"),
            options=[
                ft.dropdown.Option("alta", "Alta"),
                ft.dropdown.Option("media", "Média"),
                ft.dropdown.Option("baixa", "Baixa"),
            ],
        )

        dd_area = ft.Dropdown(
            label="Área",
            width=170,
            value=str(item.get("area") or "pessoal"),
            options=[
                ft.dropdown.Option("pessoal", "Pessoal"),
                ft.dropdown.Option("trabalho", "Trabalho"),
                ft.dropdown.Option("financeiro", "Financeiro"),
                ft.dropdown.Option("saude", "Saúde"),
                ft.dropdown.Option("outro", "Outro"),
            ],
        )

        dd_status = ft.Dropdown(
            label="Status",
            width=170,
            value=str(item.get("status") or "a_fazer"),
            options=[
                ft.dropdown.Option("a_fazer", "A fazer"),
                ft.dropdown.Option("em_progresso", "Em progresso"),
                ft.dropdown.Option("concluido", "Concluído"),
            ],
        )

        info = ft.Text("", size=12, color=self._cor("danger"))

        def _salvar(_e: ft.ControlEvent) -> None:
            titulo = (inp_titulo.value or "").strip()
            if not titulo:
                info.value = "Título é obrigatório."
                self.page.update()
                return

            payload = {
                "titulo": titulo,
                "descricao": (inp_descricao.value or "").strip(),
                "data": (inp_data.value or "").strip() or None,
                "hora_inicio": (inp_hora_inicio.value or "").strip() or None,
                "hora_fim": (inp_hora_fim.value or "").strip() or None,
                "prioridade": dd_prioridade.value or "media",
                "area": dd_area.value or "pessoal",
                "status": dd_status.value or "a_fazer",
                "organizacao_id": 1,
            }

            try:
                self.api.atualizar_tarefa_planner(tarefa_id, payload)
            except Exception as exc:
                info.value = self._mensagem_erro_api(exc, "Falha ao atualizar tarefa")
                self.page.update()
                return

            self.page.close(dialog)
            self.planner_status.value = "Tarefa atualizada com sucesso."
            self.planner_status.color = self._cor("accent")
            self._carregar_planner()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Editar tarefa"),
            content=ft.Container(
                width=760,
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        inp_titulo,
                        inp_descricao,
                        ft.Row(wrap=True, spacing=8, run_spacing=8, controls=[inp_data, inp_hora_inicio, inp_hora_fim]),
                        ft.Row(wrap=True, spacing=8, run_spacing=8, controls=[dd_prioridade, dd_area, dd_status]),
                        info,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _e: self.page.close(dialog)),
                ft.ElevatedButton("Salvar", icon=ft.Icons.SAVE_OUTLINED, on_click=_salvar),
            ],
        )
        self.page.open(dialog)

    def _planner_coluna_kanban(self, titulo: str, items_col: ft.Column, accent: str) -> ft.Control:
        return ft.Container(
            expand=True,
            border_radius=14,
            bgcolor=self._cor("panel"),
            border=ft.border.all(1, self._cor("border")),
            padding=10,
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(width=8, height=8, border_radius=8, bgcolor=accent),
                            ft.Text(titulo, weight=ft.FontWeight.W_600),
                        ],
                    ),
                    items_col,
                ],
            ),
        )

    def _agenda_financeira_card(self, item: Dict[str, Any]) -> ft.Control:
        titulo = str(item.get("titulo") or "Evento financeiro")
        status = str(item.get("status") or "pendente").replace("_", " ").title()
        tipo = str(item.get("tipo") or "outro").replace("_", " ").title()
        valor = float(item.get("valor") or 0.0)
        desc = str(item.get("descricao") or "")

        return ft.Container(
            border_radius=10,
            bgcolor=self._cor("panel_alt"),
            border=ft.border.all(1, self._cor("border_alt")),
            padding=10,
            content=ft.Column(
                spacing=4,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(titulo, weight=ft.FontWeight.W_600, expand=True),
                            ft.Text(_currency_br(valor), color=self._cor("warning")),
                        ],
                    ),
                    ft.Text(f"{tipo} - {status}", size=11, color=self._cor("muted")),
                    ft.Text(desc or "Sem descrição", size=11, color=self._cor("muted")),
                ],
            ),
        )

    def _compromisso_card(self, item: Dict[str, Any]) -> ft.Control:
        titulo = str(item.get("titulo") or "Compromisso")
        local = str(item.get("local") or "")
        desc = str(item.get("descricao") or "")
        hi = str(item.get("hora_inicio") or "").strip()
        hf = str(item.get("hora_fim") or "").strip()
        concluido = bool(item.get("concluido"))

        if hi and hf:
            horario = f"{hi} - {hf}"
        elif hi:
            horario = hi
        else:
            horario = "Sem horário"

        status = "Concluído" if concluido else "Pendente"

        return ft.Container(
            border_radius=10,
            bgcolor=self._cor("panel_alt"),
            border=ft.border.all(1, self._cor("border_alt")),
            padding=10,
            content=ft.Column(
                spacing=4,
                controls=[
                    ft.Text(titulo, weight=ft.FontWeight.W_600),
                    ft.Text(f"{horario} - {status}", size=11, color=self._cor("muted")),
                    ft.Text(f"Local: {local}" if local else "Local: não informado", size=11, color=self._cor("muted")),
                    ft.Text(desc or "Sem descrição", size=11, color=self._cor("muted")),
                ],
            ),
        )

    def _planner_view(self) -> ft.Control:
        cards = ft.Row(
            spacing=12,
            controls=[
                self._card("Pontos", self.lbl_planner_pontos, self._cor("accent_alt")),
                self._card("Nível", self.lbl_planner_nivel, self._cor("accent")),
                self._card("XP Total", self.lbl_planner_xp, self._cor("ok")),
                self._card("Badges", self.lbl_planner_badges, self._cor("warning")),
            ],
        )

        toolbar = ft.Row(
            wrap=True,
            spacing=10,
            run_spacing=10,
            controls=[
                self.planner_data,
                ft.ElevatedButton(
                    "Atualizar Planner",
                    icon=ft.Icons.REFRESH,
                    on_click=lambda _e: self._carregar_planner(),
                    style=self._button_primary(),
                ),
            ],
        )

        organizador = ft.Container(
            border_radius=16,
            bgcolor=self._cor("panel"),
            border=ft.border.all(1, self._cor("border")),
            padding=14,
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Text("Smart Planner (IA)", size=16, weight=ft.FontWeight.W_700),
                    self.planner_texto_livre,
                    ft.Row(
                        spacing=10,
                        controls=[
                            ft.ElevatedButton(
                                "Organizar com IA",
                                icon=ft.Icons.AUTO_AWESOME,
                                on_click=self._organizar_tarefas_planner,
                                style=self._button_secondary(),
                            ),
                            self.planner_status,
                        ],
                    ),
                ],
            ),
        )

        tabs = ft.Column(
            spacing=10,
            controls=[
                ft.Container(
                    border_radius=14,
                    bgcolor=self._cor("panel"),
                    border=ft.border.all(1, self._cor("border")),
                    padding=10,
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            ft.Text("Agenda Unificada (Financeira + Compromissos)", size=15, weight=ft.FontWeight.W_600),
                            ft.Row(
                                vertical_alignment=ft.CrossAxisAlignment.START,
                                spacing=10,
                                controls=[
                                    ft.Container(
                                        expand=True,
                                        content=ft.Column(
                                            spacing=8,
                                            controls=[
                                                ft.Text("Agenda Financeira", size=13, weight=ft.FontWeight.W_600, color=self._cor("warning")),
                                                self.planner_agenda_financeira_col,
                                            ],
                                        ),
                                    ),
                                    ft.Container(
                                        expand=True,
                                        content=ft.Column(
                                            spacing=8,
                                            controls=[
                                                ft.Text("Compromissos", size=13, weight=ft.FontWeight.W_600, color=self._cor("accent_alt")),
                                                self.planner_compromissos_col,
                                            ],
                                        ),
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                ft.Container(
                    border_radius=14,
                    bgcolor=self._cor("panel"),
                    border=ft.border.all(1, self._cor("border")),
                    padding=10,
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            ft.Text("Timeline", size=15, weight=ft.FontWeight.W_600),
                            self.planner_timeline_col,
                        ],
                    ),
                ),
                ft.Container(
                    border_radius=14,
                    bgcolor=self._cor("panel"),
                    border=ft.border.all(1, self._cor("border")),
                    padding=10,
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            ft.Text("SmartPlanner", size=15, weight=ft.FontWeight.W_600),
                            self.planner_smart_col,
                        ],
                    ),
                ),
                ft.Container(
                    border_radius=14,
                    bgcolor=self._cor("panel"),
                    border=ft.border.all(1, self._cor("border")),
                    padding=10,
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            ft.Text("Kanban", size=15, weight=ft.FontWeight.W_600),
                            ft.Row(
                                vertical_alignment=ft.CrossAxisAlignment.START,
                                spacing=10,
                                controls=[
                                    self._planner_coluna_kanban("A fazer", self.planner_kanban_todo_col, self._cor("warning")),
                                    self._planner_coluna_kanban("Em progresso", self.planner_kanban_doing_col, self._cor("accent_alt")),
                                    self._planner_coluna_kanban("Concluído", self.planner_kanban_done_col, self._cor("ok")),
                                ],
                            ),
                        ],
                    ),
                ),
            ],
        )

        badges_box = ft.Container(
            border_radius=16,
            bgcolor=self._cor("panel"),
            border=ft.border.all(1, self._cor("border")),
            padding=14,
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Text("Badges", size=15, weight=ft.FontWeight.W_600),
                    self.planner_badges_col,
                ],
            ),
        )

        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=12,
            controls=[cards, toolbar, organizador, badges_box, tabs],
        )

    def _completar_tarefa_planner(self, tarefa_id: int) -> None:
        try:
            resultado = self.api.completar_tarefa_planner(tarefa_id)
            pontos = int(resultado.get("pontos_ganhos") or 0)
            self.planner_status.value = f"Tarefa concluída. +{pontos} pontos!"
            self.planner_status.color = self._cor("accent")
        except Exception as exc:
            self.planner_status.value = self._mensagem_erro_api(exc, "Erro ao concluir tarefa")
            self.planner_status.color = self._cor("danger")
        self._carregar_planner()

    def _organizar_tarefas_planner(self, _e: ft.ControlEvent) -> None:
        texto = (self.planner_texto_livre.value or "").strip()
        if not texto:
            self.planner_status.value = "Digite tarefas em texto livre para a IA organizar."
            self.planner_status.color = self._cor("danger")
            self.page.update()
            return

        self.planner_status.value = "Organizando tarefas com IA..."
        self.planner_status.color = self._cor("muted")
        self.page.update()

        try:
            resposta = self.api.organizar_tarefas_planner(texto=texto, data_ref=self._planner_data_ref())
            total = int(resposta.get("tarefas_criadas") or len(resposta.get("tarefas") or []))
            self.planner_status.value = f"IA organizou {total} tarefa(s)."
            self.planner_status.color = self._cor("accent")
            self.planner_texto_livre.value = ""
        except Exception as exc:
            self.planner_status.value = self._mensagem_erro_api(exc, "Falha ao organizar tarefas")
            self.planner_status.color = self._cor("danger")

        self._carregar_planner()

    def _carregar_planner(self) -> None:
        data_ref = self._planner_data_ref()
        self.planner_status.value = f"Sincronizando Planner ({data_ref})..."
        self.planner_status.color = self._cor("muted")
        self.page.update()

        erros: List[str] = []

        try:
            pont = self.api.obter_pontuacao_planner()
            self.lbl_planner_pontos.value = str(int(pont.get("pontos_totais") or pont.get("pontos") or 0))
            self.lbl_planner_nivel.value = f"Nível {int(pont.get('nivel') or 1)}"
            self.lbl_planner_xp.value = f"{int(pont.get('xp_total') or pont.get('xp') or 0)} XP"
            self.lbl_planner_badges.value = str(int(pont.get("badges_desbloqueadas") or 0))

            self.planner_badges_col.controls.clear()
            badges = pont.get("badges") or []
            if not badges:
                self.planner_badges_col.controls.append(ft.Text("Nenhuma badge registrada ainda.", color=self._cor("muted")))
            else:
                for badge in badges[:8]:
                    unlocked = bool(badge.get("desbloqueada"))
                    ico = "[OK]" if unlocked else "[LOCK]"
                    cor = self._cor("warning") if unlocked else self._cor("muted")
                    nome = str(badge.get("nome") or "Badge")
                    desc = str(badge.get("descricao") or "")
                    self.planner_badges_col.controls.append(
                        ft.Text(f"{ico} {nome} - {desc}", size=11, color=cor)
                    )

            try:
                timeline = self.api.obter_timeline_planner(data_ref)
                horarios = timeline.get("horarios") or []
                if not horarios and isinstance(timeline.get("timeline"), dict):
                    horarios = [
                        {"hora": hora, "tarefas": tarefas}
                        for hora, tarefas in sorted((timeline.get("timeline") or {}).items())
                    ]
                self.planner_timeline_col.controls.clear()
                for slot in horarios:
                    tarefas = slot.get("tarefas") or []
                    if not tarefas:
                        continue
                    hora = str(slot.get("hora") or "--:--")
                    self.planner_timeline_col.controls.append(ft.Text(hora, size=12, color=self._cor("muted")))
                    for t in tarefas:
                        self.planner_timeline_col.controls.append(self._planner_tarefa_card(t))
                if not self.planner_timeline_col.controls:
                    self.planner_timeline_col.controls.append(ft.Text("Sem tarefas na timeline.", color=self._cor("muted")))
            except Exception:
                erros.append("timeline")

            try:
                smart = self.api.obter_smartplanner(data_ref)
                smart_horarios = smart.get("horarios") or []
                if not smart_horarios and isinstance(smart.get("timeline"), dict):
                    smart_horarios = [
                        {"hora": hora, "tarefas": tarefas}
                        for hora, tarefas in sorted((smart.get("timeline") or {}).items())
                    ]
                self.planner_smart_col.controls.clear()
                for slot in smart_horarios:
                    tarefas = slot.get("tarefas") or []
                    if not tarefas:
                        continue
                    faixa = str(slot.get("hora") or "--:--")
                    self.planner_smart_col.controls.append(ft.Text(f"Sugestão {faixa}", size=12, color=self._cor("accent")))
                    for t in tarefas:
                        self.planner_smart_col.controls.append(self._planner_tarefa_card(t))
                if not self.planner_smart_col.controls:
                    self.planner_smart_col.controls.append(ft.Text("Sem sugestões para este dia.", color=self._cor("muted")))
            except Exception:
                erros.append("smartplanner")

            try:
                kanban = self.api.obter_kanban_planner(data_ref)
                colunas = kanban.get("colunas") if isinstance(kanban.get("colunas"), dict) else kanban
                self.planner_kanban_todo_col.controls.clear()
                self.planner_kanban_doing_col.controls.clear()
                self.planner_kanban_done_col.controls.clear()

                for t in (colunas.get("a_fazer") or []):
                    self.planner_kanban_todo_col.controls.append(self._planner_tarefa_card(t))
                for t in (colunas.get("em_progresso") or []):
                    self.planner_kanban_doing_col.controls.append(self._planner_tarefa_card(t))
                for t in (colunas.get("concluido") or []):
                    self.planner_kanban_done_col.controls.append(self._planner_tarefa_card(t))

                if not self.planner_kanban_todo_col.controls:
                    self.planner_kanban_todo_col.controls.append(ft.Text("Sem itens", size=11, color=self._cor("muted")))
                if not self.planner_kanban_doing_col.controls:
                    self.planner_kanban_doing_col.controls.append(ft.Text("Sem itens", size=11, color=self._cor("muted")))
                if not self.planner_kanban_done_col.controls:
                    self.planner_kanban_done_col.controls.append(ft.Text("Sem itens", size=11, color=self._cor("muted")))
            except Exception:
                erros.append("kanban")

            try:
                agenda_fin = self.api.obter_agenda_financeira(data_ref)
                self.planner_agenda_financeira_col.controls.clear()
                for ev in (agenda_fin.get("itens") or []):
                    self.planner_agenda_financeira_col.controls.append(self._agenda_financeira_card(ev))
                if not self.planner_agenda_financeira_col.controls:
                    self.planner_agenda_financeira_col.controls.append(ft.Text("Sem eventos financeiros para esta data.", size=11, color=self._cor("muted")))
            except Exception:
                erros.append("agenda_financeira")

            try:
                compromissos = self.api.obter_compromissos(data_ref)
                self.planner_compromissos_col.controls.clear()
                for comp in (compromissos.get("itens") or []):
                    self.planner_compromissos_col.controls.append(self._compromisso_card(comp))
                if not self.planner_compromissos_col.controls:
                    self.planner_compromissos_col.controls.append(ft.Text("Sem compromissos para esta data.", size=11, color=self._cor("muted")))
            except Exception:
                erros.append("compromissos")

            if erros:
                self.planner_status.value = f"Planner atualizado com alertas: {', '.join(erros)}"
                self.planner_status.color = self._cor("warning")
            else:
                self.planner_status.value = "Planner atualizado com sucesso."
                self.planner_status.color = self._cor("accent")
        except Exception as exc:
            self.planner_status.value = self._mensagem_erro_api(exc, "Falha ao carregar Planner")
            self.planner_status.color = self._cor("danger")

        self.page.update()

    def _header(self) -> ft.Control:
        self.header_action_btn = ft.OutlinedButton(
            "Atualizar dashboard",
            icon=ft.Icons.REFRESH,
            on_click=lambda _e: self._carregar_dashboard(),
        )
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=22, vertical=14),
            bgcolor=self._cor("panel_alt"),
            border=ft.border.only(bottom=ft.BorderSide(1, self._cor("border_alt"))),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(
                        spacing=0,
                        controls=[
                            ft.Text("Assistente Financeiro Vorcaro", size=20, weight=ft.FontWeight.W_700),
                            ft.Text("Nova experiência visual em Flet", size=12, color=self._cor("muted")),
                        ],
                    ),
                    self.header_action_btn,
                ],
            ),
        )

    def _current_view(self) -> ft.Control:
        if self._menu_idx == 0:
            return self._dashboard_view()
        if self._menu_idx == 1:
            return self._assistente_view()
        if self._menu_idx == 2:
            return self._transacoes_view()
        if self._menu_idx == 3:
            return self._importar_view()
        if self._menu_idx == 4:
            return self._planner_view()
        return self._configuracoes_view()

    def _render_content(self) -> None:
        if self._menu_idx == 0:
            self.header_action_btn.text = "Atualizar dashboard"
            self.header_action_btn.icon = ft.Icons.REFRESH
            self.header_action_btn.on_click = lambda _e: self._carregar_dashboard()
        elif self._menu_idx == 2:
            self.header_action_btn.text = "Atualizar transações"
            self.header_action_btn.icon = ft.Icons.REPLAY
            self.header_action_btn.on_click = lambda _e: self._carregar_transacoes(reset=False)
        elif self._menu_idx == 3:
            self.header_action_btn.text = "Recarregar fontes"
            self.header_action_btn.icon = ft.Icons.DOWNLOAD_FOR_OFFLINE_OUTLINED
            self.header_action_btn.on_click = lambda _e: self._carregar_fontes_importacao()
        elif self._menu_idx == 4:
            self.header_action_btn.text = "Atualizar Planner"
            self.header_action_btn.icon = ft.Icons.REFRESH
            self.header_action_btn.on_click = lambda _e: self._carregar_planner()
        else:
            self.header_action_btn.text = "Sincronizar"
            self.header_action_btn.icon = ft.Icons.SYNC
            self.header_action_btn.on_click = lambda _e: None

        self.content_area.content = self._current_view()
        self.sidebar_holder.content = self._menu()
        self.page.update()

    def _montar_layout(self) -> None:
        self.sidebar_holder = ft.Container(content=self._menu())
        self.content_area = ft.Container(expand=True, padding=18, content=self._current_view())

        shell = ft.Row(
            expand=True,
            spacing=0,
            controls=[
                self.sidebar_holder,
                ft.Column(expand=True, spacing=0, controls=[self._header(), self.content_area]),
            ],
        )

        self.page.add(shell)

    def _carregar_dashboard(self) -> None:
        hoje = dt.date.today()
        self.dashboard_status.value = "Sincronizando dados do dashboard..."
        self.dashboard_diag_status.value = "Ambiente: atualizando diagnóstico..."
        self.dashboard_diag_status.color = self._cor("muted")
        self.page.update()

        try:
            dados = self.api.resumo_dashboard(hoje.month, hoje.year)
        except Exception as exc:
            self.dashboard_status.value = self._mensagem_erro_api(exc, "Falha ao carregar dashboard")
            self.dashboard_status.color = self._cor("danger")
            self.categorias_col.controls.clear()
            self.categorias_col.controls.append(
                ft.Text(
                    "Backend indisponível. Inicie a API e clique em Atualizar.",
                    color=self._cor("warning"),
                )
            )
            self.page.update()
            return

        receitas = float(dados.get("total_receitas", 0.0) or 0.0)
        despesas = float(dados.get("total_despesas", 0.0) or 0.0)
        saldo = float(dados.get("saldo_mensal", 0.0) or 0.0)
        total = int(dados.get("total_transacoes", 0) or 0)

        self.lbl_receitas.value = _currency_br(receitas)
        self.lbl_despesas.value = _currency_br(despesas)
        self.lbl_saldo.value = _currency_br(saldo)
        self.lbl_saldo.color = self._cor("ok") if saldo >= 0 else self._cor("danger")
        self.lbl_total.value = str(total)
        self.lbl_ref.value = str(dados.get("mes_referencia") or f"{hoje.month:02d}/{hoje.year}")

        categorias = dados.get("categorias_gastos") or []
        self.categorias_col.controls.clear()
        for item in categorias[:6]:
            nome = str(item.get("categoria") or "Outros")
            valor = float(item.get("valor", 0.0) or 0.0)
            percentual = float(item.get("percentual", 0.0) or 0.0)
            self.categorias_col.controls.append(
                ft.Container(
                    border_radius=12,
                    bgcolor=self._cor("panel_alt"),
                    padding=10,
                    border=ft.border.all(1, self._cor("border_alt")),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(nome, weight=ft.FontWeight.W_500),
                            ft.Text(f"{_currency_br(valor)}  -  {percentual:.1f}%", color=self._cor("muted")),
                        ],
                    ),
                )
            )

        if not categorias:
            self.categorias_col.controls.append(ft.Text("Sem gastos no período.", color=self._cor("muted")))

        try:
            diag = self.api.diagnostico_ambiente()
            self.dashboard_diag_payload = diag
            pendencias = diag.get("pendencias") or []
            if pendencias:
                self.dashboard_diag_status.value = "Ambiente: atenção necessária."
                self.dashboard_diag_status.color = self._cor("danger")
                self.dashboard_diag_pendencias.value = f"Pendências: {', '.join(pendencias)}"
                self.dashboard_diag_pendencias.color = self._cor("danger")
            else:
                self.dashboard_diag_status.value = "Ambiente: operacional."
                self.dashboard_diag_status.color = self._cor("ok")
                self.dashboard_diag_pendencias.value = "Pendências: nenhuma"
                self.dashboard_diag_pendencias.color = self._cor("ok")
        except Exception as exc:
            self.dashboard_diag_status.value = self._mensagem_erro_api(exc, "Ambiente: diagnóstico indisponível")
            self.dashboard_diag_status.color = self._cor("warning")
            self.dashboard_diag_pendencias.value = "Pendências: diagnóstico indisponível"
            self.dashboard_diag_pendencias.color = self._cor("warning")

        self.dashboard_status.value = "Dashboard atualizado."
        self.dashboard_status.color = self._cor("accent")
        self.page.update()

    def _on_enviar_pergunta(self, _e: ft.ControlEvent) -> None:
        pergunta = (self.inp_pergunta.value or "").strip()
        if not pergunta:
            return

        self.chat_list.controls.append(self._chat_bubble(pergunta, "user"))
        self.inp_pergunta.value = ""
        self.assistente_status.value = "Vorcaro está pensando..."
        self.assistente_status.color = self._cor("muted")
        self.page.update()

        try:
            payload = self.api.enviar_pergunta(pergunta)
            resposta = str(payload.get("resposta") or "Sem resposta.")
            provedor = str(payload.get("provedor") or "assistente")
        except Exception as exc:
            resposta = self._mensagem_erro_api(exc, "Erro ao consultar assistente")
            provedor = "erro"

        self.chat_list.controls.append(self._chat_bubble(resposta, "bot"))
        self.assistente_status.value = f"Resposta via: {provedor}"
        self.assistente_status.color = self._cor("accent") if provedor != "erro" else self._cor("danger")
        self.page.update()

    def _meme_financeiro_aleatorio(self) -> str:
        if not self._memes_rotacao:
            self._memes_rotacao = list(_MEMES_FINANCEIROS)
            random.shuffle(self._memes_rotacao)
            if (
                self._ultimo_meme
                and len(self._memes_rotacao) > 1
                and self._memes_rotacao[0] == self._ultimo_meme
            ):
                self._memes_rotacao.append(self._memes_rotacao.pop(0))

        meme = self._memes_rotacao.pop(0)
        self._ultimo_meme = meme
        return f"Meme financeiro do dia:\n\n{meme}"

    def _piada_financeira_aleatoria(self) -> str:
        if not self._piadas_rotacao:
            self._piadas_rotacao = list(_PIADAS_FINANCEIRAS)
            random.shuffle(self._piadas_rotacao)
            if (
                self._ultima_piada
                and len(self._piadas_rotacao) > 1
                and self._piadas_rotacao[0] == self._ultima_piada
            ):
                self._piadas_rotacao.append(self._piadas_rotacao.pop(0))

        piada = self._piadas_rotacao.pop(0)
        self._ultima_piada = piada
        return f"Piada financeira do momento:\n\n{piada}"

    def _humor_aleatorio(self) -> str:
        if random.random() < 0.5:
            base = self._meme_financeiro_aleatorio()
        else:
            base = self._piada_financeira_aleatoria()
        return self._talvez_anexar_sarcasmo(base)

    def _iniciar_humor_automatico(self) -> None:
        if not self._humor_auto_habilitado or self._humor_auto_task_iniciada:
            return
        self._humor_auto_task_iniciada = True
        self.page.run_task(self._loop_humor_automatico)

    async def _loop_humor_automatico(self) -> None:
        while True:
            await asyncio.sleep(random.randint(self._humor_auto_min_s, self._humor_auto_max_s))
            if random.random() > self._humor_auto_chance:
                continue

            chamada = random.choice(
                [
                    "ATENCAO: pausa oficial para zoeira financeira.",
                    "ALERTA DE HUMOR: sistema detectou excesso de seriedade.",
                    "BREAKING NEWS: sua fatura pediu um intervalo com piada.",
                    "MODO DISTRAIR LIGADO: recarregando seu cerebro com sarcasmo.",
                ]
            )
            texto = f"{chamada}\n\n{self._humor_aleatorio()}"
            self.chat_list.controls.append(self._chat_bubble(texto, "bot"))
            self.assistente_status.value = "ATENCAO: caiu um meme/piada automatico no chat."
            self.assistente_status.color = self._cor("warning")
            self.page.update()

    def _comentario_sarcastico_aleatorio(self) -> str:
        abertura = random.choice(_SARCASMO_ABERTURA)
        meio = random.choice(_SARCASMO_MEIO)
        fim = random.choice(_SARCASMO_FIM)
        return f"{abertura}\n{meio}, {fim}"

    def _talvez_anexar_sarcasmo(self, texto: str) -> str:
        if random.random() > self._sarcasmo_chance:
            return texto
        return f"{texto}\n\n{self._comentario_sarcastico_aleatorio()}"

    def _on_enviar_meme(self, _e: ft.ControlEvent) -> None:
        texto = self._talvez_anexar_sarcasmo(self._meme_financeiro_aleatorio())
        self.chat_list.controls.append(self._chat_bubble(texto, "bot"))
        self.assistente_status.value = "Modo zoeira ativado."
        self.assistente_status.color = self._cor("accent")
        self.page.update()

    def _on_enviar_piada(self, _e: ft.ControlEvent) -> None:
        texto = self._talvez_anexar_sarcasmo(self._piada_financeira_aleatoria())
        self.chat_list.controls.append(self._chat_bubble(texto, "bot"))
        self.assistente_status.value = "Modo stand-up financeiro ativado."
        self.assistente_status.color = self._cor("accent")
        self.page.update()


def main(page: ft.Page) -> None:
    VorcaroFletApp(page)


