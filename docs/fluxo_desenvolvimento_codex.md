# Fluxo de desenvolvimento com Codex

## Objetivo

Este documento orienta como usar o Codex no projeto EA2S SIG com seguranca, reduzindo prompts longos, suposicoes incorretas e retrabalho.

## Antes de pedir alteracoes

Informe claramente se o Codex pode ou nao:

- executar app;
- conectar ao banco;
- executar SQL;
- rodar scripts;
- fazer commit.

Quando a tarefa for apenas edicao local, diga explicitamente: nao execute app, nao conecte no banco, nao rode SQL, nao rode scripts e nao faca commit.

## Arquivos de instrucao

O Codex deve consultar:

- `AGENTS.md` para regras gerais do projeto;
- `.agents/skills/ea2s-sql/SKILL.md` para SQL;
- `.agents/skills/ea2s-streamlit/SKILL.md` para interface;
- `.agents/skills/ea2s-postgis/SKILL.md` para geoprocessamento;
- `.agents/skills/ea2s-importacao/SKILL.md` para inventario/importacao;
- `.agents/skills/ea2s-diagnostico/SKILL.md` para planos e cruzamentos;
- `.agents/skills/ea2s-git/SKILL.md` para commits e diffs.

## Como chamar uma skill

Nos proximos prompts, use frases como:

- `Use a skill ea2s-sql para revisar este script.`
- `Use a skill ea2s-streamlit para ajustar a interface.`
- `Use a skill ea2s-postgis para revisar a logica espacial.`
- `Use a skill ea2s-importacao para ajustar o inventario.`
- `Use a skill ea2s-diagnostico para montar o plano de diagnostico.`
- `Use a skill ea2s-git para preparar um resumo de commit, sem commitar.`

## Padrao de trabalho esperado

1. Ler os arquivos relevantes.
2. Preservar mudancas existentes do usuario.
3. Editar apenas o necessario.
4. Nao executar nada fora do escopo autorizado.
5. Atualizar documentacao quando a mudanca alterar fluxo, regra ou arquitetura.
6. Ao final, listar arquivos alterados, resumo, testes realizados e pendencias.

## Quando houver duvida sobre banco

Nao assumir nomes reais de colunas. Preferir:

- camada de compatibilidade;
- consulta de inspecao documentada;
- pendencia registrada;
- pedido de confirmacao ao usuario.

## Testes

Quando o usuario nao autorizar execucao, apenas sugerir testes manuais. Exemplo:

- abrir Streamlit e acessar a pagina alterada;
- executar SQL em transacao com `BEGIN` e `ROLLBACK`;
- conferir views com filtros por `execucao_id`, `projeto_id` e `area_interesse_id`;
- validar exportacoes em pasta de projeto.

## Saida final do Codex

A resposta final deve conter:

- arquivos criados ou alterados;
- resumo das mudancas;
- o que nao foi executado;
- pendencias;
- proximos passos manuais.