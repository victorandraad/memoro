from __future__ import annotations

import difflib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Achado:
    recusa: bool
    mensagem: str


@dataclass(frozen=True)
class Pedido:
    op: str
    id: object
    fato: object
    motivo: str = ""
    existentes: tuple = ()
    areas: tuple = ()


class Regra(ABC):
    @abstractmethod
    def avaliar(self, pedido):
        raise NotImplementedError


class RegraDeSegredo(Regra):
    PADROES = {
        "github-token": re.compile(
            r"\b(?:gho|ghp|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b|github_pat_[A-Za-z0-9_]{22,}"),
        "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "chave-sk": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
        "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
        "private-key-block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\."),
    }

    def avaliar(self, pedido):
        if pedido.op not in ("add", "update"):
            return []
        texto = "%s\n%s" % (pedido.fato.descricao, pedido.fato.corpo)
        achados = []
        for n, linha in enumerate(texto.splitlines(), 1):
            if "pragma: allow-secret" in linha:
                continue
            for tipo, padrao in self.PADROES.items():
                if padrao.search(linha):
                    achados.append(Achado(True, "segredo do tipo %s na linha %d" % (tipo, n)))
        return achados


class RegraDeNomeDuplicado(Regra):
    def avaliar(self, pedido):
        if pedido.op != "add":
            return []
        for existente in pedido.existentes:
            if existente.id == pedido.id:
                return [Achado(True, "id já existe; use update")]
        return []


class RegraDeAreaExistente(Regra):
    def avaliar(self, pedido):
        if pedido.op != "add":
            return []
        topo = pedido.id.topo
        if topo in pedido.areas:
            return []
        existentes = sorted(set(pedido.areas))
        extra = ""
        parecidos = difflib.get_close_matches(topo, existentes, n=1, cutoff=0.5)
        if parecidos:
            extra = " (quis dizer %s?)" % parecidos[0]
        return [Achado(
            True,
            "área inexistente: %s%s; existentes: %s" % (topo, extra, ", ".join(existentes)),
        )]


class RegraDeRelacaoConhecida(Regra):
    def avaliar(self, pedido):
        achados = []
        for relacao in pedido.fato.relacoes:
            if not relacao.conhecida:
                achados.append(Achado(True, "relação desconhecida: %s" % relacao.tipo))
        return achados


class RegraDeMotivoNaRemocao(Regra):
    def avaliar(self, pedido):
        if pedido.op != "rm":
            return []
        if (pedido.motivo or "").strip():
            return []
        return [Achado(True, "rm exige motivo")]


class Validador:
    def __init__(self, regras):
        self.regras = tuple(regras)

    def avaliar(self, pedido):
        achados = []
        for regra in self.regras:
            achados.extend(regra.avaliar(pedido))
        return achados

    @classmethod
    def padrao(cls):
        return cls((
            RegraDeSegredo(),
            RegraDeNomeDuplicado(),
            RegraDeAreaExistente(),
            RegraDeRelacaoConhecida(),
            RegraDeMotivoNaRemocao(),
        ))
