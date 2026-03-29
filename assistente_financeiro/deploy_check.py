#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para preparar o Assessor Financeiro para deploy/distribuição.
Valida ambiente, dependências e gera artefatos.
"""

import os
import sys
import subprocess
from pathlib import Path


def print_section(title: str) -> None:
    """Imprime um separador de seção."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def check_python_version() -> bool:
    """Verifica se Python >= 3.9."""
    if sys.version_info < (3, 9):
        print(f"❌ Python 3.9+ requerido. Detectado: {sys.version}")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} OK")
    return True


def check_venv() -> bool:
    """Verifica se está em um virtual environment."""
    if sys.prefix == sys.base_prefix:
        print("⚠️  Não está em um virtual environment!")
        print("   Recomendado rodar dentro de um .venv")
        return False
    print(f"✅ Virtual environment detectado: {sys.prefix}")
    return True


def check_dependencies() -> bool:
    """Verifica dependências principais."""
    try:
        import flet
        print(f"✅ Flet {flet.__version__} instalado")
    except ImportError:
        print("❌ Flet não instalado. Execute: pip install -r requirements-flet.txt")
        return False

    try:
        import requests
        print(f"✅ Requests instalado")
    except ImportError:
        print("❌ Requests não instalado")
        return False

    try:
        import dotenv
        print(f"✅ Python-dotenv instalado")
    except ImportError:
        print("❌ Python-dotenv não instalado")
        return False

    return True


def validate_structure() -> bool:
    """Valida estrutura de pastas e arquivos."""
    base = Path(__file__).parent
    required = [
        base / "app" / "__init__.py",
        base / "interface_flet" / "app_flet.py",
        base / "run_flet.py",
        base / ".env",
    ]

    all_exist = True
    for path in required:
        if path.exists():
            print(f"✅ {path.relative_to(base)}")
        else:
            print(f"❌ {path.relative_to(base)} - FALTANDO")
            all_exist = False

    return all_exist


def test_imports() -> bool:
    """Testa se consegue fazer import dos módulos principais."""
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        import app
        from interface_flet.app_flet import VorcaroFletApp, ApiClient
        print("✅ Imports dos módulos principais OK")
        return True
    except Exception as e:
        print(f"❌ Erro ao fazer imports: {e}")
        return False


def build_summary() -> None:
    """Gera resumo de configuração."""
    base = Path(__file__).parent

    print("\n📋 CONFIGURAÇÃO ATUAL:")
    print(f"  Localização:  {base}")
    print(f"  Interface:    Flet (Flutter para Python)")
    print(f"  API pendente: http://127.0.0.1:8000")

    env_file = base / ".env"
    if env_file.exists():
        from dotenv import dotenv_values
        try:
            config = dotenv_values(env_file)
            api_url = config.get("ASSISTENTE_API_URL") or "Não configurado"
            print(f"  API configurada: {api_url}")
        except Exception:
            pass


def main() -> int:
    """Função principal."""
    print_section("🔧 VALIDAÇÃO E PREPARAÇÃO PARA DEPLOY")

    steps = [
        ("Versão Python", check_python_version),
        ("Virtual Environment", check_venv),
        ("Dependências", check_dependencies),
        ("Estrutura de Pastas", validate_structure),
        ("Imports dos Módulos", test_imports),
    ]

    results = []
    for name, func in steps:
        print_section(name)
        try:
            results.append(func())
        except Exception as e:
            print(f"❌ Erro: {e}")
            results.append(False)

    # Resumo
    print_section("📊 RESUMO")
    passed = sum(results)
    total = len(results)
    print(f"✅ {passed}/{total} validações passaram")

    if all(results):
        print("\n🎉 Ambiente pronto para deploy!\n")
        build_summary()
        print("\n📌 Próximos passos:")
        print("  1. Rodar a API:    python assistente_financeiro/run_api.py")
        print("  2. Rodar Flet:    python assistente_financeiro/run_flet.py")
        print("  3. Para build:    flet build web")
        print("\n")
        return 0
    else:
        print("\n❌ Ambiente com problemas. Corrija os erros acima.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
