import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.parser_service import ParserService


class ParserServiceCartaoTests(unittest.TestCase):
    def setUp(self):
        self.parser = ParserService()

    def test_parse_bradesco_fatura_detecta_credito_e_debito(self):
        texto = """
        Bradesco Cartoes
        10/02 PAGTO. POR DEB EM C/C 1.705,56-
        26/02 ENCARGOS DE ROTATIVO 183,55
        """

        transacoes = self.parser.parsear_texto(texto, tipo_extrato="cartao")

        self.assertEqual(len(transacoes), 2)
        self.assertEqual(transacoes[0]["tipo"], "credito")
        self.assertEqual(transacoes[1]["tipo"], "debito")

    def test_parse_cartao_generico_com_data_completa(self):
        texto = """
        Itaucard Platinum
        Vencimento: 10/03/2026
        28/02/2026 MERCADO CENTRAL 123,45
        03/03/2026 PAGAMENTO RECEBIDO 123,45
        """

        transacoes = self.parser.parsear_texto(texto, tipo_extrato="cartao")

        self.assertEqual(len(transacoes), 2)
        self.assertEqual(transacoes[0]["descricao"], "mercado central")
        self.assertEqual(transacoes[0]["tipo"], "debito")
        self.assertEqual(transacoes[1]["tipo"], "credito")

    def test_parse_cartao_generico_com_mes_texto_e_rs(self):
        texto = """
        XP Visa Infinite
        Vence em 10/03/2026
        18 fev Restaurante Central R$ 89,90
        20 fev Streaming Premium R$ 39,90
        03 mar Pagamento fatura R$ 129,80
        """

        transacoes = self.parser.parsear_texto(texto, tipo_extrato="cartao")

        self.assertEqual(len(transacoes), 3)
        self.assertEqual(transacoes[0]["data"].year, 2026)
        self.assertEqual(transacoes[0]["data"].month, 2)
        self.assertEqual(transacoes[2]["tipo"], "credito")

    def test_parse_pagbank_generico(self):
        texto = """
        PagBank
        Vence em 16/03/2026
        11/03 ASSINATURA X R$ 54,90
        12/03 REEMBOLSO LOJA R$ 20,00
        """

        transacoes = self.parser.parsear_texto(texto, tipo_extrato="cartao")

        self.assertEqual(len(transacoes), 2)
        self.assertEqual(transacoes[0]["tipo"], "debito")
        self.assertEqual(transacoes[1]["tipo"], "credito")

    def test_parse_pagbank_ocr_com_linhas_quebradas(self):
        texto = """
        PagBank
        Vence em 16/03/2026
        11/03 ASSINATURA X
        R$ 54,90
        12/03 REEMBOLSO LOJA
        R$ 20,00
        """

        transacoes = self.parser.parsear_texto(texto, tipo_extrato="cartao")

        self.assertEqual(len(transacoes), 2)
        self.assertEqual(transacoes[0]["descricao"], "assinatura x")
        self.assertEqual(transacoes[0]["tipo"], "debito")
        self.assertEqual(transacoes[1]["tipo"], "credito")

    def test_parse_c6_fatura_ajusta_ano_por_ciclo_e_preserva_parcela(self):
        texto = """
        C6 Bank
        Fechamento 20/04/26
        Vencimento: 01 de Maio
        04 jul CURSO INGLES - Parcela 10/12 300,00
        """

        transacoes = self.parser.parsear_texto(texto, tipo_extrato="cartao")

        self.assertEqual(len(transacoes), 1)
        self.assertEqual(transacoes[0]["data"].year, 2025)
        self.assertEqual(transacoes[0]["data"].month, 7)
        self.assertEqual(transacoes[0]["parcela_atual"], 10)
        self.assertEqual(transacoes[0]["parcelas_total"], 12)

    def test_parse_mercado_pago_mantem_secao_credito_e_debito(self):
        texto = """
        Mercado Pago
        Vence em 16/03/2026
        Movimentacoes na fatura
        18/02 Pagamento da fatura de fevereiro/2026 R$ 904,55
        Cartao Visa Gold
        20/02 Restaurante da Praia R$ 84,90
        """

        transacoes = self.parser.parsear_texto(texto, tipo_extrato="cartao")

        self.assertEqual(len(transacoes), 2)
        self.assertEqual(transacoes[0]["tipo"], "credito")
        self.assertEqual(transacoes[1]["tipo"], "debito")


if __name__ == "__main__":
    unittest.main()