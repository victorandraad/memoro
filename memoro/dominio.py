from __future__ import annotations

import re
from dataclasses import dataclass


class IdInvalido(ValueError):
    """area ou nome fora do padrão de id."""


@dataclass(frozen=True)
class IdDeFato:
    area: str
    nome: str

    _SEGMENTO = re.compile(r"^[a-z0-9][a-z0-9-]*$")

    def __post_init__(self):
        partes = self.area.split("/")
        if len(partes) not in (1, 2):
            raise IdInvalido(self.area)
        for parte in partes + [self.nome]:
            if not self._SEGMENTO.fullmatch(parte):
                raise IdInvalido("%s/%s" % (self.area, self.nome))

    def __str__(self):
        return "%s/%s" % (self.area, self.nome)

    @classmethod
    def de_texto(cls, texto):
        area, _, nome = texto.rpartition("/")
        return cls(area, nome)

    @property
    def topo(self):
        return self.area.split("/", 1)[0]

    @property
    def subarea(self):
        if "/" not in self.area:
            return ""
        return self.area.split("/", 1)[1]

    @property
    def caminho(self):
        return "areas/%s/%s.md" % (self.area, self.nome)


@dataclass(frozen=True)
class Relacao:
    tipo: str
    alvo: str

    TIPOS = frozenset({
        "uses", "regra-de", "depende-de", "substitui", "contradiz", "detalha", "dono-de",
    })

    @classmethod
    def de_texto(cls, texto):
        tipo, sep, alvo = texto.partition(":")
        if not sep:
            return cls("uses", texto)
        return cls(tipo, alvo)

    def __str__(self):
        if self.tipo == "uses":
            return self.alvo
        return "%s:%s" % (self.tipo, self.alvo)

    @property
    def conhecida(self):
        return self.tipo in self.TIPOS


@dataclass(frozen=True)
class Fato:
    id: IdDeFato
    descricao: str
    corpo: str
    uses: tuple = ()
    scope: tuple = ()

    def __post_init__(self):
        object.__setattr__(self, "uses", tuple(self.uses))
        object.__setattr__(self, "scope", tuple(self.scope))

    @property
    def nome(self):
        return self.id.nome

    @property
    def area(self):
        return self.id.area

    @property
    def relacoes(self):
        return tuple(Relacao.de_texto(item) for item in self.uses)


@dataclass(frozen=True)
class Evento:
    ts: str
    usuario: str
    op: str
    id: str
    area: str
    resumo: str
    ok: bool
    motivo: str
    hash_do_conteudo: str
