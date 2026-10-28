"""PDFs das avaliações guardados numa pasta do Google Drive, pra o fisioterapeuta
abrir a avaliação anterior numa reavaliação.

Grava como a conta Google da clínica (OAuth com refresh token), porque conta de
serviço não tem cota de armazenamento e o Google recusa criar arquivos ("Service
Accounts do not have storage quota"). A pasta e o token são criados uma vez por
`scripts/autorizar_drive.py`; os 4 valores vão nos Secrets como chaves de nível
raiz, antes de qualquer `[tabela]`: `GOOGLE_DRIVE_CLIENT_ID`,
`GOOGLE_DRIVE_CLIENT_SECRET`, `GOOGLE_DRIVE_REFRESH_TOKEN`, `GOOGLE_DRIVE_PASTA_ID`.

Pasta única e plana: o nome do arquivo começa pelo paciente (fica agrupado na
ordem alfabética) e o vínculo com o paciente está nas propriedades do arquivo
(`appProperties`), não no nome. Regravar a mesma avaliação (voltar, corrigir e
gerar de novo) atualiza o arquivo em vez de duplicar. Nunca apaga nada.

Falha de rede/credencial/cota NUNCA bloqueia o PDF: quem chama trata a exceção.
"""
from __future__ import annotations

import datetime as dt
import io
import re

import streamlit as st

from avaliacao_fisio.config import obter_config
from avaliacao_fisio.historico import normalizar
from avaliacao_fisio.protocolos import PROTOCOLOS

# `drive.file`: o app só enxerga o que ele mesmo criou (a pasta e os PDFs), nada mais do Drive.
_ESCOPO = ["https://www.googleapis.com/auth/drive.file"]
_TOKEN_URI = "https://oauth2.googleapis.com/token"
_CAMPOS = "id, name, appProperties, createdTime, modifiedTime"
_MAX_PROP = 90  # appProperties: chave + valor somam no máximo 124 bytes


_CHAVES_OAUTH = ("GOOGLE_DRIVE_CLIENT_ID", "GOOGLE_DRIVE_CLIENT_SECRET", "GOOGLE_DRIVE_REFRESH_TOKEN")


def configurado() -> bool:
    return bool(obter_config("GOOGLE_DRIVE_PASTA_ID")) and all(obter_config(c) for c in _CHAVES_OAUTH)


def _pasta_id() -> str:
    valor = obter_config("GOOGLE_DRIVE_PASTA_ID")
    if not valor:
        raise RuntimeError("GOOGLE_DRIVE_PASTA_ID não configurado nos Secrets.")
    return valor


@st.cache_resource(show_spinner=False)
def _servico():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    if not all(obter_config(c) for c in _CHAVES_OAUTH):
        raise RuntimeError("Credenciais OAuth do Drive não configuradas nos Secrets.")
    credenciais = Credentials(
        None, refresh_token=obter_config("GOOGLE_DRIVE_REFRESH_TOKEN"), token_uri=_TOKEN_URI,
        client_id=obter_config("GOOGLE_DRIVE_CLIENT_ID"), client_secret=obter_config("GOOGLE_DRIVE_CLIENT_SECRET"),
        scopes=_ESCOPO,
    )
    return build("drive", "v3", credentials=credenciais, cache_discovery=False)


# --------------------------------------------------------------------------- pura
def nome_do_arquivo(dados: dict) -> str:
    data_av = dados.get("data_avaliacao") or dt.date.today()
    protocolo = PROTOCOLOS[dados["protocolo_id"]].nome
    paciente = re.sub(r"[\\/:*?\"<>|]", " ", dados["paciente"]["nome"] or "paciente")
    return f"{' '.join(paciente.split())} - {data_av.strftime('%Y-%m-%d')} - {protocolo}.pdf"


def propriedades(dados: dict) -> dict[str, str]:
    data_av = dados.get("data_avaliacao") or dt.date.today()
    paciente = dados["paciente"]
    return {
        "id_avaliacao": str(dados["id_avaliacao"]),
        "paciente_chave": paciente["chave"][:_MAX_PROP],
        "paciente_nome": normalizar(paciente["nome"])[:_MAX_PROP],
        "data_avaliacao": data_av.strftime("%Y-%m-%d"),
        "protocolo": dados["protocolo_id"],
        "tipo_avaliacao": dados["tipo_avaliacao"],
    }


def _aspas(valor: str) -> str:
    return valor.replace("\\", "\\\\").replace("'", "\\'")


def _filtro_propriedade(chave: str, valor: str) -> str:
    return f"appProperties has {{ key='{chave}' and value='{_aspas(valor)}' }}"


def _resumir(arquivo: dict) -> dict:
    props = arquivo.get("appProperties") or {}
    protocolo = PROTOCOLOS.get(props.get("protocolo", ""))
    return {
        "id": arquivo["id"],
        "nome": arquivo["name"],
        "id_avaliacao": props.get("id_avaliacao", ""),
        "data": props.get("data_avaliacao") or str(arquivo.get("createdTime", ""))[:10],
        "protocolo": protocolo.nome if protocolo else props.get("protocolo", ""),
        "tipo": props.get("tipo_avaliacao", ""),
    }


# --------------------------------------------------------------------------- rede
def _procurar(consulta: str) -> list[dict]:
    resposta = _servico().files().list(
        q=f"'{_pasta_id()}' in parents and trashed = false and {consulta}",
        fields=f"files({_CAMPOS})", pageSize=100, orderBy="createdTime desc",
        supportsAllDrives=True, includeItemsFromAllDrives=True, corpora="allDrives",
    ).execute()
    return resposta.get("files", [])


def salvar_pdf(pdf: bytes, dados: dict) -> dict:
    """Cria o PDF na pasta (ou atualiza, se esta avaliação já foi guardada).
    Devolve {"id", "nome", "atualizado"}."""
    from googleapiclient.http import MediaIoBaseUpload

    servico = _servico()
    midia = MediaIoBaseUpload(io.BytesIO(pdf), mimetype="application/pdf", resumable=True)
    existentes = _procurar(_filtro_propriedade("id_avaliacao", str(dados["id_avaliacao"])))
    corpo = {"name": nome_do_arquivo(dados), "appProperties": propriedades(dados)}
    if existentes:
        arquivo = servico.files().update(
            fileId=existentes[0]["id"], body=corpo, media_body=midia, fields="id, name", supportsAllDrives=True,
        ).execute()
        atualizado = True
    else:
        corpo["parents"] = [_pasta_id()]
        arquivo = servico.files().create(
            body=corpo, media_body=midia, fields="id, name", supportsAllDrives=True,
        ).execute()
        atualizado = False
    listar_cache.clear()
    return {"id": arquivo["id"], "nome": arquivo["name"], "atualizado": atualizado}


def listar(paciente_chave: str, paciente_nome: str) -> list[dict]:
    """Avaliações guardadas do paciente (pelo ID do Feegow ou pelo nome sem
    acento/caixa — mesma regra do histórico), da mais recente pra mais antiga."""
    consulta = "(" + " or ".join([
        _filtro_propriedade("paciente_chave", paciente_chave[:_MAX_PROP]),
        _filtro_propriedade("paciente_nome", normalizar(paciente_nome)[:_MAX_PROP]),
    ]) + ")"
    achados = [_resumir(a) for a in _procurar(consulta)]
    return sorted(achados, key=lambda a: a["data"], reverse=True)


@st.cache_data(ttl=120, show_spinner=False)
def listar_cache(paciente_chave: str, paciente_nome: str) -> list[dict]:
    return listar(paciente_chave, paciente_nome)


def baixar(arquivo_id: str) -> bytes:
    """Conteúdo do PDF. Só aceita arquivo que está dentro da pasta configurada."""
    servico = _servico()
    meta = servico.files().get(fileId=arquivo_id, fields="parents", supportsAllDrives=True).execute()
    if _pasta_id() not in (meta.get("parents") or []):
        raise PermissionError("Arquivo fora da pasta de avaliações.")
    return servico.files().get_media(fileId=arquivo_id, supportsAllDrives=True).execute()
