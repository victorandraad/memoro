"""memoro doutor: a porta única conferida contra o diário, sem depender de usuário unix dedicado."""
from __future__ import annotations

import json
import subprocess

from memoro.diario import DiarioDeEventos
from memoro.doutor import Doutor
from tests.apoio import ComRaiz, em_portugues

setUpModule = em_portugues


class ComPorta(ComRaiz):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.cli("init")[0], 0)
        for area in ("casa", "estudo", "hobby"):
            (self.raiz / "areas" / area).mkdir(parents=True, exist_ok=True)
        self.adotar_tudo_inicial()
        self.add("casa", "rotina", "rotina semanal da casa")
        self.add("estudo", "leituras", "fila de livros do semestre")

    def adotar_tudo_inicial(self):
        # o init pode semear exemplos por fora do diário: regulariza pra partir de um acervo limpo
        self.cli("adotar-tudo", "--motivo", "estado inicial do teste")

    def add(self, area, nome, desc, corpo="corpo do fato\n", *extra):
        codigo, _, erro = self.cli("add", area, nome, "--desc", desc, *extra, entrada=corpo)
        self.assertEqual(codigo, 0, erro)

    def arquivo(self, ident):
        return self.raiz / "areas" / (ident + ".md")

    def tipos(self):
        return sorted((a.tipo, a.id) for a in Doutor(self.raiz).examinar())

    def eventos(self):
        return DiarioDeEventos(self.raiz / "eventos.jsonl").ler()


class TesteInit(ComRaiz):
    def test_init_deixa_o_doutor_limpo(self):
        self.assertEqual(self.cli("init")[0], 0)
        self.assertEqual([(a.tipo, a.id) for a in Doutor(self.raiz).examinar()], [])
        self.assertEqual(self.cli("init")[0], 0, "init de novo não duplica nem suja")
        self.assertEqual([(a.tipo, a.id) for a in Doutor(self.raiz).examinar()], [])


class TesteExame(ComPorta):
    def test_acervo_so_escrito_pela_porta_sai_limpo(self):
        self.assertEqual(self.tipos(), [])
        codigo, saida, _ = self.cli("doutor")
        self.assertEqual(codigo, 0)
        self.assertIn("limpo", saida)

    def test_update_e_rm_pela_porta_continuam_limpos(self):
        self.cli("update", "casa/rotina", "--desc", "rotina quinzenal da casa")
        self.cli("rm", "estudo/leituras", "--motivo", "fila zerada")
        self.assertEqual(self.tipos(), [])

    def test_arquivo_alterado_fora_da_porta(self):
        with self.arquivo("casa/rotina").open("a", encoding="utf-8") as f:
            f.write("linha posta no editor\n")
        self.assertEqual(self.tipos(), [("alterado-fora-da-porta", "casa/rotina")])
        self.assertEqual(self.cli("doutor")[0], 1)

    def test_arquivo_sem_evento_de_criacao(self):
        self.escrever("hobby", "xadrez", desc="três aberturas")
        self.assertEqual(self.tipos(), [("sem-evento", "hobby/xadrez")])

    def test_arquivo_recriado_a_mao_depois_do_rm_conta_como_sem_evento(self):
        self.cli("rm", "estudo/leituras", "--motivo", "fila zerada")
        self.escrever("estudo", "leituras", desc="voltou por fora")
        self.assertEqual(self.tipos(), [("sem-evento", "estudo/leituras")])

    def test_evento_sem_arquivo(self):
        self.arquivo("estudo/leituras").unlink()
        self.assertEqual(self.tipos(), [("evento-sem-arquivo", "estudo/leituras")])

    def test_recusa_no_diario_nao_conta_como_evento_de_criacao(self):
        codigo, _, _ = self.cli("add", "nao-existe", "fato", "--desc", "área que não existe", entrada="x\n")
        self.assertEqual(codigo, 1)
        self.assertEqual(self.tipos(), [])

    def test_frontmatter_invalido(self):
        pasta = self.raiz / "areas" / "hobby"
        (pasta / "sem-bloco.md").write_text("só texto, sem frontmatter\n", encoding="utf-8")
        (pasta / "nome-torto.md").write_text("---\nname: outro-nome\ndescription: d\narea: hobby\n---\n\nc\n", encoding="utf-8")
        (pasta / "area-torta.md").write_text("---\nname: area-torta\ndescription: d\narea: casa\n---\n\nc\n", encoding="utf-8")
        (pasta / "Nome Com Espaco.md").write_text("---\nname: x\ndescription: d\narea: hobby\n---\n\nc\n", encoding="utf-8")
        invalidos = sorted(i for t, i in self.tipos() if t == "frontmatter-invalido")
        self.assertEqual(invalidos, ["hobby/Nome Com Espaco", "hobby/area-torta", "hobby/nome-torto", "hobby/sem-bloco"])

    def test_referencias_pendentes_e_ambiguas(self):
        self.add("estudo", "rotina", "blocos de cinquenta minutos", "corpo\n", "--novo-mesmo-assim")
        self.add("hobby", "violao", "dedilhado diário", "aquece com [[rotina]] e [[sumiu]]\n")
        self.assertEqual(self.tipos(), [("ambiguo", "hobby/violao"), ("pendente", "hobby/violao")])

    def test_diario_corrompido(self):
        with (self.raiz / "eventos.jsonl").open("a", encoding="utf-8") as f:
            f.write("isto nao e json\n")
            f.write('{"json": "mas sem os campos"}\n')
        achados = [a for a in Doutor(self.raiz).examinar() if a.tipo == "diario-corrompido"]
        self.assertEqual(len(achados), 2)
        self.assertTrue(all("linha" in a.detalhe for a in achados))

    def test_linha_com_campo_de_tipo_errado_conta_como_corrompida(self):
        bom = json.loads((self.raiz / "eventos.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        with (self.raiz / "eventos.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(dict(bom, ok="sim")) + "\n")
            f.write(json.dumps(dict(bom, hash_do_conteudo=None)) + "\n")
            f.write(json.dumps(dict(bom, id=["casa/rotina"])) + "\n")
        achados = [a for a in Doutor(self.raiz).examinar() if a.tipo == "diario-corrompido"]
        self.assertEqual(len(achados), 3)

    def test_lixeira_e_pastas_ocultas_ficam_fora(self):
        self.cli("rm", "estudo/leituras", "--motivo", "fila zerada")
        (self.raiz / "areas" / ".obsidian").mkdir()
        (self.raiz / "areas" / ".obsidian" / "nota.md").write_text("x\n", encoding="utf-8")
        self.assertEqual(self.tipos(), [])

    def test_json(self):
        self.arquivo("estudo/leituras").unlink()
        codigo, saida, _ = self.cli("doutor", "--json")
        dados = json.loads(saida)
        self.assertEqual(codigo, 1)
        self.assertEqual(dados["limpo"], False)
        self.assertEqual([(a["tipo"], a["id"]) for a in dados["achados"]], [("evento-sem-arquivo", "estudo/leituras")])
        self.assertTrue(dados["achados"][0]["detalhe"])


class TesteGitContraDiario(ComRaiz):
    """D7: todo evento de escrita ok tem o commit `memoro <op> <id>` e vice-versa."""

    def setUp(self):
        super().setUp()
        self.assertEqual(self.cli("init")[0], 0)
        self.git("init", "-q")
        self.git("config", "user.email", "teste@example.test")
        self.git("config", "user.name", "teste")
        (self.raiz / "areas" / "estudo").mkdir(parents=True, exist_ok=True)
        self.cli("adotar-tudo", "--motivo", "estado inicial do teste")
        for area, nome, desc in (("casa", "rotina", "rotina semanal da casa"), ("estudo", "leituras", "fila de livros")):
            self.assertEqual(self.cli("add", area, nome, "--desc", desc, entrada="corpo\n")[0], 0)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.raiz)] + list(args), capture_output=True, text=True, check=True).stdout

    def tipos(self):
        return sorted((a.tipo, a.id) for a in Doutor(self.raiz).examinar())

    def test_escritas_pela_porta_batem_com_o_git(self):
        self.cli("update", "casa/rotina", "--desc", "rotina quinzenal da casa")
        self.cli("rm", "estudo/leituras", "--motivo", "fila zerada")
        self.escrever("casa", "pia", desc="pia da cozinha")
        self.escrever("casa", "forno", desc="forno a gás")
        self.assertEqual(self.cli("adotar-tudo", "--motivo", "lote")[0], 0)
        self.assertEqual(self.tipos(), [])

    def test_commit_forjado_sem_evento(self):
        self.git("commit", "-q", "--allow-empty", "-m", "memoro add casa/fantasma")
        self.assertEqual(self.tipos(), [("commit-sem-evento", "casa/fantasma")])
        self.assertEqual(self.cli("doutor")[0], 1)

    def test_commit_apagado_deixa_evento_sem_commit(self):
        self.git("reset", "-q", "--soft", "HEAD~1")
        self.git("commit", "-q", "-m", "outra coisa")
        self.assertEqual(self.tipos(), [("evento-sem-commit", "estudo/leituras")])
        self.assertEqual(self.cli("doutor")[0], 1)

    def test_commit_que_falhou_na_porta_aparece_como_evento_sem_commit(self):
        gancho = self.raiz / ".git" / "hooks" / "pre-commit"
        gancho.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        gancho.chmod(0o755)
        self.cli("add", "casa", "fogao", "--desc", "fogão de quatro bocas", entrada="corpo\n")
        self.assertEqual(self.tipos(), [("evento-sem-commit", "casa/fogao")])


class TesteAdocao(ComPorta):
    def test_adotar_regulariza_edicao_a_mao_e_registra_o_motivo(self):
        with self.arquivo("casa/rotina").open("a", encoding="utf-8") as f:
            f.write("linha posta no editor\n")
        codigo, _, erro = self.cli("doutor", "--adotar", "casa/rotina", "--motivo", "editei no editor")
        self.assertEqual(codigo, 0, erro)
        ultimo = self.eventos()[-1]
        self.assertEqual((ultimo.op, ultimo.id, ultimo.ok, ultimo.motivo), ("adocao", "casa/rotina", True, "editei no editor"))
        self.assertEqual(self.tipos(), [])

    def test_adotar_sem_motivo_e_recusado(self):
        self.escrever("hobby", "xadrez", desc="três aberturas")
        codigo, _, erro = self.cli("doutor", "--adotar", "hobby/xadrez")
        self.assertEqual(codigo, 1)
        self.assertIn("motivo", erro)
        self.assertEqual(self.tipos(), [("sem-evento", "hobby/xadrez")])

    def test_adotar_passa_pelas_regras_da_porta(self):
        segredo = "sk-" + "a1B2c3D4" * 4
        self.escrever("hobby", "chave", desc="guarda a chave", corpo="token: %s\n" % segredo)
        codigo, _, erro = self.cli("doutor", "--adotar", "hobby/chave", "--motivo", "importei")
        self.assertEqual(codigo, 1, erro)
        recusa = self.eventos()[-1]
        self.assertEqual((recusa.op, recusa.ok), ("adocao", False))
        self.assertNotIn(segredo, json.dumps(recusa.__dict__))
        self.assertTrue(self.arquivo("hobby/chave").is_file(), "o que não passa é listado, nunca apagado")

    def test_adotar_tudo_importa_pasta_existente_e_lista_o_que_nao_passa(self):
        segredo = "sk-" + "a1B2c3D4" * 4
        self.escrever("hobby", "xadrez", desc="três aberturas")
        self.escrever("hobby/violao", "afinacao", desc="afinação padrão e duas abertas")
        self.escrever("hobby", "chave", desc="guarda a chave", corpo="token: %s\n" % segredo)
        (self.raiz / "areas" / "hobby" / "sem-bloco.md").write_text("só texto\n", encoding="utf-8")
        codigo, saida, erro = self.cli("adotar-tudo", "--motivo", "pasta que já existia")
        self.assertEqual(codigo, 1)
        self.assertIn("2 adotados", saida)
        self.assertIn("hobby/chave", erro)
        self.assertIn("hobby/sem-bloco", erro)
        self.assertTrue(self.arquivo("hobby/chave").is_file())
        self.assertEqual(self.tipos(), [("frontmatter-invalido", "hobby/sem-bloco"), ("sem-evento", "hobby/chave")])

    def test_adotar_tudo_nao_mexe_no_que_ja_bate(self):
        antes = len(self.eventos())
        codigo, saida, _ = self.cli("adotar-tudo", "--motivo", "de novo")
        self.assertEqual(codigo, 0)
        self.assertIn("0 adotados", saida)
        self.assertEqual(len(self.eventos()), antes)

    def test_adotar_tudo_le_o_acervo_uma_vez_e_nao_uma_vez_por_fato(self):
        # medido: 1.000 fatos levavam 134 s porque cada adoção relia o acervo inteiro (quadrático)
        from unittest import mock
        from memoro.repositorio import RepositorioDeFatos
        for i in range(30):
            self.escrever("hobby", "item-%02d" % i, desc="descrição única número %d zq%d" % (i, i * 7919))
        original = RepositorioDeFatos.todos
        with mock.patch.object(RepositorioDeFatos, "todos", autospec=True, side_effect=original) as todos:
            codigo, saida, erro = self.cli("adotar-tudo", "--motivo", "lote")
        self.assertEqual(codigo, 0, erro)
        self.assertIn("30 adotados", saida)
        self.assertLessEqual(todos.call_count, 4)
        self.assertEqual(self.tipos(), [])
        self.assertEqual(len([e for e in self.eventos() if e.op == "adocao" and e.motivo == "lote"]), 30)

    def test_adotar_tudo_monta_o_grafo_uma_vez_pro_lote(self):
        # perfil medido: 300 adoções = 301 grafos montados; o retrato do lote é um só, o grafo também
        from unittest import mock
        from memoro import grafo as modulo
        for i in range(30):
            self.escrever("hobby", "peca-%02d" % i, desc="descrição única número %d zq%d" % (i, i * 7919),
                          corpo="veja [[casa/rotina]] e [[sumiu-%d]]\n" % i)
        original = modulo.GrafoDeFatos._montar
        with mock.patch.object(modulo.GrafoDeFatos, "_montar", autospec=True, side_effect=original) as montar:
            codigo, saida, erro = self.cli("adotar-tudo", "--motivo", "lote")
        self.assertEqual(codigo, 0, erro)
        self.assertIn("30 adotados", saida)
        self.assertLessEqual(montar.call_count, 4)

    def test_adotar_tudo_exige_motivo(self):
        self.assertNotEqual(self.cli("adotar-tudo")[0], 0)
