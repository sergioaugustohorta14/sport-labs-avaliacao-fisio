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
import html
import re
import time
import uuid

import streamlit as st
import streamlit.components.v1 as components

from avaliacao_fisio import (
    assimetria,
    estilo,
    feegow_client,
    historico,
    pdf_anexos,
    pdf_avaliacao,
    pdfs_drive,
    runscribe_client,
)
from avaliacao_fisio.protocolos import (
    METRICAS_RUNSCRIBE,
    PROTOCOLO_MMII,
    PROTOCOLO_MMSS,
    PROTOCOLOS,
    Campo,
    Protocolo,
    Secao,
    SecaoCorrida,
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


def _guardar(chave: str, valor, avancar: bool = False) -> None:
    """`avancar=True` marca que esse campo é do tipo "clique único" (rádio/
    segmented/selectbox que já re-executa na hora) — se o valor mudou de
    verdade, sinaliza pra `render()` rolar a tela até o próximo campo
    (pedido da equipe de fisioterapeutas, 13/10/2026). Não usar em campos
    de texto/número (atrapalharia digitar)."""
    respostas = st.session_state.setdefault("respostas", {})
    if avancar and valor is not None and respostas.get(chave) != valor:
        st.session_state["_avancar_scroll"] = True
    respostas[chave] = valor


def _indice(opcoes: list[str], atual) -> int | None:
    return opcoes.index(atual) if atual in opcoes else None


def _calcular_idade(data_nascimento) -> int | None:
    if not hasattr(data_nascimento, "year"):
        return None
    hoje = dt.date.today()
    idade = hoje.year - data_nascimento.year
    if (hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day):
        idade -= 1
    return idade


def _formatar_tempo(minutos, segundos) -> str | None:
    if minutos is None and segundos is None:
        return None
    return f"{int(minutos or 0)}'{int(segundos or 0):02d}\""


def _segundos(minutos, segundos) -> int | None:
    if minutos is None and segundos is None:
        return None
    return int(minutos or 0) * 60 + int(segundos or 0)


def _rolar_offset(identificador: str, pixels: int = 220) -> None:
    """Rola a tela um pouco pra baixo depois de marcar um campo de
    clique único (rádio/segmented/selectbox) — pedido da equipe de
    fisioterapeutas pra não precisar rolar manualmente até o próximo
    campo a cada resposta. É uma aproximação por deslocamento fixo em
    pixels, não mira o campo exato seguinte."""
    components.html(
        f"""
        <!-- avancar={identificador} -->
        <script>
            const doc = window.parent.document;
            const principal = doc.querySelector('section[data-testid="stMain"]');
            // `scrollBy` é incremental (não idempotente como o reset pro
            // topo) — chamar mais de uma vez soma o deslocamento em vez de
            // só tentar de novo. Uma chamada só, depois de um instante pro
            // layout da seção assentar.
            setTimeout(() => {{
                if (principal) {{ principal.scrollBy({{top: {pixels}, behavior: 'smooth'}}); }}
            }}, 80);
        </script>
        """,
        height=0,
    )


# ---------------------------------------------------------------------------
# Renderização dos campos
# ---------------------------------------------------------------------------

def _valor_inicial(chave: str, padrao=None) -> dict:
    """`value=` do widget — omitido quando a key do widget já existe no session_state
    (valor importado/forçado), senão o Streamlit avisa que os dois foram usados."""
    if f"w__{chave}" in st.session_state:
        return {}
    valor = _obter(chave)
    return {"value": valor if valor is not None else padrao}


def renderizar_secao(secao: Secao, titulo: bool = True) -> None:
    if titulo:
        st.markdown(f"## {secao.titulo}")
    for campo in secao.campos:
        _renderizar_campo(secao.id, campo)
        st.divider()


def _avaliacoes_anteriores(texto_paciente: str | None) -> None:
    """PDFs já guardados no Drive pra este paciente, pra consultar numa
    reavaliação. Sem Drive configurado ou com falha de rede, não aparece nada
    (nunca trava o preenchimento)."""
    if not texto_paciente or not pdfs_drive.configurado():
        return
    reavaliacao = st.session_state.get("tipo_avaliacao") == "Reavaliação"
    paciente = historico.identificar_paciente(texto_paciente)
    try:
        arquivos = pdfs_drive.listar_cache(paciente["chave"], paciente["nome"])
    except Exception:
        if reavaliacao:
            st.caption("Não consegui consultar as avaliações anteriores no Drive agora.")
        return
    arquivos = [a for a in arquivos if a["id_avaliacao"] != st.session_state.get("id_avaliacao")]
    if not arquivos:
        if reavaliacao:
            st.caption("Nenhuma avaliação anterior guardada para este paciente. Só aparecem as feitas depois que o Drive foi ligado.")
        return

    with st.expander(f"Avaliações anteriores deste paciente ({len(arquivos)})", expanded=reavaliacao):
        for arquivo in arquivos[:5]:
            data = dt.date.fromisoformat(arquivo["data"]) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", arquivo["data"]) else None
            rotulo = " · ".join(p for p in (
                data.strftime("%d/%m/%Y") if data else arquivo["data"], arquivo["protocolo"], arquivo["tipo"],
            ) if p)
            chave_pdf = f"pdf_anterior_{arquivo['id']}"
            col_texto, col_acao = st.columns([3, 2])
            col_texto.markdown(rotulo)
            with col_acao:
                if chave_pdf in st.session_state:
                    st.download_button(
                        "⬇ Baixar PDF", data=st.session_state[chave_pdf], file_name=arquivo["nome"],
                        mime="application/pdf", key=f"baixar_{arquivo['id']}",
                    )
                elif st.button("Abrir PDF", key=f"abrir_{arquivo['id']}"):
                    try:
                        st.session_state[chave_pdf] = pdfs_drive.baixar(arquivo["id"])
                    except Exception:
                        st.error("Não consegui baixar este PDF do Drive.")
                    else:
                        st.rerun()


def _widget_tempo(chave_base: str, visivel: bool = True) -> None:
    """Dois `number_input` (minutos, segundos) — usado por
    "bilateral_tempo"/"unico_tempo" (ex.: prancha lateral em min/seg em
    vez de só segundos, pedido da equipe de fisioterapeutas)."""
    chave_min, chave_seg = f"{chave_base}_min", f"{chave_base}_seg"
    visibilidade = "visible" if visivel else "collapsed"
    col_min, col_seg = st.columns(2)
    with col_min:
        valor_min = st.number_input("min", value=_obter(chave_min), min_value=0, step=1, key=f"w__{chave_min}", label_visibility=visibilidade)
    with col_seg:
        valor_seg = st.number_input("seg", value=_obter(chave_seg), min_value=0, max_value=59, step=1, key=f"w__{chave_seg}", label_visibility=visibilidade)
    _guardar(chave_min, valor_min)
    _guardar(chave_seg, valor_seg)


def _renderizar_campo(secao_id: str, campo: Campo) -> None:
    tipo = campo.tipo
    chave = _chave(secao_id, campo.id)

    if tipo == "unico_texto":
        valor = st.text_input(campo.rotulo, **_valor_inicial(chave, ""), key=f"w__{chave}", help=campo.ajuda)
        _guardar(chave, valor)
    elif tipo == "idade_calculada":
        # Sem widget — deriva de "data_nascimento" (campo anterior, mesma
        # seção) e grava o resultado como se fosse um campo normal, pra
        # revisão/PDF não precisarem de tratamento especial.
        data_nascimento = _obter(_chave(secao_id, "data_nascimento"))
        idade = _calcular_idade(data_nascimento)
        if idade is not None:
            st.caption(f"{campo.rotulo}: {idade} {campo.unidade or ''}".strip())
        else:
            st.caption(f"{campo.rotulo}: preencha a data de nascimento acima")
        _guardar(chave, idade)
    elif tipo == "busca_paciente":
        # Autocomplete com os pacientes já cadastrados no Feegow (achado
        # real: a API só cobre os ~500 cadastros mais antigos e não filtra
        # por nome no servidor — por isso busca difusa no cliente, e
        # `accept_new_options` garante que digitar um nome fora da lista
        # continua funcionando normalmente, nunca trava o preenchimento).
        # O rótulo mostra o ID do Feegow entre parênteses (achado real:
        # dois cadastros com o mesmo nome, um ativo e um inativo) — ao
        # selecionar um conhecido, autopreenche a data de nascimento.
        mapa = feegow_client.pacientes_mapa_cache()
        opcoes = list(mapa.keys())
        valor_salvo = _obter(chave)
        if valor_salvo and valor_salvo not in opcoes:
            opcoes = [valor_salvo] + opcoes
        indice = opcoes.index(valor_salvo) if valor_salvo in opcoes else None
        valor = st.selectbox(
            campo.rotulo, options=opcoes, index=indice, accept_new_options=True,
            placeholder="Digite pra buscar o paciente ou digitar o nome",
            key=f"w__{chave}",
        )
        if valor != valor_salvo:
            registro = mapa.get(valor)
            if registro and registro.get("nascimento"):
                # Não basta gravar em `respostas` — o widget de data_nascimento
                # já tem a própria `key` no session_state (é desenhado logo a
                # seguir, na mesma seção) e o Streamlit ignora o `value=` de um
                # widget cuja key já existe. Precisa escrever direto na key
                # do widget pra ele realmente mostrar o valor novo.
                chave_nasc = _chave(secao_id, "data_nascimento")
                _guardar(chave_nasc, registro["nascimento"])
                st.session_state[f"w__{chave_nasc}"] = registro["nascimento"]
        _guardar(chave, valor)
        _avaliacoes_anteriores(valor)
    elif tipo == "unico_numero":
        rotulo = f"{campo.rotulo} ({campo.unidade})" if campo.unidade else campo.rotulo
        passo = float(10 ** -campo.casas_decimais)
        valor = st.number_input(rotulo, **_valor_inicial(chave), step=passo, format=f"%.{campo.casas_decimais}f", key=f"w__{chave}", help=campo.ajuda)
        _guardar(chave, valor)
    elif tipo in ("bilateral_tempo", "unico_tempo"):
        st.markdown(f"**{campo.rotulo}**")
        if campo.ajuda:
            st.caption(campo.ajuda)
        if tipo == "unico_tempo":
            _widget_tempo(chave)
        else:
            col_d, col_e = st.columns(2)
            with col_d:
                st.caption("Direito")
                _widget_tempo(_chave(secao_id, campo.id, "D"))
            with col_e:
                st.caption("Esquerdo")
                _widget_tempo(_chave(secao_id, campo.id, "E"))
    elif tipo == "foto_unica":
        arquivo = st.camera_input(campo.rotulo, key=f"w__{chave}", help=campo.ajuda)
        if arquivo is not None:
            _guardar(chave, arquivo.getvalue())
        elif _obter(chave):
            st.image(_obter(chave), width=240, caption="Foto já capturada")
        chave_desc = f"{chave}__desc"
        valor_desc = st.text_input("Legenda da foto", value=_obter(chave_desc) or "", key=f"w__{chave_desc}")
        _guardar(chave_desc, valor_desc)
    elif tipo == "video_upload":
        arquivo = st.file_uploader(campo.rotulo, type=["mp4", "mov", "avi", "mkv"], key=f"w__{chave}", help=campo.ajuda)
        if arquivo is not None:
            _guardar(chave, {"nome": arquivo.name, "bytes": arquivo.getvalue()})
        elif _obter(chave):
            st.caption(f"Vídeo já anexado nesta sessão: {_obter(chave)['nome']}")
    elif tipo == "data":
        # Se a key já existe (widget já desenhado antes, ou acabou de ser
        # forçada pelo autopreenchimento da busca de paciente), não passa
        # `value=` — o Streamlit avisa (warning) quando os dois são usados
        # juntos no mesmo render, mesmo funcionando.
        chave_widget = f"w__{chave}"
        if chave_widget in st.session_state:
            valor = st.date_input(campo.rotulo, key=chave_widget, format="DD/MM/YYYY", help=campo.ajuda)
        else:
            valor = st.date_input(campo.rotulo, value=_obter(chave), key=chave_widget, format="DD/MM/YYYY", help=campo.ajuda)
        _guardar(chave, valor)
    elif tipo == "lado_unico":
        opcoes = ["Direito", "Esquerdo"]
        valor = st.radio(campo.rotulo, options=opcoes, index=_indice(opcoes, _obter(chave)), key=f"w__{chave}", horizontal=True, help=campo.ajuda)
        _guardar(chave, valor, avancar=True)
    elif tipo == "opcoes":
        opcoes = list(campo.opcoes or ())
        valor = st.radio(campo.rotulo, options=opcoes, index=_indice(opcoes, _obter(chave)), key=f"w__{chave}", horizontal=True, help=campo.ajuda)
        _guardar(chave, valor, avancar=True)
    elif tipo in ("bilateral_numero", "bilateral_sinal", "bilateral_score"):
        rotulo = f"{campo.rotulo} ({campo.unidade})" if campo.unidade else campo.rotulo
        st.markdown(f"**{rotulo}**")
        if campo.ajuda:
            st.caption(campo.ajuda)
        col_d, col_e = st.columns(2)
        chave_d, chave_e = _chave(secao_id, campo.id, "D"), _chave(secao_id, campo.id, "E")

        if tipo == "bilateral_numero":
            passo = float(10 ** -campo.casas_decimais)
            with col_d:
                valor_d = st.number_input("Direito", **_valor_inicial(chave_d), step=passo, format=f"%.{campo.casas_decimais}f", key=f"w__{chave_d}")
            with col_e:
                valor_e = st.number_input("Esquerdo", **_valor_inicial(chave_e), step=passo, format=f"%.{campo.casas_decimais}f", key=f"w__{chave_e}")
            avancar = False
        elif tipo == "bilateral_sinal":
            opcoes = ["+", "-"]
            with col_d:
                valor_d = st.radio("Direito", options=opcoes, index=_indice(opcoes, _obter(chave_d)), key=f"w__{chave_d}", horizontal=True)
            with col_e:
                valor_e = st.radio("Esquerdo", options=opcoes, index=_indice(opcoes, _obter(chave_e)), key=f"w__{chave_e}", horizontal=True)
            avancar = True
        else:  # bilateral_score
            opcoes = ["1", "2", "3"]
            with col_d:
                valor_d = st.radio("Direito", options=opcoes, index=_indice(opcoes, _obter(chave_d)), key=f"w__{chave_d}", horizontal=True)
            with col_e:
                valor_e = st.radio("Esquerdo", options=opcoes, index=_indice(opcoes, _obter(chave_e)), key=f"w__{chave_e}", horizontal=True)
            avancar = True

        _guardar(chave_d, valor_d, avancar=avancar)
        _guardar(chave_e, valor_e, avancar=avancar)

        if campo.observacao:
            chave_obs = _chave(secao_id, campo.id, "obs")
            valor_obs = st.text_input("Observação", value=_obter(chave_obs) or "", key=f"w__{chave_obs}")
            _guardar(chave_obs, valor_obs)
    else:
        st.warning(f"Tipo de campo não suportado: {tipo}")


def _casa_nome(etiqueta: str, nome_paciente: str) -> bool:
    """A etiqueta da corrida no RunScribe é texto livre (ex.: "Suely"). Casa se todas as
    palavras de um dos lados aparecem no outro (sem acento/caixa); etiquetas padrão
    ("Run 08 jun 2024") não casam com nenhum nome."""
    palavras_etiqueta = {p for p in historico.normalizar(etiqueta).split() if len(p) >= 3}
    palavras_nome = {p for p in historico.normalizar(nome_paciente).split() if len(p) >= 3}
    if not palavras_etiqueta or not palavras_nome:
        return False
    return palavras_etiqueta <= palavras_nome or palavras_nome <= palavras_etiqueta


def _data_br(iso: str) -> str:
    try:
        return dt.date.fromisoformat(iso).strftime("%d/%m/%Y")
    except ValueError:
        return iso or "?"


def _texto_corrida(corrida: dict) -> str:
    distancia = f"{corrida['distancia'] / 1000:.2f} km".replace(".", ",") if corrida.get("distancia") else "distância ?"
    return f"{_data_br(corrida['data'])} · {corrida['label'] or 'sem nome'} · {distancia}"


def _aplicar_corrida(secao: SecaoCorrida, resumo: dict) -> None:
    """Grava os valores da corrida escolhida nos campos da seção. Escreve no dict de
    respostas E direto na key do widget (o Streamlit ignora `value=` de um widget cuja
    key já existe); valor ausente remove a key pro campo voltar a ficar em branco."""
    corrida, metricas = resumo["corrida"], resumo["metricas"]

    def gravar(chave: str, valor, casas: int = 1) -> None:
        if valor is not None and not isinstance(valor, str):
            valor = round(float(valor), casas)
        _guardar(chave, valor)
        if valor is None:
            st.session_state.pop(f"w__{chave}", None)
        else:
            st.session_state[f"w__{chave}"] = valor

    for campo in secao.campos:
        chave = _chave(secao.id, campo.id)
        if campo.id == "corrida_analisada":
            gravar(chave, f"{_data_br(corrida['data'])} · {corrida['label'] or 'sem nome'} (RunScribe nº {corrida['id']})")
        elif campo.id == "distancia_m":
            gravar(chave, corrida.get("distancia"), campo.casas_decimais)
        elif campo.id == "duracao_min":
            tempo = corrida.get("tempo")
            gravar(chave, tempo / 60 if tempo else None, campo.casas_decimais)
        elif campo.id == "passos":
            gravar(chave, corrida.get("passos"), campo.casas_decimais)
        elif campo.tipo == "bilateral_numero":
            for lado in ("D", "E"):
                gravar(_chave(secao.id, campo.id, lado), metricas.get(campo.id, {}).get(lado), campo.casas_decimais)


def renderizar_secao_corrida(secao: SecaoCorrida) -> None:
    """Escolha da corrida no RunScribe (importa as métricas por pé) + os campos, que
    continuam editáveis. Sem integração ou com falha de rede, a seção vira só os
    campos pra preencher à mão: nunca trava o preenchimento."""
    st.markdown(f"## {secao.titulo}")
    if not runscribe_client.configurado():
        st.info("A integração com o RunScribe não está configurada neste ambiente. Preencha os valores à mão.")
        renderizar_secao(secao, titulo=False)
        return
    try:
        corridas = runscribe_client.corridas_resumidas()
    except runscribe_client.RunScribeErro as erro:
        st.warning(f"{erro} Você pode preencher os valores à mão ou tentar de novo mais tarde.")
        renderizar_secao(secao, titulo=False)
        return

    nome = historico.identificar_paciente(_obter(_chave("dados_paciente", "nome_completo")))["nome"]
    sugeridas = [c for c in corridas if nome and _casa_nome(c["label"], nome)]
    if sugeridas:
        mostrar_todas = st.checkbox("Mostrar também as corridas de outros nomes", key="w__corrida_todas")
        lista = corridas if mostrar_todas else sugeridas
        st.caption(f"{len(sugeridas)} corrida(s) com o nome do paciente no RunScribe.")
    else:
        lista = corridas
        st.caption("Nenhuma corrida com o nome do paciente no RunScribe: mostrando todas, da mais recente pra mais antiga.")

    por_id = {c["id"]: c for c in corridas}
    chave_id = _chave(secao.id, "run_id")
    salvo = _obter(chave_id)
    ids = [c["id"] for c in lista]
    if salvo is not None and salvo not in ids:
        ids = [salvo] + ids
    escolha = st.selectbox(
        "Corrida do RunScribe", options=ids, index=_indice(ids, salvo), placeholder="Escolha a corrida",
        format_func=lambda i: _texto_corrida(por_id[i]) if i in por_id else f"Corrida {i}", key="w__corrida_runscribe",
    )
    if escolha is not None and escolha != salvo:
        with st.spinner("Buscando as métricas no RunScribe..."):
            try:
                resumo = runscribe_client.resumo_corrida(escolha, METRICAS_RUNSCRIBE)
            except runscribe_client.RunScribeErro as erro:
                st.error(str(erro))
            else:
                _guardar(chave_id, escolha)
                _aplicar_corrida(secao, resumo)
    st.caption("Valores importados do RunScribe: pé direito (D) e pé esquerdo (E), média da corrida. Você pode ajustar à mão.")
    renderizar_secao(secao, titulo=False)


def renderizar_secao_repetivel(secao: SecaoRepetivel) -> None:
    st.markdown(f"## {secao.titulo}")
    chave_realizado = _chave(secao.id, "realizado")
    if secao.tem_toggle_realizado:
        opcoes = ["Sim", "Não"]
        valor = st.radio("Realizado?", options=opcoes, index=_indice(opcoes, _obter(chave_realizado)), key=f"w__{chave_realizado}", horizontal=True)
        _guardar(chave_realizado, valor, avancar=True)
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
        _guardar(chave_regiao, valor_regiao, avancar=True)
        _guardar(chave_lado, valor_lado, avancar=True)
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
        chave_observacao = _chave(secao.id, f"linha{i}", "observacao")
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

        valor_observacao = st.text_area(
            f"Observação da foto {i + 1}", value=_obter(chave_observacao) or "", key=f"w__{chave_observacao}", height=80,
        )
        _guardar(chave_observacao, valor_observacao)
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
            respostas.pop(_chave(secao.id, f"linha{ultima}", "observacao"), None)
            respostas.pop(_chave(secao.id, f"linha{ultima}", "foto"), None)
            st.session_state[chave_n] -= 1
            st.rerun()


# ---------------------------------------------------------------------------
# Coleta das respostas (session_state["respostas"] -> dict limpo, pro PDF)
# ---------------------------------------------------------------------------

def _ler_campo(secao_id: str, campo: Campo):
    respostas = st.session_state.get("respostas", {})
    chave = _chave(secao_id, campo.id)

    if campo.tipo == "bilateral_tempo":
        chave_d, chave_e = _chave(secao_id, campo.id, "D"), _chave(secao_id, campo.id, "E")
        d_min, d_seg = respostas.get(f"{chave_d}_min"), respostas.get(f"{chave_d}_seg")
        e_min, e_seg = respostas.get(f"{chave_e}_min"), respostas.get(f"{chave_e}_seg")
        # "D_seg"/"E_seg": o mesmo tempo em segundos, pra calcular assimetria e histórico.
        return {
            "D": _formatar_tempo(d_min, d_seg), "E": _formatar_tempo(e_min, e_seg),
            "D_seg": _segundos(d_min, d_seg), "E_seg": _segundos(e_min, e_seg),
        }
    if campo.tipo == "unico_tempo":
        return _formatar_tempo(respostas.get(f"{chave}_min"), respostas.get(f"{chave}_seg"))
    if campo.tipo == "foto_unica":
        return {"foto_bytes": respostas.get(chave), "descricao": respostas.get(f"{chave}__desc")}
    if campo.tipo == "video_upload":
        return respostas.get(chave)
    if campo.tipo in ("bilateral_numero", "bilateral_sinal", "bilateral_score"):
        valor = {
            "D": respostas.get(_chave(secao_id, campo.id, "D")),
            "E": respostas.get(_chave(secao_id, campo.id, "E")),
        }
        if campo.observacao:
            valor["obs"] = respostas.get(_chave(secao_id, campo.id, "obs"))
        return valor
    return respostas.get(chave)


def coletar_respostas(protocolo: Protocolo) -> dict:
    respostas = st.session_state.get("respostas", {})
    dados: dict = {
        "id_avaliacao": st.session_state.get("id_avaliacao") or uuid.uuid4().hex[:12],
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
                        "observacao": respostas.get(_chave(secao.id, f"linha{i}", "observacao")),
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

    dados["paciente"] = historico.identificar_paciente(respostas.get(_chave("dados_paciente", "nome_completo")))
    return dados


def _valor_ausente_html() -> str:
    return f'<span style="color:{estilo.COR_ACENTO};font-style:italic;">Não preenchido</span>'


def _formatar_valor(valor) -> str:
    """Pra tela de Revisão (não o PDF) — pedido da equipe de
    fisioterapeutas (13/10/2026): sem travessão, ausência de informação
    em dourado em vez de "—". Valor de texto livre passa por
    `html.escape` antes de entrar no HTML (segurança)."""
    if valor is None or valor == "":
        return _valor_ausente_html()
    if isinstance(valor, dict):
        d, e = valor.get("D"), valor.get("E")
        d_html = html.escape(str(d)) if d not in (None, "") else _valor_ausente_html()
        e_html = html.escape(str(e)) if e not in (None, "") else _valor_ausente_html()
        texto = f"D: {d_html} · E: {e_html}"
        if valor.get("obs"):
            texto += f" ({html.escape(str(valor['obs']))})"
        return texto
    return html.escape(str(valor))


def _barra_assimetria(d, e) -> str | None:
    """Barra com gradiente verde→amarelo→vermelho + seta indicando a
    % de assimetria entre os lados D/E — mesma fórmula usada pela
    clínica (abaixo de 10% baixa chance de lesão, 10–20% média, acima de
    20% alta), colada pelo Sergio em 13/10/2026. Só aparece na tela de
    Revisão, quando os dois lados têm valor numérico preenchido."""
    pct = assimetria.percentual(d, e)
    if pct is None:
        return None
    posicao = min(pct, 40) / 40 * 100
    risco = assimetria.ROTULO_CHANCE[assimetria.faixa(pct)]
    return f"""
    <div style="margin:2px 0 12px; max-width:320px;">
        <div style="position:relative; height:10px; border-radius:6px; margin-top:14px;
                    background:linear-gradient(90deg, #2e7d32 0%, #2e7d32 25%, {estilo.COR_ACENTO} 50%, #c0392b 100%);">
            <div style="position:absolute; left:calc({posicao:.1f}% - 7px); top:-14px; font-size:13px;">▼</div>
        </div>
        <div style="font-size:0.75rem; color:{estilo.COR_MUTED}; margin-top:2px;">
            Assimetria: {pct:.1f}% · {risco}
        </div>
    </div>
    """


def _nome_arquivo(dados: dict) -> str:
    data_av = dados.get("data_avaliacao") or dt.date.today()
    nome_limpo = "_".join(dados["paciente"]["nome"].split()) or "paciente"
    return f"avaliacao_{dados['protocolo_id']}_{nome_limpo}_{data_av.strftime('%d%m%Y')}.pdf"


def _reiniciar() -> None:
    for chave in list(st.session_state.keys()):
        del st.session_state[chave]


# ---------------------------------------------------------------------------
# Navegação principal
# ---------------------------------------------------------------------------

def _passo_selecao_protocolo() -> None:
    st.markdown('<div class="sl-eyebrow-topo">Sport Labs</div>', unsafe_allow_html=True)
    st.markdown('<h1 class="sl-titulo-principal">Avaliação Cinética Funcional</h1>', unsafe_allow_html=True)
    st.caption("Escolha o protocolo e o tipo de avaliação para começar.")

    with estilo.cartao("protocolo"):
        st.markdown("**Protocolo**")
        protocolo_opcao = st.segmented_control(
            "Protocolo",
            options=[p.nome for p in PROTOCOLOS.values()],
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
        protocolo_id = next(p.id for p in PROTOCOLOS.values() if p.nome == protocolo_opcao)
        st.session_state["protocolo_id"] = protocolo_id
        st.session_state["tipo_avaliacao"] = tipo_opcao
        st.session_state["data_avaliacao"] = dt.date.today()
        st.session_state["id_avaliacao"] = uuid.uuid4().hex[:12]
        st.session_state["etapa"] = 1
        st.rerun()


@st.cache_data(show_spinner=False)
def _analisar_kinology(pdf_bytes: bytes):
    return pdf_anexos.analisar(pdf_bytes)


def _bloco_kinology() -> tuple[bytes | None, list[int]]:
    """Upload do PDF do Kinology + escolha das páginas que serão anexadas ao
    PDF final. Devolve (bytes, páginas escolhidas) ou (None, [])."""
    st.markdown("### Relatório do Kinology (opcional)")
    st.caption(
        "Envie o PDF gerado no Kinology e escolha as páginas que entram no final do PDF do paciente. "
        "As páginas são anexadas sem alteração."
    )
    arquivo = st.file_uploader("PDF do Kinology", type=["pdf"], key="w__kinology_pdf")
    if arquivo is not None:
        st.session_state["kinology_bytes"] = arquivo.getvalue()
        st.session_state["kinology_nome"] = arquivo.name
    pdf_bytes = st.session_state.get("kinology_bytes")
    if not pdf_bytes:
        return None, []
    if arquivo is None:
        st.caption(f"Arquivo já enviado nesta sessão: {st.session_state.get('kinology_nome', 'Kinology.pdf')}")

    try:
        paginas = _analisar_kinology(pdf_bytes)
    except ValueError as erro:
        st.error(str(erro))
        return None, []
    if not pdf_anexos.parece_kinology(pdf_bytes):
        st.warning("Este PDF não parece ser do Kinology. As páginas escolhidas serão anexadas mesmo assim.")

    n_curvas = sum(p.e_curva for p in paginas)
    incluir_curvas = False
    if n_curvas:
        incluir_curvas = st.checkbox(
            f"Incluir as {n_curvas} páginas de curvas brutas (Dinâmica e Desempenho Muscular)",
            value=False, key="w__kinology_curvas",
        )
    escolhidas = st.multiselect(
        "Páginas que entram no PDF",
        options=[p.numero for p in paginas],
        default=pdf_anexos.paginas_padrao(paginas, incluir_curvas),
        format_func=lambda n: paginas[n - 1].rotulo,
        key=f"w__kinology_paginas_{int(incluir_curvas)}",
    )
    st.caption(f"{len(escolhidas)} de {len(paginas)} páginas do Kinology serão anexadas.")
    return pdf_bytes, sorted(escolhidas)


def _gerar_pdf_final(dados: dict, kinology_bytes: bytes | None, kinology_paginas: list[int]) -> tuple[bytes, list[str]]:
    """PDF da avaliação (+ gráficos de evolução do histórico + páginas do
    Kinology). Falha do histórico (planilha fora do ar, credencial errada)
    NUNCA impede o PDF: sai sem evolução e com um aviso."""
    avisos: list[str] = []
    series = None
    if historico.configurado():
        try:
            series = historico.series_do_paciente(historico.carregar(), dados)
        except Exception:
            avisos.append("Não consegui ler o histórico do paciente: o PDF saiu sem os gráficos de evolução.")
        try:
            historico.salvar(dados, st.session_state.get("usuario_logado", ""))
        except Exception:
            avisos.append("Não consegui salvar esta avaliação no histórico: ela não aparecerá nas próximas evoluções.")

    pdf = pdf_avaliacao.gerar(dados, series)
    if kinology_bytes and kinology_paginas:
        pdf = pdf_anexos.anexar(pdf, kinology_bytes, kinology_paginas)

    st.session_state.pop("drive_guardado", None)
    if pdfs_drive.configurado():
        try:
            st.session_state["drive_guardado"] = pdfs_drive.salvar_pdf(pdf, dados)["nome"]
        except Exception:
            avisos.append("Não consegui guardar uma cópia do PDF no Drive: baixe o arquivo abaixo para não perdê-lo.")
    return pdf, avisos


def _passo_revisao(protocolo: Protocolo) -> None:
    st.markdown(f"## Revisão — {protocolo.nome}")
    dados = coletar_respostas(protocolo)
    nome_paciente = dados["secoes"][0]["campos"].get("nome_completo")

    for secao_saida in dados["secoes"]:
        with st.expander(secao_saida["titulo"]):
            if secao_saida["tipo"] == "secao":
                for campo in secao_saida["definicao"].campos:
                    valor = secao_saida["campos"][campo.id]
                    if campo.tipo == "foto_unica":
                        st.markdown(f"**{campo.rotulo}**")
                        if valor.get("foto_bytes"):
                            st.image(valor["foto_bytes"], width=200, caption=valor.get("descricao") or None)
                        else:
                            st.markdown(_valor_ausente_html(), unsafe_allow_html=True)
                        continue
                    if campo.tipo == "video_upload":
                        texto_video = f"anexado nesta sessão — {html.escape(valor['nome'])}" if valor else _valor_ausente_html()
                        st.markdown(f"**{campo.rotulo}:** {texto_video}", unsafe_allow_html=True)
                        continue
                    st.markdown(f"**{campo.rotulo}:** {_formatar_valor(valor)}", unsafe_allow_html=True)
                    if campo.tipo == "bilateral_numero" and campo.risco and isinstance(valor, dict):
                        barra = _barra_assimetria(valor.get("D"), valor.get("E"))
                        if barra:
                            st.markdown(barra, unsafe_allow_html=True)
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
                        if foto.get("observacao"):
                            st.caption(foto["observacao"])
                else:
                    st.write("Nenhuma foto registrada.")

    st.divider()
    kinology_bytes, kinology_paginas = _bloco_kinology()
    st.divider()

    if not nome_paciente:
        st.warning("Preencha o nome completo do paciente (seção Dados do Paciente) para gerar o PDF.")
    if not historico.configurado():
        st.caption("Histórico de evolução desativado: a planilha do Google ainda não está configurada neste ambiente.")

    col_voltar, col_gerar = st.columns(2)
    with col_voltar:
        if st.button("← Voltar e corrigir", key="nav_revisao_voltar"):
            st.session_state["etapa"] = len(protocolo.secoes)
            st.rerun()
    with col_gerar:
        if st.button("Gerar PDF", key="gerar_pdf", type="primary", disabled=not nome_paciente):
            st.session_state["pdf_bytes"], st.session_state["avisos_pdf"] = _gerar_pdf_final(
                dados, kinology_bytes, kinology_paginas,
            )
            st.session_state["pdf_nome_arquivo"] = _nome_arquivo(dados)

    if st.session_state.get("pdf_bytes"):
        for aviso in st.session_state.get("avisos_pdf", []):
            st.warning(aviso)
        st.success("PDF gerado! Baixe abaixo e abra no visualizador do tablet para imprimir.")
        if st.session_state.get("drive_guardado"):
            st.caption("Cópia guardada no Drive da clínica: aparece nas próximas avaliações deste paciente.")
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
    etapa = st.session_state["etapa"]

    # Achado real (13/10/2026): rolar pro topo em TODO rerun (não só ao
    # trocar de seção) fazia a tela subir sozinha a cada campo
    # preenchido — o usuário tinha que rolar de novo pra achar onde
    # estava. Agora só rola quando a etapa muda de verdade.
    mudou_de_etapa = st.session_state.get("_ultima_etapa_rolada") != etapa
    if mudou_de_etapa:
        st.session_state["_ultima_etapa_rolada"] = etapa
        # `time.time()` pra garantir conteúdo único mesmo revisitando a
        # mesma etapa (Voltar e Próximo de novo) — sem isso o Streamlit
        # não recarrega o iframe do script e ele só roda uma vez.
        _rolar_para_topo(f"{etapa}_{time.time()}")

    if etapa == 0 or not st.session_state.get("protocolo_id"):
        _passo_selecao_protocolo()
        return

    protocolo = PROTOCOLOS[st.session_state["protocolo_id"]]
    total_passos = len(protocolo.secoes)

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
    elif isinstance(secao, SecaoCorrida):
        renderizar_secao_corrida(secao)
    else:
        renderizar_secao(secao)

    # Pedido da equipe de fisioterapeutas: ao marcar um campo de clique
    # único (rádio/segmented/selectbox), rolar um pouco pra baixo sozinho
    # — só dispara se NÃO acabamos de trocar de seção (senão brigaria com
    # o scroll-pro-topo acima).
    if not mudou_de_etapa and st.session_state.pop("_avancar_scroll", False):
        _rolar_offset(str(time.time()))

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
