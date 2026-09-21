from __future__ import annotations

import unittest

from memoro.dominio import Fato, IdDeFato
from memoro.formato import EscritorDeFrontmatter, LeitorDeFrontmatter


class TestLeitor(unittest.TestCase):
    def setUp(self):
        self.leitor = LeitorDeFrontmatter()

    def test_le_campos_e_corpo(self):
        campos, corpo = self.leitor.ler(
            "---\nname: forno\ndescription: forno a gás: o de casa\narea: casa\n---\n\nliga no botão\n")
        self.assertEqual(campos["name"], "forno")
        self.assertEqual(campos["description"], "forno a gás: o de casa")  # só o primeiro ':' separa
        self.assertEqual(campos["area"], "casa")
        self.assertEqual(campos["uses"], [])
        self.assertEqual(campos["scope"], [])
        self.assertEqual(corpo, "liga no botão\n")

    def test_lista_inline_com_e_sem_colchete(self):
        campos, _ = self.leitor.ler("---\nname: x\nuses: [a, detalha:b]\nscope: casa, estudo\n---\n")
        self.assertEqual(campos["uses"], ["a", "detalha:b"])
        self.assertEqual(campos["scope"], ["casa", "estudo"])

    def test_lista_em_bloco(self):
        campos, _ = self.leitor.ler("---\nname: x\nuses:\n  - a\n  - b\nscope:\n- casa\n---\ncorpo")
        self.assertEqual(campos["uses"], ["a", "b"])
        self.assertEqual(campos["scope"], ["casa"])

    def test_sem_frontmatter_devolve_tudo_como_corpo(self):
        campos, corpo = self.leitor.ler("# título\ntexto\n")
        self.assertEqual(campos, {"uses": [], "scope": []})
        self.assertEqual(corpo, "# título\ntexto\n")

    def test_campo_desconhecido_e_preservado(self):
        campos, _ = self.leitor.ler("---\nname: x\nmotivo: duplicado\n---\n")
        self.assertEqual(campos["motivo"], "duplicado")


class TestEscritor(unittest.TestCase):
    def test_ida_e_volta(self):
        fato = Fato(IdDeFato("casa/cozinha", "forno"), "forno a gás", "liga no botão\n",
                    uses=("fogao", "detalha:casa/gas"), scope=("casa", "hobby"))
        texto = EscritorDeFrontmatter().escrever(fato)
        self.assertTrue(texto.startswith("---\nname: forno\ndescription: forno a gás\narea: casa/cozinha\n"))
        campos, corpo = LeitorDeFrontmatter().ler(texto)
        self.assertEqual(campos["uses"], ["fogao", "detalha:casa/gas"])
        self.assertEqual(campos["scope"], ["casa", "hobby"])
        self.assertEqual(corpo, "liga no botão\n")

    def test_lista_vazia_nao_vira_linha(self):
        texto = EscritorDeFrontmatter().escrever(Fato(IdDeFato("casa", "x"), "d", "c\n"))
        self.assertNotIn("uses", texto)
        self.assertNotIn("scope", texto)

    def test_extras_entram_no_fim_do_bloco(self):
        texto = EscritorDeFrontmatter().escrever(Fato(IdDeFato("casa", "x"), "d", "c\n"),
                                                 extras={"motivo": "duplicado"})
        campos, corpo = LeitorDeFrontmatter().ler(texto)
        self.assertEqual(campos["motivo"], "duplicado")
        self.assertEqual(corpo, "c\n")

    def test_descricao_nao_quebra_o_bloco(self):
        """Quebra de linha na descrição injetaria campo novo no frontmatter."""
        texto = EscritorDeFrontmatter().escrever(Fato(IdDeFato("casa", "x"), "linha um\narea: trabalho", "c\n"))
        campos, _ = LeitorDeFrontmatter().ler(texto)
        self.assertEqual(campos["area"], "casa")
        self.assertEqual(campos["description"], "linha um area: trabalho")

    def test_corpo_que_traz_frontmatter_nao_duplica_o_bloco(self):
        fato = Fato(IdDeFato("casa", "x"), "d", "---\nname: outro\n---\ntexto\n")
        campos, corpo = LeitorDeFrontmatter().ler(EscritorDeFrontmatter().escrever(fato))
        self.assertEqual(campos["name"], "x")
        self.assertEqual(corpo, "texto\n")


if __name__ == "__main__":
    unittest.main()
