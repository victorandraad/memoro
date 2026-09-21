from __future__ import annotations

import dataclasses
import unittest

from memoro.dominio import Fato, IdDeFato, IdInvalido, Relacao


class TestIdDeFato(unittest.TestCase):
    def test_escreve_area_barra_nome(self):
        self.assertEqual(str(IdDeFato("casa", "conta-de-luz")), "casa/conta-de-luz")
        self.assertEqual(str(IdDeFato("casa/cozinha", "forno")), "casa/cozinha/forno")

    def test_de_texto_separa_area_e_nome(self):
        i = IdDeFato.de_texto("casa/cozinha/forno")
        self.assertEqual((i.area, i.nome, i.topo, i.subarea), ("casa/cozinha", "forno", "casa", "cozinha"))
        self.assertEqual(IdDeFato.de_texto("casa/forno").subarea, "")

    def test_caminho_relativo(self):
        self.assertEqual(IdDeFato("casa", "forno").caminho, "areas/casa/forno.md")

    def test_mesmo_nome_em_duas_areas_sao_ids_diferentes(self):
        self.assertNotEqual(IdDeFato("casa", "rotina"), IdDeFato("trabalho", "rotina"))
        self.assertEqual(len({IdDeFato("casa", "rotina"), IdDeFato("casa", "rotina")}), 1)

    def test_recusa_travessia_e_caractere_estranho(self):
        ruins = [("..", "x"), ("casa", ".."), ("casa/..", "x"), ("casa", "../x"), ("/etc", "x"),
                 ("casa", "a/b"), ("casa", ""), ("", "x"), ("casa", "x.md"), ("casa", "A"),
                 ("casa", "a b"), ("casa\\x", "y"), ("_lixeira", "x"), ("casa", "-x"), ("casa", "x\n")]
        for area, nome in ruins:
            with self.assertRaises(IdInvalido, msg=repr((area, nome))):
                IdDeFato(area, nome)

    def test_recusa_mais_de_um_nivel_de_subpasta(self):
        with self.assertRaises(IdInvalido):
            IdDeFato("casa/cozinha/gaveta", "x")

    def test_de_texto_sem_area_e_invalido(self):
        with self.assertRaises(IdInvalido):
            IdDeFato.de_texto("solto")


class TestRelacao(unittest.TestCase):
    def test_sem_prefixo_e_uses(self):
        self.assertEqual(Relacao.de_texto("forno"), Relacao("uses", "forno"))

    def test_prefixo_vira_tipo(self):
        self.assertEqual(Relacao.de_texto("contradiz:casa/forno"), Relacao("contradiz", "casa/forno"))
        self.assertTrue(Relacao.de_texto("contradiz:x").conhecida)
        self.assertFalse(Relacao.de_texto("inventada:x").conhecida)

    def test_volta_pro_texto(self):
        for t in ("forno", "detalha:forno"):
            self.assertEqual(str(Relacao.de_texto(t)), t)


class TestFato(unittest.TestCase):
    def test_e_imutavel_e_expoe_nome_e_area(self):
        f = Fato(IdDeFato("casa", "forno"), "forno a gás", "liga no botão\n", uses=("detalha:fogao",))
        self.assertEqual((f.nome, f.area, f.scope), ("forno", "casa", ()))
        self.assertEqual(f.relacoes, (Relacao("detalha", "fogao"),))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            f.descricao = "outra"


if __name__ == "__main__":
    unittest.main()
