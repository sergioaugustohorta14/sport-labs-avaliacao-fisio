"""Geração do PDF de Avaliação Fisioterapêutica a partir do dict produzido
por `wizard.coletar_respostas()`.

Reaproveita o mesmo padrão técnico/visual do Painel Feegow
(`feegow_analytics.reports.pdf_repasses`): reportlab puro-Python (sem
wkhtmltopdf/weasyprint — funciona sem configuração extra no Streamlit
Community Cloud), faixa escura `#36363a`/`#322f33` com logo centralizado,
células `Paragraph` pra quebrar texto longo dentro da tabela (string pura
numa `Table` do reportlab não quebra linha sozinha, só transborda).

v1 = formulário preenchido (dados brutos em tabela, sem texto
interpretativo/diagnóstico — essa camada narrativa é uma fase futura, só
a iniciar com confirmação do Sergio).
"""
from __future__ import annotations

import io
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "logo.png"

_ESTILOS = getSampleStyleSheet()
_TITULO = ParagraphStyle("TituloAvaliacao", parent=_ESTILOS["Title"], fontSize=15, spaceAfter=2)
_SUBTITULO = ParagraphStyle("SubtituloAvaliacao", parent=_ESTILOS["Normal"], fontSize=9, textColor=colors.grey)
_TITULO_SECAO = ParagraphStyle("TituloSecao", parent=_ESTILOS["Heading2"], fontSize=11, spaceBefore=10, spaceAfter=4)

_COR_CABECALHO = colors.HexColor("#322f33")

_CELULA = ParagraphStyle("Celula", parent=_ESTILOS["Normal"], fontSize=8, leading=10)
_CELULA_CABECALHO = ParagraphStyle(
    "CelulaCabecalho", parent=_ESTILOS["Normal"], fontSize=8, leading=10,
    textColor=colors.white, fontName="Helvetica-Bold",
)

_LARGURA_UTIL = A4[0] - 2 * inch


def _cel(valor) -> Paragraph:
    if valor is None or valor == "":
        texto = "—"
    elif hasattr(valor, "strftime"):
        texto = valor.strftime("%d/%m/%Y")
    elif isinstance(valor, float):
        texto = f"{valor:g}".replace(".", ",")
    else:
        texto = str(valor)
    return Paragraph(texto, _CELULA)


def _cel_cab(texto: str) -> Paragraph:
    return Paragraph(texto, _CELULA_CABECALHO)


def _cabecalho_faixa(titulo: str, subtitulo: str) -> list:
    elementos: list = []
    conteudo = []
    if _LOGO_PATH.exists():
        try:
            conteudo.append(Image(str(_LOGO_PATH), width=2.4 * cm, height=1.2 * cm, kind="proportional"))
        except Exception:
            conteudo = []
    faixa = Table([conteudo or [""]], colWidths=[_LARGURA_UTIL], rowHeights=[2.2 * cm])
    faixa.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _COR_CABECALHO),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elementos.append(faixa)
    elementos.append(Spacer(1, 0.6 * cm))
    elementos.append(Paragraph(titulo, _TITULO))
    elementos.append(Paragraph(subtitulo, _SUBTITULO))
    elementos.append(Spacer(1, 0.4 * cm))
    return elementos


def _tabela_secao_fixa(secao_saida: dict) -> list:
    definicao = secao_saida["definicao"]
    campos_bilaterais = [c for c in definicao.campos if c.tipo in ("bilateral_numero", "bilateral_sinal", "bilateral_score")]
    campos_unicos = [c for c in definicao.campos if c not in campos_bilaterais]
    elementos: list = []

    if campos_bilaterais:
        linhas = [[_cel_cab("Teste"), _cel_cab("Direito"), _cel_cab("Esquerdo"), _cel_cab("Unidade")]]
        for campo in campos_bilaterais:
            valor = secao_saida["campos"][campo.id]
            linhas.append([_cel(campo.rotulo), _cel(valor.get("D")), _cel(valor.get("E")), _cel(campo.unidade)])
            if campo.observacao and valor.get("obs"):
                linhas.append([_cel("　· Observação"), _cel(valor["obs"]), "", ""])
        tabela = Table(linhas, repeatRows=1, colWidths=[6.5 * cm, 3.2 * cm, 3.2 * cm, 3.1 * cm])
        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _COR_CABECALHO),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elementos.append(tabela)

    if campos_unicos:
        linhas = []
        for campo in campos_unicos:
            rotulo = f"{campo.rotulo} ({campo.unidade})" if campo.unidade else campo.rotulo
            linhas.append([_cel(rotulo), _cel(secao_saida["campos"][campo.id])])
        tabela = Table(linhas, colWidths=[8 * cm, _LARGURA_UTIL - 8 * cm])
        tabela.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        if elementos:
            elementos.append(Spacer(1, 0.2 * cm))
        elementos.append(tabela)

    return elementos


def _tabela_secao_repetivel(secao_saida: dict) -> list:
    definicao = secao_saida["definicao"]
    if secao_saida.get("realizado") == "Não":
        return [Paragraph("Não realizado.", _CELULA)]
    if not secao_saida["linhas"]:
        return [Paragraph("Nenhuma linha preenchida.", _CELULA)]

    cabecalho = [_cel_cab(rotulo) for _id, rotulo in definicao.colunas]
    linhas = [cabecalho]
    for linha in secao_saida["linhas"]:
        linhas.append([_cel(linha.get(col_id)) for col_id, _rotulo in definicao.colunas])

    largura_col = _LARGURA_UTIL / len(definicao.colunas)
    tabela = Table(linhas, repeatRows=1, colWidths=[largura_col] * len(definicao.colunas))
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _COR_CABECALHO),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return [tabela]


def _elementos_dor(secao_saida: dict) -> list:
    repouso = secao_saida["escala_repouso"]
    atividade = secao_saida["escala_atividade"]
    elementos: list = [
        Paragraph(
            f"<b>Escala em repouso:</b> {repouso if repouso is not None else '—'} / 10"
            f"　　<b>Escala em atividade:</b> {atividade if atividade is not None else '—'} / 10",
            _ESTILOS["Normal"],
        ),
        Spacer(1, 0.2 * cm),
    ]
    locais = secao_saida["locais"]
    if locais:
        linhas = [[_cel_cab("Região"), _cel_cab("Lado"), _cel_cab("Intensidade")]]
        for local in locais:
            intensidade = local.get("intensidade")
            linhas.append([
                _cel(local.get("regiao")),
                _cel(local.get("lado")),
                _cel(f"{intensidade} / 10" if intensidade is not None else None),
            ])
        tabela = Table(linhas, colWidths=[7 * cm, 5 * cm, 4 * cm])
        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _COR_CABECALHO),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ]))
        elementos.append(tabela)
    else:
        elementos.append(Paragraph("Sem locais de dor registrados.", _CELULA))
    return elementos


def _elementos_fotos(secao_saida: dict) -> list:
    fotos = secao_saida["fotos"]
    if not fotos:
        return [Paragraph("Nenhuma foto registrada.", _CELULA)]
    elementos: list = []
    for foto in fotos:
        try:
            imagem = Image(io.BytesIO(foto["foto_bytes"]), width=8 * cm, height=6 * cm, kind="proportional")
        except Exception:
            continue
        imagem.hAlign = "CENTER"
        elementos.append(imagem)
        if foto.get("descricao"):
            legenda = ParagraphStyle("LegendaFoto", parent=_ESTILOS["Normal"], fontSize=9, alignment=1, spaceBefore=2)
            elementos.append(Paragraph(foto["descricao"], legenda))
        elementos.append(Spacer(1, 0.4 * cm))
    return elementos


def _valor_campo(dados: dict, secao_id: str, campo_id: str):
    for secao_saida in dados["secoes"]:
        if secao_saida["id"] == secao_id and secao_saida["tipo"] == "secao":
            return secao_saida["campos"].get(campo_id)
    return None


def gerar(dados: dict) -> bytes:
    """`dados` é o dict devolvido por `wizard.coletar_respostas()`."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)

    nome_paciente = _valor_campo(dados, "dados_paciente", "nome_completo") or "—"
    data_avaliacao = dados.get("data_avaliacao")
    data_texto = data_avaliacao.strftime("%d/%m/%Y") if hasattr(data_avaliacao, "strftime") else str(data_avaliacao)

    titulo = f"Avaliação Funcional — {dados['protocolo_nome']}"
    subtitulo = f"Paciente: {nome_paciente}　·　Data da avaliação: {data_texto}　·　{dados['tipo_avaliacao']}"

    elementos = _cabecalho_faixa(titulo, subtitulo)

    for secao_saida in dados["secoes"]:
        elementos.append(Paragraph(secao_saida["titulo"], _TITULO_SECAO))
        if secao_saida["tipo"] == "secao":
            elementos.extend(_tabela_secao_fixa(secao_saida))
        elif secao_saida["tipo"] == "repetivel":
            elementos.extend(_tabela_secao_repetivel(secao_saida))
        elif secao_saida["tipo"] == "dor":
            elementos.extend(_elementos_dor(secao_saida))
        elif secao_saida["tipo"] == "fotos":
            elementos.extend(_elementos_fotos(secao_saida))
        elementos.append(Spacer(1, 0.3 * cm))

    elementos.append(Spacer(1, 1.5 * cm))
    linha_assinatura = Table([["_" * 38], ["Assinatura do Fisioterapeuta"]], colWidths=[_LARGURA_UTIL])
    linha_assinatura.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 1), (0, 1), 4),
    ]))
    elementos.append(linha_assinatura)

    doc.build(elementos)
    return buffer.getvalue()
