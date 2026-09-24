"""Regressões dos achados da revisão cruzada: durabilidade, segredo fora do corpo, escrita parcial."""
from __future__ import annotations

import os
from datetime import date
from unittest import mock

from memoro.diario import DiarioDeEventos
from memoro.dominio import Evento, Fato, IdDeFato
from memoro.porta import PortaDeEscrita, Recusa
from memoro.repositorio import RepositorioDeFatos
from tests.apoio import ComRaiz, em_portugues

GITHUB = "gh" + "p_" + "a1B2" * 9
AWS_TEMPORARIA = "AS" + "IA" + "ABCDEFGHIJKLMNOP"

setUpModule = em_portugues


class TestSegredoForaDoCorpo(ComRaiz):
    def setUp(self):
        super().setUp()
        RepositorioDeFatos(self.raiz).inicializar()
        self.porta = PortaDeEscrita.padrao(self.raiz, usuario="teste")

    def recusado_sem_vazar(self, segredo, **kw):
        with self.assertRaises(Recusa) as ctx:
            self.porta.add("casa", "x", kw.pop("descricao", "d"), kw.pop("corpo", "c\n"), **kw)
        self.assertIn("segredo", str(ctx.exception))
        self.assertNotIn(segredo, str(ctx.exception))
        self.assertNotIn(segredo, (self.raiz / "eventos.jsonl").read_text(encoding="utf-8"))
        self.assertFalse((self.raiz / "areas/casa/x.md").exists())

    def test_segredo_em_uses_nao_vai_pro_diario(self):
        self.recusado_sem_vazar(GITHUB, uses=(GITHUB,))
        self.recusado_sem_vazar(GITHUB, uses=("detalha:" + GITHUB,))

    def test_segredo_em_scope(self):
        self.recusado_sem_vazar(GITHUB, scope=(GITHUB,))

    def test_chave_aws_temporaria(self):
        self.recusado_sem_vazar(AWS_TEMPORARIA, corpo="chave %s\n" % AWS_TEMPORARIA)


class TestDurabilidade(ComRaiz):
    def test_gravar_faz_fsync_antes_de_trocar_o_arquivo(self):
        ordem = []
        with mock.patch("os.fsync", side_effect=lambda fd: ordem.append("fsync")), \
                mock.patch("os.replace", side_effect=lambda a, b, _r=os.replace: (ordem.append("replace"), _r(a, b))[1]):
            RepositorioDeFatos(self.raiz).gravar(Fato(IdDeFato("casa", "x"), "d", "c\n"))
        self.assertIn("replace", ordem)
        self.assertIn("fsync", ordem[:ordem.index("replace")])

    def test_lixeira_esta_no_disco_antes_de_apagar_a_origem(self):
        repo = RepositorioDeFatos(self.raiz)
        repo.gravar(Fato(IdDeFato("casa", "x"), "d", "c\n"))
        ordem = []
        with mock.patch("os.fsync", side_effect=lambda fd: ordem.append("fsync")), \
                mock.patch("pathlib.Path.unlink", autospec=True,
                           side_effect=lambda p, *a, **k: ordem.append("unlink")), \
                mock.patch("os.unlink", side_effect=lambda p, *a, **k: ordem.append("unlink")), \
                mock.patch("os.remove", side_effect=lambda p, *a, **k: ordem.append("unlink")):
            repo.mover_para_lixeira(IdDeFato("casa", "x"), "motivo", "teste", date(2030, 1, 10))
        self.assertIn("unlink", ordem)
        self.assertIn("fsync", ordem[:ordem.index("unlink")])

    def test_diario_completa_escrita_parcial_e_faz_fsync(self):
        evento = Evento("2030-01-02T03:04:05+00:00", "teste", "add", "casa/x", "casa", "r" * 200, True, "", "")
        diario = DiarioDeEventos(self.raiz / "eventos.jsonl")
        real = os.write
        with mock.patch("os.write", side_effect=lambda fd, b: real(fd, bytes(b)[:7])), \
                mock.patch("os.fsync") as fsync:
            diario.registrar(evento)
        self.assertEqual(diario.ler(), [evento])
        self.assertTrue(fsync.called)
