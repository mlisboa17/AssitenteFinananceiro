"""
Serviço de integração com o Telegram.

Funcionalidades planejadas (prontas para ativação futura):
  1. Envio de mensagens, alertas e relatórios
  2. Recebimento de comandos de texto do usuário
  3. Registro rápido de despesas via Telegram
     Exemplos de comandos:
       - "Registrar despesa 35 mercado"
       - "Gastei 50 gasolina"
       - "Adicionar despesa 120 restaurante"
  4. Interpretação automática de valor, categoria, descrição e data
  5. Confirmação ao usuário após registrar

Para ativar:
  1. Instale: pip install python-telegram-bot
  2. Crie um bot com o @BotFather no Telegram
  3. Preencha TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no arquivo .env
"""

import os
import re
import logging
import asyncio
import requests
import io
import random
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class PerfilUsuarioTelegram:
    """Armazena e gerencia o perfil e contexto de um usuário no Telegram."""

    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        self.nome: Optional[str] = None
        self.objetivo_principal: Optional[str] = None
        self.ultima_atualizacao = datetime.now()
        self.total_transacoes_registradas = 0
        self.resumo_contexto: Optional[str] = None

    def atualizar_nome(self, nome: str):
        if nome and len(nome.strip()) > 0:
            self.nome = nome.strip()
            self.ultima_atualizacao = datetime.now()

    def atualizar_resumo(self, novo_resumo: str):
        """Simula um resumo do histórico para manter contexto sem inchar as mensagens."""
        if novo_resumo:
            self.resumo_contexto = novo_resumo
            self.ultima_atualizacao = datetime.now()

    def incrementar_transacoes(self):
        self.total_transacoes_registradas += 1


class TelegramService:
    """
    Serviço de comunicação bidirecional via Telegram Bot.

    Integração real com envio de mensagens quando token e chat_id estiverem configurados.
    """

    _PADRAO_COMANDO_PREFIXO = re.compile(
        r'^(?:registrar|cadastrar|adicionar)\s+(?:despesa|gasto)\s+(.+)$',
        re.IGNORECASE,
    )
    _PADRAO_COMANDO_VERBO = re.compile(
        r'^(?:gastei|gasto|gast|paguei|pago|despesa|comprei|pix|fiz\s+pix|dei|foi)\s+(.+)$',
        re.IGNORECASE,
    )
    _PADRAO_VALOR_DESC = re.compile(
        r'^\s*(?P<valor>(?:r\$\s*)?[0-9][0-9.,]*(?:\s*(?:reais?|rs))?)\s*(?:-|:|=|,)?\s*(?P<desc>.+?)\s*$',
        re.IGNORECASE,
    )
    _PADRAO_DESC_VALOR = re.compile(
        r'^\s*(?P<desc>.+?)\s*(?:-|:|=|,)?\s*(?P<valor>(?:r\$\s*)?[0-9][0-9.,]*(?:\s*(?:reais?|rs))?)\s*$',
        re.IGNORECASE,
    )
    _PADRAO_DATA_FIM = re.compile(
        r'^(?P<corpo>.+?)\s+(?:em\s+)?(?P<data>\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\s*$',
        re.IGNORECASE,
    )

    _EXEMPLOS_RAPIDOS = [
        "restaurante 50",
        "50 gasolina",
        "gastei 35 em padaria",
        "pix 30 uber",
        "dei 12 no cafe",
        "gasolina: 80",
        "50 uber ontem",
        "restaurante 120 em 24/03/2026",
    ]

    _MEMES_FINANCEIROS = [
        "✅ Abrir o app do banco dia 28 e falar: caramba, quem fez isso comigo?",
        "✅ Ver a fatura fechar e pensar: claramente fui hackeado por mim mesmo.",
        "✅ Dizer 'esse mes vai' e no dia 20 ja estar negociando com o proprio limite.",
        "✅ Abrir o extrato so pra confirmar que o caos continua consistente.",
        "✅ Fazer planilha de gastos e usar ela como ficcao cientifica.",
        "✅ Passar o cartao com confianca e chorar com elegancia depois.",
        "✅ Falar 'foi so um cafezinho' 17 vezes no mesmo mes.",
        "✅ Receber salario de manha e a noite ele ja estar em modo lenda urbana.",
        "✅ Consultar o saldo com a mesma coragem de quem abre resultado de prova.",
        "✅ Prometer economia e cumprir... a partir do mes que vem.",
        "✅ Olhar pro app do banco e perguntar: qual foi a emergencia dessa vez?",
        "✅ Separar dinheiro da fatura e chamar isso de investimento de alto risco.",
        "✅ Entrar no mercado pra comprar pao e sair com um rombo existencial.",
        "✅ Dizer que vai cortar gastos e assinar mais um streaming no mesmo dia.",
        "✅ Conferir o limite disponivel como quem checa batimentos cardiacos.",
        "✅ Colocar 'controle financeiro' na meta e 'delivery' na pratica diaria.",
        "✅ Pedir uma coisinha online e ganhar frete, taxa, arrependimento e boleto.",
        "✅ Lembrar da reserva de emergencia so quando a emergencia ja aconteceu.",
        "✅ Ver 'cashback de 2 reais' e gastar 200 pra nao perder a oportunidade.",
        "✅ Dizer 'agora vai' toda segunda, e toda sexta repetir a mesma tese.",
        "✅ Ler sobre investimento do tipo 'renda fixa' e investir em streaming indefinido.",
        "✅ Calcular quantas calorias tem a sobremesa e as vezes levar 3 pra 'compensar'.",
        "✅ Achar um promo de 50% off e comprar 5 coisas que nao precisa pra 'economizar'.",
        "✅ Reclamar que comida esta cara e pedir gelo com 5 refris diferentes no bar.",
        "✅ Sonhar em viagem pra Europa mas nao consegue ir de metro sem reclamar do preco.",
        "✅ Dizer 'proxima semana eu comeco a dieta' toda sexta a noite no churrasco.",
        "✅ Jurar por tudo que nunca mais vai comprar impulso... ja tem 3 coisas no carrinho.",
        "✅ Ver que aumentou o minimo no app do banco e comemorar como se fosse salario extra.",
        "✅ Planejar ir no cinema certeiro e acabar gastando 300 em pipoca + refri + comida.",
        "✅ Falar que esta sem grana pro aluguel mas tem dinheiro pra cerveja com os amigos.",
        "✅ Receber coin de alguma rede de app e achar que ficou rico digitalmente.",
        "✅ Ver anuncio de curso garantindo ficar rico e apenas mudar de pobre pra mais pobre.",
        "✅ Estipular orcamento e usar ele como sugestao bem gentil que ninguem obedece.",
        "✅ Na black friday comprar coisa que custa 300 'porque estava 250 off' do preco falso.",
        "✅ Prometer aos amigos 'vamos rachar a conta' e ir pra casa relanzando calculadora.",
    ]

    def __init__(self):
        load_dotenv()
        self.token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID",   "")
        self._bot    = None
        self._ativo  = False
        self._config_erro = ""
        self._historico_por_chat: Dict[str, List[Dict[str, str]]] = {}
        self._perfis_usuarios: Dict[str, PerfilUsuarioTelegram] = {}
        self._memes_embaralhados: List[str] = []
        self._ultimo_meme_enviado: Optional[str] = None
        self.meme_auto_chance = float(os.getenv("TELEGRAM_MEME_AUTO_CHANCE", "0.35"))

        self.ollama_enabled = os.getenv("TELEGRAM_AI_ENABLED", "true").strip().lower() in {"1", "true", "yes", "sim", "on"}
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        self.ollama_timeout = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90"))
        self.max_contexto = int(os.getenv("TELEGRAM_AI_MAX_CONTEXT", "12"))
        self.system_prompt = os.getenv(
            "TELEGRAM_AI_SYSTEM_PROMPT",
            (
                "Você é um amigo financeiro no Telegram. Conversa como humano: natural, empático e prático. "
                "NÃO se apresente como 'assistente IA' nem use formalidades robóticas. "
                "Leia o contexto das mensagens anteriores e responda considerando tudo que o usuário já te contou. "
                "Se ele mencionou uma meta de economizar, lembre disso. Se falou sobre gastos, considere na resposta. "
                "Use gírias naturais. Seja breve. Quando relevante, conecte a finanças pessoais. "
                "Nunca invente dados. Se não souber, diga 'não tenho essa info'. "
                "Linguagem: português do Brasil, informal e acessível."
            ),
        )

        if self.token:
            self._inicializar_bot()
        else:
            self._config_erro = "TELEGRAM_BOT_TOKEN ausente no .env. Integração Telegram desativada."

    # --------------------------------------------------
    # Inicialização
    # --------------------------------------------------

    def _inicializar_bot(self) -> None:
        """Tenta inicializar o bot do Telegram."""
        try:
            from telegram import Bot
            self._bot   = Bot(token=self.token)
            self._ativo = True
            self._config_erro = ""
            logger.info("Bot do Telegram inicializado com sucesso.")
        except ImportError:
            self._config_erro = "Pacote python-telegram-bot não instalado. Execute: pip install python-telegram-bot"
            logger.warning("python-telegram-bot não instalado. Telegram desativado.")
        except Exception as e:
            self._config_erro = f"Falha ao inicializar bot Telegram: {e}"
            logger.warning(f"Erro ao inicializar bot do Telegram: {e}")

    # --------------------------------------------------
    # Envio de mensagens
    # --------------------------------------------------

    async def enviar_mensagem(
        self,
        texto: str,
        chat_id: Optional[str] = None,
        botoes: Optional[List[List[str]]] = None,
    ) -> bool:
        """
        Envia uma mensagem de texto via Telegram.

        Args:
            texto:   Conteúdo da mensagem
            chat_id: ID do chat (usa o padrão do .env se None)
            botoes:  Teclado simples de resposta, quando necessário

        Returns:
            True se enviado com sucesso, False caso contrário
        """
        if not self._ativo or not self._bot:
            detalhe = self._config_erro or "Bot Telegram não inicializado."
            logger.info(f"[Telegram DESATIVADO] {detalhe} | Mensagem: {texto}")
            return False

        destino = chat_id or self.chat_id
        if not destino:
            logger.warning("TELEGRAM_CHAT_ID não configurado.")
            return False

        reply_markup = None
        if botoes:
            try:
                from telegram import ReplyKeyboardMarkup

                try:
                    # Teclado persistente deixa a experiência mais fluida como mini-app.
                    reply_markup = ReplyKeyboardMarkup(
                        botoes,
                        resize_keyboard=True,
                        one_time_keyboard=False,
                        input_field_placeholder="Use os botões ou digite sua mensagem...",
                        is_persistent=True,
                    )
                except TypeError:
                    # Compatibilidade com versões sem is_persistent/input_field_placeholder.
                    reply_markup = ReplyKeyboardMarkup(
                        botoes,
                        resize_keyboard=True,
                        one_time_keyboard=False,
                    )
            except Exception:
                logger.debug("Não foi possível montar teclado do Telegram.", exc_info=True)

        try:
            await self._bot.send_message(
                chat_id=destino,
                text=texto,
                reply_markup=reply_markup,
            )
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem Telegram: {e}")
            return False

    def enviar_mensagem_sync(self, texto: str, chat_id: Optional[str] = None) -> bool:
        """Wrapper síncrono para uso em GUI e endpoints tradicionais."""
        return asyncio.run(self.enviar_mensagem(texto, chat_id=chat_id))

    async def enviar_alerta(self, titulo: str, descricao: str, valor: Optional[float] = None) -> bool:
        """
        Envia um alerta financeiro formatado.

        Args:
            titulo:    Título do alerta
            descricao: Descrição detalhada
            valor:     Valor monetário relacionado (opcional)
        """
        from app.utils.helpers import formatar_moeda

        linhas = [f"⚠️ *{titulo}*", "", descricao]
        if valor is not None:
            linhas.append(f"Valor: *{formatar_moeda(valor)}*")

        return await self.enviar_mensagem("\n".join(linhas))

    async def enviar_relatorio(
        self,
        periodo: str,
        total_receitas: float,
        total_despesas: float,
        saldo: float,
        categorias: list,
    ) -> bool:
        """
        Envia relatório financeiro resumido via Telegram.

        Args:
            periodo:        Label do período (ex: "Janeiro/2024")
            total_receitas: Soma das receitas
            total_despesas: Soma das despesas
            saldo:          Saldo do período
            categorias:     Lista de dicts {categoria, valor}
        """
        from app.utils.helpers import formatar_moeda

        linhas = [
            f"📊 *Relatório Financeiro — {periodo}*",
            "",
            f"✅ Receitas:  {formatar_moeda(total_receitas)}",
            f"❌ Despesas: {formatar_moeda(total_despesas)}",
            f"💰 Saldo:    {formatar_moeda(saldo)}",
            "",
            "*Top Categorias:*",
        ]
        for cat in categorias[:5]:
            linhas.append(f"  • {cat['categoria']}: {formatar_moeda(cat['valor'])}")

        return await self.enviar_mensagem("\n".join(linhas))

    def teclado_menu_principal(self) -> List[List[str]]:
        """Menu principal de atalhos para o usuário no Telegram."""
        return [
            ["📌 Resumo do mês", "📊 Gráficos"],
            ["💡 Sugestões", "➕ Lançar despesa"],
            ["📎 Importar documento", "🧹 Limpar contexto"],
            ["❓ Ajuda", "🏠 Menu"],
        ]

    def meme_financeiro_aleatorio(self) -> str:
        """Retorna um meme financeiro com rotação aleatória e baixa repetição."""
        if not self._memes_embaralhados:
            self._memes_embaralhados = list(self._MEMES_FINANCEIROS)
            random.shuffle(self._memes_embaralhados)

            # Evita repetir exatamente o último meme quando o ciclo reinicia.
            if (
                self._ultimo_meme_enviado
                and len(self._memes_embaralhados) > 1
                and self._memes_embaralhados[0] == self._ultimo_meme_enviado
            ):
                self._memes_embaralhados.append(self._memes_embaralhados.pop(0))

        meme = self._memes_embaralhados.pop(0)
        self._ultimo_meme_enviado = meme
        return (
            "😂 Meme financeiro aleatório\n\n"
            f"{meme}\n\n"
            "Se quiser, eu te mando outro."
        )

    def mensagem_com_meme_automatico(self, texto_base: str, *, forcar: bool = False) -> str:
        """Anexa um meme automaticamente em parte das respostas de conversa."""
        texto_limpo = (texto_base or "").strip()
        if not texto_limpo:
            return self.meme_financeiro_aleatorio()

        chance = max(0.0, min(1.0, float(self.meme_auto_chance or 0.0)))
        if (not forcar) and random.random() > chance:
            return texto_limpo

        meme = self.meme_financeiro_aleatorio()
        return f"{texto_limpo}\n\n{meme}"

    async def enviar_grafico_resumo(
        self,
        *,
        chat_id: Optional[str],
        periodo: str,
        total_receitas: float,
        total_despesas: float,
        saldo: float,
        categorias: List[Dict[str, Any]],
    ) -> bool:
        """Gera e envia gráfico-resumo financeiro (pizza + barras) no Telegram."""
        if not self._ativo or not self._bot:
            logger.info("[Telegram DESATIVADO] Gráfico não enviado para %s", chat_id)
            return False

        destino = chat_id or self.chat_id
        if not destino:
            logger.warning("TELEGRAM_CHAT_ID não configurado para envio de gráfico.")
            return False

        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig = plt.figure(figsize=(10, 4.8), facecolor="#0B132B")
            gs = fig.add_gridspec(1, 2, width_ratios=[1.15, 1])

            ax1 = fig.add_subplot(gs[0, 0])
            ax1.set_facecolor("#0B132B")
            top = (categorias or [])[:6]
            if top:
                nomes = [str(c.get("categoria") or "Outros") for c in top]
                valores = [float(c.get("valor") or 0) for c in top]
                cores = ["#2E86AB", "#E74C3C", "#27AE60", "#F39C12", "#9B59B6", "#1ABC9C"]
                wedges, _, _ = ax1.pie(
                    valores,
                    labels=None,
                    autopct="%1.0f%%",
                    startangle=90,
                    colors=cores[: len(valores)],
                    wedgeprops={"width": 0.45},
                    textprops={"color": "white", "fontsize": 9},
                )
                ax1.legend(
                    wedges,
                    nomes,
                    loc="lower center",
                    bbox_to_anchor=(0.5, -0.22),
                    ncol=2,
                    fontsize=8,
                    frameon=False,
                    labelcolor="white",
                )
                ax1.set_title("Gastos por categoria", color="white", fontsize=11, fontweight="bold")
            else:
                ax1.text(0.5, 0.5, "Sem dados de categoria", color="white", ha="center", va="center")
                ax1.set_title("Gastos por categoria", color="white", fontsize=11, fontweight="bold")

            ax2 = fig.add_subplot(gs[0, 1])
            ax2.set_facecolor("#0B132B")
            labels = ["Receitas", "Despesas", "Saldo"]
            valores_barra = [float(total_receitas or 0), float(total_despesas or 0), float(saldo or 0)]
            cores_barra = ["#27AE60", "#E74C3C", "#00A8E8" if saldo >= 0 else "#F39C12"]
            ax2.bar(labels, valores_barra, color=cores_barra, alpha=0.9)
            ax2.tick_params(axis="x", colors="white", labelsize=9)
            ax2.tick_params(axis="y", colors="white", labelsize=8)
            ax2.grid(axis="y", linestyle="--", alpha=0.25, color="#A5B4FC")
            ax2.spines[:].set_visible(False)
            ax2.set_title("Receitas x Despesas", color="white", fontsize=11, fontweight="bold")

            fig.suptitle(f"Vorcaro • Dashboard {periodo}", color="white", fontsize=13, fontweight="bold")
            fig.tight_layout(rect=(0, 0, 1, 0.94))

            buff = io.BytesIO()
            fig.savefig(buff, format="png", dpi=140, facecolor=fig.get_facecolor())
            plt.close(fig)
            buff.seek(0)

            await self._bot.send_photo(
                chat_id=destino,
                photo=buff,
                caption=f"📊 Gráfico financeiro de {periodo}",
            )
            return True
        except ImportError:
            logger.warning("matplotlib não instalado; não foi possível gerar gráfico Telegram.")
            return await self.enviar_mensagem(
                "📊 Não consegui gerar gráfico agora porque o matplotlib não está instalado no ambiente.",
                chat_id=destino,
            )
        except Exception as exc:
            logger.exception("Falha ao enviar gráfico no Telegram")
            return await self.enviar_mensagem(
                f"❌ Não consegui gerar o gráfico agora: {exc}",
                chat_id=destino,
            )

    # --------------------------------------------------
    # Interpretação de comandos
    # --------------------------------------------------

    def interpretar_comando_despesa(self, texto: str) -> Optional[Dict[str, Any]]:
        """
        Interpreta um texto livre como comando de registro de despesa.

                Exemplos reconhecidos:
          "Registrar despesa 35 mercado"   -> {valor: 35.0, descricao: "mercado", ...}
          "Gastei 50 gasolina"             -> {valor: 50.0, descricao: "gasolina", ...}
          "120 restaurante"                -> {valor: 120.0, descricao: "restaurante", ...}
                    "restaurante 50"                 -> {valor: 50.0, descricao: "restaurante", ...}
                    "gasolina: 80"                   -> {valor: 80.0, descricao: "gasolina", ...}

        Args:
            texto: Mensagem do usuário

        Returns:
            Dicionário com dados da despesa ou None se não reconhecido
        """
        texto = (texto or "").strip()
        if not texto:
            return None

        corpo = texto
        m = self._PADRAO_COMANDO_PREFIXO.match(texto)
        if m:
            corpo = m.group(1).strip()
        else:
            m = self._PADRAO_COMANDO_VERBO.match(texto)
            if m:
                corpo = m.group(1).strip()

        corpo, data_lancamento = self._extrair_data_no_fim(corpo)

        extraido = self._extrair_valor_descricao(corpo)
        if not extraido:
            return None

        valor, descricao = extraido
        if valor <= 0:
            return None

        return {
            "valor":     valor,
            "descricao": descricao,
            "data":      data_lancamento,
            "tipo":      "debito",
            "fonte":     "telegram",
        }

    def mensagem_ajuda_despesa(self) -> str:
        exemplos = "\n".join(f"• {e}" for e in self._EXEMPLOS_RAPIDOS)
        return (
            "👋 Olá! Eu sou o Vorcaro no Telegram.\n\n"
            "Você pode usar os botões abaixo para navegar rápido ou digitar natural.\n\n"
            "🧾 Para lançar despesa, envie em texto livre.\n\n"
            "Exemplos:\n"
            f"{exemplos}\n\n"
            "Você pode informar data no final: hoje, ontem, ou DD/MM[/AAAA]."
        )

    def mensagem_formato_invalido(self) -> str:
        return (
            "Não entendi o formato da despesa.\n"
            "Use apenas descrição e valor, por exemplo:\n"
            "• restaurante 50\n"
            "• 50 gasolina\n"
            "• 50 uber ontem"
        )

    def responder_conversa(self, chat_id: str, texto: str) -> str:
        """
        Gera resposta conversacional com contexto usando Ollama local.
        Mantém perfil de usuário e resume automaticamente quando necessário.
        """
        if not self.ollama_enabled:
            return (
                "Posso te ajudar com teus gastos e metas. "
                "Ativa o modo local no .env (TELEGRAM_AI_ENABLED=true) + Ollama."
            )

        # Obtém ou cria perfil
        perfil = self._perfis_usuarios.setdefault(chat_id, PerfilUsuarioTelegram(chat_id))
        historico = self._historico_por_chat.setdefault(chat_id, [])
        
        # Detecta nome do usuário na mensagem
        if "meu nome é" in texto.lower() or "me chamo" in texto.lower():
            match = re.search(r"(?:nome|chamo)\s+[éé]\s+([A-Za-záàâãéèêíïóôõöúçñ\s]+)", texto, re.IGNORECASE)
            if match:
                nome = match.group(1).strip()
                perfil.atualizar_nome(nome)
        
        historico.append({"role": "user", "content": texto.strip()})
        
        # Sumariza automaticamente se houver muitas mensagens
        if len(historico) > self.max_contexto + 4:
            historico = self._sumarizar_historico(historico, perfil)
            self._historico_por_chat[chat_id] = historico
        elif len(historico) > self.max_contexto:
            historico[:] = historico[-self.max_contexto:]

        resposta = self._gerar_resposta_ollama(historico, perfil)
        if not resposta:
            return (
                "Não consegui acessar a IA agora. "
                "Verifica se o Ollama tá ativo (ollama serve) e se baixou o modelo."
            )

        historico.append({"role": "assistant", "content": resposta})
        if len(historico) > self.max_contexto:
            historico[:] = historico[-self.max_contexto:]
        return resposta

    def limpar_contexto_conversa(self, chat_id: str) -> bool:
        """Remove o histórico acumulado de um chat específico."""
        chat_id_norm = str(chat_id or "").strip()
        if not chat_id_norm:
            return False
        return self._historico_por_chat.pop(chat_id_norm, None) is not None

    def _gerar_resposta_ollama(self, historico: List[Dict[str, str]], perfil: Optional[PerfilUsuarioTelegram] = None) -> Optional[str]:
        # Inclui contexto de perfil se disponível
        prompt_sistema = self.system_prompt
        if perfil and perfil.nome:
            prompt_sistema += f"\n\nContexto do usuário: Seu nome é {perfil.nome}. "
        if perfil and perfil.resumo_contexto:
            prompt_sistema += f"\nResumo da conversa: {perfil.resumo_contexto}"
        
        mensagens = [{"role": "system", "content": prompt_sistema}] + historico

        try:
            resp = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.ollama_model,
                    "messages": mensagens,
                    "stream": False,
                },
                timeout=self.ollama_timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            conteudo = (data.get("message") or {}).get("content", "")
            conteudo = (conteudo or "").strip()
            return conteudo or None
        except Exception as exc:
            logger.warning(f"Falha ao gerar resposta com Ollama: {exc}")
            return None

    def _sumarizar_historico(self, historico: List[Dict[str, str]], perfil: PerfilUsuarioTelegram) -> List[Dict[str, str]]:
        """Sumariza mensagens antigas para manter contexto sem inchar a conversa."""
        if len(historico) <= 4:
            return historico
        
        # Mantém as últimas 6 mensagens e sumariza o resto
        ultimas = historico[-6:]
        antigas = historico[:-6]
        
        # Extrai pontos-chave das antigas
        resumo_pontos = []
        for msg in antigas:
            content = (msg.get("content") or "").strip()
            if "economizar" in content.lower() or "meta" in content.lower():
                resumo_pontos.append(content[:80])
            elif "gastei" in content.lower() or "gasto" in content.lower():
                resumo_pontos.append(content[:80])
        
        if resumo_pontos:
            perfil.atualizar_resumo("; ".join(resumo_pontos[:3]))
        
        # Retorna últimas + placeholder de sumarização
        resumo_msg = {"role": "system", "content": f"[Contexto anterior resumido: {perfil.resumo_contexto or 'conversa anterior'}]"}
        return [resumo_msg] + ultimas

    def _ollama_disponivel(self) -> bool:
        if not self.ollama_enabled:
            return False
        try:
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=4)
            return resp.status_code == 200
        except Exception:
            return False

    def _extrair_data_no_fim(self, texto: str) -> Tuple[str, date]:
        base = (texto or "").strip()
        if not base:
            return base, date.today()

        lower = base.lower()
        if lower.endswith(" ontem"):
            return base[:-6].strip(), date.today() - timedelta(days=1)
        if lower == "ontem":
            return "", date.today() - timedelta(days=1)
        if lower.endswith(" hoje"):
            return base[:-5].strip(), date.today()
        if lower == "hoje":
            return "", date.today()

        m = self._PADRAO_DATA_FIM.match(base)
        if not m:
            return base, date.today()

        corpo = (m.group("corpo") or "").strip()
        data_s = (m.group("data") or "").strip().replace("-", "/")
        try:
            partes = data_s.split("/")
            if len(partes) == 2:
                dia = int(partes[0])
                mes = int(partes[1])
                ano = date.today().year
            else:
                dia = int(partes[0])
                mes = int(partes[1])
                ano = int(partes[2])
                if ano < 100:
                    ano += 2000

            dt = datetime(ano, mes, dia).date()
            return corpo, dt
        except Exception:
            return base, date.today()

    def _extrair_valor_descricao(self, texto: str) -> Optional[Tuple[float, str]]:
        """Extrai valor e descrição aceitando ordens flexíveis na mensagem."""
        for padrao in (self._PADRAO_VALOR_DESC, self._PADRAO_DESC_VALOR):
            m = padrao.match(texto)
            if not m:
                continue

            valor = self._parse_valor(m.group("valor"))
            if valor is None:
                continue

            descricao = self._limpar_descricao(m.group("desc"))
            if not descricao:
                continue

            return valor, descricao

        # Fallback robusto para frases faladas, ex: "gasolina 100 reais".
        m_num = re.search(r'(?P<valor>[0-9][0-9.,]*)\s*(?:reais?|rs)?\b', texto, flags=re.IGNORECASE)
        if not m_num:
            return None

        valor = self._parse_valor(m_num.group("valor"))
        if valor is None:
            return None

        inicio, fim = m_num.span()
        desc_bruta = (texto[:inicio] + " " + texto[fim:]).strip()
        descricao = self._limpar_descricao(desc_bruta)
        if not descricao:
            return None

        return valor, descricao

        return None

    @staticmethod
    def _limpar_descricao(texto: str) -> str:
        desc = (texto or "").strip(" -:=\t")
        desc = re.sub(r'^(?:em|no|na|para|pro|pra)\s+', '', desc, flags=re.IGNORECASE)
        desc = re.sub(r'\s+', ' ', desc).strip()
        return desc

    @staticmethod
    def _parse_valor(valor_s: str) -> Optional[float]:
        bruto = (valor_s or "").lower().replace("r$", "").replace(" ", "").strip()
        bruto = re.sub(r'(reais?|rs)$', '', bruto).strip()
        if not bruto:
            return None

        tem_ponto = "." in bruto
        tem_virgula = "," in bruto

        if tem_ponto and tem_virgula:
            # Ex.: 1.234,56
            if bruto.rfind(",") > bruto.rfind("."):
                bruto = bruto.replace(".", "").replace(",", ".")
            else:
                bruto = bruto.replace(",", "")
        elif tem_virgula:
            parte_decimal = bruto.split(",")[-1]
            if len(parte_decimal) == 3:
                bruto = bruto.replace(",", "")
            else:
                bruto = bruto.replace(",", ".")
        elif tem_ponto:
            parte_decimal = bruto.split(".")[-1]
            if len(parte_decimal) == 3:
                bruto = bruto.replace(".", "")

        try:
            return float(bruto)
        except ValueError:
            return None

        return None

    def formatar_confirmacao(
        self,
        valor: float,
        descricao: str,
        categoria: str,
        data: date,
    ) -> str:
        """
        Formata mensagem de confirmação de despesa registrada.

        Returns:
            Texto formatado com markdown do Telegram
        """
        from app.utils.helpers import formatar_moeda

        return (
            f"✅ *Despesa registrada com sucesso!*\n\n"
            f"📝 Descrição:  {descricao}\n"
            f"💵 Valor:      {formatar_moeda(valor)}\n"
            f"🏷️  Categoria: {categoria}\n"
            f"📅 Data:       {data.strftime('%d/%m/%Y')}"
        )

    # --------------------------------------------------
    # Configuração do webhook / polling (para uso futuro)
    # --------------------------------------------------

    def registrar_handlers(self, app_fastapi=None) -> None:
        """
        Registra os handlers de mensagem do bot.
        Deve ser chamado durante a inicialização da aplicação.
        Implementação completa disponível para ativação futura.
        """
        if not self._ativo:
            logger.info("Telegram não ativo. Handlers não registrados.")
            return

        logger.info("Handlers do Telegram registrados (implementação futura).")

    def status(self) -> Dict[str, Any]:
        """Retorna o status atual da integração Telegram."""
        mensagem = self._config_erro
        if not mensagem and not self.chat_id:
            mensagem = "TELEGRAM_CHAT_ID ausente no .env."
        if not mensagem and self._ativo:
            mensagem = "Telegram configurado e ativo."

        return {
            "ativo":     self._ativo,
            "token_ok":  bool(self.token),
            "chat_ok":   bool(self.chat_id),
            "ai_local_enabled": self.ollama_enabled,
            "ai_local_ok": self._ollama_disponivel(),
            "ai_model": self.ollama_model,
            "mensagem": mensagem,
        }
