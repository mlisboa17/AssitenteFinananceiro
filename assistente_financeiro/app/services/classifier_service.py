"""
Serviço de classificação automática de transações financeiras.

Utiliza correspondência por palavras-chave para categorizar gastos,
com fallback baseado no histórico de transações similares já categorizadas.

Categorias suportadas:
  Alimentação, Restaurante, Transporte, Saúde, Educação, Lazer,
  Vestuário, Casa, Telecomunicações, Investimento, Serviços, Pets, Outros
"""

import logging
import hashlib
import re
from collections import Counter
from typing import Optional, Dict, List

from sqlalchemy.orm import Session

from app.models import Categoria, Transacao, AprendizadoTipoDocumento
from app.utils.helpers import normalizar_descricao

logger = logging.getLogger(__name__)


class ClassifierService:
    """
    Serviço de classificação automática de transações.

    Estratégias (em ordem de prioridade):
      1. Correspondência por palavras-chave pré-definidas
      2. Aprendizado por histórico (transações similares já categorizadas)
      3. Fallback para categoria "Outros"
    """

    # --------------------------------------------------
    # Dicionário de palavras-chave por categoria
    # --------------------------------------------------
    PALAVRAS_CHAVE: Dict[str, List[str]] = {
        "Alimentação": [
            "mercado", "supermercado", "padaria", "acougue", "açougue",
            "hortifruti", "mercearia", "sacolão", "sacolao", "feira",
            "empório", "emporio", "conveniência", "conveniencia",
            "pao de acucar", "carrefour", "extra", "atacadão", "atacadao",
            "makro", "assai", "atacarejo", "cesta basica", "prezunic",
            "walm", "st marche", "zona sul", "coop", "natural",
            "panificadora", "confeitaria", "quitanda", "mini mercado",
            "bistek", "savegnago", "tauste", "sonda", "oba hortifruti",
        ],
        "Restaurante": [
            "restaurante", "lanchonete", "pizzaria", "sushi", "churrascaria",
            "hamburger", "hamburguer", "mcdonalds", "mc donalds", "burger king",
            "subway", "bobs", "giraffas", "outback", "ifood", "rappi",
            "uber eats", "ubereats", "delivery", "bar ", "boteco",
            "quilo", "prato feito", "marmita", "sorveteria", "açaí", "acai",
            "café", "cafe", "coffee", "pastelaria", "lanche", "pizz",
            "sushiloko", "china in box", "spoleto", "coco bambu", "bk ",
            "five guys", "chili's", "madero", "dominos", "pizza hut",
            "habibs", "bob's", "jeronimo", "poke", "crepe", "tapioca",
            "boulangerie", "croissanterie",
            "belmonte", "tao lanchonete", "zig ", "zig*", "pato praia",
            "hondarribia", "empada", "quiosque", "buffet",
        ],
        "Transporte": [
            "uber", "99 taxi", "99taxi", "cabify", "táxi", "taxi",
            "combustível", "combustivel", "gasolina", "etanol", "diesel",
            "posto ", "shell", "ipiranga", "petrobras", "br distribuidora",
            "estacionamento", "parking", "zona azul", "pedágio", "pedagio",
            "bilhete único", "bilhete unico", "metrô", "metro", "ônibus",
            "onibus", "trem", "passagem", "latam", "gol ", "azul ",
            "intermunicipal", "rodoviária", "rodoviaria", "buser",
            "clickbus", "localiza", "movida", "unidas", "hertz", "aluguel carro",
            "detran", "ipva", "despachante", "inmetro", "vistoria",
        ],
        "Saúde": [
            "farmácia", "farmacia", "drogaria", "ultrafarma", "droga raia",
            "pacheco", "pague menos", "nissei", "médico", "medico",
            "hospital", "clínica", "clinica", "dentista", "odontologia",
            "laboratorio", "laboratório", "exame", "consulta", "cirurgia",
            "plano de saúde", "plano de saude", "unimed", "amil",
            "fisioterapia", "psicologia", "psiquiatra", "nutricionista",
            "sempre tem", "drogasil", "drogasmil", "panvel", "raia", "bifarma",
            "droga mais", "farmanguinhos", "veterinary", "petlove saude",
            "rdsaude", "rd saude", "ultrafarma",
            "telemedicina", "dr. consulta", "einstein", "hcor", "fleury",
            "hermes pardini", "dasa", "sabin",
        ],
        "Educação": [
            "escola", "faculdade", "universidade", "curso", "mensalidade",
            "matrícula", "matricula", "material escolar", "livro", "livraria",
            "udemy", "coursera", "alura", "descomplica", "cultura inglesa",
            "wizard", "fisk", "english", "idiomas", "tutoria", "formação",
            "skillshare", "duolingo", "babbel", "rosetta", "brit",
            "saraiva", "cultura", "amazon kindle", "kindle", "fnac",
            "pearson", "cengage", "estácio", "anhanguera", "kroton",
        ],
        "Lazer": [
            "netflix", "amazon prime", "disney+", "disney plus", "hbo max", "hbomax",
            "spotify", "deezer", "apple music", "youtube premium",
            "cinema", "teatro", "show", "ingresso", "ticket",
            "parque", "museu", "zoo", "futebol", "academia", "gym",
            "crossfit", "yoga", "pilates", "piscina", "game", "jogos",
            "steam", "playstation", "xbox", "clube", "ingresso",
            "paramount+", "globoplay", "mubi", "apple tv", "crunchyroll",
            "telecine", "now ", "claro video", "star+", "star plus",
            "lol", "valorant", "roblox", "epic games", "nuuvem",
            "imax", "cinemark", "kinoplex", "flix", "uci cinema",
            "bowling", "laser tag", "escape room", "karting",
            "prime video", "google play", "google prime",
            "ingresso.com", "trem do cor", "tremdocor",
            "eventbrite", "sympla", "blueticket",
            "ibis", "hotel", "pousada", "hostel", "windsor", "miramar",
            "sheraton", "hilton", "marriott", "novotel", "air bnb", "airbnb",
        ],
        "Vestuário": [
            "roupa", "roupas", "calçado", "calcado", "sapato", "tênis",
            "tenis", "sandália", "sandalia", "bolsa", "acessório",
            "acessorio", "renner", "c&a", "cea", "riachuelo", "marisa",
            "zara", "hering", "levis", "lojas americanas", "americanas",
            "netshoes", "dafiti", "shein", "brooksfield", "officer",
            "reserva", "forum", "colcci", "dudalina", "aramis", "ellus",
            "farm ", "animale", "shoulder", "ri happy", "artigos esport",
            "moda", "fashion", "outlet", "brechó", "brechó", "brecho",
            "lingerie", "underwear", "meias", "cueca", "sutiã",
        ],
        "Casa": [
            "aluguel", "condomínio", "condominio", "iptu", "energia elétrica",
            "energia eletrica", "luz ", "água", "agua ", "esgoto", "gás",
            "gas ", "manutenção", "manutencao", "ferragem", "leroy merlin",
            "telhanorte", "madeireira", "pintura", "encanador", "eletricista",
            "portaria", "mobília", "mobilia", "sofá", "sofa",
            "tok&stok", "tok stok", "etna", "camicado", "casa show",
            "sodimac", "brasil gas", "comgas", "sabesp", "copasa", "cedae",
            "caesb", "cosan gás", "neoenergia", "enel", "cemig", "cpfl",
            "coelce", "elektro", "energisa", "light ",
            "casas bahia", "magazine luiza", "americanas eletro",
            "fast shop", "ponto frio",
        ],
        "Telecomunicações": [
            "celular", "tim ", "vivo", "claro ", "oi ", "internet",
            "fibra", "banda larga", "wi-fi", "wifi", "recarga", "telefonia",
            "net claro", "sky ", "oi tv", "embratel", "nextel",
            "apple one", "microsoft 365", "google workspace", "google one",
            "icloud", "dropbox", "one drive", "onedrive",
        ],
        "Investimento": [
            "investimento", "tesouro direto", "fundo", "cdb", "lci", "lca",
            "debenture", "previdência", "previdencia", "poupança", "poupanca",
            "corretora", "xp ", "clear ", "rico ", "btg", "itaú invest",
            "dividendo", "dividends", "rendimento", "modal mais", "ágora",
            "agora invest", "warren", "nu invest", "genial invest",
            "easynvest", "toro ", "fracional", "fii ", "acao ", "acoes",
        ],
        "Serviços": [
            "seguro", "assistência", "assistencia", "corte de cabelo",
            "salão", "salao", "barbearia", "manicure", "pedicure",
            "lavanderia", "limpeza", "faxina", "cartório", "cartorio",
            "notário", "notario", "tabelião", "tabeliao", "registro",
            "contador", "advocacia", "advogado", "jurídico", "juridico",
            "99freelas", "workana", "rapido", "getninjas", "diary",
            "impostômetro", "dentista", "ortodontia", "implante",
            "auto escola", "autoescola", "despachante",
            "correios", "jadlog", "total express", "loggi", "azul cargo",
        ],
        "Pets": [
            "petshop", "pet shop", "veterinário", "veterinario",
            "ração", "racao", "pet ", "canil", "animal",
            "agropet", "petz", "cobasi", "petlove", "auau",
            "mundo animal", "banho e tosa", "tosa ",
        ],
    }

    def __init__(self, db: Session):
        """
        Inicializa o classificador.

        Args:
            db: Sessão do banco de dados (para aprendizado por histórico)
        """
        self.db = db

    # --------------------------------------------------
    # Interface pública
    # --------------------------------------------------

    def classificar(self, descricao: str) -> str:
        """
        Classifica uma transação pela sua descrição.

        Args:
            descricao: Texto da transação

        Returns:
            Nome da categoria identificada (ou "Outros")
        """
        if not descricao:
            return "Outros"

        desc_norm = normalizar_descricao(descricao)

        # 1. Por palavras-chave
        for categoria, palavras in self.PALAVRAS_CHAVE.items():
            for palavra in palavras:
                if palavra in desc_norm:
                    return categoria

        # 2. Por histórico
        historico = self._classificar_por_historico(desc_norm)
        if historico:
            return historico

        return "Outros"

    def classificar_e_aplicar(self, transacao: Transacao) -> Optional[Categoria]:
        """
        Classifica a transação e atribui a categoria no objeto ORM.

        Args:
            transacao: Objeto de transação a ser categorizado

        Returns:
            Objeto Categoria atribuído
        """
        nome_cat = self.classificar(transacao.descricao)

        # Busca ou cria a categoria
        categoria = (
            self.db.query(Categoria)
            .filter(Categoria.nome == nome_cat)
            .first()
        )
        if not categoria:
            categoria = Categoria(nome=nome_cat)
            self.db.add(categoria)
            self.db.flush()

        transacao.categoria_id = categoria.id
        return categoria

    def sugestoes(self, descricao: str, n: int = 3) -> List[str]:
        """
        Retorna as N categorias mais prováveis para uma descrição.

        Args:
            descricao: Texto da transação
            n:         Número de sugestões a retornar

        Returns:
            Lista de nomes de categorias em ordem de relevância
        """
        desc_norm = normalizar_descricao(descricao)
        pontuacoes: Dict[str, int] = {}

        for categoria, palavras in self.PALAVRAS_CHAVE.items():
            pts = sum(1 for p in palavras if p in desc_norm)
            if pts > 0:
                pontuacoes[categoria] = pts

        if not pontuacoes:
            return ["Outros"]

        ordenadas = sorted(pontuacoes, key=pontuacoes.get, reverse=True)
        return ordenadas[:n]

    def adicionar_palavras(self, categoria: str, novas_palavras: List[str]) -> None:
        """
        Adiciona novas palavras-chave a uma categoria existente.
        Permite personalização sem alterar o código.

        Args:
            categoria:      Nome da categoria
            novas_palavras: Palavras a acrescentar
        """
        if categoria not in self.PALAVRAS_CHAVE:
            self.PALAVRAS_CHAVE[categoria] = []

        existentes = set(self.PALAVRAS_CHAVE[categoria])
        self.PALAVRAS_CHAVE[categoria].extend(
            [p.lower() for p in novas_palavras if p.lower() not in existentes]
        )

    # --------------------------------------------------
    # Helpers internos
    # --------------------------------------------------

    def _classificar_por_historico(self, descricao_norm: str) -> Optional[str]:
        """
        Busca no histórico a categoria mais usada para descrições similares.

        Args:
            descricao_norm: Descrição já normalizada

        Returns:
            Nome da categoria mais frequente ou None
        """
        palavras = descricao_norm.split()
        if not palavras:
            return None

        # Usa a primeira palavra como âncora de busca
        ancora = palavras[0]
        try:
            transacoes = (
                self.db.query(Transacao)
                .filter(
                    Transacao.categoria_id.isnot(None),
                    Transacao.descricao.ilike(f"%{ancora}%")
                )
                .limit(20)
                .all()
            )
        except Exception:
            return None

        if not transacoes:
            return None

        contagem: Dict[str, int] = {}
        for t in transacoes:
            if t.categoria:
                nome = t.categoria.nome
                contagem[nome] = contagem.get(nome, 0) + 1

        if contagem:
            return max(contagem, key=contagem.get)

        return None

    # --------------------------------------------------
    # Classificação de TIPO DE DOCUMENTO
    # --------------------------------------------------

    # Mapeia chave interna → (nome legível, emoji, palavras-chave no texto)
    TIPOS_DOCUMENTO: Dict[str, dict] = {
        "comprovante_pagamento_bancario": {
            "nome":    "Comprovante Bancário (PIX/Transferência)",
            "emoji":   "🏦",
            "chaves":  [
                "comprovante pix", "comprovante de pix", "pix enviado",
                "pix recebido", "chave pix", "end to end", "e2e",
                "valor do pagamento", "tipo de transferencia",
                "tipo de transferência", "codigo da transacao pix",
                "código da transação pix", "id da transacao pix",
                "id da transação pix",
                "comprovante de transferencia", "comprovante de transferência",
                "transferencia realizada", "transferência realizada",
                "transferencia recebida", "transferência recebida",
                "comprovante de ted", "comprovante de doc",
                "comprovante de pagamento", "codigo de autenticacao",
                "código de autenticação", "id da transacao", "id da transação",
                "origem", "destino", "favorecido", "pagador", "recebedor",
            ],
        },
        "recibo_despesa": {
            "nome":    "Recibo de Despesa",
            "emoji":   "🧾",
            "chaves":  [
                "recibo", "recebi de", "recebemos de", "recebido de",
                "pagador", "recebedor", "referente a", "referente ao",
                "importancia de", "importância de", "valor recebido",
                "valor pago", "declaro que recebi", "dou quitacao",
                "dou quitação", "quitacao", "quitação", "assinatura",
            ],
        },
        "nota_fiscal": {
            "nome":    "Nota Fiscal de Despesa",
            "emoji":   "🧾",
            "chaves":  [
                "danfe", "nf-e", "nota fiscal", "nfce", "cupom fiscal",
                "chave de acesso", "emitente", "destinatario", "destinatário",
                "cfop", "icms", "iss", "serie", "número da nf",
                "número nf", "modelo 55", "modelo 65", "xml nf",
                "secretaria da fazenda", "sefaz",
            ],
        },
        "comprovante_compra": {
            "nome":    "Comprovante de Compra (Cartão de Crédito)",
            "emoji":   "🏷️",
            "chaves":  [
                "comprovante", "autorizado", "aprovado", "nsu",
                "cod autorizacao", "cod autorização", "codigo autorizacao",
                "transacao aprovada", "transação aprovada",
                "estabelecimento", "terminal pos", "via do cliente",
                "via estabelecimento", "bandeira", "chip", "senha",
                "parcelado em", "1x de", "2x de", "3x de",
                "contactless", "nfc", "maquininha",
            ],
        },
        "boleto": {
            "nome":    "Boleto Bancário",
            "emoji":   "📋",
            "chaves":  [
                "boleto", "boleto bancário", "boleto bancario",
                "linha digitavel", "linha digitável",
                "beneficiario", "beneficiário", "cedente", "sacado",
                "nosso numero", "nosso número", "codigo de barras",
                "código de barras", "vencimento", "pagavel em",
                "pagável em", "febraban", "banco do brasil boleto",
                "caixa boleto", "itau boleto", "bradesco boleto",
            ],
        },
        "extrato_bancario": {
            "nome":    "Extrato Bancário",
            "emoji":   "🏦",
            "chaves":  [
                "extrato", "saldo anterior", "saldo atual",
                "agencia", "agência", "conta corrente", "conta corrente",
                "historico", "histórico", "lancamentos", "lançamentos",
                "debito em conta", "débito em conta",
                "credito em conta", "crédito em conta",
                "tarifas", "rendimento poupanca", "rendimento poupança",
                "extrato de conta", "periodo do extrato",
                "saldo do dia", "saldo em conta", "saldo disponivel",
                "saldo disponível", "data do lancamento", "data do lançamento",
            ],
        },
        "extrato_cartao": {
            "nome":    "Extrato de Cartão de Crédito",
            "emoji":   "💳",
            "chaves":  [
                "fatura", "fatura do cartão", "fatura do cartao",
                "limite disponivel", "limite disponível",
                "limite de credito", "limite de crédito",
                "cartao de credito", "cartão de crédito",
                "fechamento", "vencimento da fatura",
                "pagamento minimo", "pagamento mínimo",
                "total da fatura", "compras parceladas",
                "nubank", "visa", "mastercard", "elo", "amex", "hipercard",
                "fatura aberta", "fatura fechada",
                "melhor dia de compra", "valor total da fatura",
                "pagamento da fatura", "data de vencimento",
                "limite total", "rotativo", "encargos",
            ],
        },
    }

    NOMES_TIPOS = {
        "comprovante_pagamento_bancario": "Comprovante Bancário (PIX/Transferência)",
        "recibo_despesa":     "Recibo de Despesa",
        "nota_fiscal":        "Nota Fiscal de Despesa",
        "comprovante_compra": "Comprovante de Compra (Cartão de Crédito)",
        "boleto":             "Boleto Bancário",
        "extrato_bancario":   "Extrato Bancário",
        "extrato_cartao":     "Extrato de Cartão de Crédito",
        "desconhecido":       "Tipo não identificado",
    }

    TOKENS_IGNORADOS_DOCUMENTO = {
        "para", "com", "sem", "dos", "das", "nos", "nas", "uma", "uns", "umas",
        "que", "por", "nao", "sim", "seu", "sua", "seus", "suas", "este", "essa",
        "de", "do", "da", "em", "no", "na", "e", "ou", "a", "o", "os", "as",
        "valor", "data", "total", "tipo", "nome", "numero", "doc", "pagina", "pag",
        "bradesco", "itau", "banco", "brasil", "agencia", "conta", "cliente", "cpf",
        "cnpj", "comprovante", "documento", "extrato",
    }

    def _assinatura_aprendizado_documento(self, texto: str) -> str:
        """
        Gera assinatura estável a partir dos termos mais frequentes do documento.
        Ignora números e palavras muito genéricas para generalizar em novos arquivos.
        """
        texto_norm = normalizar_descricao(texto or "")
        if not texto_norm:
            return ""

        tokens = re.findall(r"[a-zà-ÿ]{3,}", texto_norm)
        filtrados = [
            token for token in tokens
            if token not in self.TOKENS_IGNORADOS_DOCUMENTO
        ]
        if not filtrados:
            return ""

        frequencias = Counter(filtrados)
        relevantes = [token for token, _ in frequencias.most_common(24)]
        if not relevantes:
            return ""

        base = "|".join(sorted(relevantes))
        return hashlib.sha1(base.encode("utf-8")).hexdigest()

    def registrar_feedback_tipo_documento(self, texto: str, tipo_documento: str) -> None:
        """
        Persiste feedback do usuário para melhorar futuras classificações.
        """
        if not texto or not tipo_documento or tipo_documento == "desconhecido":
            return

        assinatura = self._assinatura_aprendizado_documento(texto)
        if not assinatura:
            return

        aprendizado = (
            self.db.query(AprendizadoTipoDocumento)
            .filter(
                AprendizadoTipoDocumento.assinatura == assinatura,
                AprendizadoTipoDocumento.tipo_documento == tipo_documento,
            )
            .first()
        )

        if aprendizado:
            aprendizado.ocorrencias = int(aprendizado.ocorrencias or 0) + 1
        else:
            aprendizado = AprendizadoTipoDocumento(
                assinatura=assinatura,
                tipo_documento=tipo_documento,
                ocorrencias=1,
            )
            self.db.add(aprendizado)

        self.db.commit()

    def classificar_tipo_documento(self, texto: str) -> Dict[str, str]:
        """
        Identifica o tipo de documento financeiro pelo conteúdo do texto extraído.

        Estratégia: pontuação por palavras-chave por tipo; vence o de maior score.
        Retorna confiança "alta" (≥3 chaves), "media" (1-2 chaves) ou "baixa" (0).

        Args:
            texto: Texto extraído do documento (OCR ou digital)

        Returns:
            Dicionário com:
              - tipo:       chave interna (ex. "extrato_bancario")
              - nome:       nome legível (ex. "Extrato Bancário")
              - emoji:      emoji representativo
              - confianca:  "alta" | "media" | "baixa"
              - pontuacao:  int com a pontuação obtida
        """
        if not texto:
            return {
                "tipo": "desconhecido", "nome": self.NOMES_TIPOS["desconhecido"],
                "emoji": "❓", "confianca": "baixa", "pontuacao": 0,
            }

        texto_norm = texto.lower()
        pontuacoes: Dict[str, int] = {}

        assinatura = self._assinatura_aprendizado_documento(texto)
        if assinatura:
            aprendizados = (
                self.db.query(AprendizadoTipoDocumento)
                .filter(AprendizadoTipoDocumento.assinatura == assinatura)
                .all()
            )
            for item in aprendizados:
                bonus = 8 + min(int(item.ocorrencias or 0), 6)
                pontuacoes[item.tipo_documento] = pontuacoes.get(item.tipo_documento, 0) + bonus

        for tipo, info in self.TIPOS_DOCUMENTO.items():
            pts = 0
            for kw in info["chaves"]:
                ocorrencias = texto_norm.count(kw)
                if ocorrencias:
                    # Premia repetição sem explodir score em documentos longos.
                    pts += 1 + min(ocorrencias - 1, 2)
            if pts > 0:
                pontuacoes[tipo] = pontuacoes.get(tipo, 0) + pts

        # Sinais fortes para diferenciar extrato bancário x fatura de cartão.
        reforcos = {
            "extrato_cartao": [
                "total da fatura",
                "vencimento da fatura",
                "pagamento minimo",
                "pagamento mínimo",
                "compras parceladas",
            ],
            "extrato_bancario": [
                "saldo anterior",
                "saldo atual",
                "extrato de conta",
                "conta corrente",
                "lancamentos",
                "lançamentos",
            ],
        }
        for tipo, chaves in reforcos.items():
            bonus = sum(2 for kw in chaves if kw in texto_norm)
            if bonus:
                pontuacoes[tipo] = pontuacoes.get(tipo, 0) + bonus

        # Padrões comuns em fatura de cartão em aberto (Bradesco, Itaú, etc.).
        if re.search(r"x{4}\.x{4}\.x{4}", texto_norm):
            pontuacoes["extrato_cartao"] = pontuacoes.get("extrato_cartao", 0) + 3
        if "total para:" in texto_norm:
            pontuacoes["extrato_cartao"] = pontuacoes.get("extrato_cartao", 0) + 2
        if "situacao do extrato: em aberto" in texto_norm or "situação do extrato: em aberto" in texto_norm:
            pontuacoes["extrato_cartao"] = pontuacoes.get("extrato_cartao", 0) + 2

        # Faturas PagBank e similares em imagem costumam ter pouco texto
        # estrutural, mas combinam emissor, vencimento e linhas de compra.
        emissor_cartao = any(chave in texto_norm for chave in ("pagbank", "pagseguro", "mercado pago"))
        sinais_fatura = sum(
            1 for chave in (
                "vence em",
                "vencimento",
                "fatura",
                "cartao",
                "cartão",
                "visa",
                "mastercard",
                "elo",
            )
            if chave in texto_norm
        )
        linhas_compra = len(
            re.findall(r'\b\d{2}/\d{2}(?:/\d{2,4})?\b.+?(?:r\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}', texto_norm)
        )
        if emissor_cartao and sinais_fatura >= 2 and linhas_compra >= 1:
            pontuacoes["extrato_cartao"] = pontuacoes.get("extrato_cartao", 0) + 4

        # Reforço para comprovante PIX/transferência (evita falso positivo como extrato).
        if "comprovante" in texto_norm and (
            "pix" in texto_norm
            or "transferencia" in texto_norm
            or "transferência" in texto_norm
        ):
            bonus_pix = 2
            if any(
                chave in texto_norm for chave in (
                    "valor do pagamento",
                    "tipo de transferencia",
                    "tipo de transferência",
                    "codigo da transacao pix",
                    "código da transação pix",
                    "id da transacao pix",
                    "id da transação pix",
                )
            ):
                bonus_pix += 3

            pontuacoes["comprovante_pagamento_bancario"] = (
                pontuacoes.get("comprovante_pagamento_bancario", 0) + bonus_pix
            )

        if not pontuacoes:
            return {
                "tipo": "desconhecido", "nome": self.NOMES_TIPOS["desconhecido"],
                "emoji": "❓", "confianca": "baixa", "pontuacao": 0,
            }

        melhor_tipo = max(pontuacoes, key=pontuacoes.get)
        score       = pontuacoes[melhor_tipo]
        confianca   = "alta" if score >= 5 else "media" if score >= 2 else "baixa"

        # Ambiguidade comum: extrato de conta com texto de cartão e vice-versa.
        if "extrato_cartao" in pontuacoes and "extrato_bancario" in pontuacoes:
            dif = abs(pontuacoes["extrato_cartao"] - pontuacoes["extrato_bancario"])
            if dif <= 1 and confianca == "alta":
                confianca = "media"

        info = self.TIPOS_DOCUMENTO.get(melhor_tipo, {
            "nome": self.NOMES_TIPOS.get(melhor_tipo, melhor_tipo),
            "emoji": "🧾",
        })

        return {
            "tipo":      melhor_tipo,
            "nome":      info["nome"],
            "emoji":     info["emoji"],
            "confianca": confianca,
            "pontuacao": score,
        }

