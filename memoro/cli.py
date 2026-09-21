from __future__ import annotations

import argparse
import json
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path

from dataclasses import asdict

from memoro.diario import DiarioDeEventos
from memoro.dominio import IdInvalido
from memoro.porta import PortaDeEscrita, Recusa
from memoro.repositorio import ErroDeRepositorio, RepositorioDeFatos


def _csv(valor):
    if not valor:
        return ()
    return tuple(p.strip() for p in valor.split(",") if p.strip())


class Comando(ABC):
    nome = ""

    def __init__(self, cli):
        self._cli = cli

    @abstractmethod
    def configurar(self, subparser):
        raise NotImplementedError

    @abstractmethod
    def executar(self, args):
        raise NotImplementedError

    def _usuario(self):
        return self._cli.ambiente.get("USER") or "desconhecido"

    def _porta(self):
        return PortaDeEscrita.padrao(self._cli.raiz, self._usuario())

    def _ler(self, so_se_nao_tty=False):
        entrada = self._cli.entrada
        if so_se_nao_tty and hasattr(entrada, "isatty") and entrada.isatty():
            return ""
        return entrada.read()

    def _emitir(self, resultado, args):
        rel = Path(resultado.caminho)
        try:
            rel = rel.relative_to(self._cli.raiz)
        except ValueError:
            pass
        rel_s = rel.as_posix()
        for aviso in resultado.avisos:
            self._cli.erro.write("aviso: %s\n" % aviso)
        if args.json:
            json.dump(
                {"id": str(resultado.id), "caminho": rel_s, "avisos": list(resultado.avisos)},
                self._cli.saida,
                ensure_ascii=False,
            )
            self._cli.saida.write("\n")
        else:
            self._cli.saida.write("%s\n" % rel_s)
        return 0


class ComandoInit(Comando):
    nome = "init"

    def configurar(self, subparser):
        return

    def executar(self, args):
        raiz = self._cli.raiz
        RepositorioDeFatos(raiz).inicializar()
        if args.json:
            json.dump({"raiz": str(raiz)}, self._cli.saida, ensure_ascii=False)
            self._cli.saida.write("\n")
        else:
            self._cli.saida.write("%s\n" % raiz)
        return 0


class ComandoShow(Comando):
    nome = "show"

    def configurar(self, subparser):
        subparser.add_argument("ref")

    def executar(self, args):
        repo = RepositorioDeFatos(self._cli.raiz)
        fato = repo.achar(args.ref)
        if args.json:
            json.dump(
                {
                    "id": str(fato.id),
                    "nome": fato.nome,
                    "area": fato.area,
                    "descricao": fato.descricao,
                    "corpo": fato.corpo,
                    "uses": list(fato.uses),
                    "scope": list(fato.scope),
                    "caminho": fato.id.caminho,
                },
                self._cli.saida,
                ensure_ascii=False,
            )
            self._cli.saida.write("\n")
        else:
            self._cli.saida.write(repo.caminho_de(fato.id).read_text(encoding="utf-8"))
        return 0


class ComandoLs(Comando):
    nome = "ls"

    def configurar(self, subparser):
        subparser.add_argument("area", nargs="?")

    def executar(self, args):
        repo = RepositorioDeFatos(self._cli.raiz)
        area = (args.area or "").strip("/")
        escolhidos = [
            f for f in repo.todos()
            if not area or f.area == area or f.area.startswith(area + "/")
        ]
        if args.json:
            json.dump(
                [{"id": str(f.id), "descricao": f.descricao} for f in escolhidos],
                self._cli.saida,
                ensure_ascii=False,
            )
            self._cli.saida.write("\n")
        else:
            for fato in escolhidos:
                self._cli.saida.write("%s\t%s\n" % (fato.id, fato.descricao))
        return 0


class ComandoAdd(Comando):
    nome = "add"

    def configurar(self, subparser):
        subparser.add_argument("area")
        subparser.add_argument("nome")
        subparser.add_argument("--desc", required=True)
        subparser.add_argument("--uses", default="")
        subparser.add_argument("--scope", default="")

    def executar(self, args):
        corpo = self._ler(so_se_nao_tty=True)
        r = self._porta().add(
            args.area, args.nome, args.desc, corpo, uses=_csv(args.uses), scope=_csv(args.scope),
        )
        return self._emitir(r, args)


class ComandoUpdate(Comando):
    nome = "update"

    def configurar(self, subparser):
        subparser.add_argument("ref")
        subparser.add_argument("--desc", default=None)
        subparser.add_argument("--uses", default=None)
        subparser.add_argument("--scope", default=None)
        subparser.add_argument("--corpo", action="store_true")
        subparser.add_argument("--anexar", action="store_true")

    def executar(self, args):
        texto = self._ler() if args.corpo or args.anexar else None
        r = self._porta().update(
            args.ref,
            descricao=args.desc,
            corpo=texto if args.corpo else None,
            anexo=texto if args.anexar and not args.corpo else (texto if args.anexar else None),
            uses=None if args.uses is None else _csv(args.uses),
            scope=None if args.scope is None else _csv(args.scope),
        )
        return self._emitir(r, args)


class ComandoRm(Comando):
    nome = "rm"

    def configurar(self, subparser):
        subparser.add_argument("ref")
        subparser.add_argument("--motivo", default="")

    def executar(self, args):
        return self._emitir(self._porta().rm(args.ref, args.motivo), args)


class ComandoPurga(Comando):
    nome = "purga"

    def configurar(self, subparser):
        subparser.add_argument("--dias", type=int, default=30)

    def executar(self, args):
        caminhos = self._porta().purga(args.dias)
        rels = []
        for caminho in caminhos:
            try:
                rels.append(Path(caminho).relative_to(self._cli.raiz).as_posix())
            except ValueError:
                rels.append(str(caminho))
        if args.json:
            json.dump(rels, self._cli.saida, ensure_ascii=False)
            self._cli.saida.write("\n")
        else:
            for rel in rels:
                self._cli.saida.write("%s\n" % rel)
        return 0


class ComandoLog(Comando):
    nome = "log"

    def configurar(self, subparser):
        subparser.add_argument("--id", default=None)
        subparser.add_argument("--usuario", default=None)
        subparser.add_argument("--desde", default=None)
        subparser.add_argument("--recusas", action="store_true")

    def executar(self, args):
        eventos = DiarioDeEventos(self._cli.raiz / "eventos.jsonl").ler(
            id=args.id, usuario=args.usuario, desde=args.desde, so_recusas=args.recusas,
        )
        if args.json:
            json.dump([asdict(e) for e in eventos], self._cli.saida, ensure_ascii=False)
            self._cli.saida.write("\n")
        else:
            for e in eventos:
                self._cli.saida.write(
                    "%s %s %s %s %s %s\n"
                    % (e.ts, e.usuario, "ok" if e.ok else "NEG", e.op, e.id, e.motivo)
                )
        return 0


class Cli:
    def __init__(self, entrada, saida, erro, ambiente):
        self.entrada = entrada
        self.saida = saida
        self.erro = erro
        self.ambiente = ambiente
        self._comandos = (
            ComandoInit(self), ComandoShow(self), ComandoLs(self),
            ComandoAdd(self), ComandoUpdate(self), ComandoRm(self),
            ComandoPurga(self), ComandoLog(self),
        )

    @property
    def raiz(self):
        casa = self.ambiente.get("MEMORO_HOME")
        if casa:
            return Path(casa)
        return Path(self.ambiente["HOME"]) / "memoro"

    def executar(self, argv):
        analisador = argparse.ArgumentParser(prog="memoro")
        subs = analisador.add_subparsers(dest="comando", required=True)
        for comando in self._comandos:
            sub = subs.add_parser(comando.nome)
            comando.configurar(sub)
            sub.add_argument("--json", action="store_true")
            sub.set_defaults(_comando=comando)
        antigo = sys.stderr
        sys.stderr = self.erro
        try:
            try:
                args = analisador.parse_args(list(argv))
            except SystemExit as e:
                if e.code is None:
                    return 0
                if isinstance(e.code, int):
                    return e.code
                self.erro.write("%s\n" % e.code)
                return 2
        finally:
            sys.stderr = antigo
        try:
            return args._comando.executar(args)
        except Recusa as exc:
            self.erro.write("recusado: %s\n" % exc)
            if args.json:
                json.dump({"ok": False, "motivo": str(exc)}, self.saida, ensure_ascii=False)
                self.saida.write("\n")
            return 1
        except (ErroDeRepositorio, IdInvalido) as exc:
            self.erro.write("%s\n" % exc)
            return 1


def main():
    try:
        return Cli(sys.stdin, sys.stdout, sys.stderr, os.environ).executar(sys.argv[1:])
    except BrokenPipeError:
        return 0
