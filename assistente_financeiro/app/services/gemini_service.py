"""
Serviço de IA com Google Gemini para o assistente financeiro Vorcaro.

O Vorcaro funciona como consultor financeiro pessoal:
  - Responde perguntas em linguagem natural sobre finanças do usuário
  - Analisa padrões de gasto, compara períodos, sugere economias
  - Mantém histórico de conversa dentro da sessão
  - Usa dados reais do banco de dados como contexto
"""

import logging
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, extract, desc

logger = logging.getLogger(__name__)

# ================================================
# Instrução de sistema — personalidade do Vorcaro
# ================================================

SYSTEM_INSTRUCTION = """Você é o Vorcaro, assistente financeiro pessoal inteligente, empático e direto.

Suas responsabilidades:
• Responder perguntas sobre gastos, receitas, saldo e categorias com base nos dados reais do usuário
• Identificar padrões de consumo e tendências
• Sugerir oportunidades de economia práticas e personalizadas
• Alertar sobre orçamentos próximos do limite ou estourados
• Comparar períodos (mês atual vs anterior, etc.)
• Ajudar com planejamento financeiro pessoal

Diretrizes de comportamento:
• Responda SEMPRE em português do Brasil
• Seja conciso mas completo — evite respostas longas sem necessidade
• Use formato R$ X.XXX,XX para valores monetários
• Se os dados disponíveis forem insuficientes, diga claramente o que falta
• Nunca invente valores ou transações que não estejam no contexto fornecido
• Seja encorajador e positivo, mesmo ao alertar sobre gastos excessivos
• Use bullet points ou listas apenas quando realmente melhorar a leitura
"""


# ================================================
# Serviço principal
# ================================================

class GeminiService:
    """
    Integração com Google Gemini para o assistente conversacional Vorcaro.

    Cada instância representa uma sessão de chat com contexto financeiro
    embutido no histórico inicial.
    """

    MODEL = "gemini-2.5-flash-lite"

    def __init__(self, api_key: str, db: Session):
        """
        Inicializa o serviço e abre uma sessão de chat com contexto financeiro.

        Args:
            api_key: Chave da API do Google AI Studio
            db:      Sessão ativa do banco de dados para montar o contexto
        """
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise ImportError(
                "Pacote 'google-genai' não encontrado. "
                "Instale com:  pip install google-genai"
            ) from exc

        self._client = genai.Client(api_key=api_key)
        self._types  = types

        # Injeta contexto financeiro como priming invisível ao usuário
        contexto = self.construir_contexto(db)
        priming_user  = (
            "A seguir está o contexto financeiro atual do usuário. "
            "Use esses dados para responder às perguntas dele.\n\n"
            + contexto
        )
        priming_model = (
            "Contexto financeiro recebido e carregado. "
            "Estou pronto para ajudar com suas finanças!"
        )

        self._chat = self._client.chats.create(
            model=self.MODEL,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
            ),
            history=[
                types.Content(role="user",  parts=[types.Part(text=priming_user)]),
                types.Content(role="model", parts=[types.Part(text=priming_model)]),
            ],
        )

        logger.info("GeminiService inicializado com modelo %s", self.MODEL)

    # --------------------------------------------------
    # Interface pública
    # --------------------------------------------------

    def enviar(self, pergunta: str) -> str:
        """
        Envia uma pergunta ao Gemini e retorna a resposta em texto.

        Args:
            pergunta: Mensagem do usuário

        Returns:
            Texto da resposta gerada pelo modelo
        """
        try:
            response = self._chat.send_message(pergunta)
            return response.text
        except Exception as exc:
            logger.error("Erro ao consultar Gemini: %s", exc)
            raise

    # --------------------------------------------------
    # Construção do contexto financeiro
    # --------------------------------------------------

    @staticmethod
    def construir_contexto(db: Session) -> str:
        """
        Monta um resumo textual do status financeiro atual para alimentar o LLM.

        Inclui:
          - Totais do mês corrente (receitas, despesas, saldo)
          - Gastos por categoria no mês atual
          - Comparação com mês anterior
          - Últimas 15 transações
          - Categorias cadastradas

        Args:
            db: Sessão do banco de dados

        Returns:
            String com o contexto formatado
        """
        from app.models import Transacao, Categoria, Orcamento
        from app.utils.helpers import formatar_moeda, periodo_label

        hoje = date.today()
        mes, ano = hoje.month, hoje.year

        # Mês anterior
        m_ant = mes - 1 if mes > 1 else 12
        a_ant = ano if mes > 1 else ano - 1

        def total_mes(m, a, tipo):
            r = db.query(func.sum(Transacao.valor)).filter(
                extract("month", Transacao.data) == m,
                extract("year",  Transacao.data) == a,
                Transacao.tipo == tipo,
            ).scalar()
            return float(r or 0)

        receitas  = total_mes(mes, ano, "credito")
        despesas  = total_mes(mes, ano, "debito")
        saldo     = receitas - despesas
        desp_ant  = total_mes(m_ant, a_ant, "debito")
        rec_ant   = total_mes(m_ant, a_ant, "credito")

        # Gastos por categoria no mês atual
        cat_rows = (
            db.query(Categoria.nome, func.sum(Transacao.valor))
            .join(Transacao, Transacao.categoria_id == Categoria.id)
            .filter(
                extract("month", Transacao.data) == mes,
                extract("year",  Transacao.data) == ano,
                Transacao.tipo == "debito",
            )
            .group_by(Categoria.nome)
            .order_by(func.sum(Transacao.valor).desc())
            .all()
        )
        cats_txt = (
            "\n".join(f"  • {nome}: {formatar_moeda(val)}" for nome, val in cat_rows)
            or "  (sem registros de despesas este mês)"
        )

        # Orçamentos ativos
        orcamentos = (
            db.query(Orcamento)
            .filter(Orcamento.mes == mes, Orcamento.ano == ano)
            .all()
        )
        orc_linhas = []
        for orc in orcamentos:
            gasto = next((val for nome, val in cat_rows if nome == (orc.categoria.nome if orc.categoria else "")), 0)
            perc  = (gasto / orc.valor_limite * 100) if orc.valor_limite > 0 else 0
            status = "⚠️ ESTOURADO" if perc >= 100 else (f"{perc:.0f}% usado" if perc > 0 else "sem gastos")
            nome_cat = orc.categoria.nome if orc.categoria else f"ID {orc.categoria_id}"
            orc_linhas.append(
                f"  • {nome_cat}: limite {formatar_moeda(orc.valor_limite)} — {status}"
            )
        orc_txt = "\n".join(orc_linhas) or "  (nenhum orçamento configurado)"

        # Últimas 15 transações
        recentes = (
            db.query(Transacao)
            .order_by(desc(Transacao.data), desc(Transacao.id))
            .limit(15)
            .all()
        )
        trans_lines = []
        for t in recentes:
            cat_nome = t.categoria.nome if t.categoria else "Sem categoria"
            sinal    = "-" if t.tipo == "debito" else "+"
            trans_lines.append(
                f"  {t.data.strftime('%d/%m/%Y')} | {sinal}{formatar_moeda(t.valor):>12} "
                f"| {cat_nome:<20} | {t.descricao}"
            )
        trans_txt = "\n".join(trans_lines) or "  (sem transações cadastradas)"

        # Todas as categorias
        todas_cats = db.query(Categoria).filter(Categoria.ativa == True).all()
        cats_lista = ", ".join(c.nome for c in todas_cats) or "(nenhuma)"

        # Monta texto final
        variacao_desc = _variacao_str(despesas, desp_ant)

        return f"""DATA DE HOJE: {hoje.strftime("%d/%m/%Y")}
PERÍODO DE REFERÊNCIA: {periodo_label(mes, ano)}

══ RESUMO FINANCEIRO DO MÊS ══
  Receitas:  {formatar_moeda(receitas)}
  Despesas:  {formatar_moeda(despesas)}   {variacao_desc}
  Saldo:     {formatar_moeda(saldo)}

  Mês anterior ({periodo_label(m_ant, a_ant)}):
    Receitas anteriores:  {formatar_moeda(rec_ant)}
    Despesas anteriores:  {formatar_moeda(desp_ant)}

══ GASTOS POR CATEGORIA ({periodo_label(mes, ano)}) ══
{cats_txt}

══ ORÇAMENTOS DO MÊS ══
{orc_txt}

══ ÚLTIMAS 15 TRANSAÇÕES ══
{trans_txt}

══ CATEGORIAS CADASTRADAS ══
  {cats_lista}
"""


# --------------------------------------------------
# Utilitário interno
# --------------------------------------------------

def _variacao_str(atual: float, anterior: float) -> str:
    """Retorna string de variação percentual vs mês anterior."""
    if anterior <= 0:
        return ""
    diff = ((atual - anterior) / anterior) * 100
    sinal = "▲" if diff > 0 else "▼"
    return f"({sinal} {abs(diff):.0f}% vs mês anterior)"
