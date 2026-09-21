from __future__ import annotations

import json

from memoro.diario import DiarioDeEventos
from memoro.dominio import Evento
from tests.apoio import ComRaiz


def evento(**kw):
    base = dict(ts="2030-01-02T03:04:05+00:00", usuario="teste", op="add", id="casa/fogao", area="casa",
                resumo="+3 linhas", ok=True, motivo="", hash_do_conteudo="ab" * 32)
    base.update(kw)
    return Evento(**base)


class TestDiario(ComRaiz):
    def setUp(self):
        super().setUp()
        self.caminho = self.raiz / "eventos.jsonl"
        self.diario = DiarioDeEventos(self.caminho)

    def test_sem_arquivo_le_vazio(self):
        self.assertEqual(self.diario.ler(), [])

    def test_uma_linha_json_por_evento_com_os_campos_do_contrato(self):
        self.diario.registrar(evento())
        self.diario.registrar(evento(op="rm", ok=False, motivo="rm exige motivo", hash_do_conteudo=""))
        linhas = self.caminho.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(linhas), 2)
        self.assertEqual(sorted(json.loads(linhas[0])), sorted(
            ["ts", "usuario", "op", "id", "area", "resumo", "ok", "motivo", "hash_do_conteudo"]))
        self.assertEqual(self.diario.ler()[1], evento(op="rm", ok=False, motivo="rm exige motivo", hash_do_conteudo=""))

    def test_filtros(self):
        self.diario.registrar(evento(ts="2030-01-01T00:00:00+00:00", id="casa/a", usuario="ana"))
        self.diario.registrar(evento(ts="2030-02-01T00:00:00+00:00", id="casa/b", ok=False, motivo="x"))
        self.assertEqual([e.id for e in self.diario.ler(id="casa/a")], ["casa/a"])
        self.assertEqual([e.id for e in self.diario.ler(usuario="ana")], ["casa/a"])
        self.assertEqual([e.id for e in self.diario.ler(desde="2030-01-15")], ["casa/b"])
        self.assertEqual([e.id for e in self.diario.ler(so_recusas=True)], ["casa/b"])

    def test_quebra_de_linha_no_motivo_nao_parte_o_registro(self):
        self.diario.registrar(evento(motivo="linha um\nlinha dois"))
        self.assertEqual(len(self.caminho.read_text(encoding="utf-8").splitlines()), 1)
        self.assertEqual(self.diario.ler()[0].motivo, "linha um\nlinha dois")

    def test_linha_truncada_nao_contamina_a_proxima_nem_derruba_a_leitura(self):
        """Processo morto no meio da escrita deixa meia linha sem \\n no fim."""
        self.caminho.write_text('{"ts": "2030', encoding="utf-8")
        self.diario.registrar(evento())
        self.assertEqual(self.diario.ler(), [evento()])

    def test_registrar_nunca_reescreve_o_que_ja_estava(self):
        self.diario.registrar(evento(id="casa/a"))
        antes = self.caminho.read_bytes()
        self.diario.registrar(evento(id="casa/b"))
        self.assertTrue(self.caminho.read_bytes().startswith(antes))
