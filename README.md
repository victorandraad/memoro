# memoro

**Durable facts in markdown, one write gate, no stack.** One file per fact, a live map, recall by
lens. Python 3.9+ standard library only: no database, no service, no `pip install` required.

The name is Esperanto for "memory". It is not a typo of *memory*, and it is not the MIT Media Lab
wearable or the EPFL heap profiler that share the word.

This is not an automatic session diary. A fact has to enter through a gate (secrets, near-duplicates
and empty links are refused) and leave as a `.md` file that `git log` can explain.

Portuguese: [README.pt.md](README.pt.md).

## What it is, what it is not

| you want | use | do not use memoro |
|---|---|---|
| "this repo uses pnpm", one way, refuse junk | **memoro** | AGENTS.md (it fits in context; two agents invent two rules) |
| a map of what the agent knows, as files | **memoro** | Obsidian, if a human edits all day |
| capture the session automatically | [claude-mem](https://github.com/thedotmack/claude-mem) | memoro has no session hook |
| remember a product customer, with an LLM | [Mem0](https://docs.mem0.ai/) | memoro does not extract facts from chat |
| the test proves the patch fixes the bug | [erratum](https://github.com/victorandraad/erratum) | memoro is not an error ledger |

## Install

Python 3.9+, Unix (Linux, macOS, WSL). The lock uses `fcntl`.

```sh
git clone https://github.com/victorandraad/memoro.git
cd memoro
export PYTHONPATH="$PWD"
python3 -m memoro init          # creates ~/memoro; override with MEMORO_HOME
python3 -m unittest
```

Optional global command:

```sh
pipx install git+https://github.com/victorandraad/memoro.git
```

## Five daily commands

```sh
echo "auto-pay, due on the 10th" | python3 -m memoro add casa conta-de-luz --desc "energy bill"
python3 -m memoro recall --lens dia-a-dia
python3 -m memoro ls casa
python3 -m memoro show casa/conta-de-luz
python3 -m memoro rm casa/conta-de-luz --motivo "moved house"
```

Also: `map` / `mapa`, `doctor` / `doutor`, `adopt-all` / `adotar-tudo`, `log`, `purge` / `purga`.
Every command accepts `--json`. Exit `0` ok, `1` the gate refused or the doctor found something,
`2` bad usage.

```sh
python3 -m memoro map --servir      # http://127.0.0.1:8765
python3 -m memoro doctor            # exit 0 clean, 1 finding
```

## Contributing

PRs welcome. Failing test first. Fixtures are always fictional (`casa`, `estudo`, `hobby`).

```sh
python3 -m unittest
```

Useful PRs: a duplicate the gate let through, a silent `doctor`, a recall that loaded too much.
See [CONTRIBUTING.md](CONTRIBUTING.md) ([Portuguese](CONTRIBUTING.pt.md)).

## License

[GPL-3.0](LICENSE). Use, modify, distribute. If you distribute a derivative, its code stays under
the GPL: the idea stays public. Third-party map code: [LICENCAS-DE-TERCEIROS.md](LICENCAS-DE-TERCEIROS.md).

The write gate, doctor, lenses, import and honest limits are documented in
[README.pt.md](README.pt.md) (Portuguese, same flags).
