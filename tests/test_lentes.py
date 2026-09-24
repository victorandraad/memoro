from __future__ import annotations

import json

from memoro.grafo import GrafoDeFatos
from memoro.lentes import ErroDeLente, Lentes, Recall
from memoro.repositorio import RepositorioDeFatos
from tests.apoio import ComRaiz


class ComRecall(ComRaiz):
    def setUp(self):
        super().setUp()
        self.escrever("casa", "cozinha", desc="o cômodo")
        self.escrever("casa/cozinha", "forno", uses=["detalha:trabalho/escala"])
        self.escrever("casa", "fogao", uses=["gas"])
        self.escrever("casa", "gas", uses=["estudo/quimica"])
        self.escrever("estudo", "quimica")
        self.escrever("trabalho", "escala")
        self.escrever("hobby", "violao", scope=["casa"], corpo="longe de [[trabalho/escala]]\n")
        self.escrever("trabalho", "rotina", scope=["hobby"])
        (self.raiz / "lentes.json").write_text(json.dumps({
            "lar": ["casa"], "so-cozinha": ["casa/cozinha"], "nenhuma": [], "quebrada": ["porao"]}), encoding="utf-8")

    def recall(self, teto=None):
        fatos = RepositorioDeFatos(self.raiz).todos()
        return Recall(fatos, GrafoDeFatos(fatos), teto=teto)

    def ids(self, resultado):
        return [(str(i.fato.id), i.motivo) for i in resultado.itens]


class TestLentes(ComRecall):
    def test_le_o_arquivo(self):
        lentes = Lentes(self.raiz / "lentes.json", RepositorioDeFatos(self.raiz).areas())
        self.assertEqual(lentes.nomes(), ["lar", "nenhuma", "quebrada", "so-cozinha"])
        self.assertEqual(lentes.escopos("lar"), ["casa"])
        self.assertEqual(lentes.escopos("nenhuma"), [])

    def test_lente_desconhecida_lista_as_que_existem(self):
        lentes = Lentes(self.raiz / "lentes.json", RepositorioDeFatos(self.raiz).areas())
        with self.assertRaises(ErroDeLente) as ctx:
            lentes.escopos("laar")
        self.assertIn("lar", str(ctx.exception))

    def test_alvo_sem_pasta_e_erro_e_nao_silencio(self):
        lentes = Lentes(self.raiz / "lentes.json", RepositorioDeFatos(self.raiz).areas())
        with self.assertRaises(ErroDeLente) as ctx:
            lentes.escopos("quebrada")
        self.assertIn("porao", str(ctx.exception))

    def test_sem_arquivo_nao_ha_lente(self):
        self.assertEqual(Lentes(self.raiz / "nao-existe.json", []).nomes(), [])


class TestRecall(ComRecall):
    def test_escopo_pega_a_area_as_subareas_e_quem_declara_scope(self):
        r = self.recall().por_escopos(["casa"], saltos=0)
        self.assertEqual(self.ids(r), [("casa/cozinha", "escopo"), ("casa/cozinha/forno", "escopo"),
                                       ("casa/fogao", "escopo"), ("casa/gas", "escopo"), ("hobby/violao", "escopo")])

    def test_scope_declarado_tira_o_fato_da_propria_area(self):
        """trabalho/rotina declarou scope hobby: serve a hobby, nao a trabalho."""
        self.assertEqual(self.ids(self.recall().por_escopos(["trabalho"], saltos=0)), [("trabalho/escala", "escopo")])
        self.assertIn(("trabalho/rotina", "escopo"), self.ids(self.recall().por_escopos(["hobby"], saltos=0)))

    def test_prefixo_de_subarea_recorta_so_a_pasta(self):
        r = self.recall().por_escopos(["casa/cozinha"], saltos=0)
        self.assertEqual(self.ids(r), [("casa/cozinha/forno", "escopo")])

    def test_um_salto_traz_filho_e_heranca_marcando_o_motivo(self):
        r = self.recall().por_escopos(["casa/cozinha"], saltos=1)
        self.assertEqual(self.ids(r), [("casa/cozinha/forno", "escopo"), ("trabalho/escala", "detalha")])
        r = self.recall().por_escopos(["casa"], saltos=1)
        self.assertEqual(self.ids(r)[5:], [("trabalho/escala", "detalha"), ("estudo/quimica", "herda")])  # link nunca expande

    def test_saltos_seguem_a_cadeia(self):
        self.escrever("hobby", "churrasco", uses=["casa/fogao"])
        um = self.ids(self.recall().por_escopos(["hobby"], saltos=1))
        dois = self.ids(self.recall().por_escopos(["hobby"], saltos=2))
        tres = self.ids(self.recall().por_escopos(["hobby"], saltos=3))
        self.assertIn(("casa/fogao", "herda"), um)
        self.assertNotIn(("casa/gas", "herda"), um)
        self.assertIn(("casa/gas", "herda"), dois)
        self.assertIn(("estudo/quimica", "herda"), tres)

    def test_filho_entra_pela_aresta(self):
        self.escrever("hobby", "reforma", uses=["casa/cozinha"])
        r = self.ids(self.recall().por_escopos(["hobby"], saltos=2))
        self.assertIn(("casa/cozinha", "herda"), r)
        self.assertIn(("casa/cozinha/forno", "filho"), r)

    def test_escopo_vazio_e_zero_fatos_e_none_e_tudo(self):
        self.assertEqual(self.recall().por_escopos([]).itens, ())
        self.assertEqual(len(self.recall().por_escopos(None).itens), 8)

    def test_teto_corta_e_avisa_quantos_ficaram_de_fora(self):
        r = self.recall(teto=3).por_escopos(["casa"], saltos=1)
        self.assertEqual((len(r.itens), r.cortados), (3, 4))
        self.assertEqual(self.ids(r)[0], ("casa/cozinha", "escopo"))  # o escopo direto entra antes do herdado


class TestCliRecall(ComRecall):
    def test_lens_em_texto(self):
        codigo, saida, _ = self.cli("recall", "--lens", "so-cozinha")
        self.assertEqual(codigo, 0)
        linhas = saida.splitlines()
        self.assertEqual(linhas[0], "# recall: so-cozinha (2 fatos)")
        self.assertEqual(linhas[1:], ["- casa/cozinha/forno: uma descrição",
                                      "- trabalho/escala: uma descrição (detalha)"])

    def test_scope_saltos_e_json(self):
        codigo, saida, _ = self.cli("recall", "--scope", "casa/cozinha,estudo", "--saltos", "0", "--json")
        d = json.loads(saida)
        self.assertEqual(codigo, 0)
        self.assertEqual([(i["id"], i["motivo"]) for i in d["itens"]],
                         [("casa/cozinha/forno", "escopo"), ("estudo/quimica", "escopo")])
        self.assertEqual(sorted(d["itens"][0]), ["area", "corpo", "descricao", "id", "motivo", "nome"])
        self.assertEqual(d["cortados"], 0)

    def test_lente_vazia_e_zero_de_proposito(self):
        codigo, saida, _ = self.cli("recall", "--lens", "nenhuma")
        self.assertEqual((codigo, saida.splitlines()), (0, ["# recall: nenhuma (0 fatos)"]))

    def test_lente_errada_sai_2(self):
        codigo, _, erro = self.cli("recall", "--lens", "laar")
        self.assertEqual(codigo, 2)
        self.assertIn("lar", erro)
        self.assertEqual(self.cli("recall", "--lens", "quebrada")[0], 2)

    def test_teto_vem_do_ambiente(self):
        import io
        from memoro.cli import Cli
        saida = io.StringIO()
        Cli(entrada=io.StringIO(), saida=saida, erro=io.StringIO(),
            ambiente={"MEMORO_HOME": str(self.raiz), "MEMORO_RECALL_CAP": "2"}).executar(["recall", "--lens", "lar"])
        linhas = saida.getvalue().splitlines()
        self.assertEqual(linhas[0], "# recall: lar (2 fatos, 5 cortados pelo teto)")
        self.assertEqual(len(linhas), 3)

    def test_list_lenses_em_texto_e_json(self):
        codigo, saida, _ = self.cli("recall", "--list-lenses")
        self.assertEqual(codigo, 0)
        self.assertEqual(saida.splitlines(), [
            "lar\tcasa", "nenhuma\t", "quebrada\tporao", "so-cozinha\tcasa/cozinha"])
        codigo, saida, _ = self.cli("recall", "--list-lenses", "--json")
        self.assertEqual(codigo, 0)
        self.assertEqual(json.loads(saida), [
            {"nome": "lar", "escopos": ["casa"]}, {"nome": "nenhuma", "escopos": []},
            {"nome": "quebrada", "escopos": ["porao"]}, {"nome": "so-cozinha", "escopos": ["casa/cozinha"]}])

    def test_json_traz_o_corpo_do_fato(self):
        _, saida, _ = self.cli("recall", "--scope", "hobby", "--saltos", "0", "--json")
        itens = {i["id"]: i for i in json.loads(saida)["itens"]}
        self.assertEqual(itens["trabalho/rotina"]["corpo"], "corpo\n")

    def test_lente_nao_devolve_fato_so_de_outra_lente(self):
        self.escrever("oficina", "torno", desc="só da oficina")
        (self.raiz / "lentes.json").write_text(json.dumps({
            "lar": ["casa"], "oficio": ["oficina"]}), encoding="utf-8")
        _, saida, _ = self.cli("recall", "--lens", "lar", "--saltos", "3", "--json")
        ids = [i["id"] for i in json.loads(saida)["itens"]]
        self.assertIn("casa/fogao", ids)
        self.assertNotIn("oficina/torno", ids)
        _, saida, _ = self.cli("recall", "--lens", "oficio", "--json")
        self.assertEqual([i["id"] for i in json.loads(saida)["itens"]], ["oficina/torno"])
