"""Componentes visuais do PDF — adaptados do padrão aprovado pela diretoria
no "Fechamento de Repasses" do Painel Feegow (`pdf_repasses.py`, 20 a
22/10/2026). Cópia adaptada, não importada: os dois projetos são
repositórios independentes.

O PDF usa a paleta de IMPRESSÃO (fundo branco, escuro `#322f33`, cartões
`#f4f4f1`), não o tema preto/dourado do app na tela.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import HRFlowable, Image, Paragraph, Spacer, Table, TableStyle

from avaliacao_fisio import assimetria

_ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
_LOGO_SIMBOLO = _ASSETS_DIR / "sportlabs-simbolo.png"

# O servidor (Streamlit Cloud) roda em UTC: sem fuso explícito o "Gerado em"
# sairia 3h à frente do horário de Brasília.
FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")

LARGURA_UTIL = A4[0] - 2 * inch

COR_ESCURO = colors.HexColor("#322f33")
COR_CARD = colors.HexColor("#f4f4f1")
COR_ZEBRA = colors.HexColor("#f7f7f5")
COR_GRADE = colors.HexColor("#dddddd")
COR_RODAPE = colors.HexColor("#8a8a85")
COR_NEUTRO_BARRA = colors.HexColor("#9fb0aa")

# Por faixa de assimetria: (cor da barra/texto forte, fundo da pílula, texto da pílula).
CORES_FAIXA = {
    assimetria.BAIXA: (colors.HexColor("#1fa83c"), colors.HexColor("#d9f0de"), colors.HexColor("#1a7a3c")),
    assimetria.MEDIA: (colors.HexColor("#f2a900"), colors.HexColor("#fdecc8"), colors.HexColor("#8a5a00")),
    assimetria.ALTA: (colors.HexColor("#d63a1f"), colors.HexColor("#fbdad4"), colors.HexColor("#a82a14")),
}

_ESTILOS = getSampleStyleSheet()
ESTILO_NORMAL = _ESTILOS["Normal"]
CELULA = ParagraphStyle("Celula", parent=_ESTILOS["Normal"], fontSize=8.5, leading=11)
CELULA_DIREITA = ParagraphStyle("CelulaDireita", parent=CELULA, alignment=2)
CELULA_CENTRO = ParagraphStyle("CelulaCentro", parent=CELULA, alignment=1)
CELULA_CABECALHO = ParagraphStyle(
    "CelulaCabecalho", parent=CELULA, textColor=colors.white, fontName="Helvetica-Bold",
)
CELULA_CABECALHO_CENTRO = ParagraphStyle("CelulaCabecalhoCentro", parent=CELULA_CABECALHO, alignment=1)
CELULA_CABECALHO_PEQUENA = ParagraphStyle("CelulaCabecalhoPequena", parent=CELULA_CABECALHO, fontSize=7.5)
CELULA_OBS = ParagraphStyle("CelulaObs", parent=CELULA, fontSize=8, textColor=COR_RODAPE)
_TITULO = ParagraphStyle(
    "TituloModerno", parent=_ESTILOS["Title"], fontSize=17, leading=21, textColor=COR_ESCURO, alignment=0, spaceAfter=0,
)
_SUBTITULO = ParagraphStyle("Subtitulo", parent=_ESTILOS["Normal"], fontSize=9, textColor=COR_RODAPE)
_GERADO_EM = ParagraphStyle("GeradoEm", parent=_ESTILOS["Normal"], fontSize=8, textColor=COR_RODAPE, alignment=2)
_MARCA = ParagraphStyle("Marca", parent=_ESTILOS["Normal"], fontSize=12, textColor=COR_ESCURO, fontName="Helvetica-Bold")
_INFO_CARD = ParagraphStyle("InfoCard", parent=_ESTILOS["Normal"], fontSize=9, leading=12)
TITULO_SECAO = ParagraphStyle(
    "TituloSecao", parent=_ESTILOS["Normal"], fontSize=11.5, leading=14, textColor=COR_ESCURO,
    fontName="Helvetica-Bold", spaceBefore=22, spaceAfter=9, keepWithNext=1,
)

_TAM_ICONE = 0.42 * cm


def data_br(d) -> str:
    return d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else str(d)


def numero_br(valor, casas: int | None = None) -> str:
    """12.5 -> '12,5'; inteiro sai sem casa decimal."""
    if casas is not None:
        texto = f"{valor:.{casas}f}"
    else:
        texto = f"{valor:g}"
    return texto.replace(".", ",")


_ICONES_DIR = _ASSETS_DIR / "icones"
# Ícones enviados pelo Sergio (27/10/2026), já na cor do PDF e com fundo transparente.
_ICONES_PNG = {"esporte": "esporte.png", "lesao": "lesao.png", "avaliacao": "avaliacao.png"}


def icone(tipo: str):
    arquivo = _ICONES_PNG.get(tipo)
    if arquivo and (_ICONES_DIR / arquivo).exists():
        try:
            return Image(str(_ICONES_DIR / arquivo), width=_TAM_ICONE * 1.3, height=_TAM_ICONE * 1.3, kind="proportional")
        except Exception:
            pass
    cor = COR_ESCURO
    t = _TAM_ICONE
    d = Drawing(t, t)
    if tipo == "pessoa":
        d.add(Circle(t * 0.5, t * 0.68, t * 0.22, fillColor=cor, strokeColor=None))
        d.add(Rect(t * 0.14, 0, t * 0.72, t * 0.42, rx=t * 0.2, ry=t * 0.2, fillColor=cor, strokeColor=None))
    elif tipo == "cartao":
        d.add(Rect(0, t * 0.14, t, t * 0.72, rx=t * 0.12, ry=t * 0.12, fillColor=None, strokeColor=cor, strokeWidth=1.1))
        d.add(Line(t * 0.16, t * 0.36, t * 0.84, t * 0.36, strokeColor=cor, strokeWidth=1.1))
        d.add(Line(t * 0.16, t * 0.24, t * 0.55, t * 0.24, strokeColor=cor, strokeWidth=1.1))
    elif tipo == "calendario":
        d.add(Rect(0, 0, t, t * 0.8, rx=t * 0.08, ry=t * 0.08, fillColor=None, strokeColor=cor, strokeWidth=1.1))
        d.add(Rect(0, t * 0.58, t, t * 0.22, rx=t * 0.08, ry=t * 0.08, fillColor=cor, strokeColor=None))
    elif tipo == "escudo":
        d.add(Rect(t * 0.12, t * 0.05, t * 0.76, t * 0.9, rx=t * 0.3, ry=t * 0.3, fillColor=None, strokeColor=cor, strokeWidth=1.1))
        d.add(Line(t * 0.3, t * 0.5, t * 0.45, t * 0.33, strokeColor=cor, strokeWidth=1.3))
        d.add(Line(t * 0.45, t * 0.33, t * 0.72, t * 0.68, strokeColor=cor, strokeWidth=1.3))
    elif tipo == "ponto":
        d.add(Circle(t * 0.5, t * 0.5, t * 0.3, fillColor=cor, strokeColor=None))
    return d


def badge(texto: str, cor_fundo, cor_texto) -> Table:
    t = Table([[texto]])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor_fundo),
        ("TEXTCOLOR", (0, 0), (-1, -1), cor_texto),
        ("ROUNDEDCORNERS", [5, 5, 5, 5]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def badge_faixa(texto: str, faixa: str) -> Table:
    _barra, fundo, cor_texto = CORES_FAIXA[faixa]
    return badge(texto, fundo, cor_texto)


class CanvasNumerado(Canvas):
    """Rodapé "Página X de Y": o total só é conhecido depois de montar o
    documento inteiro, então cada página fica em espera e o rodapé é
    desenhado no `save()` final."""

    def __init__(self, *args, **kwargs):
        Canvas.__init__(self, *args, **kwargs)
        self._paginas_em_espera = []

    def showPage(self):
        self._paginas_em_espera.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_paginas = len(self._paginas_em_espera)
        for estado in self._paginas_em_espera:
            self.__dict__.update(estado)
            self._desenhar_rodape(total_paginas)
            Canvas.showPage(self)
        Canvas.save(self)

    def _desenhar_rodape(self, total_paginas: int) -> None:
        largura, _ = A4
        self.saveState()
        self.setStrokeColor(COR_GRADE)
        self.setLineWidth(0.5)
        self.line(1 * inch, 1.1 * cm, largura - 1 * inch, 1.1 * cm)
        self.setFont("Helvetica", 8)
        self.setFillColor(COR_RODAPE)
        self.drawString(1 * inch, 0.6 * cm, "Sport Labs")
        self.drawRightString(largura - 1 * inch, 0.6 * cm, f"Página {self._pageNumber} de {total_paginas}")
        self.restoreState()


def cabecalho(titulo: str, subtitulo: str | None = None) -> list:
    """Logo + marca à esquerda, "Gerado em" à direita, régua fina, título
    grande e barra de destaque."""
    agora = dt.datetime.now(FUSO_BRASILIA)
    gerado_em = f"Gerado em {data_br(agora.date())} às {agora.strftime('%H:%M')}"

    celula_marca: Table | Paragraph
    if _LOGO_SIMBOLO.exists():
        try:
            logo = Image(str(_LOGO_SIMBOLO), width=1.15 * cm, height=1.87 * cm, kind="proportional")
            celula_marca = Table([[logo, Paragraph("SPORT LABS", _MARCA)]], colWidths=[1.6 * cm, 8.4 * cm])
            celula_marca.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (1, 0), (1, -1), 0),
            ]))
        except Exception:
            celula_marca = Paragraph("SPORT LABS", _MARCA)
    else:
        celula_marca = Paragraph("SPORT LABS", _MARCA)

    linha_topo = Table([[celula_marca, Paragraph(gerado_em, _GERADO_EM)]], colWidths=[10 * cm, LARGURA_UTIL - 10 * cm])
    linha_topo.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    elementos: list = [
        linha_topo,
        Spacer(1, 0.3 * cm),
        HRFlowable(width="100%", thickness=0.6, color=COR_GRADE),
        Spacer(1, 0.5 * cm),
        Paragraph(titulo, _TITULO),
    ]
    if subtitulo:
        elementos += [Spacer(1, 0.1 * cm), Paragraph(subtitulo, _SUBTITULO)]
    elementos += [Spacer(1, 0.15 * cm), HRFlowable(width="100%", thickness=2.2, color=COR_ESCURO), Spacer(1, 0.5 * cm)]
    return elementos


def cartao_info(linhas: list[tuple]) -> Table:
    """Cartão cinza claro de cantos arredondados: uma linha por item,
    `(ícone, texto)` ou `(ícone, texto, pílula)`."""
    dados = []
    for item in linhas:
        tipo, texto = item[0], item[1]
        pilula = item[2] if len(item) > 2 else None
        paragrafo = Paragraph(texto, _INFO_CARD)
        if pilula is not None:
            interno = Table([[paragrafo, pilula]], colWidths=[LARGURA_UTIL - 1.1 * cm - 4.2 * cm, 3.2 * cm])
            interno.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            paragrafo = interno
        dados.append([icone(tipo), paragrafo])
    t = Table(dados, colWidths=[1.1 * cm, LARGURA_UTIL - 1.1 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COR_CARD),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (0, -1), 14),
        ("LEFTPADDING", (1, 0), (1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def titulo_secao(texto: str) -> list:
    # keepWithNext: o título nunca fica sozinho no fim de uma página.
    return [Paragraph(texto, TITULO_SECAO)]


def tabela(
    linhas: list[list], proporcoes: tuple[float, ...], extra: list | None = None, largura: float = LARGURA_UTIL,
) -> Table:
    """Tabela padrão: cabeçalho escuro (primeira linha), cantos arredondados,
    grade clara e zebra. `proporcoes` = fração de `largura` por coluna."""
    t = Table(linhas, repeatRows=1, colWidths=[largura * f for f in proporcoes])
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), COR_ESCURO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COR_ZEBRA]),
        ("GRID", (0, 0), (-1, -1), 0.25, COR_GRADE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]
    t.setStyle(TableStyle(estilo + (extra or [])))
    return t
