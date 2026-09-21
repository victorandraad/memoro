from __future__ import annotations

import difflib
import json
import os
import tempfile
from pathlib import Path

from memoro.dominio import Fato, IdDeFato, IdInvalido
from memoro.formato import EscritorDeFrontmatter, LeitorDeFrontmatter


class ErroDeRepositorio(Exception):
    """falha ao localizar ou gravar um fato."""


class FatoNaoEncontrado(ErroDeRepositorio):
    def __init__(self, ref, ids):
        extra = ""
        # ponytail: um palpite (cutoff 0.5); índice invertido se o acervo crescer
        parecidos = difflib.get_close_matches(ref, sorted(set(ids)), n=1, cutoff=0.5)
        if parecidos:
            extra = " (quis dizer %s?)" % parecidos[0]
        super().__init__("fato não encontrado: %s%s" % (ref, extra))


class ReferenciaAmbigua(ErroDeRepositorio):
    def __init__(self, candidatas):
        self.candidatas = list(candidatas)
        super().__init__(
            "referência ambígua: " + ", ".join(str(c) for c in self.candidatas)
        )


class RepositorioDeFatos:
    def __init__(self, raiz):
        self._raiz = Path(raiz)
        self._leitor = LeitorDeFrontmatter()
        self._escritor = EscritorDeFrontmatter()

    def caminho_de(self, ident):
        return self._raiz / ident.caminho

    def todos(self):
        fatos = []
        areas = self._raiz / "areas"
        if not areas.is_dir():
            return []
        for pasta, dirnames, arquivos in os.walk(str(areas)):
            dirnames[:] = [d for d in dirnames if not d.startswith("_") and not d.startswith(".")]
            rel = Path(pasta).relative_to(areas).as_posix()
            if rel == ".":
                continue
            for nome_arq in arquivos:
                if not nome_arq.endswith(".md"):
                    continue
                try:
                    ident = IdDeFato(rel, nome_arq[:-3])
                except IdInvalido:
                    continue
                caminho = Path(pasta) / nome_arq
                if caminho.is_file():
                    fatos.append(self._ler(ident, caminho))
        fatos.sort(key=lambda f: str(f.id))
        return fatos

    def areas(self):
        resultado = []
        raiz_areas = self._raiz / "areas"
        if not raiz_areas.is_dir():
            return []
        for pasta, dirnames, _ in os.walk(str(raiz_areas)):
            dirnames[:] = [d for d in dirnames if not d.startswith("_") and not d.startswith(".")]
            rel = Path(pasta).relative_to(raiz_areas).as_posix()
            if rel != ".":
                resultado.append(rel)
        return sorted(resultado)

    def achar(self, ref):
        todos = self.todos()
        por_id = {str(f.id): f for f in todos}
        if ref in por_id:
            return por_id[ref]
        iguais = [f for f in todos if f.nome == ref]
        if len(iguais) == 1:
            return iguais[0]
        if len(iguais) > 1:
            raise ReferenciaAmbigua(sorted((f.id for f in iguais), key=str))
        raise FatoNaoEncontrado(ref, [str(f.id) for f in todos])

    def gravar(self, fato):
        destino = self.caminho_de(fato.id)
        destino.parent.mkdir(parents=True, exist_ok=True)
        texto = self._escritor.escrever(fato)
        fd, tmp = tempfile.mkstemp(prefix=".", suffix=".tmp", dir=str(destino.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as arq:
                arq.write(texto)
            os.replace(tmp, str(destino))
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return destino

    def inicializar(self):
        self._raiz.mkdir(parents=True, exist_ok=True)
        (self._raiz / "areas").mkdir(exist_ok=True)
        (self._raiz / "areas" / "_lixeira").mkdir(exist_ok=True)
        self._criar_se_falta(
            self._raiz / "lentes.json",
            json.dumps({"dia-a-dia": ["casa", "trabalho"], "nenhuma": []}, ensure_ascii=False)
            + "\n",
        )
        self._criar_se_falta(self._raiz / "eventos.jsonl", "")
        exemplos = (
            ("casa", "exemplo", "fato de exemplo da área casa"),
            ("trabalho", "exemplo", "fato de exemplo da área trabalho"),
        )
        for area, nome, desc in exemplos:
            ident = IdDeFato(area, nome)
            if not self.caminho_de(ident).exists():
                self.gravar(Fato(ident, desc, "corpo de exemplo\n"))

    def _ler(self, ident, caminho):
        campos, corpo = self._leitor.ler(caminho.read_text(encoding="utf-8", errors="replace"))
        return Fato(
            ident,
            campos.get("description", ""),
            corpo,
            uses=tuple(campos.get("uses") or ()),
            scope=tuple(campos.get("scope") or ()),
        )

    def _criar_se_falta(self, caminho, conteudo):
        if not caminho.exists():
            caminho.write_text(conteudo, encoding="utf-8")
