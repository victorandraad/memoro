"""Extrai os blocos ```fato ... do SPEC.md e confere contra a porta de verdade."""
from __future__ import annotations

import re
from pathlib import Path

from memoro.formato import LeitorDeFrontmatter
from memoro.porta import PortaDeEscrita, Recusa
from memoro.repositorio import RepositorioDeFatos
from tests.apoio import ComRaiz

SPEC = Path(__file__).resolve().parent.parent / "SPEC.md"

_BLOCO = re.compile(r"```fato (\w+)(?::(.*?))?\n(.*?)\n```", re.S)


def _blocos():
    texto = SPEC.read_text(encoding="utf-8")
    return [(tipo, motivo, conteudo) for tipo, motivo, conteudo in _BLOCO.findall(texto)]


class TestSpec(ComRaiz):
    def _porta(self):
        repo = RepositorioDeFatos(self.raiz)
        repo.inicializar()
        return PortaDeEscrita.padrao(self.raiz, usuario="teste")

    def _semear_acervo(self, porta):
        for tipo, _, conteudo in _blocos():
            if tipo != "acervo":
                continue
            campos, corpo = LeitorDeFrontmatter().ler(conteudo)
            porta.add(campos["area"], campos["name"], campos["description"], corpo,
                      uses=tuple(campos.get("uses", [])), scope=tuple(campos.get("scope", [])))

    def test_specs(self):
        blocos = _blocos()
        validos = [b for b in blocos if b[0] == "valido"]
        invalidos = [b for b in blocos if b[0] == "invalido"]
        self.assertGreater(len(validos), 0, "SPEC sem blocos válidos")
        self.assertGreater(len(invalidos), 0, "SPEC sem blocos inválidos")

        for i, (tipo, motivo, conteudo) in enumerate(validos):
            with self.subTest(valido=i):
                self.setUp()
                porta = self._porta()
                self._semear_acervo(porta)
                campos, corpo = LeitorDeFrontmatter().ler(conteudo)
                porta.add(campos["area"], campos["name"], campos["description"], corpo,
                          uses=tuple(campos.get("uses", [])), scope=tuple(campos.get("scope", [])))

        for i, (tipo, motivo, conteudo) in enumerate(invalidos):
            with self.subTest(invalido=i, motivo=motivo):
                self.setUp()
                porta = self._porta()
                self._semear_acervo(porta)
                campos, corpo = LeitorDeFrontmatter().ler(conteudo)
                with self.assertRaises(Recusa) as ctx:
                    porta.add(campos["area"], campos["name"], campos["description"], corpo,
                              uses=tuple(campos.get("uses", [])), scope=tuple(campos.get("scope", [])))
                self.assertIn(motivo, str(ctx.exception))
