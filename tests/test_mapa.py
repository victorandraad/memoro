from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memoro.mapa import ConfigDoMapa, GeradorDeMapa, No, Paleta  # noqa: E402

SEGREDO = "CORPO-SECRETO-9F3A"

MOLDE = Path(__file__).resolve().parent.parent / "memoro" / "mapa.html"


class NoComCorpo:
    """Duble do fato do nucleo: tem corpo, que o mapa nunca pode ler."""

    def __init__(self, id, descricao="", pendentes=(), ambiguos=()):
        partes = id.split("/")
        self.id = id
        self.nome = partes[-1]
        self.area = partes[0]
        self.subarea = partes[1] if len(partes) == 3 else None
        self.descricao = descricao
        self.caminho = id + ".md"
        self.pendentes = list(pendentes)
        self.ambiguos = list(ambiguos)
        self.corpo = SEGREDO


def cenario():
    nos = [
        NoComCorpo("casa/rotina", "rotina da casa"),
        NoComCorpo("estudo/rotina", "rotina de estudo"),
        NoComCorpo("casa/horta/tomate", "x" * 500),
        NoComCorpo("casa/compras", pendentes=["lista-que-nao-existe"]),
        NoComCorpo("estudo/plano", ambiguos=[{"ref": "rotina", "candidatos": ["estudo/rotina", "casa/rotina"]}]),
        NoComCorpo("hobby/violao"),
    ]
    arestas = [
        ("casa/horta/tomate", "casa/rotina", "uses"),
        ("estudo/plano", "estudo/rotina", "link"),
        ("casa/compras", "fantasma/sumiu", "uses"),
    ]
    lentes = {"lar": ["casa", "casa/horta"], "foco": ["estudo"]}
    return nos, arestas, lentes


def gerar(nos, arestas, lentes, config=None):
    destino = Path(tempfile.mkdtemp())
    GeradorDeMapa(nos, arestas, lentes, config or ConfigDoMapa(titulo="Teste")).gerar(destino)
    return (destino / "data.json").read_text(encoding="utf-8"), (destino / "index.html").read_text(encoding="utf-8")


class TesteDados(unittest.TestCase):
    def test_data_json_e_deterministico_independe_da_ordem_de_entrada(self):
        nos, arestas, lentes = cenario()
        a, _ = gerar(nos, arestas, lentes)
        b, _ = gerar(list(reversed(nos)), list(reversed(arestas)), dict(reversed(list(lentes.items()))))
        self.assertEqual(a, b)
        dados = json.loads(a)
        self.assertEqual([n["id"] for n in dados["nos"]], sorted(n.id for n in nos))

    def test_corpo_nunca_vaza(self):
        dados, html = gerar(*cenario())
        self.assertNotIn(SEGREDO, dados)
        self.assertNotIn(SEGREDO, html)
        self.assertEqual(
            set(json.loads(dados)["nos"][0]),
            {"id", "nome", "rotulo", "descricao", "area", "subarea", "caminho", "pendentes", "ambiguos", "orfao"},
        )

    def test_descricao_cortada_em_300(self):
        dados = json.loads(gerar(*cenario())[0])
        tomate = next(n for n in dados["nos"] if n["id"] == "casa/horta/tomate")
        self.assertEqual(len(tomate["descricao"]), 300)

    def test_homonimos_viram_dois_nos_com_rotulo_qualificado(self):
        dados = json.loads(gerar(*cenario())[0])
        rotulos = {n["id"]: n["rotulo"] for n in dados["nos"]}
        self.assertEqual(rotulos["casa/rotina"], "casa/rotina")
        self.assertEqual(rotulos["estudo/rotina"], "estudo/rotina")
        self.assertEqual(rotulos["hobby/violao"], "violao")

    def test_saude_conta_nos_afetados(self):
        saude = json.loads(gerar(*cenario())[0])["saude"]
        # orfao = sem nenhuma aresta valida: casa/compras (aresta pra no inexistente nao conta) e hobby/violao
        self.assertEqual(saude, {"fatos": 6, "areas": 3, "pendentes": 1, "ambiguos": 1, "orfaos": 2})

    def test_aresta_pra_no_inexistente_some_e_candidatas_ficam(self):
        dados = json.loads(gerar(*cenario())[0])
        self.assertEqual(
            dados["arestas"],
            [
                {"origem": "casa/horta/tomate", "destino": "casa/rotina", "tipo": "uses"},
                {"origem": "estudo/plano", "destino": "estudo/rotina", "tipo": "link"},
            ],
        )
        plano = next(n for n in dados["nos"] if n["id"] == "estudo/plano")
        self.assertEqual(plano["ambiguos"], [{"ref": "rotina", "candidatos": ["casa/rotina", "estudo/rotina"]}])

    def test_config_vai_pro_json(self):
        cfg = ConfigDoMapa(titulo="T", url_base_de_edicao="ftp://exemplo/base", esquema_do_editor="zed",
                           intervalo_de_atualizacao_s=5, raiz="/tmp/acervo")
        dados = json.loads(gerar(*cenario(), config=cfg)[0])
        self.assertEqual(
            (dados["titulo"], dados["url_base_de_edicao"], dados["esquema_do_editor"], dados["intervalo_s"], dados["raiz"]),
            ("T", "ftp://exemplo/base", "zed", 5, "/tmp/acervo"),
        )

    def test_no_concreto_serve_de_entrada(self):
        no = No(id="a/b", nome="b", descricao="", area="a", subarea=None, caminho="a/b.md")
        dados = json.loads(gerar([no], [], {})[0])
        self.assertEqual(dados["saude"]["orfaos"], 1)


class TestePaleta(unittest.TestCase):
    def distancia_minima(self, matizes):
        ordenados = sorted(matizes)
        voltas = ordenados + [ordenados[0] + 360]
        return min(b - a for a, b in zip(voltas, voltas[1:]))

    def test_estavel_e_independe_da_ordem(self):
        areas = ["casa", "estudo", "hobby"]
        self.assertEqual(Paleta(areas).matizes(), Paleta(list(reversed(areas))).matizes())
        self.assertEqual(Paleta(areas).matizes(), Paleta(areas).matizes())

    def test_distinta_pra_3_8_e_30_areas(self):
        for n, minimo in ((3, 60), (8, 20), (30, 4)):
            matizes = list(Paleta(["area-%d" % i for i in range(n)]).matizes().values())
            self.assertEqual(len(matizes), n)
            self.assertTrue(all(0 <= m < 360 for m in matizes))
            self.assertGreaterEqual(self.distancia_minima(matizes), minimo, n)

    def test_nenhuma_area_cai_em_faixa_de_matiz_reservada_a_estado(self):
        # vermelho (345 a 20 graus) é do pendente e âmbar (25 a 55) é do ambíguo: área nenhuma pode parecer estado
        grupos = [["area-%d" % i for i in range(n)] for n in (3, 8, 30)]
        grupos.append(["casa", "estudo", "hobby", "trabalho", "saude-do-servidor"])
        for areas in grupos:
            for area, matiz in Paleta(areas).matizes().items():
                self.assertTrue(70 <= matiz <= 335, "%s caiu em %d (margem de 15 graus das faixas de estado)" % (area, matiz))

    def test_matiz_da_area_vai_pro_json(self):
        dados = json.loads(gerar(*cenario())[0])
        self.assertEqual({a["nome"]: a["matiz"] for a in dados["areas"]}, Paleta(["casa", "estudo", "hobby"]).matizes())


class TesteHtml(unittest.TestCase):
    def test_offline_sem_url_externa(self):
        _, html = gerar(*cenario())
        urls = [u for u in re.findall(r"https?://[^\s\"'<>)]+", html) if not u.startswith("http://www.w3.org/")]
        self.assertEqual(urls, [])
        self.assertNotIn("fonts.googleapis", html)
        self.assertNotRegex(html, r"<script[^>]+src=")
        self.assertNotRegex(html, r"<link[^>]+href=")

    def test_sem_termo_privado(self):
        _, html = gerar(*cenario())
        for termo in ("inter" + "nal", "/ro" + "ot/", "git" + "hub", "ssh-" + "remote"):
            self.assertNotIn(termo, html.lower(), termo)

    def test_licenca_do_d3_preservada_e_tamanho(self):
        _, html = gerar(*cenario())
        self.assertIn("Mike Bostock", html)
        self.assertIn("Permission to use, copy, modify", html)
        self.assertLess(len(html.encode("utf-8")), 150_000)

    def test_dados_embutidos_pra_abrir_por_arquivo_e_titulo_escapado(self):
        nos, arestas, lentes = cenario()
        nos.append(NoComCorpo("hobby/xss", "</script><script>alert(1)</script>"))
        _, html = gerar(nos, arestas, lentes, ConfigDoMapa(titulo="<b>Meu & mapa</b>"))
        self.assertNotIn("<script>alert(1)", html)
        self.assertNotIn("<b>Meu", html)
        self.assertIn("&lt;b&gt;Meu &amp; mapa", html)
        embutido = re.search(r'<script id="dados" type="application/json">(.*?)</script>', html, re.S)
        self.assertIsNotNone(embutido)
        self.assertEqual(len(json.loads(embutido.group(1))["nos"]), 7)

    def test_requisitos_de_interface_presentes(self):
        _, html = gerar(*cenario())
        for trecho in ("prefers-color-scheme", "prefers-reduced-motion", ":focus-visible", "If-None-Match", 'id="legenda"', 'id="saude"'):
            self.assertIn(trecho, html, trecho)

    def test_estado_tem_segunda_codificacao_alem_da_cor(self):
        molde = MOLDE.read_text(encoding="utf-8")
        for trecho in ("stroke-dasharray", "referência pendente", "referência ambígua"):
            self.assertIn(trecho, molde, trecho)

    def test_rotulo_encurta_e_nome_inteiro_fica_acessivel(self):
        molde = MOLDE.read_text(encoding="utf-8")
        self.assertIn(chr(0x2026), molde, "reticências no rótulo encurtado")
        self.assertRegex(molde, r"""["']title["']""", "tooltip acessível: <title> criado por nó")

    def test_texto_de_interface_tem_acento_e_uma_familia_so(self):
        molde = MOLDE.read_text(encoding="utf-8")
        for torto in ("Circulo", "circulo", "heranca", "selecao", "orfaos<", "Orfaos", " areas<", "Georgia", "serif;"):
            self.assertNotIn(torto, molde.replace("sans-serif;", ""), torto)
        proprias = [f for f in re.findall(r"font-family\s*:\s*([^;]+);", molde) if f.strip() != "inherit" and not f.strip().startswith("var(")]
        self.assertEqual(len(proprias), 1, "uma pilha de fonte só; o resto herda")


if __name__ == "__main__":
    unittest.main()
