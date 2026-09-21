# O mapa

`memoro mapa` gera uma página estática com a memória inteira: um círculo por área, um menor por
subárea, um ponto por fato. É um arquivo só (`index.html`, com os dados e a biblioteca de layout
embutidos), abre por `file://`, funciona sem rede e não tem passo de build.

```sh
python3 -m memoro mapa                       # grava em $MEMORO_HOME/.memoro/mapa/
python3 -m memoro mapa --abrir               # grava e abre no navegador
python3 -m memoro mapa --servir              # http://127.0.0.1:8765, regenera quando um .md muda
python3 -m memoro mapa --servir 9000 --saida /tmp/mapa --titulo "Minha memória"
```

## Como ler

- **Cor é área.** O matiz sai do nome da área (estável entre gerações) e nunca cai em vermelho nem em
  âmbar: essas duas faixas são reservadas a estado.
- **Contorno tracejado vermelho: referência pendente** (um `[[link]]` ou `uses` que não achou alvo).
  **Pontilhado âmbar: referência ambígua** (nome solto que existe em duas áreas alheias). O estado
  tem segunda codificação além da cor: tracejado no nó, ícone e rótulo por extenso no painel.
- **Linha cheia é herança (`uses`), pontilhada é link do corpo.** A hierarquia área, subárea, fato
  não vira linha: ela já é o aninhamento dos círculos.
- **Homônimos** aparecem com o rótulo qualificado (`casa/rotina`, `estudo/rotina`).
- **Rótulo** quebra nos hífens em até três linhas, encurta com reticências e some abaixo de um raio
  mínimo; ao dar zoom ele volta. O nome inteiro está sempre no tooltip do nó e no painel.

Clique num fato: o painel mostra descrição, caminho, de quem ele herda, quem herda dele, links e
referências com problema; os vizinhos ficam destacados e o resto esmaece. `/` foca a busca, `Esc`
limpa a seleção, os botões de lente filtram pelos escopos do `lentes.json`. O cabeçalho conta fatos,
áreas, pendentes, ambíguos e órfãos (fato sem nenhuma ligação).

## O que entra na página

Só `id`, nome, descrição (cortada em 300 caracteres), área, subárea, caminho e as referências.
**O corpo do fato nunca entra no mapa.** Nome e descrição vêm de markdown escrito por você ou por um
agente, então são tratados como texto hostil: o JSON embutido tem todo `<` escapado e a página só
escreve no DOM por `textContent`, nunca por HTML. Há teste com `<script>` e `"><img onerror=` na
descrição, no título e no nome de lente.

## O servidor

`--servir` escuta **só em 127.0.0.1**, atende três rotas (`/`, `/index.html`, `/data.json`) e devolve
404 pra todo o resto, inclusive travessia com `..`. Responde com `ETag` e `304`; a página consulta o
`data.json` a cada 30 s e redesenha quando ele muda. A regeneração compara caminho, `mtime` e tamanho
de cada `.md` da raiz.

Pra publicar, copie a pasta de saída pra qualquer hospedagem de arquivo estático. Lembre que a página
leva o caminho absoluto da raiz (pro botão "abrir no editor").

## Demo

```sh
python3 demo/semear.py    # 42 fatos fictícios escritos PELA PORTA em demo/acervo/
python3 demo/gerar.py     # demo/mapa/index.html
```

A biblioteca de layout embutida é a d3-hierarchy (ISC); veja `LICENCAS-DE-TERCEIROS.md`.
