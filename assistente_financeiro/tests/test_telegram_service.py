import os
import sys
import unittest
import asyncio
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.notificacoes.telegram_service import TelegramService
from app.main import _mensagem_confirmacao_documento_pendente, _processar_pendencia_documento_telegram


class TelegramServiceTests(unittest.TestCase):
    def setUp(self):
        self._old_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self._old_chat = os.environ.get("TELEGRAM_CHAT_ID")
        os.environ["TELEGRAM_BOT_TOKEN"] = ""
        os.environ["TELEGRAM_CHAT_ID"] = ""
        self.svc = TelegramService()

    def tearDown(self):
        if self._old_token is None:
            os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        else:
            os.environ["TELEGRAM_BOT_TOKEN"] = self._old_token

        if self._old_chat is None:
            os.environ.pop("TELEGRAM_CHAT_ID", None)
        else:
            os.environ["TELEGRAM_CHAT_ID"] = self._old_chat

    def test_aceita_descricao_valor(self):
        cmd = self.svc.interpretar_comando_despesa("RESTAURANTE 50")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd["valor"], 50.0)
        self.assertEqual(cmd["descricao"].lower(), "restaurante")

    def test_aceita_valor_descricao(self):
        cmd = self.svc.interpretar_comando_despesa("50 GASOLINA")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd["valor"], 50.0)
        self.assertEqual(cmd["descricao"].lower(), "gasolina")

    def test_aceita_separador_dois_pontos(self):
        cmd = self.svc.interpretar_comando_despesa("gasolina: 80,50")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd["valor"], 80.50)
        self.assertEqual(cmd["descricao"].lower(), "gasolina")

    def test_aceita_verbo_com_preposicao(self):
        cmd = self.svc.interpretar_comando_despesa("gastei 35 em restaurante")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd["valor"], 35.0)
        self.assertEqual(cmd["descricao"].lower(), "restaurante")

    def test_aceita_valor_com_milhar(self):
        cmd = self.svc.interpretar_comando_despesa("aluguel 1.234,56")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd["valor"], 1234.56)
        self.assertEqual(cmd["descricao"].lower(), "aluguel")

    def test_rejeita_texto_sem_valor(self):
        cmd = self.svc.interpretar_comando_despesa("restaurante")
        self.assertIsNone(cmd)

    def test_data_opcional_ontem(self):
        cmd = self.svc.interpretar_comando_despesa("50 uber ontem")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd["valor"], 50.0)
        self.assertEqual(cmd["descricao"].lower(), "uber")
        self.assertEqual(cmd["data"], date.today() - timedelta(days=1))

    def test_data_opcional_data_completa(self):
        cmd = self.svc.interpretar_comando_despesa("restaurante 120 em 24/03/2026")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd["valor"], 120.0)
        self.assertEqual(cmd["descricao"].lower(), "restaurante")
        self.assertEqual(cmd["data"].strftime("%d/%m/%Y"), "24/03/2026")

    def test_mensagem_ajuda_contem_exemplos(self):
        ajuda = self.svc.mensagem_ajuda_despesa().lower()
        self.assertIn("restaurante 50", ajuda)
        self.assertIn("50 gasolina", ajuda)
        self.assertIn("ontem", ajuda)

    def test_mensagem_invalida_orienta_formato(self):
        msg = self.svc.mensagem_formato_invalido().lower()
        self.assertIn("descrição e valor", msg)
        self.assertIn("50 gasolina", msg)

    def test_confirmacao_documento_indica_ok_e_numero(self):
        msg = _mensagem_confirmacao_documento_pendente(
            {
                "tipo_documento": "nota_fiscal",
                "analise": {
                    "arquivo_nome": "compra.jpg",
                    "nome_tipo": "Nota Fiscal de Despesa",
                    "confianca": "alta",
                    "tipo_detectado": "nota_fiscal",
                    "pre_lancamento": {
                        "valor": 22.5,
                        "descricao": "Mercado XPTO",
                        "categoria_sugerida": "Alimentação",
                    },
                },
            }
        ).lower()

        self.assertIn("toque em ok", msg)
        self.assertIn("digite apenas o número", msg)

    def test_pendencia_documento_aceita_numero_para_alterar_tipo(self):
        class LoopStub:
            def run_until_complete(self, coro):
                return asyncio.run(coro)

        class SvcStub:
            def __init__(self):
                self.mensagens = []

            async def enviar_mensagem(self, texto, chat_id=None, botoes=None):
                self.mensagens.append({"texto": texto, "chat_id": chat_id, "botoes": botoes})
                return True

        svc = SvcStub()
        pendencia = {
            "caminho": "arquivo.pdf",
            "tipo_documento": "nota_fiscal",
            "analise": {
                "arquivo_nome": "arquivo.pdf",
                "nome_tipo": "Nota Fiscal de Despesa",
                "confianca": "alta",
                "tipo_detectado": "nota_fiscal",
                "pre_lancamento": {},
            },
        }

        _processar_pendencia_documento_telegram(svc, "123", "7", LoopStub(), pendencia)

        self.assertEqual(pendencia["tipo_documento"], "extrato_cartao")
        self.assertEqual(svc.mensagens[-1]["botoes"], [["OK"]])


if __name__ == "__main__":
    unittest.main()
