"""Gera demo/mapa/ a partir de demo/acervo/ pelo núcleo real.

Uso: python3 demo/gerar.py [--servir [PORTA]] [--abrir]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

from memoro.adaptador_do_mapa import AdaptadorDoMapa  # noqa: E402
from memoro.grafo import GrafoDeFatos  # noqa: E402
from memoro.lentes import Lentes  # noqa: E402
from memoro.mapa import ComandoMapa, ConfigDoMapa, GeradorDeMapa  # noqa: E402
from memoro.repositorio import RepositorioDeFatos  # noqa: E402


class FabricaDaDemo:
    def __init__(self, raiz):
        self._raiz = Path(raiz)

    def __call__(self):
        raiz = self._raiz
        repo = RepositorioDeFatos(raiz)
        adaptador = AdaptadorDoMapa(GrafoDeFatos(repo.todos()))
        lentes = Lentes(raiz / "lentes.json", repo.areas())
        return GeradorDeMapa(
            adaptador.nos(),
            adaptador.arestas(),
            dict(lentes._mapa),
            ConfigDoMapa(titulo="Memória de exemplo", raiz=str(raiz)),
        )


if __name__ == "__main__":
    raiz = AQUI / "acervo"
    comando = ComandoMapa(FabricaDaDemo(raiz), raiz)
    parser = argparse.ArgumentParser()
    comando.configurar(parser)
    parser.set_defaults(saida=str(AQUI / "mapa"))
    sys.exit(comando.executar(parser.parse_args()))
