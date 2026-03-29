"""
Processador de áudio/voz para o Assistente Financeiro.

Responsável por:
  1. Receber arquivo de áudio (OGG do Telegram, WAV, MP3...)
    2. Transcrever o áudio para texto (via Whisper local gratuito)
  3. Interpretar o comando de voz
  4. Executar a ação correspondente (ex: registrar despesa)
  5. Retornar confirmação

Para ativar a transcrição:
    1. Instale: pip install faster-whisper
    2. Configure VOICE_MODEL_SIZE no arquivo .env (padrão: tiny)
    3. O modelo Whisper local será usado automaticamente (sem API paga)

Estrutura de classes:
  VoiceProcessor
    ├── transcrever_audio(caminho)     -> str
    ├── interpretar_comando(texto)     -> dict
    └── executar_acao(comando, db)     -> dict
"""

import os
import re
import logging
from datetime import date
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


class VoiceProcessor:
    """
    Processador de mensagens de voz para o Assistente Financeiro.

    Status: PRONTO — usa transcrição local gratuita com Faster-Whisper.
    """

    # Formatos de áudio suportados pelo Whisper local.
    FORMATOS_SUPORTADOS = {".mp3", ".ogg", ".wav", ".m4a", ".webm", ".mp4"}

    def __init__(self):
        self.engine = "faster-whisper"
        self.primary_model = os.getenv("VOICE_MODEL_PRIMARY", "small").strip() or "small"
        self.reserve_model = os.getenv("VOICE_MODEL_RESERVE", "tiny").strip() or "tiny"
        self.luxury_model = os.getenv("VOICE_MODEL_LUXURY", "large-v3").strip() or "large-v3"
        self.device = os.getenv("VOICE_DEVICE", "auto").strip() or "auto"
        self.compute_type = os.getenv("VOICE_COMPUTE_TYPE", "int8").strip() or "int8"
        self.min_text_chars = int(os.getenv("VOICE_MIN_TEXT_CHARS", "6"))
        self._whisper_ok = False
        self._whisper_models: Dict[str, Any] = {}
        self._config_msg = ""
        self._last_model_used = ""
        self.model_chain = self._build_model_chain()

        self._inicializar_local_whisper()

    def _build_model_chain(self) -> List[str]:
        chain = [self.primary_model, self.reserve_model, self.luxury_model]
        dedup: List[str] = []
        for model in chain:
            model_norm = (model or "").strip()
            if model_norm and model_norm not in dedup:
                dedup.append(model_norm)
        return dedup

    # --------------------------------------------------
    # Inicialização
    # --------------------------------------------------

    def _inicializar_local_whisper(self) -> None:
        """Verifica se o motor local gratuito está disponível."""
        try:
            from faster_whisper import WhisperModel  # noqa: F401
            self._whisper_ok = True
            logger.info("Transcrição local configurada com Faster-Whisper.")
        except ImportError:
            self._config_msg = (
                "Pacote faster-whisper não instalado. "
                "Execute: pip install faster-whisper"
            )
            logger.warning("faster-whisper não instalado. Transcrição de voz indisponível.")

    def diagnostico(self) -> Dict[str, Any]:
        """Retorna o estado do serviço de voz local."""
        if self._whisper_ok:
            return {
                "ok": True,
                "engine": self.engine,
                "model": self._last_model_used or self.primary_model,
                "modelos": self.model_chain,
                "mensagem": (
                    "Voz local gratuita ativa "
                    f"({self.engine}, cadeia: {', '.join(self.model_chain)})."
                ),
            }
        return {
            "ok": False,
            "engine": self.engine,
            "model": self.primary_model,
            "modelos": self.model_chain,
            "mensagem": self._config_msg or "Voz local indisponível.",
        }

    # --------------------------------------------------
    # Transcrição de áudio
    # --------------------------------------------------

    def transcrever_audio(self, caminho_audio: str) -> str:
        """
        Transcreve um arquivo de áudio para texto.

        Usa o modelo Whisper local (multilingual, suporta português).

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

        if self._whisper_ok:
            return self._transcrever_local_whisper(caminho_audio)

        logger.warning("Voz local indisponível. %s", self._config_msg)
        return f"[Erro na transcrição] {self._config_msg or 'Serviço de voz não configurado.'}"

    def _transcrever_local_whisper(self, caminho_audio: str) -> str:
        """Usa Whisper local gratuito (faster-whisper) para transcrição."""
        erros: List[Tuple[str, str]] = []
        melhor_texto = ""

        for model_name in self.model_chain:
            texto, erro = self._transcrever_com_modelo(caminho_audio, model_name)
            if erro:
                erros.append((model_name, erro))
                continue

            if texto and self._texto_transcricao_aceitavel(texto):
                self._last_model_used = model_name
                logger.info("Áudio transcrito com modelo '%s': '%s'", model_name, texto)
                return texto

            if texto and len(texto) > len(melhor_texto):
                melhor_texto = texto

        if melhor_texto:
            return melhor_texto

        if erros:
            resumo = "; ".join([f"{m}: {e}" for m, e in erros[:2]])
            return f"[Erro na transcrição] Falha nos modelos locais ({resumo})"
        return "[Erro na transcrição] Nenhum texto reconhecido no áudio."

    def _transcrever_com_modelo(self, caminho_audio: str, model_name: str) -> Tuple[str, str]:
        try:
            from faster_whisper import WhisperModel

            model = self._whisper_models.get(model_name)
            if model is None:
                model = WhisperModel(
                    model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                )
                self._whisper_models[model_name] = model

            segments, _info = model.transcribe(
                caminho_audio,
                language="pt",
                beam_size=1,
                vad_filter=True,
            )
            texto = " ".join((seg.text or "").strip() for seg in segments).strip()
            return texto, ""

        except Exception as e:
            logger.warning("Erro na transcrição local com modelo '%s': %s", model_name, e)
            return "", str(e)

    def _texto_transcricao_aceitavel(self, texto: str) -> bool:
        txt = (texto or "").strip()
        if len(txt) < self.min_text_chars:
            return False
        if not re.search(r"[a-zA-ZÀ-ÿ]", txt):
            return False
        return True

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
