"""Texto humano da CLI: inglês por padrão, português com MEMORO_LANG=pt. Chave -> (en, pt)."""
from __future__ import annotations

import os

MENSAGENS = {
    # cli
    "recusado": ("refused: %s", "recusado: %s"),
    "aviso": ("warning: %s", "aviso: %s"),
    "limpo": ("clean", "limpo"),
    "adotados": ("%d adopted", "%d adotados"),
    "adotar-sem-motivo": ("doctor --adopt requires --reason", "doutor --adotar exige --motivo"),
    "recall-tudo": ("all", "tudo"),
    "recall-1": ("# recall: %s (1 fact)", "# recall: %s (1 fatos)"),
    "recall-n": ("# recall: %s (%d facts)", "# recall: %s (%d fatos)"),
    "recall-cortados": ("# recall: %s (%d facts, %d cut by the cap)", "# recall: %s (%d fatos, %d cortados pelo teto)"),
    "motivo-filho": ("child", "filho"),
    "motivo-herda": ("inherits", "herda"),
    "titulo-do-mapa": ("Memory", "Memória"),
    # validacao
    "segredo": ("secret of type %s in %s, line %d", "segredo do tipo %s em %s, linha %d"),
    "campo-descricao": ("description", "descrição"),
    "campo-corpo": ("body", "corpo"),
    "id-existe": ("id already exists; use update", "id já existe; use update"),
    "area-inexistente": ("unknown area: %s%s; existing: %s", "área inexistente: %s%s; existentes: %s"),
    "quis-dizer": (" (did you mean %s?)", " (quis dizer %s?)"),
    "relacao-desconhecida": ("unknown relation: %s", "relação desconhecida: %s"),
    "rm-sem-motivo": ("rm requires --reason", "rm exige motivo"),
    "uses-vazio": ("uses points to nothing: %s", "uses aponta pro vazio: %s"),
    "parecido": (
        "similar to %s, use update instead or pass --new-anyway",
        "parecido com %s: use update ou passe --novo-mesmo-assim",
    ),
    # grafo
    "ou": (" or ", " ou "),
    "ambiguo-link": ("ambiguous: [[%s]] in %s could be %s", "ambíguo: [[%s]] em %s pode ser %s"),
    "ambiguo-uses": ("ambiguous: uses %s in %s could be %s", "ambíguo: uses %s em %s pode ser %s"),
    # porta
    "adocao-sem-motivo": ("adoption requires --reason", "adoção exige motivo"),
    "frontmatter-invalido": ("invalid frontmatter", "frontmatter inválido"),
    "sem-commit": ("written to disk, not committed: %s", "gravado em disco, sem commit: %s"),
    # repositorio
    "nao-encontrado": ("fact not found: %s%s", "fato não encontrado: %s%s"),
    "referencia-ambigua": ("ambiguous reference: %s", "referência ambígua: %s"),
    # lentes
    "lente-desconhecida": ("unknown lens: %s\navailable lenses: %s", "lente desconhecida: %s\nlentes disponíveis: %s"),
    "lente-sem-pasta": ("lens %r: target has no folder: %s", "lente %r: alvo sem pasta: %s"),
    # formato
    "sem-frontmatter": ("no frontmatter block", "sem bloco de frontmatter"),
    "name-diferente": ("name differs from file name", "name diferente do arquivo"),
    "area-diferente": ("area differs from folder", "area diferente da pasta"),
    # doutor: detalhes
    "linha": ("line %d", "linha %d"),
    "hash-diverge": ("hash differs from event log", "hash diverge do diário"),
    "sem-evento-vivo": ("file has no live event in the gate", "arquivo sem evento vivo na porta"),
    "arquivo-ausente": ("file missing", "arquivo ausente"),
    "evento-sem-commit": ("%s has no git commit", "%s sem commit no git"),
    "commit-sem-evento": ("commit memoro %s has no event in the log", "commit memoro %s sem evento no diário"),
    "utf8-invalido": ("invalid utf-8", "utf-8 inválido"),
    "nome-invalido": ("file name is not a valid id", "nome de arquivo não é id válido"),
    # help
    "ajuda-memoro": ("memoro: durable facts in markdown, one write gate", "memoro: fato durável em markdown, uma porta de escrita"),
    "ajuda-init": ("create the memory root", "cria a raiz da memória"),
    "ajuda-show": ("print one fact", "mostra um fato"),
    "ajuda-ls": ("list facts, optionally under an area", "lista fatos, opcionalmente de uma área"),
    "ajuda-recall": ("facts for a lens or scope, with children and inherited", "fatos de uma lente ou escopo, com filhos e herdados"),
    "ajuda-add": ("write a new fact through the gate (body from stdin)", "grava um fato novo pela porta (corpo no stdin)"),
    "ajuda-update": ("change a fact through the gate", "altera um fato pela porta"),
    "ajuda-rm": ("move a fact to the trash, with a reason", "move um fato pra lixeira, com motivo"),
    "ajuda-purga": ("delete trashed facts older than N days", "apaga da lixeira o que passou de N dias"),
    "ajuda-log": ("show the event log", "mostra o diário de eventos"),
    "ajuda-mapa": ("build or serve the memory map", "gera ou serve o mapa da memória"),
    "ajuda-doutor": ("check files against the event log and git", "confere arquivos contra o diário e o git"),
    "ajuda-adotar-tudo": ("adopt every file the doctor flags", "adota todo arquivo que o doutor acusa"),
    "ajuda-novo": ("write even if a similar fact exists", "grava mesmo com fato parecido"),
    "ajuda-motivo": ("why (required)", "por quê (obrigatório)"),
    "ajuda-adotar": ("adopt a file changed outside the gate", "adota um arquivo alterado fora da porta"),
}

# tipo do achado do doutor: código fixo no --json, rótulo inglês só na saída humana
TIPOS_EN = {
    "sem-evento": "no-event",
    "alterado-fora-da-porta": "changed-outside-gate",
    "evento-sem-arquivo": "event-without-file",
    "frontmatter-invalido": "invalid-frontmatter",
    "diario-corrompido": "corrupt-log",
    "pendente": "pending",
    "ambiguo": "ambiguous",
    "evento-sem-commit": "event-without-commit",
    "commit-sem-evento": "commit-without-event",
}

# a Cli recebe o ambiente injetado; ela sobrescreve aqui durante a execução
sobrescrita = None


def portugues():
    valor = sobrescrita if sobrescrita is not None else os.environ.get("MEMORO_LANG", "")
    return valor.strip().lower().startswith("pt")


def t(chave, *args):
    texto = MENSAGENS[chave][1 if portugues() else 0]
    return texto % args if args else texto


def tipo(codigo):
    return codigo if portugues() else TIPOS_EN.get(codigo, codigo)
