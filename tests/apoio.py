"""Apoio dos testes: cada teste ganha uma raiz de fatos descartável, fictícia."""
from __future__ import annotations

import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def em_portugues():
    """setUpModule de quem afirma o texto em português: a saída padrão é inglês."""
    patch = mock.patch.dict(os.environ, {"MEMORO_LANG": "pt"})
    patch.start()
    unittest.addModuleCleanup(patch.stop)


class ComRaiz(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.raiz = Path(self._tmp.name) / "raiz"
        self.raiz.mkdir()

    def escrever(self, area, nome, desc="uma descrição", corpo="corpo\n", uses=None, scope=None):
        """Grava o .md cru, por fora da porta: é o estado que o teste encontra pronto."""
        pasta = self.raiz / "areas" / area
        pasta.mkdir(parents=True, exist_ok=True)
        linhas = ["name: %s" % nome, "description: %s" % desc, "area: %s" % area]
        if uses:
            linhas.append("uses: [%s]" % ", ".join(uses))
        if scope:
            linhas.append("scope: [%s]" % ", ".join(scope))
        caminho = pasta / (nome + ".md")
        caminho.write_text("---\n" + "\n".join(linhas) + "\n---\n\n" + corpo, encoding="utf-8")
        return caminho

    def cli(self, *argv, entrada=""):
        """(código, stdout, stderr) de uma execução da Cli sobre self.raiz."""
        from memoro.cli import Cli
        saida, erro = io.StringIO(), io.StringIO()
        codigo = Cli(entrada=io.StringIO(entrada), saida=saida, erro=erro,
                     ambiente=self._ambiente()).executar(list(argv))
        return codigo, saida.getvalue(), erro.getvalue()

    def _ambiente(self):
        ambiente = {"MEMORO_HOME": str(self.raiz), "USER": "teste"}
        if "MEMORO_LANG" in os.environ:
            ambiente["MEMORO_LANG"] = os.environ["MEMORO_LANG"]
        return ambiente
