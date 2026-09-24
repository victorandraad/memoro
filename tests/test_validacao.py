from __future__ import annotations

import unittest

from memoro.dominio import Fato, IdDeFato
from memoro.validacao import (Achado, Pedido, RegraDeAreaExistente, RegraDeMotivoNaRemocao,
                              RegraDeNomeDuplicado, RegraDeRelacaoConhecida, RegraDeSegredo, Validador)


def fato(area="casa", nome="fogao", desc="quatro bocas", corpo="acende com fósforo\n", uses=()):
    return Fato(IdDeFato(area, nome), desc, corpo, uses=tuple(uses))


def pedido(op="add", f=None, existentes=(), areas=("casa", "trabalho"), motivo=""):
    f = f or fato()
    return Pedido(op=op, id=f.id, fato=f, motivo=motivo, existentes=tuple(existentes), areas=tuple(areas))


class TestRegraDeSegredo(unittest.TestCase):
    # montados por concatenação: o arquivo de teste não carrega nada com cara de credencial
    SEGREDOS = {
        "github-token": "gh" + "p_" + "a1B2" * 9,
        "aws-access-key": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
        "chave-sk": "s" + "k-" + "abcDEF0123456789abcDEF",
        "slack-token": "xo" + "xb-" + "1234567890-abcdef",
        "private-key-block": "-----BEGIN RSA " + "PRIVATE KEY-----",
        "jwt": "ey" + "JhbGciOiJIUzI1NiJ9" + ".ey" + "Jzdwiqweqweqwe12" + ".assinatura",
    }

    def test_cada_formato_e_recusado_sem_vazar_o_valor(self):
        for tipo, valor in self.SEGREDOS.items():
            achados = RegraDeSegredo().avaliar(pedido(f=fato(corpo="linha\nsenha: %s\n" % valor)))
            self.assertEqual(len(achados), 1, tipo)
            self.assertTrue(achados[0].recusa, tipo)
            self.assertIn("linha", achados[0].mensagem)
            self.assertNotIn(valor, achados[0].mensagem)

    def test_segredo_na_descricao_tambem_conta(self):
        f = fato(desc="token " + self.SEGREDOS["github-token"])
        self.assertTrue(RegraDeSegredo().avaliar(pedido(f=f))[0].recusa)

    def test_texto_comum_e_pragma_passam(self):
        self.assertEqual(RegraDeSegredo().avaliar(pedido()), [])
        f = fato(corpo="exemplo %s  # pragma: allow-secret\n" % self.SEGREDOS["aws-access-key"])
        self.assertEqual(RegraDeSegredo().avaliar(pedido(f=f)), [])

    # outros formatos reais, também montados por concatenação
    SEGREDOS_EXTRA = {
        "github-token": ["gh" + "o_" + "Z9y8" * 9, "github" + "_pat_" + "11ABCDEFG0" + "a" * 20],
        "aws-access-key": ["AS" + "IA" + "QRSTUVWXYZ234567"],
        "slack-token": ["xo" + "xp-" + "98765-4321-abcdef", "xo" + "xa-" + "2-abcdefghij"],
        "private-key-block": ["-----BEGIN " + "PRIVATE KEY-----", "-----BEGIN OPENSSH " + "PRIVATE KEY-----",
                              "-----BEGIN EC " + "PRIVATE KEY-----"],
    }

    NEGATIVOS = [
        "commit 3f786850e387550fdab836ed7e6dc881de23001b corrigiu o bug",
        "ver 3f78685 no log",
        "id 123e4567-e89b-12d3-a456-426614174000 da sessão",
        "a password do wifi fica com a Ana",
        "trocar a senha do banco todo mês",
        "o token expira em uma hora, renovar pelo painel",
        "base64 curto: aGVsbG8gd29ybGQ=",
        "investimento risk-free não existe",
        "o desk-top novo e a task-list da semana",
        "exportar AWS_ACCESS_KEY_ID e AWS_SECRET_ACCESS_KEY antes do deploy",
        "repo em https://github.com/victorandraad/memoro/blob/main/README.md",
        "git clone git@github.com:victorandraad/memoro.git",
        "-----BEGIN PUBLIC KEY-----",
        "cabeçalho eyJ sozinho não é jwt",
    ]

    def test_formatos_extra_sao_recusados(self):
        for tipo, valores in self.SEGREDOS_EXTRA.items():
            for valor in valores:
                achados = RegraDeSegredo().avaliar(pedido(f=fato(corpo="x %s\n" % valor)))
                self.assertEqual(len(achados), 1, valor)
                self.assertIn(tipo, achados[0].mensagem)

    def test_corpus_negativo_nao_e_barrado(self):
        for texto in self.NEGATIVOS:
            for f in (fato(corpo=texto + "\n"), fato(desc=texto)):
                self.assertEqual(RegraDeSegredo().avaliar(pedido(f=f)), [], texto)

    def test_so_olha_escrita(self):
        f = fato(corpo=self.SEGREDOS["jwt"])
        self.assertEqual(RegraDeSegredo().avaliar(pedido(op="rm", f=f, motivo="x")), [])


class TestDemaisRegras(unittest.TestCase):
    def test_area_de_topo_precisa_existir_e_subarea_nasce_pela_porta(self):
        regra = RegraDeAreaExistente()
        self.assertEqual(regra.avaliar(pedido(f=fato(area="casa/cozinha"))), [])
        achados = regra.avaliar(pedido(f=fato(area="cassa")))
        self.assertTrue(achados[0].recusa)
        self.assertIn("casa", achados[0].mensagem)  # sugere a parecida e lista as existentes

    def test_nome_duplicado_so_na_mesma_area(self):
        regra = RegraDeNomeDuplicado()
        self.assertEqual(regra.avaliar(pedido(existentes=[fato(area="trabalho")])), [])
        achados = regra.avaliar(pedido(existentes=[fato()]))
        self.assertTrue(achados[0].recusa)
        self.assertIn("update", achados[0].mensagem)
        self.assertEqual(regra.avaliar(pedido(op="update", existentes=[fato()])), [])

    def test_relacao_fora_do_vocabulario(self):
        regra = RegraDeRelacaoConhecida()
        self.assertEqual(regra.avaliar(pedido(f=fato(uses=["detalha:gas", "gas"]))), [])
        achados = regra.avaliar(pedido(f=fato(uses=["inventada:gas"])))
        self.assertTrue(achados[0].recusa)
        self.assertIn("inventada", achados[0].mensagem)

    def test_rm_exige_motivo(self):
        regra = RegraDeMotivoNaRemocao()
        self.assertTrue(regra.avaliar(pedido(op="rm", motivo="  "))[0].recusa)
        self.assertEqual(regra.avaliar(pedido(op="rm", motivo="duplicado")), [])
        self.assertEqual(regra.avaliar(pedido(op="add")), [])

    def test_validador_compoe_na_ordem_e_junta_avisos(self):
        class SoAvisa(RegraDeMotivoNaRemocao):
            def avaliar(self, p):
                return [Achado(False, "olha lá")]
        achados = Validador([SoAvisa(), RegraDeNomeDuplicado()]).avaliar(pedido(existentes=[fato()]))
        self.assertEqual([a.recusa for a in achados], [False, True])
        self.assertEqual(len(Validador.padrao().regras) >= 5, True)


if __name__ == "__main__":
    unittest.main()
