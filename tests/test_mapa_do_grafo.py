"""O mapa em cima do núcleo real: adaptador do GrafoDeFatos, comando na Cli e conteúdo hostil."""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from memoro.adaptador_do_mapa import AdaptadorDoMapa
from memoro.grafo import GrafoDeFatos
from memoro.mapa import ConfigDoMapa, GeradorDeMapa
from memoro.repositorio import RepositorioDeFatos
from tests.apoio import ComRaiz

HOSTIL_A = "<script>alert(1)</script> fecha </script> e segue"
HOSTIL_B = '"><img src=x onerror=alert(2)> \\ fim'


class ComAcervo(ComRaiz):
    def setUp(self):
        super().setUp()
        self.escrever("casa", "rotina", desc="rotina da casa")
        self.escrever("estudo", "rotina", desc="blocos de estudo")
        self.escrever("casa", "casa", desc="fato raiz da área")
        self.escrever("casa/horta", "tomate", desc="tomate em vaso", uses=["casa/rotina"],
                      corpo="veja [[nao-existe]] e [[casa/rotina]]\n")
        self.escrever("hobby", "violao", desc="dedilhado", uses=["detalha:estudo/rotina"],
                      corpo="aquece com [[rotina]]\n")
        (self.raiz / "lentes.json").write_text(json.dumps({"dia": ["casa", "estudo"]}), encoding="utf-8")

    def adaptador(self):
        return AdaptadorDoMapa(GrafoDeFatos(RepositorioDeFatos(self.raiz).todos()))


class TesteAdaptador(ComAcervo):
    def test_area_e_o_topo_e_subarea_vazia_vira_none(self):
        nos = {no.id: no for no in self.adaptador().nos()}
        self.assertEqual((nos["casa/horta/tomate"].area, nos["casa/horta/tomate"].subarea), ("casa", "horta"))
        self.assertEqual((nos["casa/rotina"].area, nos["casa/rotina"].subarea), ("casa", None))
        self.assertEqual(nos["casa/horta/tomate"].caminho, "areas/casa/horta/tomate.md")

    def test_pendentes_e_ambiguos_viram_atributos_do_no(self):
        nos = {no.id: no for no in self.adaptador().nos()}
        self.assertEqual(list(nos["casa/horta/tomate"].pendentes), ["nao-existe"])
        self.assertEqual(list(nos["casa/rotina"].pendentes), [])
        self.assertEqual(list(nos["hobby/violao"].ambiguos),
                         [{"ref": "rotina", "candidatos": ["casa/rotina", "estudo/rotina"]}])

    def test_filho_nao_vira_aresta_e_relacao_nomeada_passa(self):
        arestas = self.adaptador().arestas()
        self.assertTrue(all(isinstance(a, tuple) and len(a) == 3 for a in arestas))
        self.assertNotIn("filho", {a[2] for a in arestas})
        self.assertIn(("casa/horta/tomate", "casa/rotina", "uses"), arestas)
        self.assertIn(("casa/horta/tomate", "casa/rotina", "link"), arestas)
        self.assertIn(("hobby/violao", "estudo/rotina", "detalha"), arestas)

    def test_gerador_aceita_o_adaptador_e_a_saude_bate(self):
        a = self.adaptador()
        dados = GeradorDeMapa(a.nos(), a.arestas(), {}, ConfigDoMapa(titulo="T")).dados()
        self.assertEqual(dados["saude"]["fatos"], 5)
        self.assertEqual(dados["saude"]["pendentes"], 1)
        self.assertEqual(dados["saude"]["ambiguos"], 1)
        self.assertEqual([x["nome"] for x in dados["areas"]], ["casa", "estudo", "hobby"])


class TesteComandoNaCli(ComAcervo):
    def test_mapa_gera_index_e_dados_do_acervo_real(self):
        with tempfile.TemporaryDirectory() as tmp:
            codigo, _, erro = self.cli("mapa", "--saida", tmp)
            self.assertEqual((codigo, erro), (0, ""))
            dados = json.loads((Path(tmp) / "data.json").read_text(encoding="utf-8"))
            self.assertTrue((Path(tmp) / "index.html").is_file())
        self.assertEqual(dados["lentes"], {"dia": ["casa", "estudo"]})
        self.assertEqual(len(dados["nos"]), 5)
        self.assertEqual(dados["titulo"], "Memória")
        self.assertEqual(dados["raiz"], str(self.raiz))

    def test_saida_padrao_fica_dentro_da_raiz_e_titulo_e_opcao(self):
        codigo, _, _ = self.cli("mapa", "--titulo", "Meu acervo")
        self.assertEqual(codigo, 0)
        dados = json.loads((self.raiz / ".memoro" / "mapa" / "data.json").read_text(encoding="utf-8"))
        self.assertEqual(dados["titulo"], "Meu acervo")

    def test_lente_torta_nao_derruba_o_mapa(self):
        (self.raiz / "lentes.json").write_text(json.dumps({"boa": ["casa"], "numero": 7, "sem-pasta": ["nao-existe"]}),
                                               encoding="utf-8")
        codigo, _, erro = self.cli("mapa")
        self.assertEqual((codigo, erro), (0, ""))
        dados = json.loads((self.raiz / ".memoro" / "mapa" / "data.json").read_text(encoding="utf-8"))
        self.assertEqual(dados["lentes"], {"boa": ["casa"], "sem-pasta": ["nao-existe"]})

    def test_pasta_de_saida_dentro_da_raiz_nao_vira_fato(self):
        self.cli("mapa")
        self.assertEqual(len(RepositorioDeFatos(self.raiz).todos()), 5)


class TesteConteudoHostil(ComAcervo):
    def setUp(self):
        super().setUp()
        self.escrever("hobby", "hostil-a", desc=HOSTIL_A)
        self.escrever("hobby", "hostil-b", desc=HOSTIL_B)
        (self.raiz / "lentes.json").write_text(json.dumps({HOSTIL_B: ["hobby"]}), encoding="utf-8")
        a = self.adaptador()
        self.gerador = GeradorDeMapa(a.nos(), a.arestas(), {HOSTIL_B: ["hobby"]}, ConfigDoMapa(titulo=HOSTIL_A))

    def test_data_json_continua_json_e_guarda_o_texto_literal(self):
        dados = json.loads(self.gerador.json())
        descricoes = {no["id"]: no["descricao"] for no in dados["nos"]}
        self.assertEqual(descricoes["hobby/hostil-a"], HOSTIL_A)
        self.assertEqual(descricoes["hobby/hostil-b"], HOSTIL_B)
        self.assertIn(HOSTIL_B, dados["lentes"])

    def test_html_nao_ganha_tag_nem_fecha_o_script(self):
        html = self.gerador.html()
        self.assertNotIn("<script>alert", html)
        self.assertNotIn("<img", html)
        blocos = re.findall(r"<script[^>]*>(.*?)</script>", html, re.S)
        embutido = [b for b in blocos if "hostil-a" in b]
        self.assertEqual(len(embutido), 1, "o dado hostil tem de morar inteiro num único bloco de script")

    def test_dado_embutido_no_html_desserializa_igual_ao_data_json(self):
        html = self.gerador.html()
        achado = re.search(r'<script id="dados" type="application/json">(.*?)</script>', html, re.S)
        self.assertIsNotNone(achado, 'o dado embutido mora em <script id="dados" type="application/json">')
        self.assertEqual(json.loads(achado.group(1)), json.loads(self.gerador.json()))

    def test_template_nao_usa_sumidouro_de_html(self):
        molde = (Path(__file__).resolve().parent.parent / "memoro" / "mapa.html").read_text(encoding="utf-8")
        for sumidouro in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
            self.assertNotIn(sumidouro, molde, sumidouro)
