from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NoDoAdaptador:
    id: str
    nome: str
    descricao: str
    area: str
    subarea: object
    caminho: str
    pendentes: list = field(default_factory=list)
    ambiguos: list = field(default_factory=list)


class AdaptadorDoMapa:
    def __init__(self, grafo):
        self._grafo = grafo

    def nos(self):
        return [self._no(no) for no in self._grafo.nos()]

    def arestas(self):
        return [
            (aresta.origem, aresta.destino, aresta.tipo)
            for aresta in self._grafo.arestas()
            if aresta.tipo != "filho"
        ]

    def _no(self, no):
        return NoDoAdaptador(
            id=no.id,
            nome=no.nome,
            descricao=no.descricao,
            area=no.area.split("/", 1)[0],
            subarea=no.subarea or None,
            caminho=no.caminho,
            pendentes=list(dict.fromkeys(p.alvo for p in self._grafo.pendentes_de(no.id))),
            ambiguos=[
                {"ref": a.alvo, "candidatos": sorted(a.candidatas)}
                for a in self._grafo.ambiguos_de(no.id)
            ],
        )
