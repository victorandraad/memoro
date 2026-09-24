"""Saída humana em inglês por padrão; MEMORO_LANG=pt devolve o português. Chaves do --json não mudam."""
from __future__ import annotations

import json
import os
from unittest import mock

from tests.apoio import ComRaiz

TOKEN = "ghp_" + "x" * 36  # fictício


class _Base(ComRaiz):
    IDIOMA = "en"

    def setUp(self):
        super().setUp()
        patch = mock.patch.dict(os.environ, {"MEMORO_LANG": self.IDIOMA})
        patch.start()
        self.addCleanup(patch.stop)
        self.assertEqual(self.cli("init")[0], 0)
        self.assertEqual(self.cli("add", "casa", "conta-de-luz", "--desc", "energy bill", entrada="c\n")[0], 0)


class TestIngles(_Base):
    def test_parecido_recusa_em_ingles_e_cita_flag_inglesa(self):
        codigo, _, erro = self.cli("add", "casa", "conta-da-luz", "--desc", "x", entrada="c\n")
        self.assertEqual(codigo, 1)
        self.assertEqual(
            erro, "refused: similar to casa/conta-de-luz, use update instead or pass --new-anyway\n")

    def test_new_anyway_aceito(self):
        codigo, saida, _ = self.cli("add", "casa", "conta-da-luz", "--desc", "x", "--new-anyway", entrada="c\n")
        self.assertEqual((codigo, saida.strip()), (0, "areas/casa/conta-da-luz.md"))

    def test_novo_mesmo_assim_continua_aceito(self):
        codigo, _, _ = self.cli("add", "casa", "conta-da-luz", "--desc", "x", "--novo-mesmo-assim", entrada="c\n")
        self.assertEqual(codigo, 0)

    def test_segredo(self):
        codigo, _, erro = self.cli("add", "casa", "cofre", "--desc", "x", entrada=TOKEN + "\n")
        self.assertEqual((codigo, erro), (1, "refused: secret of type github-token in body, line 1\n"))

    def test_duplicado(self):
        codigo, _, erro = self.cli("add", "casa", "conta-de-luz", "--desc", "y", entrada="c\n")
        self.assertEqual(codigo, 1)
        self.assertTrue(erro.startswith("refused: id already exists; use update"), erro)

    def test_area_inexistente(self):
        _, _, erro = self.cli("add", "cas", "x", "--desc", "d", entrada="c\n")
        self.assertTrue(erro.startswith("refused: unknown area: cas (did you mean casa?); existing: "), erro)

    def test_json_mantem_chaves(self):
        _, saida, _ = self.cli("add", "casa", "cofre", "--desc", "x", "--json", entrada=TOKEN + "\n")
        d = json.loads(saida)
        self.assertEqual(sorted(d), ["motivo", "ok"])
        self.assertIn("secret of type github-token", d["motivo"])

    def test_recall_cabecalho(self):
        _, saida, _ = self.cli("recall", "--scope", "casa")
        self.assertTrue(saida.startswith("# recall: casa (1 fact)\n"), saida)

    def test_recall_sem_filtro_rotulo_all(self):
        _, saida, _ = self.cli("recall")
        self.assertTrue(saida.startswith("# recall: all ("), saida)

    def test_rm_sem_motivo(self):
        codigo, _, erro = self.cli("rm", "casa/conta-de-luz")
        self.assertEqual((codigo, erro), (1, "refused: rm requires --reason\n"))

    def test_rm_reason_alias(self):
        codigo, _, _ = self.cli("rm", "casa/conta-de-luz", "--reason", "moved house")
        self.assertEqual(codigo, 0)

    def test_fato_nao_encontrado(self):
        codigo, _, erro = self.cli("show", "casa/nada")
        self.assertEqual(codigo, 1)
        self.assertTrue(erro.startswith("fact not found: casa/nada"), erro)

    def test_doutor_limpo(self):
        codigo, saida, _ = self.cli("doctor")
        self.assertEqual((codigo, saida), (0, "clean\n"))

    def test_doutor_achado_em_ingles_e_json_intacto(self):
        self.escrever("casa", "solto")
        codigo, saida, _ = self.cli("doctor")
        self.assertEqual(codigo, 1)
        self.assertIn("no-event casa/solto: file has no live event in the gate\n", saida)
        _, saida, _ = self.cli("doctor", "--json")
        d = json.loads(saida)
        self.assertEqual(sorted(d), ["achados", "limpo"])
        self.assertIn({"tipo": "sem-evento", "id": "casa/solto", "detalhe": "file has no live event in the gate"},
                      d["achados"])

    def test_doutor_adotar_sem_motivo(self):
        codigo, _, erro = self.cli("doctor", "--adopt", "casa/x")
        self.assertEqual((codigo, erro), (1, "doctor --adopt requires --reason\n"))

    def test_adotar_tudo(self):
        self.escrever("casa", "solto")
        codigo, saida, _ = self.cli("adopt-all", "--reason", "legacy")
        self.assertEqual((codigo, saida), (0, "1 adopted\n"))

    def test_help_em_ingles(self):
        codigo, saida, _ = self.cli("add", "--help")
        self.assertEqual(codigo, 0)
        self.assertIn("--new-anyway", saida)
        self.assertIn("--reason", self.cli("rm", "--help")[1])


    def test_flags_inglesas_do_log(self):
        self.cli("rm", "casa/conta-de-luz")
        codigo, saida, _ = self.cli("log", "--refusals", "--user", "teste", "--since", "2000-01-01")
        self.assertEqual(codigo, 0)
        self.assertIn("rm requires --reason", saida)

    def test_idioma_por_contexto_nao_vaza_entre_threads(self):
        import threading

        from memoro import mensagens
        visto = []
        pronto, solta = threading.Event(), threading.Event()

        def em_pt():
            ficha = mensagens.sobrescrita.set("pt")
            pronto.set()
            solta.wait(5)
            visto.append(mensagens.t("limpo"))
            mensagens.sobrescrita.reset(ficha)

        fio = threading.Thread(target=em_pt)
        fio.start()
        pronto.wait(5)
        self.assertEqual(mensagens.t("limpo"), "clean")
        solta.set()
        fio.join()
        self.assertEqual(visto, ["limpo"])


class TestPortugues(_Base):
    IDIOMA = "pt"

    def test_parecido(self):
        _, _, erro = self.cli("add", "casa", "conta-da-luz", "--desc", "x", entrada="c\n")
        self.assertEqual(erro, "recusado: parecido com casa/conta-de-luz: use update ou passe --novo-mesmo-assim\n")

    def test_segredo(self):
        _, _, erro = self.cli("add", "casa", "cofre", "--desc", "x", entrada=TOKEN + "\n")
        self.assertEqual(erro, "recusado: segredo do tipo github-token em corpo, linha 1\n")

    def test_recall_cabecalho(self):
        _, saida, _ = self.cli("recall", "--scope", "casa")
        self.assertTrue(saida.startswith("# recall: casa (1 fatos)\n"), saida)

    def test_rm_sem_motivo(self):
        _, _, erro = self.cli("rm", "casa/conta-de-luz")
        self.assertEqual(erro, "recusado: rm exige motivo\n")

    def test_doutor(self):
        self.assertEqual(self.cli("doutor")[1], "limpo\n")
        self.escrever("casa", "solto")
        self.assertIn("sem-evento casa/solto: arquivo sem evento vivo na porta\n", self.cli("doutor")[1])


class TestLogAntigo(ComRaiz):
    def test_log_recusas_le_motivo_portugues_antigo_em_ingles(self):
        with mock.patch.dict(os.environ, {"MEMORO_LANG": "pt"}):
            self.cli("init")
            self.cli("add", "casa", "velho", "--desc", "d", entrada="c\n")
            self.cli("rm", "casa/velho")
        with mock.patch.dict(os.environ, {"MEMORO_LANG": "en"}):
            codigo, saida, _ = self.cli("log", "--recusas")
            self.assertEqual(codigo, 0)
            self.assertIn("rm exige motivo", saida)
            self.assertEqual(self.cli("doctor")[0], 0)
