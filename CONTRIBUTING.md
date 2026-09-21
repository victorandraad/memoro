# Contributing

PRs welcome. Python 3.9+, standard library only. Failing test first, then the implementation.
License [GPL-3.0](LICENSE): distributed derivatives stay GPL.

Portuguese: [CONTRIBUTING.pt.md](CONTRIBUTING.pt.md).

```sh
python -m unittest
```

Each test builds its own fact repo in a temp directory. Nothing reads or writes outside it.
Classes take dependencies in the constructor; no global state.

## Repo privacy

`tests/test_privacidade.py` walks every versioned file (except `LICENSE`) and fails on em dashes,
generic identifying regexes, and private maintainer tokens stored only as sha256.

Fixtures and examples are always fictional: areas `casa`, `estudo`, `hobby`, `trabalho` and made-up
facts. No real person, product, repo or host names.

How to add a private term: see [CONTRIBUTING.pt.md](CONTRIBUTING.pt.md).
