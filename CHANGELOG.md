# Changelog

Todas as mudanças relevantes do `memoro` ficam aqui. Formato
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/), versões em
[SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado

- `recall --list-lenses`: lista cada lente e os escopos dela.
- `recall --json` traz o corpo do fato.
- Corpus negativo e formatos extra na regra de segredo (tokens GitHub novos, texto que parece
  segredo e não é).
- Doutor D7: se a raiz é repo git, todo evento de escrita ok tem o commit `memoro <op> <id>` e
  vice-versa (`evento-sem-commit`, `commit-sem-evento`); fora de git, pula.
- `SPEC.md`: formato do fato e o que a porta recusa, com exemplos que `tests/test_spec.py` passa
  pela porta.
- Teste que fixa o sha256 do `d3-hierarchy.min.js` vendorizado, registrado em
  `LICENCAS-DE-TERCEIROS.md`.

### Mudado

- A porta grava o evento no `eventos.jsonl` (com fsync) antes do commit e commita fato e diário
  juntos. Crash no meio deixa evento sem commit, nunca commit sem evento; commit que falha mantém o
  evento e o doutor acusa.
- Adoção em lote cita cada id no corpo do commit (`memoro adocao <id>` por linha).

## [0.1.0] - 2026-09-21

### Adicionado

- Fato como `areas/<area>/<nome>.md` com frontmatter (`name`, `description`, `area`, `uses`,
  `scope`), id qualificado por área, relações tipadas.
- Porta única de escrita (`add`, `update`, `rm`, `purga`) com tranca, gravação atômica com fsync,
  lixeira com motivo e commit neutro por escrita quando a raiz é repo git.
- Validação: segredo, nome duplicado, área inexistente, relação desconhecida, `uses` pro vazio,
  quase-duplicata, motivo obrigatório no `rm`.
- Diário append-only `eventos.jsonl`, inclusive das recusas; comando `log`.
- Grafo com referência ambígua que avisa; lentes e `recall` por escopo com saltos, motivo e teto.
- Mapa estático offline (`mapa` / `map`, servidor em loopback) com d3-hierarchy 3.1.2 embutido.
- Doutor (`doutor` / `doctor`) confere `areas/` contra o diário, `--adotar` e `adotar-tudo` em
  lote.
- Hook de guarda pro Claude Code que nega escrita direta em `areas/`.
- README em inglês e português, licença GPL-3.0-or-later.

[Não lançado]: https://github.com/victorandraad/memoro/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/victorandraad/memoro/releases/tag/v0.1.0
