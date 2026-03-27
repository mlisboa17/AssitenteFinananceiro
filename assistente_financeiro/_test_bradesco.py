import sys
sys.path.insert(0, '.')
from app.services.ocr_service import OCRService
from app.services.parser_service import ParserService

ocr = OCRService()
pdf = r'C:\Users\mlisb\Downloads\BradescoCartoes2026-03-23.125410.pdf'
texto = ocr.extrair_texto_pdf(pdf)
parser = ParserService()
transacoes = parser.parsear_texto(texto, tipo_extrato='cartao')
print('Total encontradas:', len(transacoes))
for t in transacoes:
    sinal = '+' if t['tipo'] == 'credito' else '-'
    print('  %s  %sR$ %.2f  %-8s  %s' % (t['data'], sinal, t['valor'], t['tipo'], t['descricao']))
