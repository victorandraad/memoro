from __future__ import annotations

import argparse
import json
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path

from dataclasses import asdict

from memoro.adaptador_do_mapa import AdaptadorDoMapa
from memoro.diario import DiarioDeEventos
from memoro.dominio import IdInvalido
from memoro.doutor import Doutor
from memoro.grafo import GrafoDeFatos
from memoro.lentes import ErroDeLente, Lentes, Recall
from memoro import mensagens
from memoro.mensagens import t, tipo
from memoro.mapa import ComandoMapa, ConfigDoMapa, GeradorDeMapa
from memoro.porta import PortaDeEscrita, Recusa
from memoro.repositorio import ErroDeRepositorio, RepositorioDeFatos


_MOTIVOS_DO_RECALL = {"filho": "motivo-filho", "herda": "motivo-herda"}


def _csv(valor):
    if not valor:
        return ()
    return tuple(p.strip() for p in valor.split(",") if p.strip())


class Comando(ABC):
    nome = ""
    aliases = ()

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
            self._cli.erro.write("%s\n" % t("aviso", aviso))
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
        self._adotar_exemplos()
        if args.json:
            json.dump({"raiz": str(raiz)}, self._cli.saida, ensure_ascii=False)
            self._cli.saida.write("\n")
        else:
            self._cli.saida.write("%s\n" % raiz)
        return 0

    def _adotar_exemplos(self):
        porta = self._porta()
        alvos = {"casa/exemplo", "trabalho/exemplo"}
        for achado in Doutor(self._cli.raiz).examinar():
            if achado.id not in alvos:
                continue
            if achado.tipo not in ("sem-evento", "alterado-fora-da-porta"):
                continue
            try:
                porta.adotar(achado.id, "init")
            except Recusa:
                continue


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


class ComandoRecall(Comando):
    nome = "recall"

    def configurar(self, subparser):
        subparser.add_argument("--lens", default=None)
        subparser.add_argument("--scope", default=None)
        subparser.add_argument("--saltos", type=int, default=1)
        subparser.add_argument("--list-lenses", action="store_true")

    def executar(self, args):
        repo = RepositorioDeFatos(self._cli.raiz)
        lentes = Lentes(self._cli.raiz / "lentes.json", repo.areas())
        if args.list_lenses:
            return self._listar_lentes(lentes, args)
        escopos = None
        if args.lens is not None:
            escopos = list(lentes.escopos(args.lens))
        if args.scope:
            extra = [s.strip() for s in args.scope.split(",") if s.strip()]
            escopos = (escopos or []) + extra
        fatos = repo.todos()
        resultado = Recall(fatos, GrafoDeFatos(fatos), teto=self._teto()).por_escopos(
            escopos, saltos=args.saltos,
        )
        if args.json:
            json.dump(
                {
                    "itens": [
                        {
                            "id": str(item.fato.id),
                            "nome": item.fato.nome,
                            "area": item.fato.area,
                            "descricao": item.fato.descricao,
                            "motivo": item.motivo,
                            "corpo": item.fato.corpo,
                        }
                        for item in resultado.itens
                    ],
                    "cortados": resultado.cortados,
                },
                self._cli.saida,
                ensure_ascii=False,
            )
            self._cli.saida.write("\n")
            return 0
        rotulo = args.lens or args.scope or t("recall-tudo")
        n = len(resultado.itens)
        if resultado.cortados:
            cabeca = t("recall-cortados", rotulo, n, resultado.cortados)
        elif n == 1:
            cabeca = t("recall-1", rotulo)
        else:
            cabeca = t("recall-n", rotulo, n)
        self._cli.saida.write("%s\n" % cabeca)
        for item in resultado.itens:
            linha = "- %s: %s" % (item.fato.id, item.fato.descricao)
            if item.motivo != "escopo":
                chave = _MOTIVOS_DO_RECALL.get(item.motivo)
                linha += " (%s)" % (t(chave) if chave else item.motivo)
            self._cli.saida.write("%s\n" % linha)
        return 0

    def _listar_lentes(self, lentes, args):
        cruas = sorted(lentes.cruas().items())
        if args.json:
            json.dump([{"nome": n, "escopos": e} for n, e in cruas], self._cli.saida, ensure_ascii=False)
            self._cli.saida.write("\n")
        else:
            for nome, escopos in cruas:
                self._cli.saida.write("%s\t%s\n" % (nome, ", ".join(escopos)))
        return 0

    def _teto(self):
        bruto = self._cli.ambiente.get("MEMORO_RECALL_CAP")
        if not bruto:
            return None
        try:
            n = int(bruto)
        except (TypeError, ValueError):
            return None
        if n > 0:
            return n
        return None


class ComandoAdd(Comando):
    nome = "add"

    def configurar(self, subparser):
        subparser.add_argument("area")
        subparser.add_argument("nome")
        subparser.add_argument("--desc", required=True)
        subparser.add_argument("--uses", default="")
        subparser.add_argument("--scope", default="")
        subparser.add_argument("--new-anyway", "--novo-mesmo-assim", dest="novo_mesmo_assim", action="store_true", help=t("ajuda-novo"))

    def executar(self, args):
        corpo = self._ler(so_se_nao_tty=True)
        r = self._porta().add(
            args.area, args.nome, args.desc, corpo, uses=_csv(args.uses), scope=_csv(args.scope),
            novo_mesmo_assim=args.novo_mesmo_assim,
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
        subparser.add_argument("--reason", "--motivo", dest="motivo", default="", help=t("ajuda-motivo"))

    def executar(self, args):
        return self._emitir(self._porta().rm(args.ref, args.motivo), args)


class ComandoPurga(Comando):
    nome = "purga"
    aliases = ("purge",)

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


class ComandoDoMapa(Comando):
    nome = "mapa"
    aliases = ("map",)

    def configurar(self, subparser):
        subparser.add_argument("--titulo", default=t("titulo-do-mapa"))
        ComandoMapa(lambda: None, self._cli.raiz).configurar(subparser)

    def executar(self, args):
        raiz = self._cli.raiz
        titulo = args.titulo

        def fabrica():
            repo = RepositorioDeFatos(raiz)
            adaptador = AdaptadorDoMapa(GrafoDeFatos(repo.todos()))
            lentes = Lentes(raiz / "lentes.json", repo.areas())
            return GeradorDeMapa(
                adaptador.nos(),
                adaptador.arestas(),
                lentes.cruas(),
                ConfigDoMapa(titulo=titulo, raiz=str(raiz)),
            )

        return ComandoMapa(fabrica, raiz).executar(args)


class ComandoDoutor(Comando):
    nome = "doutor"
    aliases = ("doctor",)

    def configurar(self, subparser):
        subparser.add_argument("--adopt", "--adotar", dest="adotar", default=None, help=t("ajuda-adotar"))
        subparser.add_argument("--reason", "--motivo", dest="motivo", default=None, help=t("ajuda-motivo"))

    def executar(self, args):
        if args.adotar is not None:
            if not args.motivo:
                self._cli.erro.write("%s\n" % t("adotar-sem-motivo"))
                return 1
            return self._emitir(self._porta().adotar(args.adotar, args.motivo), args)
        achados = Doutor(self._cli.raiz).examinar()
        payload = {
            "limpo": not achados,
            "achados": [{"tipo": a.tipo, "id": a.id, "detalhe": a.detalhe} for a in achados],
        }
        if args.json:
            json.dump(payload, self._cli.saida, ensure_ascii=False)
            self._cli.saida.write("\n")
        elif not achados:
            self._cli.saida.write("%s\n" % t("limpo"))
        else:
            for achado in achados:
                self._cli.saida.write("%s %s: %s\n" % (tipo(achado.tipo), achado.id, achado.detalhe))
        return 0 if not achados else 1


class ComandoAdotarTudo(Comando):
    nome = "adotar-tudo"
    aliases = ("adopt-all",)

    def configurar(self, subparser):
        subparser.add_argument("--reason", "--motivo", dest="motivo", required=True, help=t("ajuda-motivo"))

    def executar(self, args):
        tipos = ("sem-evento", "alterado-fora-da-porta", "frontmatter-invalido")
        vistos = set()
        refs = []
        for achado in Doutor(self._cli.raiz).examinar():
            if achado.tipo not in tipos or achado.id in vistos:
                continue
            vistos.add(achado.id)
            refs.append(achado.id)
        adotados, recusados = self._porta().adotar_varios(refs, args.motivo)
        for ident, mensagem in recusados:
            self._cli.erro.write("%s: %s\n" % (ident, mensagem))
        self._cli.saida.write("%s\n" % t("adotados", len(adotados)))
        return 1 if recusados else 0


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
            ComandoRecall(self),
            ComandoAdd(self), ComandoUpdate(self), ComandoRm(self),
            ComandoPurga(self), ComandoLog(self), ComandoDoMapa(self),
            ComandoDoutor(self), ComandoAdotarTudo(self),
        )

    @property
    def raiz(self):
        casa = self.ambiente.get("MEMORO_HOME")
        if casa:
            return Path(casa)
        return Path(self.ambiente["HOME"]) / "memoro"

    def executar(self, argv):
        anterior = mensagens.sobrescrita
        mensagens.sobrescrita = self.ambiente.get("MEMORO_LANG", "")
        try:
            return self._executar(argv)
        finally:
            mensagens.sobrescrita = anterior

    def _executar(self, argv):
        analisador = argparse.ArgumentParser(prog="memoro", description=t("ajuda-memoro"))
        subs = analisador.add_subparsers(dest="comando", required=True)
        for comando in self._comandos:
            extras = {}
            if comando.aliases:
                extras["aliases"] = list(comando.aliases)
            sub = subs.add_parser(comando.nome, help=t("ajuda-" + comando.nome), **extras)
            comando.configurar(sub)
            sub.add_argument("--json", action="store_true")
            sub.set_defaults(_comando=comando)
        antigo, antigo_out = sys.stderr, sys.stdout
        sys.stderr, sys.stdout = self.erro, self.saida
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
            sys.stderr, sys.stdout = antigo, antigo_out
        try:
            return args._comando.executar(args)
        except Recusa as exc:
            self.erro.write("%s\n" % t("recusado", exc))
            if args.json:
                json.dump({"ok": False, "motivo": str(exc)}, self.saida, ensure_ascii=False)
                self.saida.write("\n")
            return 1
        except ErroDeLente as exc:
            self.erro.write("%s\n" % exc)
            return 2
        except (ErroDeRepositorio, IdInvalido) as exc:
            self.erro.write("%s\n" % exc)
            return 1


def main():
    try:
        return Cli(sys.stdin, sys.stdout, sys.stderr, os.environ).executar(sys.argv[1:])
    except BrokenPipeError:
        return 0
