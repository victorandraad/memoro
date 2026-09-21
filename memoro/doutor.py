from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from memoro.diario import DiarioDeEventos
from memoro.dominio import Fato, IdDeFato, IdInvalido
from memoro.formato import LeitorDeFrontmatter, problemas_do_frontmatter
from memoro.grafo import GrafoDeFatos


_OPS_VIVOS = frozenset({"add", "update", "adocao"})
_OPS_MORTOS = frozenset({"rm", "purga"})


@dataclass(frozen=True)
class Achado:
    tipo: str
    id: str
    detalhe: str


class Doutor:
    def __init__(self, raiz):
        self._raiz = Path(raiz)
        self._diario = DiarioDeEventos(self._raiz / "eventos.jsonl")
        self._leitor = LeitorDeFrontmatter()

    def examinar(self):
        achados = []
        for numero, _linha in self._diario.linhas_corrompidas():
            achados.append(Achado("diario-corrompido", "", "linha %d" % numero))
        ultimo_ok = {}
        for evento in self._diario.ler():
            if evento.ok:
                ultimo_ok[evento.id] = evento
        presentes = {}
        validos = []
        for rel, caminho in self._arquivos_md():
            presentes[rel] = caminho
            ident, blob, texto, erro = self._ler_arquivo(rel, caminho)
            ev = ultimo_ok.get(rel)
            digest = hashlib.sha256(blob).hexdigest() if blob is not None else None
            if erro is not None:
                achados.append(Achado("frontmatter-invalido", rel, erro))
                if digest is not None and ev is not None and ev.op in _OPS_VIVOS and digest != ev.hash_do_conteudo:
                    achados.append(Achado("alterado-fora-da-porta", rel, "hash diverge do diário"))
                continue
            if ev is None or ev.op in _OPS_MORTOS:
                achados.append(Achado("sem-evento", rel, "arquivo sem evento vivo na porta"))
            elif ev.op in _OPS_VIVOS and digest != ev.hash_do_conteudo:
                achados.append(Achado("alterado-fora-da-porta", rel, "hash diverge do diário"))
            validos.append(self._fato_de(ident, texto))
        for ident, ev in ultimo_ok.items():
            if ev.op in _OPS_VIVOS and ident not in presentes:
                achados.append(Achado("evento-sem-arquivo", ident, "arquivo ausente"))
        grafo = GrafoDeFatos(validos)
        for no in grafo.nos():
            pendentes = grafo.pendentes_de(no.id)
            if pendentes:
                alvos = ", ".join(p.alvo for p in pendentes)
                achados.append(Achado("pendente", no.id, alvos))
            ambiguos = grafo.ambiguos_de(no.id)
            if ambiguos:
                alvos = ", ".join(a.alvo for a in ambiguos)
                achados.append(Achado("ambiguo", no.id, alvos))
        achados.sort(key=lambda a: (a.tipo, a.id, a.detalhe))
        return achados

    def _arquivos_md(self):
        areas = self._raiz / "areas"
        if not areas.is_dir():
            return []
        encontrados = []
        for pasta, dirnames, arquivos in os.walk(str(areas)):
            dirnames[:] = [d for d in dirnames if not d.startswith("_") and not d.startswith(".")]
            rel_pasta = Path(pasta).relative_to(areas).as_posix()
            for nome_arq in arquivos:
                if not nome_arq.endswith(".md"):
                    continue
                caminho = Path(pasta) / nome_arq
                if not caminho.is_file():
                    continue
                stem = nome_arq[:-3]
                if rel_pasta == ".":
                    rel = stem
                else:
                    rel = "%s/%s" % (rel_pasta, stem)
                encontrados.append((rel, caminho))
        encontrados.sort()
        return encontrados

    def _ler_arquivo(self, rel, caminho):
        try:
            blob = caminho.read_bytes()
        except OSError as exc:
            return None, None, None, str(exc)
        try:
            texto = blob.decode("utf-8")
        except UnicodeDecodeError:
            return None, blob, None, "utf-8 inválido"
        area, _, nome = rel.rpartition("/")
        try:
            ident = IdDeFato(area, nome)
        except IdInvalido:
            return None, blob, texto, "nome de arquivo não é id válido"
        problemas = problemas_do_frontmatter(texto, ident.area, ident.nome)
        if problemas:
            return ident, blob, texto, "; ".join(problemas)
        return ident, blob, texto, None

    def _fato_de(self, ident, texto):
        campos, corpo = self._leitor.ler(texto)
        return Fato(
            ident,
            campos.get("description", ""),
            corpo,
            uses=tuple(campos.get("uses") or ()),
            scope=tuple(campos.get("scope") or ()),
        )
