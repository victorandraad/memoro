"""hooks/guarda_da_porta.py: PreToolUse do Claude Code que nega escrita direta em <MEMORO_HOME>/areas/.

Contrato do hook (o mesmo dos hooks de verdade): payload JSON no stdin com tool_name e tool_input
(file_path, ou notebook_path no NotebookEdit); exit 0 deixa passar; exit 2 bloqueia e o stderr
vira a razão mostrada ao modelo.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.apoio import ComRaiz

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "guarda_da_porta.py"


class TesteGuarda(ComRaiz):
    def setUp(self):
        super().setUp()
        (self.raiz / "areas" / "casa").mkdir(parents=True)
        self.fora = self.raiz.parent / "fora"
        self.fora.mkdir()

    def rodar(self, entrada, casa="padrao", cwd=None):
        ambiente = {k: v for k, v in os.environ.items() if k != "MEMORO_HOME"}
        if casa == "padrao":
            ambiente["MEMORO_HOME"] = str(self.raiz)
        elif casa is not None:
            ambiente["MEMORO_HOME"] = casa
        if not isinstance(entrada, (str, bytes)):
            entrada = json.dumps(entrada)
        if isinstance(entrada, str):
            entrada = entrada.encode("utf-8")
        r = subprocess.run([sys.executable, str(HOOK)], input=entrada, capture_output=True, env=ambiente,
                           cwd=str(cwd or self.fora), timeout=10)
        return r.returncode, r.stderr.decode("utf-8", errors="replace")

    def payload(self, caminho, ferramenta="Write", chave="file_path"):
        return {"session_id": "s", "hook_event_name": "PreToolUse", "cwd": str(self.fora),
                "tool_name": ferramenta, "tool_input": {chave: str(caminho), "content": "x"}}

    def test_nega_escrita_direta_e_ensina_a_porta(self):
        for ferramenta in ("Write", "Edit", "MultiEdit"):
            codigo, erro = self.rodar(self.payload(self.raiz / "areas" / "casa" / "rotina.md", ferramenta))
            self.assertEqual(codigo, 2, ferramenta)
            for trecho in ("memoro add", "memoro update", "memoro rm"):
                self.assertIn(trecho, erro)

    def test_nega_notebook_e_arquivo_que_ainda_nao_existe_em_pasta_nova(self):
        alvo = self.raiz / "areas" / "nova" / "sub" / "fato.ipynb"
        self.assertEqual(self.rodar(self.payload(alvo, "NotebookEdit", "notebook_path"))[0], 2)

    def test_deixa_passar_fora_de_areas(self):
        for alvo in (self.fora / "a.md", self.raiz / "lentes.json", self.raiz / "areas-velhas" / "a.md",
                     self.raiz.parent / "raiz-vizinha" / "areas" / "a.md"):
            self.assertEqual(self.rodar(self.payload(alvo))[0], 0, str(alvo))

    def test_travessia_com_ponto_ponto(self):
        alvo = "%s/../raiz/areas/casa/rotina.md" % self.fora
        self.assertEqual(self.rodar(self.payload(alvo))[0], 2)
        escapa = "%s/areas/../lentes.json" % self.raiz
        self.assertEqual(self.rodar(self.payload(escapa))[0], 0)

    def test_symlink_pra_dentro_de_areas(self):
        (self.fora / "atalho").symlink_to(self.raiz / "areas" / "casa", target_is_directory=True)
        self.assertEqual(self.rodar(self.payload(self.fora / "atalho" / "rotina.md"))[0], 2)
        (self.raiz / "areas" / "casa" / "rotina.md").write_text("x\n", encoding="utf-8")
        (self.fora / "solto.md").symlink_to(self.raiz / "areas" / "casa" / "rotina.md")
        self.assertEqual(self.rodar(self.payload(self.fora / "solto.md"))[0], 2)

    def test_memoro_home_que_e_symlink(self):
        (self.fora / "casa-do-memoro").symlink_to(self.raiz, target_is_directory=True)
        codigo, _ = self.rodar(self.payload(self.raiz / "areas" / "casa" / "a.md"), casa=str(self.fora / "casa-do-memoro"))
        self.assertEqual(codigo, 2)

    def test_caminho_relativo_resolve_pelo_cwd_do_payload(self):
        p = self.payload("areas/casa/rotina.md")
        p["cwd"] = str(self.raiz)
        self.assertEqual(self.rodar(p, cwd=self.fora)[0], 2)

    def test_sem_memoro_home_usa_o_padrao_da_cli(self):
        ambiente_home = self.raiz.parent / "lar"
        (ambiente_home / "memoro" / "areas").mkdir(parents=True)
        entrada = json.dumps(self.payload(ambiente_home / "memoro" / "areas" / "a.md")).encode("utf-8")
        ambiente = {k: v for k, v in os.environ.items() if k != "MEMORO_HOME"}
        ambiente["HOME"] = str(ambiente_home)
        r = subprocess.run([sys.executable, str(HOOK)], input=entrada, capture_output=True, env=ambiente, timeout=10)
        self.assertEqual(r.returncode, 2)

    def test_entrada_torta_deixa_passar(self):
        tortos = ["", "nao e json", "[]", "null", '{"tool_input": "texto"}', '{"tool_input": {"file_path": 7}}',
                  '{"tool_input": {}}', b"\xff\xfe\x00", '{"tool_input": {"file_path": "a\\u0000b"}}']
        for torto in tortos:
            codigo, _ = self.rodar(torto)
            self.assertEqual(codigo, 0, repr(torto))

    def test_nao_carrega_caminho_fixo(self):
        fonte = HOOK.read_text(encoding="utf-8")
        self.assertIn("MEMORO_HOME", fonte)
        self.assertNotIn("/home/", fonte)
