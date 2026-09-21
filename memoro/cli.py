from __future__ import annotations

import argparse
import json
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path

from memoro.dominio import IdInvalido
from memoro.repositorio import ErroDeRepositorio, RepositorioDeFatos


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


class Cli:
    def __init__(self, entrada, saida, erro, ambiente):
        self.entrada = entrada
        self.saida = saida
        self.erro = erro
        self.ambiente = ambiente
        self._comandos = (ComandoInit(self), ComandoShow(self), ComandoLs(self))

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
        except (ErroDeRepositorio, IdInvalido) as exc:
            self.erro.write("%s\n" % exc)
            return 1


def main():
    try:
        return Cli(sys.stdin, sys.stdout, sys.stderr, os.environ).executar(sys.argv[1:])
    except BrokenPipeError:
        return 0
