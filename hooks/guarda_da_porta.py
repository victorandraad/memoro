#!/usr/bin/env python3
"""Hook PreToolUse do Claude Code: recusa escrita direta em áreas da memória.

Trecho de settings.json:

{"matcher": "Edit|Write|MultiEdit|NotebookEdit", "hooks": [{"type": "command", "command": "python3 /caminho/do/repo/hooks/guarda_da_porta.py", "timeout": 5}]}
"""
from __future__ import annotations

import json
import os
import sys


class GuardaDaPorta:
    def __init__(self, ambiente):
        self._ambiente = ambiente

    def decidir(self, carga):
        if not isinstance(carga, dict):
            return None
        entrada = carga.get("tool_input")
        if not isinstance(entrada, dict):
            return None
        caminho = entrada.get("file_path")
        if caminho is None:
            caminho = entrada.get("notebook_path")
        if not isinstance(caminho, str) or not caminho or "\0" in caminho:
            return None
        if not os.path.isabs(caminho):
            cwd = carga.get("cwd")
            if not isinstance(cwd, str):
                return None
            caminho = os.path.join(cwd, caminho)
        # os dois olhares: o real (atalho de fora pra dentro) e o lexical (atalho de dentro pra fora)
        areas_lexical = os.path.abspath(os.path.join(self._raiz(), "areas"))
        areas = os.path.realpath(areas_lexical)
        dentro = (self._mesmo_prefixo(os.path.realpath(caminho), areas)
                  or self._mesmo_prefixo(os.path.abspath(caminho), areas_lexical))
        if not dentro:
            return None
        if self._ambiente.get("MEMORO_LANG", "").strip().lower().startswith("pt"):
            return (
                "escrita direta em áreas da memória recusada: "
                "use 'memoro add', 'memoro update' ou 'memoro rm'.\n"
            )
        return (
            "direct write to memory areas refused: "
            "use 'memoro add', 'memoro update' or 'memoro rm'.\n"
        )

    def _raiz(self):
        casa = self._ambiente.get("MEMORO_HOME")
        if casa:
            return casa
        return os.path.join(self._ambiente["HOME"], "memoro")

    @staticmethod
    def _mesmo_prefixo(alvo, prefixo):
        partes_alvo = alvo.split(os.sep)
        partes_pref = prefixo.split(os.sep)
        return partes_alvo[:len(partes_pref)] == partes_pref


def main():
    try:
        carga = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        razao = GuardaDaPorta(os.environ).decidir(carga)
        if razao:
            sys.stderr.write(razao)
            return 2
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
