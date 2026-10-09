"""Motor do wizard: desenha uma seção por tela, navega com os botões
Voltar/Próximo.

Importante: as respostas NÃO ficam só na `key` do widget. O Streamlit
limpa (`prune`) o valor de um widget do `session_state` sempre que esse
widget não é desenhado numa execução — como aqui cada tela desenha só a
seção atual, as respostas das seções anteriores seriam apagadas assim que
o usuário avançasse. Por isso cada widget é lido pelo valor de RETORNO da
própria chamada (`valor = st.text_input(...)`) e gravado manualmente em
`st.session_state["respostas"]` (um dict comum, não ligado a nenhum
widget, que o Streamlit não mexe sozinho) — essa é a fonte da verdade,
inclusive pra mostrar o valor já digitado quando o usuário volta uma
seção.

`coletar_respostas()` lê esse dict de volta num formato limpo, desacoplado
do Streamlit, que `pdf_avaliacao.gerar()` consome.
"""
from __future__ import annotations

import datetime as dt
import time

import streamlit as st
import streamlit.components.v1 as components

from avaliacao_fisio import estilo, pdf_avaliacao
from avaliacao_fisio.protocolos import (
    PROTOCOLO_MMII,
    PROTOCOLO_MMSS,
    PROTOCOLOS,
    Campo,
    Protocolo,
    Secao,
    SecaoDor,
    SecaoFotos,
    SecaoRepetivel,
)


def _chave(*partes: str) -> str:
    return "__".join(partes)


def _rolar_para_topo(identificador: str) -> None:
    """O Streamlit não reseta o scroll sozinho entre reruns — ao navegar
    pra uma seção mais curta que a anterior (com a página rolada pra
    baixo), o título/indicador de progresso ficavam escondidos acima do
    topo da tela (achado real, 10/10/2026). `st.markdown`/`unsafe_allow_html`
    não executa `<script>`, por isso usa `components.html` (roda num
    iframe de verdade) e acessa o DOM real do app via `window.parent`.

    `identificador` (a etapa atual) precisa variar a cada chamada — com o
    mesmo HTML de sempre, o Streamlit não recarrega o iframe entre reruns
    e o script só rodava na primeiríssima vez (achado real: o scroll
    nunca resetava depois do primeiro clique)."""
    components.html(
        f"""
        <!-- etapa={identificador} -->
        <script>
            const doc = window.parent.document;
            function resetarScroll() {{
                const principal = doc.querySelector('section[data-testid="stMain"]');
                if (principal) {{ principal.scrollTop = 0; }}
            }}
            resetarScroll();
            [0, 50, 100, 200, 350, 500].forEach(ms => setTimeout(resetarScroll, ms));
        </script>
        """,
        height=0,
    )


def _obter(chave: str):
    return st.session_state.get("respostas", {}).get(chave)


def _guardar(chave: str, valor) -> None:
    st.session_state.setdefault("respostas", {})[chave] = valor


def _indice(opcoes: list[str], atual) -> int | None:
    return opcoes.index(atual) if atual in opcoes else None


# ---------------------------------------------------------------------------
# Renderização dos campos
# ---------------------------------------------------------------------------

def renderizar_secao(secao: Secao) -> None:
    st.markdown(f"## {secao.titulo}")
    for campo in secao.campos:
        _renderizar_campo(secao.id, campo)
        st.divider()


def _renderizar_campo(secao_id: str, campo: Campo) -> None:
    tipo = campo.tipo
    chave = _chave(secao_id, campo.id)

    if tipo == "unico_texto":
        valor = st.text_input(campo.rotulo, value=_obter(chave) or "", key=f"w__{chave}")
        _guardar(chave, valor)
    elif tipo == "unico_numero":
        rotulo = f"{campo.rotulo} ({campo.unidade})" if campo.unidade else campo.rotulo
        valor = st.number_input(rotulo, value=_obter(chave), step=0.1, format="%.1f", key=f"w__{chave}")
        _guardar(chave, valor)
    elif tipo == "data":
        valor = st.date_input(campo.rotulo, value=_obter(chave), key=f"w__{chave}", format="DD/MM/YYYY")
        _guardar(chave, valor)
    elif tipo == "lado_unico":
        opcoes = ["Direito", "Esquerdo"]
        valor = st.radio(campo.rotulo, options=opcoes, index=_indice(opcoes, _obter(chave)), key=f"w__{chave}", horizontal=True)
        _guardar(chave, valor)
    elif tipo == "opcoes":
        opcoes = list(campo.opcoes or ())
        valor = st.radio(campo.rotulo, options=opcoes, index=_indice(opcoes, _obter(chave)), key=f"w__{chave}", horizontal=True)
        _guardar(chave, valor)
    elif tipo in ("bilateral_numero", "bilateral_sinal", "bilateral_score"):
        rotulo = f"{campo.rotulo} ({campo.unidade})" if campo.unidade else campo.rotulo
        st.markdown(f"**{rotulo}**")
        col_d, col_e = st.columns(2)
        chave_d, chave_e = _chave(secao_id, campo.id, "D"), _chave(secao_id, campo.id, "E")

        if tipo == "bilateral_numero":
            with col_d:
                valor_d = st.number_input("Direito", value=_obter(chave_d), step=0.1, format="%.1f", key=f"w__{chave_d}")
            with col_e:
                valor_e = st.number_input("Esquerdo", value=_obter(chave_e), step=0.1, format="%.1f", key=f"w__{chave_e}")
        elif tipo == "bilateral_sinal":
            opcoes = ["+", "-"]
            with col_d:
                valor_d = st.radio("Direito", options=opcoes, index=_indice(opcoes, _obter(chave_d)), key=f"w__{chave_d}", horizontal=True)
            with col_e:
                valor_e = st.radio("Esquerdo", options=opcoes, index=_indice(opcoes, _obter(chave_e)), key=f"w__{chave_e}", horizontal=True)
        else:  # bilateral_score
            opcoes = ["1", "2", "3"]
            with col_d:
                valor_d = st.radio("Direito", options=opcoes, index=_indice(opcoes, _obter(chave_d)), key=f"w__{chave_d}", horizontal=True)
            with col_e:
                valor_e = st.radio("Esquerdo", options=opcoes, index=_indice(opcoes, _obter(chave_e)), key=f"w__{chave_e}", horizontal=True)

        _guardar(chave_d, valor_d)
        _guardar(chave_e, valor_e)

        if campo.observacao:
            chave_obs = _chave(secao_id, campo.id, "obs")
            valor_obs = st.text_input("Observação", value=_obter(chave_obs) or "", key=f"w__{chave_obs}")
            _guardar(chave_obs, valor_obs)
    else:
        st.warning(f"Tipo de campo não suportado: {tipo}")


def renderizar_secao_repetivel(secao: SecaoRepetivel) -> None:
    st.markdown(f"## {secao.titulo}")
    chave_realizado = _chave(secao.id, "realizado")
    if secao.tem_toggle_realizado:
        opcoes = ["Sim", "Não"]
        valor = st.radio("Realizado?", options=opcoes, index=_indice(opcoes, _obter(chave_realizado)), key=f"w__{chave_realizado}", horizontal=True)
        _guardar(chave_realizado, valor)
        if valor == "Não":
            return

    chave_n = _chave("n_linhas", secao.id)
    if chave_n not in st.session_state:
        st.session_state[chave_n] = secao.minimo_linhas
    n_linhas = st.session_state[chave_n]

    for i in range(n_linhas):
        colunas_widgets = st.columns(len(secao.colunas))
        for (col_id, col_rotulo), container in zip(secao.colunas, colunas_widgets):
            chave_campo = _chave(secao.id, f"linha{i}", col_id)
            visibilidade = "visible" if i == 0 else "collapsed"
            with container:
                if col_id in ("direito", "esquerdo"):
                    valor = st.number_input(col_rotulo, value=_obter(chave_campo), step=0.1, format="%.1f", key=f"w__{chave_campo}", label_visibility=visibilidade)
                else:
                    valor = st.text_input(col_rotulo, value=_obter(chave_campo) or "", key=f"w__{chave_campo}", label_visibility=visibilidade)
            _guardar(chave_campo, valor)

    col_add, col_rem = st.columns(2)
    with col_add:
        if st.button("➕ Adicionar linha", key=_chave(secao.id, "add")):
            st.session_state[chave_n] += 1
            st.rerun()
    with col_rem:
        if n_linhas > 0 and st.button("➖ Remover última linha", key=_chave(secao.id, "rem")):
            ultima = n_linhas - 1
            respostas = st.session_state.get("respostas", {})
            for col_id, _rotulo in secao.colunas:
                respostas.pop(_chave(secao.id, f"linha{ultima}", col_id), None)
            st.session_state[chave_n] -= 1
            st.rerun()


def renderizar_secao_dor(secao: SecaoDor) -> None:
    st.markdown(f"## {secao.titulo}")
    chave_repouso = _chave(secao.id, "escala_repouso")
    chave_atividade = _chave(secao.id, "escala_atividade")
    col_r, col_a = st.columns(2)
    with col_r:
        valor_r = st.slider("Escala de dor em repouso (0–10)", min_value=0, max_value=10, value=_obter(chave_repouso) or 0, key=f"w__{chave_repouso}")
    with col_a:
        valor_a = st.slider("Escala de dor em atividade (0–10)", min_value=0, max_value=10, value=_obter(chave_atividade) or 0, key=f"w__{chave_atividade}")
    _guardar(chave_repouso, valor_r)
    _guardar(chave_atividade, valor_a)

    st.markdown("**Locais de dor**")
    chave_n = _chave("n_linhas", secao.id)
    if chave_n not in st.session_state:
        st.session_state[chave_n] = 0
    n_linhas = st.session_state[chave_n]

    for i in range(n_linhas):
        col1, col2, col3 = st.columns(3)
        visibilidade = "visible" if i == 0 else "collapsed"
        chave_regiao = _chave(secao.id, f"linha{i}", "regiao")
        chave_lado = _chave(secao.id, f"linha{i}", "lado")
        chave_intensidade = _chave(secao.id, f"linha{i}", "intensidade")
        opcoes_regiao = list(secao.opcoes_regiao)
        opcoes_lado = list(secao.opcoes_lado)
        with col1:
            valor_regiao = st.selectbox("Região", options=opcoes_regiao, index=_indice(opcoes_regiao, _obter(chave_regiao)), key=f"w__{chave_regiao}", label_visibility=visibilidade)
        with col2:
            valor_lado = st.selectbox("Lado", options=opcoes_lado, index=_indice(opcoes_lado, _obter(chave_lado)), key=f"w__{chave_lado}", label_visibility=visibilidade)
        with col3:
            valor_intensidade = st.slider("Intensidade", min_value=0, max_value=10, value=_obter(chave_intensidade) or 0, key=f"w__{chave_intensidade}", label_visibility=visibilidade)
        _guardar(chave_regiao, valor_regiao)
        _guardar(chave_lado, valor_lado)
        _guardar(chave_intensidade, valor_intensidade)

    col_add, col_rem = st.columns(2)
    with col_add:
        if st.button("➕ Adicionar local de dor", key=_chave(secao.id, "add")):
            st.session_state[chave_n] += 1
            st.rerun()
    with col_rem:
        if n_linhas > 0 and st.button("➖ Remover último local", key=_chave(secao.id, "rem")):
            ultima = n_linhas - 1
            respostas = st.session_state.get("respostas", {})
            for col_id in ("regiao", "lado", "intensidade"):
                respostas.pop(_chave(secao.id, f"linha{ultima}", col_id), None)
            st.session_state[chave_n] -= 1
            st.rerun()


def renderizar_secao_fotos(secao: SecaoFotos) -> None:
    st.markdown(f"## {secao.titulo}")
    st.caption("Tire fotos pela câmera do tablet/celular pra ilustrar o relatório (opcional).")

    chave_n = _chave("n_linhas", secao.id)
    if chave_n not in st.session_state:
        st.session_state[chave_n] = 0
    n_linhas = st.session_state[chave_n]

    for i in range(n_linhas):
        chave_descricao = _chave(secao.id, f"linha{i}", "descricao")
        chave_foto = _chave(secao.id, f"linha{i}", "foto")

        valor_descricao = st.text_input(
            f"Descrição da foto {i + 1}", value=_obter(chave_descricao) or "", key=f"w__{chave_descricao}"
        )
        _guardar(chave_descricao, valor_descricao)

        arquivo = st.camera_input(f"Foto {i + 1}", key=f"w__{chave_foto}")
        if arquivo is not None:
            _guardar(chave_foto, arquivo.getvalue())
        elif _obter(chave_foto):
            # O próprio widget de câmera perde a prévia ao navegar pra
            # outra seção e voltar (mesma limpeza de session_state que
            # afeta qualquer widget não desenhado numa execução) — mostra
            # a foto já salva em `respostas` como substituta.
            st.image(_obter(chave_foto), width=240, caption="Foto já capturada")
        st.divider()

    col_add, col_rem = st.columns(2)
    with col_add:
        if st.button("➕ Adicionar foto", key=_chave(secao.id, "add")):
            st.session_state[chave_n] += 1
            st.rerun()
    with col_rem:
        if n_linhas > 0 and st.button("➖ Remover última foto", key=_chave(secao.id, "rem")):
            ultima = n_linhas - 1
            respostas = st.session_state.get("respostas", {})
            respostas.pop(_chave(secao.id, f"linha{ultima}", "descricao"), None)
            respostas.pop(_chave(secao.id, f"linha{ultima}", "foto"), None)
            st.session_state[chave_n] -= 1
            st.rerun()


# ---------------------------------------------------------------------------
# Coleta das respostas (session_state["respostas"] -> dict limpo, pro PDF)
# ---------------------------------------------------------------------------

def _ler_campo(secao_id: str, campo: Campo):
    respostas = st.session_state.get("respostas", {})
    if campo.tipo in ("bilateral_numero", "bilateral_sinal", "bilateral_score"):
        valor = {
            "D": respostas.get(_chave(secao_id, campo.id, "D")),
            "E": respostas.get(_chave(secao_id, campo.id, "E")),
        }
        if campo.observacao:
            valor["obs"] = respostas.get(_chave(secao_id, campo.id, "obs"))
        return valor
    return respostas.get(_chave(secao_id, campo.id))


def coletar_respostas(protocolo: Protocolo) -> dict:
    respostas = st.session_state.get("respostas", {})
    dados: dict = {
        "protocolo_id": protocolo.id,
        "protocolo_nome": protocolo.nome,
        "tipo_avaliacao": st.session_state.get("tipo_avaliacao", "Nova avaliação"),
        "data_avaliacao": st.session_state.get("data_avaliacao") or dt.date.today(),
        "secoes": [],
    }

    for secao in protocolo.secoes:
        if isinstance(secao, SecaoRepetivel):
            realizado = respostas.get(_chave(secao.id, "realizado")) if secao.tem_toggle_realizado else None
            n_linhas = st.session_state.get(_chave("n_linhas", secao.id), secao.minimo_linhas)
            linhas = []
            for i in range(n_linhas):
                linha = {col_id: respostas.get(_chave(secao.id, f"linha{i}", col_id)) for col_id, _r in secao.colunas}
                if any(v not in (None, "") for v in linha.values()):
                    linhas.append(linha)
            dados["secoes"].append({
                "tipo": "repetivel", "id": secao.id, "titulo": secao.titulo,
                "realizado": realizado, "linhas": linhas, "definicao": secao,
            })
        elif isinstance(secao, SecaoDor):
            n_linhas = st.session_state.get(_chave("n_linhas", secao.id), 0)
            locais = []
            for i in range(n_linhas):
                regiao = respostas.get(_chave(secao.id, f"linha{i}", "regiao"))
                if regiao:
                    locais.append({
                        "regiao": regiao,
                        "lado": respostas.get(_chave(secao.id, f"linha{i}", "lado")),
                        "intensidade": respostas.get(_chave(secao.id, f"linha{i}", "intensidade")),
                    })
            dados["secoes"].append({
                "tipo": "dor", "id": secao.id, "titulo": secao.titulo,
                "escala_repouso": respostas.get(_chave(secao.id, "escala_repouso")),
                "escala_atividade": respostas.get(_chave(secao.id, "escala_atividade")),
                "locais": locais, "definicao": secao,
            })
        elif isinstance(secao, SecaoFotos):
            n_linhas = st.session_state.get(_chave("n_linhas", secao.id), 0)
            fotos = []
            for i in range(n_linhas):
                foto_bytes = respostas.get(_chave(secao.id, f"linha{i}", "foto"))
                if foto_bytes:
                    fotos.append({
                        "descricao": respostas.get(_chave(secao.id, f"linha{i}", "descricao")),
                        "foto_bytes": foto_bytes,
                    })
            dados["secoes"].append({
                "tipo": "fotos", "id": secao.id, "titulo": secao.titulo,
                "fotos": fotos, "definicao": secao,
            })
        else:  # Secao
            campos_saida = {campo.id: _ler_campo(secao.id, campo) for campo in secao.campos}
            dados["secoes"].append({
                "tipo": "secao", "id": secao.id, "titulo": secao.titulo,
                "campos": campos_saida, "definicao": secao,
            })

    return dados


def _formatar_valor(valor) -> str:
    if valor is None or valor == "":
        return "—"
    if isinstance(valor, dict):
        d = valor.get("D")
        e = valor.get("E")
        texto = f"D: {d if d not in (None, '') else '—'} · E: {e if e not in (None, '') else '—'}"
        if valor.get("obs"):
            texto += f" ({valor['obs']})"
        return texto
    return str(valor)


def _nome_arquivo(dados: dict, nome_paciente: str) -> str:
    data_av = dados.get("data_avaliacao") or dt.date.today()
    nome_limpo = "_".join(nome_paciente.strip().split()) or "paciente"
    return f"avaliacao_{dados['protocolo_id']}_{nome_limpo}_{data_av.strftime('%d%m%Y')}.pdf"


def _reiniciar() -> None:
    for chave in list(st.session_state.keys()):
        del st.session_state[chave]


# ---------------------------------------------------------------------------
# Navegação principal
# ---------------------------------------------------------------------------

def _passo_selecao_protocolo() -> None:
    st.markdown("# Avaliação Cinética Funcional — Sport Labs")
    st.caption("Escolha o protocolo e o tipo de avaliação para começar.")

    with estilo.cartao("protocolo"):
        st.markdown("**Protocolo**")
        protocolo_opcao = st.segmented_control(
            "Protocolo",
            options=[PROTOCOLO_MMII.nome, PROTOCOLO_MMSS.nome],
            label_visibility="collapsed",
            key="segmented_protocolo",
            width="stretch",
        )

    with estilo.cartao("tipo"):
        st.markdown("**Tipo de avaliação**")
        tipo_opcao = st.segmented_control(
            "Tipo de avaliação",
            options=["Nova avaliação", "Reavaliação"],
            label_visibility="collapsed",
            key="segmented_tipo",
            width="stretch",
        )

    if st.button("Iniciar Avaliação", type="primary", disabled=not (protocolo_opcao and tipo_opcao)):
        protocolo_id = PROTOCOLO_MMII.id if protocolo_opcao == PROTOCOLO_MMII.nome else PROTOCOLO_MMSS.id
        st.session_state["protocolo_id"] = protocolo_id
        st.session_state["tipo_avaliacao"] = tipo_opcao
        st.session_state["data_avaliacao"] = dt.date.today()
        st.session_state["etapa"] = 1
        st.rerun()


def _passo_revisao(protocolo: Protocolo) -> None:
    st.markdown(f"## Revisão — {protocolo.nome}")
    dados = coletar_respostas(protocolo)
    nome_paciente = dados["secoes"][0]["campos"].get("nome_completo")

    for secao_saida in dados["secoes"]:
        with st.expander(secao_saida["titulo"]):
            if secao_saida["tipo"] == "secao":
                for campo in secao_saida["definicao"].campos:
                    st.write(f"**{campo.rotulo}:** {_formatar_valor(secao_saida['campos'][campo.id])}")
            elif secao_saida["tipo"] == "repetivel":
                if secao_saida["realizado"] == "Não":
                    st.write("Não realizado.")
                elif not secao_saida["linhas"]:
                    st.write("Sem linhas preenchidas.")
                else:
                    st.table(secao_saida["linhas"])
            elif secao_saida["tipo"] == "dor":
                st.write(
                    f"Repouso: {secao_saida['escala_repouso'] if secao_saida['escala_repouso'] is not None else '—'} / 10"
                    f" — Atividade: {secao_saida['escala_atividade'] if secao_saida['escala_atividade'] is not None else '—'} / 10"
                )
                if secao_saida["locais"]:
                    st.table(secao_saida["locais"])
                else:
                    st.write("Sem locais de dor registrados.")
            elif secao_saida["tipo"] == "fotos":
                if secao_saida["fotos"]:
                    for foto in secao_saida["fotos"]:
                        st.image(foto["foto_bytes"], width=160, caption=foto.get("descricao") or None)
                else:
                    st.write("Nenhuma foto registrada.")

    st.divider()

    if not nome_paciente:
        st.warning("Preencha o nome completo do paciente (seção Dados do Paciente) para gerar o PDF.")

    col_voltar, col_gerar = st.columns(2)
    with col_voltar:
        if st.button("← Voltar e corrigir", key="nav_revisao_voltar"):
            st.session_state["etapa"] = len(protocolo.secoes)
            st.rerun()
    with col_gerar:
        if st.button("Gerar PDF", key="gerar_pdf", type="primary", disabled=not nome_paciente):
            st.session_state["pdf_bytes"] = pdf_avaliacao.gerar(dados)
            st.session_state["pdf_nome_arquivo"] = _nome_arquivo(dados, nome_paciente)

    if st.session_state.get("pdf_bytes"):
        st.success("PDF gerado! Baixe abaixo e abra no visualizador do tablet para imprimir.")
        st.download_button(
            "⬇ Baixar PDF",
            data=st.session_state["pdf_bytes"],
            file_name=st.session_state["pdf_nome_arquivo"],
            mime="application/pdf",
            type="primary",
            key="download_pdf",
        )
        if st.button("Iniciar nova avaliação", key="reiniciar"):
            _reiniciar()
            st.rerun()


def render() -> None:
    if "etapa" not in st.session_state:
        st.session_state["etapa"] = 0
    # `time.time()` em vez da etapa: revisitar a mesma seção (Voltar e
    # Próximo de novo) repetiria o mesmo identificador e o Streamlit não
    # recarregaria o iframe do script uma segunda vez.
    _rolar_para_topo(str(time.time()))

    if st.session_state["etapa"] == 0 or not st.session_state.get("protocolo_id"):
        _passo_selecao_protocolo()
        return

    protocolo = PROTOCOLOS[st.session_state["protocolo_id"]]
    total_passos = len(protocolo.secoes)
    etapa = st.session_state["etapa"]

    if etapa > total_passos:
        _passo_revisao(protocolo)
        return

    secao = protocolo.secoes[etapa - 1]
    st.markdown(f'<div class="sl-progresso">Seção {etapa} de {total_passos} — {protocolo.nome}</div>', unsafe_allow_html=True)

    if isinstance(secao, SecaoRepetivel):
        renderizar_secao_repetivel(secao)
    elif isinstance(secao, SecaoDor):
        renderizar_secao_dor(secao)
    elif isinstance(secao, SecaoFotos):
        renderizar_secao_fotos(secao)
    else:
        renderizar_secao(secao)

    st.divider()
    col_voltar, col_proximo = st.columns(2)
    with col_voltar:
        if st.button("← Voltar", key="nav_voltar"):
            st.session_state["etapa"] -= 1
            st.rerun()
    with col_proximo:
        rotulo = "Revisar e gerar PDF →" if etapa == total_passos else "Próximo →"
        if st.button(rotulo, key="nav_proximo", type="primary"):
            st.session_state["etapa"] += 1
            st.rerun()
