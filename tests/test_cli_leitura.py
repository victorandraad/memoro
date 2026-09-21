from __future__ import annotations

import json

from tests.apoio import ComRaiz


class TestCliLeitura(ComRaiz):
    def test_init_cria_a_raiz(self):
        codigo, saida, _ = self.cli("init")
        self.assertEqual(codigo, 0)
        self.assertTrue((self.raiz / "areas").is_dir())
        self.assertIn(str(self.raiz), saida)

    def test_ls_lista_e_filtra_por_area(self):
        self.escrever("casa", "fogao", desc="quatro bocas")
        self.escrever("casa/cozinha", "forno")
        self.escrever("trabalho", "rotina")
        codigo, saida, _ = self.cli("ls")
        self.assertEqual(codigo, 0)
        self.assertEqual(len(saida.splitlines()), 3)
        self.assertIn("casa/fogao\tquatro bocas", saida)
        _, saida, _ = self.cli("ls", "casa")
        self.assertEqual(len(saida.splitlines()), 2)
        _, saida, _ = self.cli("ls", "casa", "--json")
        self.assertEqual([i["id"] for i in json.loads(saida)], ["casa/cozinha/forno", "casa/fogao"])

    def test_show_por_id_e_json(self):
        self.escrever("casa", "fogao", desc="quatro bocas", corpo="acende com fósforo\n")
        codigo, saida, _ = self.cli("show", "casa/fogao")
        self.assertEqual(codigo, 0)
        self.assertIn("acende com fósforo", saida)
        self.assertIn("name: fogao", saida)
        _, saida, _ = self.cli("show", "fogao", "--json")
        d = json.loads(saida)
        self.assertEqual((d["id"], d["nome"], d["area"], d["descricao"], d["corpo"]),
                         ("casa/fogao", "fogao", "casa", "quatro bocas", "acende com fósforo\n"))

    def test_show_ambiguo_lista_as_candidatas_e_sai_1(self):
        self.escrever("casa", "rotina")
        self.escrever("trabalho", "rotina")
        codigo, _, erro = self.cli("show", "rotina")
        self.assertEqual(codigo, 1)
        self.assertIn("casa/rotina", erro)
        self.assertIn("trabalho/rotina", erro)

    def test_show_inexistente_sai_1(self):
        self.assertEqual(self.cli("show", "nada")[0], 1)

    def test_uso_errado_sai_2(self):
        self.assertEqual(self.cli("comando-que-nao-existe")[0], 2)
        self.assertEqual(self.cli()[0], 2)
        self.assertEqual(self.cli("show")[0], 2)

    def test_raiz_padrao_vem_do_ambiente_injetado(self):
        """Sem MEMORO_HOME a raiz cai em HOME/memoro: nada de caminho fixo no código."""
        import io
        from memoro.cli import Cli
        saida = io.StringIO()
        casa = self.raiz / "lar"
        casa.mkdir()
        Cli(entrada=io.StringIO(), saida=saida, erro=io.StringIO(), ambiente={"HOME": str(casa)}).executar(["init"])
        self.assertTrue((casa / "memoro" / "areas").is_dir())
