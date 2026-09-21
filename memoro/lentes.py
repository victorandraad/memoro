from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class ErroDeLente(Exception):
    """lente desconhecida ou alvo que não é pasta existente."""


class Lentes:
    def __init__(self, caminho, areas):
        self._areas = frozenset(areas)
        caminho = Path(caminho)
        if not caminho.is_file():
            self._mapa = {}
            return
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
        self._mapa = dict(bruto) if isinstance(bruto, dict) else {}

    def nomes(self):
        return sorted(self._mapa)

    def escopos(self, lente):
        if lente not in self._mapa:
            disponiveis = ", ".join(self.nomes())
            raise ErroDeLente(
                "lente desconhecida: %s\nlentes disponíveis: %s" % (lente, disponiveis)
            )
        alvos = [str(a) for a in list(self._mapa[lente])]
        ruins = [a for a in alvos if a.strip("/") not in self._areas]
        if ruins:
            raise ErroDeLente(
                "lente %r: alvo sem pasta: %s" % (lente, ", ".join(sorted(ruins)))
            )
        return alvos


@dataclass(frozen=True)
class ItemDeRecall:
    fato: object
    motivo: str


@dataclass(frozen=True)
class ResultadoDeRecall:
    itens: tuple
    cortados: int

    def __post_init__(self):
        object.__setattr__(self, "itens", tuple(self.itens))


class Recall:
    def __init__(self, fatos, grafo, teto=None):
        self._fatos = tuple(fatos)
        self._por_id = {str(f.id): f for f in self._fatos}
        self._grafo = grafo
        self._teto = teto

    def por_escopos(self, escopos, saltos=1):
        selecionados = self._selecionar(escopos)
        itens = [ItemDeRecall(fato, "escopo") for fato in selecionados]
        vistos = {str(fato.id) for fato in selecionados}
        borda = set(vistos)
        arestas = self._grafo.arestas()
        for _ in range(max(0, saltos)):
            nova = set()
            for aresta in arestas:
                if aresta.tipo == "link":
                    continue
                if aresta.origem not in borda or aresta.destino in vistos:
                    continue
                fato = self._por_id.get(aresta.destino)
                if fato is None:
                    continue
                itens.append(ItemDeRecall(fato, self._motivo(aresta.tipo)))
                vistos.add(aresta.destino)
                nova.add(aresta.destino)
            borda = nova
        cortados = 0
        teto = self._teto
        if teto is not None and teto > 0 and len(itens) > teto:
            cortados = len(itens) - teto
            itens = itens[:teto]
        return ResultadoDeRecall(tuple(itens), cortados)

    def _selecionar(self, escopos):
        if escopos is None:
            escolhidos = list(self._fatos)
        elif not escopos:
            escolhidos = []
        else:
            escolhidos = [fato for fato in self._fatos if self._casa(fato, escopos)]
        escolhidos.sort(key=lambda f: str(f.id))
        return escolhidos

    def _casa(self, fato, escopos):
        efetivos = self._escopos_efetivos(fato)
        for escopo in escopos:
            alvo = (escopo or "").strip("/")
            if not alvo:
                continue
            if "/" in alvo:
                if (fato.area + "/").startswith(alvo + "/"):
                    return True
            elif alvo in efetivos:
                return True
        return False

    def _escopos_efetivos(self, fato):
        if fato.scope:
            return tuple(fato.scope)
        return (fato.id.topo,)

    def _motivo(self, tipo):
        if tipo == "filho":
            return "filho"
        if tipo == "uses":
            return "herda"
        return tipo
