from __future__ import annotations

import json

from tests.apoio import ComRaiz


class TestCliEscrita(ComRaiz):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.cli("init")[0], 0)

    def test_add_le_o_corpo_do_stdin(self):
        codigo, saida, erro = self.cli("add", "casa", "fogao", "--desc", "quatro bocas", "--scope", "hobby,casa",
                                       entrada="acende com fósforo\n")
        self.assertEqual((codigo, saida.strip(), erro), (0, "areas/casa/fogao.md", ""))
        _, saida, _ = self.cli("show", "casa/fogao", "--json")
        d = json.loads(saida)
        self.assertEqual((d["corpo"], d["scope"]), ("acende com fósforo\n", ["hobby", "casa"]))

    def test_add_json(self):
        _, saida, _ = self.cli("add", "casa", "fogao", "--desc", "d", "--json", entrada="c\n")
        self.assertEqual(json.loads(saida), {"id": "casa/fogao", "caminho": "areas/casa/fogao.md", "avisos": []})

    def test_recusa_sai_1_com_motivo_no_stderr_e_no_log(self):
        codigo, saida, erro = self.cli("add", "porao", "x", "--desc", "d", entrada="c")
        self.assertEqual((codigo, saida), (1, ""))
        self.assertTrue(erro.startswith("recusado: "))
        codigo, saida, _ = self.cli("log", "--recusas", "--json")
        eventos = json.loads(saida)
        self.assertEqual((codigo, len(eventos), eventos[0]["ok"], eventos[0]["op"]), (0, 1, False, "add"))
        codigo, saida, _ = self.cli("add", "porao", "x", "--desc", "d", "--json", entrada="c")
        self.assertEqual(codigo, 1)
        self.assertEqual(json.loads(saida)["ok"], False)

    def test_travessia_pela_cli(self):
        self.assertEqual(self.cli("add", "../x", "y", "--desc", "d", entrada="c")[0], 1)
        self.assertEqual(self.cli("rm", "../../x", "--motivo", "m")[0], 1)
        self.assertEqual(self.cli("show", "../../etc/hostname")[0], 1)

    def test_update_corpo_e_anexar(self):
        self.cli("add", "casa", "fogao", "--desc", "d", entrada="um\n")
        self.assertEqual(self.cli("update", "casa/fogao", "--desc", "d2")[0], 0)
        self.assertEqual(self.cli("update", "fogao", "--anexar", entrada="dois\n")[0], 0)
        d = json.loads(self.cli("show", "casa/fogao", "--json")[1])
        self.assertEqual((d["descricao"], d["corpo"]), ("d2", "um\n\ndois\n"))
        self.assertEqual(self.cli("update", "fogao", "--corpo", entrada="tres\n")[0], 0)
        self.assertEqual(json.loads(self.cli("show", "fogao", "--json")[1])["corpo"], "tres\n")

    def test_rm_purga_e_log(self):
        self.cli("add", "casa", "fogao", "--desc", "d", entrada="c\n")
        self.assertEqual(self.cli("rm", "casa/fogao")[0], 1)
        codigo, saida, _ = self.cli("rm", "casa/fogao", "--motivo", "vendi")
        self.assertEqual((codigo, saida.strip()), (0, "areas/_lixeira/casa/fogao.md"))
        self.assertEqual(self.cli("purga", "--dias", "30")[0], 0)
        codigo, saida, _ = self.cli("log")
        self.assertEqual(codigo, 0)
        self.assertEqual(len(saida.splitlines()), 3)  # add, rm recusado, rm
        self.assertIn("NEG", saida)
        _, saida, _ = self.cli("log", "--id", "casa/fogao", "--json")
        self.assertEqual([e["op"] for e in json.loads(saida)], ["add", "rm", "rm"])
