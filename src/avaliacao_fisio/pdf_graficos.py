"""Gráficos de evolução do PDF: barras Direito/Esquerdo agrupadas por data da
avaliação, com a tabela de valores e a assimetria ao lado — mesmo formato do
"Evolução de Assimetria" do Kinology. Desenhados com `reportlab.graphics`
(vetoriais, sem matplotlib).

Uma `serie` é uma lista ordenada por data: `[{"data": date, "D": 13.2, "E": 17.6}, ...]`.
"""
from __future__ import annotations

from typing import Callable

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Flowable, Paragraph, Spacer, Table, TableStyle

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


# Tons mais suaves que os da tabela de assimetria: o gráfico é só um apoio visual.
_CINZA_BARRA = colors.HexColor("#cdd5d1")
_BARRA_FAIXA = {
    assimetria.BAIXA: colors.HexColor("#52b788"),
    assimetria.MEDIA: colors.HexColor("#f4b942"),
    assimetria.ALTA: colors.HexColor("#e4624f"),
}
_TEXTO_SUAVE = colors.HexColor("#6f6f6a")
_LINHA_BASE = colors.HexColor("#dfe3e0")


def _faixa_do_lado_fraco(lado: str, d, e, sentido: str | None) -> str | None:
    """Faixa de risco se `lado` é o mais fraco (leva cor); None nos demais (cinza)."""
    if assimetria.lado_mais_fraco(d, e, sentido) != lado:
        return None
    return assimetria.faixa(assimetria.percentual(d, e))


def _desenho(serie: list[dict], sentido: str | None, formatar: Callable) -> Drawing:
    largura = _LARGURA_CARD
    desenho = Drawing(largura, _ALTURA_GRAFICO)
    valores = [v for p in serie for v in (p.get("D"), p.get("E")) if v is not None]
    maior = max(valores) if valores else 1
    if maior <= 0:
        maior = 1
    base_y = 0.95 * cm
    area_h = _ALTURA_GRAFICO - base_y - 0.5 * cm
    n = len(serie)
    largura_grupo = largura / n
    largura_barra = min(0.34 * cm, largura_grupo * 0.12)
    folga = 0.12 * cm

    desenho.add(Line(0, base_y, largura, base_y, strokeColor=_LINHA_BASE, strokeWidth=0.5))

    for i, ponto in enumerate(serie):
        centro = largura_grupo * (i + 0.5)
        x_barras = {"D": centro - folga / 2 - largura_barra, "E": centro + folga / 2}
        for lado in ("D", "E"):
            valor = ponto.get(lado)
            meio = x_barras[lado] + largura_barra / 2
            desenho.add(String(
                meio, base_y - 0.3 * cm, lado, fontName="Helvetica", fontSize=6.5, fillColor=_TEXTO_SUAVE, textAnchor="middle",
            ))
            if valor is None:
                continue
            altura = max(area_h * (valor / maior), 0.12 * cm)
            faixa = _faixa_do_lado_fraco(lado, ponto.get("D"), ponto.get("E"), sentido)
            cor = _BARRA_FAIXA[faixa] if faixa else _CINZA_BARRA
            raio = min(largura_barra / 2, altura / 2)
            desenho.add(Rect(x_barras[lado], base_y, largura_barra, altura, fillColor=cor, strokeColor=None, rx=raio, ry=raio))
            # Valor em negrito e na cor do risco só no lado fraco; nos demais, cinza discreto.
            desenho.add(String(
                meio, base_y + altura + 3, formatar(valor),
                fontName="Helvetica-Bold" if faixa else "Helvetica", fontSize=7,
                fillColor=pdf_base.CORES_FAIXA[faixa][2] if faixa else _TEXTO_SUAVE, textAnchor="middle",
            ))
        desenho.add(String(
            centro, 0.12 * cm, data_curta(ponto["data"]), fontName="Helvetica", fontSize=7,
            fillColor=colors.HexColor("#4a4a46"), textAnchor="middle",
        ))
    return desenho


def _tabela_valores(serie: list[dict], formatar: Callable) -> Table:
    """Tabela leve: cabeçalho claro, sem zebra, só uma linha fina entre as datas.
    Sem a unidade em cada célula: ela já está no título do gráfico."""

    def texto_valor(v) -> str:
        return formatar(v) if v is not None else ""

    cab = ParagraphStyle("CabLeve", parent=pdf_base.CELULA_CABECALHO_PEQUENA, textColor=pdf_base.COR_ESCURO)
    cel = ParagraphStyle("CelLeve", parent=pdf_base.CELULA, fontSize=8, leading=10)
    linhas = [[Paragraph("Data", cab), Paragraph("Direito", cab), Paragraph("Esquerdo", cab), Paragraph("Assimetria", cab)]]
    for ponto in serie:
        pct = assimetria.percentual(ponto.get("D"), ponto.get("E"))
        if pct is None:
            texto_pct = ""
        else:
            cor = pdf_base.CORES_FAIXA[assimetria.faixa(pct)][2].hexval()[2:]
            texto_pct = f'<font color="#{cor}"><b>{pdf_base.numero_br(pct, 1)}%</b></font>'
        linhas.append([
            Paragraph(data_curta(ponto["data"]), cel), Paragraph(texto_valor(ponto.get("D")), cel),
            Paragraph(texto_valor(ponto.get("E")), cel), Paragraph(texto_pct, cel),
        ])
    t = Table(linhas, colWidths=[_LARGURA_CARD * f for f in (0.23, 0.24, 0.25, 0.28)])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), pdf_base.COR_CARD),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, pdf_base.COR_GRADE),
        ("BOX", (0, 0), (-1, -1), 0.4, pdf_base.COR_GRADE),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    return t


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
    """Dois blocos por linha. Cada linha é uma Table própria (nunca cortada entre
    páginas), pra o conjunto fluir pelas páginas sem deixar grandes espaços vazios."""
    linhas = []
    for i in range(0, len(blocos), 2):
        par = blocos[i:i + 2]
        t = Table([[par[0], "", par[1] if len(par) > 1 else ""]], colWidths=[_LARGURA_CARD, _GAP, _LARGURA_CARD])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ]))
        linhas.append(t)
    return linhas


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


# --------------------------------------------------------------------------- escala visual analógica (dor)
_CORES_EVA = [
    "#ffffff", "#bfe6fb", "#2f9bf0", "#2fb34a", "#c8d82d", "#ffe600", "#ff8f00", "#e0262d", "#7a0f2e",
]
_POSICOES_EVA = [0, 0.12, 0.22, 0.42, 0.52, 0.60, 0.72, 0.85, 1.0]
_LEGENDA_EVA = ParagraphStyle(
    "LegendaEva", parent=pdf_base.ESTILO_NORMAL, fontSize=8.5, textColor=pdf_base.COR_ESCURO,
    fontName="Helvetica-Bold", alignment=1, spaceBefore=4, spaceAfter=0,
)


class EscalaEVA(Flowable):
    """Escala Visual Analógica (0 a 10): barra em degradê (branco, azul, verde,
    amarelo, vermelho, vinho), régua com 11 marcas e um triângulo preto apontando
    o valor da dor. Desenhada direto no canvas (gradiente e recorte arredondado)."""

    LARGURA = 12.4 * cm
    ALTURA = 1.35 * cm
    _MARGEM_LATERAL = 1.45 * cm

    def __init__(self, valor: float):
        super().__init__()
        self.valor = max(0.0, min(10.0, float(valor)))
        self.hAlign = "CENTER"

    def wrap(self, largura_disponivel, altura_disponivel):
        return self.LARGURA, self.ALTURA

    def draw(self):
        c = self.canv
        escuro = pdf_base.COR_ESCURO
        x0 = self._MARGEM_LATERAL
        larg = self.LARGURA - 2 * self._MARGEM_LATERAL
        y0, alt = 0.18 * cm, 0.3 * cm
        raio = alt / 2

        c.saveState()
        caminho = c.beginPath()
        caminho.roundRect(x0, y0, larg, alt, raio)
        c.clipPath(caminho, stroke=0, fill=0)
        c.linearGradient(x0, 0, x0 + larg, 0, [colors.HexColor(h) for h in _CORES_EVA], _POSICOES_EVA)
        c.restoreState()

        c.setStrokeColor(colors.HexColor("#c9c9c4"))
        c.setLineWidth(0.6)
        c.roundRect(x0, y0, larg, alt, raio, stroke=1, fill=0)

        topo_barra = y0 + alt
        c.setStrokeColor(escuro)
        c.setLineWidth(0.5)
        for i in range(11):
            x = x0 + larg * i / 10
            c.line(x, topo_barra + 0.07 * cm, x, topo_barra + 0.16 * cm)

        c.setFillColor(escuro)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(x0, topo_barra + 0.3 * cm, "0")
        c.drawCentredString(x0 + larg, topo_barra + 0.3 * cm, "10")

        c.setFont("Helvetica-Oblique", 6.5)
        c.setFillColor(pdf_base.COR_RODAPE)
        c.drawRightString(x0 - 0.2 * cm, y0 + 0.2 * cm, "Sem")
        c.drawRightString(x0 - 0.2 * cm, y0 - 0.03 * cm, "Dor")
        c.drawString(x0 + larg + 0.2 * cm, y0 + 0.2 * cm, "Máximo")
        c.drawString(x0 + larg + 0.2 * cm, y0 - 0.03 * cm, "de Dor")

        marcador_x = x0 + larg * self.valor / 10
        meia_base = 0.15 * cm
        c.setFillColor(colors.HexColor("#111111"))
        triangulo = c.beginPath()
        triangulo.moveTo(marcador_x - meia_base, topo_barra + 0.5 * cm)
        triangulo.lineTo(marcador_x + meia_base, topo_barra + 0.5 * cm)
        triangulo.lineTo(marcador_x, topo_barra + 0.1 * cm)
        triangulo.close()
        c.drawPath(triangulo, fill=1, stroke=0)


def escala_eva(valor: float, rotulo: str) -> list:
    """Legenda ("Em repouso", "Em atividade") + a escala com o marcador em `valor`."""
    return [Paragraph(rotulo, _LEGENDA_EVA), EscalaEVA(valor)]
