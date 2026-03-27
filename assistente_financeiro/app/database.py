"""
Configuração do banco de dados usando SQLAlchemy.
Suporta SQLite (padrão para desenvolvimento) e PostgreSQL (produção).
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
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


def obter_sessao() -> SessionLocal:
    """
    Retorna uma sessão direta (para uso fora do contexto FastAPI).
    Lembre-se de fechar manualmente com .close().
    """
    return SessionLocal()
