from __future__ import annotations

import difflib
import json
import os
import tempfile
from datetime import datetime
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
        self._gravar_atomico(destino, self._escritor.escrever(fato))
        return destino

    def mover_para_lixeira(self, ident, motivo, usuario, dia):
        origem = self.caminho_de(ident)
        fato = self._ler(ident, origem)
        pasta = self._raiz / "areas" / "_lixeira" / ident.area
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / (ident.nome + ".md")
        n = 2
        # ponytail: sufixo linear -2,-3; índice se um nome encher a lixeira
        while destino.exists():
            destino = pasta / ("%s-%d.md" % (ident.nome, n))
            n += 1
        extras = {
            "motivo": motivo,
            "removido_por": usuario,
            "removido_em": dia.strftime("%Y-%m-%d"),
        }
        self._gravar_atomico(destino, self._escritor.escrever(fato, extras=extras))
        origem.unlink()
        return destino

    def purgar(self, dias, hoje):
        lixeira = self._raiz / "areas" / "_lixeira"
        if not lixeira.is_dir():
            return []
        if hasattr(hoje, "date") and callable(hoje.date):
            try:
                hoje = hoje.date()
            except TypeError:
                pass
        removidos = []
        for caminho in sorted(lixeira.rglob("*.md")):
            if not caminho.is_file():
                continue
            campos, _ = self._leitor.ler(caminho.read_text(encoding="utf-8", errors="replace"))
            bruto = campos.get("removido_em") or ""
            try:
                dia = datetime.strptime(bruto, "%Y-%m-%d").date()
            except (TypeError, ValueError):
                continue
            if (hoje - dia).days > dias:
                caminho.unlink()
                removidos.append(caminho)
        return removidos

    def inicializar(self):
        self._raiz.mkdir(parents=True, exist_ok=True)
        (self._raiz / "areas").mkdir(exist_ok=True)
        (self._raiz / "areas" / "_lixeira").mkdir(exist_ok=True)
        self._criar_se_falta(self._raiz / ".gitignore", ".memoro.lock\n")
        self._criar_se_falta(
            self._raiz / "lentes.json",
            json.dumps({"dia-a-dia": ["casa", "trabalho"], "nenhuma": []}, ensure_ascii=False)
            + "\n",
        )
        self._criar_se_falta(self._raiz / "eventos.jsonl", "")
        for area in ("casa", "trabalho"):
            (self._raiz / "areas" / area).mkdir(exist_ok=True)

    def _ler(self, ident, caminho):
        campos, corpo = self._leitor.ler(caminho.read_text(encoding="utf-8", errors="replace"))
        return Fato(
            ident,
            campos.get("description", ""),
            corpo,
            uses=tuple(campos.get("uses") or ()),
            scope=tuple(campos.get("scope") or ()),
        )

    def _gravar_atomico(self, destino, texto):
        destino.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".", suffix=".tmp", dir=str(destino.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as arq:
                arq.write(texto)
                arq.flush()
                os.fsync(arq.fileno())
            os.replace(tmp, str(destino))
            self._sincronizar_pasta(destino.parent)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _sincronizar_pasta(self, pasta):
        """O rename só é durável depois do fsync da pasta que o contém."""
        fd = os.open(str(pasta), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _criar_se_falta(self, caminho, conteudo):
        if not caminho.exists():
            caminho.write_text(conteudo, encoding="utf-8")
