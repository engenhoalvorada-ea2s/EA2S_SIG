# Skill: ea2s-git

Use esta skill quando a tarefa envolver estado do repositorio, diffs, commits, branches ou revisao de mudancas.

## Regras obrigatorias

- Nao fazer commit sem autorizacao explicita.
- Nao usar `git reset --hard` sem pedido claro.
- Nao usar `git checkout --` para descartar mudancas do usuario sem pedido claro.
- Nao reverter arquivos alterados por outros sem entender o impacto.
- Antes de orientar commit, verificar `git status`.

## Fluxo recomendado

1. Verificar `git status --short`.
2. Conferir arquivos relevantes com diff.
3. Separar mudancas por tema.
4. Sugerir commit pequeno e descritivo.
5. Fazer commit apenas se o usuario autorizar.

## Mensagens de commit

Preferir mensagens curtas em portugues, no imperativo ou substantivo claro, por exemplo:

- `Documenta fluxo Codex do EA2S SIG`
- `Ajusta compatibilidade de camadas de analise`
- `Cria views tecnicas socioeconomicas`
- `Organiza modulo de importacao geografica`

## Relatorio ao usuario

Ao final de uma tarefa com arquivos editados, informar:

- arquivos alterados;
- resumo das mudancas;
- testes realizados ou nao realizados;
- pendencias;
- aviso quando nao houve commit.