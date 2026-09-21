# Contribuindo

Python 3.9+, só biblioteca padrão. Teste que falha primeiro, depois a implementação.

```sh
python -m unittest
```

Cada teste monta o seu repositório de fatos num diretório temporário: nenhum teste lê nem escreve
fora dele. Classes recebem dependência pelo construtor, sem estado global.

## Privacidade do repo

`tests/test_privacidade.py` varre todo arquivo versionado (menos `LICENSE`, que leva o nome do
titular por obrigação legal) e reprova:

- travessão em qualquer arquivo (no código, só via `chr(0x2014)`);
- padrões genéricos por regex: caminho na home do superusuário, domínio interno, e-mail de
  provedor gratuito, id de card;
- **termos privados de quem mantém o fork**, guardados só como sha256. O teste nunca contém o termo,
  nem em pedaços: quem lê o arquivo não descobre o que está sendo protegido.

Fixture e exemplo são sempre fictícios: áreas `casa`, `estudo`, `hobby`, `trabalho` e fatos
inventados. Nada de nome de pessoa, produto, repo ou host.

### Acrescentar um termo privado

O arquivo é quebrado em tokens `[a-z0-9]+` minúsculos, e a varredura compara o hash de cada token
e de cada junção de 2 e 3 tokens vizinhos. Então o termo entra **minúsculo e sem separador**:
`Meu-Produto` vira `meuproduto`.

```sh
python3 -c "import hashlib,sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest())" meuproduto
```

Cole o hash em `HASHES_PROIBIDOS`, sem comentário dizendo o que ele é. Rode o comando num terminal
cujo histórico não vá pro repo. Se o teste acusar, a mensagem mostra arquivo, linha e o prefixo do
hash, nunca o termo.

Limite conhecido: palavra que só **contém** o termo (`meuprodutos`) não é acusada, e junção
`camelCase` também não. Registre as variações que importam como hashes separados.
