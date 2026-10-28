"""Autoriza o app a guardar os PDFs no Drive da conta Google da clínica (uma vez só).

1. Abre o navegador pra você entrar com a conta da clínica e aprovar.
2. Cria a pasta privada "Avaliações Cinético Funcionais" nessa conta.
3. Grava os 4 valores dos Secrets num arquivo `*_para_colar.txt` (ignorado pelo Git).
   Nada é impresso na tela. Cole o conteúdo nos Secrets (local e Streamlit Cloud),
   no topo, antes de qualquer `[tabela]`, e apague o arquivo.

Uso (na raiz do projeto):
    ./.venv/Scripts/python.exe scripts/autorizar_drive.py [caminho/do/client_secret.json]

Precisa de `pip install google-auth-oauthlib` (só aqui, o app em si não usa).
"""
import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

ESCOPO = ["https://www.googleapis.com/auth/drive.file"]
NOME_PASTA = "Avaliações Cinético Funcionais"
RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / ".streamlit" / "drive_secrets_para_colar.txt"


def main() -> None:
    caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / ".streamlit" / "client_secret.json"
    if not caminho.exists():
        raise SystemExit(f"Não achei o arquivo de credencial OAuth em {caminho}")
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    cliente = dados.get("installed") or dados.get("web") or {}

    fluxo = InstalledAppFlow.from_client_secrets_file(str(caminho), ESCOPO)
    # offline + consent: garante o refresh token mesmo se a conta já autorizou antes.
    # Não abre o navegador sozinho (pode cair no perfil/conta errada): imprime o link
    # pra colar no navegador onde a conta da clínica está conectada.
    credenciais = fluxo.run_local_server(
        port=8788, open_browser=False, access_type="offline", prompt="consent",
        authorization_prompt_message="Abra este link no navegador com a conta da clinica:\n{url}\n",
        success_message="Autorizado. Pode fechar esta aba.",
    )
    if not credenciais.refresh_token:
        raise SystemExit("O Google não devolveu o refresh token. Revogue o acesso do app na conta e rode de novo.")

    drive = build("drive", "v3", credentials=credenciais, cache_discovery=False)
    pasta = drive.files().create(
        body={"name": NOME_PASTA, "mimeType": "application/vnd.google-apps.folder"}, fields="id",
    ).execute()

    SAIDA.parent.mkdir(exist_ok=True)
    SAIDA.write_text(
        "\n".join([
            f'GOOGLE_DRIVE_CLIENT_ID = "{cliente["client_id"]}"',
            f'GOOGLE_DRIVE_CLIENT_SECRET = "{cliente["client_secret"]}"',
            f'GOOGLE_DRIVE_REFRESH_TOKEN = "{credenciais.refresh_token}"',
            f'GOOGLE_DRIVE_PASTA_ID = "{pasta["id"]}"',
        ]) + "\n",
        encoding="utf-8",
    )
    print(f"Pronto. Pasta '{NOME_PASTA}' criada no seu Drive.")
    print(f"Valores dos Secrets salvos em: {SAIDA}")


if __name__ == "__main__":
    main()
