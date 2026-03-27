# Roadmap de Escala - Assistente Financeiro

## Objetivo
Evoluir de uso individual para plataforma multiempresa com Telegram em grupos, isolamento de dados por organizacao e governanca de acesso.

## Fase 1 - Base multi-tenant
- Criar tabela `organizacoes`.
- Criar tabela `usuarios`.
- Criar tabela `membros_organizacao` com papel (owner, admin, editor, viewer).
- Adicionar `organizacao_id` em transacoes, categorias, metas, orcamentos, extratos e demais entidades de dominio.
- Aplicar filtro obrigatorio por `organizacao_id` em todas as consultas.
- Criar migracoes e script de backfill para dados existentes.

## Fase 2 - Telegram multiempresa
- Criar tabela `telegram_chats` com vinculo `chat_id -> organizacao_id`.
- Comandos de onboarding no Telegram: `/start`, `/vincular`, `/status`, `/ajuda`.
- Fluxo de autorizacao para admin de grupo.
- Isolar contexto de conversa por organizacao e por chat.
- Definir comportamento de grupos (comandos explicitos e fallback conversacional controlado).

## Fase 3 - Seguranca e compliance
- RBAC por endpoint e por acao de escrita.
- Trilha de auditoria para operacoes sensiveis.
- Rotacao de segredos e politica de token.
- Mascaramento de dados sensiveis em logs.

## Fase 4 - Operacao e confiabilidade
- Migrar para PostgreSQL em producao.
- Health checks, readiness e liveness.
- Dashboard de metricas (latencia, erros, throughput).
- Alertas de degradacao de Ollama, Telegram e OCR.

## Fase 5 - Produto
- Comandos de resumo por periodo e centro de custo.
- Alertas proativos (orcamento, assinaturas, anomalias).
- Mini app Telegram para operacao visual de aprovacao/confirmacao.

## Criterios de pronto da primeira versao B2B
- Isolamento de dados validado entre organizacoes.
- Suporte a mais de um grupo Telegram por organizacao.
- Controle de permissao por papel ativo.
- Logs auditaveis e monitoramento minimo operacional.
