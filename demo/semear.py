"""Recria a memória fictícia da vitrine em demo/acervo/. Tudo aqui e inventado e inofensivo.

Uso: python3 demo/semear.py
Formato de cada linha de FATOS: (id, descricao, uses, links). Referencia sem area e resolvida pelo nome.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

FATOS = [
    ("casa/rotina", "Rotina semanal da casa: o que se repete e em que dia.", [], []),
    ("casa/compras", "Lista base do mercado, o que nunca pode faltar.", ["casa/rotina"], ["lista-da-feira"]),
    ("casa/contas-do-mes", "Vencimentos fixos e onde cada boleto chega.", ["casa/rotina"], []),
    ("casa/manutencao", "O que revisar a cada estacao: calhas, filtros, vedacao.", ["casa/rotina"], []),
    ("casa/horta/tomate", "Tomate cereja em vaso: rega e tutor.", ["casa/horta/calendario-de-plantio"], []),
    ("casa/horta/manjericao", "Manjericao gosta de sol da manha e poda frequente.", ["casa/horta/calendario-de-plantio"], []),
    ("casa/horta/calendario-de-plantio", "O que plantar em cada mes na varanda.", ["casa/rotina"], []),
    ("casa/horta/compostagem", "Composteira de tres baldes: o que entra e o que nao entra.", [], ["casa/horta/tomate"]),
    ("casa/receitas/pao-de-fermentacao-lenta", "Pao de 18 horas, sem sova.", [], ["casa/compras"]),
    ("casa/receitas/caldo-base", "Caldo de legumes que vira base de tudo na semana.", [], ["casa/compras"]),
    ("estudo/rotina", "Blocos de estudo: 50 minutos, pausa de 10, revisao no fim.", [], []),
    ("estudo/plano-do-semestre", "Temas do semestre e a ordem de ataque.", ["estudo/rotina"], []),
    ("estudo/metodo-de-revisao", "Repeticao espacada: 1, 3, 7 e 21 dias.", ["estudo/rotina"], []),
    ("estudo/fichamento", "Como resumir um capitulo em uma pagina.", ["estudo/metodo-de-revisao"], []),
    ("estudo/idiomas/italiano-verbos", "Verbos irregulares mais comuns do italiano.", ["estudo/metodo-de-revisao"], []),
    ("estudo/idiomas/italiano-frases", "Frases prontas de viagem.", ["estudo/idiomas/italiano-verbos"], []),
    ("estudo/matematica/algebra-linear", "Intuicao geometrica antes da conta.", ["estudo/plano-do-semestre"], []),
    ("estudo/matematica/probabilidade", "Problemas classicos e onde a intuicao engana.", ["estudo/plano-do-semestre"], ["estudo/fichamento"]),
    ("estudo/leituras", "Fila de livros e o motivo de cada um estar nela.", [], ["estudo/fichamento"]),
    ("hobby/violao/afinacao", "Afinacao padrao e duas afinacoes abertas.", [], []),
    ("hobby/violao/repertorio", "Musicas que ja saem inteiras.", ["hobby/violao/afinacao"], []),
    ("hobby/violao/exercicios-de-dedilhado", "Quatro padroes de mao direita pra aquecer.", ["hobby/violao/afinacao"], ["rotina"]),
    ("hobby/fotografia/triangulo-de-exposicao", "Abertura, velocidade e ISO em uma frase cada.", [], []),
    ("hobby/fotografia/luz-de-janela", "Retrato com luz lateral e rebatedor de papel.", ["hobby/fotografia/triangulo-de-exposicao"], []),
    ("hobby/fotografia/revelacao", "Fluxo de edicao: corte, exposicao, cor, nitidez.", ["hobby/fotografia/triangulo-de-exposicao"], []),
    ("hobby/trilhas", "Trilhas curtas da regiao e a melhor epoca de cada uma.", [], ["hobby/fotografia/luz-de-janela"]),
    ("hobby/checklist", "O que vai na mochila de um dia.", [], ["hobby/trilhas"]),
    ("hobby/xadrez-aberturas", "Tres aberturas e a ideia por tras de cada uma.", [], []),
    ("trabalho/checklist", "Antes de entregar: revisar, testar, avisar.", [], []),
    ("trabalho/convencoes-de-codigo", "Nomes, tamanho de funcao e quando comentar.", [], []),
    ("trabalho/revisao-de-codigo", "O que olhar primeiro num diff.", ["trabalho/convencoes-de-codigo", "trabalho/checklist"], []),
    ("trabalho/reunioes", "Pauta antes, decisao por escrito depois.", [], ["modelo-de-ata"]),
    ("trabalho/estimativas", "Estimar por faixa, nunca por numero unico.", [], ["trabalho/reunioes"]),
    ("trabalho/projeto-biblioteca/escopo", "Catalogo de uma biblioteca de bairro ficticia.", ["trabalho/convencoes-de-codigo"], []),
    ("trabalho/projeto-biblioteca/modelo-de-dados", "Livro, exemplar, leitor, emprestimo.", ["trabalho/projeto-biblioteca/escopo"], []),
    ("trabalho/projeto-biblioteca/regras-de-emprestimo", "Prazo, renovacao e fila de espera.", ["trabalho/projeto-biblioteca/modelo-de-dados"], []),
    ("saude-do-servidor/backup", "Regra 3-2-1 aplicada a um servidor caseiro.", [], []),
    ("saude-do-servidor/teste-de-restauracao", "Backup que nunca foi restaurado nao e backup.", ["saude-do-servidor/backup"], []),
    ("saude-do-servidor/disco-cheio", "O que olhar primeiro quando o disco enche.", [], ["saude-do-servidor/rotacao-de-logs"]),
    ("saude-do-servidor/rotacao-de-logs", "Tamanho maximo, retencao e compressao.", [], []),
    ("saude-do-servidor/atualizacoes", "Janela de atualizacao e como voltar atras.", ["saude-do-servidor/backup"], ["trabalho/checklist"]),
    ("saude-do-servidor/certificados", "Renovacao automatica e o alerta de 15 dias.", ["saude-do-servidor/atualizacoes"], []),
]

LENTES = {
    "dia-a-dia": ["casa", "estudo"],
    "maos-na-massa": ["casa/horta", "casa/receitas", "hobby"],
    "oficio": ["trabalho", "saude-do-servidor"],
}


class Semeador:
    def __init__(self, raiz: Path):
        self.raiz = raiz

    def semear(self) -> int:
        shutil.rmtree(self.raiz, ignore_errors=True)
        for id_, descricao, uses, links in FATOS:
            arquivo = self.raiz / (id_ + ".md")
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            nome = id_.rsplit("/", 1)[-1]
            cabecalho = ["---", "name: " + nome, "description: " + descricao]
            if uses:
                cabecalho.append("uses: [" + ", ".join(uses) + "]")
            corpo = "Texto de exemplo do fato. O corpo nunca aparece no mapa."
            if links:
                corpo += "\n\nVeja tambem: " + ", ".join("[[%s]]" % x for x in links) + "."
            arquivo.write_text("\n".join(cabecalho + ["---", "", corpo, ""]), encoding="utf-8")
        (self.raiz / "lentes.json").write_text(json.dumps(LENTES, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return len(FATOS)


if __name__ == "__main__":
    print(Semeador(Path(__file__).resolve().parent / "acervo").semear(), "fatos")
