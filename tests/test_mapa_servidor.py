from __future__ import annotations

import argparse
import http.client
import json
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memoro.mapa import ComandoMapa, ConfigDoMapa, GeradorDeMapa, No, ServidorDoMapa  # noqa: E402


class Acervo:
    """Duble do nucleo: cada .md da raiz vira um no da area 'a'. A fabrica rele o disco a cada chamada."""

    def __init__(self):
        self.raiz = Path(tempfile.mkdtemp())
        self.saida = Path(tempfile.mkdtemp()) / "mapa"
        self.chamadas = 0
        (self.raiz / "a").mkdir()
        self.escreve("um")
        (self.raiz / "segredo.txt").write_text("NAO-SERVIR")

    def escreve(self, nome, mtime=None):
        arquivo = self.raiz / "a" / (nome + ".md")
        arquivo.write_text("corpo")
        if mtime:
            os.utime(arquivo, (mtime, mtime))

    def fabrica(self):
        self.chamadas += 1
        nos = [No(id="a/" + p.stem, nome=p.stem, descricao="", area="a", subarea=None, caminho="a/" + p.name)
               for p in sorted((self.raiz / "a").glob("*.md"))]
        return GeradorDeMapa(nos, [], {}, ConfigDoMapa(titulo="T"))


class TesteServidor(unittest.TestCase):
    def setUp(self):
        self.mem = Acervo()
        self.mem.fabrica().gerar(self.mem.saida)
        (self.mem.saida.parent / "fora.txt").write_text("NAO-SERVIR")
        self.servidor = ServidorDoMapa(self.mem.saida, self.mem.fabrica, self.mem.raiz, porta=0)
        self.servidor.iniciar()
        self.addCleanup(self.servidor.parar)

    def pedir(self, caminho, cabecalhos=None):
        conexao = http.client.HTTPConnection(*self.servidor.endereco, timeout=5)
        conexao.request("GET", caminho, headers=cabecalhos or {})
        resposta = conexao.getresponse()
        corpo = resposta.read()
        conexao.close()
        return resposta, corpo

    def cru(self, linha):
        with socket.create_connection(self.servidor.endereco, timeout=5) as s:
            s.sendall(("GET %s HTTP/1.0\r\n\r\n" % linha).encode())
            pedacos = []
            while True:
                pedaco = s.recv(65536)
                if not pedaco:
                    break
                pedacos.append(pedaco)
        return b"".join(pedacos)

    def test_so_escuta_em_loopback(self):
        self.assertEqual(self.servidor.endereco[0], "127.0.0.1")
        self.assertGreater(self.servidor.endereco[1], 0)
        import inspect
        self.assertNotIn("host", inspect.signature(ServidorDoMapa.__init__).parameters)

    def test_serve_indice_e_dados(self):
        resposta, corpo = self.pedir("/")
        self.assertEqual(resposta.status, 200)
        self.assertIn(b"<svg", corpo)
        resposta, corpo = self.pedir("/data.json")
        self.assertEqual(resposta.status, 200)
        self.assertEqual(len(json.loads(corpo)["nos"]), 1)

    def test_recusa_tudo_fora_da_saida(self):
        (self.mem.saida / "outro.txt").write_text("NAO-SERVIR")
        for caminho in ("/../fora.txt", "/..%2ffora.txt", "/%2e%2e/fora.txt", "//etc/passwd", "/outro.txt",
                        "/../../" + str(self.mem.raiz / "segredo.txt"), "/a/um.md"):
            bruto = self.cru(caminho)
            self.assertIn(b" 404 ", bruto.split(b"\r\n", 1)[0], caminho)
            self.assertNotIn(b"NAO-SERVIR", bruto, caminho)
            self.assertNotIn(b"root:", bruto, caminho)

    def test_etag_devolve_304(self):
        resposta, _ = self.pedir("/data.json")
        etag = resposta.getheader("ETag")
        self.assertTrue(etag)
        resposta, corpo = self.pedir("/data.json", {"If-None-Match": etag})
        self.assertEqual((resposta.status, corpo), (304, b""))

    def test_regenera_quando_md_muda_e_so_quando_muda(self):
        antes = self.mem.chamadas
        self.pedir("/data.json")
        self.pedir("/data.json")
        self.assertEqual(self.mem.chamadas, antes, "sem mudanca de mtime nao regenera")
        self.mem.escreve("dois", mtime=4102444800)
        _, corpo = self.pedir("/data.json")
        self.assertEqual(self.mem.chamadas, antes + 1)
        self.assertEqual([n["id"] for n in json.loads(corpo)["nos"]], ["a/dois", "a/um"])
        (self.mem.raiz / "a" / "um.md").unlink()
        _, corpo = self.pedir("/data.json")
        self.assertEqual([n["id"] for n in json.loads(corpo)["nos"]], ["a/dois"], "apagar fato tambem regenera")


class TesteComando(unittest.TestCase):
    def test_molde_e_geracao(self):
        mem = Acervo()
        comando = ComandoMapa(mem.fabrica, mem.raiz)
        self.assertEqual(comando.nome, "mapa")
        parser = argparse.ArgumentParser()
        comando.configurar(parser)
        args = parser.parse_args(["--saida", str(mem.saida)])
        self.assertEqual((args.servir, args.abrir), (None, False))
        self.assertEqual(comando.executar(args), 0)
        self.assertTrue((mem.saida / "index.html").is_file())
        self.assertTrue((mem.saida / "data.json").is_file())

    def test_servir_aceita_porta_opcional_e_saida_padrao_fica_na_raiz(self):
        mem = Acervo()
        comando = ComandoMapa(mem.fabrica, mem.raiz)
        parser = argparse.ArgumentParser()
        comando.configurar(parser)
        self.assertIsInstance(parser.parse_args(["--servir"]).servir, int)
        self.assertEqual(parser.parse_args(["--servir", "9123"]).servir, 9123)
        self.assertEqual(comando.executar(parser.parse_args([])), 0)
        self.assertTrue((mem.raiz / ".memoro" / "mapa" / "index.html").is_file())


if __name__ == "__main__":
    unittest.main()
