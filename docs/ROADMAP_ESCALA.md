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

### Como fazer (Fase 1)
1. Modelagem:
- Criar modelos SQLAlchemy de organizacao e usuario.
- Criar tabela de vinculo usuario-organizacao com papel.
2. Persistencia:
- Incluir `organizacao_id` nas entidades de dominio.
- Criar script de backfill definindo organizacao padrao para dados atuais.
3. Aplicacao:
- Injetar contexto de organizacao na requisicao.
- Bloquear queries sem filtro por tenant.
4. Validacao:
- Testes de isolamento entre organizacoes.

## Fase 2 - Telegram multiempresa
- Criar tabela `telegram_chats` com vinculo `chat_id -> organizacao_id`.
- Comandos de onboarding no Telegram: `/start`, `/vincular`, `/status`, `/ajuda`.
- Fluxo de autorizacao para admin de grupo.
- Isolar contexto de conversa por organizacao e por chat.
- Definir comportamento de grupos (comandos explicitos e fallback conversacional controlado).

### Como fazer (Fase 2)
1. Vinculo de chats:
- Persistir `chat_id` com `organizacao_id`.
2. Onboarding:
- Implementar comandos `/start`, `/vincular`, `/status` e `/ajuda`.
3. Seguranca:
- Permitir vinculo apenas por administradores.
4. Validacao:
- Garantir que grupos diferentes nao compartilham contexto.

## Fase 3 - Seguranca e compliance
- RBAC por endpoint e por acao de escrita.
- Trilha de auditoria para operacoes sensiveis.
- Rotacao de segredos e politica de token.
- Mascaramento de dados sensiveis em logs.

### Como fazer (Fase 3)
1. RBAC:
- Implementar middleware de autorizacao por papel.
2. Auditoria:
- Registrar quem alterou o que e quando.
3. Segredos:
- Remover tokens/chaves de logs e arquivos versionados.
4. Validacao:
- Testes de permissao por endpoint critico.

## Fase 4 - Operacao e confiabilidade
- Migrar para PostgreSQL em producao.
- Health checks, readiness e liveness.
- Dashboard de metricas (latencia, erros, throughput).
- Alertas de degradacao de Ollama, Telegram e OCR.

### Como fazer (Fase 4)
1. Infra:
- Migrar para PostgreSQL em ambiente de producao.
2. Confiabilidade:
- Adicionar health/readiness/liveness.
3. Observabilidade:
- Coletar metricas de erros e latencia.
4. Alertas:
- Definir alarmes para integracoes criticas.

## Fase 5 - Produto
- Comandos de resumo por periodo e centro de custo.
- Alertas proativos (orcamento, assinaturas, anomalias).
- Mini app Telegram para operacao visual de aprovacao/confirmacao.

### Como fazer (Fase 5)
1. Funcional:
- Comandos de resumo por periodo e centro de custo.
2. Proatividade:
- Lembretes e alertas inteligentes por perfil de usuario.
3. UX:
- Evoluir para mini app Telegram para operacao mais visual.
4. Validacao:
- Medir adesao, engajamento e taxa de resposta dos alertas.

## Criterios de pronto da primeira versao B2B
- Isolamento de dados validado entre organizacoes.
- Suporte a mais de um grupo Telegram por organizacao.
- Controle de permissao por papel ativo.
- Logs auditaveis e monitoramento minimo operacional.
