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

## Estrutura

- `src/avaliacao_fisio/protocolos.py` — definição dos campos de cada
  protocolo (MMII, MMSS) e das seções compartilhadas (Dados do Paciente,
  Dor, Testes Adicionais, Registros Fotográficos, Classificação de
  Risco, Responsável).
- `src/avaliacao_fisio/wizard.py` — motor do wizard (navegação,
  formulários, coleta das respostas).
- `src/avaliacao_fisio/pdf_avaliacao.py` — geração do PDF final
  (reportlab).
- `src/avaliacao_fisio/auth.py` — tela de login opcional (usuário/senha
  via Secrets).
- `src/avaliacao_fisio/feegow_client.py` — busca de pacientes cadastrados
  (autocomplete do Nome completo).
- `src/avaliacao_fisio/estilo.py` — tema visual fixo (dark, fonte Inter,
  botões grandes pra toque).
- `assets/logo.png` — logo da Sport Labs.

## Escopo da v1

Gera o **formulário preenchido** (dados brutos em tabela), sem texto
interpretativo/diagnóstico. Uma camada narrativa (correlação clínica,
diagnóstico cinético-funcional) é uma fase futura — só entra com
confirmação explícita, não está neste escopo.

O protocolo de Membros Superiores foi reconstruído a partir de um
formulário preenchido à mão (sem PDF limpo de referência) — vale
validar o layout fino com a prática real antes de considerar fechado.
