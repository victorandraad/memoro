from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from memoro.dominio import Relacao
from memoro.mensagens import t


@dataclass(frozen=True, order=True)
class No:
    id: str
    nome: str
    descricao: str
    area: str
    subarea: str
    caminho: str

    def __post_init__(self):
        object.__setattr__(self, "descricao", self.descricao[:300])


@dataclass(frozen=True, order=True)
class Aresta:
    origem: str
    destino: str
    tipo: str


@dataclass(frozen=True, order=True)
class Pendente:
    citado_em: str
    alvo: str
    tipo: str


@dataclass(frozen=True, order=True)
class Ambiguo:
    citado_em: str
    alvo: str
    tipo: str
    candidatas: tuple

    def __post_init__(self):
        object.__setattr__(self, "candidatas", tuple(self.candidatas))

    @property
    def mensagem(self):
        opcoes = t("ou").join(self.candidatas)
        if self.tipo == "link":
            return t("ambiguo-link", self.alvo, self.citado_em, opcoes)
        return t("ambiguo-uses", self.alvo, self.citado_em, opcoes)


@dataclass(frozen=True)
class Resolucao:
    id: object
    candidatas: tuple

    def __post_init__(self):
        object.__setattr__(self, "candidatas", tuple(self.candidatas))


class GrafoDeFatos:
    # ponytail: regex nao cobre fence sem fechar; upgrade = lexer
    _CODIGO = re.compile(r"```.*?```|`[^`\n]+`", re.S)
    _LINK = re.compile(r"\[\[([a-z0-9-]+(?:/[a-z0-9-]+){0,2})\]\]")

    def __init__(self, fatos):
        vistos = {}
        for fato in fatos:
            ident = str(fato.id)
            if ident not in vistos:
                vistos[ident] = fato
        self._fatos = tuple(vistos.values())
        self._nos = tuple(sorted(
            No(
                str(fato.id),
                fato.nome,
                fato.descricao,
                fato.area,
                fato.id.subarea,
                fato.id.caminho,
            )
            for fato in self._fatos
        ))
        self._por_id = {no.id: no for no in self._nos}
        self._arestas, self._pendentes, self._ambiguos = self._montar()

    def nos(self):
        return list(self._nos)

    def arestas(self):
        return list(self._arestas)

    def pendentes(self):
        return list(self._pendentes)

    def ambiguos(self):
        return list(self._ambiguos)

    def pendentes_de(self, ident):
        ident = str(ident)
        return [p for p in self._pendentes if p.citado_em == ident]

    def ambiguos_de(self, ident):
        ident = str(ident)
        return [a for a in self._ambiguos if a.citado_em == ident]

    def resolver(self, ref, area_de_quem_cita):
        # ponytail: varredura linear por resolucao; indice nome->lista se o acervo crescer
        if "/" in ref:
            if ref in self._por_id:
                return Resolucao(ref, ())
            return Resolucao(None, ())
        na_area = None
        outras = []
        for no in self._nos:
            if no.nome != ref:
                continue
            if no.area == area_de_quem_cita:
                na_area = no
            else:
                outras.append(no)
        if na_area is not None:
            return Resolucao(na_area.id, ())
        if len(outras) == 1:
            return Resolucao(outras[0].id, ())
        if len(outras) > 1:
            return Resolucao(None, tuple(sorted(n.id for n in outras)))
        return Resolucao(None, ())

    def como_dict(self):
        return {
            "nos": [asdict(n) for n in self._nos],
            "arestas": [asdict(a) for a in self._arestas],
            "pendentes": [asdict(p) for p in self._pendentes],
            "ambiguos": [
                {
                    "citado_em": a.citado_em,
                    "alvo": a.alvo,
                    "tipo": a.tipo,
                    "candidatas": list(a.candidatas),
                }
                for a in self._ambiguos
            ],
        }

    def _montar(self):
        arestas = set()
        pendentes = set()
        ambiguos = set()
        for fato in self._fatos:
            origem = str(fato.id)
            for item in fato.uses:
                relacao = Relacao.de_texto(item)
                if not relacao.conhecida:
                    pendentes.add(Pendente(origem, item, "uses"))
                    continue
                self._aplicar(
                    origem, relacao.alvo, relacao.tipo, "uses", fato.area,
                    arestas, pendentes, ambiguos,
                )
            for ref in self._referencias_do_corpo(fato.corpo):
                self._aplicar(
                    origem, ref, "link", "link", fato.area,
                    arestas, pendentes, ambiguos,
                )
            if fato.id.subarea and origem != fato.area and fato.area in self._por_id:
                arestas.add(Aresta(fato.area, origem, "filho"))
        return tuple(sorted(arestas)), tuple(sorted(pendentes)), tuple(sorted(ambiguos))

    def _aplicar(self, origem, ref, tipo_aresta, tipo_citacao, area, arestas, pendentes, ambiguos):
        resolucao = self.resolver(ref, area)
        if resolucao.id is not None:
            if resolucao.id != origem:
                arestas.add(Aresta(origem, resolucao.id, tipo_aresta))
            return
        if resolucao.candidatas:
            ambiguos.add(Ambiguo(origem, ref, tipo_citacao, resolucao.candidatas))
            return
        pendentes.add(Pendente(origem, ref, tipo_citacao))

    def _referencias_do_corpo(self, corpo):
        limpo = self._CODIGO.sub("", corpo)
        return self._LINK.findall(limpo)
