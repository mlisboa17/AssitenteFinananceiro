"""
Processador de áudio/voz para o Assistente Financeiro.

Responsável por:
  1. Receber arquivo de áudio (OGG do Telegram, WAV, MP3...)
  2. Transcrever o áudio para texto (via OpenAI Whisper)
  3. Interpretar o comando de voz
  4. Executar a ação correspondente (ex: registrar despesa)
  5. Retornar confirmação

Para ativar a transcrição:
  1. Instale: pip install openai
  2. Configure OPENAI_API_KEY no arquivo .env
  3. O modelo Whisper da OpenAI será usado automaticamente

Estrutura de classes:
  VoiceProcessor
    ├── transcrever_audio(caminho)     -> str
    ├── interpretar_comando(texto)     -> dict
    └── executar_acao(comando, db)     -> dict
"""

import os
import logging
from datetime import date
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class VoiceProcessor:
    """
    Processador de mensagens de voz para o Assistente Financeiro.

    Status: PREPARADO — requer OpenAI API Key para transcrição real.
    Modo fallback: simula transcrição para testes locais.
    """

    # Formatos de áudio suportados pelo Whisper
    FORMATOS_SUPORTADOS = {".mp3", ".ogg", ".wav", ".m4a", ".webm", ".mp4"}

    def __init__(self):
        self.api_key   = os.getenv("OPENAI_API_KEY", "")
        self._openai_ok = False

        if self.api_key:
            self._inicializar_openai()

    # --------------------------------------------------
    # Inicialização
    # --------------------------------------------------

    def _inicializar_openai(self) -> None:
        """Verifica e configura a conexão com a API da OpenAI."""
        try:
            import openai
            self._openai_ok = True
            logger.info("OpenAI configurada para transcrição de voz.")
        except ImportError:
            logger.warning("openai não instalado. Transcrição desativada (pip install openai).")

    # --------------------------------------------------
    # Transcrição de áudio
    # --------------------------------------------------

    def transcrever_audio(self, caminho_audio: str) -> str:
        """
        Transcreve um arquivo de áudio para texto.

        Usa o modelo Whisper da OpenAI (multilingual, suporta português).
        Em modo offline ou sem chave, retorna aviso automático.

        Args:
            caminho_audio: Caminho do arquivo de áudio

        Returns:
            Texto transcrito ou mensagem de erro
        """
        if not os.path.exists(caminho_audio):
            return f"[Erro] Arquivo de áudio não encontrado: {caminho_audio}"

        sufixo = os.path.splitext(caminho_audio)[1].lower()
        if sufixo not in self.FORMATOS_SUPORTADOS:
            return f"[Erro] Formato não suportado: {sufixo}. Use: {', '.join(self.FORMATOS_SUPORTADOS)}"

        if self._openai_ok and self.api_key:
            return self._transcrever_openai(caminho_audio)

        # Modo fallback (simulação para desenvolvimento)
        logger.warning("OpenAI não configurada. Retornando transcrição simulada.")
        return "[SIMULAÇÃO] Gastei cinquenta reais no mercado"

    def _transcrever_openai(self, caminho_audio: str) -> str:
        """Usa o Whisper via API da OpenAI para transcrição."""
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
            with open(caminho_audio, "rb") as f:
                resultado = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language="pt",       # Força português
                    response_format="text"
                )
            texto = resultado.strip()
            logger.info(f"Áudio transcrito: '{texto}'")
            return texto

        except Exception as e:
            logger.error(f"Erro na transcrição OpenAI: {e}")
            return f"[Erro na transcrição] {str(e)}"

    # --------------------------------------------------
    # Interpretação do comando
    # --------------------------------------------------

    def interpretar_comando(self, texto: str) -> Optional[Dict[str, Any]]:
        """
        Interpreta um texto transcrito como comando financeiro.

        Utiliza o serviço Telegram para reaproveitar a lógica
        de parsing de comandos de despesa.

        Args:
            texto: Texto transcrito do áudio

        Returns:
            Dicionário com dados do comando ou None se não reconhecido
        """
        from app.services.notificacoes.telegram_service import TelegramService

        telegram = TelegramService()
        comando  = telegram.interpretar_comando_despesa(texto)

        if comando:
            logger.info(f"Comando interpretado: {comando}")
        else:
            logger.info(f"Não foi possível interpretar: '{texto}'")

        return comando

    # --------------------------------------------------
    # Execução da ação
    # --------------------------------------------------

    def executar_acao(self, comando: Dict[str, Any], db) -> Dict[str, Any]:
        """
        Executa a ação correspondente ao comando interpretado.

        Args:
            comando: Dicionário com dados do comando
                     (esperado: valor, descricao, data, tipo)
            db:      Sessão do banco de dados SQLAlchemy

        Returns:
            Dicionário com resultado da ação:
              {"sucesso": bool, "mensagem": str, "transacao_id": int | None}
        """
        from app.models import Transacao
        from app.services.classifier_service import ClassifierService

        try:
            classifier = ClassifierService(db)

            transacao = Transacao(
                data      = comando.get("data", date.today()),
                descricao = comando.get("descricao", "Despesa por voz"),
                valor     = float(comando.get("valor", 0)),
                tipo      = comando.get("tipo", "debito"),
                fonte     = "voz",
            )

            # Classifica automaticamente
            categoria = classifier.classificar_e_aplicar(transacao)

            db.add(transacao)
            db.commit()
            db.refresh(transacao)

            from app.utils.helpers import formatar_moeda
            nome_cat = categoria.nome if categoria else "Outros"

            return {
                "sucesso":      True,
                "transacao_id": transacao.id,
                "mensagem":     (
                    f"✅ Despesa registrada: {transacao.descricao} | "
                    f"{formatar_moeda(transacao.valor)} | Categoria: {nome_cat}"
                ),
                "categoria":    nome_cat,
            }

        except Exception as e:
            logger.error(f"Erro ao executar ação de voz: {e}")
            db.rollback()
            return {
                "sucesso":      False,
                "transacao_id": None,
                "mensagem":     f"Erro ao registrar despesa: {str(e)}",
            }

    # --------------------------------------------------
    # Pipeline completo
    # --------------------------------------------------

    def processar_audio(self, caminho_audio: str, db) -> Dict[str, Any]:
        """
        Pipeline completo: áudio -> transcrição -> interpretação -> ação.

        Args:
            caminho_audio: Caminho do arquivo de áudio
            db:            Sessão do banco de dados

        Returns:
            Resultado final da ação executada
        """
        texto   = self.transcrever_audio(caminho_audio)

        if texto.startswith("[Erro"):
            return {"sucesso": False, "mensagem": texto, "transcricao": texto}

        comando = self.interpretar_comando(texto)

        if not comando:
            return {
                "sucesso":     False,
                "mensagem":    f"Não entendi o comando: '{texto}'. Tente: 'Gastei 50 gasolina'",
                "transcricao": texto,
            }

        resultado = self.executar_acao(comando, db)
        resultado["transcricao"] = texto
        return resultado
