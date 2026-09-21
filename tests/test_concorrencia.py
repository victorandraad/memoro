"""Dois processos de verdade na mesma raiz: a tranca de arquivo tem que serializar a porta."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.apoio import ComRaiz

PACOTE = str(Path(__file__).resolve().parent.parent)


class TestConcorrencia(ComRaiz):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.cli("init")[0], 0)
        git = ["git", "-C", str(self.raiz)]
        subprocess.run(git + ["init", "-q"], check=True)
        subprocess.run(git + ["config", "user.email", "teste@example.test"], check=True)
        subprocess.run(git + ["config", "user.name", "teste"], check=True)

    def disparar(self, argvs):
        env = dict(os.environ, MEMORO_HOME=str(self.raiz), PYTHONPATH=PACOTE)
        procs = [subprocess.Popen([sys.executable, "-m", "memoro"] + a, env=env, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE) for a in argvs]
        return [(p.communicate(b"corpo\n", timeout=120), p.returncode)[1] for p in procs]

    def eventos(self):
        return [json.loads(l) for l in (self.raiz / "eventos.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_doze_adds_simultaneos_nao_perdem_fato_evento_nem_commit(self):
        n = 12
        codigos = self.disparar([["add", "casa", "fato-%d" % i, "--desc", "descrição %d" % i] for i in range(n)])
        self.assertEqual(codigos, [0] * n)
        self.assertEqual(len(list((self.raiz / "areas/casa").glob("fato-*.md"))), n)
        self.assertEqual(len([e for e in self.eventos() if e["ok"]]), n)  # toda linha é JSON inteiro
        log = subprocess.run(["git", "-C", str(self.raiz), "log", "--format=%s"], capture_output=True, text=True)
        self.assertEqual(len(log.stdout.splitlines()), n)

    def test_mesmo_id_em_paralelo_so_um_vence(self):
        codigos = self.disparar([["add", "casa", "unico", "--desc", "versão %d" % i] for i in range(6)])
        self.assertEqual(sorted(codigos), [0, 1, 1, 1, 1, 1])
        self.assertEqual(sorted(e["ok"] for e in self.eventos()), [False] * 5 + [True])
