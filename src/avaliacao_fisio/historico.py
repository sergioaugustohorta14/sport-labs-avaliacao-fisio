"""Histórico das avaliações num Google Sheets, pra montar os gráficos de
evolução (data a data) quando o paciente volta pra uma reavaliação.

Formato LONGO e só-acrescenta: uma linha por (avaliação x teste x lado). Nunca
apaga nem sobrescreve; regravar a mesma avaliação (voltar, corrigir e gerar o
PDF de novo) acrescenta linhas com o mesmo `id_avaliacao` e, na leitura, vale
a última por (avaliação, teste, lado).

Só entram os TESTES medidos (força, amplitude, saltos, equilíbrio, tempos).
Dados do paciente (peso, altura, diagnóstico), dor, fotos e vídeo NÃO vão pra
planilha — dado de saúde fora do app, o mínimo necessário.

`salvar`/`carregar` falam com a rede. O resto é função pura.
"""
from __future__ import annotations

import datetime as dt
import re
import unicodedata

from avaliacao_fisio.config import obter_config, obter_secret_tabela
from avaliacao_fisio.pdf_base import FUSO_BRASILIA
from avaliacao_fisio.protocolos import PROTOCOLOS, Secao

COLUNAS = [
    "id_avaliacao", "criado_em", "data_avaliacao", "paciente_chave", "paciente_nome", "protocolo",
    "tipo_avaliacao", "secao_id", "campo_id", "rotulo", "lado", "valor_num", "valor_texto", "unidade",
    "fisioterapeuta", "usuario",
]
_INTERVALO = "A:P"  # sem nome de aba: vale a primeira
_TIPOS_COM_LADOS = ("bilateral_numero", "bilateral_tempo", "bilateral_score", "bilateral_sinal")
_TIPOS_EVOLUTIVOS = ("bilateral_numero", "bilateral_tempo")
_RE_ID = re.compile(r"\s*\(ID\s*(\d+)\)\s*$")


def configurado() -> bool:
    return bool(obter_config("GOOGLE_AVALIACOES_SHEET_ID")) and bool(obter_secret_tabela("gcp_service_account"))


def _sheet_id() -> str:
    valor = obter_config("GOOGLE_AVALIACOES_SHEET_ID")
    if not valor:
        raise RuntimeError("GOOGLE_AVALIACOES_SHEET_ID não configurado nos Secrets.")
    return valor


def normalizar(nome: str) -> str:
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", nome or "") if not unicodedata.combining(c))
    return " ".join(sem_acento.lower().split())


def identificar_paciente(texto: str | None) -> dict:
    """"Fulano (ID 1234)" (veio da busca do Feegow) -> id do Feegow; nome
    digitado à mão -> chave pelo nome sem acento/caixa."""
    texto = (texto or "").strip()
    achado = _RE_ID.search(texto)
    if achado:
        nome = texto[:achado.start()].strip()
        return {"nome": nome, "id": int(achado.group(1)), "chave": f"feegow:{achado.group(1)}"}
    return {"nome": texto, "id": None, "chave": f"nome:{normalizar(texto)}"}


# --------------------------------------------------------------------------- pura
def _campos_evolutivos() -> dict[tuple[str, str], object]:
    """(secao_id, campo_id) -> Campo, dos testes que têm D e E numéricos (os que viram gráfico)."""
    achados = {}
    for protocolo in PROTOCOLOS.values():
        for secao in protocolo.secoes:
            if isinstance(secao, Secao):
                for campo in secao.campos:
                    if campo.tipo in _TIPOS_EVOLUTIVOS:
                        achados[(secao.id, campo.id)] = campo
    return achados


def _numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _responsavel(dados: dict) -> str:
    for secao in dados["secoes"]:
        if secao["id"] == "responsavel":
            return secao["campos"].get("fisioterapeuta_responsavel") or ""
    return ""


def linhas_da_avaliacao(dados: dict, usuario: str, criado_em: dt.datetime | None = None) -> list[list]:
    """Linhas (na ordem de `COLUNAS`) dos testes preenchidos desta avaliação."""
    criado_em = criado_em or dt.datetime.now(FUSO_BRASILIA)
    data_av = dados.get("data_avaliacao") or criado_em.date()
    paciente = dados["paciente"]
    fisio = _responsavel(dados)
    base = [
        dados["id_avaliacao"], criado_em.strftime("%Y-%m-%dT%H:%M:%S"), data_av.strftime("%Y-%m-%d"),
        paciente["chave"], paciente["nome"], dados["protocolo_id"], dados["tipo_avaliacao"],
    ]
    linhas: list[list] = []

    def acrescentar(secao_id, campo, lado, num, texto):
        if num is None and not texto:
            return
        linhas.append(base + [
            secao_id, campo.id, campo.rotulo, lado, num if num is not None else "", texto or "",
            campo.unidade or "", fisio, usuario,
        ])

    for secao in dados["secoes"]:
        if secao["tipo"] != "secao" or secao["id"] in ("dados_paciente", "classificacao_risco", "responsavel"):
            continue
        for campo in secao["definicao"].campos:
            valor = secao["campos"].get(campo.id)
            if campo.tipo == "bilateral_numero" and isinstance(valor, dict):
                for lado in ("D", "E"):
                    if _numero(valor.get(lado)):
                        acrescentar(secao["id"], campo, lado, float(valor[lado]), "")
            elif campo.tipo == "bilateral_tempo" and isinstance(valor, dict):
                for lado in ("D", "E"):
                    acrescentar(secao["id"], campo, lado, valor.get(f"{lado}_seg"), valor.get(lado))
            elif campo.tipo in ("bilateral_score", "bilateral_sinal") and isinstance(valor, dict):
                for lado in ("D", "E"):
                    texto = valor.get(lado)
                    if texto:
                        num = float(texto) if campo.tipo == "bilateral_score" else None
                        acrescentar(secao["id"], campo, lado, num, str(texto))
            elif campo.tipo == "unico_numero" and _numero(valor):
                acrescentar(secao["id"], campo, "U", float(valor), "")
    return linhas


def _linhas_para_dicts(linhas: list[list]) -> list[dict]:
    if not linhas or list(linhas[0][:len(COLUNAS)]) != COLUNAS:
        return []
    return [dict(zip(COLUNAS, l + [""] * (len(COLUNAS) - len(l)))) for l in linhas[1:]]


def series_do_paciente(linhas_planilha: list[list], dados_atual: dict) -> dict[tuple[str, str], list[dict]]:
    """Séries (data a data) dos testes bilaterais numéricos do paciente: o que
    já está na planilha (sem contar esta avaliação) + os valores desta
    avaliação, que ainda estão só na memória.

    Devolve {(secao_id, campo_id): [{"data": date, "D": float|None, "E": float|None}, ...]}
    em ordem de data. Mesma data em avaliações diferentes: vale a gravada por último."""
    evolutivos = _campos_evolutivos()
    paciente = dados_atual["paciente"]
    nome_norm = normalizar(paciente["nome"])
    id_atual = dados_atual["id_avaliacao"]

    ultimas: dict[tuple, dict] = {}
    for linha in _linhas_para_dicts(linhas_planilha):
        if linha["id_avaliacao"] == id_atual:
            continue
        if linha["paciente_chave"] != paciente["chave"] and normalizar(str(linha["paciente_nome"])) != nome_norm:
            continue
        if (linha["secao_id"], linha["campo_id"]) not in evolutivos or linha["lado"] not in ("D", "E"):
            continue
        if not _numero(linha["valor_num"]):
            continue
        ultimas[(linha["id_avaliacao"], linha["secao_id"], linha["campo_id"], linha["lado"])] = linha

    por_campo: dict[tuple[str, str], dict[dt.date, dict]] = {}
    for linha in sorted(ultimas.values(), key=lambda l: str(l["criado_em"])):
        try:
            data = dt.date.fromisoformat(str(linha["data_avaliacao"])[:10])
        except ValueError:
            continue
        ponto = por_campo.setdefault((linha["secao_id"], linha["campo_id"]), {}).setdefault(data, {"D": None, "E": None})
        ponto[linha["lado"]] = float(linha["valor_num"])

    data_atual = dados_atual.get("data_avaliacao") or dt.date.today()
    for secao in dados_atual["secoes"]:
        if secao["tipo"] != "secao":
            continue
        for campo in secao["definicao"].campos:
            if (secao["id"], campo.id) not in evolutivos:
                continue
            valor = secao["campos"].get(campo.id)
            if not isinstance(valor, dict):
                continue
            chaves = ("D", "E") if campo.tipo == "bilateral_numero" else ("D_seg", "E_seg")
            d, e = (valor.get(k) for k in chaves)
            if _numero(d) or _numero(e):
                por_campo.setdefault((secao["id"], campo.id), {})[data_atual] = {
                    "D": float(d) if _numero(d) else None, "E": float(e) if _numero(e) else None,
                }

    return {
        chave: [{"data": data, **valores} for data, valores in sorted(pontos.items())]
        for chave, pontos in por_campo.items()
    }


# --------------------------------------------------------------------------- rede
def carregar() -> list[list]:
    from avaliacao_fisio.google_sheets_client import GoogleSheetsClient

    return GoogleSheetsClient().ler_intervalo(_sheet_id(), _INTERVALO)


def salvar(dados: dict, usuario: str) -> int:
    """Acrescenta as linhas desta avaliação (com o cabeçalho, se a planilha
    ainda estiver vazia). Devolve quantas linhas gravou."""
    from avaliacao_fisio.google_sheets_client import GoogleSheetsClient

    linhas = linhas_da_avaliacao(dados, usuario)
    if not linhas:
        return 0
    cliente = GoogleSheetsClient()
    if not cliente.ler_intervalo(_sheet_id(), "A1:A1"):
        cliente.escrever_intervalo(_sheet_id(), _INTERVALO, [COLUNAS])
    cliente.acrescentar_linhas(_sheet_id(), _INTERVALO, linhas)
    return len(linhas)
