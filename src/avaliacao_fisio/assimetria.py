"""Regra de assimetria entre o lado direito e o esquerdo (única fonte da
verdade — usada pela tela de Revisão e pelo PDF).

Fórmula da clínica (colada pelo Sergio em 13/10/2026), a mesma do Kinology:
diferença entre os lados dividida pelo MAIOR valor medido. Abaixo de 10% =
baixa chance de lesão, de 10% a 20% = média, acima de 20% = alta.
"""
from __future__ import annotations

LIMITE_MEDIA = 10.0
LIMITE_ALTA = 20.0

BAIXA = "baixa"
MEDIA = "media"
ALTA = "alta"

ROTULO_CHANCE = {
    BAIXA: "baixa chance de lesão",
    MEDIA: "média chance de lesão",
    ALTA: "alta chance de lesão",
}


def _numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def percentual(d, e) -> float | None:
    """None quando falta um dos lados ou quando os dois são zero."""
    if not _numero(d) or not _numero(e):
        return None
    maior = max(abs(d), abs(e))
    if maior == 0:
        return None
    return abs(d - e) / maior * 100


def faixa(pct: float) -> str:
    if pct < LIMITE_MEDIA:
        return BAIXA
    if pct < LIMITE_ALTA:
        return MEDIA
    return ALTA


def lado_mais_fraco(d, e, sentido: str | None) -> str | None:
    """"D" ou "E" — o lado de pior desempenho, que recebe a cor de risco no
    gráfico. `sentido`: "maior" (mais é melhor: força, alcance, saltos),
    "menor" (menos é melhor: tempo de salto) ou None (sem direção clara,
    ex.: flexibilidade — nenhum lado é destacado). Empate ou dado faltando
    devolve None."""
    if sentido not in ("maior", "menor") or not _numero(d) or not _numero(e) or d == e:
        return None
    d_pior = d < e if sentido == "maior" else d > e
    return "D" if d_pior else "E"
