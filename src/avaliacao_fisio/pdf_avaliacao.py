"""PDF da avaliação, voltado ao PACIENTE (pasta entregue na clínica).

Visual do "Fechamento de Repasses" do Painel Feegow (ver `pdf_base.py`):
cabeçalho com a marca, cartão com os dados do paciente, tabelas limpas com
pílulas de assimetria, gráficos de evolução data a data e linhas de assinatura.

Regra de conteúdo: campo ou seção sem dado é OMITIDO (nada de "Não
preenchido" ou "-" num documento que vai pro paciente). Continua sendo o
formulário preenchido, sem texto interpretativo/diagnóstico (fase futura, só
com confirmação do Sergio).
"""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, inch
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

from avaliacao_fisio import assimetria, pdf_base, pdf_graficos
from avaliacao_fisio.pdf_base import (
    CELULA, CELULA_CABECALHO, CELULA_CABECALHO_CENTRO, CELULA_CENTRO, CELULA_OBS, LARGURA_UTIL, numero_br,
)

_TIPOS_BILATERAIS = ("bilateral_numero", "bilateral_sinal", "bilateral_score", "bilateral_tempo")
_TIPOS_FOTOGRAFIA = ("foto_unica", "video_upload")
_SECOES_FORA_DAS_TABELAS = ("dados_paciente", "classificacao_risco", "responsavel")
_FAIXA_DO_RISCO = {"Baixo": assimetria.BAIXA, "Moderado": assimetria.MEDIA, "Alto": assimetria.ALTA}
_LEGENDA_FOTO = ParagraphStyle("LegendaFoto", parent=pdf_base.ESTILO_NORMAL, fontSize=8.5, alignment=1, spaceBefore=2)
_OBS_FOTO = ParagraphStyle("ObsFoto", parent=CELULA_OBS, alignment=1)


def _esc(valor) -> str:
    return escape(str(valor))


def _vazio(valor) -> bool:
    return valor is None or valor == ""


def _texto_valor(valor) -> str:
    if _vazio(valor):
        return ""
    if hasattr(valor, "strftime"):
        return pdf_base.data_br(valor)
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if isinstance(valor, (int, float)):
        return numero_br(valor)
    return _esc(valor)


def _campo(dados: dict, secao_id: str, campo_id: str):
    for secao in dados["secoes"]:
        if secao["id"] == secao_id and secao["tipo"] == "secao":
            return secao["campos"].get(campo_id)
    return None


def _formatar_tempo(segundos: float) -> str:
    total = int(round(segundos))
    return f"{total // 60}'{total % 60:02d}\""


# --------------------------------------------------------------------------- cartão do paciente
def _partes(*itens: tuple[str, object]) -> str:
    """"<b>Rótulo:</b> valor" só dos itens com valor, separados por " · "."""
    return " · ".join(f"<b>{rotulo}:</b> {_texto_valor(valor)}" for rotulo, valor in itens if not _vazio(valor))


def _cartao_paciente(dados: dict) -> Table:
    c = lambda cid: _campo(dados, "dados_paciente", cid)  # noqa: E731
    idade = f"{c('idade')} anos" if not _vazio(c("idade")) else None
    peso = f"{numero_br(c('peso_kg'))} kg" if not _vazio(c("peso_kg")) else None
    altura = f"{numero_br(c('altura_m'), 2)} m" if not _vazio(c("altura_m")) else None
    medidas = " · ".join(x for x in (idade, peso, altura) if x)

    linhas: list[tuple] = [("pessoa", f"<b>Paciente:</b> {_esc(dados['paciente']['nome'])}" + (f" · {medidas}" if medidas else ""))]

    esporte = _partes(("Esporte", c("esporte_modalidade")), ("Membro dominante", c("membro_dominante")))
    if esporte:
        linhas.append(("esporte", esporte))
    lesao = _partes(("Lesão / diagnóstico", c("lesao_diagnostico")), ("Local", c("local_lesao")))
    if lesao:
        linhas.append(("lesao", lesao))
    datas_lesao = _partes(("Data da lesão", c("data_lesao")), ("Médico responsável", c("medico_responsavel")))
    if datas_lesao:
        linhas.append(("calendario", datas_lesao))

    data_av = pdf_base.data_br(dados.get("data_avaliacao"))
    linhas.append(("avaliacao", f"<b>Avaliação:</b> {data_av} · {_esc(dados['tipo_avaliacao'])}"))

    risco = _campo(dados, "classificacao_risco", "risco")
    if risco in _FAIXA_DO_RISCO:
        linhas.append(("escudo", "<b>Classificação de risco do paciente</b>", pdf_base.badge_faixa(risco, _FAIXA_DO_RISCO[risco])))
    return pdf_base.cartao_info(linhas)


# --------------------------------------------------------------------------- seções
def _celula_assimetria(d, e) -> object:
    pct = assimetria.percentual(d, e)
    if pct is None:
        return ""
    return pdf_base.badge_faixa(f"{numero_br(pct, 1)}%", assimetria.faixa(pct))


def _tabela_bilateral(secao: dict, campos) -> list:
    linhas = [[
        Paragraph("Teste", CELULA_CABECALHO), Paragraph("Direito", CELULA_CABECALHO_CENTRO),
        Paragraph("Esquerdo", CELULA_CABECALHO_CENTRO), Paragraph("Assimetria", CELULA_CABECALHO_CENTRO),
    ]]
    extra: list = []
    for campo in campos:
        valor = secao["campos"][campo.id]
        d, e = valor.get("D"), valor.get("E")
        if _vazio(d) and _vazio(e):
            continue
        if campo.tipo == "bilateral_tempo":
            num_d, num_e = valor.get("D_seg"), valor.get("E_seg")
        elif campo.tipo == "bilateral_numero":
            num_d, num_e = d, e
        else:
            num_d = num_e = None
        rotulo = f"{campo.rotulo} ({campo.unidade})" if campo.unidade else campo.rotulo
        linhas.append([
            Paragraph(_esc(rotulo), CELULA), Paragraph(_texto_valor(d), CELULA_CENTRO),
            Paragraph(_texto_valor(e), CELULA_CENTRO), _celula_assimetria(num_d, num_e),
        ])
        if campo.observacao and valor.get("obs"):
            linhas.append([Paragraph(f"Observação: {_esc(valor['obs'])}", CELULA_OBS), "", "", ""])
            extra.append(("SPAN", (0, len(linhas) - 1), (-1, len(linhas) - 1)))
    if len(linhas) == 1:
        return []
    return [pdf_base.tabela(linhas, (0.46, 0.17, 0.17, 0.20), extra=extra)]


def _tabela_chave_valor(pares: list[tuple[str, str]]) -> Table:
    dados = [[Paragraph(f"<b>{_esc(rotulo)}</b>", CELULA), Paragraph(valor, CELULA)] for rotulo, valor in pares]
    t = Table(dados, colWidths=[LARGURA_UTIL * 0.42, LARGURA_UTIL * 0.58])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), pdf_base.COR_CARD),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, pdf_base.COR_GRADE),
    ]))
    return t


def _imagem(foto_bytes: bytes, largura: float, altura: float):
    try:
        imagem = Image(io.BytesIO(foto_bytes), width=largura, height=altura, kind="proportional")
    except Exception:
        return None
    imagem.hAlign = "CENTER"
    return imagem


def _secao_fixa(secao: dict) -> list:
    campos = secao["definicao"].campos
    bilaterais = [c for c in campos if c.tipo in _TIPOS_BILATERAIS]
    fotografias = [c for c in campos if c.tipo in _TIPOS_FOTOGRAFIA]
    unicos = [c for c in campos if c not in bilaterais and c not in fotografias]

    elementos: list = _tabela_bilateral(secao, bilaterais) if bilaterais else []

    pares = []
    for campo in unicos:
        texto = _texto_valor(secao["campos"].get(campo.id))
        if texto:
            rotulo = f"{campo.rotulo} ({campo.unidade})" if campo.unidade else campo.rotulo
            pares.append((rotulo, texto))
    if pares:
        if elementos:
            elementos.append(Spacer(1, 0.2 * cm))
        elementos.append(_tabela_chave_valor(pares))

    for campo in fotografias:
        valor = secao["campos"].get(campo.id)
        # Vídeo nunca entra no PDF (fica só na sessão do app) — nada a imprimir.
        if campo.tipo == "foto_unica" and isinstance(valor, dict) and valor.get("foto_bytes"):
            imagem = _imagem(valor["foto_bytes"], 8 * cm, 6 * cm)
            if imagem is not None:
                bloco = [Spacer(1, 0.25 * cm), imagem]
                if valor.get("descricao"):
                    bloco.append(Paragraph(_esc(valor["descricao"]), _LEGENDA_FOTO))
                elementos.append(KeepTogether(bloco))
    return elementos


def _secao_repetivel(secao: dict) -> list:
    if secao.get("realizado") == "Não" or not secao["linhas"]:
        return []
    colunas = secao["definicao"].colunas
    linhas = [[Paragraph(_esc(rotulo), CELULA_CABECALHO) for _id, rotulo in colunas]]
    for linha in secao["linhas"]:
        linhas.append([Paragraph(_texto_valor(linha.get(col_id)), CELULA) for col_id, _r in colunas])
    return [pdf_base.tabela(linhas, tuple(1 / len(colunas) for _ in colunas))]


def _secao_dor(secao: dict, titulo: list) -> list:
    """Devolve a seção COM o título (`titulo`): o título entra no mesmo bloco da escala
    pra nunca ficar sozinho no fim de uma página."""
    repouso, atividade = secao["escala_repouso"], secao["escala_atividade"]
    locais = secao["locais"]
    if not locais and not repouso and not atividade:
        return []
    elementos: list = []
    # Cartão + escala EVA num bloco só (com o título da seção, que fica junto por
    # `keepWithNext`): a seção Dor não se parte entre duas páginas.
    bloco_escala: list = []
    if repouso is not None or atividade is not None:
        bloco_escala.append(pdf_base.cartao_info([(
            "ponto",
            f"<b>Escala de dor em repouso:</b> {repouso or 0} / 10 · <b>em atividade:</b> {atividade or 0} / 10",
        )]))
    eva: list = []
    for rotulo, valor in (("Em repouso", repouso), ("Em atividade", atividade)):
        if valor is not None:
            eva += pdf_graficos.escala_eva(valor, rotulo)
    if eva:
        titulo_eva = ParagraphStyle(
            "TituloEva", parent=CELULA, fontSize=10.5, leading=13, alignment=1, fontName="Helvetica-Bold",
            textColor=pdf_base.COR_ESCURO, spaceBefore=10, spaceAfter=2,
        )
        bloco_escala += [Paragraph("ESCALA VISUAL ANALÓGICA (EVA)", titulo_eva)] + eva
    if bloco_escala:
        elementos.append(KeepTogether(titulo + bloco_escala))
    else:
        elementos += titulo
    if locais:
        linhas = [[Paragraph(t, CELULA_CABECALHO) for t in ("Região", "Lado", "Intensidade")]]
        for local in locais:
            intensidade = local.get("intensidade")
            linhas.append([
                Paragraph(_texto_valor(local.get("regiao")), CELULA), Paragraph(_texto_valor(local.get("lado")), CELULA),
                Paragraph(f"{intensidade} / 10" if intensidade is not None else "", CELULA),
            ])
        elementos += [Spacer(1, 0.2 * cm), pdf_base.tabela(linhas, (0.5, 0.25, 0.25))]
    return elementos


def _secao_fotos(secao: dict) -> list:
    celulas = []
    for foto in secao["fotos"]:
        imagem = _imagem(foto["foto_bytes"], 7.4 * cm, 5.6 * cm)
        if imagem is None:
            continue
        bloco: list = [imagem]
        if foto.get("descricao"):
            bloco.append(Paragraph(_esc(foto["descricao"]), _LEGENDA_FOTO))
        if foto.get("observacao"):
            bloco.append(Paragraph(_esc(foto["observacao"]), _OBS_FOTO))
        celulas.append(bloco)
    if not celulas:
        return []
    metade = LARGURA_UTIL / 2
    linhas = [[par[0], par[1] if len(par) > 1 else ""] for par in (celulas[i:i + 2] for i in range(0, len(celulas), 2))]
    t = Table(linhas, colWidths=[metade, metade])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [t]


# --------------------------------------------------------------------------- evolução
def _blocos_evolucao(dados: dict, series: dict) -> list:
    blocos = []
    for secao in dados["secoes"]:
        if secao["tipo"] != "secao":
            continue
        for campo in secao["definicao"].campos:
            serie = series.get((secao["id"], campo.id), [])
            if campo.tipo not in ("bilateral_numero", "bilateral_tempo") or len(serie) < 2:
                continue
            tempo = campo.tipo == "bilateral_tempo"
            blocos.append(pdf_graficos.bloco(
                campo.rotulo, None if tempo else campo.unidade, serie, campo.sentido,
                formatar=_formatar_tempo if tempo else None,
            ))
    return blocos


# --------------------------------------------------------------------------- documento
def _assinaturas(dados: dict) -> list:
    nome = ""
    crefito = ""
    for secao in dados["secoes"]:
        if secao["id"] == "responsavel":
            nome = secao["campos"].get("fisioterapeuta_responsavel") or ""
            crefito = secao["campos"].get("crefito") or ""
    rotulo_prof = "Assinatura do profissional"
    if nome:
        rotulo_prof = f"{_esc(nome)}" + (f"<br/>CREFITO {_esc(crefito)}" if crefito else "")
    estilo = ParagraphStyle("Assinatura", parent=CELULA, alignment=1, fontSize=9, leading=12)
    t = Table(
        [["_" * 38, "_" * 38], [Paragraph(rotulo_prof, estilo), Paragraph("Assinatura da clínica", estilo)]],
        colWidths=[LARGURA_UTIL / 2, LARGURA_UTIL / 2],
    )
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("FONTSIZE", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 1), (-1, 1), 4)]))
    return [KeepTogether([Spacer(1, 1.6 * cm), t])]


def _cabecalho_demais_paginas(nome_paciente: str, protocolo: str):
    def desenhar(canvas, _doc) -> None:
        largura, altura = A4
        topo = altura - 1.3 * cm
        canvas.saveState()
        if pdf_base._LOGO_SIMBOLO.exists():
            try:
                canvas.drawImage(
                    str(pdf_base._LOGO_SIMBOLO), 1 * inch, topo - 0.9 * cm, width=0.55 * cm, height=0.9 * cm,
                    mask="auto", preserveAspectRatio=True,
                )
            except Exception:
                pass
        canvas.setFillColor(pdf_base.COR_ESCURO)
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(1 * inch + 0.8 * cm, topo - 0.55 * cm, "SPORT LABS")
        canvas.setFillColor(pdf_base.COR_RODAPE)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(largura - 1 * inch, topo - 0.55 * cm, f"{nome_paciente} · {protocolo}")
        canvas.setStrokeColor(pdf_base.COR_GRADE)
        canvas.setLineWidth(0.6)
        canvas.line(1 * inch, topo - 1.1 * cm, largura - 1 * inch, topo - 1.1 * cm)
        canvas.restoreState()

    return desenhar


def gerar(dados: dict, series: dict | None = None) -> bytes:
    """`dados`: dict de `wizard.coletar_respostas()`. `series`: evolução
    data a data de `historico.series_do_paciente()` (None = sem histórico)."""
    buffer = io.BytesIO()
    margem = 1 * inch
    doc = BaseDocTemplate(
        buffer, pagesize=A4, leftMargin=margem, rightMargin=margem, topMargin=1.3 * cm, bottomMargin=1.6 * cm,
        title=f"Avaliação - {dados['paciente']['nome']}", author="Sport Labs",
    )
    largura_frame = A4[0] - 2 * margem
    base_y = 1.6 * cm
    frame_primeira = Frame(
        margem, base_y, largura_frame, A4[1] - 1.3 * cm - base_y, id="primeira",
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    frame_demais = Frame(
        margem, base_y, largura_frame, A4[1] - 1.3 * cm - 1.6 * cm - base_y, id="demais",
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    doc.addPageTemplates([
        PageTemplate(id="primeira", frames=[frame_primeira], autoNextPageTemplate="demais"),
        PageTemplate(id="demais", frames=[frame_demais], onPage=_cabecalho_demais_paginas(dados["paciente"]["nome"], dados["protocolo_nome"])),
    ])

    elementos: list = pdf_base.cabecalho("Avaliação Cinética Funcional", f"{dados['protocolo_nome']} · {dados['tipo_avaliacao']}")
    elementos.append(_cartao_paciente(dados))

    for secao in dados["secoes"]:
        if secao["id"] in _SECOES_FORA_DAS_TABELAS:
            continue
        if secao["tipo"] == "secao":
            conteudo = _secao_fixa(secao)
        elif secao["tipo"] == "repetivel":
            conteudo = _secao_repetivel(secao)
        elif secao["tipo"] == "dor":
            elementos += _secao_dor(secao, pdf_base.titulo_secao(secao["titulo"]))
            continue
        else:
            conteudo = _secao_fotos(secao)
        if conteudo:
            elementos += pdf_base.titulo_secao(secao["titulo"]) + conteudo

    blocos = _blocos_evolucao(dados, series or {})
    if blocos:
        elementos += pdf_base.titulo_secao("Evolução entre avaliações") + pdf_graficos.grade(blocos) + pdf_graficos.legenda()

    elementos += _assinaturas(dados)

    doc.build(elementos, canvasmaker=pdf_base.CanvasNumerado)
    return buffer.getvalue()
