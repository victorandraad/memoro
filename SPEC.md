# SPEC do fato memoro

## Formato do fato

Um fato é um arquivo `areas/<area>/<nome>.md`, id qualificado como `area/nome`
(a área pode ter subárea, `area/subarea/nome`, criada sob demanda). O arquivo
tem frontmatter obrigatório entre `---`:

- `name`: igual ao nome do arquivo (sem `.md`).
- `description`: uma linha.
- `area`: igual à pasta (`areas/<area>/`).

Campos opcionais (ver `memoro/formato.py` e `memoro/dominio.py`):

- `uses`: lista `[a, b]` ou em linhas `- item`. Cada item é uma relação: sem
  `tipo:` é `uses` puro (referência a outro fato); com `tipo:alvo` é uma
  relação tipada. Tipos conhecidos (`Relacao.TIPOS` em `dominio.py`):
  `regra-de`, `depende-de`, `substitui`, `contradiz`, `detalha`, `dono-de`
  (e o implícito `uses`).
- `scope`: lista, mesmo formato de `uses`.

Depois do frontmatter, o corpo em texto livre.

## O que a porta recusa

A porta (`PortaDeEscrita.add`) roda `Validador.padrao()`
(`memoro/validacao.py`, linhas ~181-206) mais a conversão de `IdInvalido`
(`memoro/dominio.py`) em `Recusa`. Na ordem:

- **IdInvalido** (`dominio.py`): área ou nome fora de `[a-z0-9][a-z0-9-]*`
  (por segmento). Mensagem: o texto do id inválido (ex: `"Casa"` ou
  `"casa//x"`), sem palavra fixa.
- **RegraDeSegredo**: acha padrão de token/chave/JWT/private-key em
  descrição, uses, scope ou corpo. Mensagem: `"segredo do tipo <tipo> em
  <campo>, linha <n>"`.
- **RegraDeNomeDuplicado**: id já existe. Mensagem: `"id já existe; use
  update"`.
- **RegraDeAreaExistente**: área-topo não está entre as áreas já existentes
  no acervo. Mensagem: `"área inexistente: <topo>...; existentes: ..."`.
- **RegraDeRelacaoConhecida**: tipo de relação em `uses` fora de
  `Relacao.TIPOS`. Mensagem: `"relação desconhecida: <tipo>"`.
- **RegraDeMotivoNaRemocao**: só vale para `rm` sem motivo (não testável via
  `add`).
- **RegraDeReferencias**: item de `uses` (relação tipo `uses` puro) que não
  aponta pra nenhum fato existente nem para o próprio pedido. Mensagem:
  `"uses aponta pro vazio: <alvo>"`.
- **RegraDeQuaseDuplicata**: nome ou descrição (normalizados, sem acento)
  muito parecidos (`ratio >= 0.8`) com um fato já existente na mesma área.
  Mensagem: `"parecido com <id>: use update ou passe --novo-mesmo-assim"`.

## Acervo dos exemplos

Fatos que já existem antes de rodar os exemplos abaixo (criados via
`PortaDeEscrita.add` antes de cada caso que depende de estado):

```fato acervo
---
name: rotina
description: rotina da casa
area: casa
---

corpo da rotina.
```

```fato acervo
---
name: fogao
description: fogão de quatro bocas
area: casa
---

acende com fósforo.
```

## Exemplos válidos

```fato valido
---
name: geladeira
description: geladeira duas portas
area: casa
---

corpo da geladeira.
```

```fato valido
---
name: chuveiro
description: chuveiro elétrico
area: casa
uses: [casa/fogao]
---

corpo do chuveiro.
```

```fato valido
---
name: manutencao
description: manutenção do fogão
area: casa
uses: [regra-de:casa/fogao]
---

detalhe da manutenção, relação tipada válida.
```

```fato valido
---
name: piso
description: piso da cozinha, cerâmica
area: casa
scope: [casa]
---

corpo do piso.
```

```fato valido
---
name: forno
description: forno elétrico embutido
area: casa/cozinha
---

subárea nasce sob demanda.
```

## Exemplos inválidos

```fato invalido:segredo
---
name: deploy
description: chave do servidor
area: casa
---

aws_access_key_id = AKIAIOSFODNN7EXAMPLE
```

```fato invalido:área
---
name: caldeira
description: caldeira industrial
area: predio
---

corpo qualquer.
```

```fato invalido:uses aponta pro vazio
---
name: torneira
description: torneira da pia
area: casa
uses: [casa/inexistente]
---

corpo qualquer.
```

```fato invalido:relação desconhecida
---
name: varal
description: varal de roupas
area: casa
uses: [inventada:casa/fogao]
---

corpo qualquer.
```

```fato invalido:parecido com
---
name: fogao2
description: fogão de quatro bocas
area: casa
---

corpo quase igual ao existente.
```

```fato invalido:id já existe
---
name: rotina
description: outra rotina, bem diferente
area: casa
---

corpo qualquer.
```

```fato invalido:casa/oficina/fundo
---
name: mesa
description: mesa de jantar
area: casa/oficina/fundo
---

corpo qualquer, área com mais de dois níveis é id inválido.
```
