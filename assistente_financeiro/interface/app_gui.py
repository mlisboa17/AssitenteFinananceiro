"""
Interface Gráfica do Assistente Financeiro Pessoal.

UI moderna e leve construída com CustomTkinter.
Usa o backend local para operações e respostas do assistente.

Layout:
  ┌────────────┬──────────────────────────────────────┐
  │  Sidebar   │         Área de Conteúdo              │
  │            │                                       │
  │ 🏠 Dashboard│  [Frames dinâmicos por seção]         │
  │ 💰 Transações│                                     │
  │ 📤 Importar │                                      │
  │ 🎯 Metas   │                                       │
  │ 💸 Orçamento│                                      │
  │ 📊 Relatórios│                                     │
  │ 🤖 Assistente│                                     │
  │ ⚙️ Config  │                                       │
  └────────────┴──────────────────────────────────────┘

Requisito: pip install customtkinter matplotlib
"""

import sys
import os
import asyncio
import threading
import heapq
import time
import logging
import random
from itertools import count
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import requests

# Garante que o pacote 'app' seja encontrado ao rodar a interface diretamente
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox
import tkinter as tk

try:
    from CTkMessagebox import CTkMessagebox  # type: ignore
except Exception:
    CTkMessagebox = None

# ================================================
# Configuração visual global
# ================================================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Paleta de cores
COR_PRIMARIA    = "#14B8A6"
COR_SECUNDARIA  = "#1C2A43"
COR_SIDEBAR     = "#0D1629"
COR_FUNDO       = "#090F1D"
COR_CARD        = "#121C31"
COR_CARD_ALT    = "#0F1A2E"
COR_SUCESSO     = "#22C55E"
COR_PERIGO      = "#F87171"
COR_AVISO       = "#FBBF24"
COR_TEXTO       = "#E6EDF7"
COR_TEXTO_SUAVE = "#9FB3C8"
COR_BORDA       = "#263A5A"
COR_DESTAQUE    = "#38BDF8"
COR_ACENTO      = "#8B5CF6"
COR_PRIMARIA_HOVER = "#0D9488"
COR_SCROLL      = "#27456B"
COR_SCROLL_HOVER = "#315A8A"


logger = logging.getLogger(__name__)


_MEMES_GUI_TEMPLATES = [
    "Saldo em {saldo} e eu aqui fingindo que o carrinho online nao existe.",
    "Receitas de {receitas}, despesas de {despesas}: a batalha mensal segue intensa.",
    "Com {transacoes} transacoes no periodo, ja da pra abrir uma serie documental.",
    "Despesas em {despesas}: oficialmente no modo 'foi so um cafezinho'.",
    "Saldo atual {saldo}. O coracao agradece, o cartao discorda.",
    "Receitas {receitas} versus despesas {despesas}: quem venceu hoje foi a realidade.",
    "Com {transacoes} lancamentos, o extrato esta mais movimentado que agenda de feriado.",
    "Saldo {saldo} nunca foi tanto ate o dia em que descobri que 'impulsivo' e meu melhor coach.",
    "Transacoes registradas: {transacoes}. Remorso registrado: infinito.",
    "Receitas {receitas}, despesas {despesas}. A diferenca e so um numero tentando enganar meu coracao.",
    "Com saldo de {saldo}, tenho 2 opcoes: economia criativa ou ignorancia financeira bliss.",
    "{transacoes} movimentacoes este mes. Se fosse um videoclipe, seria uma tragedia em 4K.",
    "Despesas chegaram em {despesas}. Os boletos chegam toda segunda rindo da minha cara.",
    "Receitas em {receitas}. Que pena que a fatura do mes eh um numero maior (spoiler: nao eh verdade).",
    "Saldo positivo de {saldo}? Aproveita que quando acordar mudou novamente.",
]


def _habilitar_dialogos_modernos() -> None:
    """Substitui tkinter.messagebox por CTkMessagebox quando disponível.

    Mantém a assinatura básica usada no projeto e cai para o comportamento
    padrão caso a biblioteca não esteja instalada.
    """
    if CTkMessagebox is None:
        return

    _tk_showinfo = messagebox.showinfo
    _tk_showwarning = messagebox.showwarning
    _tk_showerror = messagebox.showerror
    _tk_askyesno = messagebox.askyesno

    def _showinfo(title, msg, **kwargs):
        try:
            CTkMessagebox(title=str(title), message=str(msg), icon="info", option_1="OK")
            return "ok"
        except Exception:
            return _tk_showinfo(title, msg, **kwargs)

    def _showwarning(title, msg, **kwargs):
        try:
            CTkMessagebox(title=str(title), message=str(msg), icon="warning", option_1="OK")
            return "ok"
        except Exception:
            return _tk_showwarning(title, msg, **kwargs)

    def _showerror(title, msg, **kwargs):
        try:
            CTkMessagebox(title=str(title), message=str(msg), icon="cancel", option_1="OK")
            return "ok"
        except Exception:
            return _tk_showerror(title, msg, **kwargs)

    def _askyesno(title, msg, **kwargs):
        try:
            dlg = CTkMessagebox(
                title=str(title),
                message=str(msg),
                icon="question",
                option_1="Não",
                option_2="Sim",
            )
            return str(dlg.get()).strip().lower() == "sim"
        except Exception:
            return _tk_askyesno(title, msg, **kwargs)

    messagebox.showinfo = _showinfo
    messagebox.showwarning = _showwarning
    messagebox.showerror = _showerror
    messagebox.askyesno = _askyesno


_habilitar_dialogos_modernos()


_UI_HEAP_LOCK = threading.Lock()
_UI_HEAP = []
_UI_SEQ = count()
_UI_ROOT = None
_LOGO_CACHE: Dict[tuple[int, int], Optional[ctk.CTkImage]] = {}


def _resolver_logo_sistema() -> Optional[str]:
    """Resolve caminho do símbolo principal do sistema.

    Ordem de busca:
    1) Variáveis de ambiente SISTEMA_LOGO_PATH/LOGO_SISTEMA_PATH
    2) Pastas assets comuns dentro do projeto
    3) Sem fallback automático em uploads para evitar usar fotos erradas
    """
    base_dir = Path(__file__).resolve().parents[1]          # assistente_financeiro/
    workspace_dir = base_dir.parent                          # raiz do workspace

    env_candidates = [
        os.getenv("SISTEMA_LOGO_PATH", "").strip(),
        os.getenv("LOGO_SISTEMA_PATH", "").strip(),
    ]
    for raw in env_candidates:
        if not raw:
            continue
        p = Path(raw)
        if not p.is_absolute():
            p = workspace_dir / p
        if p.exists() and p.is_file():
            return str(p)

    common_candidates = [
        base_dir / "assets" / "logo_sistema.png",
        base_dir / "assets" / "logo_sistema.jpg",
        base_dir / "assets" / "logo_sistema.jpeg",
        base_dir / "assets" / "logo_sistema.webp",
        base_dir / "assets" / "logo.png",
        base_dir / "assets" / "logos.png",
        base_dir / "interface" / "assets" / "logo_sistema.png",
        base_dir / "interface" / "assets" / "logo.png",
        workspace_dir / "assets" / "logo_sistema.png",
        workspace_dir / "assets" / "logo.png",
    ]
    for p in common_candidates:
        if p.exists() and p.is_file():
            return str(p)

    return None


def _carregar_logo_ctk(size: tuple[int, int]) -> Optional[ctk.CTkImage]:
    """Carrega logo como CTkImage com cache; retorna None se indisponível."""
    if size in _LOGO_CACHE:
        return _LOGO_CACHE[size]

    caminho = _resolver_logo_sistema()
    if not caminho:
        _LOGO_CACHE[size] = None
        return None

    try:
        from PIL import Image

        img = Image.open(caminho)
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
        _LOGO_CACHE[size] = ctk_img
        return ctk_img
    except Exception:
        logger.exception("Não foi possível carregar logo do sistema em %s", caminho)
        _LOGO_CACHE[size] = None
        return None


def _criar_marca_logos(parent, *, compacto: bool = False, bg: Optional[str] = None):
    """Desenha uma marca vetorial simples do LOGOS como fallback visual."""
    fundo = bg or COR_SIDEBAR
    frame = ctk.CTkFrame(parent, fg_color="transparent")

    if compacto:
        canvas = tk.Canvas(frame, width=54, height=28, bg=fundo, highlightthickness=0, bd=0)
        canvas.pack(side="left")
        canvas.create_line(6, 15, 26, 5, 48, 15, smooth=True, width=2, fill="#6EE7F9")
        canvas.create_line(6, 15, 26, 24, 48, 15, smooth=True, width=2, fill="#38BDF8")
        canvas.create_oval(22, 11, 30, 19, outline="#A78BFA", width=2)
        canvas.create_oval(24, 13, 28, 17, fill="#38BDF8", outline="#38BDF8")
        ctk.CTkLabel(frame, text="LOGOS", font=ctk.CTkFont(size=11, weight="bold"), text_color=COR_TEXTO).pack(side="left", padx=(6, 0))
        return frame

    canvas = tk.Canvas(frame, width=190, height=130, bg=fundo, highlightthickness=0, bd=0)
    canvas.pack()
    canvas.create_line(18, 48, 78, 16, 150, 36, smooth=True, width=5, fill="#6EE7F9")
    canvas.create_line(22, 54, 84, 86, 156, 60, smooth=True, width=5, fill="#38BDF8")
    canvas.create_arc(56, 28, 124, 88, start=200, extent=320, style="arc", outline="#A78BFA", width=4)
    canvas.create_oval(74, 40, 106, 72, outline="#6EE7F9", width=3)
    canvas.create_oval(84, 50, 96, 62, fill="#38BDF8", outline="#38BDF8")
    canvas.create_text(95, 98, text="LOGOS", fill="#E5E7EB", font=("Segoe UI", 24, "bold"))
    canvas.create_text(95, 118, text="ECOSSISTEMA DE INTELIGÊNCIA", fill="#94A3B8", font=("Segoe UI", 9, "bold"))
    return frame


def _registrar_dispatch_ui(root):
    """Registra a janela raiz para executar callbacks de UI na main thread."""
    global _UI_ROOT
    _UI_ROOT = root
    _bombear_dispatch_ui()


def _widget_existe(widget) -> bool:
    try:
        return bool(widget.winfo_exists())
    except Exception:
        return False


def _bombear_dispatch_ui():
    """Executa callbacks pendentes da fila de UI (sempre na thread principal)."""
    root = _UI_ROOT
    if not _widget_existe(root):
        return

    agora = time.monotonic()
    callbacks = []
    with _UI_HEAP_LOCK:
        while _UI_HEAP and _UI_HEAP[0][0] <= agora:
            _, _, widget, callback = heapq.heappop(_UI_HEAP)
            callbacks.append((widget, callback))

    for widget, callback in callbacks:
        if not _widget_existe(widget):
            continue
        try:
            callback()
        except tk.TclError:
            pass
        except Exception:
            logger.exception("Erro em callback de UI agendado")

    try:
        root.after(30, _bombear_dispatch_ui)
    except (tk.TclError, RuntimeError):
        pass


def _after_seguro(widget, delay_ms: int, callback):
    def _wrapped():
        if not _widget_existe(widget):
            return
        try:
            callback()
        except tk.TclError:
            pass

    # Chamada na main thread: usa after normal.
    if threading.current_thread() is threading.main_thread():
        try:
            widget.after(delay_ms, _wrapped)
        except (tk.TclError, RuntimeError):
            pass
        return

    # Chamada em thread de background: agenda em fila para o loop principal.
    executar_em = time.monotonic() + max(delay_ms, 0) / 1000.0
    with _UI_HEAP_LOCK:
        heapq.heappush(_UI_HEAP, (executar_em, next(_UI_SEQ), widget, _wrapped))



# ================================================
# Utilitário: persistência do arquivo .env
# ================================================

def _salvar_env_key(env_path: str, chave: str, valor: str):
    """
    Insere ou atualiza uma variável no arquivo .env do projeto.
    Cria o arquivo se não existir.
    """
    linhas: list[str] = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            linhas = f.readlines()

    encontrou = False
    for i, linha in enumerate(linhas):
        if linha.startswith(f"{chave}=") or linha.startswith(f"{chave} ="):
            linhas[i] = f"{chave}={valor}\n"
            encontrou = True
            break

    if not encontrou:
        linhas.append(f"{chave}={valor}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(linhas)


# ================================================
# Classe principal da aplicação
# ================================================

class AssistenteFinanceiroApp(ctk.CTk):
    """
    Janela principal do Assistente Financeiro Pessoal.
    Gerencia a navegação entre seções e o ciclo de vida da aplicação.
    """

    def __init__(self):
        super().__init__()

        screen_w = int(self.winfo_screenwidth() or 1366)
        screen_h = int(self.winfo_screenheight() or 768)
        self._ui_compacto = screen_w < 1520 or screen_h < 900
        self._sidebar_width = 200 if self._ui_compacto else 236

        # Em monitores menores, reduz escala para evitar cortes sem perder legibilidade.
        if screen_h < 760:
            ctk.set_widget_scaling(0.90)
        elif screen_h < 900:
            ctk.set_widget_scaling(0.95)

        _registrar_dispatch_ui(self)
        self.logo_path = _resolver_logo_sistema()
        self._logo_sidebar = _carregar_logo_ctk((118, 68) if self._ui_compacto else (146, 84))
        self._logo_topbar = _carregar_logo_ctk((30, 20) if self._ui_compacto else (36, 24))

        self.title("💰 Vorcaro")
        largura = min(1280, max(980, int(screen_w * 0.90)))
        altura = min(820, max(620, int(screen_h * 0.88)))
        pos_x = max(0, (screen_w - largura) // 2)
        pos_y = max(0, (screen_h - altura) // 2)
        self.geometry(f"{largura}x{altura}+{pos_x}+{pos_y}")
        self.minsize(860 if self._ui_compacto else 980, 560 if self._ui_compacto else 640)

        # Inicializa banco de dados
        self._inicializar_db()

        # Frame atual
        self._frame_atual: Optional[ctk.CTkFrame] = None
        self._botoes_nav  = {}
        self._memes_gui_pool: List[str] = []
        self._ultimo_meme_gui: Optional[str] = None

        # Constrói layout principal
        self._construir_layout()

        # Mostra dashboard
        self._navegar("dashboard")

        # Manipula fechamento
        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)

    # --------------------------------------------------
    # Inicialização
    # --------------------------------------------------

    def _inicializar_db(self):
        """Cria tabelas e sessão do banco."""
        try:
            from app.database import criar_tabelas, SessionLocal
            criar_tabelas()
            self.SessionLocal = SessionLocal
        except Exception as e:
            messagebox.showerror("Erro de Banco", f"Erro ao inicializar banco de dados:\n{e}")
            sys.exit(1)

    def _obter_db(self):
        """Retorna uma nova sessão do banco de dados."""
        return self.SessionLocal()

    # --------------------------------------------------
    # Layout estrutural
    # --------------------------------------------------

    def _construir_layout(self):
        """Constrói a estrutura principal: sidebar + área de conteúdo."""
        self.configure(fg_color=COR_FUNDO)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(
            self,
            width=self._sidebar_width,
            fg_color=COR_SIDEBAR,
            corner_radius=0,
            border_width=1,
            border_color=COR_BORDA,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self._construir_sidebar()

        # Área de conteúdo
        self.area_conteudo = ctk.CTkFrame(self, fg_color=COR_FUNDO, corner_radius=0)
        self.area_conteudo.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.area_conteudo.grid_columnconfigure(0, weight=1)
        self.area_conteudo.grid_rowconfigure(1, weight=1)

        topbar = ctk.CTkFrame(
            self.area_conteudo,
            fg_color=COR_CARD_ALT,
            height=44 if self._ui_compacto else 50,
            corner_radius=0,
            border_width=1,
            border_color=COR_BORDA,
        )
        topbar.grid(row=0, column=0, sticky="ew")
        topbar.grid_columnconfigure(1, weight=1)

        if self._logo_topbar is not None:
            ctk.CTkLabel(topbar, text="", image=self._logo_topbar).grid(row=0, column=0, padx=(12, 8), pady=7, sticky="w")
        else:
            _criar_marca_logos(topbar, compacto=True, bg=COR_CARD_ALT).grid(row=0, column=0, padx=(12, 8), pady=7, sticky="w")

        ctk.CTkLabel(
            topbar,
            text="LOGOS • Ecossistema de Inteligência",
            font=ctk.CTkFont(family="Segoe UI", size=12 if self._ui_compacto else 13, weight="bold"),
            text_color=COR_TEXTO,
        ).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            topbar,
            text="Subsistema ativo: Vorcaro",
            font=ctk.CTkFont(family="Segoe UI", size=10 if self._ui_compacto else 11),
            text_color=COR_DESTAQUE,
        ).grid(row=0, column=2, padx=(8, 12), sticky="e")

    def _construir_sidebar(self):
        """Constrói a barra lateral com logo e navegação."""
        # Logo / Título
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(pady=(10, 4), padx=10, fill="x")

        if self._logo_sidebar is not None:
            ctk.CTkLabel(logo_frame, text="", image=self._logo_sidebar).pack(pady=(0, 4))
        else:
            _criar_marca_logos(logo_frame, compacto=False, bg=COR_SIDEBAR).pack(pady=(0, 2))

        ctk.CTkLabel(
            logo_frame, text="Ecossistema Principal",
            font=ctk.CTkFont(size=10 if self._ui_compacto else 11, weight="bold"),
            text_color=COR_DESTAQUE,
        ).pack()
        ctk.CTkLabel(
            logo_frame, text="Vorcaro",
            font=ctk.CTkFont(size=13 if self._ui_compacto else 14, weight="bold"),
            text_color=COR_TEXTO,
        ).pack()
        ctk.CTkLabel(
            logo_frame, text="Inteligência financeira para decidir melhor.",
            font=ctk.CTkFont(size=10 if self._ui_compacto else 11),
            text_color=COR_TEXTO_SUAVE,
        ).pack(pady=(2, 0))

        ctk.CTkFrame(self.sidebar, height=1, fg_color=COR_BORDA).pack(fill="x", padx=12, pady=8)

        # Botão rápido de despesa
        ctk.CTkButton(
            self.sidebar,
            text="➕  Nova Despesa",
            fg_color=COR_SUCESSO,
            hover_color="#16A34A",
            font=ctk.CTkFont(size=11 if self._ui_compacto else 12, weight="bold"),
            command=self._dialog_nova_despesa,
            corner_radius=8,
            height=32 if self._ui_compacto else 36,
        ).pack(padx=12, pady=(0, 10), fill="x")

        nav_container = ctk.CTkScrollableFrame(
            self.sidebar,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=COR_SCROLL,
            scrollbar_button_hover_color=COR_SCROLL_HOVER,
        )
        nav_container.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        # Itens de navegação
        itens_nav = [
            ("dashboard",          "🏠  Dashboard"),
            ("transacoes",         "💳  Transações"),
            ("importar",           "📤  Importar"),
            ("fatura_cartao",      "💳  Fatura Cartão"),
            ("categorias",         "🏷️  Categorias"),
            ("metas",              "🎯  Metas"),
            ("orcamentos",         "💸  Orçamentos"),
            ("agenda_financeira",  "📅  Agenda Financeira"),
            ("agenda_compromissos","🗓️  Compromissos"),
            ("planner",            "📋  Planner"),
            ("relatorios",         "📊  Relatórios"),
            ("assistente",         "🤖  Vorcaro"),
            ("configuracoes",      "⚙️  Configurações"),
        ]

        for chave, texto in itens_nav:
            btn = ctk.CTkButton(
                nav_container,
                text=texto,
                fg_color="transparent",
                text_color=COR_TEXTO_SUAVE,
                hover_color=COR_SECUNDARIA,
                anchor="w",
                font=ctk.CTkFont(size=11 if self._ui_compacto else 12, weight="bold"),
                corner_radius=8,
                height=28 if self._ui_compacto else 32,
                command=lambda c=chave: self._navegar(c),
            )
            btn.pack(padx=4, pady=2, fill="x")
            self._botoes_nav[chave] = btn

        # Rodapé sidebar
        ctk.CTkFrame(self.sidebar, height=1, fg_color=COR_BORDA).pack(
            fill="x", padx=12, pady=8, side="bottom"
        )
        ctk.CTkLabel(
            self.sidebar,
            text="LOGOS Platform • v1.0.0",
            font=ctk.CTkFont(size=9 if self._ui_compacto else 10),
            text_color=COR_TEXTO_SUAVE,
        ).pack(side="bottom", pady=4)

    # --------------------------------------------------
    # Navegação
    # --------------------------------------------------

    def _navegar(self, secao: str):
        """Navega para a seção indicada."""
        # Remove frame atual
        if self._frame_atual:
            self._frame_atual.destroy()

        # Reseta destaque dos botões
        for chave, btn in self._botoes_nav.items():
            if chave == secao:
                btn.configure(fg_color=COR_PRIMARIA, hover_color=COR_PRIMARIA_HOVER, text_color="#F8FAFC")
            else:
                btn.configure(fg_color="transparent", text_color=COR_TEXTO_SUAVE)

        # Cria novo frame
        mapa = {
            "dashboard":           DashboardFrame,
            "transacoes":          TransacoesFrame,
            "importar":            ImportarFrame,
            "fatura_cartao":       FaturaCartaoFrame,
            "categorias":          CategoriasFrame,
            "metas":               MetasFrame,
            "orcamentos":          OrcamentosFrame,
            "agenda_financeira":   AgendaFinanceiraFrame,
            "agenda_compromissos": AgendaCompromissosFrame,
            "planner":             PlannerFrame,
            "relatorios":          RelatoriosFrame,
            "assistente":          AssistenteFrame,
            "configuracoes":       ConfiguracoesFrame,
        }
        FrameClass = mapa.get(secao, DashboardFrame)
        self._frame_atual = FrameClass(self.area_conteudo, self)
        self._frame_atual.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=12 if self._ui_compacto else 16,
            pady=10 if self._ui_compacto else 14,
        )

        if hasattr(self._frame_atual, "receber_meme_automatico"):
            try:
                self._frame_atual.receber_meme_automatico()
            except Exception:
                logger.exception("Falha ao atualizar meme automatico na troca de tela.")

    def proximo_meme_gui(self, contexto: Optional[Dict[str, Any]] = None) -> str:
        """Retorna um meme em rotação aleatória para uso na GUI."""
        if not self._memes_gui_pool:
            self._memes_gui_pool = list(_MEMES_GUI_TEMPLATES)
            random.shuffle(self._memes_gui_pool)
            if (
                self._ultimo_meme_gui
                and len(self._memes_gui_pool) > 1
                and self._memes_gui_pool[0] == self._ultimo_meme_gui
            ):
                self._memes_gui_pool.append(self._memes_gui_pool.pop(0))

        template = self._memes_gui_pool.pop(0)
        self._ultimo_meme_gui = template

        ctx = contexto or {}
        return template.format(
            receitas=str(ctx.get("receitas", "R$ 0,00")),
            despesas=str(ctx.get("despesas", "R$ 0,00")),
            saldo=str(ctx.get("saldo", "R$ 0,00")),
            transacoes=str(ctx.get("transacoes", "0")),
        )

    # --------------------------------------------------
    # Dialog de nova despesa rápida
    # --------------------------------------------------

    def _dialog_nova_despesa(self):
        """Abre dialog para registro rápido de despesa (com opção recorrente)."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Nova Despesa")
        dialog.geometry("400x440")
        dialog.resizable(False, False)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="💳 Registrar Despesa",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 10))

        frame = ctk.CTkFrame(dialog, fg_color="transparent")
        frame.pack(padx=20, fill="x")

        def _lbl(txt):
            ctk.CTkLabel(frame, text=txt, text_color=COR_TEXTO_SUAVE,
                         font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(8,2))

        _lbl("Valor (R$):")
        entry_valor = ctk.CTkEntry(frame, placeholder_text="Ex: 45.90")
        entry_valor.pack(fill="x")

        _lbl("Descrição:")
        entry_desc = ctk.CTkEntry(frame, placeholder_text="Ex: Supermercado Extra")
        entry_desc.pack(fill="x")

        _lbl("Categoria (opcional):")
        entry_cat = ctk.CTkEntry(frame, placeholder_text="Ex: Alimentação")
        entry_cat.pack(fill="x")

        _lbl("Data (padrão: hoje):")
        entry_data = ctk.CTkEntry(frame, placeholder_text="DD/MM/AAAA")
        entry_data.pack(fill="x")
        _aplicar_mascara_data(entry_data)

        # ── Opção recorrente ──
        rec_var = ctk.BooleanVar(value=False)
        rec_frame = ctk.CTkFrame(frame, fg_color="transparent")
        rec_frame.pack(fill="x", pady=(10, 0))
        ctk.CTkCheckBox(rec_frame, text="Lançamento recorrente (todo mês)",
                        variable=rec_var, text_color=COR_TEXTO).pack(side="left")

        def salvar():
            # ── Validação ──
            valor_raw = entry_valor.get().strip().replace(",", ".")
            desc      = entry_desc.get().strip()
            cat       = entry_cat.get().strip() or None
            data_txt  = entry_data.get().strip()

            if not valor_raw:
                messagebox.showwarning("Atenção", "Informe o valor.", parent=dialog)
                return
            try:
                valor = float(valor_raw)
            except ValueError:
                messagebox.showwarning("Atenção", "Valor inválido. Use formato: 45.90", parent=dialog)
                return

            if not desc:
                messagebox.showwarning("Atenção", "Informe a descrição.", parent=dialog)
                return

            if data_txt:
                try:
                    dd, mm, aaaa = data_txt.split("/")
                    t_data = date(int(aaaa), int(mm), int(dd))
                except Exception:
                    messagebox.showwarning("Atenção", "Data inválida. Use DD/MM/AAAA.", parent=dialog)
                    return
            else:
                t_data = date.today()

            # ── Persistência ──
            db = self._obter_db()
            try:
                from app.models import Transacao, Categoria
                from app.services.classifier_service import ClassifierService

                t = Transacao(
                    data=t_data, descricao=desc,
                    valor=valor, tipo="debito", fonte="manual"
                )
                if cat:
                    c = db.query(Categoria).filter(Categoria.nome.ilike(f"%{cat}%")).first()
                    if c:
                        t.categoria_id = c.id
                    else:
                        ClassifierService(db).classificar_e_aplicar(t)
                else:
                    ClassifierService(db).classificar_e_aplicar(t)

                db.add(t)

                # Se recorrente → adiciona EventoFinanceiro na mesma sessão
                if rec_var.get():
                    from app.models import EventoFinanceiro
                    ev = EventoFinanceiro(
                        titulo          = desc,
                        valor           = valor,
                        data_vencimento = t_data,
                        tipo            = "conta",
                        recorrente      = True,
                        dia_recorrencia = t_data.day,
                        descricao       = f"Despesa recorrente registrada em {date.today().strftime('%d/%m/%Y')}",
                    )
                    db.add(ev)

                db.commit()

                msg = f"Despesa '{desc}' registrada com sucesso!"
                if rec_var.get():
                    msg += "\n📅 Evento recorrente salvo na Agenda Financeira."
                messagebox.showinfo("✅ Sucesso", msg, parent=dialog)
                dialog.destroy()
                if hasattr(self._frame_atual, "carregar_dados"):
                    self._frame_atual.carregar_dados()

            except Exception as ex:
                db.rollback()
                messagebox.showerror("Erro ao Salvar", str(ex), parent=dialog)
            finally:
                db.close()

        ctk.CTkButton(dialog, text="💾 Salvar", command=salvar,
                      fg_color=COR_SUCESSO, hover_color="#1E8449").pack(pady=14, padx=20, fill="x")

    def _ao_fechar(self):
        """Trata o evento de fechar a janela."""
        self.quit()
        self.destroy()


# ================================================
# Frame: Dashboard
# ================================================

class DashboardFrame(ctk.CTkScrollableFrame):
    """Painel principal com resumo financeiro e gráficos."""

    def __init__(self, parent, app: AssistenteFinanceiroApp):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)

        hoje = date.today()
        self.mes = hoje.month
        self.ano = hoje.year

        self._construir_ui()
        self.carregar_dados()

    def _construir_ui(self):
        hoje  = date.today()
        hora  = datetime.now().hour
        saud  = "☀️ Bom dia" if hora < 12 else ("🌤️ Boa tarde" if hora < 18 else "🌙 Boa noite")
        _ml   = ["","Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                 "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
        hoje_fmt = f"{hoje.day} de {_ml[hoje.month]} de {hoje.year}"

        # ── Banda superior: saudação + seletor de período ─────────────
        topo = ctk.CTkFrame(self, fg_color=COR_CARD_ALT, corner_radius=14, border_width=1, border_color=COR_BORDA)
        topo.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        topo.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            topo,
            text="LOGOS  ➜  Vorcaro",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COR_DESTAQUE,
        ).grid(row=0, column=0, padx=18, pady=(8, 0), sticky="w")

        ctk.CTkLabel(
            topo,
            text=f"{saud}  •  {hoje_fmt}",
            font=ctk.CTkFont(size=13),
            text_color=COR_TEXTO_SUAVE,
        ).grid(row=1, column=0, padx=18, pady=(2, 12), sticky="w")

        nav = ctk.CTkFrame(topo, fg_color="transparent")
        nav.grid(row=0, column=1, rowspan=2, padx=12, sticky="e")
        ctk.CTkButton(nav, text="◀", width=32, height=28,
                      fg_color=COR_SECUNDARIA, hover_color=COR_PRIMARIA_HOVER,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._mes_anterior).pack(side="left", padx=2)
        self.lbl_periodo = ctk.CTkLabel(
            nav, text="",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COR_TEXTO, width=160,
        )
        self.lbl_periodo.pack(side="left", padx=8)
        ctk.CTkButton(nav, text="▶", width=32, height=28,
                      fg_color=COR_SECUNDARIA, hover_color=COR_PRIMARIA_HOVER,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._mes_proximo).pack(side="left", padx=2)

        # ── Subtítulo ─────────────────────────────────────────────────
        ctk.CTkLabel(
            self, text="📊  Resumo do Período",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COR_TEXTO_SUAVE,
        ).grid(row=1, column=0, sticky="w", pady=(0, 6))

        # ── Cards de resumo ───────────────────────────────────────────
        self.frame_cards = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_cards.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        if self.app._ui_compacto:
            for i in range(3):
                self.frame_cards.grid_columnconfigure(i, weight=1)

            self.card_receitas    = self._criar_card(self.frame_cards, "Receitas",          "💵", "R$ 0,00", COR_SUCESSO, 0, 0)
            self.card_despesas    = self._criar_card(self.frame_cards, "Despesas",          "💸", "R$ 0,00", COR_PERIGO,  1, 0)
            self.card_saldo       = self._criar_card(self.frame_cards, "Saldo",             "💰", "R$ 0,00", COR_PRIMARIA,2, 0)
            self.card_transacoes  = self._criar_card(self.frame_cards, "Transações",        "📋", "0",       COR_AVISO,   0, 1)
            self.card_vencimentos = self._criar_card(self.frame_cards, "Próx. Vencimentos", "🗓️", "—",       COR_ACENTO,   1, 1)
        else:
            for i in range(5):
                self.frame_cards.grid_columnconfigure(i, weight=1)

            self.card_receitas    = self._criar_card(self.frame_cards, "Receitas",          "💵", "R$ 0,00", COR_SUCESSO, 0, 0)
            self.card_despesas    = self._criar_card(self.frame_cards, "Despesas",          "💸", "R$ 0,00", COR_PERIGO,  1, 0)
            self.card_saldo       = self._criar_card(self.frame_cards, "Saldo",             "💰", "R$ 0,00", COR_PRIMARIA,2, 0)
            self.card_transacoes  = self._criar_card(self.frame_cards, "Transações",        "📋", "0",       COR_AVISO,   3, 0)
            self.card_vencimentos = self._criar_card(self.frame_cards, "Próx. Vencimentos", "🗓️", "—",       COR_ACENTO,   4, 0)

        # ── Gráficos ──────────────────────────────────────────────────
        self.frame_vorcaro = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=14)
        self.frame_vorcaro.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        self.frame_vorcaro.grid_columnconfigure(0, weight=1)
        self.frame_vorcaro.grid_columnconfigure(1, weight=0)

        bloco_texto = ctk.CTkFrame(self.frame_vorcaro, fg_color="transparent")
        bloco_texto.grid(row=0, column=0, sticky="ew", padx=14, pady=12)
        bloco_texto.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            bloco_texto,
            text="🧠 Radar Vorcaro",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COR_TEXTO,
        ).grid(row=0, column=0, sticky="w")

        self.lbl_vorcaro_status = ctk.CTkLabel(
            bloco_texto,
            text="Status: analisando seu mês...",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COR_PRIMARIA,
        )
        self.lbl_vorcaro_status.grid(row=1, column=0, sticky="w", pady=(3, 0))

        self.lbl_vorcaro_recomendacao = ctk.CTkLabel(
            bloco_texto,
            text="Em instantes vou trazer sua principal recomendação financeira.",
            font=ctk.CTkFont(size=11),
            text_color=COR_TEXTO_SUAVE,
            wraplength=520 if self.app._ui_compacto else 650,
            justify="left",
        )
        self.lbl_vorcaro_recomendacao.grid(row=2, column=0, sticky="w", pady=(4, 0))

        self.lbl_vorcaro_meme = ctk.CTkLabel(
            bloco_texto,
            text="😏 Meme do dia: carregando sarcasmo financeiro...",
            font=ctk.CTkFont(size=11),
            text_color=COR_AVISO,
            wraplength=520 if self.app._ui_compacto else 650,
            justify="left",
        )
        self.lbl_vorcaro_meme.grid(row=3, column=0, sticky="w", pady=(6, 0))

        bloco_acoes = ctk.CTkFrame(self.frame_vorcaro, fg_color="transparent")
        bloco_acoes.grid(row=0, column=1, sticky="e", padx=14, pady=10)
        ctk.CTkButton(
            bloco_acoes,
            text="Perguntar ao Vorcaro",
            height=30,
            fg_color=COR_PRIMARIA,
            hover_color=COR_PRIMARIA_HOVER,
            command=self._abrir_assistente,
        ).pack(pady=(0, 6), fill="x")
        ctk.CTkButton(
            bloco_acoes,
            text="Ver Relatórios",
            height=30,
            fg_color=COR_SECUNDARIA,
            hover_color=COR_PRIMARIA,
            command=lambda: self.app._navegar("relatorios"),
        ).pack(fill="x")

        self.frame_graficos = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_graficos.grid(row=4, column=0, sticky="nsew")
        self.frame_graficos.grid_columnconfigure(0, weight=1)
        self.frame_graficos.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # ── Insights ──────────────────────────────────────────────────
        self.frame_insights = ctk.CTkScrollableFrame(self, height=110, fg_color="transparent")
        self.frame_insights.grid(row=5, column=0, sticky="ew", pady=(12, 0))

    def _criar_card(self, parent, titulo, emoji, valor, cor, col, row=0):
        """Card visual com faixa colorida no topo, ícone, título e valor em destaque."""
        card = ctk.CTkFrame(parent, fg_color=COR_CARD, corner_radius=14)
        card.configure(border_width=1, border_color=COR_BORDA)
        card.grid(row=row, column=col, padx=5, pady=5, sticky="ew")

        # Faixa colorida no topo
        ctk.CTkFrame(card, fg_color=cor, height=5, corner_radius=0).pack(fill="x")

        # Ícone + título
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 0))
        ctk.CTkLabel(top, text=emoji, font=ctk.CTkFont(size=20)).pack(side="left")
        ctk.CTkLabel(
            top, text=titulo,
            font=ctk.CTkFont(size=11),
            text_color=COR_TEXTO_SUAVE,
        ).pack(side="left", padx=(6, 0))

        # Divisor
        ctk.CTkFrame(card, fg_color=COR_SECUNDARIA, height=1).pack(fill="x", padx=12, pady=(8, 0))

        # Valor em destaque
        lbl_valor = ctk.CTkLabel(
            card, text=valor,
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color=cor,
        )
        lbl_valor.pack(pady=(8, 14), padx=12, anchor="w")

        return lbl_valor

    def carregar_dados(self):
        """Carrega dados do dashboard de forma assíncrona."""
        _meses = ["","Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                  "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
        self.lbl_periodo.configure(text=f"{_meses[self.mes]}  /  {self.ano}")
        threading.Thread(target=self._carregar_async, daemon=True).start()

    def _carregar_async(self):
        db     = self.app._obter_db()
        n_venc = 0
        try:
            from app.services.insights_service import InsightsService
            from app.services.agenda_service   import listar_proximos_eventos
            dados    = InsightsService(db).resumo_dashboard(self.mes, self.ano)
            insights = InsightsService(db).gerar_insights(self.mes, self.ano)
            n_venc   = len(listar_proximos_eventos(db, dias=7))
        finally:
            db.close()

        _after_seguro(self, 0, lambda: self._atualizar_ui(dados, insights, n_venc))

    def _atualizar_ui(self, dados, insights, n_venc=0):
        if not _widget_existe(self):
            return

        from app.utils.helpers import formatar_moeda

        self.card_receitas.configure(text=formatar_moeda(dados["total_receitas"]))
        self.card_despesas.configure(text=formatar_moeda(dados["total_despesas"]))
        saldo = dados["saldo_mensal"]
        self.card_saldo.configure(
            text=formatar_moeda(saldo),
            text_color=COR_SUCESSO if saldo >= 0 else COR_PERIGO,
        )
        self.card_transacoes.configure(text=str(dados["total_transacoes"]))
        self.card_vencimentos.configure(
            text=f"{n_venc} pendente{'s' if n_venc != 1 else ''}",
            text_color=COR_PERIGO if n_venc > 0 else COR_ACENTO,
        )

        self._atualizar_radar_vorcaro(dados, insights, n_venc)
        self._atualizar_meme_dashboard(dados)

        # Gráficos
        self._renderizar_graficos(dados)

        # Insights como chips coloridos
        for w in self.frame_insights.winfo_children():
            w.destroy()

        if insights:
            ctk.CTkLabel(
                self.frame_insights,
                text="💡  Insights do período:",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COR_TEXTO,
            ).pack(anchor="w", pady=(0, 6))

        for insight in insights[:5]:
            cor   = {"alerta": COR_PERIGO, "aviso": COR_AVISO, "oportunidade": COR_SUCESSO}.get(insight["tipo"], COR_TEXTO)
            icone = {"alerta": "🚨", "aviso": "⚠️", "oportunidade": "✨", "info": "ℹ️"}.get(insight["tipo"], "•")
            chip  = ctk.CTkFrame(self.frame_insights, fg_color=COR_CARD, corner_radius=8)
            chip.pack(fill="x", pady=2, padx=2)
            ctk.CTkLabel(
                chip,
                text=f"{icone}  {insight['titulo']}: {insight['descricao']}",
                text_color=cor,
                font=ctk.CTkFont(size=11),
                wraplength=880,
                justify="left",
            ).pack(anchor="w", padx=10, pady=6)

    def _atualizar_meme_dashboard(self, dados):
        from app.utils.helpers import formatar_moeda

        contexto = {
            "receitas": formatar_moeda(dados.get("total_receitas", 0) or 0),
            "despesas": formatar_moeda(dados.get("total_despesas", 0) or 0),
            "saldo": formatar_moeda(dados.get("saldo_mensal", 0) or 0),
            "transacoes": int(dados.get("total_transacoes", 0) or 0),
        }
        self.lbl_vorcaro_meme.configure(text=f"😏 {self.app.proximo_meme_gui(contexto)}")

    def receber_meme_automatico(self):
        if _widget_existe(self):
            self.lbl_vorcaro_meme.configure(text=f"😏 {self.app.proximo_meme_gui()}")

    def _atualizar_radar_vorcaro(self, dados, insights, n_venc: int):
        receitas = float(dados.get("total_receitas", 0) or 0)
        despesas = float(dados.get("total_despesas", 0) or 0)
        saldo = float(dados.get("saldo_mensal", 0) or 0)

        comprometimento = (despesas / receitas) if receitas > 0 else 1.0
        if saldo >= 0 and comprometimento <= 0.75:
            status_txt = "Status: saudável"
            status_cor = COR_SUCESSO
        elif saldo >= 0 and comprometimento <= 1.0:
            status_txt = "Status: atenção"
            status_cor = COR_AVISO
        else:
            status_txt = "Status: risco"
            status_cor = COR_PERIGO

        self.lbl_vorcaro_status.configure(
            text=f"{status_txt}  |  Comprometimento: {comprometimento * 100:.0f}%",
            text_color=status_cor,
        )

        sugestao_base = "Revise seus gastos fixos e alinhe suas metas para o próximo ciclo."
        if insights:
            item = insights[0]
            titulo = str(item.get("titulo") or "Sugestão")
            descricao = str(item.get("descricao") or "")
            sugestao_base = f"{titulo}: {descricao}".strip()
        if n_venc > 0:
            sugestao_base += f" Você tem {n_venc} vencimento(s) próximo(s)."

        self.lbl_vorcaro_recomendacao.configure(text=sugestao_base)

    def _abrir_assistente(self):
        try:
            self.app._navegar("assistente")
            frame = getattr(self.app, "_frame_atual", None)
            if frame and hasattr(frame, "entry") and hasattr(frame, "_enviar"):
                frame.entry.delete(0, "end")
                frame.entry.insert(0, "Me dê um plano de economia para este mês")
                frame._enviar()
        except Exception:
            logger.exception("Não foi possível abrir o assistente a partir do dashboard.")

    def _renderizar_graficos(self, dados):
        """Cria gráficos matplotlib dentro do frame."""
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            for w in self.frame_graficos.winfo_children():
                w.destroy()
        except ImportError:
            ctk.CTkLabel(self.frame_graficos, text="📊 Instale matplotlib para visualizar gráficos",
                         text_color=COR_TEXTO_SUAVE).pack(pady=20)
            return

        plt.style.use("dark_background")
        BG = COR_CARD

        # ── Rosca: gastos por categoria ───────────────────────────────
        frame_pizza = ctk.CTkFrame(self.frame_graficos, fg_color=COR_CARD, corner_radius=14)
        frame_pizza.configure(border_width=1, border_color=COR_BORDA)
        if self.app._ui_compacto:
            frame_pizza.grid(row=0, column=0, padx=0, pady=(0, 10), sticky="nsew")
        else:
            frame_pizza.grid(row=0, column=0, padx=(0, 6), sticky="nsew")
        frame_pizza.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame_pizza, text="🏷️  Gastos por Categoria",
                     font=ctk.CTkFont(size=13, weight="bold"), text_color=COR_TEXTO).pack(pady=(12, 0))

        cats = dados.get("categorias_gastos", [])
        if cats:
            pizza_size = (4.0, 2.8) if self.app._ui_compacto else (4.2, 3.0)
            fig_pizza, ax = plt.subplots(figsize=pizza_size, facecolor=BG)
            ax.set_facecolor(BG)
            nomes   = [c["categoria"] for c in cats[:6]]
            valores = [c["valor"]     for c in cats[:6]]
            cores   = [COR_DESTAQUE, COR_PERIGO, COR_SUCESSO, COR_AVISO, COR_ACENTO, COR_PRIMARIA]
            wedges, _, autotexts = ax.pie(
                valores, labels=None, autopct="%1.0f%%",
                colors=cores[:len(nomes)], startangle=90,
                pctdistance=0.75,
                wedgeprops={"width": 0.55},
                textprops={"color": "white", "fontsize": 8},
            )
            ax.legend(wedges, nomes, loc="lower center", ncol=3,
                      bbox_to_anchor=(0.5, -0.22), fontsize=7,
                      labelcolor="white", framealpha=0)
            plt.tight_layout()
            canvas = FigureCanvasTkAgg(fig_pizza, master=frame_pizza)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=(0, 8))
            plt.close(fig_pizza)
        else:
            ctk.CTkLabel(frame_pizza, text="Nenhum dado disponível",
                         text_color=COR_TEXTO_SUAVE).pack(pady=40)

        # ── Barras: evolução mensal ───────────────────────────────────
        frame_barras = ctk.CTkFrame(self.frame_graficos, fg_color=COR_CARD, corner_radius=14)
        frame_barras.configure(border_width=1, border_color=COR_BORDA)
        if self.app._ui_compacto:
            frame_barras.grid(row=1, column=0, padx=0, pady=(0, 4), sticky="nsew")
        else:
            frame_barras.grid(row=0, column=1, padx=(6, 0), sticky="nsew")
        frame_barras.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame_barras, text="📈  Evolução Mensal",
                     font=ctk.CTkFont(size=13, weight="bold"), text_color=COR_TEXTO).pack(pady=(12, 0))

        evolucao = dados.get("evolucao_mensal", [])
        if evolucao:
            barras_size = (4.8, 2.8) if self.app._ui_compacto else (5.0, 3.0)
            fig_ev, ax2 = plt.subplots(figsize=barras_size, facecolor=BG)
            ax2.set_facecolor(BG)
            meses    = [e["mes"][:7]  for e in evolucao]
            receitas = [e["receitas"] for e in evolucao]
            desp     = [e["despesas"] for e in evolucao]
            x        = range(len(meses))
            largura  = 0.35

            ax2.bar([i - largura/2 for i in x], receitas, largura, label="Receitas", color=COR_SUCESSO, alpha=0.88)
            ax2.bar([i + largura/2 for i in x], desp,     largura, label="Despesas", color=COR_PERIGO, alpha=0.88)
            ax2.set_xticks(list(x))
            ax2.set_xticklabels(meses, rotation=35, ha="right", fontsize=7, color="white")
            ax2.tick_params(colors="white", axis="both")
            ax2.yaxis.grid(True, color=COR_SECUNDARIA, linestyle="--", linewidth=0.6, alpha=0.75)
            ax2.set_axisbelow(True)
            ax2.legend(fontsize=8, labelcolor="white", framealpha=0)
            ax2.spines[:].set_visible(False)
            plt.tight_layout()
            canvas2 = FigureCanvasTkAgg(fig_ev, master=frame_barras)
            canvas2.draw()
            canvas2.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=(0, 8))
            plt.close(fig_ev)
        else:
            ctk.CTkLabel(frame_barras, text="Nenhum dado disponível",
                         text_color=COR_TEXTO_SUAVE).pack(pady=40)

    def _mes_anterior(self):
        self.mes -= 1
        if self.mes == 0:
            self.mes, self.ano = 12, self.ano - 1
        self.carregar_dados()

    def _mes_proximo(self):
        self.mes += 1
        if self.mes == 13:
            self.mes, self.ano = 1, self.ano + 1
        self.carregar_dados()

    @staticmethod
    def _nome_mes(mes):
        nomes = ["", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                 "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        return nomes[mes]


# ================================================
# Utilitário: máscara de data  DD/MM/AAAA
# ================================================

def _aplicar_mascara_data(entry: ctk.CTkEntry) -> None:
    """
    Aplica máscara automática de data (DD/MM/AAAA) a um CTkEntry.
    - Aceita somente dígitos; insere '/' automaticamente nas posições 2 e 5.
    - Limita o campo a 10 caracteres.
    - Destaca em vermelho se o valor digitado não formar uma data válida.
    """
    import tkinter as _tk
    from datetime import date as _date

    def _on_key(event):
        widget = event.widget
        # Ignora teclas de controle (setas, backspace, delete, home, end)
        if event.keysym in ("BackSpace", "Delete", "Left", "Right",
                             "Home", "End", "Tab"):
            return

        # Só permite dígitos
        if not event.char.isdigit():
            return "break"

        # Obtém valor atual e posição do cursor
        try:
            raw  = widget.get()
            pos  = widget.index(_tk.INSERT)
        except Exception:
            return

        # Remove caracteres extras além do limite
        digits = raw.replace("/", "")
        if len(digits) >= 8:
            return "break"

    def _on_keyrelease(event):
        widget = event.widget
        try:
            raw = widget.get()
        except Exception:
            return

        # Reconstrói somente com dígitos + barras nas posições certas
        digits = raw.replace("/", "")[:8]
        novo   = ""
        for i, c in enumerate(digits):
            if i in (2, 4):
                novo += "/"
            novo += c

        # Atualiza somente se mudou
        try:
            cur_pos = widget.index(_tk.INSERT)
        except Exception:
            cur_pos = len(novo)

        if widget.get() != novo:
            widget.delete(0, _tk.END)
            widget.insert(0, novo)
            # Reposiciona cursor de forma natural
            nova_pos = min(len(novo), cur_pos + (1 if len(novo) > len(raw) else 0))
            widget.icursor(nova_pos)

        # Validação visual: destaca quando completo mas inválido
        if len(novo) == 10:
            try:
                dd, mm, aaaa = novo.split("/")
                _date(int(aaaa), int(mm), int(dd))
                widget.configure(border_color="#27AE60")   # verde = ok
            except Exception:
                widget.configure(border_color="#E74C3C")   # vermelho = inválido
        else:
            widget.configure(border_color=("gray75", "gray30"))  # neutro

    # Obtém o widget Tkinter interno do CTkEntry
    try:
        inner = entry._entry
    except AttributeError:
        inner = entry

    inner.bind("<Key>",        _on_key,        add="+")
    inner.bind("<KeyRelease>", _on_keyrelease, add="+")


def _normalizar_hora_hhmm(valor: str) -> str:
    bruto = (valor or "").strip()
    if not bruto:
        return ""
    if ":" in bruto:
        hh, mm = bruto.split(":", 1)
    else:
        digitos = "".join(ch for ch in bruto if ch.isdigit())
        if len(digitos) not in {3, 4}:
            raise ValueError("Hora inválida")
        hh, mm = digitos[:-2], digitos[-2:]
    hora = int(hh)
    minuto = int(mm)
    if not (0 <= hora <= 23 and 0 <= minuto <= 59):
        raise ValueError("Hora inválida")
    return f"{hora:02d}:{minuto:02d}"


def _aplicar_mascara_hora(entry: ctk.CTkEntry) -> None:
    import tkinter as _tk

    def _on_key(event):
        widget = event.widget
        if event.keysym in ("BackSpace", "Delete", "Left", "Right", "Home", "End", "Tab"):
            return
        if not event.char.isdigit():
            return "break"
        try:
            raw = widget.get().replace(":", "")
        except Exception:
            return
        if len(raw) >= 4:
            return "break"

    def _on_keyrelease(event):
        widget = event.widget
        try:
            raw = widget.get()
        except Exception:
            return
        digitos = "".join(ch for ch in raw if ch.isdigit())[:4]
        novo = digitos if len(digitos) < 3 else digitos[:2] + ":" + digitos[2:]
        if widget.get() != novo:
            widget.delete(0, _tk.END)
            widget.insert(0, novo)
        if len(novo) == 5:
            try:
                _normalizar_hora_hhmm(novo)
                widget.configure(border_color="#27AE60")
            except Exception:
                widget.configure(border_color="#E74C3C")
        else:
            widget.configure(border_color=("gray75", "gray30"))

    try:
        inner = entry._entry
    except AttributeError:
        inner = entry

    inner.bind("<Key>", _on_key, add="+")
    inner.bind("<KeyRelease>", _on_keyrelease, add="+")


# ================================================
# Frame: Transações
# ================================================

class TransacoesFrame(ctk.CTkFrame):
    """Listagem, busca e edição de transações."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._sort_column = "data"
        self._sort_reverse = True
        self._headers_base = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._construir_ui()
        self.carregar_dados()

    def _construir_ui(self):
        # Título e controles
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="💳 Transações",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=COR_TEXTO).grid(row=0, column=0, sticky="w")

        # Barra de filtros
        filtros = ctk.CTkFrame(header, fg_color=COR_CARD, corner_radius=10)
        filtros.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        filtros.grid_columnconfigure(0, weight=1)

        hoje       = date.today()
        self.var_mes = ctk.StringVar(value=str(hoje.month))
        self.var_ano = ctk.StringVar(value=str(hoje.year))
        self.var_busca = ctk.StringVar()
        self.var_categoria = ctk.StringVar(value="Todas")
        self.var_data_inicial = ctk.StringVar()
        self.var_data_final = ctk.StringVar()
        self.var_valor_min = ctk.StringVar()
        self.var_valor_max = ctk.StringVar()

        linha_superior = ctk.CTkFrame(filtros, fg_color="transparent")
        linha_superior.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))

        linha_inferior = ctk.CTkFrame(filtros, fg_color="transparent")
        linha_inferior.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))

        ctk.CTkLabel(linha_superior, text="Mês:", text_color=COR_TEXTO_SUAVE).pack(side="left", padx=(0, 2))
        ctk.CTkComboBox(linha_superior, values=[str(i) for i in range(1, 13)],
                        variable=self.var_mes, width=55).pack(side="left", padx=2)
        ctk.CTkLabel(linha_superior, text="Ano:", text_color=COR_TEXTO_SUAVE).pack(side="left", padx=(6, 2))
        ctk.CTkEntry(linha_superior, textvariable=self.var_ano, width=65).pack(side="left", padx=2)
        ctk.CTkLabel(linha_superior, text="Busca:", text_color=COR_TEXTO_SUAVE).pack(side="left", padx=(6, 2))
        ctk.CTkEntry(linha_superior, textvariable=self.var_busca,
                     placeholder_text="descrição...", width=160).pack(side="left", padx=2)
        ctk.CTkLabel(linha_superior, text="Categoria:", text_color=COR_TEXTO_SUAVE).pack(side="left", padx=(6, 2))
        self.combo_categoria = ctk.CTkComboBox(
            linha_superior,
            variable=self.var_categoria,
            values=["Todas"],
            width=170,
            state="readonly",
        )
        self.combo_categoria.pack(side="left", padx=2)

        ctk.CTkLabel(linha_inferior, text="Data de:", text_color=COR_TEXTO_SUAVE).pack(side="left", padx=(0, 2))
        self.entry_data_inicial = ctk.CTkEntry(linha_inferior, textvariable=self.var_data_inicial,
                                               placeholder_text="DD/MM/AAAA", width=110)
        self.entry_data_inicial.pack(side="left", padx=2)
        _aplicar_mascara_data(self.entry_data_inicial)

        ctk.CTkLabel(linha_inferior, text="até:", text_color=COR_TEXTO_SUAVE).pack(side="left", padx=(6, 2))
        self.entry_data_final = ctk.CTkEntry(linha_inferior, textvariable=self.var_data_final,
                                             placeholder_text="DD/MM/AAAA", width=110)
        self.entry_data_final.pack(side="left", padx=2)
        _aplicar_mascara_data(self.entry_data_final)

        ctk.CTkLabel(linha_inferior, text="Valor de:", text_color=COR_TEXTO_SUAVE).pack(side="left", padx=(6, 2))
        ctk.CTkEntry(linha_inferior, textvariable=self.var_valor_min,
                     placeholder_text="0,00", width=90).pack(side="left", padx=2)
        ctk.CTkLabel(linha_inferior, text="até:", text_color=COR_TEXTO_SUAVE).pack(side="left", padx=(6, 2))
        ctk.CTkEntry(linha_inferior, textvariable=self.var_valor_max,
                     placeholder_text="0,00", width=90).pack(side="left", padx=2)

        ctk.CTkButton(linha_inferior, text="🔍 Filtrar", width=80,
                      command=self.carregar_dados).pack(side="left", padx=(8, 4), pady=2)
        ctk.CTkButton(linha_inferior, text="Limpar", width=70,
                      fg_color="#5D6D7E", hover_color="#4A5A68",
                      command=self._limpar_filtros).pack(side="left", padx=(0, 8), pady=2)
        ctk.CTkButton(linha_inferior, text="🗑️ Excluir", width=80, fg_color=COR_PERIGO,
                      hover_color="#C0392B", command=self._excluir_sel).pack(side="right", padx=(0, 4), pady=2)
        ctk.CTkButton(linha_inferior, text="✏️ Editar", width=80, fg_color=COR_PRIMARIA,
                      command=self._editar_sel).pack(side="right", padx=(0, 4), pady=2)
        ctk.CTkButton(linha_inferior, text="🏷️ Categoria", width=90, fg_color=COR_SECUNDARIA,
                      command=self._alterar_categoria_sel).pack(side="right", padx=(0, 4), pady=2)

        self._carregar_filtro_categorias()

        # Tabela (Treeview customizado)
        frame_tabela = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)
        frame_tabela.grid(row=1, column=0, sticky="nsew")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.Treeview",
                        background="#0F3460", foreground="white",
                        rowheight=26, fieldbackground="#0F3460",
                        font=("Segoe UI", 10))
        style.configure("Dark.Treeview.Heading",
                        background="#2E86AB", foreground="white",
                        font=("Segoe UI", 10, "bold"))
        style.map("Dark.Treeview", background=[("selected", "#2980B9")])

        colunas = ("id", "data", "descricao", "categoria", "tipo", "valor", "parcela")
        self.tree = ttk.Treeview(frame_tabela, columns=colunas, show="headings",
                                  style="Dark.Treeview", selectmode="extended")

        headers = {"id": ("ID", 40), "data": ("Data", 80), "descricao": ("Descrição", 320),
                   "categoria": ("Categoria", 120), "tipo": ("Tipo", 70),
                   "valor": ("Valor", 100), "parcela": ("Parcela", 65)}

        self._headers_base = {col: label for col, (label, _w) in headers.items()}

        for col, (label, width) in headers.items():
            self.tree.heading(col, text=label, command=lambda c=col: self._ordenar_por_coluna(c))
            self.tree.column(col, width=width, anchor="center" if col in ("id","tipo","data","parcela") else "w")

        self._atualizar_cabecalhos_ordenacao()

        vsb = ttk.Scrollbar(frame_tabela, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8,0), pady=8)
        vsb.pack(side="right", fill="y", pady=8, padx=(0,4))

        # Tags de cor por tipo
        self.tree.tag_configure("debito",  foreground="#E74C3C")
        self.tree.tag_configure("credito", foreground="#27AE60")

        # Duplo clique para editar
        self.tree.bind("<Double-1>", lambda e: self._editar_sel())

        # Rodapé com totais
        self.lbl_totais = ctk.CTkLabel(self, text="", text_color=COR_TEXTO_SUAVE,
                                        font=ctk.CTkFont(size=11))
        self.lbl_totais.grid(row=2, column=0, sticky="e", pady=(4, 0))

    def carregar_dados(self):
        """Recarrega a tabela com os filtros aplicados."""
        for row in self.tree.get_children():
            self.tree.delete(row)

        db = self.app._obter_db()
        try:
            from app.models import Categoria, Transacao
            from app.utils.helpers import formatar_moeda
            from sqlalchemy import extract

            q = db.query(Transacao)
            try:
                mes = int(self.var_mes.get())
                ano = int(self.var_ano.get())
                q = q.filter(extract("month", Transacao.data) == mes,
                              extract("year",  Transacao.data) == ano)
            except ValueError:
                pass

            busca = self.var_busca.get().strip()
            if busca:
                q = q.filter(Transacao.descricao.ilike(f"%{busca}%"))

            categoria = self.var_categoria.get().strip()
            if categoria and categoria != "Todas":
                q = q.join(Categoria, Transacao.categoria_id == Categoria.id)
                q = q.filter(Categoria.nome == categoria)

            data_inicial = self._parse_data_filtro(self.var_data_inicial.get(), "Data inicial")
            data_final = self._parse_data_filtro(self.var_data_final.get(), "Data final")
            if data_inicial is None and self.var_data_inicial.get().strip():
                return
            if data_final is None and self.var_data_final.get().strip():
                return
            if data_inicial and data_final and data_inicial > data_final:
                messagebox.showwarning("Filtro inválido", "A data inicial não pode ser maior que a data final.", parent=self)
                return
            if data_inicial:
                q = q.filter(Transacao.data >= data_inicial)
            if data_final:
                q = q.filter(Transacao.data <= data_final)

            valor_min = self._parse_valor_filtro(self.var_valor_min.get(), "Valor mínimo")
            valor_max = self._parse_valor_filtro(self.var_valor_max.get(), "Valor máximo")
            if valor_min is None and self.var_valor_min.get().strip():
                return
            if valor_max is None and self.var_valor_max.get().strip():
                return
            if valor_min is not None and valor_max is not None and valor_min > valor_max:
                messagebox.showwarning("Filtro inválido", "O valor mínimo não pode ser maior que o valor máximo.", parent=self)
                return
            if valor_min is not None:
                q = q.filter(Transacao.valor >= valor_min)
            if valor_max is not None:
                q = q.filter(Transacao.valor <= valor_max)

            transacoes = q.order_by(Transacao.data.desc()).limit(500).all()

            total_deb = total_cred = 0.0
            for t in transacoes:
                cat      = t.categoria.nome if t.categoria else "—"
                parcela  = f"{t.parcela_atual}/{t.parcelas_total}" if t.parcela_atual else "—"
                tipo_txt = "Débito" if t.tipo == "debito" else "Crédito"
                tag      = t.tipo

                self.tree.insert("", "end", iid=t.id, tags=(tag,), values=(
                    t.id,
                    t.data.strftime("%d/%m/%Y"),
                    t.descricao[:55],
                    cat,
                    tipo_txt,
                    formatar_moeda(t.valor),
                    parcela,
                ))
                if t.tipo == "debito":
                    total_deb += t.valor
                else:
                    total_cred += t.valor

            self.lbl_totais.configure(
                text=f"Receitas: {formatar_moeda(total_cred)}   |   "
                     f"Despesas: {formatar_moeda(total_deb)}   |   "
                     f"Saldo: {formatar_moeda(total_cred - total_deb)}   |   "
                     f"{len(transacoes)} transações"
            )

            # Mantém a ordenação escolhida no cabeçalho ao recarregar dados.
            if self._sort_column:
                self._ordenar_por_coluna(self._sort_column, manter_direcao=True)
        finally:
            db.close()

    def _atualizar_cabecalhos_ordenacao(self):
        for col, label in self._headers_base.items():
            if col == self._sort_column:
                seta = "▼" if self._sort_reverse else "▲"
                self.tree.heading(col, text=f"{label} {seta}", command=lambda c=col: self._ordenar_por_coluna(c))
            else:
                self.tree.heading(col, text=label, command=lambda c=col: self._ordenar_por_coluna(c))

    def _ordenar_por_coluna(self, coluna: str, manter_direcao: bool = False):
        if not manter_direcao:
            if self._sort_column == coluna:
                self._sort_reverse = not self._sort_reverse
            else:
                self._sort_column = coluna
                # Padrão: data começa desc; demais começam asc.
                self._sort_reverse = coluna == "data"

        itens = list(self.tree.get_children(""))
        if not itens:
            return

        def chave_item(iid):
            vals = self.tree.item(iid, "values")
            idx = {
                "id": 0,
                "data": 1,
                "descricao": 2,
                "categoria": 3,
                "tipo": 4,
                "valor": 5,
                "parcela": 6,
            }.get(coluna, 0)
            raw = vals[idx] if idx < len(vals) else ""
            return self._normalizar_chave_ordenacao(coluna, raw)

        itens.sort(key=chave_item, reverse=self._sort_reverse)

        for pos, iid in enumerate(itens):
            self.tree.move(iid, "", pos)

        self._atualizar_cabecalhos_ordenacao()

    def _normalizar_chave_ordenacao(self, coluna: str, raw):
        texto = str(raw or "").strip()

        if coluna == "id":
            try:
                return int(texto)
            except Exception:
                return 0

        if coluna == "data":
            try:
                d, m, a = texto.split("/")
                return (int(a), int(m), int(d))
            except Exception:
                return (0, 0, 0)

        if coluna == "valor":
            limpo = texto.lower().replace("r$", "").replace(" ", "")
            try:
                return float(limpo.replace(".", "").replace(",", "."))
            except Exception:
                return 0.0

        if coluna == "parcela":
            if texto in {"", "—", "-"}:
                return (9999, 9999)
            try:
                atual, total = texto.split("/")
                return (int(total), int(atual))
            except Exception:
                return (9999, 9999)

        return texto.lower()

    def _carregar_filtro_categorias(self):
        db = self.app._obter_db()
        try:
            from app.models import Categoria

            categorias = db.query(Categoria).filter(Categoria.ativa == True).order_by(Categoria.nome).all()
            valores = ["Todas"] + [categoria.nome for categoria in categorias]
            self.combo_categoria.configure(values=valores)
            if self.var_categoria.get() not in valores:
                self.var_categoria.set("Todas")
        finally:
            db.close()

    def _limpar_filtros(self):
        hoje = date.today()
        self.var_mes.set(str(hoje.month))
        self.var_ano.set(str(hoje.year))
        self.var_busca.set("")
        self.var_categoria.set("Todas")
        self.var_data_inicial.set("")
        self.var_data_final.set("")
        self.var_valor_min.set("")
        self.var_valor_max.set("")
        self.carregar_dados()

    def _parse_data_filtro(self, valor: str, rotulo: str):
        valor = valor.strip()
        if not valor:
            return None
        try:
            dia, mes, ano = valor.split("/")
            return date(int(ano), int(mes), int(dia))
        except Exception:
            messagebox.showwarning("Data inválida", f"{rotulo} inválida. Use DD/MM/AAAA.", parent=self)
            return None

    def _parse_valor_filtro(self, valor: str, rotulo: str):
        valor = valor.strip()
        if not valor:
            return None
        try:
            return abs(float(valor.replace(".", "").replace(",", ".")))
        except ValueError:
            messagebox.showwarning("Valor inválido", f"{rotulo} inválido. Use formato como 150,00.", parent=self)
            return None

    def _excluir_sel(self):
        selecionados = self.tree.selection()
        if not selecionados:
            messagebox.showinfo("Atenção", "Selecione uma transação para excluir.")
            return
        if not messagebox.askyesno("Confirmar", f"Excluir {len(selecionados)} transação(ões)?"):
            return

        db = self.app._obter_db()
        try:
            from app.models import Transacao
            for iid in selecionados:
                t = db.query(Transacao).filter(Transacao.id == int(iid)).first()
                if t:
                    db.delete(t)
            db.commit()
        finally:
            db.close()

        self.carregar_dados()

    def _editar_sel(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("É preciso selecionar", "Selecione uma ou mais transações para editar.", parent=self)
            return
        if len(sel) == 1:
            self._dialog_editar(int(sel[0]))
        else:
            self._dialog_editar_multiplos(list(sel))

    def _dialog_editar_multiplos(self, iids: list):
        """Edição em lote: altera data e/ou categoria de várias transações."""
        db = self.app._obter_db()
        try:
            from app.models import Categoria
            cats = db.query(Categoria).filter(Categoria.ativa == True).order_by(Categoria.nome).all()
            cats_nomes = ["-- Manter atual --"] + [c.nome for c in cats]
            cats_map   = {c.nome: c.id for c in cats}
        finally:
            db.close()

        dialog = ctk.CTkToplevel(self)
        dialog.title(f"✏️ Editar em Lote — {len(iids)} transações")
        dialog.geometry("500x380")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.lift()

        ctk.CTkLabel(dialog,
                     text=f"✏️  Editar em Lote  —  {len(iids)} transações selecionadas",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=COR_TEXTO).pack(pady=(20, 6))
        ctk.CTkLabel(dialog,
                     text="Deixe o campo vazio para manter o valor original.",
                     font=ctk.CTkFont(size=11),
                     text_color=COR_TEXTO_SUAVE).pack(pady=(0, 12))

        frm = ctk.CTkFrame(dialog, fg_color=COR_CARD, corner_radius=10)
        frm.pack(padx=20, fill="x", pady=(0, 8))
        frm.grid_columnconfigure(1, weight=1)

        # —— Data ——
        ctk.CTkLabel(frm, text="Nova Data:",
                     text_color=COR_TEXTO, anchor="w"
                     ).grid(row=0, column=0, sticky="w", padx=(16, 12), pady=12)
        e_data = ctk.CTkEntry(frm, placeholder_text="DD/MM/AAAA  (opcional)")
        e_data.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=12)
        _aplicar_mascara_data(e_data)
        lbl_data_err = ctk.CTkLabel(frm, text="", text_color=COR_PERIGO,
                                     font=ctk.CTkFont(size=10))
        lbl_data_err.grid(row=1, column=1, sticky="w", padx=(0, 16))

        # —— Categoria ——
        ctk.CTkLabel(frm, text="Categoria:",
                     text_color=COR_TEXTO, anchor="w"
                     ).grid(row=2, column=0, sticky="w", padx=(16, 12), pady=12)
        var_cat = ctk.StringVar(value="-- Manter atual --")
        ctk.CTkComboBox(frm, variable=var_cat, values=cats_nomes,
                        state="readonly", width=280
                        ).grid(row=2, column=1, sticky="ew", padx=(0, 16), pady=12)

        # —— Tipo ——
        ctk.CTkLabel(frm, text="Tipo:",
                     text_color=COR_TEXTO, anchor="w"
                     ).grid(row=3, column=0, sticky="w", padx=(16, 12), pady=12)
        var_tipo = ctk.StringVar(value="-- Manter atual --")
        tipo_vals = ["-- Manter atual --", "debito", "credito"]
        ctk.CTkComboBox(frm, variable=var_tipo, values=tipo_vals,
                        state="readonly", width=180
                        ).grid(row=3, column=1, sticky="w", padx=(0, 16), pady=12)

        def _aplicar_lote():
            from datetime import date as _date
            nova_data = None
            raw_data  = e_data.get().strip()
            if raw_data:
                try:
                    dd, mm, aaaa = raw_data.split("/")
                    nova_data = _date(int(aaaa), int(mm), int(dd))
                    lbl_data_err.configure(text="")
                except Exception:
                    lbl_data_err.configure(text="⚠️ Data inválida — use DD/MM/AAAA")
                    return

            nome_cat = var_cat.get()
            nova_cat = cats_map.get(nome_cat) if nome_cat != "-- Manter atual --" else "_MANTER_"
            tipo_val = var_tipo.get() if var_tipo.get() != "-- Manter atual --" else None

            if nova_data is None and nova_cat == "_MANTER_" and tipo_val is None:
                messagebox.showinfo("⚠️ Nada a alterar",
                                    "Preencha pelo menos um campo para alterar.",
                                    parent=dialog)
                return

            db2 = self.app._obter_db()
            try:
                from app.models import Transacao as _T
                atualizadas = 0
                for iid in iids:
                    t = db2.query(_T).filter(_T.id == int(iid)).first()
                    if not t:
                        continue
                    if nova_data is not None:
                        t.data = nova_data
                    if nova_cat != "_MANTER_":
                        t.categoria_id = nova_cat
                    if tipo_val is not None:
                        t.tipo = tipo_val
                    atualizadas += 1
                db2.commit()
            finally:
                db2.close()

            messagebox.showinfo("✅ Concluído",
                                 f"{atualizadas} transação(oes) atualizadas.",
                                 parent=dialog)
            dialog.destroy()
            self.carregar_dados()

        ctk.CTkButton(dialog, text="💾  Aplicar a todas as selecionadas",
                      fg_color=COR_SUCESSO, hover_color="#1E8449",
                      command=_aplicar_lote).pack(pady=(4, 4), padx=20, fill="x")
        ctk.CTkButton(dialog, text="Cancelar",
                      fg_color="transparent", border_width=1,
                      command=dialog.destroy).pack(pady=(0, 16), padx=20, fill="x")

    def _alterar_categoria_sel(self):
        """Altera a categoria de todas as linhas selecionadas de uma só vez."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Selecione", "Selecione uma ou mais transações para alterar a categoria.", parent=self)
            return

        db = self.app._obter_db()
        try:
            from app.models import Categoria
            cats = db.query(Categoria).filter(Categoria.ativa == True).order_by(Categoria.nome).all()
            cats_nomes = ["-- Manter atual --"] + [c.nome for c in cats]
            cats_map   = {c.nome: c.id for c in cats}
        finally:
            db.close()

        dialog = ctk.CTkToplevel(self)
        dialog.title("🏷️ Alterar Categoria")
        dialog.geometry("380x200")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.lift()

        ctk.CTkLabel(dialog, text=f"🏷️ Alterar Categoria — {len(sel)} transação(oes)",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=COR_TEXTO).pack(pady=(18, 10))

        var_cat = ctk.StringVar(value="-- Manter atual --")
        combo = ctk.CTkComboBox(dialog, variable=var_cat, values=cats_nomes,
                                state="readonly", width=320)
        combo.pack(padx=20, pady=6)

        def _aplicar():
            nome = var_cat.get()
            if nome == "-- Manter atual --":
                dialog.destroy()
                return
            cat_id = cats_map.get(nome)
            db2 = self.app._obter_db()
            try:
                from app.models import Transacao
                for iid in sel:
                    t = db2.query(Transacao).filter(Transacao.id == int(iid)).first()
                    if t:
                        t.categoria_id = cat_id
                db2.commit()
            finally:
                db2.close()
            dialog.destroy()
            self.carregar_dados()

        ctk.CTkButton(dialog, text="💾 Aplicar", fg_color=COR_SUCESSO,
                      command=_aplicar).pack(pady=10, padx=20, fill="x")

    def _dialog_editar(self, t_id: int):
        """Abre formulário completo para editar todos os campos de uma transação."""
        db = self.app._obter_db()
        try:
            from app.models import Transacao, Categoria
            t = db.query(Transacao).filter(Transacao.id == t_id).first()
            if not t:
                return
            cats            = db.query(Categoria).filter(Categoria.ativa == True).order_by(Categoria.nome).all()
            data_val        = t.data
            desc_val        = t.descricao
            valor_val       = t.valor
            tipo_val        = t.tipo.value if hasattr(t.tipo, "value") else str(t.tipo)
            cat_nome_atual  = t.categoria.nome if t.categoria else None
            obs_val         = t.observacao or ""
            cats_nomes      = ["— Sem categoria —"] + [c.nome for c in cats]
            cats_map        = {c.nome: c.id for c in cats}
        finally:
            db.close()

        dialog = ctk.CTkToplevel(self)
        dialog.title(f"✏️ Editar Transação #{t_id}")
        dialog.geometry("500x465")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.lift()

        ctk.CTkLabel(dialog, text=f"✏️  Editar Transação  #{t_id}",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=COR_TEXTO).pack(pady=(18, 12))

        frm = ctk.CTkFrame(dialog, fg_color="transparent")
        frm.pack(padx=24, fill="x")
        frm.grid_columnconfigure(1, weight=1)

        def _lbl(texto, row):
            ctk.CTkLabel(frm, text=texto, text_color=COR_TEXTO,
                         anchor="w").grid(row=row, column=0, sticky="w", padx=(0, 12), pady=5)

        # Data com máscara
        _lbl("Data:", 0)
        e_data = ctk.CTkEntry(frm, placeholder_text="DD/MM/AAAA")
        e_data.insert(0, data_val.strftime("%d/%m/%Y"))
        e_data.grid(row=0, column=1, sticky="ew", pady=5)
        _aplicar_mascara_data(e_data)

        # Descrição
        _lbl("Descrição:", 1)
        e_desc = ctk.CTkEntry(frm, placeholder_text="Descrição da transação")
        e_desc.insert(0, desc_val)
        e_desc.grid(row=1, column=1, sticky="ew", pady=5)

        # Valor
        _lbl("Valor (R$):", 2)
        e_valor = ctk.CTkEntry(frm, placeholder_text="0,00")
        e_valor.insert(0, f"{valor_val:.2f}".replace(".", ","))
        e_valor.grid(row=2, column=1, sticky="ew", pady=5)

        # Tipo
        _lbl("Tipo:", 3)
        var_tipo = ctk.StringVar(value=tipo_val)
        tipo_f = ctk.CTkFrame(frm, fg_color="transparent")
        tipo_f.grid(row=3, column=1, sticky="w", pady=5)
        ctk.CTkRadioButton(tipo_f, text="💸 Débito",  variable=var_tipo, value="debito").pack(side="left", padx=(0, 18))
        ctk.CTkRadioButton(tipo_f, text="💵 Crédito", variable=var_tipo, value="credito").pack(side="left")

        # Categoria
        _lbl("Categoria:", 4)
        var_cat = ctk.StringVar(value=cat_nome_atual or "— Sem categoria —")
        ctk.CTkComboBox(frm, variable=var_cat, values=cats_nomes,
                        state="readonly").grid(row=4, column=1, sticky="ew", pady=5)

        # Observação
        _lbl("Observação:", 5)
        e_obs = ctk.CTkEntry(frm, placeholder_text="Opcional")
        e_obs.insert(0, obs_val)
        e_obs.grid(row=5, column=1, sticky="ew", pady=5)

        def _salvar():
            from datetime import date as _date
            try:
                d = e_data.get().strip()
                dd, mm, aaaa = d.split("/")
                nova_data = _date(int(aaaa), int(mm), int(dd))
            except Exception:
                messagebox.showwarning("Data inválida", "Use o formato DD/MM/AAAA.", parent=dialog)
                return
            try:
                novo_valor = abs(float(
                    e_valor.get().strip().replace(".", "").replace(",", ".")
                ))
            except ValueError:
                messagebox.showwarning("Valor inválido",
                                       "Ex: 1.234,56  ou  45,90", parent=dialog)
                return
            db2 = self.app._obter_db()
            try:
                from app.models import Transacao
                tr = db2.query(Transacao).filter(Transacao.id == t_id).first()
                if not tr:
                    return
                tr.data        = nova_data
                tr.descricao   = e_desc.get().strip() or tr.descricao
                tr.valor       = novo_valor
                tr.tipo        = var_tipo.get()
                nome_cat       = var_cat.get()
                tr.categoria_id = cats_map.get(nome_cat) if nome_cat != "— Sem categoria —" else None
                tr.observacao   = e_obs.get().strip() or None
                db2.commit()
            finally:
                db2.close()
            dialog.destroy()
            self.carregar_dados()

        ctk.CTkButton(dialog, text="💾  Salvar alterações",
                      fg_color=COR_SUCESSO, hover_color="#1E8449",
                      command=_salvar).pack(pady=(14, 4), padx=24, fill="x")
        ctk.CTkButton(dialog, text="Cancelar",
                      fg_color="transparent", border_width=1,
                      command=dialog.destroy).pack(pady=(0, 16), padx=24, fill="x")


# ================================================
# Frame: Importar
# ================================================

class ImportarFrame(ctk.CTkFrame):
    """Interface de importação de extratos."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self._construir_ui()

    def _construir_ui(self):
        ctk.CTkLabel(self, text="📤 Importar Extrato",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=COR_TEXTO).grid(row=0, column=0, sticky="w", pady=(0, 10))

        # ── Painel de opções avançadas (importação em lote) ────────────
        topo_avancado = ctk.CTkFrame(self, fg_color="transparent")
        topo_avancado.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        topo_avancado.grid_columnconfigure(0, weight=1)

        self._mostrar_avancado = False
        self.btn_toggle_avancado = ctk.CTkButton(
            topo_avancado,
            text="▶ Mostrar opções avançadas (Extrato/Fatura em lote)",
            fg_color="transparent",
            border_width=1,
            border_color=COR_SECUNDARIA,
            hover_color="#102A43",
            text_color=COR_TEXTO,
            anchor="w",
            command=self._alternar_opcoes_avancadas,
        )
        self.btn_toggle_avancado.grid(row=0, column=0, sticky="ew")

        self.frame_opcoes_avancadas = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)
        opcoes = self.frame_opcoes_avancadas
        opcoes.grid_columnconfigure(1, weight=1)

        # Tipo de extrato (Bancário / Cartão de Crédito)
        ctk.CTkLabel(opcoes, text="Tipo:", text_color=COR_TEXTO,
                     font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(12, 6), pady=10, sticky="w")

        self.var_tipo = ctk.StringVar(value="bancario")
        frame_tipo = ctk.CTkFrame(opcoes, fg_color="transparent")
        frame_tipo.grid(row=0, column=1, sticky="w", pady=10)
        ctk.CTkRadioButton(frame_tipo, text="🏦 Extrato Bancário",
                           variable=self.var_tipo, value="bancario",
                           command=self._atualizar_origem).pack(side="left", padx=(0, 20))
        ctk.CTkRadioButton(frame_tipo, text="💳 Fatura de Cartão",
                           variable=self.var_tipo, value="cartao",
                           command=self._atualizar_origem).pack(side="left")

        # Seletor de conta bancária
        self.lbl_conta = ctk.CTkLabel(opcoes, text="Conta:", text_color=COR_TEXTO,
                                       font=ctk.CTkFont(size=12))
        self.lbl_conta.grid(row=1, column=0, padx=(12, 6), pady=(0, 10), sticky="w")
        self.var_conta = ctk.StringVar(value="— Nenhuma —")
        self.combo_conta = ctk.CTkComboBox(opcoes, variable=self.var_conta,
                                            values=["— Nenhuma —"], width=260, state="readonly")
        self.combo_conta.grid(row=1, column=1, sticky="w", pady=(0, 10))

        # Seletor de cartão (inicialmente oculto)
        self.lbl_cartao = ctk.CTkLabel(opcoes, text="Cartão:", text_color=COR_TEXTO,
                                        font=ctk.CTkFont(size=12))
        self.var_cartao = ctk.StringVar(value="— Nenhum —")
        self.combo_cartao = ctk.CTkComboBox(opcoes, variable=self.var_cartao,
                                             values=["— Nenhum —"], width=260, state="readonly")

        # Botão de cadastro rápido
        self.btn_novo_cartao = ctk.CTkButton(opcoes, text="+ Novo Cartão", width=110,
                                              fg_color=COR_SECUNDARIA,
                                              command=self._dialog_novo_cartao)

        # Carrega listas do banco
        self._carregar_contas_e_cartoes()

        ctk.CTkLabel(
            opcoes,
            text=(
                "Dica: no botão 'Importar & Classificar Documento' não é necessário escolher tipo. "
                "A seleção Extrato/Fatura abaixo vale apenas para importação em lote (PDF/CSV/Excel/OFX)."
            ),
            font=ctk.CTkFont(size=10),
            text_color=COR_TEXTO_SUAVE,
            justify="left",
            wraplength=840,
        ).grid(row=2, column=0, columnspan=3, padx=12, pady=(0, 10), sticky="w")

        # ── Novo: Card "Importar & Classificar Documento" ───────────────
        card_doc = ctk.CTkFrame(self, fg_color="#1B2A3B", corner_radius=14)
        card_doc.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        card_doc.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card_doc, text="🔍", font=ctk.CTkFont(size=36)
        ).grid(row=0, column=0, rowspan=2, padx=(18, 12), pady=16)

        ctk.CTkLabel(
            card_doc,
            text="Importar & Classificar Documento",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COR_TEXTO,
        ).grid(row=0, column=1, sticky="w", pady=(16, 2))

        ctk.CTkLabel(
            card_doc,
            text="Aceita PDF, Imagens (JPG/PNG/BMP/TIFF/WEBP), DOCX e TXT\n"
                 "O sistema detecta automaticamente: Nota Fiscal • Boleto • "
                 "Comprovante • Extrato Bancário • Extrato Cartão",
            font=ctk.CTkFont(size=10),
            text_color=COR_TEXTO_SUAVE,
            justify="left",
        ).grid(row=1, column=1, sticky="w", pady=(0, 4))

        ctk.CTkButton(
            card_doc,
            text="📂  Selecionar Documento",
            fg_color="#2E86AB",
            hover_color="#1B5C7A",
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=8,
            command=self._importar_documento,
        ).grid(row=0, column=2, rowspan=2, padx=18, pady=16, sticky="e")

        # ── Cards de formato (avançado) ─────────────────────────────────
        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.grid(row=3, column=0, sticky="ew")
        for i in range(4):
            cards.grid_columnconfigure(i, weight=1)

        info = [
            ("PDF",   "📄", "Extrato ou fatura em PDF\n(digital ou escaneado)",   self._importar_pdf),
            ("CSV",   "📊", "Arquivo CSV exportado\npelo seu banco",              self._importar_csv),
            ("Excel", "📗", "Planilha Excel (.xlsx)\nde qualquer banco",          self._importar_excel),
            ("OFX",   "🏦", "Formato OFX/QFX — padrão\ninternacional bancário",  self._importar_ofx),
        ]

        for i, (nome, icone, desc, cmd) in enumerate(info):
            card = ctk.CTkFrame(cards, fg_color=COR_CARD, corner_radius=14)
            card.grid(row=0, column=i, padx=6, sticky="nsew")
            ctk.CTkLabel(card, text=icone, font=ctk.CTkFont(size=32)).pack(pady=(20, 4))
            ctk.CTkLabel(card, text=nome, font=ctk.CTkFont(size=15, weight="bold"),
                         text_color=COR_TEXTO).pack()
            ctk.CTkLabel(card, text=desc, font=ctk.CTkFont(size=10),
                         text_color=COR_TEXTO_SUAVE, justify="center").pack(pady=(4, 12))
            ctk.CTkButton(card, text=f"Selecionar {nome}", command=cmd,
                          fg_color=COR_PRIMARIA, corner_radius=8).pack(padx=15, pady=(0, 20), fill="x")

        self.frame_importacao_lote = cards
        self._alternar_opcoes_avancadas(inicial=True)

        # Log de resultado
        ctk.CTkLabel(self, text="Resultado:", text_color=COR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=12)).grid(row=4, column=0, sticky="w", pady=(12, 4))
        self.txt_log = ctk.CTkTextbox(self, height=150, fg_color=COR_CARD, corner_radius=10)
        self.txt_log.grid(row=5, column=0, sticky="ew")

        # Barra de progresso — aparece apenas durante importação
        # Usa ttk.Progressbar nativo (Tcl/Tk puro) para evitar crash cross-thread
        _sty = ttk.Style()
        _sty.configure("Import.Horizontal.TProgressbar",
                       troughcolor="#1a1a2e", background="#4A90D9",
                       thickness=8)
        self.prg_import = ttk.Progressbar(
            self, style="Import.Horizontal.TProgressbar",
            orient="horizontal", mode="indeterminate", length=200)
        self.prg_import.grid(row=6, column=0, sticky="ew", pady=(6, 0))
        self.prg_import.grid_remove()  # oculta por padrão

        self._log("Use 'Importar & Classificar Documento' para fluxo guiado. Opções de lote ficam em avançado.")

    def _alternar_opcoes_avancadas(self, inicial: bool = False):
        """Mostra/oculta os controles de importação em lote para simplificar o fluxo padrão."""
        if not inicial:
            self._mostrar_avancado = not self._mostrar_avancado

        if self._mostrar_avancado:
            self.btn_toggle_avancado.configure(
                text="▼ Ocultar opções avançadas (Extrato/Fatura em lote)"
            )
            self.frame_opcoes_avancadas.grid(row=1, column=0, sticky="ew", pady=(0, 12))
            self.frame_importacao_lote.grid(row=3, column=0, sticky="ew")
            self._atualizar_origem()
        else:
            self.btn_toggle_avancado.configure(
                text="▶ Mostrar opções avançadas (Extrato/Fatura em lote)"
            )
            self.frame_opcoes_avancadas.grid_remove()
            self.frame_importacao_lote.grid_remove()

    def _carregar_contas_e_cartoes(self):
        """Popula combos de conta bancária e cartão de crédito."""
        db = self.app._obter_db()
        try:
            from app.models import ContaBancaria, CartaoCredito
            contas  = db.query(ContaBancaria).filter(ContaBancaria.ativa == True).all()
            cartoes = db.query(CartaoCredito).filter(CartaoCredito.ativo == True).all()
        finally:
            db.close()

        self._contas  = {c.nome: c.id for c in contas}
        self._cartoes = {f"{c.nome} ({c.bandeira})": c.id for c in cartoes}

        nomes_conta  = ["— Nenhuma —"] + list(self._contas.keys())
        nomes_cartao = ["— Nenhum —"]  + list(self._cartoes.keys())

        self.combo_conta.configure(values=nomes_conta)
        self.var_conta.set(nomes_conta[0])
        self.combo_cartao.configure(values=nomes_cartao)
        self.var_cartao.set(nomes_cartao[0])

    def _atualizar_origem(self):
        """Alterna entre seleção de conta bancária e cartão."""
        if self.var_tipo.get() == "cartao":
            # Oculta conta, mostra cartão
            self.lbl_conta.grid_remove()
            self.combo_conta.grid_remove()
            self.lbl_cartao.grid(row=1, column=0, padx=(12, 6), pady=(0, 10), sticky="w")
            self.combo_cartao.grid(row=1, column=1, sticky="w", pady=(0, 10))
            self.btn_novo_cartao.grid(row=1, column=2, padx=(8, 12), pady=(0, 10))
        else:
            # Mostra conta, oculta cartão
            self.lbl_cartao.grid_remove()
            self.combo_cartao.grid_remove()
            self.btn_novo_cartao.grid_remove()
            self.lbl_conta.grid(row=1, column=0, padx=(12, 6), pady=(0, 10), sticky="w")
            self.combo_conta.grid(row=1, column=1, sticky="w", pady=(0, 10))

    def _get_ids(self):
        """Retorna (tipo_extrato, conta_id, cartao_id) conforme seleção."""
        tipo = self.var_tipo.get()
        if tipo == "cartao":
            nome = self.var_cartao.get()
            cartao_id = self._cartoes.get(nome)
            return "cartao", None, cartao_id
        else:
            nome = self.var_conta.get()
            conta_id = self._contas.get(nome)
            return "bancario", conta_id, None

    def _dialog_novo_cartao(self):
        """Cadastro rápido de cartão de crédito."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Novo Cartão de Crédito")
        dialog.geometry("360x280")
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="💳 Novo Cartão",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 10))

        frame = ctk.CTkFrame(dialog, fg_color="transparent")
        frame.pack(padx=20, fill="x")

        ctk.CTkLabel(frame, text="Nome do cartão:").pack(anchor="w")
        e_nome = ctk.CTkEntry(frame, placeholder_text="Ex: Nubank Roxinho")
        e_nome.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(frame, text="Bandeira:").pack(anchor="w")
        var_band = ctk.StringVar(value="Visa")
        ctk.CTkComboBox(frame, variable=var_band,
                        values=["Visa", "Mastercard", "Elo", "Amex", "Hipercard", "Outros"],
                        state="readonly").pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(frame, text="Limite (R$):").pack(anchor="w")
        e_limite = ctk.CTkEntry(frame, placeholder_text="Ex: 5000")
        e_limite.pack(fill="x", pady=(0, 15))

        def salvar():
            nome = e_nome.get().strip()
            if not nome:
                return
            try:
                limite = float(e_limite.get().replace(",", ".")) if e_limite.get().strip() else None
            except ValueError:
                limite = None

            db = self.app._obter_db()
            try:
                from app.models import CartaoCredito
                c = CartaoCredito(nome=nome, bandeira=var_band.get(), limite=limite, ativo=True)
                db.add(c)
                db.commit()
            finally:
                db.close()

            self._carregar_contas_e_cartoes()
            dialog.destroy()

        ctk.CTkButton(dialog, text="💾 Salvar", command=salvar,
                      fg_color=COR_PRIMARIA).pack(pady=5, padx=20, fill="x")

    def _log(self, texto: str):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {texto}\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _mostrar_progresso(self):
        self.prg_import.grid()
        self.prg_import.start(30)

    def _ocultar_progresso(self):
        self.prg_import.stop()
        self.prg_import.grid_remove()

    def _dialog_pedir_senha_pdf(self, caminho: str, tipo: str,
                                 conta_id, cartao_id, msg_erro: str = None):
        """Diálogo para pedir senha de PDF protegido antes de importar."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("PDF Protegido")
        dlg.geometry("420x240")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.lift()

        ctk.CTkLabel(dlg, text="🔒  PDF Protegido por Senha",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=COR_TEXTO).pack(pady=(20, 6))
        ctk.CTkLabel(dlg, text=os.path.basename(caminho),
                     text_color=COR_TEXTO_SUAVE, font=ctk.CTkFont(size=11)).pack()

        if msg_erro:
            ctk.CTkLabel(dlg, text=msg_erro, text_color=COR_PERIGO,
                         font=ctk.CTkFont(size=11)).pack(pady=(4, 0))

        entry = ctk.CTkEntry(dlg, show="*", width=320,
                              placeholder_text="Digite a senha do arquivo...")
        entry.pack(pady=14)
        entry.focus()

        def _confirmar():
            s = entry.get().strip()
            if not s:
                return
            if not messagebox.askyesno(
                "Confirmar Inclusão",
                f"Deseja incluir os dados de '{os.path.basename(caminho)}' no banco?",
                parent=dlg,
            ):
                self._log("Inclusão cancelada pelo usuário.")
                return
            dlg.destroy()
            self._log(f"Importando PDF com senha: {os.path.basename(caminho)}...")
            self._mostrar_progresso()
            threading.Thread(target=self._executar_importacao,
                             args=("pdf", caminho, tipo, conta_id, cartao_id, s),
                             daemon=True).start()

        btns = ctk.CTkFrame(dlg, fg_color="transparent")
        btns.pack()
        ctk.CTkButton(btns, text="✅ Importar", width=130,
                      fg_color=COR_PRIMARIA, command=_confirmar).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Cancelar", width=100,
                      fg_color=COR_SECUNDARIA, command=dlg.destroy).pack(side="left", padx=6)
        entry.bind("<Return>", lambda e: _confirmar())

    # --------------------------------------------------
    # Fluxo de Importar & Classificar Documento
    # --------------------------------------------------

    def _importar_documento(self):
        """Abre file dialog para qualquer formato e inicia o fluxo de análise + confirmação."""
        formatos = [
            ("Todos os documentos suportados",
             "*.pdf *.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp *.docx *.doc *.txt"),
            ("PDF", "*.pdf"),
            ("Imagens", "*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp"),
            ("Word",    "*.docx *.doc"),
            ("Texto",   "*.txt"),
            ("Todos os arquivos", "*.*"),
        ]
        caminho = filedialog.askopenfilename(title="Selecionar Documento", filetypes=formatos)
        if not caminho:
            return

        self._log(f"Analisando documento: {os.path.basename(caminho)}...")
        self._mostrar_progresso()
        threading.Thread(
            target=self._executar_analise_documento,
            args=(caminho,),
            daemon=True,
        ).start()

    def _executar_analise_documento(self, caminho: str, senha=None):
        """Roda a análise do documento em thread separada (não bloqueia a UI)."""
        try:
            from app.services.import_service import ImportService
            from app.services.ocr_service import DocumentoProtegidoError
        except ImportError as ie:
            _after_seguro(self, 0, self._ocultar_progresso)
            _after_seguro(self, 0, lambda: messagebox.showerror(
                "Erro", f"Não foi possível carregar os serviços: {ie}"))
            return

        erro    = None
        analise = None
        try:
            db = self.app._obter_db()
            try:
                analise = ImportService(db).analisar_documento(caminho, senha=senha)
            finally:
                db.close()
        except DocumentoProtegidoError:
            _after_seguro(self, 0, self._ocultar_progresso)
            _after_seguro(self, 0, lambda c=caminho: self._dialog_pedir_senha(c))
            return
        except ValueError as e:
            if "senha incorreta" in str(e).lower():
                _after_seguro(self, 0, self._ocultar_progresso)
                _after_seguro(self, 0, lambda c=caminho: self._dialog_pedir_senha(
                    c, mensagem="❌ Senha incorreta. Tente novamente."
                ))
                return
            erro = str(e)
        except Exception as e:
            erro = str(e)

        _after_seguro(self, 0, self._ocultar_progresso)

        if erro:
            _after_seguro(self, 0, lambda e=erro: (
                self._log(f"❌ Erro ao analisar: {e}"),
                messagebox.showerror("Erro na Análise", e),
            ))
        else:
            _after_seguro(
                self,
                0,
                lambda a=analise, c=caminho, s=senha: self._apos_analise_documento(a, c, s),
            )

    def _apos_analise_documento(self, analise: dict, caminho: str, senha=None):
        """Exibe retorno claro da análise antes de abrir a tela de confirmação."""
        tipo = analise.get("tipo_detectado", "desconhecido")
        nome = analise.get("nome_tipo", "Tipo não identificado")
        confianca = str(analise.get("confianca", "baixa")).upper()

        if tipo == "desconhecido":
            msg = (
                "Não consegui identificar automaticamente o tipo do documento.\n\n"
                "Você poderá selecionar manualmente na próxima tela para concluir a importação."
            )
            self._log("⚠️ Documento não reconhecido automaticamente. Solicitar seleção manual.")
            messagebox.showwarning("Documento não reconhecido", msg)
        else:
            self._log(f"✅ Documento reconhecido: {nome} (confiança: {confianca}).")

        self._dialog_confirmar_documento(analise, caminho, senha=senha)

    def _dialog_pedir_senha(self, caminho: str, mensagem: str = None):
        """
        Diálogo modal para solicitar a senha de abertura de um documento protegido.
        Ao confirmar, relança a análise passando a senha informada.
        """
        dialog = ctk.CTkToplevel(self)
        dialog.title("🔒 Documento Protegido")
        dialog.geometry("420x260")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.lift()
        dialog.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            dialog,
            text="🔒  Documento Protegido por Senha",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COR_TEXTO,
        ).grid(row=0, column=0, pady=(20, 6), padx=24, sticky="w")

        import os as _os
        ctk.CTkLabel(
            dialog,
            text=f"Arquivo: {_os.path.basename(caminho)}",
            font=ctk.CTkFont(size=11),
            text_color=COR_TEXTO_SUAVE,
        ).grid(row=1, column=0, padx=24, sticky="w")

        if mensagem:
            ctk.CTkLabel(
                dialog,
                text=mensagem,
                font=ctk.CTkFont(size=11),
                text_color=COR_PERIGO,
            ).grid(row=2, column=0, padx=24, pady=(6, 0), sticky="w")

        ctk.CTkLabel(
            dialog,
            text="Digite a senha do documento:",
            font=ctk.CTkFont(size=12),
            text_color=COR_TEXTO,
        ).grid(row=3, column=0, padx=24, pady=(14, 4), sticky="w")

        entry_senha = ctk.CTkEntry(
            dialog,
            placeholder_text="Senha...",
            show="*",
            width=280,
        )
        entry_senha.grid(row=4, column=0, padx=24, sticky="w")
        entry_senha.focus()

        barra = ctk.CTkFrame(dialog, fg_color="transparent")
        barra.grid(row=5, column=0, sticky="ew", padx=24, pady=(18, 16))
        barra.grid_columnconfigure(0, weight=1)

        def _tentar():
            senha_digitada = entry_senha.get()
            dialog.destroy()
            self._log(f"Tentando abrir com senha: {_os.path.basename(caminho)}...")
            import threading as _t
            _t.Thread(
                target=self._executar_analise_documento,
                args=(caminho,),
                kwargs={"senha": senha_digitada},
                daemon=True,
            ).start()

        entry_senha.bind("<Return>", lambda _: _tentar())

        ctk.CTkButton(
            barra,
            text="🔓  Tentar Abrir",
            fg_color=COR_SUCESSO, hover_color="#1E8449",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=_tentar,
        ).grid(row=0, column=1, padx=(8, 0))

        ctk.CTkButton(
            barra,
            text="Cancelar",
            fg_color="transparent", border_width=1,
            command=dialog.destroy,
        ).grid(row=0, column=0, sticky="e")

    def _dialog_confirmar_documento(self, analise: dict, caminho: str, senha=None):
        """
        Exibe o diálogo de confirmação do tipo de documento:
          - Preview do arquivo (imagem ou texto)
          - Tipo detectado automaticamente
          - 5 opções de tipo para o usuário confirmar/corrigir
          - Seletor de conta/cartão conforme o tipo
          - Botão "Confirmar e Importar"
        """
        dialog = ctk.CTkToplevel(self)
        dialog.title("🔍 Confirmar Tipo de Documento")
        dialog.geometry("1020x760")
        dialog.resizable(True, True)
        dialog.grab_set()
        dialog.lift()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(2, weight=1)

        # ── Cabeçalho ───────────────────────────────────────────────────
        ctk.CTkLabel(
            dialog, text="🔍  Confirmar Tipo de Documento",
            font=ctk.CTkFont(size=17, weight="bold"), text_color=COR_TEXTO,
        ).grid(row=0, column=0, pady=(18, 4), padx=20, sticky="w")

        ctk.CTkLabel(
            dialog,
            text=f"Arquivo: {analise['arquivo_nome']}",
            font=ctk.CTkFont(size=11), text_color=COR_TEXTO_SUAVE,
        ).grid(row=1, column=0, padx=20, sticky="w")

        # ── Área central: preview + seleção ─────────────────────────────
        centro = ctk.CTkFrame(dialog, fg_color="transparent")
        centro.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)
        centro.grid_columnconfigure(0, weight=1)
        centro.grid_columnconfigure(1, weight=1)
        centro.grid_rowconfigure(0, weight=1)

        # -- Coluna esquerda: preview -------------------------------------
        frame_prev = ctk.CTkFrame(centro, fg_color=COR_CARD, corner_radius=12)
        frame_prev.grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        frame_prev.grid_columnconfigure(0, weight=1)
        frame_prev.grid_rowconfigure(1, weight=1)

        # ── Cabeçalho do preview com controles de zoom ──────────────────
        frame_prev_hdr = ctk.CTkFrame(frame_prev, fg_color="transparent")
        frame_prev_hdr.grid(row=0, column=0, pady=(10, 4), padx=12, sticky="ew")
        frame_prev_hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame_prev_hdr, text="Pré-visualização",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO,
        ).grid(row=0, column=0, sticky="w")

        ext = analise["extensao"].lower()
        imagens_ext = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}

        if ext in imagens_ext:
            try:
                from PIL import Image as PILImage, ImageTk
                _img_orig = PILImage.open(caminho)

                # Zoom inicial: caber no painel (~450×390 px)
                _fit_scale = min(450 / _img_orig.width, 390 / _img_orig.height, 1.0)
                _zoom_state = {"level": _fit_scale, "photo": None}

                # ── Controles de zoom ──────────────────────────────────
                frame_zoom = ctk.CTkFrame(frame_prev_hdr, fg_color="transparent")
                frame_zoom.grid(row=0, column=1, sticky="e")

                lbl_pct = ctk.CTkLabel(frame_zoom, text="",
                                       width=46, font=ctk.CTkFont(size=11),
                                       text_color=COR_TEXTO_SUAVE)

                def _render_zoom():
                    lv = _zoom_state["level"]
                    w = max(1, int(_img_orig.width  * lv))
                    h = max(1, int(_img_orig.height * lv))
                    _resized = _img_orig.resize((w, h), PILImage.LANCZOS)
                    _photo = ImageTk.PhotoImage(_resized)
                    _zoom_state["photo"] = _photo   # previne GC
                    _canvas.delete("all")
                    _canvas.create_image(0, 0, anchor="nw", image=_photo)
                    _canvas.configure(scrollregion=(0, 0, w, h))
                    lbl_pct.configure(text=f"{int(lv * 100)}%")

                def _zoom_in(*_):
                    _zoom_state["level"] = min(_zoom_state["level"] + 0.25, 4.0)
                    _render_zoom()

                def _zoom_out(*_):
                    _zoom_state["level"] = max(_zoom_state["level"] - 0.25, 0.25)
                    _render_zoom()

                def _zoom_fit(*_):
                    _zoom_state["level"] = _fit_scale
                    _render_zoom()

                def _wheel_zoom(event):
                    if event.delta > 0:
                        _zoom_in()
                    else:
                        _zoom_out()

                ctk.CTkButton(frame_zoom, text="🔎+", width=46, height=24,
                              command=_zoom_in, font=ctk.CTkFont(size=12),
                              ).pack(side="left", padx=(0, 2))
                lbl_pct.pack(side="left", padx=2)
                ctk.CTkButton(frame_zoom, text="🔎−", width=46, height=24,
                              command=_zoom_out, font=ctk.CTkFont(size=12),
                              ).pack(side="left", padx=2)
                ctk.CTkButton(frame_zoom, text="↺ Fit", width=58, height=24,
                              command=_zoom_fit, font=ctk.CTkFont(size=11),
                              ).pack(side="left", padx=(4, 0))

                # ── Canvas scrollável ──────────────────────────────────
                _canvas_outer = tk.Frame(frame_prev, bg="#0A1A2E")
                _canvas_outer.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
                _canvas_outer.grid_rowconfigure(0, weight=1)
                _canvas_outer.grid_columnconfigure(0, weight=1)

                _canvas = tk.Canvas(_canvas_outer, bg="#0A1A2E",
                                    highlightthickness=0, cursor="fleur")
                _sb_v = tk.Scrollbar(_canvas_outer, orient="vertical",   command=_canvas.yview)
                _sb_h = tk.Scrollbar(_canvas_outer, orient="horizontal", command=_canvas.xview)
                _canvas.configure(yscrollcommand=_sb_v.set, xscrollcommand=_sb_h.set)
                _sb_v.grid(row=0, column=1, sticky="ns")
                _sb_h.grid(row=1, column=0, sticky="ew")
                _canvas.grid(row=0, column=0, sticky="nsew")

                _canvas.bind("<MouseWheel>", _wheel_zoom)
                _render_zoom()

            except Exception:
                ctk.CTkLabel(
                    frame_prev, text="[Pré-visualização indisponível]",
                    text_color=COR_TEXTO_SUAVE,
                ).grid(row=1, column=0, padx=12, pady=20)
        else:
            txt_prev = ctk.CTkTextbox(
                frame_prev, fg_color="#0A1A2E", corner_radius=8,
                font=ctk.CTkFont(size=11, family="Courier New"),
                wrap="word",
            )
            txt_prev.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
            frame_prev.grid_rowconfigure(1, weight=1)
            conteudo = analise.get("texto_preview", "(sem texto extraído)")
            txt_prev.insert("1.0", conteudo or "(sem texto extraído)")
            txt_prev.configure(state="disabled")

        # -- Coluna direita: tipo detectado + seleção ----------------------
        frame_sel = ctk.CTkFrame(centro, fg_color=COR_CARD, corner_radius=12)
        frame_sel.grid(row=0, column=1, padx=(8, 0), sticky="nsew")
        frame_sel.grid_columnconfigure(0, weight=1)

        confianca_cor = {
            "alta":  COR_SUCESSO,
            "media": COR_AVISO,
            "baixa": COR_PERIGO,
        }.get(analise["confianca"], COR_TEXTO_SUAVE)

        ctk.CTkLabel(
            frame_sel, text="Tipo detectado automaticamente:",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO,
        ).pack(pady=(14, 4), padx=14, anchor="w")

        badge_frame = ctk.CTkFrame(frame_sel, fg_color="#0A1A2E", corner_radius=8)
        badge_frame.pack(padx=14, fill="x", pady=(0, 4))

        ctk.CTkLabel(
            badge_frame,
            text=f"{analise['emoji_tipo']}  {analise['nome_tipo']}",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=COR_TEXTO,
        ).pack(side="left", padx=10, pady=8)

        ctk.CTkLabel(
            badge_frame,
            text=f"Confiança: {analise['confianca'].upper()}",
            font=ctk.CTkFont(size=10), text_color=confianca_cor,
        ).pack(side="right", padx=10)

        pre = analise.get("pre_lancamento", {}) or {}
        resumo = ctk.CTkFrame(frame_sel, fg_color="#0A1A2E", corner_radius=8)
        resumo.pack(padx=14, fill="x", pady=(8, 6))

        ctk.CTkLabel(
            resumo,
            text="Resumo da leitura (antes de salvar)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COR_TEXTO,
        ).pack(anchor="w", padx=10, pady=(8, 2))

        for linha, cor in self._linhas_pre_lancamento(analise, pre):
            ctk.CTkLabel(
                resumo,
                text=linha,
                font=ctk.CTkFont(size=10),
                text_color=cor,
                justify="left",
                anchor="w",
            ).pack(anchor="w", padx=10, pady=1)

        ctk.CTkLabel(
            resumo,
            text="Confira os dados acima e confirme o tipo para concluir o lançamento.",
            font=ctk.CTkFont(size=10),
            text_color=COR_TEXTO,
            justify="left",
            anchor="w",
        ).pack(anchor="w", padx=10, pady=(4, 8))

        ctk.CTkLabel(
            frame_sel, text="Confirme ou selecione o tipo correto:",
            font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE,
        ).pack(pady=(6, 4), padx=14, anchor="w")

        TIPOS = [
            ("comprovante_pagamento_bancario", "🏦",  "Comprovante Bancário (PIX/Transferência)"),
            ("recibo_despesa",     "🧾",  "Recibo de Despesa"),
            ("nota_fiscal",        "🧾",  "Nota Fiscal de Despesa"),
            ("comprovante_compra", "🏷️", "Comprovante de Compra (Cartão)"),
            ("boleto",             "📋",  "Boleto Bancário"),
            ("extrato_bancario",   "🏦",  "Extrato Bancário"),
            ("extrato_cartao",     "💳",  "Extrato de Cartão de Crédito"),
        ]

        mapa_tipos = {chave: nome for chave, _emoji, nome in TIPOS}
        mapa_tipo_para_rotulo = {
            chave: f"{emoji}  {nome}" for chave, emoji, nome in TIPOS
        }
        mapa_rotulo_para_tipo = {
            rotulo: chave for chave, rotulo in mapa_tipo_para_rotulo.items()
        }

        tipo_inicial = (
            analise["tipo_detectado"]
            if analise["tipo_detectado"] in mapa_tipo_para_rotulo
            else "extrato_bancario"
        )

        var_tipo_doc = ctk.StringVar(
            value=mapa_tipo_para_rotulo[tipo_inicial]
        )

        ctk.CTkComboBox(
            frame_sel,
            variable=var_tipo_doc,
            values=list(mapa_tipo_para_rotulo.values()),
            state="readonly",
            width=420,
            command=lambda _valor: _atualizar_campos(),
        ).pack(padx=14, pady=(0, 8), anchor="w")

        # Campos dinâmicos (serão exibidos/ocultados conforme o tipo)
        var_conta  = ctk.StringVar(value="— Nenhuma —")
        var_cartao = ctk.StringVar(value="— Nenhum —")
        nomes_conta  = ["— Nenhuma —"] + list(getattr(self, "_contas",  {}).keys())
        nomes_cartao = ["— Nenhum —"]  + list(getattr(self, "_cartoes", {}).keys())

        combo_conta = ctk.CTkComboBox(
            frame_sel, variable=var_conta,
            values=nomes_conta, state="readonly", width=220,
        )
        combo_cartao = ctk.CTkComboBox(
            frame_sel, variable=var_cartao,
            values=nomes_cartao, state="readonly", width=220,
        )
        lbl_conta  = ctk.CTkLabel(frame_sel, text="Conta bancária:",
                                   font=ctk.CTkFont(size=11), text_color=COR_TEXTO_SUAVE)
        lbl_cartao = ctk.CTkLabel(frame_sel, text="Cartão de crédito:",
                                   font=ctk.CTkFont(size=11), text_color=COR_TEXTO_SUAVE)
        lbl_desc   = ctk.CTkLabel(frame_sel, text="Descrição (opcional):",
                                   font=ctk.CTkFont(size=11), text_color=COR_TEXTO_SUAVE)
        entry_desc = ctk.CTkEntry(frame_sel, placeholder_text="Ex: Padaria Central", width=220)

        campos_dinamicos = ctk.CTkFrame(frame_sel, fg_color="transparent")
        campos_dinamicos.pack(padx=14, fill="x")

        def _atualizar_campos():
            for w in campos_dinamicos.winfo_children():
                w.destroy()
            tipo = mapa_rotulo_para_tipo.get(var_tipo_doc.get(), "extrato_bancario")
            if tipo == "extrato_bancario":
                ctk.CTkLabel(campos_dinamicos, text="Conta bancária:",
                             font=ctk.CTkFont(size=11),
                             text_color=COR_TEXTO_SUAVE).pack(anchor="w", pady=(4, 2))
                ctk.CTkComboBox(campos_dinamicos, variable=var_conta,
                                values=nomes_conta, state="readonly",
                                width=220).pack(anchor="w", pady=(0, 6))
            elif tipo == "comprovante_pagamento_bancario":
                ctk.CTkLabel(campos_dinamicos, text="Conta bancária:",
                             font=ctk.CTkFont(size=11),
                             text_color=COR_TEXTO_SUAVE).pack(anchor="w", pady=(4, 2))
                ctk.CTkComboBox(campos_dinamicos, variable=var_conta,
                                values=nomes_conta, state="readonly",
                                width=220).pack(anchor="w", pady=(0, 6))
                ctk.CTkLabel(campos_dinamicos, text="Descrição (opcional):",
                             font=ctk.CTkFont(size=11),
                             text_color=COR_TEXTO_SUAVE).pack(anchor="w", pady=(4, 2))
                e = ctk.CTkEntry(campos_dinamicos,
                                 placeholder_text="Ex: PIX para João", width=220)
                e.pack(anchor="w", pady=(0, 6))
                campos_dinamicos._entry_desc = e
            elif tipo in ("extrato_cartao", "comprovante_compra"):
                ctk.CTkLabel(campos_dinamicos, text="Cartão de crédito:",
                             font=ctk.CTkFont(size=11),
                             text_color=COR_TEXTO_SUAVE).pack(anchor="w", pady=(4, 2))
                ctk.CTkComboBox(campos_dinamicos, variable=var_cartao,
                                values=nomes_cartao, state="readonly",
                                width=220).pack(anchor="w", pady=(0, 6))
            elif tipo in ("recibo_despesa", "nota_fiscal", "boleto"):
                ctk.CTkLabel(campos_dinamicos, text="Descrição (opcional):",
                             font=ctk.CTkFont(size=11),
                             text_color=COR_TEXTO_SUAVE).pack(anchor="w", pady=(4, 2))
                e = ctk.CTkEntry(campos_dinamicos,
                                 placeholder_text="Ex: Mercado Extra", width=220)
                e.pack(anchor="w", pady=(0, 6))
                # guarda referência para leitura no confirmar
                campos_dinamicos._entry_desc = e

        ctk.CTkFrame(frame_sel, height=1, fg_color=COR_SECUNDARIA).pack(
            fill="x", padx=14, pady=8
        )
        _atualizar_campos()  # estado inicial

        # ── Barra de botões ──────────────────────────────────────────────
        barra = ctk.CTkFrame(dialog, fg_color="transparent")
        barra.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 16))
        barra.grid_columnconfigure(0, weight=1)

        def _confirmar():
            tipo_sel = mapa_rotulo_para_tipo.get(var_tipo_doc.get(), "extrato_bancario")
            conta_id  = getattr(self, "_contas",  {}).get(var_conta.get())
            cartao_id = getattr(self, "_cartoes", {}).get(var_cartao.get())
            # Tenta ler o entry de descrição (se existir)
            desc_man = None
            if hasattr(campos_dinamicos, "_entry_desc"):
                desc_man = campos_dinamicos._entry_desc.get().strip() or None

            confirmar = messagebox.askyesno(
                "Confirmar Inclusão",
                (
                    f"Deseja incluir no banco os dados de '{analise['arquivo_nome']}'\n"
                    f"como '{mapa_tipos.get(tipo_sel, tipo_sel)}'?"
                ),
                parent=dialog,
            )
            if not confirmar:
                self._log("Inclusão cancelada pelo usuário antes da gravação.")
                return

            dialog.destroy()
            self._mostrar_progresso()
            self._log(
                f"Importando '{analise['arquivo_nome']}' como "
                f"{mapa_tipos.get(tipo_sel, tipo_sel)}..."
            )
            threading.Thread(
                target=self._executar_importacao_documento,
                args=(
                    caminho,
                    tipo_sel,
                    conta_id,
                    cartao_id,
                    desc_man,
                    senha,
                    analise.get("texto_completo"),
                    analise.get("tipo_detectado"),
                ),
                daemon=True,
            ).start()

        ctk.CTkButton(
            barra,
            text="✅  Confirmar e Importar",
            fg_color=COR_SUCESSO, hover_color="#1E8449",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=_confirmar,
        ).grid(row=0, column=1, padx=(8, 0))

        ctk.CTkButton(
            barra,
            text="❌  Cancelar",
            fg_color="transparent", border_width=1,
            command=dialog.destroy,
        ).grid(row=0, column=0, sticky="e")

    def _linhas_pre_lancamento(self, analise: dict, pre: dict) -> list[tuple[str, str]]:
        """Converte a prévia de leitura em linhas amigáveis para o usuário."""
        linhas = []
        tipo = analise.get("nome_tipo", "Documento")
        linhas.append((f"Tipo identificado: {tipo}", COR_TEXTO_SUAVE))

        confianca = (analise.get("confianca") or "").lower()
        if confianca in ("media", "baixa"):
            nivel = "MÉDIA" if confianca == "media" else "BAIXA"
            linhas.append((
                f"Atenção: confiança {nivel}. Revise os campos antes de confirmar.",
                COR_AVISO if confianca == "media" else COR_PERIGO,
            ))

        qtd = pre.get("qtd_transacoes")
        if qtd is not None:
            linhas.append((f"Transações lidas: {qtd}", COR_TEXTO_SUAVE))
            if qtd == 0:
                linhas.append((
                    "Atenção: nenhuma transação foi encontrada no texto extraído.",
                    COR_PERIGO,
                ))

        amostras = pre.get("amostra_transacoes") or []
        if amostras:
            linhas.append(("Amostra lida:", COR_TEXTO_SUAVE))
            for item in amostras[:3]:
                d = item.get("data") or "--/--/----"
                desc = item.get("descricao") or "Sem descrição"
                valor_item = item.get("valor")
                tipo_item = (item.get("tipo") or "").lower()
                sinal = "-" if tipo_item == "debito" else "+"
                valor_txt = self._formatar_moeda_br(valor_item) if valor_item is not None else "R$ 0,00"
                linhas.append((f"  {d} | {sinal}{valor_txt} | {desc[:46]}", COR_TEXTO_SUAVE))

        valor = pre.get("valor")
        if valor is not None:
            linhas.append((f"Valor sugerido: {self._formatar_moeda_br(valor)}", COR_TEXTO_SUAVE))
        else:
            linhas.append(("Valor sugerido: não identificado", COR_AVISO))

        tipo_mov = pre.get("tipo_movimento")
        if tipo_mov:
            mapa_tipo = {
                "debito": "Débito",
                "credito": "Crédito",
                "evento_pendente": "Conta a pagar (evento)",
            }
            linhas.append((f"Movimento sugerido: {mapa_tipo.get(tipo_mov, tipo_mov)}", COR_TEXTO_SUAVE))
        else:
            linhas.append(("Movimento sugerido: não identificado", COR_AVISO))

        descricao = pre.get("descricao")
        if descricao:
            linhas.append((f"Descrição sugerida: {descricao}", COR_TEXTO_SUAVE))
        else:
            linhas.append(("Descrição sugerida: não identificada", COR_AVISO))

        categoria = pre.get("categoria_sugerida")
        if categoria:
            linhas.append((f"Categoria sugerida: {categoria}", COR_TEXTO_SUAVE))
        else:
            linhas.append(("Categoria sugerida: não identificada", COR_AVISO))

        venc = pre.get("vencimento")
        if venc:
            linhas.append((f"Vencimento identificado: {venc}", COR_TEXTO_SUAVE))

        if len(linhas) == 1:
            linhas.append((
                "Não foi possível extrair campos objetivos; confirme manualmente abaixo.",
                COR_PERIGO,
            ))

        return linhas

    @staticmethod
    def _formatar_moeda_br(valor) -> str:
        try:
            numero = float(valor)
        except Exception:
            return "R$ 0,00"
        bruto = f"{numero:,.2f}"
        return "R$ " + bruto.replace(",", "X").replace(".", ",").replace("X", ".")

    def _executar_importacao_documento(
        self,
        caminho: str,
        tipo_documento: str,
        conta_id,
        cartao_id,
        descricao_manual,
        senha=None,
        texto_analise: Optional[str] = None,
        tipo_detectado: Optional[str] = None,
    ):
        """Executa a importação confirmada em thread separada."""
        db        = self.app._obter_db()
        resultado = None
        erro      = None
        try:
            from app.services.import_service import ImportService
            svc = ImportService(db)
            resultado = svc.importar_por_tipo_documento(
                caminho          = caminho,
                tipo_documento   = tipo_documento,
                conta_id         = conta_id,
                cartao_id        = cartao_id,
                descricao_manual = descricao_manual,
                senha            = senha,
            )
            if resultado and texto_analise:
                svc.registrar_feedback_tipo_documento(
                    texto=texto_analise,
                    tipo_confirmado=tipo_documento,
                    tipo_detectado=tipo_detectado,
                )
        except BaseException as e:
            erro = str(e) or type(e).__name__
        finally:
            db.close()

        _after_seguro(self, 0, self._ocultar_progresso)

        if erro:
            _after_seguro(self, 0, lambda e=erro: self._dialog_erro_importacao(e))
        elif resultado:
            tipo_map = {
                "comprovante_pagamento_bancario": "Comprovante Bancário",
                "recibo_despesa":     "Recibo",
                "nota_fiscal":        "Nota Fiscal",
                "boleto":             "Boleto",
                "comprovante_compra": "Comprovante",
                "extrato_bancario":   "Extrato Bancário",
                "extrato_cartao":     "Extrato Cartão",
            }
            nome_tipo = tipo_map.get(tipo_documento, tipo_documento)

            if tipo_documento in ("extrato_bancario", "extrato_cartao"):
                msg = (f"✅ [{nome_tipo}] "
                       f"{resultado.get('importadas', 0)} importadas | "
                       f"{resultado.get('ignoradas', 0)} ignoradas")
                _after_seguro(self, 0, lambda: self._log(msg))
                if resultado.get("extrato_id"):
                    _after_seguro(self, 100, lambda r=resultado, td=tipo_documento,
                                  cid=resultado.get("cartao_id", cartao_id):
                                  self._dialog_resultado(r, td, cid))
            else:
                valor_fmt = f"R$ {resultado.get('valor', 0):.2f}".replace(".", ",")
                if tipo_documento == "boleto":
                    msg = (f"✅ [{nome_tipo}] Evento criado | "
                           f"Valor: {valor_fmt} | "
                           f"Vencimento: {resultado.get('vencimento', '—')}")
                else:
                    msg = f"✅ [{nome_tipo}] Transação criada | Valor: {valor_fmt}"
                _after_seguro(self, 0, lambda m=msg: (
                    self._log(m),
                    messagebox.showinfo("✅ Importado com Sucesso", m),
                ))

    # --------------------------------------------------
    # Importadores por formato (avançado)
    # --------------------------------------------------

    def _importar_pdf(self):
        # PDF agora segue o fluxo de análise + confirmação para permitir
        # ajuste manual do tipo do documento antes da importação.
        self._importar_documento()

    def _importar_csv(self):
        caminho = filedialog.askopenfilename(
            title="Selecionar CSV", filetypes=[("CSV", "*.csv"), ("Todos", "*.*")]
        )
        if not caminho:
            return
        tipo, conta_id, cartao_id = self._get_ids()
        if not messagebox.askyesno(
            "Confirmar Inclusão",
            f"Deseja incluir os dados do arquivo '{os.path.basename(caminho)}' no banco?",
            parent=self,
        ):
            self._log("Inclusão cancelada pelo usuário.")
            return
        self._log(f"Importando CSV ({tipo}): {os.path.basename(caminho)}...")
        threading.Thread(target=self._executar_importacao,
                         args=("csv", caminho, tipo, conta_id, cartao_id), daemon=True).start()

    def _importar_excel(self):
        caminho = filedialog.askopenfilename(
            title="Selecionar Excel", filetypes=[("Excel", "*.xlsx *.xls"), ("Todos", "*.*")]
        )
        if not caminho:
            return
        tipo, conta_id, cartao_id = self._get_ids()
        if not messagebox.askyesno(
            "Confirmar Inclusão",
            f"Deseja incluir os dados do arquivo '{os.path.basename(caminho)}' no banco?",
            parent=self,
        ):
            self._log("Inclusão cancelada pelo usuário.")
            return
        self._log(f"Importando Excel ({tipo}): {os.path.basename(caminho)}...")
        threading.Thread(target=self._executar_importacao,
                         args=("excel", caminho, tipo, conta_id, cartao_id), daemon=True).start()

    def _importar_ofx(self):
        caminho = filedialog.askopenfilename(
            title="Selecionar OFX", filetypes=[("OFX", "*.ofx *.qfx"), ("Todos", "*.*")]
        )
        if not caminho:
            return
        tipo, conta_id, cartao_id = self._get_ids()
        if not messagebox.askyesno(
            "Confirmar Inclusão",
            f"Deseja incluir os dados do arquivo '{os.path.basename(caminho)}' no banco?",
            parent=self,
        ):
            self._log("Inclusão cancelada pelo usuário.")
            return
        self._log(f"Importando OFX ({tipo}): {os.path.basename(caminho)}...")
        threading.Thread(target=self._executar_importacao,
                         args=("ofx", caminho, tipo, conta_id, cartao_id), daemon=True).start()

    def _executar_importacao(self, formato: str, caminho: str,
                              tipo: str = "bancario",
                              conta_id: Optional[int] = None,
                              cartao_id: Optional[int] = None,
                              senha: Optional[str] = None):
        db = self.app._obter_db()
        resultado = None
        erro      = None
        try:
            from app.services.import_service import ImportService
            svc = ImportService(db)
            kwargs = {"tipo_extrato": tipo, "conta_id": conta_id, "cartao_id": cartao_id}
            if formato == "pdf" and senha:
                kwargs["senha"] = senha
            metodos = {
                "pdf":   svc.importar_pdf,
                "csv":   svc.importar_csv,
                "excel": svc.importar_excel,
                "ofx":   svc.importar_ofx,
            }
            resultado = metodos[formato](caminho, **kwargs)
        except Exception as e:
            erro = str(e)
        finally:
            db.close()

        _after_seguro(self, 0, self._ocultar_progresso)

        if erro:
            _after_seguro(self, 0, lambda e=erro: self._dialog_erro_importacao(e))
        elif resultado and resultado.get("duplicado"):
            _after_seguro(self, 0, lambda r=resultado: self._dialog_duplicado(
                r, formato, caminho, tipo, conta_id, cartao_id))
        else:
            n = resultado.get('importadas', 0)
            msg = (f"✅ {n} transaç{'ão' if n==1 else 'ões'} importada{'s' if n!=1 else ''} | "
                   f"{resultado['ignoradas']} ignoradas")
            _after_seguro(self, 0, lambda: self._log(msg))
            _after_seguro(self, 100, lambda r=resultado, t=tipo,
                          cid=resultado.get("cartao_id", cartao_id):
                          self._dialog_resultado(r, t, cid))

    # --------------------------------------------------
    # Dialogs pós-importação
    # --------------------------------------------------

    def _dialog_erro_importacao(self, erro: str):
        self._log(f"❌ Erro: {erro}")
        dialog = ctk.CTkToplevel(self)
        dialog.title("❌ Erro na Importação")
        dialog.geometry("520x230")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.lift()
        ctk.CTkLabel(dialog, text="❌  Erro na Importação",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=COR_PERIGO).pack(pady=(22, 8))
        ctk.CTkLabel(dialog, text=erro,
                     text_color=COR_TEXTO_SUAVE, wraplength=480,
                     justify="left").pack(padx=20, pady=(0, 14))
        ctk.CTkButton(dialog, text="Fechar",
                      command=dialog.destroy).pack(pady=8, padx=24, fill="x")

    def _dialog_duplicado(self, resultado: dict, formato: str, caminho: str,
                           tipo: str, conta_id, cartao_id):
        arq = os.path.basename(caminho)
        self._log(f"⚠️ '{arq}' já importado (Extrato #{resultado['extrato_id']}).")

        dialog = ctk.CTkToplevel(self)
        dialog.title("⚠️ Arquivo já Importado")
        dialog.geometry("520x320")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.lift()

        ctk.CTkLabel(dialog, text="⚠️  Arquivo Já Importado",
                     font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=COR_AVISO).pack(pady=(22, 6))

        imp_em    = resultado.get("importado_em", "—")
        total_ant = resultado.get("total_anterior", "?")
        info_txt  = (
            f"O arquivo  '{arq}'  já foi importado anteriormente.\n\n"
            f"📅  Importado em:  {imp_em}\n"
            f"📋  Transações:  {total_ant}\n"
            f"🆔  Extrato ID:  #{resultado['extrato_id']}"
        )
        ctk.CTkLabel(dialog, text=info_txt,
                     text_color=COR_TEXTO_SUAVE, justify="left",
                     font=ctk.CTkFont(size=12)).pack(padx=24, pady=(0, 8))

        ctk.CTkFrame(dialog, height=1, fg_color=COR_SECUNDARIA).pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(dialog, text="O que deseja fazer?",
                     text_color=COR_TEXTO,
                     font=ctk.CTkFont(size=12, weight="bold")).pack(pady=(4, 4))

        btn_f = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_f.pack(padx=24, pady=4, fill="x")

        def _ver_existentes():
            dialog.destroy()
            self.app._navegar("transacoes")

        def _reimportar():
            dialog.destroy()
            self._log(f"🔄 Re-importando '{arq}' — apagando dados anteriores...")
            threading.Thread(
                target=self._executar_reimportacao,
                args=(formato, caminho, tipo, conta_id, cartao_id,
                      resultado["extrato_id"]),
                daemon=True
            ).start()

        ctk.CTkButton(btn_f, text="📋  Ver transações existentes",
                      fg_color=COR_PRIMARIA,
                      command=_ver_existentes).pack(fill="x", pady=3)
        ctk.CTkButton(btn_f, text="🔄  Re-importar  (substitui os dados anteriores)",
                      fg_color=COR_AVISO, hover_color="#D68910",
                      command=_reimportar).pack(fill="x", pady=3)
        ctk.CTkButton(btn_f, text="❌  Cancelar",
                      fg_color="transparent", border_width=1,
                      command=dialog.destroy).pack(fill="x", pady=3)

    def _executar_reimportacao(self, formato: str, caminho: str,
                                tipo: str, conta_id, cartao_id,
                                extrato_id_antigo: int):
        db = self.app._obter_db()
        resultado = None
        erro      = None
        try:
            from app.services.import_service import ImportService
            from app.models import Transacao as _T, Extrato as _E
            db.query(_T).filter(_T.extrato_id == extrato_id_antigo).delete()
            ext_ant = db.query(_E).filter(_E.id == extrato_id_antigo).first()
            if ext_ant:
                db.delete(ext_ant)
            db.flush()
            svc    = ImportService(db)
            kwargs = {"tipo_extrato": tipo, "conta_id": conta_id, "cartao_id": cartao_id}
            metodos = {
                "pdf":   svc.importar_pdf,
                "csv":   svc.importar_csv,
                "excel": svc.importar_excel,
                "ofx":   svc.importar_ofx,
            }
            resultado = metodos[formato](caminho, **kwargs)
        except Exception as e:
            erro = str(e)
        finally:
            db.close()

        if erro:
            _after_seguro(self, 0, lambda e=erro: self._dialog_erro_importacao(e))
        else:
            msg = f"✅ Re-importado! {resultado['importadas']} transações"
            _after_seguro(self, 0, lambda: self._log(msg))
            _after_seguro(self, 100, lambda r=resultado, t=tipo,
                          cid=resultado.get("cartao_id", cartao_id):
                          self._dialog_resultado(r, t, cid))

    def _dialog_resultado(self, resultado: dict,
                           tipo: str = "bancario",
                           cartao_id: Optional[int] = None):
        """Mostra popup com todas as transações importadas e opção de editar."""
        from app.utils.helpers import formatar_moeda
        extrato_id = resultado.get("extrato_id")
        n_imp = resultado.get("importadas", 0)
        n_ign = resultado.get("ignoradas",  0)
        arq   = resultado.get("arquivo", "—")

        dialog = ctk.CTkToplevel(self)
        dialog.title("✅ Importação Concluída")
        dialog.geometry("940x580")
        dialog.grab_set()
        dialog.lift()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(1, weight=1)

        # — Cards de resumo —
        header = ctk.CTkFrame(dialog, fg_color=COR_CARD, corner_radius=10)
        header.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 8))
        for i in range(3):
            header.grid_columnconfigure(i, weight=1)

        def _card(parent, titulo, valor, cor, col):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.grid(row=0, column=col, padx=12, pady=12)
            ctk.CTkLabel(f, text=titulo, font=ctk.CTkFont(size=11),
                         text_color=COR_TEXTO_SUAVE).pack()
            ctk.CTkLabel(f, text=str(valor), font=ctk.CTkFont(size=22, weight="bold"),
                         text_color=cor).pack()

        _card(header, "✅ Importadas", n_imp, COR_SUCESSO, 0)
        _card(header, "⏭️ Ignoradas",  n_ign, COR_AVISO,   1)
        _card(header, "📄 Arquivo",    arq[:36], COR_TEXTO,  2)

        # — Tabela das transações importadas —
        frame_tab = ctk.CTkFrame(dialog, fg_color=COR_CARD, corner_radius=10)
        frame_tab.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 8))
        frame_tab.grid_columnconfigure(0, weight=1)
        frame_tab.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        style.configure("Res.Treeview",
                        background="#0F3460", foreground="white",
                        rowheight=26, fieldbackground="#0F3460",
                        font=("Segoe UI", 10))
        style.configure("Res.Treeview.Heading",
                        background="#2E86AB", foreground="white",
                        font=("Segoe UI", 10, "bold"))
        style.map("Res.Treeview", background=[("selected", "#2980B9")])

        cols = ("data", "descricao", "categoria", "tipo", "valor")
        tree = ttk.Treeview(frame_tab, columns=cols, show="headings", style="Res.Treeview")
        tree.heading("data",      text="Data");       tree.column("data",      width=90,  anchor="center")
        tree.heading("descricao", text="Descrição");  tree.column("descricao", width=340, anchor="w")
        tree.heading("categoria", text="Categoria");  tree.column("categoria", width=140, anchor="w")
        tree.heading("tipo",      text="Tipo");       tree.column("tipo",      width=75,  anchor="center")
        tree.heading("valor",     text="Valor (R$)"); tree.column("valor",     width=115, anchor="e")
        tree.tag_configure("debito",  foreground="#E74C3C")
        tree.tag_configure("credito", foreground="#27AE60")

        vsb = ttk.Scrollbar(frame_tab, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        vsb.grid(row=0, column=1, sticky="ns",    padx=(0, 6), pady=8)

        total_deb = 0.0
        if extrato_id:
            db = self.app._obter_db()
            try:
                from app.models import Transacao as _T
                trans = db.query(_T).filter(
                    _T.extrato_id == extrato_id
                ).order_by(_T.data).all()
                for t in trans:
                    cat      = t.categoria.nome if t.categoria else "—"
                    e_val    = t.tipo.value if hasattr(t.tipo, "value") else str(t.tipo)
                    tag      = "debito" if e_val == "debito" else "credito"
                    tipo_txt = "Débito" if tag == "debito" else "Crédito"
                    tree.insert("", "end", iid=str(t.id), tags=(tag,), values=(
                        t.data.strftime("%d/%m/%Y"),
                        t.descricao[:52],
                        cat,
                        tipo_txt,
                        formatar_moeda(t.valor),
                    ))
                    if tag == "debito":
                        total_deb += t.valor
            finally:
                db.close()

        # — Rodapé —
        footer = ctk.CTkFrame(dialog, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 15))

        ctk.CTkLabel(footer, text=f"Total débitos: {formatar_moeda(total_deb)}",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=COR_PERIGO).pack(side="left")

        def _revisar():
            dialog.destroy()
            self.app._navegar("transacoes")

        # Botão "Salvar na Agenda" — exibido somente em importações de cartão
        if tipo == "cartao":
            ctk.CTkButton(
                footer,
                text="📅 Salvar Fatura na Agenda",
                fg_color="#8E44AD", hover_color="#6C3483",
                command=lambda: self._dialog_salvar_fatura_agenda(
                    total_deb, cartao_id, dialog),
            ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(footer, text="✏️ Revisar e Editar Transações",
                      fg_color=COR_PRIMARIA,
                      command=_revisar).pack(side="right", padx=(8, 0))
        ctk.CTkButton(footer, text="✅ Fechar",
                      fg_color=COR_SUCESSO, hover_color="#1E8449",
                      command=dialog.destroy).pack(side="right")

    def _dialog_salvar_fatura_agenda(self, total_deb: float,
                                     cartao_id: Optional[int],
                                     dialog_pai=None):
        """
        Diálogo para salvar a fatura do cartão na Agenda Financeira.
        Preenche automaticamente o valor total e permite informar
        o código de barras e a data de vencimento.
        """
        # Tenta descobrir o nome do cartão e dia de vencimento
        nome_cartao = "Fatura Cartão"
        dia_venc    = None
        if cartao_id:
            try:
                from app.models import CartaoCredito as _CC
                db = self.app._obter_db()
                try:
                    cc = db.query(_CC).get(cartao_id)
                    if cc:
                        nome_cartao = f"Fatura {cc.nome}"
                        dia_venc    = cc.dia_vencimento
                finally:
                    db.close()
            except Exception:
                pass

        # Calcula data de vencimento provável (próximo mês)
        import calendar as _cal
        from datetime import date as _date
        hoje = _date.today()
        if dia_venc:
            mes_prox = hoje.month + 1 if hoje.month < 12 else 1
            ano_prox = hoje.year if hoje.month < 12 else hoje.year + 1
            ult_dia  = _cal.monthrange(ano_prox, mes_prox)[1]
            data_sug = _date(ano_prox, mes_prox, min(dia_venc, ult_dia))
        else:
            data_sug = hoje.replace(day=min(hoje.day + 30, 28))

        d = ctk.CTkToplevel(self)
        d.title("📅 Salvar Fatura na Agenda")
        d.geometry("440x460")
        d.resizable(False, False)
        d.grab_set()
        d.lift()

        ctk.CTkLabel(d, text="📅 Salvar Fatura na Agenda",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=COR_TEXTO).pack(pady=(18, 4))
        ctk.CTkLabel(d, text="A fatura será registrada como evento financeiro\npendente de pagamento.",
                     text_color=COR_TEXTO_SUAVE, font=ctk.CTkFont(size=11),
                     justify="center").pack(pady=(0, 12))

        frm = ctk.CTkFrame(d, fg_color="transparent")
        frm.pack(padx=24, fill="x")

        def row(lbl):
            ctk.CTkLabel(frm, text=lbl, text_color=COR_TEXTO_SUAVE,
                         font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(8, 2))

        row("Título *")
        e_titulo = ctk.CTkEntry(frm, placeholder_text="Ex: Fatura Nubank")
        e_titulo.pack(fill="x")
        e_titulo.insert(0, nome_cartao)

        row("Valor Total (R$) *")
        e_valor = ctk.CTkEntry(frm, placeholder_text="0,00")
        e_valor.pack(fill="x")
        e_valor.insert(0, f"{total_deb:.2f}".replace(".", ","))

        row("Data de Vencimento *")
        e_data = ctk.CTkEntry(frm, placeholder_text="DD/MM/AAAA")
        e_data.pack(fill="x")
        _aplicar_mascara_data(e_data)
        e_data.insert(0, data_sug.strftime("%d/%m/%Y"))

        row("Código de Barras / Linha Digitável")
        e_cod = ctk.CTkEntry(frm, placeholder_text="Cole ou digite o código aqui")
        e_cod.pack(fill="x")

        rec_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(frm, text="Recorrente (gerar todo mês automaticamente)",
                        variable=rec_var, text_color=COR_TEXTO).pack(anchor="w", pady=(10, 0))

        def _salvar():
            titulo   = e_titulo.get().strip()
            valor_tx = e_valor.get().strip().replace(",", ".")
            data_tx  = e_data.get().strip()
            cod_bar  = e_cod.get().strip() or None

            if not titulo or not valor_tx or not data_tx:
                messagebox.showwarning("Atenção", "Preencha todos os campos obrigatórios (*)", parent=d)
                return
            try:
                valor = float(valor_tx)
                dd, mm, aaaa = data_tx.split("/")
                venc = _date(int(aaaa), int(mm), int(dd))
            except Exception:
                messagebox.showwarning("Atenção", "Valor ou data inválidos.", parent=d)
                return

            payload = {
                "titulo":          titulo,
                "valor":           valor,
                "data_vencimento": venc,
                "tipo":            "parcela",
                "codigo_barras":   cod_bar,
                "recorrente":      rec_var.get(),
                "dia_recorrencia": venc.day if rec_var.get() else None,
                "descricao":       f"Fatura do cartão importada em {hoje.strftime('%d/%m/%Y')}",
            }
            try:
                from app.services.agenda_service import criar_evento
                db2 = self.app._obter_db()
                try:
                    criar_evento(db2, payload)
                finally:
                    db2.close()
            except Exception as ex:
                messagebox.showerror("Erro", str(ex), parent=d)
                return

            d.destroy()
            if dialog_pai:
                dialog_pai.destroy()
            messagebox.showinfo("✅ Salvo", "Fatura adicionada à Agenda Financeira!")

        ctk.CTkButton(d, text="💾 Salvar na Agenda", fg_color="#8E44AD", hover_color="#6C3483",
                      command=_salvar).pack(pady=18, padx=24, fill="x")
        ctk.CTkButton(d, text="Cancelar", fg_color="transparent", border_width=1,
                      command=d.destroy).pack(padx=24, fill="x")


# ================================================
# Frame: Fatura Cartão de Crédito
# ================================================

class FaturaCartaoFrame(ctk.CTkFrame):
    """
    Interface dedicada para importação e análise de faturas de cartão de crédito.

    Funcionalidades:
      - Seleção de cartão cadastrado (com cadastro rápido)
      - Importação de fatura em CSV, PDF, Excel ou OFX
      - Auto-detecção de formato: Nubank, Inter, C6, XP, Itaú e genérico
      - Tabela de transações importadas com categoria, valor e parcelas
      - Resumo: total da fatura, n.º de compras, categoria mais cara
    """

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._cartoes: dict = {}
        self._cartoes_por_id: dict = {}
        self._transacoes_importadas: list = []
        self.grid_columnconfigure(0, weight=1)
        self._construir_ui()
        self._carregar_cartoes()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _construir_ui(self):
        # Título
        ctk.CTkLabel(self, text="💳 Importar Fatura de Cartão",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=COR_TEXTO).grid(row=0, column=0, sticky="w", pady=(0, 12))

        # ── Painel de seleção de cartão ──────────────────────────────
        painel = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)
        painel.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        painel.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(painel, text="Cartão:", text_color=COR_TEXTO,
                     font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(14, 8), pady=12, sticky="w")
        self.var_cartao = ctk.StringVar(value="— Selecione —")
        self.combo_cartao = ctk.CTkComboBox(painel, variable=self.var_cartao,
                                             values=["— Selecione —"], width=280, state="readonly",
                                             command=lambda _valor: self._atualizar_info_cartao())
        self.combo_cartao.grid(row=0, column=1, sticky="w", pady=12)

        ctk.CTkButton(painel, text="+ Novo Cartão", width=120,
                      fg_color=COR_SECUNDARIA,
                      command=self._dialog_novo_cartao).grid(row=0, column=2, padx=(8, 14), pady=12)

        self.lbl_info_cartao = ctk.CTkLabel(
            painel,
            text="Fechamento: —  |  Vencimento: —",
            text_color=COR_TEXTO_SUAVE,
            font=ctk.CTkFont(size=11),
        )
        self.lbl_info_cartao.grid(row=1, column=1, columnspan=2, sticky="w", padx=(0, 14), pady=(0, 12))

        # ── Cards de formato ────────────────────────────────────────
        ctk.CTkLabel(self, text="Selecione o formato da fatura:",
                     text_color=COR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=12)).grid(row=2, column=0, sticky="w", pady=(0, 6))

        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.grid(row=3, column=0, sticky="ew")
        for i in range(4):
            cards.grid_columnconfigure(i, weight=1)

        formatos = [
            ("CSV",   "📊", "Nubank, Inter, C6, XP\nItaú e outros bancos",   self._importar_csv),
            ("PDF",   "📄", "Fatura em PDF\n(digital ou escaneado)",          self._importar_pdf),
            ("Excel", "📗", "Planilha .xlsx\nexportada pelo banco",            self._importar_excel),
            ("OFX",   "🏦", "Formato OFX/QFX\npadrão internacional",          self._importar_ofx),
        ]
        for i, (nome, icone, desc, cmd) in enumerate(formatos):
            card = ctk.CTkFrame(cards, fg_color=COR_CARD, corner_radius=14)
            card.grid(row=0, column=i, padx=6, sticky="nsew")
            ctk.CTkLabel(card, text=icone, font=ctk.CTkFont(size=32)).pack(pady=(16, 4))
            ctk.CTkLabel(card, text=nome, font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=COR_TEXTO).pack()
            ctk.CTkLabel(card, text=desc, font=ctk.CTkFont(size=10),
                         text_color=COR_TEXTO_SUAVE, justify="center").pack(pady=(4, 10))
            ctk.CTkButton(card, text=f"Importar {nome}", command=cmd,
                          fg_color=COR_PRIMARIA, corner_radius=8).pack(padx=14, pady=(0, 16), fill="x")

        # ── Resumo da fatura ────────────────────────────────────────
        self.frame_resumo = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)
        self.frame_resumo.grid(row=4, column=0, sticky="ew", pady=(12, 6))
        self.frame_resumo.grid_columnconfigure((0, 1, 2), weight=1)

        self.lbl_total_fatura = ctk.CTkLabel(self.frame_resumo, text="R$ 0,00",
            font=ctk.CTkFont(size=18, weight="bold"), text_color=COR_PERIGO)
        self.lbl_total_fatura.grid(row=0, column=0, padx=16, pady=10)
        ctk.CTkLabel(self.frame_resumo, text="Total da Fatura",
            font=ctk.CTkFont(size=10), text_color=COR_TEXTO_SUAVE).grid(row=1, column=0, padx=16)

        self.lbl_qtd_compras = ctk.CTkLabel(self.frame_resumo, text="0",
            font=ctk.CTkFont(size=18, weight="bold"), text_color=COR_TEXTO)
        self.lbl_qtd_compras.grid(row=0, column=1, padx=16, pady=10)
        ctk.CTkLabel(self.frame_resumo, text="Compras",
            font=ctk.CTkFont(size=10), text_color=COR_TEXTO_SUAVE).grid(row=1, column=1, padx=16)

        self.lbl_cat_principal = ctk.CTkLabel(self.frame_resumo, text="—",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=COR_AVISO)
        self.lbl_cat_principal.grid(row=0, column=2, padx=16, pady=10)
        ctk.CTkLabel(self.frame_resumo, text="Categoria Principal",
            font=ctk.CTkFont(size=10), text_color=COR_TEXTO_SUAVE).grid(row=1, column=2, padx=16, pady=(0, 10))

        # ── Tabela de transações importadas ─────────────────────────
        ctk.CTkLabel(self, text="Transações reconhecidas:",
                     text_color=COR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=12)).grid(row=5, column=0, sticky="w", pady=(8, 4))

        frame_tabela = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)
        frame_tabela.grid(row=6, column=0, sticky="nsew", pady=(0, 4))
        frame_tabela.grid_columnconfigure(0, weight=1)
        frame_tabela.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(6, weight=1)

        colunas = ("data", "descricao", "valor", "tipo", "categoria", "parcelas")
        self.tabela = ttk.Treeview(frame_tabela, columns=colunas, show="headings", height=12)
        self.tabela.heading("data",      text="Data")
        self.tabela.heading("descricao", text="Descrição")
        self.tabela.heading("valor",     text="Valor (R$)")
        self.tabela.heading("tipo",      text="Tipo")
        self.tabela.heading("categoria", text="Categoria")
        self.tabela.heading("parcelas",  text="Parcelas")
        self.tabela.column("data",      width=90,  anchor="center")
        self.tabela.column("descricao", width=300, anchor="w")
        self.tabela.column("valor",     width=100, anchor="e")
        self.tabela.column("tipo",      width=80,  anchor="center")
        self.tabela.column("categoria", width=130, anchor="center")
        self.tabela.column("parcelas",  width=80,  anchor="center")

        scroll_y = ttk.Scrollbar(frame_tabela, orient="vertical", command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=scroll_y.set)
        self.tabela.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        scroll_y.grid(row=0, column=1, sticky="ns", pady=8, padx=(0, 8))

        # ── Log de status ────────────────────────────────────────────
        self.lbl_status = ctk.CTkLabel(self, text="Selecione um cartão e importe a fatura.",
                                        text_color=COR_TEXTO_SUAVE, font=ctk.CTkFont(size=11))
        self.lbl_status.grid(row=7, column=0, sticky="w", pady=(4, 0))

        # Barra de progresso — aparece apenas durante importação
        # Usa ttk.Progressbar nativo (Tcl/Tk puro) para evitar crash cross-thread
        _sty2 = ttk.Style()
        _sty2.configure("Cartao.Horizontal.TProgressbar",
                        troughcolor="#1a1a2e", background="#4A90D9",
                        thickness=8)
        self.prg_cartao = ttk.Progressbar(
            self, style="Cartao.Horizontal.TProgressbar",
            orient="horizontal", mode="indeterminate", length=200)
        self.prg_cartao.grid(row=8, column=0, sticky="ew", pady=(4, 0))
        self.prg_cartao.grid_remove()  # oculta por padrão

    # --------------------------------------------------
    # Dados
    # --------------------------------------------------

    def _carregar_cartoes(self):
        db = self.app._obter_db()
        try:
            from app.models import CartaoCredito
            cartoes = db.query(CartaoCredito).filter(CartaoCredito.ativo == True).all()
        finally:
            db.close()
        atual = self.var_cartao.get().strip()
        self._cartoes = {}
        self._cartoes_por_id = {}
        for cartao in cartoes:
            label = self._formatar_label_cartao(cartao)
            info = {
                "id": cartao.id,
                "nome": cartao.nome,
                "bandeira": cartao.bandeira,
                "dia_fechamento": cartao.dia_fechamento,
                "dia_vencimento": cartao.dia_vencimento,
            }
            self._cartoes[label] = info
            self._cartoes_por_id[cartao.id] = info

        nomes = ["— Selecione —"] + list(self._cartoes.keys())
        self.combo_cartao.configure(values=nomes)
        self.var_cartao.set(atual if atual in self._cartoes else nomes[0])
        self._atualizar_info_cartao()

    def _get_cartao_id(self) -> Optional[int]:
        info = self._cartoes.get(self.var_cartao.get())
        return info.get("id") if info else None

    def _formatar_label_cartao(self, cartao) -> str:
        partes = [cartao.nome, f"({cartao.bandeira})"]
        if cartao.dia_fechamento:
            partes.append(f"fecha {cartao.dia_fechamento:02d}")
        if cartao.dia_vencimento:
            partes.append(f"vence {cartao.dia_vencimento:02d}")
        return " • ".join(partes)

    def _atualizar_info_cartao(self) -> None:
        info = self._cartoes.get(self.var_cartao.get())
        if not info:
            self.lbl_info_cartao.configure(text="Cartão: —  |  Fechamento: —  |  Vencimento: —")
            return

        dia_fechamento = info.get("dia_fechamento")
        dia_vencimento = info.get("dia_vencimento")
        self.lbl_info_cartao.configure(
            text=(
                f"Cartão: {info.get('nome', '—')}  |  "
                f"Fechamento: {dia_fechamento:02d}  |  "
                f"Vencimento: {dia_vencimento:02d}"
            ) if dia_fechamento and dia_vencimento else (
                f"Cartão: {info.get('nome', '—')}  |  "
                f"Fechamento: {dia_fechamento:02d}" if dia_fechamento else f"Cartão: {info.get('nome', '—')}  |  Fechamento: —"
            ) + (f"  |  Vencimento: {dia_vencimento:02d}" if dia_vencimento else "  |  Vencimento: —")
        )

    def _selecionar_cartao_por_id(self, cartao_id: Optional[int]) -> None:
        if not cartao_id:
            return

        self._carregar_cartoes()
        for nome, cid in self._cartoes.items():
            if cid.get("id") == cartao_id:
                self.var_cartao.set(nome)
                self._atualizar_info_cartao()
                return

    # --------------------------------------------------
    # Importação
    # --------------------------------------------------

    def _importar_csv(self):
        caminho = filedialog.askopenfilename(
            title="Selecionar CSV da Fatura",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")]
        )
        if caminho:
            self._executar(caminho)

    def _importar_pdf(self):
        caminho = filedialog.askopenfilename(
            title="Selecionar PDF da Fatura",
            filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")]
        )
        if not caminho:
            return
        # Detecta se o PDF é protegido por senha
        try:
            import pdfplumber as _plb
            with _plb.open(caminho):
                pass
            self._executar(caminho)
        except Exception:
            self._dialog_senha_cartao(caminho)

    def _importar_excel(self):
        caminho = filedialog.askopenfilename(
            title="Selecionar Excel da Fatura",
            filetypes=[("Excel", "*.xlsx *.xls"), ("Todos", "*.*")]
        )
        if caminho:
            self._executar(caminho)

    def _importar_ofx(self):
        caminho = filedialog.askopenfilename(
            title="Selecionar OFX da Fatura",
            filetypes=[("OFX", "*.ofx *.qfx"), ("Todos", "*.*")]
        )
        if caminho:
            self._executar(caminho)

    def _executar(self, caminho: str, senha: Optional[str] = None):
        cartao_id = self._get_cartao_id()
        self._set_status(f"⏳ Lendo {os.path.basename(caminho)} (prévia, sem salvar)...")
        self.prg_cartao.grid()
        self.prg_cartao.start(30)
        threading.Thread(
            target=self._rodar_previa_fatura,
            args=(caminho, cartao_id, senha), daemon=True
        ).start()

    def _dialog_senha_cartao(self, caminho: str):
        """Diálogo para pedir senha de PDF protegido na importação de fatura."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("PDF Protegido")
        dlg.geometry("420x220")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.lift()
        ctk.CTkLabel(dlg, text="🔒  PDF Protegido por Senha",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=COR_TEXTO).pack(pady=(20, 4))
        ctk.CTkLabel(dlg, text=os.path.basename(caminho),
                     text_color=COR_TEXTO_SUAVE, font=ctk.CTkFont(size=11)).pack()
        entry = ctk.CTkEntry(dlg, show="*", width=320,
                              placeholder_text="Senha do arquivo...")
        entry.pack(pady=14)
        entry.focus()
        def _ok():
            s = entry.get().strip()
            if not s:
                return
            dlg.destroy()
            self._executar(caminho, senha=s)
        btns = ctk.CTkFrame(dlg, fg_color="transparent")
        btns.pack()
        ctk.CTkButton(btns, text="✅ Importar", width=130,
                      fg_color=COR_PRIMARIA, command=_ok).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Cancelar", width=100,
                      fg_color=COR_SECUNDARIA, command=dlg.destroy).pack(side="left", padx=6)
        entry.bind("<Return>", lambda e: _ok())

    def _rodar_previa_fatura(self, caminho: str, cartao_id: Optional[int], senha: Optional[str] = None):
        db = self.app._obter_db()
        previa = None
        erro = None
        try:
            from app.services.import_service import ImportService
            previa = ImportService(db).previsualizar_fatura_cartao(caminho, senha=senha)
        except Exception as e:
            erro = str(e)
        finally:
            db.close()

        def _abrir():
            self.prg_cartao.stop()
            self.prg_cartao.grid_remove()
            if erro:
                self._set_status(f"❌ Erro na leitura: {erro}")
                messagebox.showerror("Erro na Leitura", erro)
                return
            self._set_status(
                f"Prévia pronta: {previa.get('qtd_previa', 0)} transações para revisão antes de salvar."
            )
            self._dialog_previa_fatura(caminho, previa or {}, cartao_id, senha)

        _after_seguro(self, 0, _abrir)

    def _dialog_previa_fatura(
        self,
        caminho: str,
        previa: Dict[str, Any],
        cartao_id: Optional[int],
        senha: Optional[str],
    ):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Revisar Fatura Antes de Salvar")
        dialog.geometry("980x640")
        dialog.grab_set()
        dialog.lift()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            dialog,
            text="🧾 Revisão da 1ª leitura (nenhum dado salvo ainda)",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COR_TEXTO,
        ).grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

        resumo = (
            f"Arquivo: {os.path.basename(caminho)}  |  "
            f"Banco: {previa.get('banco') or '—'}  |  "
            f"Lidas: {previa.get('qtd_lidas', 0)}  |  "
            f"Prévia: {previa.get('qtd_previa', 0)}  |  "
            f"Ignoradas: {previa.get('qtd_ignoradas', 0)}"
        )
        ctk.CTkLabel(
            dialog,
            text=resumo,
            font=ctk.CTkFont(size=11),
            text_color=COR_TEXTO_SUAVE,
        ).grid(row=1, column=0, padx=16, pady=(0, 10), sticky="w")

        corpo = ctk.CTkFrame(dialog, fg_color=COR_CARD, corner_radius=10)
        corpo.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 8))
        corpo.grid_columnconfigure(0, weight=1)
        corpo.grid_rowconfigure(0, weight=1)

        tree = ttk.Treeview(corpo, columns=("data", "descricao", "valor", "tipo"), show="headings", height=14)
        tree.heading("data", text="Data")
        tree.heading("descricao", text="Descrição")
        tree.heading("valor", text="Valor (R$)")
        tree.heading("tipo", text="Tipo")
        tree.column("data", width=110, anchor="center")
        tree.column("descricao", width=520, anchor="w")
        tree.column("valor", width=140, anchor="e")
        tree.column("tipo", width=120, anchor="center")
        tree.grid(row=0, column=0, sticky="nsew", padx=(10, 2), pady=10)

        vsb = ttk.Scrollbar(corpo, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns", pady=10, padx=(0, 8))

        for item in (previa.get("transacoes") or []):
            data_txt = str(item.get("data") or "")
            desc_txt = (item.get("descricao") or "").strip()
            valor_txt = f"{float(item.get('valor') or 0.0):.2f}".replace(".", ",")
            tipo_txt = str(item.get("tipo") or "debito").lower()
            tree.insert("", "end", values=(data_txt, desc_txt, valor_txt, tipo_txt))

        editor = ctk.CTkFrame(dialog, fg_color="transparent")
        editor.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 8))
        editor.grid_columnconfigure(7, weight=1)

        ctk.CTkLabel(editor, text="Data", text_color=COR_TEXTO_SUAVE).grid(row=0, column=0, padx=(0, 4), sticky="w")
        e_data = ctk.CTkEntry(editor, width=110, placeholder_text="AAAA-MM-DD")
        e_data.grid(row=1, column=0, padx=(0, 8))

        ctk.CTkLabel(editor, text="Descrição", text_color=COR_TEXTO_SUAVE).grid(row=0, column=1, padx=(0, 4), sticky="w")
        e_desc = ctk.CTkEntry(editor, width=360)
        e_desc.grid(row=1, column=1, padx=(0, 8))

        ctk.CTkLabel(editor, text="Valor", text_color=COR_TEXTO_SUAVE).grid(row=0, column=2, padx=(0, 4), sticky="w")
        e_valor = ctk.CTkEntry(editor, width=120, placeholder_text="0,00")
        e_valor.grid(row=1, column=2, padx=(0, 8))

        ctk.CTkLabel(editor, text="Tipo", text_color=COR_TEXTO_SUAVE).grid(row=0, column=3, padx=(0, 4), sticky="w")
        var_tipo = ctk.StringVar(value="debito")
        c_tipo = ctk.CTkComboBox(editor, width=110, variable=var_tipo, values=["debito", "credito"], state="readonly")
        c_tipo.grid(row=1, column=3, padx=(0, 8))

        def _carregar_linha(_event=None):
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0], "values")
            if not vals:
                return
            e_data.delete(0, "end")
            e_data.insert(0, vals[0])
            e_desc.delete(0, "end")
            e_desc.insert(0, vals[1])
            e_valor.delete(0, "end")
            e_valor.insert(0, vals[2])
            var_tipo.set(vals[3] or "debito")

        def _aplicar_edicao():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Seleção", "Selecione uma linha para editar.", parent=dialog)
                return
            tree.item(
                sel[0],
                values=(
                    e_data.get().strip(),
                    e_desc.get().strip(),
                    e_valor.get().strip(),
                    var_tipo.get().strip() or "debito",
                ),
            )

        def _adicionar_linha():
            tree.insert(
                "",
                "end",
                values=(
                    e_data.get().strip(),
                    e_desc.get().strip(),
                    e_valor.get().strip() or "0,00",
                    var_tipo.get().strip() or "debito",
                ),
            )

        def _remover_linha():
            sel = tree.selection()
            if not sel:
                return
            for item_sel in sel:
                tree.delete(item_sel)

        tree.bind("<<TreeviewSelect>>", _carregar_linha)

        ctk.CTkButton(editor, text="Aplicar", width=92, fg_color=COR_PRIMARIA, command=_aplicar_edicao).grid(row=1, column=4, padx=(0, 6))
        ctk.CTkButton(editor, text="Adicionar", width=96, fg_color=COR_SECUNDARIA, command=_adicionar_linha).grid(row=1, column=5, padx=(0, 6))
        ctk.CTkButton(editor, text="Remover", width=92, fg_color=COR_PERIGO, command=_remover_linha).grid(row=1, column=6, padx=(0, 6))

        barra = ctk.CTkFrame(dialog, fg_color="transparent")
        barra.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 14))
        barra.grid_columnconfigure(0, weight=1)

        def _confirmar_salvar():
            transacoes_editadas: List[Dict[str, Any]] = []
            for item_id in tree.get_children():
                data_txt, desc_txt, valor_txt, tipo_txt = tree.item(item_id, "values")
                if not desc_txt:
                    continue
                transacoes_editadas.append({
                    "data": data_txt,
                    "descricao": desc_txt,
                    "valor": valor_txt,
                    "tipo": (tipo_txt or "debito").lower(),
                })

            if not transacoes_editadas:
                messagebox.showwarning("Prévia vazia", "Inclua ao menos uma transação antes de salvar.", parent=dialog)
                return

            confirmar = messagebox.askyesno(
                "Confirmar Inclusão",
                (
                    f"Confirma a inclusão de {len(transacoes_editadas)} transações no banco?\n"
                    "Após confirmar, os dados serão persistidos."
                ),
                parent=dialog,
            )
            if not confirmar:
                return

            dialog.destroy()
            self._set_status("⏳ Salvando transações confirmadas...")
            self.prg_cartao.grid()
            self.prg_cartao.start(30)
            threading.Thread(
                target=self._rodar_importacao_previa_confirmada,
                args=(caminho, cartao_id, senha, transacoes_editadas),
                daemon=True,
            ).start()

        ctk.CTkButton(
            barra,
            text="✅ Confirmar Inclusão no Banco",
            fg_color=COR_SUCESSO,
            hover_color="#1E8449",
            command=_confirmar_salvar,
        ).grid(row=0, column=1, padx=(8, 0))

        ctk.CTkButton(
            barra,
            text="Cancelar",
            fg_color="transparent",
            border_width=1,
            command=dialog.destroy,
        ).grid(row=0, column=0, sticky="e")

    def _rodar_importacao_previa_confirmada(
        self,
        caminho: str,
        cartao_id: Optional[int],
        senha: Optional[str],
        transacoes_editadas: List[Dict[str, Any]],
    ):
        db = self.app._obter_db()
        duplicado = None
        cartao_info = None
        try:
            from app.services.import_service import ImportService
            resultado = ImportService(db).salvar_fatura_cartao_previa(
                caminho=caminho,
                transacoes_editadas=transacoes_editadas,
                cartao_id=cartao_id,
                senha=senha,
            )
            cartao_info = {
                "cartao_id": resultado.get("cartao_id"),
                "cartao_nome": resultado.get("cartao_nome"),
                "cartao_bandeira": resultado.get("cartao_bandeira"),
                "cartao_criado": resultado.get("cartao_criado", False),
            }
            extrato_id = resultado.get("extrato_id")

            # Busca transações recém-importadas para exibir na tabela
            from app.models import Transacao
            transacoes = (
                db.query(Transacao)
                .filter(Transacao.extrato_id == extrato_id)
                .order_by(Transacao.data)
                .all()
            ) if extrato_id else []

            dados = [{
                "data":      str(t.data),
                "descricao": t.descricao,
                "valor":     t.valor,
                "tipo":      t.tipo,
                "categoria": t.categoria.nome if t.categoria else "Outros",
                "parcelas":  f"{t.parcela_atual}/{t.parcelas_total}" if t.parcelas_total else "—",
            } for t in transacoes]

            if resultado.get("duplicado"):
                duplicado = resultado
                msg = (
                    f"⚠️ Arquivo já importado em {resultado.get('importado_em', '—')} "
                    f"(Extrato #{resultado.get('extrato_id', '—')})."
                )
            else:
                msg = (f"✅ Inclusão confirmada. {resultado['importadas']} transações importadas, "
                       f"{resultado['ignoradas']} ignoradas.")
                if cartao_info.get("cartao_criado") and cartao_info.get("cartao_nome"):
                    msg = (
                        f"✅ Cartão {cartao_info['cartao_nome']} "
                        f"({cartao_info.get('cartao_bandeira', 'Outros')}) cadastrado automaticamente. "
                        + msg[2:]
                    )
        except Exception as e:
            dados = []
            msg = f"❌ Erro: {e}"
        finally:
            db.close()

        _after_seguro(self, 0, lambda: self._atualizar_resultado(
            dados,
            msg,
            duplicado=duplicado,
            cartao_info=cartao_info,
        ))

    # --------------------------------------------------
    # Atualização da UI após importação
    # --------------------------------------------------

    def _atualizar_resultado(self, dados: list, msg: str,
                             duplicado: Optional[dict] = None,
                             cartao_info: Optional[dict] = None):
        if not _widget_existe(self):
            return

        if cartao_info and cartao_info.get("cartao_id"):
            self._selecionar_cartao_por_id(cartao_info["cartao_id"])

        # Para e oculta a barra de progresso
        self.prg_cartao.stop()
        self.prg_cartao.grid_remove()
        self._set_status(msg)
        self._limpar_tabela()

        total = 0.0
        categorias: dict = {}

        for row in dados:
            self.tabela.insert("", "end", values=(
                row["data"], row["descricao"],
                f"R$ {row['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                row["tipo"], row["categoria"], row["parcelas"],
            ))
            if row["tipo"] == "debito":
                total += row["valor"]
                categorias[row["categoria"]] = categorias.get(row["categoria"], 0.0) + row["valor"]

        cat_principal = max(categorias, key=categorias.get) if categorias else "—"
        total_br = f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        self.lbl_total_fatura.configure(text=total_br)
        self.lbl_qtd_compras.configure(text=str(len(dados)))
        self.lbl_cat_principal.configure(text=cat_principal)

        if duplicado:
            messagebox.showwarning(
                "Arquivo já Importado",
                (
                    f"Este arquivo já havia sido importado.\n\n"
                    f"Extrato ID: #{duplicado.get('extrato_id', '—')}\n"
                    f"Importado em: {duplicado.get('importado_em', '—')}\n"
                    f"Transações anteriores: {duplicado.get('total_anterior', 0)}"
                ),
            )

    def _limpar_tabela(self):
        for item in self.tabela.get_children():
            self.tabela.delete(item)

    def _set_status(self, msg: str):
        self.lbl_status.configure(text=msg)

    # --------------------------------------------------
    # Dialog de novo cartão
    # --------------------------------------------------

    def _dialog_novo_cartao(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Novo Cartão de Crédito")
        dialog.geometry("360x290")
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="💳 Novo Cartão",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 10))

        frame = ctk.CTkFrame(dialog, fg_color="transparent")
        frame.pack(padx=20, fill="x")

        ctk.CTkLabel(frame, text="Nome do cartão:").pack(anchor="w")
        e_nome = ctk.CTkEntry(frame, placeholder_text="Ex: Nubank Roxinho")
        e_nome.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(frame, text="Bandeira:").pack(anchor="w")
        var_band = ctk.StringVar(value="Visa")
        ctk.CTkComboBox(frame, variable=var_band,
                        values=["Visa", "Mastercard", "Elo", "Amex", "Hipercard", "Outros"],
                        state="readonly").pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(frame, text="Limite (R$):").pack(anchor="w")
        e_limite = ctk.CTkEntry(frame, placeholder_text="Ex: 5000")
        e_limite.pack(fill="x", pady=(0, 15))

        def salvar():
            nome = e_nome.get().strip()
            if not nome:
                return
            try:
                limite = float(e_limite.get().replace(",", ".")) if e_limite.get().strip() else 0.0
            except ValueError:
                limite = 0.0
            db = self.app._obter_db()
            try:
                from app.models import CartaoCredito
                c = CartaoCredito(nome=nome, bandeira=var_band.get(),
                                  limite=limite, limite_disponivel=limite, ativo=True)
                db.add(c)
                db.commit()
            finally:
                db.close()
            self._carregar_cartoes()
            dialog.destroy()

        ctk.CTkButton(dialog, text="💾 Salvar", command=salvar,
                      fg_color=COR_PRIMARIA).pack(pady=5, padx=20, fill="x")


# ================================================
# Frame: Metas
# ================================================

class MetasFrame(ctk.CTkFrame):
    """Gerenciamento de metas financeiras."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self._construir_ui()
        self.carregar_dados()

    def _construir_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ctk.CTkLabel(header, text="🎯 Metas Financeiras",
                     font=ctk.CTkFont(size=22, weight="bold"), text_color=COR_TEXTO).pack(side="left")
        ctk.CTkButton(header, text="+ Nova Meta", fg_color=COR_SUCESSO,
                      hover_color="#1E8449", command=self._dialog_nova_meta).pack(side="right")

        self.frame_lista = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.frame_lista.grid(row=1, column=0, sticky="nsew")
        self.grid_rowconfigure(1, weight=1)

    def carregar_dados(self):
        for w in self.frame_lista.winfo_children():
            w.destroy()

        db = self.app._obter_db()
        try:
            from app.services.metas_service import MetasService
            metas = MetasService(db).resumo_metas()
        finally:
            db.close()

        if not metas:
            ctk.CTkLabel(self.frame_lista, text="Nenhuma meta cadastrada.\nClique em '+ Nova Meta' para começar.",
                         text_color=COR_TEXTO_SUAVE, font=ctk.CTkFont(size=13),
                         justify="center").pack(pady=40)
            return

        for meta in metas:
            self._criar_card_meta(meta)

    def _criar_card_meta(self, meta: dict):
        from app.utils.helpers import formatar_moeda

        card = ctk.CTkFrame(self.frame_lista, fg_color=COR_CARD, corner_radius=12)
        card.pack(fill="x", pady=5, padx=2)
        card.grid_columnconfigure(0, weight=1)

        # Linha superior
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(12, 4))
        icone = "✅" if meta["concluida"] else "🎯"
        ctk.CTkLabel(top, text=f"{icone} {meta['nome']}",
                     font=ctk.CTkFont(size=14, weight="bold"), text_color=COR_TEXTO).pack(side="left")
        ctk.CTkLabel(top, text=f"{meta['percentual']:.1f}%",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_SUCESSO if meta["concluida"] else COR_PRIMARIA).pack(side="right")

        # Barra de progresso
        prog = ctk.CTkProgressBar(card, height=10, corner_radius=5)
        prog.set(meta["percentual"] / 100)
        prog.configure(progress_color=COR_SUCESSO if meta["concluida"] else COR_PRIMARIA)
        prog.pack(fill="x", padx=12, pady=(0, 6))

        # Valores
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(info, text=f"Atual: {formatar_moeda(meta['valor_atual'])}",
                     text_color=COR_TEXTO_SUAVE, font=ctk.CTkFont(size=11)).pack(side="left")
        ctk.CTkLabel(info, text=f"Meta: {formatar_moeda(meta['valor_alvo'])}",
                     text_color=COR_TEXTO_SUAVE, font=ctk.CTkFont(size=11)).pack(side="left", padx=10)
        ctk.CTkLabel(info, text=f"Falta: {formatar_moeda(meta['falta'])}",
                     text_color=COR_AVISO if meta['falta'] > 0 else COR_SUCESSO,
                     font=ctk.CTkFont(size=11)).pack(side="right")

    def _dialog_nova_meta(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Nova Meta")
        dialog.geometry("380x320")
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="🎯 Nova Meta", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 10))

        frame = ctk.CTkFrame(dialog, fg_color="transparent")
        frame.pack(padx=20, fill="x")

        ctk.CTkLabel(frame, text="Nome:").pack(anchor="w")
        e_nome = ctk.CTkEntry(frame, placeholder_text="Ex: Viagem Europa")
        e_nome.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(frame, text="Valor alvo (R$):").pack(anchor="w")
        e_valor = ctk.CTkEntry(frame, placeholder_text="Ex: 5000")
        e_valor.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(frame, text="Descrição (opcional):").pack(anchor="w")
        e_desc = ctk.CTkEntry(frame, placeholder_text="Detalhes da meta...")
        e_desc.pack(fill="x", pady=(0, 15))

        def salvar():
            try:
                nome  = e_nome.get().strip()
                valor = float(e_valor.get().replace(",", "."))
                desc  = e_desc.get().strip() or None
                if not nome:
                    return
                db = self.app._obter_db()
                try:
                    from app.services.metas_service import MetasService
                    MetasService(db).criar_meta(nome=nome, valor_alvo=valor, descricao=desc)
                finally:
                    db.close()
                dialog.destroy()
                self.carregar_dados()
            except ValueError:
                messagebox.showwarning("Atenção", "Valor inválido.", parent=dialog)

        ctk.CTkButton(dialog, text="💾 Salvar Meta", command=salvar,
                      fg_color=COR_SUCESSO).pack(pady=5, padx=20, fill="x")


# ================================================
# Frame: Orçamentos
# ================================================

class OrcamentosFrame(ctk.CTkFrame):
    """Gerenciamento de orçamentos mensais por categoria."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        hoje = date.today()
        self.mes = hoje.month
        self.ano = hoje.year
        self._construir_ui()
        self.carregar_dados()

    def _construir_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ctk.CTkLabel(header, text="💸 Orçamentos",
                     font=ctk.CTkFont(size=22, weight="bold"), text_color=COR_TEXTO).pack(side="left")
        ctk.CTkButton(header, text="+ Novo Orçamento", fg_color=COR_PRIMARIA,
                      command=self._dialog_novo_orcamento).pack(side="right")

        self.frame_lista = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.frame_lista.grid(row=1, column=0, sticky="nsew")
        self.grid_rowconfigure(1, weight=1)

    def carregar_dados(self):
        for w in self.frame_lista.winfo_children():
            w.destroy()

        db = self.app._obter_db()
        try:
            from app.services.metas_service import MetasService
            from app.utils.helpers import formatar_moeda

            orcamentos = MetasService(db).resumo_orcamentos(self.mes, self.ano)
        finally:
            db.close()

        if not orcamentos:
            ctk.CTkLabel(self.frame_lista,
                         text=f"Nenhum orçamento para {self.mes}/{self.ano}.\nClique em '+ Novo Orçamento'.",
                         text_color=COR_TEXTO_SUAVE, justify="center").pack(pady=40)
            return

        for orc in orcamentos:
            self._criar_card_orcamento(orc)

    def _criar_card_orcamento(self, orc: dict):
        from app.utils.helpers import formatar_moeda

        cor_status = {"ok": COR_SUCESSO, "alerta": COR_AVISO, "estourado": COR_PERIGO}.get(orc["status"], COR_TEXTO)

        card = ctk.CTkFrame(self.frame_lista, fg_color=COR_CARD, corner_radius=12)
        card.pack(fill="x", pady=4, padx=2)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(top, text=f"🏷️ {orc['categoria']}",
                     font=ctk.CTkFont(size=13, weight="bold"), text_color=COR_TEXTO).pack(side="left")
        status_txt = {"ok": "✅ OK", "alerta": "⚠️ Atenção", "estourado": "🚨 Estourado"}.get(orc["status"], "")
        ctk.CTkLabel(top, text=status_txt, text_color=cor_status,
                     font=ctk.CTkFont(size=12)).pack(side="right")

        prog = ctk.CTkProgressBar(card, height=10, corner_radius=5)
        prog.set(min(orc["percentual"] / 100, 1.0))
        prog.configure(progress_color=cor_status)
        prog.pack(fill="x", padx=12, pady=(0, 6))

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(info, text=f"Gasto: {formatar_moeda(orc['gasto'])}",
                     text_color=COR_TEXTO_SUAVE, font=ctk.CTkFont(size=11)).pack(side="left")
        ctk.CTkLabel(info, text=f"Limite: {formatar_moeda(orc['limite'])}",
                     text_color=COR_TEXTO_SUAVE, font=ctk.CTkFont(size=11)).pack(side="left", padx=10)
        ctk.CTkLabel(info, text=f"{orc['percentual']:.0f}% utilizado",
                     text_color=cor_status, font=ctk.CTkFont(size=11)).pack(side="right")

    def _dialog_novo_orcamento(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Novo Orçamento")
        dialog.geometry("360x280")
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="💸 Novo Orçamento",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 10))

        frame = ctk.CTkFrame(dialog, fg_color="transparent")
        frame.pack(padx=20, fill="x")

        db = self.app._obter_db()
        try:
            from app.models import Categoria
            cats = [(c.id, c.nome) for c in db.query(Categoria).filter(Categoria.ativa == True).all()]
        finally:
            db.close()

        ctk.CTkLabel(frame, text="Categoria:").pack(anchor="w")
        var_cat     = ctk.StringVar()
        combo_cat   = ctk.CTkComboBox(frame, values=[n for _, n in cats], variable=var_cat, state="readonly")
        combo_cat.pack(fill="x", pady=(0, 8))
        if cats:
            var_cat.set(cats[0][1])

        ctk.CTkLabel(frame, text="Limite mensal (R$):").pack(anchor="w")
        e_limite = ctk.CTkEntry(frame, placeholder_text="Ex: 800")
        e_limite.pack(fill="x", pady=(0, 15))

        def salvar():
            try:
                nome_cat  = var_cat.get()
                cat_id    = next((i for i, n in cats if n == nome_cat), None)
                limite    = float(e_limite.get().replace(",", "."))
                if not cat_id:
                    return
                db = self.app._obter_db()
                try:
                    from app.services.metas_service import MetasService
                    MetasService(db).criar_orcamento(
                        categoria_id=cat_id, valor_limite=limite,
                        mes=self.mes, ano=self.ano
                    )
                finally:
                    db.close()
                dialog.destroy()
                self.carregar_dados()
            except ValueError:
                messagebox.showwarning("Atenção", "Valor inválido.", parent=dialog)

        ctk.CTkButton(dialog, text="💾 Salvar", command=salvar,
                      fg_color=COR_PRIMARIA).pack(pady=5, padx=20, fill="x")


# ================================================
# Frame: Relatórios
# ================================================

class RelatoriosFrame(ctk.CTkFrame):
    """Exportação de relatórios em CSV, Excel e PDF."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self._construir_ui()

    def _construir_ui(self):
        ctk.CTkLabel(self, text="📊 Relatórios & Exportação",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=COR_TEXTO).grid(row=0, column=0, sticky="w", pady=(0, 15))

        # Filtros de período
        filtros = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)
        filtros.grid(row=1, column=0, sticky="ew", pady=(0, 15))

        hoje = date.today()
        ctk.CTkLabel(filtros, text="Período:", text_color=COR_TEXTO).pack(side="left", padx=(15, 5))
        self.var_mes = ctk.StringVar(value=str(hoje.month))
        self.var_ano = ctk.StringVar(value=str(hoje.year))
        ctk.CTkComboBox(filtros, values=[str(i) for i in range(1, 13)],
                        variable=self.var_mes, width=55).pack(side="left", padx=4, pady=8)
        ctk.CTkEntry(filtros, textvariable=self.var_ano, width=65).pack(side="left", padx=4)

        # Cards de exportação
        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.grid(row=2, column=0, sticky="ew")
        for i in range(3):
            cards.grid_columnconfigure(i, weight=1)

        formatos = [
            ("CSV",   "📊", "Planilha CSV\nCompatível com qualquer\napplicativo",    self._exportar_csv,   COR_PRIMARIA),
            ("Excel", "📗", "Planilha Excel\nFormatada profissionalmente\ncom resumo",self._exportar_excel, COR_SUCESSO),
            ("PDF",   "📄", "Relatório PDF\nCompleto com tabelas\ne resumo visual",   self._exportar_pdf,   COR_PERIGO),
        ]

        for i, (nome, icone, desc, cmd, cor) in enumerate(formatos):
            card = ctk.CTkFrame(cards, fg_color=COR_CARD, corner_radius=14)
            card.grid(row=0, column=i, padx=6, sticky="nsew")
            ctk.CTkLabel(card, text=icone, font=ctk.CTkFont(size=36)).pack(pady=(20, 4))
            ctk.CTkLabel(card, text=nome, font=ctk.CTkFont(size=15, weight="bold"),
                         text_color=COR_TEXTO).pack()
            ctk.CTkLabel(card, text=desc, font=ctk.CTkFont(size=10),
                         text_color=COR_TEXTO_SUAVE, justify="center").pack(pady=(4, 12))
            ctk.CTkButton(card, text=f"Exportar {nome}", command=cmd,
                          fg_color=cor, corner_radius=8).pack(padx=20, pady=(0, 20), fill="x")

        # Log
        ctk.CTkLabel(self, text="Log:", text_color=COR_TEXTO_SUAVE).grid(row=3, column=0, sticky="w", pady=(15, 4))
        self.txt_log = ctk.CTkTextbox(self, height=120, fg_color=COR_CARD, corner_radius=10)
        self.txt_log.grid(row=4, column=0, sticky="ew")
        self._log("Selecione o período e clique em exportar.")

    def _log(self, msg):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _get_periodo(self):
        try:
            return int(self.var_mes.get()), int(self.var_ano.get())
        except ValueError:
            return None, None

    def _exportar_csv(self):
        caminho = filedialog.asksaveasfilename(defaultextension=".csv",
                                               filetypes=[("CSV", "*.csv")])
        if not caminho:
            return
        mes, ano = self._get_periodo()
        db = self.app._obter_db()
        try:
            from app.services.export_service import ExportService
            ExportService(db).exportar_csv(caminho, mes, ano)
            self._log(f"✅ CSV exportado: {caminho}")
        except Exception as e:
            self._log(f"❌ Erro: {e}")
        finally:
            db.close()

    def _exportar_excel(self):
        caminho = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                               filetypes=[("Excel", "*.xlsx")])
        if not caminho:
            return
        mes, ano = self._get_periodo()
        db = self.app._obter_db()
        try:
            from app.services.export_service import ExportService
            ExportService(db).exportar_excel(caminho, mes, ano)
            self._log(f"✅ Excel exportado: {caminho}")
        except Exception as e:
            self._log(f"❌ Erro: {e}")
        finally:
            db.close()

    def _exportar_pdf(self):
        caminho = filedialog.asksaveasfilename(defaultextension=".pdf",
                                               filetypes=[("PDF", "*.pdf")])
        if not caminho:
            return
        mes, ano = self._get_periodo()
        db = self.app._obter_db()
        try:
            from app.services.export_service import ExportService
            ExportService(db).exportar_pdf(caminho, mes, ano)
            self._log(f"✅ PDF exportado: {caminho}")
        except Exception as e:
            self._log(f"❌ Erro: {e}")
        finally:
            db.close()


# ================================================
# Frame: Assistente Conversacional (Gemini)
# ================================================

class AssistenteFrame(ctk.CTkFrame):
    """Chat com o assistente financeiro Vorcaro — powered by Google Gemini."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._assistente_api_url = os.getenv("ASSISTENTE_API_URL", "http://127.0.0.1:8000/assistente/")
        self._pensando = False        # Evita envios duplos durante resposta
        self._chance_meme_auto = float(os.getenv("GUI_MEME_AUTO_CHANCE", "0.45"))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._construir_ui()
        self._verificar_api_key()

    # --------------------------------------------------
    # Construção da UI
    # --------------------------------------------------

    def _construir_ui(self):
        # Cabeçalho
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="🤖 Vorcaro",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=COR_TEXTO).grid(row=0, column=0, sticky="w")

        self.lbl_status_api = ctk.CTkLabel(
            header, text="⚙️ Gemini não configurado",
            font=ctk.CTkFont(size=11), text_color=COR_AVISO,
        )
        self.lbl_status_api.grid(row=0, column=1, sticky="e", padx=(0, 4))

        self.btn_config_api = ctk.CTkButton(
            header, text="Configurar API ⚙️", width=130,
            height=26, corner_radius=6,
            fg_color=COR_SECUNDARIA, hover_color=COR_PRIMARIA,
            font=ctk.CTkFont(size=11),
            command=self._dialog_configurar_api,
        )
        self.btn_config_api.grid(row=0, column=2, sticky="e")

        # Área de chat
        self.chat = ctk.CTkTextbox(self, font=ctk.CTkFont(size=12),
                                    fg_color=COR_CARD, corner_radius=12, state="disabled")
        self.chat.grid(row=1, column=0, sticky="nsew")

        # Sugestões rápidas
        sugestoes = ctk.CTkFrame(self, fg_color="transparent")
        sugestoes.grid(row=2, column=0, sticky="ew", pady=(8, 4))
        ctk.CTkLabel(sugestoes, text="Sugestões:", text_color=COR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 8))
        perguntas = [
            "Quanto gastei este mês?",
            "Qual minha maior despesa?",
            "Estou gastando mais que no mês passado?",
            "Onde posso economizar?",
            "Como está meu orçamento?",
        ]
        for p in perguntas:
            ctk.CTkButton(sugestoes, text=p, font=ctk.CTkFont(size=10),
                          fg_color="#2C2C54", hover_color=COR_PRIMARIA,
                          height=26, corner_radius=6,
                          command=lambda q=p: self._enviar(q)).pack(side="left", padx=3)

        # Input
        input_frame = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)
        input_frame.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        input_frame.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Faça uma pergunta financeira ao Vorcaro...",
            font=ctk.CTkFont(size=13), border_width=0, fg_color="transparent",
        )
        self.entry.grid(row=0, column=0, sticky="ew", padx=(12, 6), pady=10)
        self.entry.bind("<Return>", lambda e: self._enviar())

        self.btn_enviar = ctk.CTkButton(
            input_frame, text="Enviar ▶", width=90,
            fg_color=COR_PRIMARIA, command=self._enviar,
        )
        self.btn_enviar.grid(row=0, column=1, padx=(0, 8), pady=8)

    def _verificar_api_key(self):
        """Lê a chave da env e atualiza status visual."""
        from dotenv import load_dotenv
        from app.services.local_ai_service import LocalAIService
        from app.services.openrouter_service import OpenRouterService
        _env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
        )
        load_dotenv(_env_path, override=True)
        key = os.getenv("GEMINI_API_KEY", "")
        local_ai = LocalAIService()
        openrouter_ai = OpenRouterService()
        if key and key != "sua_chave_gemini_aqui":
            self.lbl_status_api.configure(text="✅ Gemini ativo", text_color=COR_SUCESSO)
            self.btn_config_api.configure(text="Reconfigurar ⚙️")
            self._exibir_boas_vindas()
        elif openrouter_ai.disponivel():
            self.lbl_status_api.configure(text="🟢 OpenRouter free ativo", text_color=COR_SUCESSO)
            self.btn_config_api.configure(text="Configurar API ⚙️")
            self._exibir("🤖 Vorcaro", (
                "Olá! Estou usando fallback online gratuito (OpenRouter) no momento.\n"
                "Quando o Gemini estiver disponível, ele volta a ser o provedor principal."
            ), COR_PRIMARIA)
        elif local_ai.disponivel():
            self.lbl_status_api.configure(text="🟢 IA local ativa", text_color=COR_SUCESSO)
            self.btn_config_api.configure(text="Configurar API ⚙️")
            self._exibir("🤖 Vorcaro", (
                "Olá! Sou o Vorcaro, seu assistente financeiro pessoal.\n\n"
                "Estou operando em IA local gratuita (Ollama).\n"
                "Se você configurar Gemini, uso Gemini e volto para local automaticamente quando houver limite/crédito."
            ), COR_PRIMARIA)
        else:
            self._exibir("🤖 Vorcaro", (
                "Olá! Sou o Vorcaro, seu assistente financeiro pessoal.\n\n"
                "Você pode usar Gemini (com fallback automático) ou IA local grátis.\n"
                "Para modo local, instale Ollama e rode: ollama serve"
            ), COR_PRIMARIA)

    def _exibir_boas_vindas(self):
        self._exibir("🤖 Vorcaro", (
            "Olá! Sou o Vorcaro, seu assistente financeiro pessoal com IA do Google Gemini.\n\n"
            "Posso te ajudar com:\n"
            "• Análise de gastos por categoria e período\n"
            "• Comparação com meses anteriores\n"
            "• Dicas de economia personalizadas\n"
            "• Status de orçamentos e metas\n"
            "• Qualquer pergunta sobre suas finanças!\n\n"
            "💬 Pode perguntar à vontade — contexto já carregado."
        ), COR_PRIMARIA)

    # --------------------------------------------------
    # Diálogo de configuração da API
    # --------------------------------------------------

    def _dialog_configurar_api(self):
        """Abre dialog para inserir e salvar a chave da API Gemini."""
        from dotenv import load_dotenv
        load_dotenv()
        chave_atual = os.getenv("GEMINI_API_KEY", "")

        dlg = ctk.CTkToplevel(self)
        dlg.title("Configurar Google Gemini")
        dlg.geometry("520x320")
        dlg.resizable(False, False)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="🔑 Configurar Google Gemini API",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=COR_TEXTO).pack(pady=(20, 4))

        ctk.CTkLabel(
            dlg,
            text=(
                "Obtenha sua chave gratuita em:\n"
                "aistudio.google.com  →  Get API key"
            ),
            font=ctk.CTkFont(size=11),
            text_color=COR_TEXTO_SUAVE,
        ).pack(pady=(0, 12))

        entry_key = ctk.CTkEntry(
            dlg, width=440, show="*",
            placeholder_text="AIzaSy...",
            font=ctk.CTkFont(size=12),
        )
        entry_key.pack(padx=20)
        if chave_atual and chave_atual != "sua_chave_gemini_aqui":
            entry_key.insert(0, chave_atual)

        lbl_erro = ctk.CTkLabel(dlg, text="", text_color=COR_PERIGO,
                                font=ctk.CTkFont(size=11))
        lbl_erro.pack(pady=(6, 0))

        def _salvar():
            key = entry_key.get().strip()
            if len(key) < 20:
                lbl_erro.configure(text="⚠️ Chave inválida — verifique e tente novamente.")
                return
            # Persiste no arquivo .env dentro do projeto
            env_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                ".env"
            )
            _salvar_env_key(env_path, "GEMINI_API_KEY", key)
            os.environ["GEMINI_API_KEY"] = key   # atualiza processo atual
            self.lbl_status_api.configure(text="✅ Gemini ativo", text_color=COR_SUCESSO)
            self.btn_config_api.configure(text="Reconfigurar ⚙️")
            dlg.destroy()
            self._exibir("⚙️ Sistema", "Chave Gemini configurada com sucesso! Próxima pergunta iniciará nova sessão.", COR_SUCESSO)

        btns = ctk.CTkFrame(dlg, fg_color="transparent")
        btns.pack(pady=16)
        ctk.CTkButton(btns, text="💾 Salvar", width=120,
                      fg_color=COR_SUCESSO, command=_salvar).pack(side="left", padx=8)
        ctk.CTkButton(btns, text="Cancelar", width=100,
                      fg_color=COR_SECUNDARIA, command=dlg.destroy).pack(side="left", padx=8)

        entry_key.bind("<Return>", lambda e: _salvar())

    # --------------------------------------------------
    # Utilitários de exibição
    # --------------------------------------------------

    def _exibir(self, autor: str, texto: str, cor: str):
        self.chat.configure(state="normal")
        self.chat.insert("end", f"\n{autor}:\n", ("autor",))
        self.chat.insert("end", f"{texto}\n")
        self.chat.tag_config("autor", foreground=cor)
        self.chat.see("end")
        self.chat.configure(state="disabled")

    def _set_pensando(self, ativo: bool):
        self._pensando = ativo
        estado = "disabled" if ativo else "normal"
        self.btn_enviar.configure(state=estado, text="..." if ativo else "Enviar ▶")
        self.entry.configure(state=estado)

    # --------------------------------------------------
    # Envio de mensagem
    # --------------------------------------------------

    def _enviar(self, pergunta: Optional[str] = None):
        if self._pensando:
            return

        q = pergunta or self.entry.get().strip()
        if not q:
            return

        self._exibir("Você", q, COR_AVISO)
        self.entry.delete(0, "end")
        self._set_pensando(True)
        self._exibir("🤖 Vorcaro", "⌛ Pensando...", COR_TEXTO_SUAVE)

        def responder():
            resposta = ""
            provedor = ""
            try:
                timeout = float(os.getenv("ASSISTENTE_API_TIMEOUT_SECONDS", "70"))
                resposta_api = requests.post(
                    self._assistente_api_url,
                    json={"pergunta": q},
                    timeout=timeout,
                )
                resposta_api.raise_for_status()
                dados = resposta_api.json()
                resposta = str(dados.get("resposta") or "")
                provedor = str(dados.get("provedor") or "")
                if not resposta:
                    resposta = "❌ O backend respondeu sem conteúdo para esta pergunta."
            except requests.exceptions.Timeout:
                resposta = (
                    "❌ O assistente excedeu o tempo limite de resposta.\n"
                    "Verifique se a API está ativa e se o provedor configurado está respondendo."
                )
                provedor = "erro"
            except requests.exceptions.ConnectionError:
                resposta = (
                    "❌ Não foi possível conectar ao backend do assistente.\n"
                    "Inicie a API local antes de usar o Vorcaro na GUI."
                )
                provedor = "erro"
            except requests.exceptions.HTTPError as exc:
                try:
                    detalhe = exc.response.json()
                except ValueError:
                    detalhe = exc.response.text if exc.response is not None else str(exc)
                resposta = f"❌ O backend retornou um erro: {detalhe}"
                provedor = "erro"
            except Exception as exc:
                resposta = f"❌ Falha ao consultar o assistente: {exc}"
                provedor = "erro"

            def _atualizar():
                texto_resposta = resposta
                # Remove o "⌛ Pensando..." e exibe resposta real
                self.chat.configure(state="normal")
                idx = self.chat.search("⌛ Pensando...", "1.0", "end")
                if idx:
                    # Apaga a linha do "Pensando"
                    line_start = idx
                    line_end   = f"{idx}+{len('⌛ Pensando...')+1}c"
                    self.chat.delete(line_start, line_end)
                self.chat.configure(state="disabled")

                if provedor == "openrouter_free":
                    texto_resposta = "ℹ️ Usando IA secundária (OpenRouter free).\n\n" + texto_resposta
                elif provedor == "ollama_local":
                    texto_resposta = "ℹ️ Usando IA secundária local (Ollama).\n\n" + texto_resposta

                if provedor == "gemini":
                    self.lbl_status_api.configure(text="✅ Gemini ativo", text_color=COR_SUCESSO)
                elif provedor == "openrouter_free":
                    self.lbl_status_api.configure(text="🟢 OpenRouter free ativo", text_color=COR_SUCESSO)
                elif provedor == "ollama_local":
                    self.lbl_status_api.configure(text="🟢 IA local ativa", text_color=COR_SUCESSO)
                elif provedor == "historico":
                    self.lbl_status_api.configure(text="🟡 Resposta analítica local", text_color=COR_AVISO)
                else:
                    self.lbl_status_api.configure(text="🔴 Falha ao consultar assistente", text_color=COR_PERIGO)

                self._exibir("🤖 Vorcaro", texto_resposta, COR_PRIMARIA)
                if random.random() <= self._chance_meme_auto:
                    self._exibir("😏 Meme Vorcaro", self.app.proximo_meme_gui(), COR_AVISO)
                self._set_pensando(False)

            _after_seguro(self, 0, _atualizar)

        threading.Thread(target=responder, daemon=True).start()

    def receber_meme_automatico(self):
        if random.random() <= self._chance_meme_auto:
            self._exibir("😏 Meme Vorcaro", self.app.proximo_meme_gui(), COR_AVISO)


# ================================================
# Frame: Categorias (CRUD)
# ================================================

class CategoriasFrame(ctk.CTkFrame):
    """CRUD completo de categorias financeiras."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._ids_por_iid: dict = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._construir_ui()
        self.carregar_dados()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _construir_ui(self):
        # Cabeçalho
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="🏷️ Categorias",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=COR_TEXTO).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(header, text="➕ Nova Categoria",
                      fg_color=COR_SUCESSO, hover_color="#1E8449",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      command=self._dialog_categoria).grid(row=0, column=1, sticky="e")

        # Tabela
        frame_tabela = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)
        frame_tabela.grid(row=1, column=0, sticky="nsew")
        frame_tabela.grid_columnconfigure(0, weight=1)
        frame_tabela.grid_rowconfigure(0, weight=1)

        colunas = ("icone", "nome", "descricao", "cor", "status")
        self.tree = ttk.Treeview(frame_tabela, columns=colunas, show="headings", height=18)

        self.tree.heading("icone",    text="🎨 Ícone")
        self.tree.heading("nome",     text="Nome")
        self.tree.heading("descricao",text="Descrição")
        self.tree.heading("cor",      text="Cor")
        self.tree.heading("status",   text="Status")

        self.tree.column("icone",    width=70,  anchor="center")
        self.tree.column("nome",     width=200)
        self.tree.column("descricao",width=380)
        self.tree.column("cor",      width=100, anchor="center")
        self.tree.column("status",   width=100, anchor="center")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                         background="#0F3460", foreground="white",
                         fieldbackground="#0F3460", rowheight=28,
                         font=("Arial", 11))
        style.configure("Treeview.Heading",
                         background="#1B4F72", foreground="white",
                         font=("Arial", 11, "bold"))
        style.map("Treeview", background=[("selected", COR_PRIMARIA)])

        sb = ctk.CTkScrollbar(frame_tabela, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        sb.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=8)

        # Duplo clique para editar
        self.tree.bind("<Double-1>", lambda e: self._editar_selecionado())

        # Botões de ação
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        ctk.CTkButton(btn_frame, text="✏️ Editar",
                      fg_color=COR_PRIMARIA,
                      command=self._editar_selecionado).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_frame, text="🔄 Ativar / Desativar",
                      fg_color=COR_AVISO, hover_color="#D68910",
                      command=self._toggle_ativo).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_frame, text="🗑️ Excluir",
                      fg_color=COR_PERIGO, hover_color="#C0392B",
                      command=self._excluir_selecionado).pack(side="left")

    # --------------------------------------------------
    # Dados
    # --------------------------------------------------

    def carregar_dados(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        self._ids_por_iid = {}
        db = self.app._obter_db()
        try:
            from app.models import Categoria
            cats = db.query(Categoria).order_by(Categoria.nome).all()
            for c in cats:
                status = "✅ Ativa" if c.ativa else "⛔ Inativa"
                iid = self.tree.insert("", "end", values=(
                    c.icone or "💰",
                    c.nome,
                    c.descricao or "",
                    c.cor or "#3498db",
                    status,
                ))
                self._ids_por_iid[iid] = c.id
        finally:
            db.close()

    # --------------------------------------------------
    # Ações
    # --------------------------------------------------

    def _get_id_selecionado(self) -> Optional[int]:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("É preciso selecionar", "Selecione uma categoria na tabela.", parent=self)
            return None
        return self._ids_por_iid.get(sel[0])

    def _dialog_categoria(self, cat_id: Optional[int] = None):
        """Abre dialog para criar ou editar categoria."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Nova Categoria" if cat_id is None else "Editar Categoria")
        dialog.geometry("420x370")
        dialog.resizable(False, False)
        dialog.grab_set()

        # Carrega dados existentes (edição)
        cat = None
        if cat_id:
            db = self.app._obter_db()
            try:
                from app.models import Categoria
                cat = db.query(Categoria).filter(Categoria.id == cat_id).first()
            finally:
                db.close()

        titulo_txt = "➕ Nova Categoria" if cat is None else "✏️ Editar Categoria"
        ctk.CTkLabel(dialog, text=titulo_txt,
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 12))

        frame = ctk.CTkFrame(dialog, fg_color="transparent")
        frame.pack(padx=20, fill="x")

        # Nome
        ctk.CTkLabel(frame, text="Nome *:").pack(anchor="w")
        e_nome = ctk.CTkEntry(frame, placeholder_text="Ex: Alimentação")
        e_nome.pack(fill="x", pady=(0, 8))
        if cat:
            e_nome.insert(0, cat.nome)

        # Ícone
        ctk.CTkLabel(frame, text="Ícone (emoji):").pack(anchor="w")
        e_icone = ctk.CTkEntry(frame, placeholder_text="Ex: 🍔")
        e_icone.pack(fill="x", pady=(0, 8))
        e_icone.insert(0, (cat.icone if cat and cat.icone else "💰"))

        # Cor
        ctk.CTkLabel(frame, text="Cor (hex):").pack(anchor="w")
        e_cor = ctk.CTkEntry(frame, placeholder_text="Ex: #3498db")
        e_cor.pack(fill="x", pady=(0, 8))
        e_cor.insert(0, (cat.cor if cat and cat.cor else "#3498db"))

        # Descrição
        ctk.CTkLabel(frame, text="Descrição:").pack(anchor="w")
        e_desc = ctk.CTkEntry(frame, placeholder_text="Ex: Gastos com comida e bebida")
        e_desc.pack(fill="x", pady=(0, 15))
        if cat and cat.descricao:
            e_desc.insert(0, cat.descricao)

        def salvar():
            nome = e_nome.get().strip()
            if not nome:
                messagebox.showwarning("É preciso preencher", "O nome é obrigatório.", parent=dialog)
                return

            db2 = self.app._obter_db()
            try:
                from app.models import Categoria
                if cat_id:
                    c = db2.query(Categoria).filter(Categoria.id == cat_id).first()
                    if not c:
                        return
                    c.nome     = nome
                    c.icone    = e_icone.get().strip() or "💰"
                    c.cor      = e_cor.get().strip() or "#3498db"
                    c.descricao = e_desc.get().strip() or None
                else:
                    existe = db2.query(Categoria).filter(Categoria.nome == nome).first()
                    if existe:
                        messagebox.showwarning("É preciso verificar",
                                               f"Categoria '{nome}' já existe.", parent=dialog)
                        return
                    c = Categoria(
                        nome=nome,
                        icone=e_icone.get().strip() or "💰",
                        cor=e_cor.get().strip() or "#3498db",
                        descricao=e_desc.get().strip() or None,
                        ativa=True,
                    )
                    db2.add(c)
                db2.commit()
            finally:
                db2.close()

            dialog.destroy()
            self.carregar_dados()

        ctk.CTkButton(dialog, text="💾 Salvar", command=salvar,
                      fg_color=COR_SUCESSO, hover_color="#1E8449").pack(pady=5, padx=20, fill="x")

    def _editar_selecionado(self):
        cat_id = self._get_id_selecionado()
        if cat_id:
            self._dialog_categoria(cat_id=cat_id)

    def _toggle_ativo(self):
        cat_id = self._get_id_selecionado()
        if not cat_id:
            return
        db = self.app._obter_db()
        try:
            from app.models import Categoria
            c = db.query(Categoria).filter(Categoria.id == cat_id).first()
            if c:
                c.ativa = not c.ativa
                db.commit()
                estado = "ativada" if c.ativa else "desativada"
                messagebox.showinfo("✅", f"Categoria '{c.nome}' {estado}.", parent=self)
        finally:
            db.close()
        self.carregar_dados()

    def _excluir_selecionado(self):
        cat_id = self._get_id_selecionado()
        if not cat_id:
            return

        db = self.app._obter_db()
        try:
            from app.models import Categoria, Transacao
            c = db.query(Categoria).filter(Categoria.id == cat_id).first()
            if not c:
                return
            nome   = c.nome
            n_trans = db.query(Transacao).filter(Transacao.categoria_id == cat_id).count()
        finally:
            db.close()

        if n_trans > 0:
            confirma = messagebox.askyesno(
                "⚠️ Atenção",
                f"A categoria '{nome}' possui {n_trans} transação(oes) vinculadas.\n"
                f"As transações ficarão sem categoria após exclusão.\n\nDeseja continuar?",
                parent=self,
            )
        else:
            confirma = messagebox.askyesno(
                "Confirmar Exclusão",
                f"Deseja excluir a categoria '{nome}'?",
                parent=self,
            )
        if not confirma:
            return

        db = self.app._obter_db()
        try:
            from app.models import Categoria
            c = db.query(Categoria).filter(Categoria.id == cat_id).first()
            if c:
                db.delete(c)
                db.commit()
                messagebox.showinfo("✅", f"Categoria '{nome}' excluída.", parent=self)
        finally:
            db.close()
        self.carregar_dados()


# ================================================
# Frame: Configurações
# ================================================

class ConfiguracoesFrame(ctk.CTkFrame):
    """Configurações do sistema."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self._construir_ui()

    def _construir_ui(self):
        ctk.CTkLabel(self, text="⚙️ Configurações",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=COR_TEXTO).grid(row=0, column=0, sticky="w", pady=(0, 15))

        row = 1

        # Aparência
        sec = self._secao("🎨 Aparência", row); row += 1
        modo_frame = ctk.CTkFrame(sec, fg_color="transparent")
        modo_frame.pack(fill="x", padx=15, pady=8)
        ctk.CTkLabel(modo_frame, text="Tema:", text_color=COR_TEXTO).pack(side="left")
        ctk.CTkOptionMenu(modo_frame, values=["Dark", "Light", "System"],
                          command=lambda m: ctk.set_appearance_mode(m)
                          ).pack(side="left", padx=10)

        # Banco de dados
        sec2 = self._secao("🗄️ Banco de Dados", row); row += 1
        db_frame = ctk.CTkFrame(sec2, fg_color="transparent")
        db_frame.pack(fill="x", padx=15, pady=8)
        from app.database import DATABASE_URL
        ctk.CTkLabel(db_frame, text=f"Banco: {DATABASE_URL}",
                     text_color=COR_TEXTO_SUAVE, font=ctk.CTkFont(size=11)).pack(side="left")

        # Telegram
        sec3 = self._secao("📱 Telegram", row); row += 1
        tel_frame = ctk.CTkFrame(sec3, fg_color="transparent")
        tel_frame.pack(fill="x", padx=15, pady=8)
        tel_frame.grid_columnconfigure(1, weight=1)

        token_atual = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id_atual = os.getenv("TELEGRAM_CHAT_ID", "")

        ctk.CTkLabel(tel_frame, text="Token:", text_color=COR_TEXTO).grid(row=0, column=0, sticky="w")
        self.e_telegram_token = ctk.CTkEntry(
            tel_frame, width=320, show="*",
            placeholder_text="Cole seu token do @BotFather aqui"
        )
        self.e_telegram_token.insert(0, token_atual)
        self.e_telegram_token.grid(row=0, column=1, padx=8, sticky="ew")

        ctk.CTkLabel(tel_frame, text="Chat ID:", text_color=COR_TEXTO).grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.e_telegram_chat = ctk.CTkEntry(
            tel_frame, width=320,
            placeholder_text="Ex: 123456789"
        )
        self.e_telegram_chat.insert(0, chat_id_atual)
        self.e_telegram_chat.grid(row=1, column=1, padx=8, pady=(8, 0), sticky="ew")

        self.lbl_telegram_status = ctk.CTkLabel(
            sec3,
            text="",
            text_color=COR_TEXTO_SUAVE,
            font=ctk.CTkFont(size=11),
        )
        self.lbl_telegram_status.pack(anchor="w", padx=15, pady=(0, 8))

        btns_tel = ctk.CTkFrame(sec3, fg_color="transparent")
        btns_tel.pack(fill="x", padx=15, pady=(0, 8))
        ctk.CTkButton(
            btns_tel,
            text="💾 Salvar Telegram",
            fg_color=COR_SUCESSO,
            hover_color="#1E8449",
            command=self._salvar_telegram,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btns_tel,
            text="📨 Enviar teste",
            fg_color=COR_PRIMARIA,
            command=self._testar_telegram,
        ).pack(side="left")

        ctk.CTkLabel(
            sec3,
            text="Use o chat com o bot no Telegram e informe aqui o chat id que receberá as mensagens.",
            text_color=COR_TEXTO_SUAVE,
            font=ctk.CTkFont(size=11),
            justify="left",
        ).pack(anchor="w", padx=15, pady=(0, 10))

        self._atualizar_status_telegram()

        # Memes e Humor
        sec_memes = self._secao("😏 Memes e Humor", row); row += 1
        
        # Telegram meme frequency
        lbl_tel_meme = ctk.CTkLabel(sec_memes, text="Frequência de Memes no Telegram:", 
                                    text_color=COR_TEXTO, font=ctk.CTkFont(size=11))
        lbl_tel_meme.pack(anchor="w", padx=15, pady=(10, 5))
        
        telegram_meme_freq = float(os.getenv("TELEGRAM_MEME_AUTO_CHANCE", "0.35")) * 100
        self.lbl_telegram_meme_freq = ctk.CTkLabel(sec_memes, text=f"{int(telegram_meme_freq)}%",
                                                    text_color=COR_PRIMARIA, 
                                                    font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_telegram_meme_freq.pack(anchor="e", padx=15, pady=(0, 5))
        
        self.slider_telegram_meme = ctk.CTkSlider(
            sec_memes,
            from_=0, to=100,
            number_of_steps=20,
            fg_color=COR_PRIMARIA,
            progress_color=COR_SUCESSO,
            command=self._atualizar_freq_telegram_meme
        )
        self.slider_telegram_meme.set(telegram_meme_freq)
        self.slider_telegram_meme.pack(fill="x", padx=15, pady=(0, 20))
        
        # GUI meme frequency
        lbl_gui_meme = ctk.CTkLabel(sec_memes, text="Frequência de Memes na GUI:", 
                                   text_color=COR_TEXTO, font=ctk.CTkFont(size=11))
        lbl_gui_meme.pack(anchor="w", padx=15, pady=(0, 5))
        
        gui_meme_freq = float(os.getenv("GUI_MEME_AUTO_CHANCE", "0.45")) * 100
        self.lbl_gui_meme_freq = ctk.CTkLabel(sec_memes, text=f"{int(gui_meme_freq)}%",
                                               text_color=COR_PRIMARIA, 
                                               font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_gui_meme_freq.pack(anchor="e", padx=15, pady=(0, 5))
        
        self.slider_gui_meme = ctk.CTkSlider(
            sec_memes,
            from_=0, to=100,
            number_of_steps=20,
            fg_color=COR_PRIMARIA,
            progress_color=COR_SUCESSO,
            command=self._atualizar_freq_gui_meme
        )
        self.slider_gui_meme.set(gui_meme_freq)
        self.slider_gui_meme.pack(fill="x", padx=15, pady=(0, 15))
        
        # Botão salvar memes
        ctk.CTkButton(
            sec_memes,
            text="💾 Salvar Preferências de Memes",
            fg_color=COR_SUCESSO,
            hover_color="#1E8449",
            command=self._salvar_memes_config,
        ).pack(pady=(0, 15))
        
        ctk.CTkLabel(
            sec_memes,
            text="Ajuste a frequência com que memes aparecem automaticamente no sistema.",
            text_color=COR_TEXTO_SUAVE,
            font=ctk.CTkFont(size=11),
            justify="left",
        ).pack(anchor="w", padx=15, pady=(0, 10))

        # Sobre
        sec4 = self._secao("ℹ️ Sobre", row); row += 1
        ctk.CTkLabel(sec4, text=(
            "Vorcaro v1.0.0\n"
            "Python • FastAPI • SQLite • CustomTkinter\n"
            "Desenvolvido com ❤️ para gestão financeira pessoal inteligente."
        ), text_color=COR_TEXTO_SUAVE, font=ctk.CTkFont(size=11),
            justify="left").pack(padx=15, pady=10, anchor="w")

    def _secao(self, titulo: str, row: int) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)
        frame.grid(row=row, column=0, sticky="ew", pady=5)
        ctk.CTkLabel(frame, text=titulo,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_TEXTO).pack(anchor="w", padx=15, pady=(10, 0))
        return frame

    def _salvar_telegram(self):
        token = self.e_telegram_token.get().strip()
        chat_id = self.e_telegram_chat.get().strip()
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".env"
        )
        _salvar_env_key(env_path, "TELEGRAM_BOT_TOKEN", token)
        _salvar_env_key(env_path, "TELEGRAM_CHAT_ID", chat_id)
        os.environ["TELEGRAM_BOT_TOKEN"] = token
        os.environ["TELEGRAM_CHAT_ID"] = chat_id
        self._atualizar_status_telegram()
        messagebox.showinfo("Telegram", "Configuração do Telegram salva com sucesso.", parent=self)

    def _atualizar_status_telegram(self):
        try:
            from app.services.notificacoes.telegram_service import TelegramService
            status = TelegramService().status()
        except Exception as exc:
            self.lbl_telegram_status.configure(
                text=f"Erro ao verificar Telegram: {exc}",
                text_color=COR_PERIGO,
            )
            return

        if status["ativo"] and status["token_ok"] and status["chat_ok"]:
            self.lbl_telegram_status.configure(
                text="Status: Telegram ativo e pronto para enviar mensagens.",
                text_color=COR_SUCESSO,
            )
        elif status["token_ok"] and not status["chat_ok"]:
            self.lbl_telegram_status.configure(
                text="Status: token configurado, mas falta o chat id.",
                text_color=COR_AVISO,
            )
        else:
            self.lbl_telegram_status.configure(
                text="Status: Telegram não configurado.",
                text_color=COR_AVISO,
            )

    def _testar_telegram(self):
        token = self.e_telegram_token.get().strip()
        chat_id = self.e_telegram_chat.get().strip()
        if not token or not chat_id:
            messagebox.showwarning(
                "Telegram",
                "Preencha token e chat id antes de testar.",
                parent=self,
            )
            return

        self._salvar_telegram()

        def _executar_teste():
            try:
                from app.services.notificacoes.telegram_service import TelegramService
                ok = TelegramService().enviar_mensagem_sync(
                    "✅ Teste do Vorcaro: Telegram configurado com sucesso.",
                    chat_id=chat_id,
                )
            except Exception as exc:
                _after_seguro(self, 0, lambda: messagebox.showerror(
                    "Telegram",
                    f"Erro ao testar Telegram: {exc}",
                    parent=self,
                ))
                return

            _after_seguro(self, 0, lambda: self._resultado_teste_telegram(ok))

        threading.Thread(target=_executar_teste, daemon=True).start()

    def _resultado_teste_telegram(self, ok: bool):
        self._atualizar_status_telegram()
        if ok:
            messagebox.showinfo(
                "Telegram",
                "Mensagem de teste enviada com sucesso.",
                parent=self,
            )
        else:
            messagebox.showerror(
                "Telegram",
                "Falha ao enviar mensagem. Verifique token e chat id.",
                parent=self,
            )

    def _atualizar_freq_telegram_meme(self, valor: float):
        """Atualiza o label de frequência de memes no Telegram."""
        self.lbl_telegram_meme_freq.configure(text=f"{int(float(valor))}%")

    def _atualizar_freq_gui_meme(self, valor: float):
        """Atualiza o label de frequência de memes na GUI."""
        self.lbl_gui_meme_freq.configure(text=f"{int(float(valor))}%")

    def _salvar_memes_config(self):
        """Salva as configurações de frequência de memes no .env."""
        telegram_freq = self.slider_telegram_meme.get() / 100.0
        gui_freq = self.slider_gui_meme.get() / 100.0
        
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".env"
        )
        
        _salvar_env_key(env_path, "TELEGRAM_MEME_AUTO_CHANCE", str(telegram_freq))
        _salvar_env_key(env_path, "GUI_MEME_AUTO_CHANCE", str(gui_freq))
        
        os.environ["TELEGRAM_MEME_AUTO_CHANCE"] = str(telegram_freq)
        os.environ["GUI_MEME_AUTO_CHANCE"] = str(gui_freq)
        
        # Atualizar a frequência no app também
        if hasattr(self.app, '_chance_meme_auto'):
            self.app._chance_meme_auto = gui_freq
        
        messagebox.showinfo(
            "Memes",
            f"Configurações salvas com sucesso!\n\n"
            f"Telegram: {int(telegram_freq * 100)}%\n"
            f"GUI: {int(gui_freq * 100)}%",
            parent=self
        )


# ================================================
# Frame: Agenda Financeira
# ================================================

class AgendaFinanceiraFrame(ctk.CTkFrame):
    """Agenda de eventos financeiros: contas a pagar, receitas esperadas, parcelas."""

    _MESES = ["","Janeiro","Fevereiro","Março","Abril","Maio","Junho",
               "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    _DIAS_SEMANA = ["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"]

    _COR_STATUS = {
        "pendente":  "#F39C12",
        "pago":      "#27AE60",
        "recebido":  "#27AE60",
        "atrasado":  "#E74C3C",
        "cancelado": "#95A5A6",
    }
    _ICONE_TIPO = {
        "conta":    "🧾",
        "receita":  "💵",
        "reserva":  "🏦",
        "parcela":  "💳",
        "outro":    "📌",
    }

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app   = app
        from datetime import date
        self._hoje     = date.today()
        self._mes_vis  = self._hoje.month
        self._ano_vis  = self._hoje.year
        self._dia_sel  = self._hoje
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._construir_ui()
        self._atualizar_status_atrasados()
        self.carregar()

    def _atualizar_status_atrasados(self):
        try:
            from app.services.agenda_service import atualizar_status_atrasados
            db = self.app._obter_db()
            try:
                atualizar_status_atrasados(db)
            finally:
                db.close()
        except Exception:
            pass

    def _construir_ui(self):
        # Cabeçalho
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkLabel(hdr, text="📅 Agenda Financeira",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=COR_TEXTO).pack(side="left")
        ctk.CTkButton(hdr, text="➕ Novo Evento", width=130,
                      fg_color=COR_SUCESSO, hover_color="#1E8449",
                      command=self._dialog_evento).pack(side="right", padx=5)

        # Layout principal: calendário (esq) + lista (dir)
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew")
        main.grid_columnconfigure(0, weight=0)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        # ── Painel calendário ──
        self._frame_cal = ctk.CTkFrame(main, fg_color=COR_CARD, corner_radius=12, width=300)
        self._frame_cal.grid(row=0, column=0, sticky="nsew", padx=(0,10))
        self._frame_cal.grid_propagate(False)
        self._construir_calendario()

        # ── Painel lista ──
        right = ctk.CTkFrame(main, fg_color=COR_CARD, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        # Toolbar lista
        tb = ctk.CTkFrame(right, fg_color="transparent")
        tb.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 8))
        self._lbl_mes_lista = ctk.CTkLabel(tb, text="",
                                            font=ctk.CTkFont(size=14, weight="bold"),
                                            text_color=COR_TEXTO)
        self._lbl_mes_lista.pack(side="left")

        # Filtro de status
        self._filtro_var = ctk.StringVar(value="todos")
        for txt, val in [("Todos","todos"),("Pendente","pendente"),
                         ("Pago","pago"),("Atrasado","atrasado")]:
            ctk.CTkRadioButton(tb, text=txt, variable=self._filtro_var,
                               value=val, command=self.carregar,
                               text_color=COR_TEXTO_SUAVE).pack(side="left", padx=6)

        # Treeview
        cols = ("tipo","titulo","vencimento","valor","status")
        frame_tree = ctk.CTkFrame(right, fg_color="transparent")
        frame_tree.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0,8))
        frame_tree.grid_columnconfigure(0, weight=1)
        frame_tree.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        style.configure("Agenda.Treeview",
                        background="#0F3460", foreground="#ECF0F1",
                        fieldbackground="#0F3460", rowheight=26)
        style.configure("Agenda.Treeview.Heading",
                        background="#1B4F72", foreground="#ECF0F1", font=("Arial",10,"bold"))
        style.map("Agenda.Treeview", background=[("selected","#2E86AB")])

        self._tree = ttk.Treeview(frame_tree, columns=cols, show="headings",
                                   style="Agenda.Treeview", selectmode="browse")
        for col, w, texto in [("tipo",40,""),("titulo",220,"Título"),
                               ("vencimento",100,"Vencimento"),
                               ("valor",90,"Valor"),("status",90,"Status")]:
            self._tree.heading(col, text=texto)
            self._tree.column(col, width=w, anchor="center" if col != "titulo" else "w")
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(frame_tree, orient="vertical", command=self._tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.bind("<Double-1>", lambda e: self._editar_sel())

        # Botões ação
        btn_bar = ctk.CTkFrame(right, fg_color="transparent")
        btn_bar.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 12))
        ctk.CTkButton(btn_bar, text="✅ Marcar Pago", width=130,
                      fg_color=COR_SUCESSO, hover_color="#1E8449",
                      command=self._marcar_pago_sel).pack(side="left", padx=4)
        ctk.CTkButton(btn_bar, text="✏️ Editar", width=90,
                      fg_color=COR_PRIMARIA,
                      command=self._editar_sel).pack(side="left", padx=4)
        ctk.CTkButton(btn_bar, text="🗑️ Excluir", width=90,
                      fg_color=COR_PERIGO, hover_color="#922B21",
                      command=self._excluir_sel).pack(side="left", padx=4)

        # Rodapé resumo
        self._lbl_resumo = ctk.CTkLabel(right, text="",
                                         font=ctk.CTkFont(size=11),
                                         text_color=COR_TEXTO_SUAVE)
        self._lbl_resumo.grid(row=3, column=0, sticky="w", padx=15, pady=(0,12))

    def _construir_calendario(self):
        for w in self._frame_cal.winfo_children():
            w.destroy()

        # Nav mês
        nav = ctk.CTkFrame(self._frame_cal, fg_color="transparent")
        nav.pack(fill="x", padx=10, pady=(12,4))
        ctk.CTkButton(nav, text="◀", width=30, fg_color=COR_SECUNDARIA,
                      command=self._mes_anterior).pack(side="left")
        self._lbl_mes_cal = ctk.CTkLabel(nav, text="",
                                          font=ctk.CTkFont(size=13, weight="bold"),
                                          text_color=COR_TEXTO)
        self._lbl_mes_cal.pack(side="left", expand=True)
        ctk.CTkButton(nav, text="▶", width=30, fg_color=COR_SECUNDARIA,
                      command=self._proximo_mes).pack(side="right")

        self._lbl_mes_cal.configure(
            text=f"{self._MESES[self._mes_vis]} {self._ano_vis}")

        # Cabeçalho dias semana
        grid = ctk.CTkFrame(self._frame_cal, fg_color="transparent")
        grid.pack(padx=8, pady=(4,0))
        for i, d in enumerate(self._DIAS_SEMANA):
            ctk.CTkLabel(grid, text=d, width=36,
                         font=ctk.CTkFont(size=10),
                         text_color=COR_TEXTO_SUAVE).grid(row=0, column=i, padx=1)

        import calendar as _cal
        import calendar
        # Quais dias têm eventos
        try:
            from app.services.agenda_service import listar_eventos
            db = self.app._obter_db()
            try:
                evs = listar_eventos(db, self._mes_vis, self._ano_vis)
            finally:
                db.close()
            dias_com_evento = {}
            for ev in evs:
                d = ev.data_vencimento.day
                if d not in dias_com_evento:
                    dias_com_evento[d] = ev.status.value if hasattr(ev.status, 'value') else str(ev.status)
                else:
                    if "atrasado" in [dias_com_evento[d], ev.status.value if hasattr(ev.status,'value') else str(ev.status)]:
                        dias_com_evento[d] = "atrasado"
        except Exception:
            dias_com_evento = {}

        primeiro_dia_semana, n_dias = calendar.monthrange(self._ano_vis, self._mes_vis)
        # primeiro_dia_semana: 0=Seg … 6=Dom
        row = 1
        col = primeiro_dia_semana
        from datetime import date as _date
        for day in range(1, n_dias + 1):
            dia_date = _date(self._ano_vis, self._mes_vis, day)
            eh_hoje   = dia_date == self._hoje
            eh_sel    = dia_date == self._dia_sel
            cor_ev    = self._COR_STATUS.get(dias_com_evento.get(day, ""), None)

            if eh_sel:
                fg = COR_PRIMARIA
            elif eh_hoje:
                fg = COR_SECUNDARIA
            elif cor_ev:
                fg = cor_ev
            else:
                fg = "transparent"

            btn = ctk.CTkButton(
                grid, text=str(day), width=34, height=28,
                fg_color=fg,
                hover_color=COR_PRIMARIA,
                text_color=COR_TEXTO,
                font=ctk.CTkFont(size=11, weight="bold" if eh_hoje or eh_sel else "normal"),
                corner_radius=6,
                command=lambda d=dia_date: self._selecionar_dia(d),
            )
            btn.grid(row=row, column=col, padx=1, pady=2)
            col += 1
            if col > 6:
                col = 0
                row += 1

        # Legenda
        leg = ctk.CTkFrame(self._frame_cal, fg_color="transparent")
        leg.pack(pady=(8, 12), padx=10, fill="x")
        for txt, cor in [("Pendente","#F39C12"),("Pago","#27AE60"),("Atrasado","#E74C3C")]:
            f = ctk.CTkFrame(leg, fg_color="transparent")
            f.pack(side="left", padx=6)
            ctk.CTkLabel(f, text="■", text_color=cor,
                         font=ctk.CTkFont(size=12)).pack(side="left")
            ctk.CTkLabel(f, text=txt, text_color=COR_TEXTO_SUAVE,
                         font=ctk.CTkFont(size=10)).pack(side="left")

    def _mes_anterior(self):
        if self._mes_vis == 1:
            self._mes_vis = 12
            self._ano_vis -= 1
        else:
            self._mes_vis -= 1
        self._construir_calendario()
        self.carregar()

    def _proximo_mes(self):
        if self._mes_vis == 12:
            self._mes_vis = 1
            self._ano_vis += 1
        else:
            self._mes_vis += 1
        self._construir_calendario()
        self.carregar()

    def _selecionar_dia(self, d):
        self._dia_sel = d
        self._construir_calendario()
        self.carregar()

    def carregar(self):
        try:
            from app.services.agenda_service import listar_eventos
            db = self.app._obter_db()
            try:
                evs = listar_eventos(db, self._mes_vis, self._ano_vis)
            finally:
                db.close()
        except Exception as e:
            messagebox.showerror("Erro", str(e))
            return

        filtro = self._filtro_var.get()
        if filtro != "todos":
            evs = [e for e in evs if (e.status.value if hasattr(e.status,'value') else str(e.status)) == filtro]

        self._lbl_mes_lista.configure(
            text=f"{self._MESES[self._mes_vis]} {self._ano_vis}")

        for item in self._tree.get_children():
            self._tree.delete(item)

        total_pagar = 0.0
        total_receber = 0.0
        for ev in evs:
            status_v = ev.status.value if hasattr(ev.status, 'value') else str(ev.status)
            tipo_v   = ev.tipo.value   if hasattr(ev.tipo,   'value') else str(ev.tipo)
            icone    = self._ICONE_TIPO.get(tipo_v, "📌")
            cor_tag  = status_v
            self._tree.insert("", "end", iid=str(ev.id),
                              values=(icone,
                                      ev.titulo,
                                      ev.data_vencimento.strftime("%d/%m/%Y"),
                                      f"R$ {ev.valor:,.2f}",
                                      status_v.capitalize()),
                              tags=(cor_tag,))
            if tipo_v == "receita" and status_v in ("pendente","recebido"):
                total_receber += ev.valor
            elif status_v in ("pendente","atrasado"):
                total_pagar += ev.valor

        self._tree.tag_configure("pago",      foreground="#27AE60")
        self._tree.tag_configure("recebido",  foreground="#27AE60")
        self._tree.tag_configure("atrasado",  foreground="#E74C3C")
        self._tree.tag_configure("pendente",  foreground="#F39C12")
        self._tree.tag_configure("cancelado", foreground="#95A5A6")

        n = len(evs)
        self._lbl_resumo.configure(
            text=f"{n} evento(s)  |  A pagar: R$ {total_pagar:,.2f}  |  A receber: R$ {total_receber:,.2f}")

    def _marcar_pago_sel(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Atenção", "Selecione um evento.")
            return
        ev_id = int(sel[0])
        try:
            from app.services.agenda_service import marcar_pago
            db = self.app._obter_db()
            try:
                marcar_pago(db, ev_id)
            finally:
                db.close()
        except Exception as e:
            messagebox.showerror("Erro", str(e))
            return
        self._construir_calendario()
        self.carregar()

    def _excluir_sel(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Atenção", "Selecione um evento.")
            return
        if not messagebox.askyesno("Confirmar", "Excluir o evento selecionado?"):
            return
        ev_id = int(sel[0])
        try:
            from app.services.agenda_service import excluir_evento
            db = self.app._obter_db()
            try:
                excluir_evento(db, ev_id)
            finally:
                db.close()
        except Exception as e:
            messagebox.showerror("Erro", str(e))
            return
        self._construir_calendario()
        self.carregar()

    def _editar_sel(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Atenção", "Selecione um evento.")
            return
        ev_id = int(sel[0])
        try:
            from app.models import EventoFinanceiro as EvM
            db = self.app._obter_db()
            try:
                ev = db.query(EvM).get(ev_id)
                if not ev:
                    return
                dados = {
                    "titulo":          ev.titulo,
                    "descricao":       ev.descricao or "",
                    "valor":           ev.valor,
                    "data_vencimento": ev.data_vencimento,
                    "tipo":            ev.tipo.value if hasattr(ev.tipo,'value') else str(ev.tipo),
                    "recorrente":      ev.recorrente,
                    "dia_recorrencia": ev.dia_recorrencia,
                    "codigo_barras":   ev.codigo_barras or "",
                    "categoria_id":    ev.categoria_id,
                }
            finally:
                db.close()
        except Exception as e:
            messagebox.showerror("Erro", str(e))
            return
        self._dialog_evento(ev_id, dados)

    def _dialog_evento(self, ev_id=None, dados=None):
        """Diálogo para criar ou editar um evento financeiro."""
        d = ctk.CTkToplevel(self)
        d.title("Novo Evento" if ev_id is None else "Editar Evento")
        d.geometry("430x500")
        d.resizable(False, False)
        d.grab_set()

        ctk.CTkLabel(d, text="📅 Evento Financeiro",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=COR_TEXTO).pack(pady=(18, 8))

        frm = ctk.CTkScrollableFrame(d, fg_color="transparent")
        frm.pack(fill="both", expand=True, padx=20)

        def campo(label, widget_fn):
            ctk.CTkLabel(frm, text=label, text_color=COR_TEXTO_SUAVE,
                         font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(8, 2))
            w = widget_fn()
            w.pack(fill="x")
            return w

        e_titulo = campo("Título *", lambda: ctk.CTkEntry(frm, placeholder_text="Ex: Conta de luz"))
        e_valor  = campo("Valor (R$) *", lambda: ctk.CTkEntry(frm, placeholder_text="0,00"))
        e_data   = campo("Data de Vencimento *", lambda: ctk.CTkEntry(frm, placeholder_text="DD/MM/AAAA"))
        _aplicar_mascara_data(e_data)

        ctk.CTkLabel(frm, text="Tipo *", text_color=COR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(8, 2))
        cb_tipo = ctk.CTkComboBox(frm, values=["conta","receita","reserva","parcela","outro"],
                                  state="readonly")
        cb_tipo.pack(fill="x")

        e_desc    = campo("Descrição", lambda: ctk.CTkEntry(frm, placeholder_text="Opcional"))
        e_cod_bar = campo("Código de Barras / Linha Digitável",
                          lambda: ctk.CTkEntry(frm, placeholder_text="Cole o código aqui (opcional)"))

        rec_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(frm, text="Recorrente (todo mês)", variable=rec_var,
                        text_color=COR_TEXTO).pack(anchor="w", pady=(8, 0))

        e_dia_rec = campo("Dia de recorrência", lambda: ctk.CTkEntry(frm, placeholder_text="1–31"))

        # Preenche se edição
        if dados:
            e_titulo.insert(0, dados["titulo"])
            e_valor.insert(0, f"{dados['valor']:.2f}".replace(".",","))
            e_data.insert(0, dados["data_vencimento"].strftime("%d/%m/%Y"))
            cb_tipo.set(dados["tipo"])
            e_desc.insert(0, dados.get("descricao",""))
            e_cod_bar.insert(0, dados.get("codigo_barras","") or "")
            rec_var.set(dados.get("recorrente", False))
            if dados.get("dia_recorrencia"):
                e_dia_rec.insert(0, str(dados["dia_recorrencia"]))

        def _salvar():
            titulo = e_titulo.get().strip()
            valor_txt = e_valor.get().strip().replace(",",".")
            data_txt  = e_data.get().strip()
            tipo      = cb_tipo.get()
            if not titulo or not valor_txt or not data_txt:
                messagebox.showwarning("Atenção", "Preencha os campos obrigatórios (*)", parent=d)
                return
            try:
                valor = float(valor_txt)
                dd, mm, aaaa = data_txt.split("/")
                from datetime import date as _date
                venc = _date(int(aaaa), int(mm), int(dd))
            except Exception:
                messagebox.showwarning("Atenção", "Valor ou data inválidos.", parent=d)
                return

            dia_rec_txt = e_dia_rec.get().strip()
            dia_rec = int(dia_rec_txt) if dia_rec_txt.isdigit() else None

            payload = {
                "titulo":          titulo,
                "valor":           valor,
                "data_vencimento": venc,
                "tipo":            tipo,
                "descricao":       e_desc.get().strip() or None,
                "codigo_barras":   e_cod_bar.get().strip() or None,
                "recorrente":      rec_var.get(),
                "dia_recorrencia": dia_rec,
            }

            try:
                db = self.app._obter_db()
                try:
                    if ev_id is None:
                        from app.services.agenda_service import criar_evento
                        criar_evento(db, payload)
                    else:
                        from app.services.agenda_service import atualizar_evento
                        atualizar_evento(db, ev_id, payload)
                finally:
                    db.close()
            except Exception as ex:
                messagebox.showerror("Erro", str(ex), parent=d)
                return
            d.destroy()
            self._construir_calendario()
            self.carregar()

        ctk.CTkButton(d, text="💾 Salvar", fg_color=COR_SUCESSO, hover_color="#1E8449",
                      command=_salvar).pack(pady=14)


# ================================================
# Frame: Agenda de Compromissos
# ================================================

class AgendaCompromissosFrame(ctk.CTkFrame):
    """Agenda pessoal com compromissos, eventos e lembretes."""

    _MESES = ["","Janeiro","Fevereiro","Março","Abril","Maio","Junho",
               "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    _DIAS_SEMANA = ["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"]

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        from datetime import date
        self._hoje    = date.today()
        self._mes_vis = self._hoje.month
        self._ano_vis = self._hoje.year
        self._dia_sel = self._hoje
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._construir_ui()
        self.carregar()

    def _construir_ui(self):
        # Cabeçalho
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", pady=(0,10))
        ctk.CTkLabel(hdr, text="🗓️ Agenda de Compromissos",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=COR_TEXTO).pack(side="left")
        ctk.CTkButton(hdr, text="➕ Novo Compromisso", width=160,
                      fg_color=COR_SUCESSO, hover_color="#1E8449",
                      command=self._dialog_compromisso).pack(side="right", padx=5)

        # Layout: calendário (topo esq) + detalhe do dia (dir)
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew")
        main.grid_columnconfigure(0, weight=0)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        # Painel calendário
        self._frame_cal = ctk.CTkFrame(main, fg_color=COR_CARD, corner_radius=12, width=300)
        self._frame_cal.grid(row=0, column=0, sticky="nsew", padx=(0,10))
        self._frame_cal.grid_propagate(False)
        self._construir_calendario()

        # Painel detalhe dia
        right = ctk.CTkFrame(main, fg_color=COR_CARD, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        self._lbl_dia_sel = ctk.CTkLabel(right, text="",
                                          font=ctk.CTkFont(size=14, weight="bold"),
                                          text_color=COR_TEXTO)
        self._lbl_dia_sel.grid(row=0, column=0, sticky="w", padx=15, pady=(15,5))

        # Lista do dia selecionado
        self._lista_dia = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self._lista_dia.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0,8))

        # Botões
        btn_bar = ctk.CTkFrame(right, fg_color="transparent")
        btn_bar.grid(row=2, column=0, sticky="ew", padx=15, pady=(0,12))
        ctk.CTkButton(btn_bar, text="✏️ Editar", width=90,
                      fg_color=COR_PRIMARIA, command=self._editar_comp).pack(side="left", padx=4)
        ctk.CTkButton(btn_bar, text="✅ Concluir", width=100,
                      fg_color=COR_SUCESSO, hover_color="#1E8449",
                      command=self._concluir_comp).pack(side="left", padx=4)
        ctk.CTkButton(btn_bar, text="🗑️ Excluir", width=90,
                      fg_color=COR_PERIGO, hover_color="#922B21",
                      command=self._excluir_comp).pack(side="left", padx=4)

        self._comp_sel_id = None

    def _construir_calendario(self):
        for w in self._frame_cal.winfo_children():
            w.destroy()

        nav = ctk.CTkFrame(self._frame_cal, fg_color="transparent")
        nav.pack(fill="x", padx=10, pady=(12,4))
        ctk.CTkButton(nav, text="◀", width=30, fg_color=COR_SECUNDARIA,
                      command=self._mes_anterior).pack(side="left")
        self._lbl_mes_cal = ctk.CTkLabel(nav, text="",
                                          font=ctk.CTkFont(size=13, weight="bold"),
                                          text_color=COR_TEXTO)
        self._lbl_mes_cal.pack(side="left", expand=True)
        ctk.CTkButton(nav, text="▶", width=30, fg_color=COR_SECUNDARIA,
                      command=self._proximo_mes).pack(side="right")
        self._lbl_mes_cal.configure(
            text=f"{self._MESES[self._mes_vis]} {self._ano_vis}")

        grid = ctk.CTkFrame(self._frame_cal, fg_color="transparent")
        grid.pack(padx=8, pady=(4,0))
        for i, d in enumerate(self._DIAS_SEMANA):
            ctk.CTkLabel(grid, text=d, width=36,
                         font=ctk.CTkFont(size=10),
                         text_color=COR_TEXTO_SUAVE).grid(row=0, column=i, padx=1)

        import calendar
        try:
            from app.services.agenda_service import listar_compromissos
            db = self.app._obter_db()
            try:
                comps = listar_compromissos(db, self._mes_vis, self._ano_vis)
            finally:
                db.close()
            dias_com_comp = {c.data.day for c in comps}
        except Exception:
            dias_com_comp = set()

        primeiro_dia, n_dias = calendar.monthrange(self._ano_vis, self._mes_vis)
        row = 1; col = primeiro_dia
        from datetime import date as _date
        for day in range(1, n_dias + 1):
            dia_date = _date(self._ano_vis, self._mes_vis, day)
            eh_hoje  = dia_date == self._hoje
            eh_sel   = dia_date == self._dia_sel
            tem_comp = day in dias_com_comp

            if eh_sel:
                fg = COR_PRIMARIA
            elif eh_hoje:
                fg = COR_SECUNDARIA
            elif tem_comp:
                fg = "#8E44AD"
            else:
                fg = "transparent"

            btn = ctk.CTkButton(
                grid, text=str(day), width=34, height=28,
                fg_color=fg, hover_color=COR_PRIMARIA,
                text_color=COR_TEXTO,
                font=ctk.CTkFont(size=11, weight="bold" if eh_hoje or eh_sel else "normal"),
                corner_radius=6,
                command=lambda d=dia_date: self._selecionar_dia(d),
            )
            btn.grid(row=row, column=col, padx=1, pady=2)
            col += 1
            if col > 6:
                col = 0; row += 1

        # Legenda
        leg = ctk.CTkFrame(self._frame_cal, fg_color="transparent")
        leg.pack(pady=(8,12), padx=10, fill="x")
        for txt, cor in [("Compromisso","#8E44AD"),("Hoje",COR_SECUNDARIA)]:
            f = ctk.CTkFrame(leg, fg_color="transparent")
            f.pack(side="left", padx=6)
            ctk.CTkLabel(f, text="■", text_color=cor, font=ctk.CTkFont(size=12)).pack(side="left")
            ctk.CTkLabel(f, text=txt, text_color=COR_TEXTO_SUAVE, font=ctk.CTkFont(size=10)).pack(side="left")

    def _mes_anterior(self):
        if self._mes_vis == 1:
            self._mes_vis = 12; self._ano_vis -= 1
        else:
            self._mes_vis -= 1
        self._construir_calendario()
        self.carregar()

    def _proximo_mes(self):
        if self._mes_vis == 12:
            self._mes_vis = 1; self._ano_vis += 1
        else:
            self._mes_vis += 1
        self._construir_calendario()
        self.carregar()

    def _selecionar_dia(self, d):
        self._dia_sel = d
        self._construir_calendario()
        self.carregar()

    def carregar(self):
        self._comp_sel_id = None
        nome_dia = self._DIAS_SEMANA[self._dia_sel.weekday()]
        self._lbl_dia_sel.configure(
            text=f"📌 {nome_dia}, {self._dia_sel.strftime('%d/%m/%Y')}")

        for w in self._lista_dia.winfo_children():
            w.destroy()

        try:
            from app.services.agenda_service import listar_compromissos_dia
            db = self.app._obter_db()
            try:
                comps = listar_compromissos_dia(db, self._dia_sel)
            finally:
                db.close()
        except Exception as e:
            messagebox.showerror("Erro", str(e))
            return

        if not comps:
            ctk.CTkLabel(self._lista_dia, text="Nenhum compromisso neste dia.",
                         text_color=COR_TEXTO_SUAVE).pack(pady=20)
            return

        for comp in comps:
            card = ctk.CTkFrame(self._lista_dia, fg_color=COR_CARD, corner_radius=8)
            card.pack(fill="x", pady=4)
            card.bind("<Button-1>", lambda e, cid=comp.id: self._selecionar_comp(cid))

            hora_txt = ""
            if comp.hora_inicio:
                hora_txt = f"  {comp.hora_inicio}"
                if comp.hora_fim:
                    hora_txt += f" – {comp.hora_fim}"

            cor_dot = comp.cor or "#3498db"
            ctk.CTkLabel(card, text="●", text_color=cor_dot,
                         font=ctk.CTkFont(size=16)).pack(side="left", padx=(10,4), pady=8)
            info_f = ctk.CTkFrame(card, fg_color="transparent")
            info_f.pack(side="left", fill="x", expand=True, pady=6)
            titulo_txt = comp.titulo + (" ✅" if comp.concluido else "")
            ctk.CTkLabel(info_f, text=titulo_txt,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=COR_TEXTO_SUAVE if comp.concluido else COR_TEXTO,
                         anchor="w").pack(fill="x")
            sub = hora_txt
            if comp.local:
                sub += f"  📍 {comp.local}"
            if sub:
                ctk.CTkLabel(info_f, text=sub,
                             font=ctk.CTkFont(size=10),
                             text_color=COR_TEXTO_SUAVE, anchor="w").pack(fill="x")

    def _selecionar_comp(self, comp_id: int):
        self._comp_sel_id = comp_id

    def _editar_comp(self):
        cid = self._comp_sel_id
        if not cid:
            messagebox.showwarning("Atenção", "Clique em um compromisso para selecioná-lo.")
            return
        try:
            from app.models import Compromisso as CompM
            db = self.app._obter_db()
            try:
                comp = db.query(CompM).get(cid)
                if not comp:
                    return
                dados = {k: getattr(comp, k) for k in
                         ["titulo","descricao","local","data","hora_inicio","hora_fim","cor","lembrete_min"]}
            finally:
                db.close()
        except Exception as e:
            messagebox.showerror("Erro", str(e))
            return
        self._dialog_compromisso(cid, dados)

    def _concluir_comp(self):
        cid = self._comp_sel_id
        if not cid:
            messagebox.showwarning("Atenção", "Clique em um compromisso para selecioná-lo.")
            return
        try:
            from app.models import Compromisso as CompM
            db = self.app._obter_db()
            try:
                comp = db.query(CompM).get(cid)
                if comp:
                    comp.concluido = not comp.concluido
                    db.commit()
            finally:
                db.close()
        except Exception as e:
            messagebox.showerror("Erro", str(e))
            return
        self._construir_calendario()
        self.carregar()

    def _excluir_comp(self):
        cid = self._comp_sel_id
        if not cid:
            messagebox.showwarning("Atenção", "Clique em um compromisso para selecioná-lo.")
            return
        if not messagebox.askyesno("Confirmar", "Excluir este compromisso?"):
            return
        try:
            from app.services.agenda_service import excluir_compromisso
            db = self.app._obter_db()
            try:
                excluir_compromisso(db, cid)
            finally:
                db.close()
        except Exception as e:
            messagebox.showerror("Erro", str(e))
            return
        self._comp_sel_id = None
        self._construir_calendario()
        self.carregar()

    def _dialog_compromisso(self, comp_id=None, dados=None):
        d = ctk.CTkToplevel(self)
        d.title("Novo Compromisso" if comp_id is None else "Editar Compromisso")
        d.geometry("420x520")
        d.resizable(False, False)
        d.grab_set()

        ctk.CTkLabel(d, text="🗓️ Compromisso",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=COR_TEXTO).pack(pady=(18,8))

        frm = ctk.CTkScrollableFrame(d, fg_color="transparent")
        frm.pack(fill="both", expand=True, padx=20)

        def campo(lbl, ph):
            ctk.CTkLabel(frm, text=lbl, text_color=COR_TEXTO_SUAVE,
                         font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(8,2))
            e = ctk.CTkEntry(frm, placeholder_text=ph)
            e.pack(fill="x")
            return e

        e_titulo    = campo("Título *", "Ex: Reunião com cliente")
        e_data      = campo("Data *", "DD/MM/AAAA")
        _aplicar_mascara_data(e_data)
        e_hora_ini  = campo("Hora início", "HH:MM")
        e_hora_fim  = campo("Hora fim", "HH:MM")
        e_local     = campo("Local", "Ex: Sala de reuniões")
        e_desc      = campo("Descrição", "Opcional")

        ctk.CTkLabel(frm, text="Cor", text_color=COR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(8,2))
        cores_disponiveis = ["#3498db","#8E44AD","#27AE60","#E74C3C","#F39C12","#E67E22","#1ABC9C"]
        cb_cor = ctk.CTkComboBox(frm, values=cores_disponiveis, state="readonly")
        cb_cor.pack(fill="x")

        if dados:
            e_titulo.insert(0, dados.get("titulo",""))
            dt = dados.get("data")
            if dt:
                e_data.insert(0, dt.strftime("%d/%m/%Y"))
            e_hora_ini.insert(0, dados.get("hora_inicio","") or "")
            e_hora_fim.insert(0, dados.get("hora_fim","") or "")
            e_local.insert(0, dados.get("local","") or "")
            e_desc.insert(0, dados.get("descricao","") or "")
            cb_cor.set(dados.get("cor","#3498db"))

        def _salvar():
            titulo   = e_titulo.get().strip()
            data_txt = e_data.get().strip()
            if not titulo or not data_txt:
                messagebox.showwarning("Atenção", "Título e data são obrigatórios.", parent=d)
                return
            try:
                dd, mm, aaaa = data_txt.split("/")
                from datetime import date as _date
                dt = _date(int(aaaa), int(mm), int(dd))
            except Exception:
                messagebox.showwarning("Atenção", "Data inválida.", parent=d)
                return

            payload = {
                "titulo":      titulo,
                "data":        dt,
                "hora_inicio": e_hora_ini.get().strip() or None,
                "hora_fim":    e_hora_fim.get().strip() or None,
                "local":       e_local.get().strip() or None,
                "descricao":   e_desc.get().strip() or None,
                "cor":         cb_cor.get(),
            }
            try:
                db = self.app._obter_db()
                try:
                    if comp_id is None:
                        from app.services.agenda_service import criar_compromisso
                        criar_compromisso(db, payload)
                    else:
                        from app.services.agenda_service import atualizar_compromisso
                        atualizar_compromisso(db, comp_id, payload)
                finally:
                    db.close()
            except Exception as ex:
                messagebox.showerror("Erro", str(ex), parent=d)
                return
            d.destroy()
            self._construir_calendario()
            self.carregar()

        ctk.CTkButton(d, text="💾 Salvar", fg_color=COR_SUCESSO, hover_color="#1E8449",
                      command=_salvar).pack(pady=14)


# ================================================
# Frame: Planner Semanal
# ================================================

class PlannerFrame(ctk.CTkFrame):
    """Planner semanal com visão de tarefas por dia, área e prioridade."""

    _DIAS_PT  = ["Segunda","Terça","Quarta","Quinta","Sexta","Sábado","Domingo"]
    _FAIXAS_HORARIO = [
        ("manha", "Manhã", "☀", "09:00"),
        ("tarde", "Tarde", "◐", "14:00"),
        ("noite", "Noite", "☾", "19:00"),
        ("flexivel", "Sem horário", "○", ""),
    ]
    _COR_PRIORIDADE = {"alta": "#E74C3C", "media": "#F39C12", "baixa": "#27AE60"}
    _COR_STATUS     = {"a_fazer": "#95A5A6", "em_progresso": "#3498db", "concluido": "#27AE60"}
    _ICONE_AREA     = {"financeiro":"💰","pessoal":"👤","trabalho":"💼","saude":"🏥","outro":"📌"}

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        from datetime import date, timedelta
        hoje = date.today()
        # Início da semana (segunda-feira)
        self._semana_inicio = hoje - timedelta(days=hoje.weekday())
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._construir_ui()
        self.carregar()

    def _construir_ui(self):
        # Cabeçalho
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", pady=(0,10))
        ctk.CTkLabel(hdr, text="📋 Planner Semanal",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=COR_TEXTO).pack(side="left")

        nav_f = ctk.CTkFrame(hdr, fg_color="transparent")
        nav_f.pack(side="left", padx=20)
        ctk.CTkButton(nav_f, text="◀ Semana", width=90, fg_color=COR_SECUNDARIA,
                      command=self._semana_anterior).pack(side="left", padx=2)
        self._lbl_semana = ctk.CTkLabel(nav_f, text="",
                                         font=ctk.CTkFont(size=12, weight="bold"),
                                         text_color=COR_TEXTO)
        self._lbl_semana.pack(side="left", padx=8)
        ctk.CTkButton(nav_f, text="Semana ▶", width=90, fg_color=COR_SECUNDARIA,
                      command=self._proxima_semana).pack(side="left", padx=2)
        ctk.CTkButton(nav_f, text="Hoje", width=60, fg_color=COR_PRIMARIA,
                      command=self._ir_para_hoje).pack(side="left", padx=4)

        ctk.CTkButton(hdr, text="➕ Nova Tarefa", width=120,
                      fg_color=COR_SUCESSO, hover_color="#1E8449",
                      command=self._dialog_tarefa).pack(side="right", padx=5)

        # Barra de filtro
        filtro_f = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=8)
        filtro_f.grid(row=1, column=0, sticky="ew", pady=(0,8))
        ctk.CTkLabel(filtro_f, text="Área:", text_color=COR_TEXTO_SUAVE).pack(side="left", padx=(12,6))
        self._filtro_area = ctk.StringVar(value="todas")
        for txt, val in [("Todas","todas"),("Financeiro","financeiro"),
                         ("Pessoal","pessoal"),("Trabalho","trabalho"),
                         ("Saúde","saude")]:
            ctk.CTkRadioButton(filtro_f, text=txt, variable=self._filtro_area,
                               value=val, command=self.carregar,
                               text_color=COR_TEXTO_SUAVE).pack(side="left", padx=6)

        ctk.CTkLabel(filtro_f, text="Status:", text_color=COR_TEXTO_SUAVE).pack(side="left", padx=(20,6))
        self._filtro_status = ctk.StringVar(value="todos")
        for txt, val in [("Todos","todos"),("A Fazer","a_fazer"),
                         ("Em Progresso","em_progresso"),("Concluído","concluido")]:
            ctk.CTkRadioButton(filtro_f, text=txt, variable=self._filtro_status,
                               value=val, command=self.carregar,
                               text_color=COR_TEXTO_SUAVE).pack(side="left", padx=6)

        # Grade semanal: 7 colunas
        self._grade = ctk.CTkScrollableFrame(self, fg_color="transparent", orientation="vertical")
        self._grade.grid(row=2, column=0, sticky="nsew", pady=(0,8))
        self.grid_rowconfigure(2, weight=1)
        for i in range(7):
            self._grade.grid_columnconfigure(i, weight=1, uniform="dias")

        # Rodapé métricas
        self._lbl_metrics = ctk.CTkLabel(self, text="",
                                          font=ctk.CTkFont(size=11),
                                          text_color=COR_TEXTO_SUAVE)
        self._lbl_metrics.grid(row=3, column=0, sticky="w", pady=(0,4))

        self._tarefa_sel_id = None

    def _semana_anterior(self):
        from datetime import timedelta
        self._semana_inicio -= timedelta(weeks=1)
        self.carregar()

    def _proxima_semana(self):
        from datetime import timedelta
        self._semana_inicio += timedelta(weeks=1)
        self.carregar()

    def _ir_para_hoje(self):
        from datetime import date, timedelta
        hoje = date.today()
        self._semana_inicio = hoje - timedelta(days=hoje.weekday())
        self.carregar()

    def _hora_para_minutos(self, hora_txt: Optional[str]) -> Optional[int]:
        if not hora_txt:
            return None
        try:
            hh, mm = str(hora_txt).split(":", 1)
            hora = int(hh)
            minuto = int(mm)
        except Exception:
            return None
        if 0 <= hora <= 23 and 0 <= minuto <= 59:
            return hora * 60 + minuto
        return None

    def _faixa_da_tarefa(self, tarefa) -> str:
        inicio_min = self._hora_para_minutos(getattr(tarefa, "hora_inicio", None))
        if inicio_min is None:
            return "flexivel"
        if inicio_min < 12 * 60:
            return "manha"
        if inicio_min < 18 * 60:
            return "tarde"
        return "noite"

    def _renderizar_faixa_dia(self, parent, dia, chave_faixa: str, titulo: str, icone: str, hora_padrao: str, tarefas):
        sec = ctk.CTkFrame(parent, fg_color="#162033", corner_radius=10, border_width=1, border_color=COR_BORDA)
        sec.pack(fill="x", pady=(0, 8))

        topo = ctk.CTkFrame(sec, fg_color="transparent")
        topo.pack(fill="x", padx=8, pady=(7, 4))
        ctk.CTkLabel(
            topo,
            text=f"{icone} {titulo}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COR_TEXTO,
        ).pack(side="left")
        ctk.CTkLabel(
            topo,
            text=f"{len(tarefas)} item(ns)",
            font=ctk.CTkFont(size=9),
            text_color=COR_TEXTO_SUAVE,
        ).pack(side="right")

        corpo = ctk.CTkFrame(sec, fg_color="transparent")
        corpo.pack(fill="x", padx=6, pady=(0, 6))

        if tarefas:
            for tarefa in tarefas:
                self._card_tarefa(corpo, tarefa)
        else:
            ctk.CTkLabel(
                corpo,
                text="Sem tarefas nesta faixa",
                font=ctk.CTkFont(size=10),
                text_color=COR_TEXTO_SUAVE,
            ).pack(anchor="w", padx=6, pady=(2, 6))

        ctk.CTkButton(
            sec,
            text="+ adicionar",
            height=28,
            fg_color="transparent",
            border_width=1,
            border_color=COR_BORDA,
            text_color=COR_DESTAQUE,
            hover_color="#1E293B",
            command=lambda d=dia, hp=hora_padrao if chave_faixa != "flexivel" else None: self._dialog_tarefa(data_pre=d, hora_pre=hp),
        ).pack(fill="x", padx=8, pady=(0, 8))

    def carregar(self):
        from datetime import timedelta
        semana_fim = self._semana_inicio + timedelta(days=6)
        self._lbl_semana.configure(
            text=f"{self._semana_inicio.strftime('%d/%m')} – {semana_fim.strftime('%d/%m/%Y')}")

        try:
            from app.services.agenda_service import listar_tarefas, resumo_semana
            db = self.app._obter_db()
            try:
                tarefas = listar_tarefas(db, semana_inicio=self._semana_inicio)
                res = resumo_semana(db, self._semana_inicio)
            finally:
                db.close()
        except Exception as e:
            messagebox.showerror("Erro", str(e))
            return

        # Aplica filtros
        area_f   = self._filtro_area.get()
        status_f = self._filtro_status.get()
        if area_f != "todas":
            tarefas = [t for t in tarefas if (t.area.value if hasattr(t.area,'value') else str(t.area)) == area_f]
        if status_f != "todos":
            tarefas = [t for t in tarefas if (t.status.value if hasattr(t.status,'value') else str(t.status)) == status_f]

        # Reorganiza por dia
        from datetime import timedelta
        por_dia = {}
        for i in range(7):
            dia = self._semana_inicio + timedelta(days=i)
            por_dia[dia] = []
        for t in tarefas:
            if t.data in por_dia:
                por_dia[t.data].append(t)
        for dia in por_dia:
            por_dia[dia].sort(key=lambda tarefa: (str(getattr(tarefa, "hora_inicio", "") or "99:99"), str(getattr(tarefa, "prioridade", "z"))))

        # Reconstrói grade
        for w in self._grade.winfo_children():
            w.destroy()

        from datetime import date as _date
        hoje = _date.today()
        for col_i, (dia, lista) in enumerate(sorted(por_dia.items())):
            eh_hoje = dia == hoje
            # Cabeçalho da coluna
            hdr_col = ctk.CTkFrame(
                self._grade,
                fg_color=COR_PRIMARIA if eh_hoje else COR_CARD,
                corner_radius=8)
            hdr_col.grid(row=0, column=col_i, padx=4, pady=(0,4), sticky="ew")

            ctk.CTkLabel(hdr_col,
                         text=self._DIAS_PT[col_i],
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=COR_TEXTO).pack()
            ctk.CTkLabel(hdr_col,
                         text=dia.strftime("%d/%m"),
                         font=ctk.CTkFont(size=11),
                         text_color=COR_TEXTO).pack()
            ctk.CTkLabel(hdr_col,
                         text=f"{len(lista)} tarefa(s)",
                         font=ctk.CTkFont(size=9),
                         text_color=COR_TEXTO_SUAVE).pack(pady=(0,4))

            # Coluna de cards
            col_frame = ctk.CTkFrame(self._grade, fg_color="transparent")
            col_frame.grid(row=1, column=col_i, padx=4, sticky="nsew")

            tarefas_por_faixa = {chave: [] for chave, _, _, _ in self._FAIXAS_HORARIO}
            for tarefa in lista:
                tarefas_por_faixa[self._faixa_da_tarefa(tarefa)].append(tarefa)

            for chave, titulo, icone, hora_padrao in self._FAIXAS_HORARIO:
                self._renderizar_faixa_dia(
                    col_frame,
                    dia,
                    chave,
                    titulo,
                    icone,
                    hora_padrao,
                    tarefas_por_faixa.get(chave, []),
                )

        # Métricas
        self._lbl_metrics.configure(
            text=f"Total: {res['total']}  |  ✅ Concluídas: {res['concluidas']}  |  ⏳ Pendentes: {res['pendentes']}")

    def _card_tarefa(self, parent, tarefa):
        status_v   = tarefa.status.value   if hasattr(tarefa.status,   'value') else str(tarefa.status)
        prio_v     = tarefa.prioridade.value if hasattr(tarefa.prioridade,'value') else str(tarefa.prioridade)
        area_v     = tarefa.area.value      if hasattr(tarefa.area,     'value') else str(tarefa.area)
        cor_prio   = self._COR_PRIORIDADE.get(prio_v, "#95A5A6")
        cor_status = self._COR_STATUS.get(status_v, "#95A5A6")
        icone_area = self._ICONE_AREA.get(area_v, "📌")

        card = ctk.CTkFrame(parent, fg_color=COR_CARD, corner_radius=6, border_width=2,
                            border_color=cor_prio)
        card.pack(fill="x", pady=2)
        card.bind("<Button-1>", lambda e, tid=tarefa.id: setattr(self, "_tarefa_sel_id", tid))

        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=6, pady=(5,2))
        ctk.CTkLabel(top_row, text=icone_area, width=18,
                     font=ctk.CTkFont(size=12)).pack(side="left")
        titulo_txt = tarefa.titulo[:22] + "…" if len(tarefa.titulo) > 22 else tarefa.titulo
        if status_v == "concluido":
            titulo_txt = "✅ " + titulo_txt
        ctk.CTkLabel(top_row, text=titulo_txt,
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=COR_TEXTO_SUAVE if status_v == "concluido" else COR_TEXTO,
                     anchor="w").pack(side="left", fill="x", expand=True)

        horario_txt = ""
        if getattr(tarefa, "hora_inicio", None) and getattr(tarefa, "hora_fim", None):
            horario_txt = f"⏰ {tarefa.hora_inicio} - {tarefa.hora_fim}"
        elif getattr(tarefa, "hora_inicio", None) and getattr(tarefa, "duracao_min", None):
            horario_txt = f"⏰ {tarefa.hora_inicio}  •  {int(tarefa.duracao_min)} min"
        elif getattr(tarefa, "hora_inicio", None):
            horario_txt = f"⏰ Início {tarefa.hora_inicio}"

        if horario_txt:
            ctk.CTkLabel(
                card,
                text=horario_txt,
                text_color=COR_DESTAQUE,
                font=ctk.CTkFont(size=9),
                anchor="w",
            ).pack(fill="x", padx=8, pady=(0, 2))

        bot_row = ctk.CTkFrame(card, fg_color="transparent")
        bot_row.pack(fill="x", padx=6, pady=(0,5))
        ctk.CTkLabel(bot_row, text=f"● {prio_v.capitalize()}",
                     text_color=cor_prio, font=ctk.CTkFont(size=9)).pack(side="left")
        ctk.CTkLabel(bot_row, text=f"  {status_v.replace('_',' ').capitalize()}",
                     text_color=cor_status, font=ctk.CTkFont(size=9)).pack(side="left")

        # Botões rápidos no hover
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=4, pady=(0,4))
        ctk.CTkButton(btn_row, text="✅", width=28, height=22,
                      fg_color="transparent", text_color=COR_SUCESSO,
                      command=lambda tid=tarefa.id: self._concluir_tarefa(tid)).pack(side="left")
        ctk.CTkButton(btn_row, text="✏️", width=28, height=22,
                      fg_color="transparent", text_color=COR_PRIMARIA,
                      command=lambda tid=tarefa.id: self._editar_tarefa(tid)).pack(side="left")
        ctk.CTkButton(btn_row, text="🗑️", width=28, height=22,
                      fg_color="transparent", text_color=COR_PERIGO,
                      command=lambda tid=tarefa.id: self._excluir_tarefa(tid)).pack(side="left")

    def _concluir_tarefa(self, tarefa_id: int):
        try:
            from app.services.agenda_service import concluir_tarefa
            db = self.app._obter_db()
            try:
                concluir_tarefa(db, tarefa_id)
            finally:
                db.close()
        except Exception as e:
            messagebox.showerror("Erro", str(e))
            return
        self.carregar()

    def _excluir_tarefa(self, tarefa_id: int):
        if not messagebox.askyesno("Confirmar", "Excluir esta tarefa?"):
            return
        try:
            from app.services.agenda_service import excluir_tarefa
            db = self.app._obter_db()
            try:
                excluir_tarefa(db, tarefa_id)
            finally:
                db.close()
        except Exception as e:
            messagebox.showerror("Erro", str(e))
            return
        self.carregar()

    def _editar_tarefa(self, tarefa_id: int):
        try:
            from app.models import TarefaPlanner as TpM
            db = self.app._obter_db()
            try:
                t = db.query(TpM).get(tarefa_id)
                if not t:
                    return
                dados = {
                    "titulo":      t.titulo,
                    "descricao":   t.descricao or "",
                    "data":        t.data,
                    "hora_inicio": t.hora_inicio or "",
                    "hora_fim":    t.hora_fim or "",
                    "duracao_min": t.duracao_min,
                    "prioridade":  t.prioridade.value if hasattr(t.prioridade,'value') else str(t.prioridade),
                    "status":      t.status.value     if hasattr(t.status,'value')     else str(t.status),
                    "area":        t.area.value        if hasattr(t.area,'value')       else str(t.area),
                }
            finally:
                db.close()
        except Exception as e:
            messagebox.showerror("Erro", str(e))
            return
        self._dialog_tarefa(tarefa_id=tarefa_id, dados=dados)

    def _dialog_tarefa(self, tarefa_id=None, dados=None, data_pre=None, hora_pre=None):
        """
        Cria/edita tarefa com suporte a 3 modos:
          – Data única
          – Múltiplos dias da semana de uma só vez
          – Recorrência inteligente (Diária / Dias úteis / Semanal / Quinzenal / Mensal)
        """
        edicao = tarefa_id is not None
        d = ctk.CTkToplevel(self)
        d.title("Editar Tarefa" if edicao else "Nova Tarefa")
        d.geometry("620x640")
        d.resizable(False, True)
        d.grab_set()
        d.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            d,
            text="✏️  Editar Tarefa" if edicao else "📋  Nova Tarefa",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COR_TEXTO,
        ).grid(row=0, column=0, padx=20, pady=(16, 8), sticky="w")

        # ── Campos base ──────────────────────────────────────────────────
        frm = ctk.CTkFrame(d, fg_color=COR_CARD, corner_radius=12)
        frm.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        frm.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frm, text="Título *", text_color=COR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=11)).pack(anchor="w", padx=14, pady=(10, 2))
        e_titulo = ctk.CTkEntry(frm, placeholder_text="Ex: Pagar fatura do cartão")
        e_titulo.pack(fill="x", padx=14, pady=(0, 4))

        ctk.CTkLabel(frm, text="Descrição (opcional)", text_color=COR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=11)).pack(anchor="w", padx=14, pady=(4, 2))
        e_desc = ctk.CTkEntry(frm, placeholder_text="Detalhes adicionais")
        e_desc.pack(fill="x", padx=14, pady=(0, 8))

        row_cb = ctk.CTkFrame(frm, fg_color="transparent")
        row_cb.pack(fill="x", padx=14, pady=(0, 12))
        for _ci in range(3):
            row_cb.grid_columnconfigure(_ci, weight=1)

        def _mkcombo(lbl, vals, col):
            ctk.CTkLabel(row_cb, text=lbl, text_color=COR_TEXTO_SUAVE,
                         font=ctk.CTkFont(size=11)).grid(row=0, column=col, sticky="w")
            cb = ctk.CTkComboBox(row_cb, values=vals, state="readonly", width=150)
            cb.grid(row=1, column=col, padx=(0, 8) if col < 2 else (0, 0), sticky="ew")
            return cb

        cb_prio   = _mkcombo("Prioridade", ["alta", "media", "baixa"],   0)
        cb_area   = _mkcombo("Área",       ["financeiro","pessoal","trabalho","saude","outro"], 1)
        cb_status = _mkcombo("Status",     ["a_fazer","em_progresso","concluido"], 2)
        cb_prio.set("media");  cb_area.set("pessoal");  cb_status.set("a_fazer")

        agenda_row = ctk.CTkFrame(frm, fg_color="transparent")
        agenda_row.pack(fill="x", padx=14, pady=(0, 12))
        for _ci in range(3):
            agenda_row.grid_columnconfigure(_ci, weight=1)

        ctk.CTkLabel(agenda_row, text="Hora início", text_color=COR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(agenda_row, text="Hora fim", text_color=COR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(agenda_row, text="Duração (min)", text_color=COR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=2, sticky="w")

        e_hora_ini = ctk.CTkEntry(agenda_row, placeholder_text="08:30", width=120)
        e_hora_ini.grid(row=1, column=0, padx=(0, 8), sticky="ew")
        _aplicar_mascara_hora(e_hora_ini)

        e_hora_fim = ctk.CTkEntry(agenda_row, placeholder_text="10:00", width=120)
        e_hora_fim.grid(row=1, column=1, padx=(0, 8), sticky="ew")
        _aplicar_mascara_hora(e_hora_fim)

        e_duracao = ctk.CTkEntry(agenda_row, placeholder_text="90", width=120)
        e_duracao.grid(row=1, column=2, sticky="ew")

        ctk.CTkLabel(
            frm,
            text="Use início + fim ou início + duração. Se informar fim, ele prevalece sobre a duração.",
            text_color=COR_DESTAQUE,
            font=ctk.CTkFont(size=10),
        ).pack(anchor="w", padx=14, pady=(0, 8))

        # ── Seção "Quando?" ───────────────────────────────────────────────
        sec_q = ctk.CTkFrame(d, fg_color=COR_CARD, corner_radius=12)
        sec_q.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 8))
        sec_q.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(sec_q, text="🗓️  Quando?",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=COR_TEXTO).pack(anchor="w", padx=14, pady=(10, 6))

        var_modo  = ctk.StringVar(value="unica")
        modos_row = ctk.CTkFrame(sec_q, fg_color="transparent")
        modos_row.pack(fill="x", padx=14)
        for _txt, _val in [("Data única","unica"),
                            ("Dias da semana","dias"),
                            ("Recorrente","recorrente")]:
            ctk.CTkRadioButton(
                modos_row, text=_txt, variable=var_modo, value=_val,
                text_color=COR_TEXTO,
                state="normal" if (not edicao or _val == "unica") else "disabled",
                command=lambda: _atualizar_modo(),
            ).pack(side="left", padx=(0, 16))

        cont_modo = ctk.CTkFrame(sec_q, fg_color="transparent")
        cont_modo.pack(fill="x", padx=14, pady=(8, 14))

        # Preview + bottom bar (grid rows reserved now)
        lbl_prev = ctk.CTkLabel(d, text="", font=ctk.CTkFont(size=11), text_color=COR_PRIMARIA)
        lbl_prev.grid(row=3, column=0, sticky="w", padx=24, pady=(2, 4))

        barra = ctk.CTkFrame(d, fg_color="transparent")
        barra.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 16))
        barra.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(barra, text="💾  Salvar", fg_color=COR_SUCESSO, hover_color="#1E8449",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=lambda: _salvar()).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(barra, text="Cancelar", fg_color="transparent", border_width=1,
                      command=d.destroy).grid(row=0, column=0, sticky="e")

        # ── State dict (evita nonlocal rebinding) ────────────────────────
        S = {
            "e_data_unica":   None,
            "dias_vars":      {},    # weekday → (BoolVar, date)
            "e_rec_inicio":   None,
            "e_rec_fim":      None,
            "cb_freq":        None,
            "dias_rec_vars":  {},    # weekday → BoolVar
            "frame_dias_rec": None,
        }
        _DIAS_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

        # ── Builders ─────────────────────────────────────────────────────

        def _build_unica():
            for w in cont_modo.winfo_children():
                w.destroy()
            ctk.CTkLabel(cont_modo, text="Data:", text_color=COR_TEXTO_SUAVE,
                         font=ctk.CTkFont(size=11)).pack(anchor="w")
            e = ctk.CTkEntry(cont_modo, placeholder_text="DD/MM/AAAA", width=160)
            e.pack(anchor="w", pady=(2, 0))
            _aplicar_mascara_data(e)
            if dados and dados.get("data"):
                e.insert(0, dados["data"].strftime("%d/%m/%Y"))
            elif data_pre:
                e.insert(0, data_pre.strftime("%d/%m/%Y"))
            S["e_data_unica"] = e

        def _build_dias():
            from datetime import timedelta as _td
            for w in cont_modo.winfo_children():
                w.destroy()
            S["dias_vars"] = {}
            ctk.CTkLabel(
                cont_modo,
                text=f"Semana de {self._semana_inicio.strftime('%d/%m')}  —  selecione os dias:",
                text_color=COR_TEXTO_SUAVE, font=ctk.CTkFont(size=11),
            ).pack(anchor="w", pady=(0, 6))
            chk_row = ctk.CTkFrame(cont_modo, fg_color="transparent")
            chk_row.pack(anchor="w")
            for _i, _nd in enumerate(_DIAS_PT):
                _dia = self._semana_inicio + _td(days=_i)
                _pre = data_pre is not None and data_pre.weekday() == _i
                _v   = ctk.BooleanVar(value=_pre)
                S["dias_vars"][_i] = (_v, _dia)
                ctk.CTkCheckBox(
                    chk_row,
                    text=f"{_nd}\n{_dia.strftime('%d/%m')}",
                    variable=_v, text_color=COR_TEXTO,
                    font=ctk.CTkFont(size=10),
                ).pack(side="left", padx=5)

        def _toggle_dias_rec():
            fr = S.get("frame_dias_rec")
            cb = S.get("cb_freq")
            if fr is None or cb is None:
                return
            if cb.get() in ("Semanal", "Quinzenal"):
                fr.pack(anchor="w", pady=(8, 0))
            else:
                fr.pack_forget()

        def _build_recorrente():
            from datetime import date as _dt
            for w in cont_modo.winfo_children():
                w.destroy()

            r1 = ctk.CTkFrame(cont_modo, fg_color="transparent")
            r1.pack(fill="x")

            ctk.CTkLabel(r1, text="Frequência:", text_color=COR_TEXTO_SUAVE,
                         font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w", padx=(0, 6))
            cb_f = ctk.CTkComboBox(
                r1,
                values=["Diária", "Dias úteis", "Semanal", "Quinzenal", "Mensal"],
                state="readonly", width=140,
                command=lambda _: _toggle_dias_rec(),
            )
            cb_f.set("Semanal")
            cb_f.grid(row=0, column=1, padx=(0, 18))
            S["cb_freq"] = cb_f

            ctk.CTkLabel(r1, text="De:", text_color=COR_TEXTO_SUAVE,
                         font=ctk.CTkFont(size=11)).grid(row=0, column=2, sticky="w", padx=(0, 4))
            e_ini = ctk.CTkEntry(r1, placeholder_text="DD/MM/AAAA", width=110)
            e_ini.grid(row=0, column=3, padx=(0, 12))
            _aplicar_mascara_data(e_ini)

            ctk.CTkLabel(r1, text="Até:", text_color=COR_TEXTO_SUAVE,
                         font=ctk.CTkFont(size=11)).grid(row=0, column=4, sticky="w", padx=(0, 4))
            e_fim = ctk.CTkEntry(r1, placeholder_text="DD/MM/AAAA", width=110)
            e_fim.grid(row=0, column=5)
            _aplicar_mascara_data(e_fim)
            S["e_rec_inicio"] = e_ini
            S["e_rec_fim"]    = e_fim

            ref = data_pre or _dt.today()
            e_ini.insert(0, ref.strftime("%d/%m/%Y"))

            fr_dias = ctk.CTkFrame(cont_modo, fg_color="transparent")
            S["frame_dias_rec"] = fr_dias
            S["dias_rec_vars"]  = {}
            ctk.CTkLabel(fr_dias, text="Nos dias:", text_color=COR_TEXTO_SUAVE,
                         font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 8))
            for _i2, _nd2 in enumerate(_DIAS_PT):
                _v2 = ctk.BooleanVar(value=(_i2 < 5))
                S["dias_rec_vars"][_i2] = _v2
                ctk.CTkCheckBox(
                    fr_dias, text=_nd2, variable=_v2,
                    text_color=COR_TEXTO, font=ctk.CTkFont(size=10), width=62,
                ).pack(side="left", padx=2)

            _toggle_dias_rec()

        # ── Logic ────────────────────────────────────────────────────────

        def _calcular_datas():
            from datetime import date as _dt, timedelta as _td
            modo = var_modo.get()

            if modo == "unica":
                e = S["e_data_unica"]
                if e is None:
                    return [_dt.today()]
                txt = e.get().strip()
                if not txt:
                    return [_dt.today()]
                try:
                    dd, mm, aa = txt.split("/")
                    return [_dt(int(aa), int(mm), int(dd))]
                except Exception:
                    return []

            elif modo == "dias":
                return [dia for _, (_v, dia) in sorted(S["dias_vars"].items()) if _v.get()]

            elif modo == "recorrente":
                try:
                    e_ini = S["e_rec_inicio"]
                    e_fim = S["e_rec_fim"]
                    if e_ini is None:
                        return []
                    di_txt = e_ini.get().strip()
                    df_txt = e_fim.get().strip() if e_fim else ""
                    dd, mm, aa = di_txt.split("/")
                    inicio = _dt(int(aa), int(mm), int(dd))
                    if df_txt:
                        dd2, mm2, aa2 = df_txt.split("/")
                        fim = _dt(int(aa2), int(mm2), int(dd2))
                    else:
                        fim = inicio + _td(weeks=4)
                    freq     = S["cb_freq"].get() if S["cb_freq"] else "Semanal"
                    dias_sel = [_i3 for _i3, _vv in S["dias_rec_vars"].items() if _vv.get()]
                except Exception:
                    return []

                datas = []
                cur   = inicio
                ult_qz: dict = {}
                while cur <= fim:
                    if freq == "Diária":
                        datas.append(cur)
                    elif freq == "Dias úteis":
                        if cur.weekday() < 5:
                            datas.append(cur)
                    elif freq == "Semanal":
                        if cur.weekday() in dias_sel:
                            datas.append(cur)
                    elif freq == "Quinzenal":
                        if cur.weekday() in dias_sel:
                            ult = ult_qz.get(cur.weekday())
                            if ult is None or (cur - ult).days >= 14:
                                datas.append(cur)
                                ult_qz[cur.weekday()] = cur
                    elif freq == "Mensal":
                        if cur.day == inicio.day:
                            datas.append(cur)
                    cur += _td(days=1)
                return datas

            return []

        def _atualizar_preview():
            n = len(_calcular_datas())
            if n == 0:
                lbl_prev.configure(text="")
            elif n == 1:
                lbl_prev.configure(text="📅  1 tarefa será criada")
            else:
                lbl_prev.configure(text=f"📅  {n} tarefas serão criadas ao salvar")

        def _atualizar_modo():
            modo = var_modo.get()
            if   modo == "unica":       _build_unica()
            elif modo == "dias":        _build_dias()
            elif modo == "recorrente":  _build_recorrente()
            _atualizar_preview()

        def _salvar():
            titulo = e_titulo.get().strip()
            if not titulo:
                messagebox.showwarning("Atenção", "O título é obrigatório.", parent=d)
                return

            try:
                hora_inicio = _normalizar_hora_hhmm(e_hora_ini.get().strip()) if e_hora_ini.get().strip() else None
                hora_fim = _normalizar_hora_hhmm(e_hora_fim.get().strip()) if e_hora_fim.get().strip() else None
            except Exception:
                messagebox.showwarning("Atenção", "Horário inválido. Use HH:MM.", parent=d)
                return

            duracao_txt = e_duracao.get().strip()
            duracao_min = None
            if duracao_txt:
                try:
                    duracao_min = max(1, int(duracao_txt))
                except Exception:
                    messagebox.showwarning("Atenção", "Duração inválida. Informe minutos inteiros.", parent=d)
                    return

            if (hora_fim or duracao_min is not None) and not hora_inicio:
                messagebox.showwarning("Atenção", "Informe a hora de início para usar fim ou duração.", parent=d)
                return

            payload_base = {
                "titulo":     titulo,
                "descricao":  e_desc.get().strip() or None,
                "data":       None,
                "hora_inicio": hora_inicio,
                "hora_fim":    hora_fim,
                "duracao_min": duracao_min,
                "prioridade": cb_prio.get(),
                "status":     cb_status.get(),
                "area":       cb_area.get(),
            }

            datas    = _calcular_datas()
            n_datas  = len(datas)
            if n_datas == 0:
                messagebox.showwarning("Atenção", "Selecione ao menos uma data.", parent=d)
                return

            if n_datas > 30 and not messagebox.askyesno(
                "Confirmar",
                f"Serão criadas {n_datas} tarefas. Confirma?",
                parent=d,
            ):
                return

            try:
                db = self.app._obter_db()
                try:
                    if edicao:
                        from app.services.agenda_service import atualizar_tarefa
                        payload_base["data"] = datas[0]
                        atualizar_tarefa(db, tarefa_id, payload_base)
                    elif n_datas == 1:
                        from app.services.agenda_service import criar_tarefa
                        payload_base["data"] = datas[0]
                        criar_tarefa(db, payload_base)
                    else:
                        from app.services.agenda_service import criar_multiplas_tarefas
                        criar_multiplas_tarefas(db, payload_base, datas)
                finally:
                    db.close()
            except Exception as ex:
                messagebox.showerror("Erro", str(ex), parent=d)
                return

            msg = (
                f"✅ {n_datas} tarefa{'s' if n_datas > 1 else ''} "
                f"criada{'s' if n_datas > 1 else ''}!"
                if not edicao else "✅ Tarefa atualizada!"
            )
            d.destroy()
            self._lbl_metrics.configure(text=msg)
            self.carregar()

        # ── Pré-popula (edição) ───────────────────────────────────────────
        if dados:
            e_titulo.insert(0, dados.get("titulo", ""))
            e_desc.insert(0,   dados.get("descricao", "") or "")
            e_hora_ini.insert(0, dados.get("hora_inicio", "") or "")
            e_hora_fim.insert(0, dados.get("hora_fim", "") or "")
            if dados.get("duracao_min") is not None:
                e_duracao.insert(0, str(dados.get("duracao_min")))
            cb_prio.set(  dados.get("prioridade", "media"))
            cb_status.set(dados.get("status",      "a_fazer"))
            cb_area.set(  dados.get("area",        "pessoal"))
        elif hora_pre:
            e_hora_ini.insert(0, hora_pre)

        # Inicia no modo "Data única"
        _build_unica()


# ================================================
# Ponto de entrada
# ================================================

def main():
    """Inicia a interface gráfica do Assistente Financeiro."""
    app = AssistenteFinanceiroApp()
    app.mainloop()


if __name__ == "__main__":
    main()
