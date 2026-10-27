"""Gráficos de evolução do PDF: barras Direito/Esquerdo agrupadas por data da
avaliação, com a tabela de valores e a assimetria ao lado — mesmo formato do
"Evolução de Assimetria" do Kinology. Desenhados com `reportlab.graphics`
(vetoriais, sem matplotlib).

Uma `serie` é uma lista ordenada por data: `[{"data": date, "D": 13.2, "E": 17.6}, ...]`.
"""
from __future__ import annotations

from typing import Callable

from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from avaliacao_fisio import assimetria, pdf_base

MAX_DATAS = 4
_GAP = 0.5 * cm
_LARGURA_CARD = (pdf_base.LARGURA_UTIL - _GAP) / 2
_ALTURA_GRAFICO = 3.4 * cm

_TITULO_BLOCO = ParagraphStyle(
    "TituloBlocoEvolucao", parent=pdf_base.ESTILO_NORMAL, fontSize=9.5, leading=12,
    textColor=pdf_base.COR_ESCURO, fontName="Helvetica-Bold",
)
_LEGENDA = ParagraphStyle("LegendaEvolucao", parent=pdf_base.CELULA_OBS, fontSize=7.5, leading=10, spaceBefore=6)


def data_curta(d) -> str:
    return d.strftime("%d/%m/%y") if hasattr(d, "strftime") else str(d)


def _padrao(valor) -> str:
    return pdf_base.numero_br(valor)


def _cor_barra(lado: str, d, e, sentido: str | None):
    """Cor da barra do lado `lado`: o lado mais fraco leva a cor da faixa de
    risco; o outro (e os dois, sem direção clara) ficam neutros."""
    if assimetria.lado_mais_fraco(d, e, sentido) != lado:
        return pdf_base.COR_NEUTRO_BARRA
    pct = assimetria.percentual(d, e)
    return pdf_base.CORES_FAIXA[assimetria.faixa(pct)][0]


def _desenho(serie: list[dict], sentido: str | None, formatar: Callable) -> Drawing:
    largura = _LARGURA_CARD
    desenho = Drawing(largura, _ALTURA_GRAFICO)
    valores = [v for p in serie for v in (p.get("D"), p.get("E")) if v is not None]
    maior = max(valores) if valores else 1
    if maior <= 0:
        maior = 1
    base_y = 0.62 * cm
    area_h = _ALTURA_GRAFICO - base_y - 0.55 * cm
    n = len(serie)
    largura_grupo = largura / n
    largura_barra = min(0.95 * cm, largura_grupo * 0.3)
    folga = 0.12 * cm

    desenho.add(Rect(0, base_y - 0.5, largura, 0.8, fillColor=colors.HexColor("#cfd6d3"), strokeColor=None))

    for i, ponto in enumerate(serie):
        centro = largura_grupo * (i + 0.5)
        x_barras = {"D": centro - folga / 2 - largura_barra, "E": centro + folga / 2}
        for lado in ("D", "E"):
            valor = ponto.get(lado)
            if valor is None:
                continue
            altura = max(area_h * (valor / maior), 0.12 * cm)
            cor = _cor_barra(lado, ponto.get("D"), ponto.get("E"), sentido)
            desenho.add(Rect(x_barras[lado], base_y, largura_barra, altura, fillColor=cor, strokeColor=None, rx=2, ry=2))
            desenho.add(String(
                x_barras[lado] + largura_barra / 2, base_y + altura + 3, formatar(valor), fontName="Helvetica-Bold",
                fontSize=7.5, fillColor=colors.HexColor("#4a4a46") if cor == pdf_base.COR_NEUTRO_BARRA else cor,
                textAnchor="middle",
            ))
            if altura > 0.5 * cm:
                desenho.add(String(
                    x_barras[lado] + largura_barra / 2, base_y + 0.14 * cm, lado, fontName="Helvetica-Bold",
                    fontSize=7.5, fillColor=colors.white, textAnchor="middle",
                ))
        desenho.add(String(
            centro, 0.1 * cm, data_curta(ponto["data"]), fontName="Helvetica", fontSize=7.5,
            fillColor=colors.HexColor("#4a4a46"), textAnchor="middle",
        ))
    return desenho


def _tabela_valores(serie: list[dict], formatar: Callable) -> Table:
    # Sem a unidade em cada célula: ela já está no título do gráfico.
    def texto_valor(v) -> str:
        return formatar(v) if v is not None else ""

    cab = pdf_base.CELULA_CABECALHO_PEQUENA
    linhas = [[Paragraph("Data", cab), Paragraph("Direito", cab), Paragraph("Esquerdo", cab), Paragraph("Assimetria", cab)]]
    for ponto in serie:
        pct = assimetria.percentual(ponto.get("D"), ponto.get("E"))
        if pct is None:
            texto_pct = ""
        else:
            cor = pdf_base.CORES_FAIXA[assimetria.faixa(pct)][0].hexval()[2:]
            texto_pct = f'<font color="#{cor}"><b>{pdf_base.numero_br(pct, 1)}%</b></font>'
        linhas.append([
            Paragraph(data_curta(ponto["data"]), pdf_base.CELULA), Paragraph(texto_valor(ponto.get("D")), pdf_base.CELULA),
            Paragraph(texto_valor(ponto.get("E")), pdf_base.CELULA), Paragraph(texto_pct, pdf_base.CELULA),
        ])
    apertado = [("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    return pdf_base.tabela(linhas, (0.23, 0.24, 0.25, 0.28), extra=apertado, largura=_LARGURA_CARD)


def bloco(titulo: str, unidade: str | None, serie: list[dict], sentido: str | None, formatar: Callable | None = None) -> Table:
    formatar = formatar or _padrao
    serie = serie[-MAX_DATAS:]
    rotulo = f"{titulo} ({unidade})" if unidade else titulo
    card = Table(
        [[Paragraph(rotulo, _TITULO_BLOCO)], [_desenho(serie, sentido, formatar)], [_tabela_valores(serie, formatar)]],
        colWidths=[_LARGURA_CARD],
    )
    card.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return card


def grade(blocos: list[Table]) -> list:
    """Dois blocos por linha (uma linha nunca é cortada entre páginas)."""
    if not blocos:
        return []
    linhas = []
    for i in range(0, len(blocos), 2):
        par = blocos[i:i + 2]
        linhas.append([par[0], "", par[1] if len(par) > 1 else ""])
    t = Table(linhas, colWidths=[_LARGURA_CARD, _GAP, _LARGURA_CARD])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    return [t]


def legenda() -> list:
    verde, amarelo, vermelho = (
        pdf_base.CORES_FAIXA[f][0].hexval()[2:] for f in (assimetria.BAIXA, assimetria.MEDIA, assimetria.ALTA)
    )
    texto = (
        "Chance de lesão por assimetria: "
        f'<font color="#{verde}"><b>■</b></font> abaixo de 10% (baixa) · '
        f'<font color="#{amarelo}"><b>■</b></font> de 10% a 20% (média) · '
        f'<font color="#{vermelho}"><b>■</b></font> acima de 20% (alta). '
        "A assimetria é calculada em relação ao lado com o maior valor medido. "
        "A barra colorida é o lado de menor desempenho; testes sem direção definida (ex.: amplitude de movimento) "
        "não destacam nenhum lado."
    )
    return [Spacer(1, 0.1 * cm), Paragraph(texto, _LEGENDA)]
