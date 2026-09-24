from __future__ import annotations

import json

from memoro.grafo import Ambiguo, Aresta, GrafoDeFatos, No, Pendente
from memoro.repositorio import RepositorioDeFatos
from tests.apoio import ComRaiz, em_portugues

setUpModule = em_portugues


class ComGrafo(ComRaiz):
    def grafo(self):
        return GrafoDeFatos(RepositorioDeFatos(self.raiz).todos())


class TestResolucao(ComGrafo):
    """Os quatro casos da resolução de referência, em uses e em [[link]]."""

    def test_1_id_qualificado_casa_exato(self):
        self.escrever("casa", "rotina")
        self.escrever("trabalho", "rotina")
        self.escrever("estudo", "plano", uses=["trabalho/rotina"], corpo="veja [[casa/rotina]]\n")
        g = self.grafo()
        self.assertIn(Aresta("estudo/plano", "trabalho/rotina", "uses"), g.arestas())
        self.assertIn(Aresta("estudo/plano", "casa/rotina", "link"), g.arestas())
        self.assertEqual((g.pendentes(), g.ambiguos()), ([], []))

    def test_2_nome_solto_resolve_primeiro_na_area_de_quem_cita(self):
        self.escrever("casa", "rotina")
        self.escrever("trabalho", "rotina")
        self.escrever("casa", "plano", uses=["rotina"], corpo="e [[rotina]]\n")
        g = self.grafo()
        self.assertEqual([a for a in g.arestas() if a.origem == "casa/plano"],
                         [Aresta("casa/plano", "casa/rotina", "link"), Aresta("casa/plano", "casa/rotina", "uses")])
        self.assertEqual(g.ambiguos(), [])

    def test_3_nome_solto_unico_no_repositorio_resolve_de_qualquer_area(self):
        self.escrever("trabalho", "rotina")
        self.escrever("casa", "plano", uses=["detalha:rotina"])
        self.assertEqual(self.grafo().arestas(), [Aresta("casa/plano", "trabalho/rotina", "detalha")])

    def test_4_nome_solto_em_duas_areas_alheias_vira_ambiguo(self):
        self.escrever("estudo", "x")
        self.escrever("trabalho", "x")
        self.escrever("casa", "y", uses=["x"], corpo="cita [[x]] aqui\n")
        g = self.grafo()
        self.assertEqual(g.arestas(), [])
        self.assertEqual(g.pendentes(), [])
        self.assertEqual(g.ambiguos(), [Ambiguo("casa/y", "x", "link", ("estudo/x", "trabalho/x")),
                                        Ambiguo("casa/y", "x", "uses", ("estudo/x", "trabalho/x"))])
        self.assertEqual(g.ambiguos()[0].mensagem, "ambíguo: [[x]] em casa/y pode ser estudo/x ou trabalho/x")
        self.assertEqual(g.ambiguos_de("casa/y"), g.ambiguos())
        self.assertEqual(g.ambiguos_de("estudo/x"), [])

    def test_homonimos_continuam_enderecaveis_e_sao_dois_nos(self):
        self.escrever("casa", "rotina", desc="a de casa")
        self.escrever("trabalho", "rotina", desc="a do trabalho")
        nos = {n.id: n for n in self.grafo().nos()}
        self.assertEqual(sorted(nos), ["casa/rotina", "trabalho/rotina"])
        self.assertEqual((nos["casa/rotina"].descricao, nos["trabalho/rotina"].descricao),
                         ("a de casa", "a do trabalho"))

    def test_resolver_avulso(self):
        self.escrever("estudo", "x")
        self.escrever("trabalho", "x")
        g = self.grafo()
        self.assertEqual(g.resolver("x", "estudo").id, "estudo/x")
        r = g.resolver("x", "casa")
        self.assertEqual((r.id, r.candidatas), (None, ("estudo/x", "trabalho/x")))
        r = g.resolver("nada", "casa")
        self.assertEqual((r.id, r.candidatas), (None, ()))
        self.assertEqual(g.resolver("../x", "casa").id, None)


class TestArestas(ComGrafo):
    def test_pendente_relacao_desconhecida_e_autocitacao(self):
        self.escrever("casa", "y", uses=["fantasma", "inventada:y"], corpo="[[sumiu]] e [[y]]\n")
        g = self.grafo()
        self.assertEqual(g.arestas(), [])
        self.assertEqual(g.pendentes(), [Pendente("casa/y", "fantasma", "uses"),
                                         Pendente("casa/y", "inventada:y", "uses"),
                                         Pendente("casa/y", "sumiu", "link")])
        self.assertEqual(g.pendentes_de("casa/y"), g.pendentes())

    def test_link_dentro_de_codigo_nao_conta(self):
        self.escrever("casa", "x")
        self.escrever("casa", "y", corpo="`[[x]]`\n```\n[[x]] e [[sumiu]]\n```\n")
        g = self.grafo()
        self.assertEqual((g.arestas(), g.pendentes()), ([], []))

    def test_filho_fato_com_o_nome_da_subpasta_e_o_pai_dela(self):
        self.escrever("casa", "cozinha")
        self.escrever("casa/cozinha", "forno")
        self.escrever("casa/quintal", "horta")  # sem fato casa/quintal: sem pai, sem aresta
        self.assertEqual(self.grafo().arestas(), [Aresta("casa/cozinha", "casa/cozinha/forno", "filho")])

    def test_arestas_saem_ordenadas_e_sem_repeticao(self):
        self.escrever("casa", "a", uses=["b", "b"], corpo="[[b]] [[b]]\n")
        self.escrever("casa", "b")
        self.assertEqual(self.grafo().arestas(), [Aresta("casa/a", "casa/b", "link"), Aresta("casa/a", "casa/b", "uses")])


class TestContratoDoMapa(ComGrafo):
    def test_no_tem_os_campos_que_o_mapa_precisa(self):
        self.escrever("casa/cozinha", "forno", desc="d" * 400)
        self.escrever("casa", "fogao", desc="quatro bocas")
        forno, fogao = self.grafo().nos()
        self.assertEqual(fogao, No("casa/fogao", "fogao", "quatro bocas", "casa", "", "areas/casa/fogao.md"))
        self.assertEqual((forno.area, forno.subarea, forno.caminho, len(forno.descricao)),
                         ("casa/cozinha", "cozinha", "areas/casa/cozinha/forno.md", 300))

    def test_como_dict_e_json_puro(self):
        self.escrever("estudo", "x")
        self.escrever("trabalho", "x")
        self.escrever("casa", "y", uses=["x", "fantasma", "estudo/x"])
        d = json.loads(json.dumps(self.grafo().como_dict()))
        self.assertEqual(sorted(d), ["ambiguos", "arestas", "nos", "pendentes"])
        self.assertEqual(sorted(d["nos"][0]), ["area", "caminho", "descricao", "id", "nome", "subarea"])
        self.assertEqual(d["arestas"], [{"origem": "casa/y", "destino": "estudo/x", "tipo": "uses"}])
        self.assertEqual(d["pendentes"], [{"citado_em": "casa/y", "alvo": "fantasma", "tipo": "uses"}])
        self.assertEqual(d["ambiguos"], [{"citado_em": "casa/y", "alvo": "x", "tipo": "uses",
                                          "candidatas": ["estudo/x", "trabalho/x"]}])
