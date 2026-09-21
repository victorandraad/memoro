"""Recria a memória fictícia da vitrine em demo/acervo/. Tudo aqui é inventado e inofensivo.

Uso: python3 demo/semear.py
Formato de cada linha de FATOS: (id, descricao, uses, links). Referência sem área é resolvida pelo nome.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

from memoro.porta import PortaDeEscrita  # noqa: E402

FATOS = [
    ("casa/rotina", "Rotina semanal da casa: o que se repete e em que dia.", [], []),
    ("casa/compras", "Lista base do mercado, o que nunca pode faltar.", ["casa/rotina"], ["lista-da-feira"]),
    ("casa/contas-do-mes", "Vencimentos fixos e onde cada boleto chega.", ["casa/rotina"], []),
    ("casa/manutencao", "O que revisar a cada estação: calhas, filtros, vedação.", ["casa/rotina"], []),
    ("casa/horta/tomate", "Tomate cereja em vaso: rega e tutor.", ["casa/horta/calendario-de-plantio"], []),
    ("casa/horta/manjericao", "Manjericão gosta de sol da manhã e poda frequente.", ["casa/horta/calendario-de-plantio"], []),
    ("casa/horta/calendario-de-plantio", "O que plantar em cada mês na varanda.", ["casa/rotina"], []),
    ("casa/horta/compostagem", "Composteira de três baldes: o que entra e o que não entra.", [], ["casa/horta/tomate"]),
    ("casa/receitas/pao-de-fermentacao-lenta", "Pão de 18 horas, sem sova.", [], ["casa/compras"]),
    ("casa/receitas/caldo-base", "Caldo de legumes que vira base de tudo na semana.", [], ["casa/compras"]),
    ("estudo/rotina", "Blocos de estudo: 50 minutos, pausa de 10, revisão no fim.", [], []),
    ("estudo/plano-do-semestre", "Temas do semestre e a ordem de ataque.", ["estudo/rotina"], []),
    ("estudo/metodo-de-revisao", "Repetição espaçada: 1, 3, 7 e 21 dias.", ["estudo/rotina"], []),
    ("estudo/fichamento", "Como resumir um capítulo em uma página.", ["estudo/metodo-de-revisao"], []),
    ("estudo/idiomas/italiano-verbos", "Verbos irregulares mais comuns do italiano.", ["estudo/metodo-de-revisao"], []),
    ("estudo/idiomas/italiano-frases", "Frases prontas de viagem.", ["estudo/idiomas/italiano-verbos"], []),
    ("estudo/matematica/algebra-linear", "Intuição geométrica antes da conta.", ["estudo/plano-do-semestre"], []),
    ("estudo/matematica/probabilidade", "Problemas clássicos e onde a intuição engana.", ["estudo/plano-do-semestre"], ["estudo/fichamento"]),
    ("estudo/leituras", "Fila de livros e o motivo de cada um estar nela.", [], ["estudo/fichamento"]),
    ("hobby/violao/afinacao", "Afinação padrão e duas afinações abertas.", [], []),
    ("hobby/violao/repertorio", "Músicas que já saem inteiras.", ["hobby/violao/afinacao"], []),
    ("hobby/violao/exercicios-de-dedilhado", "Quatro padrões de mão direita para aquecer.", ["hobby/violao/afinacao"], ["rotina"]),
    ("hobby/fotografia/triangulo-de-exposicao", "Abertura, velocidade e ISO em uma frase cada.", [], []),
    ("hobby/fotografia/luz-de-janela", "Retrato com luz lateral e rebatedor de papel.", ["hobby/fotografia/triangulo-de-exposicao"], []),
    ("hobby/fotografia/revelacao", "Fluxo de edição: corte, exposição, cor, nitidez.", ["hobby/fotografia/triangulo-de-exposicao"], []),
    ("hobby/trilhas", "Trilhas curtas da região e a melhor época de cada uma.", [], ["hobby/fotografia/luz-de-janela"]),
    ("hobby/checklist", "O que vai na mochila de um dia.", [], ["hobby/trilhas"]),
    ("hobby/xadrez-aberturas", "Três aberturas e a ideia por trás de cada uma.", [], []),
    ("trabalho/checklist", "Antes de entregar: revisar, testar, avisar.", [], []),
    ("trabalho/convencoes-de-codigo", "Nomes, tamanho de função e quando comentar.", [], []),
    ("trabalho/revisao-de-codigo", "O que olhar primeiro num diff.", ["trabalho/convencoes-de-codigo", "trabalho/checklist"], []),
    ("trabalho/reunioes", "Pauta antes, decisão por escrito depois.", [], ["modelo-de-ata"]),
    ("trabalho/estimativas", "Estimar por faixa, nunca por número único.", [], ["trabalho/reunioes"]),
    ("trabalho/projeto-biblioteca/escopo", "Catálogo de uma biblioteca de bairro fictícia.", ["trabalho/convencoes-de-codigo"], []),
    ("trabalho/projeto-biblioteca/modelo-de-dados", "Livro, exemplar, leitor, empréstimo.", ["trabalho/projeto-biblioteca/escopo"], []),
    ("trabalho/projeto-biblioteca/regras-de-emprestimo", "Prazo, renovação e fila de espera.", ["trabalho/projeto-biblioteca/modelo-de-dados"], []),
    ("saude-do-servidor/backup", "Regra 3-2-1 aplicada a um servidor caseiro.", [], []),
    ("saude-do-servidor/teste-de-restauracao", "Backup que nunca foi restaurado não é backup.", ["saude-do-servidor/backup"], []),
    ("saude-do-servidor/disco-cheio", "O que olhar primeiro quando o disco enche.", [], ["saude-do-servidor/rotacao-de-logs"]),
    ("saude-do-servidor/rotacao-de-logs", "Tamanho máximo, retenção e compressão.", [], []),
    ("saude-do-servidor/atualizacoes", "Janela de atualização e como voltar atrás.", ["saude-do-servidor/backup"], ["trabalho/checklist"]),
    ("saude-do-servidor/certificados", "Renovação automática e o alerta de 15 dias.", ["saude-do-servidor/atualizacoes"], []),
]

LENTES = {
    "dia-a-dia": ["casa", "estudo"],
    "maos-na-massa": ["casa/horta", "casa/receitas", "hobby"],
    "oficio": ["trabalho", "saude-do-servidor"],
}


class Semeador:
    def __init__(self, raiz):
        self.raiz = Path(raiz)

    def semear(self):
        shutil.rmtree(self.raiz, ignore_errors=True)
        self.raiz.mkdir(parents=True)
        topos = sorted({ident.split("/", 1)[0] for ident, *_ in FATOS})
        for topo in topos:
            (self.raiz / "areas" / topo).mkdir(parents=True, exist_ok=True)
        (self.raiz / "lentes.json").write_text(
            json.dumps(LENTES, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        porta = PortaDeEscrita.padrao(self.raiz, "demo")
        vistos = set()
        n = 0
        for ident, descricao, uses, links in self._ordenar(FATOS):
            area, _, nome = ident.rpartition("/")
            corpo = "Texto de exemplo do fato. O corpo nunca aparece no mapa."
            if links:
                corpo += "\n\nVeja também: " + ", ".join("[[%s]]" % x for x in links) + "."
            porta.add(
                area, nome, descricao, corpo + "\n",
                uses=uses,
                novo_mesmo_assim=nome in vistos,
            )
            vistos.add(nome)
            n += 1
        return n

    def _ordenar(self, fatos):
        ids = [item[0] for item in fatos]
        por_id = {item[0]: item for item in fatos}
        presentes = set(ids)
        falta = set(ids)
        saida = []
        while falta:
            progresso = False
            for ident in ids:
                if ident not in falta:
                    continue
                if any(alvo in falta for alvo in por_id[ident][2] if alvo in presentes):
                    continue
                saida.append(por_id[ident])
                falta.remove(ident)
                progresso = True
            if not progresso:
                for ident in ids:
                    if ident in falta:
                        saida.append(por_id[ident])
                break
        return saida


if __name__ == "__main__":
    print(Semeador(AQUI / "acervo").semear(), "fatos")
