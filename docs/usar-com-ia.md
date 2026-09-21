# Usar com agente de IA

A ideia: o agente **lê** por `recall` (só o que serve à decisão) e **escreve** pela porta. O arquivo
markdown continua sendo seu, legível e versionável; o agente não ganha um caminho paralelo.

## Bloco pra colar em `CLAUDE.md` ou `AGENTS.md`

```markdown
## Memória (memoro)

A memória durável mora em `$MEMORO_HOME/areas/` e só entra e sai pela porta `memoro`.

- Antes de decidir: `python3 -m memoro recall --lens <lente>` ou `--scope <area[/sub]>`.
  Vem o fato, os filhos e o que ele herda, com o motivo de cada um. Não leia a pasta inteira.
- Aprendeu fato durável: `echo "<corpo>" | python3 -m memoro add <area> <nome> --desc "<uma linha>"`.
  Corrigir: `memoro update <id>`. Errado ou vencido: `memoro rm <id> --motivo "<por quê>"`.
- Nunca use Edit/Write em `areas/`: o hook de guarda barra, e o `memoro doutor` acusa.
- Regras: 1 fato = 1 arquivo; data absoluta; segredo só por caminho, nunca o valor.
- Recusa da porta (exit 1) é informação, não obstáculo: leia o motivo. "parecido com <id>" quer
  dizer `update`, não `--novo-mesmo-assim`.
- Referência ambígua (`rotina` existe em `casa/` e em `estudo/`): qualifique, `[[casa/rotina]]`.
```

## O hook de guarda (Claude Code)

`hooks/guarda_da_porta.py` é um `PreToolUse` que nega `Edit`, `Write`, `MultiEdit` e `NotebookEdit`
dentro de `$MEMORO_HOME/areas/` e devolve ao modelo a instrução de usar `memoro add/update/rm`.
Em `~/.claude/settings.json` (ou no `.claude/settings.json` do projeto):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit|NotebookEdit",
        "hooks": [
          {"type": "command", "command": "python3 /caminho/do/memoro/hooks/guarda_da_porta.py", "timeout": 5}
        ]
      }
    ]
  }
}
```

- A raiz vem de `MEMORO_HOME` (padrão `~/memoro`), nunca de caminho fixo. Exporte a variável no
  ambiente em que o Claude Code roda.
- Symlink e `..` são resolvidos dos dois lados antes de comparar, então atalho pra dentro de
  `areas/` também é negado, e `areas-velhas/` não é confundida com `areas/`.
- Entrada torta ou erro interno **deixa passar** (exit 0): o hook nunca trava o editor. A garantia
  de verdade não é o hook, é o doutor.
- Bloqueio é `exit 2` com a razão no stderr, que é o que o Claude Code mostra ao modelo.

Testar à mão:

```sh
echo '{"tool_name":"Write","tool_input":{"file_path":"'"$MEMORO_HOME"'/areas/casa/x.md"}}' \
  | python3 hooks/guarda_da_porta.py; echo "exit=$?"     # exit=2
```

O hook cobre as ferramentas de edição. Um `echo > arquivo` pelo shell passa por ele; é aí que entra:

## O doutor

```sh
python3 -m memoro doutor          # exit 0 limpo, 1 com achado
python3 -m memoro doutor --json
```

Confere cada `.md` de `areas/` contra o `hash_do_conteudo` do último evento ok daquele id no diário
e acusa: arquivo alterado fora da porta, arquivo sem evento de criação, evento sem arquivo,
frontmatter inválido, referência pendente ou ambígua, e linha corrompida no diário. Bom pra rodar no
fim da sessão do agente, num cron ou num `pre-commit` da raiz.

Editou no editor de propósito? Regularize, com motivo:

```sh
python3 -m memoro doutor --adotar casa/rotina --motivo "reescrevi no editor"
```

A adoção passa pelas mesmas regras da porta (segredo no texto é recusado) e fica no diário como
evento `adocao`.
