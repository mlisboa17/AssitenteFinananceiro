---
name: "01 - Multi-tenant base"
about: "Estrutura de contas e isolamento por organizacao"
title: "[Escala] Base multi-tenant"
labels: ["escala", "arquitetura", "backend"]
assignees: []
---

## Objetivo
Implementar estrutura de organizacoes e usuarios com isolamento de dados por tenant.

## Entregas
- [ ] Tabela `organizacoes`
- [ ] Tabela `usuarios`
- [ ] Tabela `membros_organizacao`
- [ ] `organizacao_id` nas tabelas de dominio
- [ ] Regras de consulta filtrando por `organizacao_id`
- [ ] Migracao de dados legados

## Criterios de aceite
- [ ] Usuario A nao enxerga dados da Organizacao B
- [ ] APIs de leitura/escrita exigem contexto de organizacao
- [ ] Testes cobrindo isolamento minimo

## Riscos
- Erro de filtro em query pode causar vazamento entre tenants.

## Notas
Referenciar roadmap: `docs/ROADMAP_ESCALA.md`.
