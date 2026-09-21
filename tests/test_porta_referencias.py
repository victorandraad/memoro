from __future__ import annotations

import json

from memoro.porta import PortaDeEscrita, Recusa
from memoro.repositorio import RepositorioDeFatos
from tests.apoio import ComRaiz


class ComPorta(ComRaiz):
    def setUp(self):
        super().setUp()
        self.repo = RepositorioDeFatos(self.raiz)
        self.repo.inicializar()
        for area in ("estudo", "hobby"):
            (self.raiz / "areas" / area).mkdir()
        self.porta = PortaDeEscrita.padrao(self.raiz, usuario="teste")


class TestReferenciasNaPorta(ComPorta):
    def test_uses_pro_vazio_recusa(self):
        with self.assertRaises(Recusa) as ctx:
            self.porta.add("casa", "y", "d", "c\n", uses=("fantasma",))
        self.assertIn("fantasma", str(ctx.exception))

    def test_uses_ambiguo_avisa_mas_grava(self):
        self.porta.add("estudo", "x", "plano de leitura do semestre", "c\n")
        self.porta.add("trabalho", "x", "escala de plantão do mês", "c\n")
        r = self.porta.add("casa", "y", "d", "cita [[x]]\n", uses=("x",))
        self.assertEqual(r.avisos, ("ambíguo: [[x]] em casa/y pode ser estudo/x ou trabalho/x",
                                    "ambíguo: uses x em casa/y pode ser estudo/x ou trabalho/x"))
        self.assertTrue(r.caminho.is_file())
        self.assertTrue(self.porta.diario.ler()[-1].ok)
        r = self.porta.update("casa/y", uses=("estudo/x",), corpo="cita [[trabalho/x]]\n")
        self.assertEqual(r.avisos, ())

    def test_uses_na_mesma_area_nao_avisa(self):
        self.porta.add("estudo", "x", "plano de leitura do semestre", "c\n")
        self.porta.add("trabalho", "x", "escala de plantão do mês", "c\n")
        self.assertEqual(self.porta.add("estudo", "y", "d", "c\n", uses=("x",)).avisos, ())

    def test_aviso_aparece_na_cli_sem_mudar_o_exit(self):
        self.porta.add("estudo", "x", "plano de leitura do semestre", "c\n")
        self.porta.add("trabalho", "x", "escala de plantão do mês", "c\n")
        codigo, saida, erro = self.cli("add", "casa", "y", "--desc", "d", "--uses", "x", entrada="c\n")
        self.assertEqual((codigo, saida.strip()), (0, "areas/casa/y.md"))
        self.assertIn("aviso: ambíguo: uses x em casa/y pode ser estudo/x ou trabalho/x", erro)
        _, saida, _ = self.cli("add", "casa", "z", "--desc", "outra coisa bem diferente", "--uses", "x", "--json",
                               entrada="c\n")
        self.assertEqual(len(json.loads(saida)["avisos"]), 1)


class TestQuaseDuplicata(ComPorta):
    def setUp(self):
        super().setUp()
        self.porta.add("casa", "conta-de-luz", "vence todo dia 10, débito automático", "c\n")

    def test_nome_parecido_na_mesma_area_recusa_apontando_o_id(self):
        with self.assertRaises(Recusa) as ctx:
            self.porta.add("casa", "conta-da-luz", "boleto da energia", "c\n")
        self.assertIn("parecido com casa/conta-de-luz", str(ctx.exception))
        self.assertIn("--novo-mesmo-assim", str(ctx.exception))
        self.assertFalse(self.porta.diario.ler()[-1].ok)

    def test_descricao_parecida_na_mesma_area_recusa(self):
        with self.assertRaises(Recusa):
            self.porta.add("casa", "energia", "vence todo dia 10, debito automatico", "c\n")

    def test_em_outra_area_passa(self):
        self.porta.add("trabalho", "conta-da-luz", "vence todo dia 10, débito automático", "c\n")

    def test_coisa_diferente_passa(self):
        self.porta.add("casa", "horta", "regar de manhã, nunca ao meio-dia", "c\n")

    def test_novo_mesmo_assim_libera_e_update_nunca_acusa(self):
        self.porta.add("casa", "conta-da-luz", "boleto da energia", "c\n", novo_mesmo_assim=True)
        self.porta.update("casa/conta-da-luz", descricao="vence todo dia 10, débito automático")

    def test_flag_na_cli(self):
        self.assertEqual(self.cli("add", "casa", "conta-da-luz", "--desc", "x", entrada="c")[0], 1)
        self.assertEqual(self.cli("add", "casa", "conta-da-luz", "--desc", "x", "--novo-mesmo-assim", entrada="c")[0], 0)
