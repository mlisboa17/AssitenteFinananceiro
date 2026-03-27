import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base
from app.models import AprendizadoTipoDocumento
from app.services.classifier_service import ClassifierService


class ClassifierLearningTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.Session()
        self.classifier = ClassifierService(self.db)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_feedback_usuario_prioriza_tipo_confirmado(self):
        texto = (
            "Documento exemplo alpha beta."
            " Linha digitavel 23790 12345 12345 12345."
            " Beneficiario Empresa XPTO."
            " Vencimento 10/04/2026."
        )

        self.classifier.registrar_feedback_tipo_documento(texto, "boleto")
        resultado = self.classifier.classificar_tipo_documento(texto)

        self.assertEqual(resultado["tipo"], "boleto")

    def test_feedback_incrementa_ocorrencias(self):
        texto = (
            "Documento de pagamento recorrente."
            " Linha digitavel 34191 23456 78901 23456."
            " Beneficiario Prestador de Servico ABC."
        )

        self.classifier.registrar_feedback_tipo_documento(texto, "boleto")
        self.classifier.registrar_feedback_tipo_documento(texto, "boleto")

        assinatura = self.classifier._assinatura_aprendizado_documento(texto)
        registro = (
            self.db.query(AprendizadoTipoDocumento)
            .filter(
                AprendizadoTipoDocumento.assinatura == assinatura,
                AprendizadoTipoDocumento.tipo_documento == "boleto",
            )
            .first()
        )

        self.assertIsNotNone(registro)
        self.assertEqual(registro.ocorrencias, 2)

    def test_classifica_fatura_cartao_em_aberto(self):
        texto = (
            "bradesco data: 23/03/2026 - 13:05\n"
            "situacao do extrato: em aberto\n"
            "marcio lima - visa infinite prime\n"
            "xxxx.xxxx.xxxx.7016\n"
            "10/03 saldo anterior usd 0,00 r$ 1.109,89\n"
            "10/03 amazon prime canais r$ 29,90\n"
            "total para: marcio lima\n"
        )

        resultado = self.classifier.classificar_tipo_documento(texto)

        self.assertEqual(resultado["tipo"], "extrato_cartao")

    def test_classifica_fatura_pagbank_com_vencimento_e_linhas_de_compra(self):
        texto = (
            "PagBank\n"
            "Vence em 16/03/2026\n"
            "Cartao Visa Gold\n"
            "11/03 ASSINATURA X R$ 54,90\n"
            "12/03 REEMBOLSO LOJA R$ 20,00\n"
        )

        resultado = self.classifier.classificar_tipo_documento(texto)

        self.assertEqual(resultado["tipo"], "extrato_cartao")


if __name__ == "__main__":
    unittest.main()
