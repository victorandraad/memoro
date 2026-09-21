from __future__ import annotations

from memoro.dominio import Fato, IdDeFato
from memoro.repositorio import FatoNaoEncontrado, ReferenciaAmbigua, RepositorioDeFatos
from tests.apoio import ComRaiz


class TestRepositorio(ComRaiz):
    def setUp(self):
        super().setUp()
        self.repo = RepositorioDeFatos(self.raiz)

    def test_raiz_vazia_nao_tem_fato(self):
        self.assertEqual(self.repo.todos(), [])
        self.assertEqual(self.repo.areas(), [])

    def test_carrega_ordenado_por_id_e_ignora_lixeira(self):
        self.escrever("trabalho", "rotina")
        self.escrever("casa/cozinha", "forno", desc="forno a gás", uses=["fogao"])
        self.escrever("casa", "fogao")
        self.escrever("_lixeira/casa", "velho")
        ids = [str(f.id) for f in self.repo.todos()]
        self.assertEqual(ids, ["casa/cozinha/forno", "casa/fogao", "trabalho/rotina"])
        forno = self.repo.todos()[0]
        self.assertEqual((forno.descricao, forno.uses, forno.corpo), ("forno a gás", ("fogao",), "corpo\n"))
        self.assertEqual(self.repo.areas(), ["casa", "casa/cozinha", "trabalho"])

    def test_a_pasta_manda_no_id(self):
        """area: no frontmatter divergente da pasta nao muda onde o fato mora."""
        c = self.escrever("casa", "fogao")
        c.write_text(c.read_text(encoding="utf-8").replace("area: casa", "area: trabalho"), encoding="utf-8")
        self.assertEqual([str(f.id) for f in self.repo.todos()], ["casa/fogao"])

    def test_arquivo_de_nome_invalido_e_pulado_sem_derrubar(self):
        self.escrever("casa", "fogao")
        (self.raiz / "areas" / "casa" / "Nome Ruim.md").write_text("x", encoding="utf-8")
        self.assertEqual([str(f.id) for f in self.repo.todos()], ["casa/fogao"])

    def test_achar_por_id_qualificado_e_por_nome_unico(self):
        self.escrever("casa", "fogao")
        self.assertEqual(self.repo.achar("casa/fogao").nome, "fogao")
        self.assertEqual(str(self.repo.achar("fogao").id), "casa/fogao")

    def test_homonimo_em_duas_areas_continua_enderecavel(self):
        self.escrever("casa", "rotina", desc="a de casa")
        self.escrever("trabalho", "rotina", desc="a do trabalho")
        self.assertEqual(self.repo.achar("casa/rotina").descricao, "a de casa")
        self.assertEqual(self.repo.achar("trabalho/rotina").descricao, "a do trabalho")
        with self.assertRaises(ReferenciaAmbigua) as ctx:
            self.repo.achar("rotina")
        self.assertEqual([str(i) for i in ctx.exception.candidatas], ["casa/rotina", "trabalho/rotina"])

    def test_achar_o_que_nao_existe(self):
        self.escrever("casa", "fogao")
        with self.assertRaises(FatoNaoEncontrado) as ctx:
            self.repo.achar("fogoa")
        self.assertIn("casa/fogao", str(ctx.exception))  # sugere o parecido
        with self.assertRaises(FatoNaoEncontrado):
            self.repo.achar("../../etc/passwd")

    def test_gravar_cria_a_pasta_e_le_de_volta(self):
        fato = Fato(IdDeFato("estudo/idiomas", "verbos"), "verbos irregulares", "lista\n", scope=("estudo",))
        caminho = self.repo.gravar(fato)
        self.assertEqual(caminho, self.raiz / "areas/estudo/idiomas/verbos.md")
        self.assertEqual(self.repo.achar("estudo/idiomas/verbos"), fato)

    def test_gravar_e_atomico_e_nao_deixa_temporario(self):
        self.repo.gravar(Fato(IdDeFato("casa", "x"), "d", "c\n"))
        self.repo.gravar(Fato(IdDeFato("casa", "x"), "d2", "c2\n"))
        self.assertEqual(sorted(p.name for p in (self.raiz / "areas/casa").iterdir()), ["x.md"])
        self.assertEqual(self.repo.achar("casa/x").descricao, "d2")

    def test_inicializar_cria_estrutura_e_e_idempotente(self):
        self.repo.inicializar()
        self.assertTrue((self.raiz / "areas/_lixeira").is_dir())
        self.assertTrue((self.raiz / "lentes.json").is_file())
        self.assertEqual(len([a for a in self.repo.areas() if "/" not in a]), 2)
        (self.raiz / "lentes.json").write_text("{}", encoding="utf-8")
        self.repo.inicializar()
        self.assertEqual((self.raiz / "lentes.json").read_text(encoding="utf-8"), "{}")
