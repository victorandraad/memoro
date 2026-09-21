from __future__ import annotations

import fcntl
import json
import os
from dataclasses import asdict
from pathlib import Path

from memoro.dominio import Evento

# ponytail: fcntl tranca só em Unix; upgrade é lock portátil (portalocker ou equivalente)


_CAMPOS = (
    "ts", "usuario", "op", "id", "area", "resumo", "ok", "motivo", "hash_do_conteudo",
)


class DiarioDeEventos:
    def __init__(self, caminho):
        self._caminho = Path(caminho)

    def registrar(self, evento):
        blob = (json.dumps(asdict(evento), ensure_ascii=False) + "\n").encode("utf-8")
        fd = os.open(str(self._caminho), os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            if os.fstat(fd).st_size > 0:
                # O_WRONLY não lê: o último byte sai de um fd de leitura, já com a tranca
                leitor = os.open(str(self._caminho), os.O_RDONLY)
                try:
                    os.lseek(leitor, -1, os.SEEK_END)
                    if os.read(leitor, 1) != b"\n":
                        blob = b"\n" + blob
                finally:
                    os.close(leitor)
            os.write(fd, blob)
        finally:
            os.close(fd)

    def ler(self, id=None, usuario=None, desde=None, so_recusas=False):
        if not self._caminho.is_file():
            return []
        eventos = []
        texto = self._caminho.read_text(encoding="utf-8", errors="replace")
        for linha in texto.splitlines():
            evento = self._evento_de(linha)
            if evento is None:
                continue
            if id is not None and evento.id != id:
                continue
            if usuario is not None and evento.usuario != usuario:
                continue
            if desde is not None and evento.ts < desde:
                continue
            if so_recusas and evento.ok:
                continue
            eventos.append(evento)
        return eventos

    def _evento_de(self, linha):
        try:
            dados = json.loads(linha)
        except ValueError:
            return None
        if not isinstance(dados, dict):
            return None
        for campo in _CAMPOS:
            if campo not in dados:
                return None
        return Evento(**{campo: dados[campo] for campo in _CAMPOS})
