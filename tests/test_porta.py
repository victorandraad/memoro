from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone

from memoro.porta import PortaDeEscrita, Recusa
from memoro.repositorio import RepositorioDeFatos
from tests.apoio import ComRaiz


class Relogio:
    def __init__(self):
        self.agora = datetime(2030, 1, 10, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.agora


class ComPorta(ComRaiz):
    def setUp(self):
        super().setUp()
        self.repo = RepositorioDeFatos(self.raiz)
        self.repo.inicializar()
        self.relogio = Relogio()
        self.porta = PortaDeEscrita.padrao(self.raiz, usuario="teste", relogio=self.relogio)

    def eventos(self):
        return self.porta.diario.ler()


class TestAdd(ComPorta):
    def test_add_grava_registra_e_devolve_o_caminho(self):
        r = self.porta.add("casa", "fogao", "quatro bocas", "acende com fósforo\n", uses=(), scope=("hobby",))
        self.assertEqual(str(r.id), "casa/fogao")
        self.assertEqual(r.caminho, self.raiz / "areas/casa/fogao.md")
        self.assertEqual(r.avisos, ())
        self.assertEqual(self.repo.achar("casa/fogao").scope, ("hobby",))
        e = self.eventos()[-1]
        self.assertEqual((e.op, e.id, e.area, e.ok, e.usuario, e.ts), (
            "add", "casa/fogao", "casa", True, "teste", "2030-01-10T12:00:00+00:00"))
        self.assertEqual(e.hash_do_conteudo, hashlib.sha256(r.caminho.read_bytes()).hexdigest())

    def test_subarea_nasce_pela_porta(self):
        self.porta.add("casa/cozinha", "forno", "a gás", "x\n")
        self.assertTrue((self.raiz / "areas/casa/cozinha/forno.md").is_file())

    def test_recusas_vao_pro_diario_e_nada_e_gravado(self):
        segredo = "gh" + "p_" + "a1B2" * 9
        casos = [
            (("porao", "x", "d", "c"), "área"),
            (("casa", "x", "d", "token %s" % segredo), "segredo"),
            (("casa", "x", "d", "c", ("inventada:y",)), "relação"),
            (("casa/cozinha/gaveta", "x", "d", "c"), ""),
        ]
        for args, trecho in casos:
            antes = len(self.eventos())
            with self.assertRaises(Recusa) as ctx:
                self.porta.add(*args)
            self.assertIn(trecho, str(ctx.exception).lower())
            e = self.eventos()
            self.assertEqual(len(e), antes + 1)
            self.assertEqual((e[-1].ok, e[-1].op, e[-1].hash_do_conteudo), (False, "add", ""))
            self.assertEqual(e[-1].motivo, str(ctx.exception))
            self.assertNotIn(segredo, e[-1].motivo)
        self.assertFalse((self.raiz / "areas/porao").exists())
        self.assertFalse((self.raiz / "areas/casa/x.md").exists())

    def test_mesmo_nome_recusa_na_mesma_area_e_aceita_em_outra(self):
        self.porta.add("casa", "rotina", "a de casa", "c\n")
        with self.assertRaises(Recusa):
            self.porta.add("casa", "rotina", "de novo", "c\n")
        self.porta.add("trabalho", "rotina", "a do trabalho", "c\n")
        self.assertEqual(self.repo.achar("casa/rotina").descricao, "a de casa")
        self.assertEqual(self.repo.achar("trabalho/rotina").descricao, "a do trabalho")

    def test_travessia_de_caminho_e_recusada_e_nada_nasce_fora(self):
        fora = self.raiz.parent
        antes = sorted(p.name for p in fora.iterdir())
        for area, nome in [("../fora", "x"), ("casa", "../../x"), ("casa/..", "x"), ("/tmp", "x"),
                           ("_lixeira", "x"), ("casa", "..")]:
            with self.assertRaises(Recusa, msg=repr((area, nome))):
                self.porta.add(area, nome, "d", "c")
        self.assertEqual(sorted(p.name for p in fora.iterdir()), antes)
        self.assertEqual([p for p in (self.raiz / "areas").rglob("x.md")], [])
        self.assertFalse(self.eventos()[-1].ok)


class TestUpdate(ComPorta):
    def setUp(self):
        super().setUp()
        self.porta.add("casa", "fogao", "quatro bocas", "acende com fósforo\n", uses=(), scope=("hobby",))

    def test_muda_so_o_que_foi_passado(self):
        self.porta.update("casa/fogao", descricao="cinco bocas")
        f = self.repo.achar("casa/fogao")
        self.assertEqual((f.descricao, f.corpo, f.scope), ("cinco bocas", "acende com fósforo\n", ("hobby",)))
        self.porta.update("fogao", corpo="novo corpo\n", scope=())
        f = self.repo.achar("casa/fogao")
        self.assertEqual((f.descricao, f.corpo, f.scope), ("cinco bocas", "novo corpo\n", ()))
        self.assertEqual([e.op for e in self.eventos()][-2:], ["update", "update"])

    def test_anexo_apensa_sem_reescrever(self):
        self.porta.update("casa/fogao", anexo="trocar a mangueira em 2031\n")
        self.assertEqual(self.repo.achar("casa/fogao").corpo,
                         "acende com fósforo\n\ntrocar a mangueira em 2031\n")

    def test_update_recusado_mantem_o_arquivo_intacto(self):
        antes = (self.raiz / "areas/casa/fogao.md").read_bytes()
        with self.assertRaises(Recusa):
            self.porta.update("casa/fogao", corpo="chave " + "AK" + "IA" + "ABCDEFGHIJKLMNOP")
        with self.assertRaises(Recusa):
            self.porta.update("casa/nao-existe", descricao="x")
        with self.assertRaises(Recusa):
            self.porta.update("../../etc/passwd", descricao="x")
        self.assertEqual((self.raiz / "areas/casa/fogao.md").read_bytes(), antes)
        self.assertEqual([e.ok for e in self.eventos()][-3:], [False, False, False])

    def test_nome_solto_ambiguo_e_recusado_com_as_candidatas(self):
        self.porta.add("trabalho", "fogao", "o da copa", "c\n")
        with self.assertRaises(Recusa) as ctx:
            self.porta.update("fogao", descricao="x")
        self.assertIn("casa/fogao", str(ctx.exception))
        self.assertIn("trabalho/fogao", str(ctx.exception))


class TestRmEPurga(ComPorta):
    def setUp(self):
        super().setUp()
        self.porta.add("casa", "rotina", "a de casa", "corpo de casa\n")
        self.porta.add("trabalho", "rotina", "a do trabalho", "corpo do trabalho\n")

    def test_rm_sem_motivo_recusa_e_nao_toca_no_arquivo(self):
        with self.assertRaises(Recusa):
            self.porta.rm("casa/rotina", "")
        self.assertTrue((self.raiz / "areas/casa/rotina.md").is_file())
        self.assertFalse(self.eventos()[-1].ok)

    def test_rm_move_pra_lixeira_com_motivo_e_data(self):
        r = self.porta.rm("casa/rotina", "virou hábito")
        self.assertFalse((self.raiz / "areas/casa/rotina.md").exists())
        self.assertEqual(r.caminho, self.raiz / "areas/_lixeira/casa/rotina.md")
        texto = r.caminho.read_text(encoding="utf-8")
        for trecho in ("motivo: virou hábito", "removido_por: teste", "removido_em: 2030-01-10", "corpo de casa"):
            self.assertIn(trecho, texto)
        self.assertEqual([str(f.id) for f in self.repo.todos() if f.nome == "rotina"], ["trabalho/rotina"])
        self.assertEqual((self.eventos()[-1].op, self.eventos()[-1].motivo), ("rm", "virou hábito"))

    def test_lixeira_nunca_sobrescreve(self):
        """Homônimo removido duas vezes da mesma área: o segundo não pode apagar o primeiro."""
        self.porta.rm("casa/rotina", "primeira")
        self.porta.add("casa", "rotina", "de novo", "segundo corpo\n")
        r2 = self.porta.rm("casa/rotina", "segunda")
        arquivos = sorted((self.raiz / "areas/_lixeira/casa").iterdir())
        self.assertEqual(len(arquivos), 2)
        self.assertIn(r2.caminho, arquivos)
        textos = "".join(a.read_text(encoding="utf-8") for a in arquivos)
        self.assertIn("corpo de casa", textos)
        self.assertIn("segundo corpo", textos)

    def test_purga_so_leva_o_que_passou_do_prazo(self):
        self.porta.rm("casa/rotina", "velho")
        self.relogio.agora += timedelta(days=40)
        self.porta.rm("trabalho/rotina", "novo")
        removidos = self.porta.purga(30)
        self.assertEqual([p.name for p in removidos], ["rotina.md"])
        self.assertFalse((self.raiz / "areas/_lixeira/casa/rotina.md").exists())
        self.assertTrue((self.raiz / "areas/_lixeira/trabalho/rotina.md").exists())
        self.assertEqual(self.eventos()[-1].op, "purga")


class TestGit(ComPorta):
    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.raiz)] + list(args), capture_output=True, text=True).stdout

    def test_sem_git_nao_commita_e_nao_reclama(self):
        r = self.porta.add("casa", "fogao", "d", "c\n")
        self.assertEqual(r.avisos, ())
        self.assertFalse((self.raiz / ".git").exists())

    def test_com_git_cada_escrita_e_um_commit_neutro_so_do_que_tocou(self):
        self.git("init", "-q")
        self.git("config", "user.email", "teste@example.test")
        self.git("config", "user.name", "teste")
        (self.raiz / "rascunho.txt").write_text("alheio", encoding="utf-8")
        self.porta.add("casa", "fogao", "d", "c\n")
        self.porta.update("casa/fogao", descricao="d2")
        self.porta.rm("casa/fogao", "teste")
        log = self.git("log", "--format=%s").splitlines()
        self.assertEqual(log, ["memoro rm casa/fogao", "memoro update casa/fogao", "memoro add casa/fogao"])
        self.assertEqual(self.git("log", "-1", "--format=%an"), "teste\n")  # identidade é a do repo, nunca fixa
        self.assertIn("?? rascunho.txt", self.git("status", "--porcelain"))
        self.assertNotIn("fogao", self.git("status", "--porcelain"))

    def iniciar_git(self):
        self.git("init", "-q")
        self.git("config", "user.email", "teste@example.test")
        self.git("config", "user.name", "teste")

    def test_fato_e_evento_saem_no_mesmo_commit(self):
        self.iniciar_git()
        self.porta.add("casa", "fogao", "d", "c\n")
        self.porta.update("casa/fogao", descricao="d2")
        self.porta.rm("casa/fogao", "teste")
        self.relogio.agora += timedelta(days=40)
        self.porta.purga(30)
        for rev, op in (("HEAD~3", "add"), ("HEAD~2", "update"), ("HEAD~1", "rm"), ("HEAD", "purga")):
            self.assertIn("eventos.jsonl", self.git("show", "--name-only", "--format=", rev).split(), rev)
            ultimo = json.loads(self.git("show", rev + ":eventos.jsonl").splitlines()[-1])
            self.assertEqual((ultimo["op"], ultimo["id"], ultimo["ok"]), (op, "casa/fogao", True))
        self.assertNotIn("eventos.jsonl", self.git("status", "--porcelain"))

    def test_adocao_leva_o_diario_no_commit_e_cita_cada_id(self):
        self.iniciar_git()
        for nome in ("pia", "forno"):
            self.escrever("casa", nome, desc="adotado " + nome)
        adotados, _ = self.porta.adotar_varios(["casa/pia", "casa/forno"], "estado inicial")
        self.assertEqual(len(adotados), 2)
        self.assertIn("eventos.jsonl", self.git("show", "--name-only", "--format=", "HEAD").split())
        corpo = self.git("log", "-1", "--format=%B").splitlines()
        self.assertIn("memoro adocao casa/pia", corpo)
        self.assertIn("memoro adocao casa/forno", corpo)

    def test_commit_que_falha_deixa_evento_ok_e_aviso(self):
        # escolha: o evento já foi gravado e descreve o disco; o doutor (D7) acusa o commit que faltou
        self.iniciar_git()
        gancho = self.raiz / ".git" / "hooks" / "pre-commit"
        gancho.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        gancho.chmod(0o755)
        r = self.porta.add("casa", "fogao", "d", "c\n")
        self.assertTrue(any("sem commit" in a for a in r.avisos))
        self.assertEqual([(e.op, e.id, e.ok) for e in self.eventos()][-1], ("add", "casa/fogao", True))

    def test_raiz_dentro_de_outro_repo_nao_commita_no_repo_de_fora(self):
        fora = self.raiz.parent
        subprocess.run(["git", "-C", str(fora), "init", "-q"], check=True)
        self.porta.add("casa", "fogao", "d", "c\n")
        vazio = subprocess.run(["git", "-C", str(fora), "log", "--oneline"], capture_output=True, text=True)
        self.assertEqual(vazio.stdout, "")
