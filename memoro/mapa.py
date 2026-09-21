"""Gera o mapa estático da memória (index.html + data.json) e o serve em loopback.

Contrato de entrada (o gerador so le estes campos, nunca o corpo do fato):

No / NoDoMapa
    id         str  qualificado: "area/nome" ou "area/sub/nome"
    nome       str  stem do fato
    descricao  str  texto curto; o mapa corta em 300 caracteres
    area       str
    subarea    str | None
    caminho    str  relativo a raiz da memória
    pendentes  lista[str]  refs que nao resolveram (default [])
    ambiguos   lista[{"ref": str, "candidatos": lista[str]}]  (default [])

arestas
    sequencia de tuplas (origem_id, destino_id, tipo) com tipo "uses" ou "link".
    Arestas cuja ponta nao existe em nos sao descartadas.

lentes
    dict[str, lista[str]]  nome da lente -> escopos ("area" ou "area/sub").

ConfigDoMapa
    titulo, url_base_de_edicao=None, esquema_do_editor="vscode",
    intervalo_de_atualizacao_s=30, raiz=None
    raiz absoluta so entra no JSON para o editor / copiar caminho; o corpo
    do fato nunca entra no mapa.
"""
from __future__ import annotations

import hashlib
import html as html_mod
import json
import os
import threading
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable, Optional, Protocol, Sequence
from urllib.parse import urlsplit

PASSO_DE_OURO = 137.508
DESLOCAMENTO_DA_PALETA = 0
# arco livre: pula vermelho 345-20 (pendente) e ambar 25-55 (ambiguo), com 15 graus de margem
INICIO_DO_ARCO_LIVRE = 70
ARCO_LIVRE = 265
PASSO_NO_ARCO_LIVRE = PASSO_DE_OURO * ARCO_LIVRE / 360
LIMITE_DA_DESCRICAO = 300
ROTAS_SERVICAS = ("/", "/index.html", "/data.json")


class NoDoMapa(Protocol):
    id: str
    nome: str
    descricao: str
    area: str
    subarea: Optional[str]
    caminho: str
    pendentes: Sequence[str]
    ambiguos: Sequence[object]


@dataclass
class No:
    id: str
    nome: str
    descricao: str
    area: str
    subarea: Optional[str]
    caminho: str
    pendentes: list = field(default_factory=list)
    ambiguos: list = field(default_factory=list)


@dataclass
class ConfigDoMapa:
    titulo: str
    url_base_de_edicao: Optional[str] = None
    esquema_do_editor: str = "vscode"
    intervalo_de_atualizacao_s: int = 30
    raiz: Optional[str] = None


class Paleta:
    """Matiz estavel por area: ordem por sha256, passo de ouro no arco 70-335."""

    def __init__(self, areas: Sequence[str]):
        self._areas = list(areas)

    def matizes(self) -> dict:
        unicas = sorted(set(self._areas), key=_chave_estavel)
        return {
            area: int(round(
                INICIO_DO_ARCO_LIVRE
                + (DESLOCAMENTO_DA_PALETA + i * PASSO_NO_ARCO_LIVRE) % ARCO_LIVRE
            ))
            for i, area in enumerate(unicas)
        }


class GeradorDeMapa:
    def __init__(self, nos: Sequence[object], arestas: Sequence[tuple], lentes: dict, config: ConfigDoMapa):
        self._nos = [_ler_no(no) for no in nos]
        self._arestas = [(a[0], a[1], a[2]) for a in arestas]
        self._lentes = {nome: list(escopos) for nome, escopos in lentes.items()}
        self._config = config

    def dados(self) -> dict:
        ids = {no["id"] for no in self._nos}
        nomes = [no["nome"] for no in self._nos]
        repetidos = {nome for nome in nomes if nomes.count(nome) > 1}
        validas = [
            (origem, destino, tipo)
            for origem, destino, tipo in self._arestas
            if origem in ids and destino in ids
        ]
        ligados = {p for par in validas for p in par[:2]}
        areas = sorted({no["area"] for no in self._nos})
        matizes = Paleta(areas).matizes()
        nos = []
        for no in sorted(self._nos, key=lambda n: n["id"]):
            nos.append({
                "id": no["id"],
                "nome": no["nome"],
                "rotulo": ("%s/%s" % (no["area"], no["nome"])) if no["nome"] in repetidos else no["nome"],
                "descricao": no["descricao"][:LIMITE_DA_DESCRICAO],
                "area": no["area"],
                "subarea": no["subarea"],
                "caminho": no["caminho"],
                "pendentes": list(no["pendentes"]),
                "ambiguos": [
                    {"ref": item["ref"], "candidatos": sorted(item["candidatos"])}
                    for item in no["ambiguos"]
                ],
                "orfao": no["id"] not in ligados,
            })
        arestas = [
            {"origem": origem, "destino": destino, "tipo": tipo}
            for origem, destino, tipo in sorted(validas)
        ]
        return {
            "titulo": self._config.titulo,
            "intervalo_s": self._config.intervalo_de_atualizacao_s,
            "url_base_de_edicao": self._config.url_base_de_edicao,
            "esquema_do_editor": self._config.esquema_do_editor,
            "raiz": self._config.raiz,
            "areas": [{"nome": nome, "matiz": matizes[nome]} for nome in areas],
            "nos": nos,
            "arestas": arestas,
            "lentes": {nome: sorted(escopos) for nome, escopos in self._lentes.items()},
            "saude": {
                "fatos": len(nos),
                "areas": len(areas),
                "pendentes": sum(1 for no in nos if no["pendentes"]),
                "ambiguos": sum(1 for no in nos if no["ambiguos"]),
                "orfaos": sum(1 for no in nos if no["orfao"]),
            },
        }

    def json(self) -> str:
        return json.dumps(self.dados(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"

    def html(self) -> str:
        pasta = Path(__file__).resolve().parent
        molde = (pasta / "mapa.html").read_text(encoding="utf-8")
        d3 = (pasta / "d3-hierarchy.min.js").read_text(encoding="utf-8")
        titulo = html_mod.escape(self._config.titulo)
        # <\/ quebra </script> no HTML; \u003c tira o < restante pra nao abrir tag.
        dados = self.json().replace("</", "<\\/").replace("<", "\\u003c")
        return (
            molde.replace("__TITULO__", titulo)
            .replace("__D3_HIERARCHY__", d3)
            .replace("__DADOS__", dados)
        )

    def gerar(self, destino) -> None:
        pasta = Path(destino)
        pasta.mkdir(parents=True, exist_ok=True)
        _escrever_atomico(pasta / "data.json", self.json())
        _escrever_atomico(pasta / "index.html", self.html())


class ServidorDoMapa:
    def __init__(self, saida, fabrica_de_gerador: Callable, raiz_dos_fatos, porta: int = 0):
        self._saida = Path(saida)
        self._fabrica = fabrica_de_gerador
        self._raiz = Path(raiz_dos_fatos)
        self._porta = porta
        self._httpd: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._assinatura = None
        self._trava = threading.Lock()

    @property
    def endereco(self):
        return self._httpd.server_address

    def iniciar(self) -> None:
        if self._httpd is None:
            self._montar()
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
            self._thread.start()

    def parar(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def servir_para_sempre(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            self._thread.join()
            return
        if self._httpd is None:
            self._montar()
        self._httpd.serve_forever()

    def _montar(self) -> None:
        mapa = self

        class Manipulador(BaseHTTPRequestHandler):
            def log_message(self, formato, *args):
                return

            def do_GET(self):
                caminho = urlsplit(self.path).path
                if caminho not in ROTAS_SERVICAS:
                    self.send_error(404, "nao encontrado")
                    return
                if caminho == "/data.json":
                    mapa._renovar_se_preciso()
                    arquivo = mapa._saida / "data.json"
                    tipo = "application/json; charset=utf-8"
                else:
                    arquivo = mapa._saida / "index.html"
                    tipo = "text/html; charset=utf-8"
                corpo = arquivo.read_bytes()
                etag = '"%s"' % hashlib.sha256(corpo).hexdigest()
                if self.headers.get("If-None-Match") == etag:
                    self.send_response(304)
                    self.send_header("ETag", etag)
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(corpo)))
                self.send_header("ETag", etag)
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(corpo)

        self._httpd = HTTPServer(("127.0.0.1", self._porta), Manipulador)
        self._assinatura = _assinatura_md(self._raiz)

    def _renovar_se_preciso(self) -> None:
        with self._trava:
            atual = _assinatura_md(self._raiz)
            if atual != self._assinatura:
                self._fabrica().gerar(self._saida)
                self._assinatura = atual


class ComandoMapa:
    nome = "mapa"

    def __init__(self, fabrica_de_gerador: Callable, raiz_dos_fatos):
        self._fabrica = fabrica_de_gerador
        self._raiz = Path(raiz_dos_fatos)

    def configurar(self, parser) -> None:
        parser.add_argument("--saida", default=None)
        parser.add_argument("--servir", nargs="?", const=8765, type=int, default=None)
        parser.add_argument("--abrir", action="store_true")

    def executar(self, args) -> int:
        saida = Path(args.saida) if args.saida else self._raiz / ".memoro" / "mapa"
        self._fabrica().gerar(saida)
        if args.servir is not None:
            servidor = ServidorDoMapa(saida, self._fabrica, self._raiz, porta=args.servir)
            servidor.iniciar()
            if args.abrir:
                webbrowser.open("http://127.0.0.1:%d/" % servidor.endereco[1])
            try:
                servidor.servir_para_sempre()
            except KeyboardInterrupt:
                pass
            finally:
                servidor.parar()
        elif args.abrir:
            webbrowser.open((saida / "index.html").resolve().as_uri())
        return 0


def _chave_estavel(area: str) -> bytes:
    return hashlib.sha256(area.encode("utf-8")).digest()


def _ler_no(no: object) -> dict:
    ambiguos = []
    for item in list(getattr(no, "ambiguos", []) or []):
        ambiguos.append({
            "ref": item["ref"],
            "candidatos": list(item["candidatos"]),
        })
    return {
        "id": getattr(no, "id"),
        "nome": getattr(no, "nome"),
        "descricao": getattr(no, "descricao") or "",
        "area": getattr(no, "area"),
        "subarea": getattr(no, "subarea"),
        "caminho": getattr(no, "caminho"),
        "pendentes": list(getattr(no, "pendentes", []) or []),
        "ambiguos": ambiguos,
    }


def _escrever_atomico(caminho: Path, texto: str) -> None:
    tmp = caminho.with_name(".%s.tmp" % caminho.name)
    tmp.write_text(texto, encoding="utf-8")
    os.replace(tmp, caminho)


def _assinatura_md(raiz: Path) -> tuple:
    itens = []
    for arquivo in sorted(raiz.rglob("*.md")):
        info = arquivo.stat()
        itens.append((str(arquivo), info.st_mtime_ns, info.st_size))
    return tuple(itens)
