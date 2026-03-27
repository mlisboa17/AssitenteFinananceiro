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
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


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
        r'^(?:gastei|gasto|paguei|pago|despesa)\s+(.+)$',
        re.IGNORECASE,
    )
    _PADRAO_VALOR_DESC = re.compile(
        r'^\s*(?P<valor>(?:r\$\s*)?[0-9][0-9.,]*)\s*(?:-|:|=|,)?\s*(?P<desc>.+?)\s*$',
        re.IGNORECASE,
    )
    _PADRAO_DESC_VALOR = re.compile(
        r'^\s*(?P<desc>.+?)\s*(?:-|:|=|,)?\s*(?P<valor>(?:r\$\s*)?[0-9][0-9.,]*)\s*$',
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
        "gasolina: 80",
        "50 uber ontem",
        "restaurante 120 em 24/03/2026",
    ]

    def __init__(self):
        load_dotenv()
        self.token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID",   "")
        self._bot    = None
        self._ativo  = False
        self._historico_por_chat: Dict[str, List[Dict[str, str]]] = {}

        self.ollama_enabled = os.getenv("TELEGRAM_AI_ENABLED", "true").strip().lower() in {"1", "true", "yes", "sim", "on"}
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        self.ollama_timeout = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90"))
        self.max_contexto = int(os.getenv("TELEGRAM_AI_MAX_CONTEXT", "12"))
        self.system_prompt = os.getenv(
            "TELEGRAM_AI_SYSTEM_PROMPT",
            (
                "Voce e um assistente financeiro pessoal conversando no Telegram em portugues do Brasil. "
                "Responda como humano: empatico, claro e objetivo. "
                "Use contexto das mensagens anteriores quando relevante. "
                "Quando fizer sentido, conecte sua resposta a controle de gastos, metas e organizacao financeira. "
                "Evite respostas robóticas e nao invente dados."
            ),
        )

        if self.token:
            self._inicializar_bot()

    # --------------------------------------------------
    # Inicialização
    # --------------------------------------------------

    def _inicializar_bot(self) -> None:
        """Tenta inicializar o bot do Telegram."""
        try:
            from telegram import Bot
            self._bot   = Bot(token=self.token)
            self._ativo = True
            logger.info("Bot do Telegram inicializado com sucesso.")
        except ImportError:
            logger.warning("python-telegram-bot não instalado. Telegram desativado.")
        except Exception as e:
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
            logger.info(f"[Telegram DESATIVADO] Mensagem: {texto}")
            return False

        destino = chat_id or self.chat_id
        if not destino:
            logger.warning("TELEGRAM_CHAT_ID não configurado.")
            return False

        reply_markup = None
        if botoes:
            try:
                from telegram import ReplyKeyboardMarkup

                reply_markup = ReplyKeyboardMarkup(
                    botoes,
                    resize_keyboard=True,
                    one_time_keyboard=True,
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
            "👋 Olá! Envie uma despesa em texto livre.\n\n"
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
        """
        if not self.ollama_enabled:
            return (
                "Posso te ajudar com gastos, metas e planejamento financeiro. "
                "Ative o modo de IA local configurando TELEGRAM_AI_ENABLED=true e Ollama."
            )

        historico = self._historico_por_chat.setdefault(chat_id, [])
        historico.append({"role": "user", "content": texto.strip()})
        if len(historico) > self.max_contexto:
            historico[:] = historico[-self.max_contexto:]

        resposta = self._gerar_resposta_ollama(historico)
        if not resposta:
            return (
                "Não consegui acessar a IA local agora. "
                "Verifique se o Ollama esta ativo e se o modelo foi baixado."
            )

        historico.append({"role": "assistant", "content": resposta})
        if len(historico) > self.max_contexto:
            historico[:] = historico[-self.max_contexto:]
        return resposta

    def _gerar_resposta_ollama(self, historico: List[Dict[str, str]]) -> Optional[str]:
        mensagens = [{"role": "system", "content": self.system_prompt}] + historico

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
        return {
            "ativo":     self._ativo,
            "token_ok":  bool(self.token),
            "chat_ok":   bool(self.chat_id),
            "ai_local_enabled": self.ollama_enabled,
            "ai_local_ok": self._ollama_disponivel(),
            "ai_model": self.ollama_model,
        }
