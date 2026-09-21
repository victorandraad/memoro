from __future__ import annotations

import fcntl
import hashlib
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from memoro.diario import DiarioDeEventos
from memoro.dominio import Evento, Fato, IdDeFato, IdInvalido
from memoro.formato import LeitorDeFrontmatter, problemas_do_frontmatter
from memoro.grafo import GrafoDeFatos
from memoro.repositorio import FatoNaoEncontrado, ReferenciaAmbigua, RepositorioDeFatos
from memoro.validacao import Pedido, Validador


class Recusa(Exception):
    """regra, id ou referência barraram a escrita."""


@dataclass(frozen=True)
class Resultado:
    id: object
    caminho: object
    avisos: tuple


def _agora():
    return datetime.now(timezone.utc)


class Tranca:
    # ponytail: uma tranca global por raiz, so Unix; upgrade = tranca por area
    def __init__(self, caminho):
        self._caminho = Path(caminho)
        self._arquivo = None

    def __enter__(self):
        self._caminho.parent.mkdir(parents=True, exist_ok=True)
        self._arquivo = open(self._caminho, "a+")
        fcntl.flock(self._arquivo.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        arquivo = self._arquivo
        self._arquivo = None
        if arquivo is not None:
            try:
                fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN)
            finally:
                arquivo.close()
        return False


class Versionador:
    def __init__(self, raiz):
        self._raiz = Path(raiz)

    def commitar(self, caminhos, mensagem):
        if not caminhos or not self._e_topo():
            return None
        rels = self._relativos(caminhos)
        raiz = str(self._raiz)
        try:
            subprocess.run(["git", "-C", raiz, "add", "--"] + rels, capture_output=True)
            r = subprocess.run(
                ["git", "-C", raiz, "commit", "-q", "-m", mensagem, "--"] + rels,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            return "gravado em disco, sem commit: %s" % exc
        if r.returncode != 0:
            detalhe = (r.stderr or r.stdout or "").strip()
            return "gravado em disco, sem commit: %s" % detalhe
        return None

    def _e_topo(self):
        try:
            r = subprocess.run(
                ["git", "-C", str(self._raiz), "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
            )
        except OSError:
            return False
        if r.returncode != 0:
            return False
        return os.path.realpath(r.stdout.strip()) == os.path.realpath(str(self._raiz))

    def _relativos(self, caminhos):
        raiz = os.path.realpath(str(self._raiz))
        rels = []
        for caminho in caminhos:
            p = Path(caminho)
            if not p.is_absolute():
                p = self._raiz / p
            rels.append(os.path.relpath(os.path.realpath(str(p)), raiz))
        return rels


class PortaDeEscrita:
    def __init__(self, repositorio, validador, diario, versionador, tranca, usuario, relogio):
        self._repositorio = repositorio
        self._validador = validador
        self.diario = diario
        self._versionador = versionador
        self._tranca = tranca
        self._usuario = usuario
        self._relogio = relogio

    @classmethod
    def padrao(cls, raiz, usuario, relogio=None):
        raiz = Path(raiz)
        if relogio is None:
            relogio = _agora
        return cls(
            RepositorioDeFatos(raiz),
            Validador.padrao(),
            DiarioDeEventos(raiz / "eventos.jsonl"),
            Versionador(raiz),
            Tranca(raiz / ".memoro.lock"),
            usuario,
            relogio,
        )

    def add(self, area, nome, descricao, corpo, uses=(), scope=(), novo_mesmo_assim=False):
        uses, scope = tuple(uses), tuple(scope)
        return self._executar(
            "add",
            "%s/%s" % (area, nome),
            area,
            lambda: self._add(area, nome, descricao, corpo, uses, scope, novo_mesmo_assim),
        )

    def update(self, ref, descricao=None, corpo=None, anexo=None, uses=None, scope=None):
        return self._executar(
            "update",
            ref,
            "",
            lambda: self._update(ref, descricao, corpo, anexo, uses, scope),
        )

    def rm(self, ref, motivo):
        return self._executar("rm", ref, "", lambda: self._rm(ref, motivo))

    def adotar(self, ref, motivo):
        adotados, recusados = self.adotar_varios((ref,), motivo)
        if recusados:
            raise Recusa(recusados[0][1])
        return adotados[0]

    def adotar_varios(self, refs, motivo):
        with self._tranca:
            return self._adotar_varios(tuple(refs), motivo)

    def purga(self, dias):
        with self._tranca:
            return self._purga(dias)

    def _executar(self, op, ident, area, trabalho):
        with self._tranca:
            try:
                return trabalho()
            except Recusa as exc:
                self._registrar(op, ident, area, "", False, str(exc), "")
                raise
            except (IdInvalido, FatoNaoEncontrado, ReferenciaAmbigua) as exc:
                recusa = Recusa(str(exc))
                self._registrar(op, ident, area, "", False, str(recusa), "")
                raise recusa from exc

    def _add(self, area, nome, descricao, corpo, uses, scope, novo_mesmo_assim=False):
        ident = IdDeFato(area, nome)
        fato = Fato(ident, descricao, corpo, uses=uses, scope=scope)
        avisos = self._validar("add", ident, fato, "", novo_mesmo_assim=novo_mesmo_assim)
        caminho = self._repositorio.gravar(fato)
        return self._fechar("add", ident, caminho, [caminho], avisos)

    def _update(self, ref, descricao, corpo, anexo, uses, scope):
        atual = self._repositorio.achar(ref)
        novo_corpo = atual.corpo if corpo is None else corpo
        if anexo is not None:
            novo_corpo = atual.corpo if corpo is None else novo_corpo
            novo_corpo = novo_corpo.rstrip("\n") + "\n\n" + anexo.lstrip("\n")
        fato = Fato(
            atual.id,
            atual.descricao if descricao is None else descricao,
            novo_corpo,
            uses=atual.uses if uses is None else tuple(uses),
            scope=atual.scope if scope is None else tuple(scope),
        )
        avisos = self._validar("update", fato.id, fato, "")
        caminho = self._repositorio.gravar(fato)
        return self._fechar("update", fato.id, caminho, [caminho], avisos)

    def _rm(self, ref, motivo):
        atual = self._repositorio.achar(ref)
        avisos = self._validar("rm", atual.id, atual, motivo)
        origem = self._repositorio.caminho_de(atual.id)
        destino = self._repositorio.mover_para_lixeira(
            atual.id, motivo, self._usuario, self._relogio().date(),
        )
        return self._fechar("rm", atual.id, destino, [origem, destino], avisos, motivo)

    def _adotar_varios(self, refs, motivo):
        adotados, recusados, caminhos = [], [], []
        if not refs:
            return adotados, recusados
        existentes = tuple(self._repositorio.todos())
        areas = tuple(self._repositorio.areas())
        grafo = GrafoDeFatos(existentes)
        eventos = []
        for ref in refs:
            try:
                ident, caminho, avisos = self._adotar_um(ref, motivo, existentes, areas, grafo)
            except Recusa as exc:
                eventos.append(self._evento("adocao", ref, "", "", False, str(exc), ""))
                recusados.append((ref, str(exc)))
                continue
            except (IdInvalido, FatoNaoEncontrado, ReferenciaAmbigua) as exc:
                eventos.append(self._evento("adocao", ref, "", "", False, str(exc), ""))
                recusados.append((ref, str(exc)))
                continue
            blob = caminho.read_bytes()
            resumo = "+%d linhas" % len(blob.decode("utf-8", errors="replace").splitlines())
            eventos.append(self._evento(
                "adocao", str(ident), ident.area, resumo, True, motivo,
                hashlib.sha256(blob).hexdigest(),
            ))
            adotados.append(Resultado(ident, caminho, tuple(avisos)))
            caminhos.append(caminho)
        if eventos:
            self.diario.registrar_varios(eventos)
        if caminhos:
            mensagem = "memoro adocao %s" % adotados[0].id if len(adotados) == 1 else "memoro adocao"
            aviso_git = self._versionador.commitar(caminhos, mensagem)
            if aviso_git:
                adotados = [Resultado(r.id, r.caminho, r.avisos + (aviso_git,)) for r in adotados]
        return adotados, recusados

    def _adotar_um(self, ref, motivo, existentes, areas, grafo=None):
        if not (motivo or "").strip():
            raise Recusa("adoção exige motivo")
        ident, caminho = self._resolver_para_adotar(ref, existentes)
        try:
            texto = caminho.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            raise Recusa("frontmatter inválido")
        if problemas_do_frontmatter(texto, ident.area, ident.nome):
            raise Recusa("frontmatter inválido")
        campos, corpo = LeitorDeFrontmatter().ler(texto)
        fato = Fato(
            ident,
            campos.get("description", ""),
            corpo,
            uses=tuple(campos.get("uses") or ()),
            scope=tuple(campos.get("scope") or ()),
        )
        avisos = self._validar(
            "adocao", ident, fato, motivo, existentes=existentes, areas=areas, grafo=grafo,
        )
        return ident, caminho, avisos

    def _resolver_para_adotar(self, ref, existentes=None):
        try:
            ident = IdDeFato.de_texto(ref)
        except IdInvalido:
            ident = None
        if ident is not None:
            caminho = self._repositorio.caminho_de(ident)
            if caminho.is_file():
                return ident, caminho
        try:
            if existentes is None:
                atual = self._repositorio.achar(ref)
            else:
                atual = self._achar_no_retrato(ref, existentes)
            return atual.id, self._repositorio.caminho_de(atual.id)
        except (FatoNaoEncontrado, ReferenciaAmbigua):
            if ident is None:
                raise Recusa("frontmatter inválido")
            raise

    def _achar_no_retrato(self, ref, existentes):
        por_id = {str(f.id): f for f in existentes}
        if ref in por_id:
            return por_id[ref]
        iguais = [f for f in existentes if f.nome == ref]
        if len(iguais) == 1:
            return iguais[0]
        if len(iguais) > 1:
            raise ReferenciaAmbigua(sorted((f.id for f in iguais), key=str))
        raise FatoNaoEncontrado(ref, [str(f.id) for f in existentes])

    def _purga(self, dias):
        removidos = self._repositorio.purgar(dias, self._relogio().date())
        for caminho in removidos:
            ident, area = self._id_lixeira(caminho)
            aviso = self._versionador.commitar([caminho], "memoro purga %s" % ident)
            self._registrar("purga", ident, area, "purga", True, aviso or "", "")
        return removidos

    def _validar(self, op, ident, fato, motivo, novo_mesmo_assim=False, existentes=None, areas=None, grafo=None):
        pedido = Pedido(
            op=op,
            id=ident,
            fato=fato,
            motivo=motivo,
            existentes=tuple(self._repositorio.todos() if existentes is None else existentes),
            areas=tuple(self._repositorio.areas() if areas is None else areas),
            novo_mesmo_assim=novo_mesmo_assim,
            grafo=grafo,
        )
        achados = self._validador.avaliar(pedido)
        recusas = [a.mensagem for a in achados if a.recusa]
        if recusas:
            raise Recusa("; ".join(recusas))
        return [a.mensagem for a in achados if not a.recusa]

    def _fechar(self, op, ident, caminho, tocados, avisos, motivo=""):
        aviso_git = self._versionador.commitar(tocados, "memoro %s %s" % (op, ident))
        if aviso_git:
            avisos.append(aviso_git)
        blob = caminho.read_bytes()
        resumo = "+%d linhas" % len(blob.decode("utf-8", errors="replace").splitlines())
        self._registrar(
            op, str(ident), ident.area, resumo, True, motivo, hashlib.sha256(blob).hexdigest(),
        )
        return Resultado(ident, caminho, tuple(avisos))

    def _evento(self, op, ident, area, resumo, ok, motivo, hash_do_conteudo):
        return Evento(
            ts=self._relogio().isoformat(timespec="seconds"),
            usuario=self._usuario,
            op=op,
            id=str(ident),
            area=area or "",
            resumo=resumo,
            ok=ok,
            motivo=motivo or "",
            hash_do_conteudo=hash_do_conteudo,
        )

    def _registrar(self, op, ident, area, resumo, ok, motivo, hash_do_conteudo):
        self.diario.registrar(self._evento(op, ident, area, resumo, ok, motivo, hash_do_conteudo))

    def _id_lixeira(self, caminho):
        marcador = "/areas/_lixeira/"
        texto = Path(caminho).as_posix()
        i = texto.find(marcador)
        rel = texto[i + len(marcador):] if i >= 0 else Path(caminho).name
        area, _, arquivo = rel.rpartition("/")
        nome = arquivo[:-3] if arquivo.endswith(".md") else arquivo
        return ("%s/%s" % (area, nome) if area else nome), area
