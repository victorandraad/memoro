from __future__ import annotations

import re

_FRONT = re.compile(r"^---\n(.*?)\n---\n", re.S)


class LeitorDeFrontmatter:
    def ler(self, texto):
        campos = {"uses": [], "scope": []}
        achado = _FRONT.match(texto)
        if not achado:
            return campos, texto
        alvo = None
        for linha in achado.group(1).splitlines():
            if alvo is not None:
                item = linha.strip()
                if item.startswith("- "):
                    alvo.append(item[2:].strip())
                    continue
                alvo = None
            chave, _, valor = linha.partition(":")
            chave, valor = chave.strip(), valor.strip()
            if not chave:
                continue
            if chave in ("uses", "scope"):
                lista = [s.strip() for s in valor.strip("[]").split(",") if s.strip()]
                campos[chave] = lista
                if not valor:
                    alvo = campos[chave]
            else:
                campos[chave] = valor
        return campos, texto[achado.end():].lstrip("\n")


def problemas_do_frontmatter(texto, area, nome):
    """Inconsistências entre o bloco --- e o caminho do arquivo; vazio se alinhado."""
    if _FRONT.match(texto) is None:
        return ["sem bloco de frontmatter"]
    campos, _ = LeitorDeFrontmatter().ler(texto)
    problemas = []
    if campos.get("name") != nome:
        problemas.append("name diferente do arquivo")
    if campos.get("area") != area:
        problemas.append("area diferente da pasta")
    return problemas


class EscritorDeFrontmatter:
    def escrever(self, fato, extras=None):
        linhas = [
            "name: %s" % fato.nome,
            "description: %s" % self._uma_linha(fato.descricao),
            "area: %s" % fato.area,
        ]
        if fato.uses:
            linhas.append("uses: [%s]" % ", ".join(fato.uses))
        if fato.scope:
            linhas.append("scope: [%s]" % ", ".join(fato.scope))
        for chave, valor in (extras or {}).items():
            linhas.append("%s: %s" % (chave, self._uma_linha(str(valor))))
        return "---\n%s\n---\n\n%s" % ("\n".join(linhas), self._corpo_sem_bloco(fato.corpo))

    def _uma_linha(self, texto):
        return " ".join(texto.splitlines())

    def _corpo_sem_bloco(self, corpo):
        while True:
            texto = corpo.lstrip("\n")
            achado = _FRONT.match(texto)
            if not achado:
                return texto
            corpo = texto[achado.end():]
