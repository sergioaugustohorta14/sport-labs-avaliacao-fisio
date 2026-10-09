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

## Estrutura

- `src/avaliacao_fisio/protocolos.py` — definição dos campos de cada
  protocolo (MMII, MMSS) e das seções compartilhadas (Dados do Paciente,
  Dor, Testes Adicionais, Classificação de Risco, Responsável).
- `src/avaliacao_fisio/wizard.py` — motor do wizard (navegação,
  formulários, coleta das respostas).
- `src/avaliacao_fisio/pdf_avaliacao.py` — geração do PDF final
  (reportlab).
- `src/avaliacao_fisio/auth.py` — tela de login opcional (usuário/senha
  via Secrets).
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
