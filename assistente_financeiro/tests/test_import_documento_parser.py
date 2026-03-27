import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base
from app.services.classifier_service import ClassifierService
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


if __name__ == "__main__":
    unittest.main()
