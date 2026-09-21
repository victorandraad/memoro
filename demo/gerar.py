"""Gera demo/mapa/ a partir de demo/acervo/. E um duble minimo do nucleo: o leitor de verdade substitui isto.

Uso: python3 demo/gerar.py [--servir [PORTA]] [--abrir]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

from memoro.mapa import ComandoMapa, ConfigDoMapa, GeradorDeMapa, No  # noqa: E402


class LeitorDaDemo:
    def __init__(self, raiz: Path):
        self.raiz = raiz

    def gerador(self) -> GeradorDeMapa:
        crus = {}
        for arquivo in sorted(self.raiz.rglob("*.md")):
            id_ = arquivo.relative_to(self.raiz).with_suffix("").as_posix()
            _, cabecalho, corpo = arquivo.read_text(encoding="utf-8").split("---", 2)
            campos = dict(l.split(": ", 1) for l in cabecalho.strip().splitlines())
            uses = [u.strip() for u in campos.get("uses", "[]").strip("[]").split(",") if u.strip()]
            crus[id_] = (campos, uses, re.findall(r"\[\[([^\]]+)\]\]", corpo))
        por_nome = {}
        for id_ in crus:
            por_nome.setdefault(id_.rsplit("/", 1)[-1], []).append(id_)
        nos, arestas = [], []
        for id_, (campos, uses, links) in crus.items():
            partes = id_.split("/")
            pendentes, ambiguos = [], []
            for ref, tipo in [(u, "uses") for u in uses] + [(l, "link") for l in links]:
                alvos = [ref] if ref in crus else por_nome.get(ref, [])
                if len(alvos) == 1:
                    arestas.append((id_, alvos[0], tipo))
                elif alvos:
                    ambiguos.append({"ref": ref, "candidatos": alvos})
                else:
                    pendentes.append(ref)
            nos.append(No(id=id_, nome=campos["name"], descricao=campos.get("description", ""), area=partes[0],
                          subarea=partes[1] if len(partes) == 3 else None, caminho=id_ + ".md",
                          pendentes=pendentes, ambiguos=ambiguos))
        lentes = json.loads((self.raiz / "lentes.json").read_text(encoding="utf-8"))
        return GeradorDeMapa(nos, arestas, lentes, ConfigDoMapa(titulo="Memória de exemplo"))


if __name__ == "__main__":
    raiz = AQUI / "acervo"
    comando = ComandoMapa(LeitorDaDemo(raiz).gerador, raiz)
    parser = argparse.ArgumentParser()
    comando.configurar(parser)
    parser.set_defaults(saida=str(AQUI / "mapa"))
    sys.exit(comando.executar(parser.parse_args()))
