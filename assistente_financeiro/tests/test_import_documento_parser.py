import sys
import unittest
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base
from app.models import ContaBancaria, CartaoCredito, EventoFinanceiro, FormaPagamento, StatusEvento, TipoEvento, Transacao
from app.services.classifier_service import ClassifierService
from app.services.agenda_service import quitar_evento
from app.services.import_service import ImportService


class ImportDocumentoParserTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.Session()
        self.classifier = ClassifierService(self.db)
        self.import_service = ImportService(self.db)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_classifica_comprovante_pix_em_vez_de_extrato(self):
        texto = (
            "Comprovante de pagamento Pix\n"
            "22/03/2026 as 21:45:25\n"
            "Valor do pagamento R$ 87,98\n"
            "Tipo de transferencia Pix\n"
            "Codigo da transacao Pix E08561701202603230045TP90JW06FKDZ\n"
        )

        resultado = self.classifier.classificar_tipo_documento(texto)

        self.assertEqual(resultado["tipo"], "comprovante_pagamento_bancario")

    def test_extrai_valor_de_comprovante_pix(self):
        texto = (
            "Comprovante de pagamento Pix\n"
            "Valor do pagamento R$ 87,98\n"
            "Codigo da transacao Pix E08561701202603230045TP90JW06FKDZ\n"
        )

        valor = self.import_service._extrair_valor_documento(texto)

        self.assertEqual(valor, 87.98)

    def test_extrai_valor_a_pagar_e_ignora_troco(self):
        texto = (
            "Documento Auxiliar da Nota Fiscal de Consumidor Eletronica\n"
            "Valor a Pagar R$ 88,89\n"
            "Forma Pagamento Dinheiro 90,00\n"
            "Troco R$ 1,11\n"
        )

        valor = self.import_service._extrair_valor_documento(texto)

        self.assertEqual(valor, 88.89)

    def test_nota_fiscal_prefere_valor_total_ao_valor_pago(self):
        texto = (
            "Documento Auxiliar da Nota Fiscal de Consumidor Eletronica\n"
            "Valor pago R$ 18,00\n"
            "Valor total R$ 22,50\n"
            "Desconto R$ 4,50\n"
        )

        valor = self.import_service._extrair_valor_documento(texto, tipo_documento="nota_fiscal")

        self.assertEqual(valor, 22.50)

    def test_nota_fiscal_ler_documento_inteiro_para_achar_total(self):
        texto = (
            "DANFE NFC-e\n"
            "MERCADO BOA COMPRA LTDA\n"
            "item 1 arroz 10,00\n"
            "item 2 feijao 12,00\n"
            "valor pago 20,00\n"
            "desconto 2,00\n"
            "VALOR TOTAL R$ 22,00\n"
            "troco 0,00\n"
        )

        valor = self.import_service._extrair_valor_documento(texto, tipo_documento="nota_fiscal")

        self.assertEqual(valor, 22.00)

    def test_nota_fiscal_sugere_categoria_a_partir_do_texto_completo(self):
        texto = (
            "DANFE NFC-e\n"
            "DROGARIA CENTRAL LTDA\n"
            "vitamina c 25,00\n"
            "dipirona 12,00\n"
            "valor total 37,00\n"
        )

        previa = self.import_service.montar_previa_documento(texto, "nota_fiscal")

        self.assertEqual(previa["valor"], 37.00)
        self.assertEqual(previa["categoria_sugerida"], "Saúde")

    def test_boleto_importado_cria_evento_pendente_com_conta(self):
        conta = ContaBancaria(nome="Conta Principal", banco="Itaú")
        self.db.add(conta)
        self.db.commit()
        self.db.refresh(conta)

        texto_boleto = (
            "BANCO XYZ\n"
            "Pagável em qualquer banco até o vencimento\n"
            "Beneficiário: Escola Exemplo LTDA\n"
            "Vencimento 15/04/2026\n"
            "Valor do documento R$ 250,00\n"
            "Linha digitável 34191.79001 01043.510047 91020.150008 9 12340000025000\n"
        )
        self.import_service.ocr.extrair_texto = lambda *args, **kwargs: texto_boleto

        resultado = self.import_service.importar_por_tipo_documento(
            caminho="boleto.pdf",
            tipo_documento="boleto",
            conta_id=conta.id,
        )

        evento = self.db.query(EventoFinanceiro).filter(EventoFinanceiro.id == resultado["evento_id"]).first()
        self.assertIsNotNone(evento)
        self.assertEqual(evento.conta_id, conta.id)
        self.assertEqual(evento.status, StatusEvento.PENDENTE)

    def test_comprovante_quita_boleto_e_gera_despesa(self):
        conta = ContaBancaria(nome="Conta Principal", banco="Itaú")
        self.db.add(conta)
        self.db.commit()
        self.db.refresh(conta)

        boleto = EventoFinanceiro(
            titulo="Escola Exemplo LTDA",
            valor=250.00,
            data_vencimento=date(2026, 4, 15),
            tipo=TipoEvento.CONTA,
            status=StatusEvento.PENDENTE,
            codigo_barras="34191790010104351004791020150008912340000025000",
            conta_id=conta.id,
        )
        self.db.add(boleto)
        self.db.commit()
        self.db.refresh(boleto)

        texto_comprovante = (
            "Comprovante de pagamento\n"
            "Valor do pagamento R$ 250,00\n"
            "Favorecido Escola Exemplo LTDA\n"
        )
        self.import_service.ocr.extrair_texto = lambda *args, **kwargs: texto_comprovante

        resultado = self.import_service.importar_por_tipo_documento(
            caminho="comprovante.pdf",
            tipo_documento="comprovante_pagamento_bancario",
            conta_id=conta.id,
        )

        evento = self.db.query(EventoFinanceiro).filter(EventoFinanceiro.id == boleto.id).first()
        transacao = self.db.query(Transacao).filter(Transacao.id == evento.transacao_id).first()

        self.assertEqual(resultado["tipo"], "quitacao_evento")
        self.assertEqual(evento.status, StatusEvento.PAGO)
        self.assertIsNotNone(transacao)
        self.assertEqual(transacao.forma_pagamento, FormaPagamento.BOLETO_CONTA)
        self.assertEqual(transacao.conta_id, conta.id)

    def test_quitar_fatura_cartao_nao_duplica_despesa(self):
        cartao = CartaoCredito(nome="Nubank", bandeira="Mastercard")
        self.db.add(cartao)
        self.db.commit()
        self.db.refresh(cartao)

        evento = EventoFinanceiro(
            titulo="Fatura Nubank",
            valor=800.00,
            data_vencimento=date(2026, 4, 20),
            tipo=TipoEvento.FATURA_CARTAO,
            status=StatusEvento.PENDENTE,
            cartao_id=cartao.id,
        )
        self.db.add(evento)
        self.db.commit()
        self.db.refresh(evento)

        evento_pago = quitar_evento(self.db, evento.id, conta_id=None)

        self.assertEqual(evento_pago.status, StatusEvento.PAGO)
        self.assertIsNone(evento_pago.transacao_id)

    def test_importacao_fatura_cartao_mantem_data_da_compra_e_cria_evento(self):
        cartao = CartaoCredito(nome="Nubank", bandeira="Mastercard", dia_vencimento=10)
        self.db.add(cartao)
        self.db.commit()
        self.db.refresh(cartao)

        resultado = self.import_service._salvar_transacoes(
            [
                {"data": date(2026, 3, 5), "descricao": "Mercado", "valor": 120.0, "tipo": "debito", "fonte": "Nubank"},
                {"data": date(2026, 3, 7), "descricao": "Farmácia", "valor": 50.0, "tipo": "debito", "fonte": "Nubank"},
            ],
            arquivo_nome="fatura_marco.pdf",
            arquivo_path="fatura_marco.pdf",
            tipo="cartao",
            banco="Nubank",
            cartao_id=cartao.id,
        )

        transacoes = self.db.query(Transacao).order_by(Transacao.data.asc()).all()
        evento = self.db.query(EventoFinanceiro).filter(EventoFinanceiro.id == resultado["evento_fatura_id"]).first()

        self.assertEqual(transacoes[0].data, date(2026, 3, 5))
        self.assertEqual(transacoes[0].forma_pagamento, FormaPagamento.CARTAO_CREDITO)
        self.assertIsNotNone(evento)
        self.assertEqual(evento.tipo, TipoEvento.FATURA_CARTAO)


if __name__ == "__main__":
    unittest.main()
