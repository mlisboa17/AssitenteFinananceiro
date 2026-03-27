---
name: "02 - Telegram grupos multiempresa"
about: "Habilitar operacao em grupos com vinculo por organizacao"
title: "[Telegram] Grupos e vinculo por organizacao"
labels: ["telegram", "escala", "produto"]
assignees: []
---

## Objetivo
Permitir uso seguro do bot em grupos Telegram para multiplas empresas.

## Entregas
- [ ] Tabela `telegram_chats` com `chat_id` e `organizacao_id`
- [ ] Comando `/vincular` para associar grupo a organizacao
- [ ] Comando `/status` para diagnostico do chat
- [ ] Contexto de conversa separado por chat e organizacao
- [ ] Politica de comandos para grupos (modo explicito)

## Criterios de aceite
- [ ] Dois grupos diferentes nao compartilham contexto
- [ ] Usuario sem permissao nao altera configuracao do grupo
- [ ] Mensagens de progresso continuam durante processamento longo

## Riscos
- Privacy mode no Telegram pode limitar recebimento de mensagens em grupos.

## Notas
Revisar configuracao de comandos e modo de privacidade no BotFather.
