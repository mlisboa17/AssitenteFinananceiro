---
name: "03 - RBAC, auditoria e operacao"
about: "Governanca de acesso e observabilidade para ambiente empresarial"
title: "[Seguranca] RBAC + auditoria + observabilidade"
labels: ["seguranca", "devops", "escala"]
assignees: []
---

## Objetivo
Adicionar governanca e operacao minima para uso empresarial.

## Entregas
- [ ] Perfis de acesso (owner/admin/editor/viewer)
- [ ] Middleware de autorizacao por acao
- [ ] Trilha de auditoria para alteracoes sensiveis
- [ ] Logs estruturados com mascaramento de dados
- [ ] Health checks e metricas basicas

## Criterios de aceite
- [ ] Acoes bloqueadas para perfis sem permissao
- [ ] Eventos criticos registrados em auditoria
- [ ] Ambiente com monitoramento de disponibilidade

## Riscos
- Complexidade de permissao em endpoints legados.

## Notas
Acompanhar com revisao de arquitetura de dados multi-tenant.
