import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import ocr_service as ocr_module
from app.services.ocr_service import OCRService


class OCRServiceTests(unittest.TestCase):
    def _build_service(self):
        service = OCRService.__new__(OCRService)
        service.lang = "por"
        return service

    def test_extrair_texto_ocr_faz_fallback_para_fitz_quando_pdf2image_falha(self):
        service = self._build_service()
        fake_tesseract = SimpleNamespace(
            image_to_string=Mock(side_effect=["texto pagina 1", "texto pagina 2"])
        )

        with (
            patch.object(ocr_module, "PYTESSERACT_OK", True),
            patch.object(ocr_module, "PDF2IMAGE_OK", True),
            patch.object(
                ocr_module,
                "convert_from_path",
                side_effect=RuntimeError("poppler ausente"),
            ),
            patch.object(
                service,
                "_renderizar_paginas_pdf_com_fitz",
                return_value=["pagina-1", "pagina-2"],
            ) as renderizar_mock,
            patch.object(
                service,
                "_preprocessar_imagem",
                side_effect=lambda imagem: f"prep-{imagem}",
            ) as preprocessar_mock,
            patch.object(ocr_module, "pytesseract", fake_tesseract, create=True),
        ):
            texto = service._extrair_texto_ocr("arquivo.pdf", senha="1234")

        self.assertEqual(texto, "texto pagina 1\ntexto pagina 2")
        renderizar_mock.assert_called_once_with("arquivo.pdf", senha="1234")
        self.assertEqual(preprocessar_mock.call_count, 2)
        fake_tesseract.image_to_string.assert_any_call("prep-pagina-1", lang="por")
        fake_tesseract.image_to_string.assert_any_call("prep-pagina-2", lang="por")

    def test_extrair_texto_ocr_lanca_erro_quando_nao_consegue_rasterizar(self):
        service = self._build_service()

        with (
            patch.object(ocr_module, "PYTESSERACT_OK", True),
            patch.object(ocr_module, "PDF2IMAGE_OK", True),
            patch.object(
                ocr_module,
                "convert_from_path",
                side_effect=RuntimeError("poppler ausente"),
            ),
            patch.object(
                service,
                "_renderizar_paginas_pdf_com_fitz",
                return_value=[],
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "Não foi possível rasterizar o PDF"):
                service._extrair_texto_ocr("arquivo.pdf")


if __name__ == "__main__":
    unittest.main()