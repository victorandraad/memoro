# memoro

Memória em arquivos markdown, um fato por arquivo, com **uma única porta de escrita**. Só biblioteca
padrão do Python (3.9+), sem banco, sem serviço.

- **Um fato = um `.md`** com frontmatter (`name`, `description`, `area`, e opcionais `uses`, `scope`).
- **Área = pasta.** `areas/<area>[/<subarea>]/<nome>.md`, no máximo um nível de subpasta.
- **Id qualificado por área.** `casa/rotina` e `trabalho/rotina` são dois fatos, os dois endereçáveis.
  Nome solto resolve primeiro na área de quem cita, depois se for único no repositório; se existir
  em duas áreas alheias, a referência é reportada como ambígua com as candidatas, e não some.
- **Toda escrita passa pela porta**: valida (segredo por regex de alta confiança, área inexistente,
  relação desconhecida, `uses` pro vazio, nome duplicado na área, quase-duplicata, motivo no `rm`),
  grava de forma atômica sob tranca de arquivo e registra no diário, **inclusive as recusas**.
- **`rm` não apaga**: move pra `areas/_lixeira/` com motivo e data. `purga` apaga o que venceu.
- **Se a raiz for um repo git**, cada escrita vira um commit só do que tocou, com a identidade do
  próprio repo. Se não for, nada é commitado.
- **Recall por lente**: `lentes.json` mapeia um nome de consumidor pra uma lista de escopos; o recall
  devolve os fatos do escopo, os filhos e o que eles herdam por `uses`, dizendo por que cada um entrou.

## Rodar sem instalar

```sh
git clone <este repo> memoro && cd memoro
export PYTHONPATH="$PWD"
python3 -m memoro init          # cria ~/memoro; mude com MEMORO_HOME=/outro/lugar
```

## Os cinco comandos do dia a dia

```sh
# 1. guardar: o corpo vem do stdin
echo "débito automático, vence todo dia 10" | python3 -m memoro add casa conta-de-luz --desc "conta de energia"

# 2. corrigir
python3 -m memoro update casa/conta-de-luz --desc "conta de energia, no débito"
echo "trocou de titular em 2031" | python3 -m memoro update conta-de-luz --anexar

# 3. lembrar só o que serve à decisão
python3 -m memoro recall --lens dia-a-dia
python3 -m memoro recall --scope casa/cozinha --saltos 2 --json

# 4. ver
python3 -m memoro ls casa
python3 -m memoro show casa/conta-de-luz

# 5. aposentar, com motivo
python3 -m memoro rm casa/conta-de-luz --motivo "mudei de casa"
```

E ainda: `log [--id X] [--recusas] [--desde AAAA-MM-DD]`, `purga [--dias 30]`. Todo comando aceita
`--json`. Saída `0` deu certo, `1` a porta recusou (o motivo vai pro stderr e pro diário), `2` uso errado.

`add` parecido demais com um fato da mesma área é recusado com `parecido com <id>`: use `update`, ou
passe `--novo-mesmo-assim`. `uses` aceita relação tipada: `--uses detalha:casa/gas,contradiz:forno`
(`regra-de`, `depende-de`, `substitui`, `contradiz`, `detalha`, `dono-de`; sem prefixo é herança).
No corpo, `[[nome]]` ou `[[area/nome]]` vira link no grafo.

## A raiz

```
$MEMORO_HOME/            (padrão: ~/memoro)
  areas/<area>/<nome>.md
  areas/_lixeira/
  lentes.json            {"dia-a-dia": ["casa", "trabalho"], "nenhuma": []}
  eventos.jsonl          diário append-only: ts, usuario, op, id, area, resumo, ok, motivo, hash_do_conteudo
```

`MEMORO_RECALL_CAP=40` põe um teto no recall; o que ficou de fora é contado na saída.

Limite conhecido: a tranca usa `fcntl`, então a porta é só pra Unix.

## Desenvolver

```sh
python3 -m unittest
```

Veja [CONTRIBUTING.md](CONTRIBUTING.md). Licença MIT.
