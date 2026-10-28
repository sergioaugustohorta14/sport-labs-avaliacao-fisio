# Tablet de Avaliação — Sport Labs

App Streamlit (wizard passo a passo) pra coletar os dados de uma
avaliação fisioterapêutica (Membros Inferiores ou Membros Superiores) e
gerar um PDF de relatório no final. A impressão é manual: o PDF é
baixado e aberto no visualizador nativo do tablet, que já tem o caminho
pra impressora da clínica.

## Rodar localmente

```bash
# Criar e ativar o ambiente virtual (uma vez só)
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt

# Rodar o app
./.venv/Scripts/python.exe -m streamlit run src/avaliacao_fisio/app.py
```

## Login (opcional)

Sem nenhuma configuração, o app libera o acesso direto (modo
desenvolvimento — aparece um aviso amarelo na barra lateral). Pra exigir
usuário/senha (importante antes de publicar num link público, ex.
Streamlit Community Cloud), crie `.streamlit/secrets.toml` na raiz do
projeto (mesmo padrão do Painel Feegow — **nunca commitar esse arquivo**,
já está no `.gitignore`):

```toml
[auth.users]
recepcao = "uma-senha-forte-aqui"
fisio = "outra-senha-forte-aqui"
```

Cada linha é um usuário. Ao publicar no Streamlit Community Cloud, esses
mesmos valores vão na aba "Secrets" das configurações do app (não no
arquivo).

## Busca de paciente (API Feegow)

O campo "Nome completo" (seção Dados do Paciente) sugere pacientes já
cadastrados no Feegow, com busca difusa — mesmo token de API já usado no
Painel Feegow (Feegow-Analytics). Sem o token configurado, o campo
simplesmente vira digitação livre (nenhuma funcionalidade quebra).
Adicione ao `.streamlit/secrets.toml`:

```toml
FEEGOW_API_TOKEN = "o-token-jwt-aqui"
FEEGOW_API_BASE_URL = "https://api.feegow.com/v1/api"
```

**Limitação conhecida da API** (documentada na skill `integracao_feegow`
do Feegow-Analytics, confirmada aqui): `GET /patient/list` não pagina de
verdade (sempre devolve os mesmos ~500 cadastros mais antigos) e não
filtra por nome no servidor — por isso a lista é buscada uma vez
(cacheada 24h) e filtrada no cliente. Pacientes fora desses ~500 não
aparecem como sugestão, mas o campo aceita digitar o nome livremente
nesse caso (nunca trava o preenchimento).

## Histórico e gráficos de evolução (Google Sheets)

Ao gerar o PDF, o app grava os **testes medidos** (força, amplitude,
saltos, equilíbrio, tempos) numa planilha Google, e nas reavaliações do
mesmo paciente o PDF ganha gráficos de evolução data a data. Dados do
paciente, dor, fotos e vídeo não vão pra planilha. Sem a configuração
abaixo o app funciona normalmente, só sem os gráficos de evolução.

1. Crie a planilha e compartilhe com o e-mail da conta de serviço do
   Google como **Editor**.
2. Nos Secrets (local e Streamlit Cloud), com a chave de nível raiz
   **antes** de qualquer `[tabela]`:

```toml
GOOGLE_AVALIACOES_SHEET_ID = "id-da-planilha"

[gcp_service_account]
# conteúdo do JSON da conta de serviço (type, project_id, private_key, ...)
```

## PDFs guardados no Google Drive

Ao gerar o PDF, o app guarda uma cópia numa pasta do Drive da clínica. Na
seção Dados do Paciente, ao escolher um paciente que já tem avaliações
guardadas, aparece "Avaliações anteriores deste paciente" com botão para
abrir/baixar cada PDF (útil na reavaliação). Gerar de novo a mesma avaliação
atualiza o arquivo, não duplica.

1. Crie a pasta e compartilhe com o e-mail da conta de serviço do Google
   como **Editor**. A pasta deve ser privada (o PDF tem dado de saúde e fotos).
2. Ative a **Google Drive API** no mesmo projeto do Google Cloud da conta de serviço.
3. Nos Secrets (local e Streamlit Cloud), como chave de nível raiz **antes**
   de qualquer `[tabela]`:

```toml
GOOGLE_DRIVE_PASTA_ID = "id-da-pasta"
```

Sem isso o app funciona normalmente, só sem guardar/consultar os PDFs. Falha
do Drive nunca impede o PDF.

## Protocolo de Corrida (RunScribe)

O protocolo "Corrida" importa as métricas por pé (cadência, tempo de contato,
potência, impacto, pronação...) de uma corrida registrada no RunScribe. Precisa
das credenciais da conta nos Secrets, como chaves de nível raiz (antes de
qualquer `[tabela]`):

```toml
RUNSCRIBE_EMAIL = "e-mail-da-conta"
RUNSCRIBE_PASSWORD = "senha-da-conta"
```

Sem elas, a seção de Corrida continua funcionando para preenchimento manual.

## Relatório do Kinology

Na tela de Revisão, é possível enviar o PDF gerado no Kinology e escolher
as páginas que entram no fim do PDF do paciente (sem alteração).

## Estrutura

- `src/avaliacao_fisio/protocolos.py` — definição dos campos de cada
  protocolo (MMII, MMSS) e das seções compartilhadas (Dados do Paciente,
  Dor, Testes Adicionais, Registros Fotográficos, Classificação de
  Risco, Responsável).
- `src/avaliacao_fisio/wizard.py` — motor do wizard (navegação,
  formulários, coleta das respostas).
- `src/avaliacao_fisio/pdf_avaliacao.py`, `pdf_base.py`, `pdf_graficos.py`
  — geração do PDF final (reportlab) e gráficos de evolução.
- `src/avaliacao_fisio/historico.py`, `google_sheets_client.py` —
  histórico das avaliações na planilha Google.
- `src/avaliacao_fisio/pdf_anexos.py` — anexo de páginas do Kinology.
- `src/avaliacao_fisio/pdfs_drive.py` — cópia dos PDFs na pasta do Drive e
  consulta das avaliações anteriores do paciente.
- `src/avaliacao_fisio/assimetria.py` — regra de assimetria (10% / 20%).
- `src/avaliacao_fisio/auth.py` — tela de login opcional (usuário/senha
  via Secrets).
- `src/avaliacao_fisio/feegow_client.py` — busca de pacientes cadastrados
  (autocomplete do Nome completo).
- `src/avaliacao_fisio/estilo.py` — tema visual fixo (dark, fonte Inter,
  botões grandes pra toque).
- `assets/logo.png` — logo da Sport Labs.

## Escopo da v1

Gera o **formulário preenchido** (campos vazios omitidos), sem texto
interpretativo/diagnóstico. Uma camada narrativa (correlação clínica,
diagnóstico cinético-funcional) é uma fase futura — só entra com
confirmação explícita, não está neste escopo.

O protocolo de Membros Superiores foi reconstruído a partir de um
formulário preenchido à mão (sem PDF limpo de referência) — vale
validar o layout fino com a prática real antes de considerar fechado.
