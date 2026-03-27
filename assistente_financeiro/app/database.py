"""
Configuração do banco de dados usando SQLAlchemy.
Suporta SQLite (padrão para desenvolvimento) e PostgreSQL (produção).
"""

import os
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker, DeclarativeBase
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Caminho absoluto do banco — sempre relativo a este arquivo, nunca ao cwd
_APP_DIR  = os.path.dirname(os.path.abspath(__file__))          # .../app/
_DATA_DIR = os.path.dirname(_APP_DIR)                           # .../assistente_financeiro/
_DB_PATH  = os.path.join(_DATA_DIR, "assistente_financeiro.db") # caminho fixo

# URL do banco de dados (SQLite por padrão)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///" + _DB_PATH.replace("\\", "/")
)

# Argumentos de conexão específicos para SQLite
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# Criação do engine com pool de conexões
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False  # Altere para True para ver o SQL gerado no console
)

# Ativa suporte a chaves estrangeiras no SQLite
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# Fábrica de sessões do banco de dados
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


class Base(DeclarativeBase):
    """Classe base para todos os modelos SQLAlchemy."""
    pass


def get_db():
    """
    Gerador de sessão do banco de dados.
    Usado como dependência injetável nas rotas FastAPI.
    Garante que a sessão seja sempre fechada ao final.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def criar_tabelas():
    """
    Cria todas as tabelas definidas nos modelos, caso não existam.
    Deve ser chamado na inicialização da aplicação.
    """
    from app import models  # noqa: F401 - importa para registrar os modelos
    Base.metadata.create_all(bind=engine)
    _garantir_colunas_planner_sqlite()
    _garantir_colunas_multi_tenant_sqlite()
    _garantir_tenant_padrao_sqlite()


def _garantir_colunas_planner_sqlite() -> None:
    """Adiciona colunas novas do planner em bases SQLite legadas sem migration formal."""
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as conn:
        cols = conn.execute(text("PRAGMA table_info(tarefas_planner)")).fetchall()
        existentes = {str(c[1]).lower() for c in cols}

        if "hora_inicio" not in existentes:
            conn.execute(text("ALTER TABLE tarefas_planner ADD COLUMN hora_inicio VARCHAR(5)"))
        if "hora_fim" not in existentes:
            conn.execute(text("ALTER TABLE tarefas_planner ADD COLUMN hora_fim VARCHAR(5)"))
        if "duracao_min" not in existentes:
            conn.execute(text("ALTER TABLE tarefas_planner ADD COLUMN duracao_min INTEGER"))


def _garantir_colunas_multi_tenant_sqlite() -> None:
    """Adiciona colunas organizacao_id em bases legadas sem migration formal."""
    if not DATABASE_URL.startswith("sqlite"):
        return

    alvos = {
        "categorias": "organizacao_id INTEGER",
        "contas_bancarias": "organizacao_id INTEGER",
        "cartoes_credito": "organizacao_id INTEGER",
        "transacoes": "organizacao_id INTEGER",
        "extratos": "organizacao_id INTEGER",
        "metas": "organizacao_id INTEGER",
        "orcamentos": "organizacao_id INTEGER",
        "eventos_financeiros": "organizacao_id INTEGER",
        "compromissos": "organizacao_id INTEGER",
        "tarefas_planner": "organizacao_id INTEGER",
    }

    with engine.begin() as conn:
        for tabela, coluna_ddl in alvos.items():
            cols = conn.execute(text(f"PRAGMA table_info({tabela})")).fetchall()
            if not cols:
                continue

            existentes = {str(c[1]).lower() for c in cols}
            if "organizacao_id" not in existentes:
                conn.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {coluna_ddl}"))


def _garantir_tenant_padrao_sqlite() -> None:
    """Cria organização/usuário padrão e faz backfill do organizacao_id quando ausente."""
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as conn:
        org_row = conn.execute(text("SELECT id FROM organizacoes ORDER BY id LIMIT 1")).fetchone()
        if org_row:
            org_id = int(org_row[0])
        else:
            conn.execute(
                text(
                    "INSERT INTO organizacoes (nome, slug, ativa, criado_em) "
                    "VALUES (:nome, :slug, 1, CURRENT_TIMESTAMP)"
                ),
                {"nome": "Organização Padrão", "slug": "organizacao-padrao"},
            )
            org_id = int(conn.execute(text("SELECT id FROM organizacoes ORDER BY id LIMIT 1")).fetchone()[0])

        user_row = conn.execute(text("SELECT id FROM usuarios ORDER BY id LIMIT 1")).fetchone()
        if user_row:
            user_id = int(user_row[0])
        else:
            conn.execute(
                text(
                    "INSERT INTO usuarios (nome, email, telegram_user_id, ativo, criado_em) "
                    "VALUES (:nome, :email, NULL, 1, CURRENT_TIMESTAMP)"
                ),
                {"nome": "Administrador", "email": "admin@local"},
            )
            user_id = int(conn.execute(text("SELECT id FROM usuarios ORDER BY id LIMIT 1")).fetchone()[0])

        membro = conn.execute(
            text(
                "SELECT id FROM membros_organizacao "
                "WHERE usuario_id = :u AND organizacao_id = :o LIMIT 1"
            ),
            {"u": user_id, "o": org_id},
        ).fetchone()
        if not membro:
            conn.execute(
                text(
                    "INSERT INTO membros_organizacao "
                    "(usuario_id, organizacao_id, papel, ativo, criado_em) "
                    "VALUES (:u, :o, :papel, 1, CURRENT_TIMESTAMP)"
                ),
                {"u": user_id, "o": org_id, "papel": "owner"},
            )

        tabelas = [
            "categorias",
            "contas_bancarias",
            "cartoes_credito",
            "transacoes",
            "extratos",
            "metas",
            "orcamentos",
            "eventos_financeiros",
            "compromissos",
            "tarefas_planner",
        ]
        for tabela in tabelas:
            cols = conn.execute(text(f"PRAGMA table_info({tabela})")).fetchall()
            existentes = {str(c[1]).lower() for c in cols}
            if "organizacao_id" in existentes:
                conn.execute(
                    text(f"UPDATE {tabela} SET organizacao_id = :org WHERE organizacao_id IS NULL"),
                    {"org": org_id},
                )


def obter_sessao() -> Session:
    """
    Retorna uma sessão direta (para uso fora do contexto FastAPI).
    Lembre-se de fechar manualmente com .close().
    """
    return SessionLocal()
