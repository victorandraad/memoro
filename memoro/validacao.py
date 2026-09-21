from __future__ import annotations

import difflib
import re
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass

from memoro.dominio import Relacao
from memoro.grafo import GrafoDeFatos


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
    novo_mesmo_assim: bool = False


class Regra(ABC):
    @abstractmethod
    def avaliar(self, pedido):
        raise NotImplementedError


class RegraDeSegredo(Regra):
    PADROES = {
        "github-token": re.compile(
            r"\b(?:gho|ghp|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b|github_pat_[A-Za-z0-9_]{22,}"),
        "aws-access-key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        "chave-sk": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
        "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
        "private-key-block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\."),
    }

    def avaliar(self, pedido):
        if pedido.op not in ("add", "update"):
            return []
        # uses e scope também viram arquivo e motivo de recusa no diário: passam pela mesma peneira
        campos = (
            ("descrição", pedido.fato.descricao),
            ("uses", "\n".join(pedido.fato.uses)),
            ("scope", "\n".join(pedido.fato.scope)),
            ("corpo", pedido.fato.corpo),
        )
        achados = []
        for campo, texto in campos:
            for n, linha in enumerate(texto.splitlines(), 1):
                if "pragma: allow-secret" in linha:
                    continue
                for tipo, padrao in self.PADROES.items():
                    if padrao.search(linha):
                        achados.append(Achado(True, "segredo do tipo %s em %s, linha %d" % (tipo, campo, n)))
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


class RegraDeReferencias(Regra):
    def avaliar(self, pedido):
        if pedido.op not in ("add", "update"):
            return []
        fatos = [f for f in pedido.existentes if str(f.id) != str(pedido.id)]
        fatos.append(pedido.fato)
        grafo = GrafoDeFatos(fatos)
        ident = str(pedido.id)
        achados = []
        for pendente in grafo.pendentes_de(ident):
            if pendente.tipo != "uses":
                continue
            if not Relacao.de_texto(pendente.alvo).conhecida:
                continue
            achados.append(Achado(True, "uses aponta pro vazio: %s" % pendente.alvo))
        for ambiguo in grafo.ambiguos_de(ident):
            achados.append(Achado(False, ambiguo.mensagem))
        return achados


class RegraDeQuaseDuplicata(Regra):
    # ponytail: O(n) por area, comparacao de caracteres, nao de sentido; serie (fato-0, fato-1) nao conta; upgrade = embedding
    CORTE_NOME = 0.8
    CORTE_DESCRICAO = 0.8

    def avaliar(self, pedido):
        if pedido.op != "add" or pedido.novo_mesmo_assim:
            return []
        nome = pedido.fato.nome
        descricao = self._normalizar(pedido.fato.descricao)
        achados = []
        for existente in pedido.existentes:
            if existente.area != pedido.fato.area:
                continue
            if self._parecido(nome, existente.nome, self.CORTE_NOME):
                achados.append(self._recusa(existente))
                continue
            outra = self._normalizar(existente.descricao).strip()
            # descrição vazia não diz nada: duas vazias não são o mesmo fato
            if descricao.strip() and outra and self._parecido(descricao, outra, self.CORTE_DESCRICAO):
                achados.append(self._recusa(existente))
        return achados

    def _parecido(self, a, b, corte):
        if a == b:
            return True
        if self._so_digito_muda(a, b):
            return False
        return difflib.SequenceMatcher(None, a, b).ratio() >= corte

    def _so_digito_muda(self, a, b):
        return "".join(c for c in a if not c.isdigit()) == "".join(c for c in b if not c.isdigit())

    def _recusa(self, existente):
        return Achado(
            True,
            "parecido com %s: use update ou passe --novo-mesmo-assim" % existente.id,
        )

    def _normalizar(self, texto):
        texto = unicodedata.normalize("NFD", texto.lower())
        return "".join(c for c in texto if unicodedata.category(c) != "Mn")


class Validador:
    def __init__(self, regras):
        self.regras = tuple(regras)

    def avaliar(self, pedido):
        achados = []
        for regra in self.regras:
            novos = regra.avaliar(pedido)
            achados.extend(novos)
            # segredo acusado: para aqui, porque as regras seguintes citam a entrada na mensagem
            # e a mensagem vai pro diário
            if isinstance(regra, RegraDeSegredo) and any(a.recusa for a in novos):
                break
        return achados

    @classmethod
    def padrao(cls):
        return cls((
            RegraDeSegredo(),
            RegraDeNomeDuplicado(),
            RegraDeAreaExistente(),
            RegraDeRelacaoConhecida(),
            RegraDeMotivoNaRemocao(),
            RegraDeReferencias(),
            RegraDeQuaseDuplicata(),
        ))
