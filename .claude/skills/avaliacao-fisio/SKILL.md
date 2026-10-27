---
name: avaliacao-fisio
description: Documentação técnica completa do "Tablet de Avaliação" (Sport Labs) — app Streamlit tipo wizard que coleta uma avaliação fisioterapêutica (MMII/MMSS) e gera PDF. Use sempre que for mexer nesse projeto (pasta D:\Sport Labs\Projeto-Avaliacao-Fisio).
---

# Tablet de Avaliação — Sport Labs

App Streamlit standalone pra rodar num tablet da clínica: um wizard passo
a passo que coleta uma avaliação fisioterapêutica (protocolo Membros
Inferiores ou Membros Superiores) e gera um PDF "formulário preenchido"
no final. Projeto separado do Painel Feegow (`Feegow-Analytics`), com
repo git próprio, mas reaproveitando os padrões visuais/técnicos
validados lá (ver skill `feegow-analytics` naquele projeto).

- **Pasta do projeto:** `D:\Sport Labs\Projeto-Avaliacao-Fisio`
- **Repositório:** https://github.com/sergioaugustohorta14/sport-labs-avaliacao-fisio (público)
- **Hospedagem:** Streamlit Community Cloud, deploy automático a cada `git push` na `main`. Python 3.12 (não 3.14 — risco de faltar wheel pré-compilado do reportlab).
- **Login:** usuário/senha via Secrets (`[auth.users]`) — ver seção "Login" abaixo. **Credenciais NÃO ficam documentadas aqui de propósito** (este repositório é público no GitHub) — consultar os Secrets do Streamlit Cloud ou a memória local do Sergio. **A URL pública do app também não está anotada aqui** (nunca foi colada de volta nesta sessão) — recuperar em share.streamlit.io e, se possível, atualizar esta skill com ela.
- A impressão é manual: o PDF é baixado e aberto no visualizador nativo do tablet, que já segue pro caminho normal de impressão da clínica — não há impressão "silenciosa"/kiosk no escopo.

## Escopo da v1 (importante)

Gera o **formulário preenchido** — reproduz os campos em tabela/PDF, sem
nenhuma camada interpretativa/diagnóstica (sem correlação clínica, sem
objetivos terapêuticos redigidos). Essa camada narrativa é uma **fase 2
futura, explicitamente não iniciada** — só começar com confirmação
direta do Sergio, mesma preferência já registrada nas outras skills dele.

Também **sem persistência/histórico**: o app só coleta → gera PDF →
baixa. Não grava em planilha/banco nenhuma avaliação — é stateless além
da sessão atual do navegador. Consequência real: vídeo anexado
(`video_upload`) só vive na sessão; se fechar a aba sem gerar o PDF,
perde (avisado no `help=` do campo, mas reforçar se o Sergio perguntar
"cadê o vídeo depois").

## Arquitetura do código

```
src/avaliacao_fisio/
├── app.py              # Ponto de entrada: set_page_config + tema + login + wizard.render()
├── auth.py             # Tela de login (usuário/senha via st.secrets[auth][users])
├── estilo.py           # Tema visual (tokens de cor, injetar_tema(), CSS de todos os widgets)
├── protocolos.py       # MODELO de dados: Campo/Secao/SecaoRepetivel/SecaoDor/SecaoFotos/Protocolo
├── wizard.py           # Motor do wizard: navegação, renderização dos campos, coleta das respostas
├── feegow_client.py    # Busca de pacientes cadastrados no Feegow (autocomplete do Nome completo)
└── pdf_avaliacao.py    # Geração do PDF final (reportlab)
assets/
└── logo.png            # Logo com fundo transparente (preto/branco/dourado)
```

`protocolos.py` é só o MODELO — `wizard.py` usa essas definições pra
desenhar os widgets e `pdf_avaliacao.py` usa as mesmas pra montar as
tabelas do PDF. A ordem das seções/campos em `protocolos.py` é a ordem
real que aparece nos dois lugares (adicionar um campo = editar só esse
arquivo, os outros dois já têm dispatch genérico por `campo.tipo`).

### Modelo de dados (`protocolos.py`)

`Campo(id, rotulo, tipo, unidade=None, observacao=False, opcoes=None, ajuda=None, casas_decimais=1)`.
Tipos de campo suportados (cada um tem um branch espelhado em
`wizard._renderizar_campo`/`_ler_campo` e em `pdf_avaliacao._tabela_secao_fixa`):

| tipo | widget | observação |
|---|---|---|
| `unico_texto` | `st.text_input` | |
| `unico_numero` | `st.number_input` | usa `casas_decimais` pro `step`/`format` |
| `data` | `st.date_input` | formato `DD/MM/YYYY` |
| `idade_calculada` | nenhum (`st.caption`) | deriva de `data_nascimento` (campo anterior, mesma seção) |
| `lado_unico` | `st.radio` Direito/Esquerdo | dispara scroll-avançar |
| `busca_paciente` | `st.selectbox` com `accept_new_options=True` | autocomplete Feegow, ver seção própria |
| `bilateral_numero` | 2× `st.number_input` (D/E) | pode ter `observacao=True` (campo de texto extra) |
| `bilateral_sinal` | 2× `st.radio` +/- (D/E) | dispara scroll-avançar |
| `bilateral_score` | 2× `st.radio` 1/2/3 (D/E) | dispara scroll-avançar |
| `bilateral_tempo` / `unico_tempo` | 2× `st.number_input` (min, seg) por lado | formatado como string `"1'30\""` na coleta |
| `foto_unica` | `st.camera_input` + legenda | não repetível, 1 foto fixa dentro da seção |
| `video_upload` | `st.file_uploader` (mp4/mov/avi/mkv) | **não entra no PDF**, só anexo de sessão |
| `opcoes` | `st.radio` horizontal | lista livre em `campo.opcoes` |

Seções compartilhadas entre MMII e MMSS (reaproveitadas, não duplicadas):
`DADOS_PACIENTE`, `DOR` (`SecaoDor` — VAS repouso/atividade + lista
repetível região/lado/intensidade, substitui o diagrama corporal
desenhado à mão do papel), `TESTES_ADICIONAIS` (`SecaoRepetivel` livre —
cobre testes fora do formulário padrão, ex. Arremesso de 6M, CK-CUEST),
`FOTOS` (`SecaoFotos` — registros fotográficos gerais, repetíveis),
`CLASSIFICACAO_RISCO`, `RESPONSAVEL`.

**PROTOCOLO_MMII** (12 seções): Dados do Paciente → Mobilidade e
Flexibilidade → Força → Controle Motor e Estabilidade → Análise de
Movimento (inclui foto própria + vídeo) → Y-Balance Test → Hop Test →
Dor → Testes Adicionais → Registros Fotográficos → Classificação de
Risco → Responsável. Extraído do formulário oficial em PDF
(`Avaliacao_Funcional_MMII_SportLabs.pdf`).

**PROTOCOLO_MMSS** (9 seções): Dados do Paciente → Avaliação de Membros
Superiores → Análise de Movimento (Discinese Escapular) → Y-Balance Test
(Membro Superior) → Dor → Testes Adicionais → Registros Fotográficos →
Classificação de Risco → Responsável. **Reconstruído a partir de uma
foto de formulário preenchido à mão (sem PDF limpo de referência)** —
ainda vale validar o layout fino com o uso real antes de considerar
100% fechado.

Dinamometria e Termografia existiam na v1 original e foram **removidas**
no lote de 13/10/2026 (pedido da equipe de fisioterapeutas) — não
recriar sem pedido novo.

### Motor do wizard (`wizard.py`)

- `st.session_state["respostas"]` é a ÚNICA fonte de verdade — nunca
  confiar na `key` do widget pra persistência. **Achado estrutural
  central deste projeto:** o Streamlit apaga (`prune`) o valor de um
  widget do `session_state` quando esse widget não é desenhado numa
  execução; como aqui cada tela desenha só a seção atual, um wizard que
  dependesse só da `key` do widget perderia os dados das seções
  anteriores ao avançar. Por isso todo widget é lido pelo valor de
  RETORNO da própria chamada e gravado manualmente via `_guardar()`.
- Navegação: `st.session_state["etapa"]` (inteiro) — 0 é a tela de
  seleção de protocolo, 1..N são as seções do protocolo escolhido,
  N+1 é a Revisão. `_passo_selecao_protocolo()`, seção normal via
  `renderizar_secao*`, `_passo_revisao()`.
  - **Teclas duplicadas de propósito**: dentro de uma `SecaoRepetivel`/
    `SecaoDor`/`SecaoFotos`, cada linha usa `_chave(secao.id, f"linha{i}", col_id)` — remover
    uma linha (`➖`) precisa apagar essas chaves específicas de
    `respostas`, não só decrementar o contador (`st.session_state[chave_n]`).
- `coletar_respostas(protocolo)` lê `respostas` de volta num dict limpo
  (`{"secoes": [{"tipo": "secao"|"repetivel"|"dor"|"fotos", ..., "definicao": <objeto original>}]}`),
  desacoplado do Streamlit — é isso que `pdf_avaliacao.gerar()` consome.
  Cada item de seção carrega `"definicao"` (o objeto `Secao`/etc. de
  `protocolos.py`) pra quem monta a tabela saber rótulos/tipos sem ter
  que repetir essa informação no dict de dados.
- `_rolar_para_topo()` / `_rolar_offset()`: usam `components.html()`
  (iframe real) porque `st.markdown(unsafe_allow_html=True)` **não**
  executa `<script>`. O conteúdo HTML precisa variar a cada chamada
  (embute `time.time()`) — com HTML idêntico o Streamlit não recarrega o
  iframe entre reruns e o script só dispara na primeira vez.
  - `_rolar_para_topo` só é chamado quando `st.session_state["_ultima_etapa_rolada"]`
    muda (bug real corrigido 13/10/2026: rolar em todo rerun fazia a
    tela subir sozinha a cada campo preenchido dentro da mesma seção).
  - `_rolar_offset` (scroll-avançar ao marcar um campo de clique único)
    usa `scrollBy` — **incremental, não idempotente** como o reset pro
    topo (`scrollTop = 0`); por isso dispara só UMA vez por sinalização
    (`st.session_state["_avancar_scroll"]`, setada em `_guardar(..., avancar=True)`
    e consumida com `.pop()`), nunca num loop de retry.
- Campo `busca_paciente`: ao escolher um paciente conhecido, precisa
  escrever o valor de `data_nascimento` tanto no dict `respostas` quanto
  **direto na key do widget** (`st.session_state[f"w__{chave_nasc}"]`) —
  o Streamlit ignora `value=` de um widget cuja `key` já existe no
  `session_state`. Pelo mesmo motivo, `_renderizar_campo` (tipo `"data"`)
  evita passar `value=` quando a key já existe, pra não disparar o aviso
  do Streamlit sobre os dois serem usados juntos.
- `_barra_assimetria(d, e)`: só na tela de Revisão (não no PDF). Fórmula
  `abs(d-e)/max(|d|,|e|)*100` — <10% baixa chance de lesão, 10–20% média,
  >20% alta (valores confirmados com o Sergio, 13/10/2026). Barra com
  gradiente verde→dourado→vermelho + seta posicionada via `calc()`.
- `_formatar_valor()`/`_valor_ausente_html()`: só a tela de Revisão
  (nunca o PDF) — devolve HTML com "Não preenchido" em dourado
  (`COR_ACENTO`) em vez de "—", exigido pela diretoria. Texto livre do
  paciente passa por `html.escape()` antes de entrar no HTML.

### Busca de paciente no Feegow (`feegow_client.py`)

Campo "Nome completo" é um autocomplete sobre `GET /patient/list`,
reaproveitando o **mesmo token de API** já usado pelo Painel Feegow
(`Feegow-Analytics`, confirmado com o Sergio em 10/10/2026 que pode
reusar). Limitações reais da API (mesmas documentadas na skill
`integracao_feegow` do outro projeto, confirmadas aqui de forma
independente):

- `/patient/list` **não pagina de verdade** — sempre devolve os mesmos
  ~500 cadastros mais antigos por `patient_id`; não filtra por `nome` no
  servidor (parâmetro aceito, mas ignorado). Por isso a lista inteira é
  buscada uma vez (`_listar_pacientes_bruto()`, `@st.cache_data(ttl=86400)`)
  e o filtro por nome é feito no cliente via `st.selectbox` com
  `accept_new_options=True` — paciente fora dos ~500 não aparece como
  sugestão, mas digitar o nome livremente sempre funciona (nunca trava
  o preenchimento).
- **Sem campo de status ativo/inativo** exposto pela API — confirmado
  empiricamente comparando dois cadastros reais com o mesmo nome
  ("WARLEI CANTARERO", um ativo ID 2753, um inativo ID 1302): nenhum
  campo do payload distingue os dois. Por isso o rótulo mostra o ID
  entre parênteses (`"Nome (ID 1234)"`) pra desambiguar — e selecionar
  um paciente conhecido autopreenche `data_nascimento` a partir do
  próprio campo `nascimento` do bulk (`AAAA-MM-DD`), sem chamada extra.
- Se a API falhar ou o token não estiver configurado,
  `_listar_pacientes_bruto()` devolve lista vazia silenciosamente — o
  campo degrada pra digitação livre, nunca quebra o wizard.
- **Confirmado em produção (27/10/2026)**: `FEEGOW_API_TOKEN` e
  `FEEGOW_API_BASE_URL` já estão nos Secrets do Streamlit Cloud, na
  ordem certa (antes do bloco `[auth.users]`) — a busca de paciente
  funciona no app publicado, não só local.

### PDF (`pdf_avaliacao.py`)

Mesma espinha dorsal de `feegow_analytics.reports.pdf_repasses`:
reportlab puro-Python (sem wkhtmltopdf/weasyprint — roda sem
configuração extra no Streamlit Community Cloud), faixa escura
`#322f33` com logo centralizado, células `Paragraph` pra quebrar texto
longo (string pura numa `Table` não quebra linha, só transborda), linha
de assinatura "Fisioterapeuta Responsável" no rodapé.

- Uma seção do protocolo pode gerar até 3 blocos no PDF:
  tabela bilateral (D/E/Unidade), tabela de campos únicos, e elementos
  de foto/vídeo — `_tabela_secao_fixa()` separa os `campo.tipo` em
  `campos_bilaterais`/`campos_unicos`/`campos_fotografia` antes de montar.
- `video_upload` **nunca aparece como vídeo no PDF** (reportlab não
  reproduz vídeo) — só uma linha de texto dizendo que foi anexado (ou
  não) na sessão.
- Nome do arquivo: `avaliacao_<protocolo_id>_<nome_paciente_sem_espaco>_<ddmmaaaa>.pdf`.

### Login (`auth.py`)

Mesmo padrão do `feegow_analytics.reports.auth`: usuário/senha em
`st.secrets["auth"]["users"]` (TOML `[auth.users]`), nunca no código.
**Sem usuários configurados, libera acesso direto** (modo
desenvolvimento, aviso amarelo na sidebar) — não é bug, é intencional
pra rodar local sem precisar configurar nada.

- Credenciais atuais: **propositalmente não documentadas aqui** — repositório público; consultar os Secrets do Streamlit Cloud ou a memória local do Sergio.
- **Gotcha de `secrets.toml`**: a resolução do Streamlit depende do
  diretório de trabalho do PROCESSO no momento de rodar `streamlit run`,
  não do caminho do script — sempre `cd` pra raiz do projeto antes.
  Mesmo motivo faz top-level keys (`FEEGOW_API_TOKEN` etc.) precisarem
  vir ANTES de qualquer `[tabela]` no TOML, senão ficam aninhadas lá
  dentro silenciosamente.
- Proteção básica (senha em texto simples, sem hashing/rate-limit) —
  suficiente contra acesso casual ao link público, não é nível
  corporativo. Nunca reusar essas senhas em outro sistema.

### Identidade visual (`estilo.py`)

Paleta própria do app: **preto / branco / dourado** — decisão do Sergio
(09/10/2026, mockup externo) confirmada depois (14/10/2026) como a
identidade visual REAL da marca Sport Labs, diferente do cinza `#36363a`
usado no Painel Feegow (que foi aprovação pontual da diretoria só pra
aquele painel). Esse mesmo tema foi **portado pro Feegow-Analytics em
15/10/2026** (commit `d0e8e83` lá) — ver skill `feegow-analytics` se
precisar comparar.

```python
COR_FUNDO = "#121212"
COR_SURFACE = "#1a1a1a"
COR_TEXTO = "#f3efe6"
COR_MUTED = "#9c9690"
COR_BORDA = "rgba(212, 175, 95, 0.35)"
COR_GLOW = "rgba(212, 175, 95, 0.30)"
COR_TEXTO_SOBRE_GRADIENTE = "#1a1407"
COR_ACENTO = "#d4af5f"
GRADIENTE_PRIMARIO = "linear-gradient(90deg, #9c7a2e 0%, #f0cf7a 50%, #b8902f 100%)"
```
Fundo de página: `radial-gradient(circle at 50% 0%, #1c1c1c 0%, #121212 55%, #090909 100%)`.

**Achados de CSS/widget do Streamlit encontrados aqui (reconfirmar se a
versão do Streamlit mudar — nenhum é óbvio só lendo a doc):**

1. Widget com `key=` **ignora** `value=` depois da primeira
   renderização — forçar valor novo programaticamente exige escrever
   direto em `st.session_state[f"w__{chave}"]`.
2. A seta nativa de colapsar/expandir a sidebar só aparece com `:hover`
   do mouse (`visibility:hidden` por padrão) — **invisível em
   touchscreen de tablet**. Dois testids com estrutura DOM diferente:
   `stSidebarCollapseButton` (testid num wrapper) e
   `stExpandSidebarButton` (testid no próprio `<button>`); cor nativa do
   ícone (`rgba(49,51,63,0.6)`) é pra tema claro, some no fundo escuro.
3. O dropdown do `st.selectbox` renderiza num portal direto em `<body>`
   (`stSelectboxVirtualDropdown`), fora do container principal — não
   herda CSS nenhum do app, precisa de seletor próprio. O `<input>` de
   digitação (`accept_new_options=True`) também tem fundo transparente
   por padrão.
4. `st.date_input` nesta versão não usa `<input>` — é composto por
   `<span role="spinbutton">` (`stDateInputField`).
5. `st.slider` colore a bolinha/trilho via classes `efbyxodN` (labels
   estáveis do Emotion), não o hash `st-emotion-cache-*` que muda a cada
   build — frágil, reconfirmar se a versão mudar.
6. `st.button`/`st.form_submit_button` renderizam em wrappers CSS
   diferentes (`.stButton` vs `div[data-testid="stFormSubmitButton"]`) —
   uma regra "primary" que só mira um dos dois nunca pega o outro. Se
   precisar de duas folhas de estilo pro mesmo botão (ex. tema global +
   CSS local da tela de login), **nunca declarar a mesma propriedade nas
   duas** — preferir uma fonte única por propriedade (fundo/borda/cor/
   sombra/hover no tema global; largura/margem/padding/tipografia
   locais), mesmo que a teoria de especificidade CSS "devesse" resolver.
7. `components.html()` (iframe) é a única forma de rodar `<script>` de
   verdade no Streamlit — `st.markdown(unsafe_allow_html=True)` não
   executa. O iframe só recarrega/roda de novo se o HTML mudar entre
   reruns (embutir algo variável, ex. `time.time()`, num comentário).

**Método de verificação usado neste projeto (reusar sempre que mexer em
CSS fino de widget):** Playwright (`pip install playwright && playwright
install chromium`) no `.venv` do projeto, app local rodando
(`streamlit run ... --server.headless true --server.port 8765`),
navegador headless real pra clicar/inspecionar `getComputedStyle()`/DOM
e tirar screenshot — pego 3+ bugs reais que só ler o CSS não acharia
(date_input sem `<input>`, sidebar hover-only, portal do selectbox).
Câmera testável via `--use-fake-device-for-media-stream` +
`--use-fake-ui-for-media-stream`. Regressão funcional sem navegador via
`streamlit.testing.v1.AppTest` (percorre o wizard inteiro até o PDF,
inclusive setando widgets por `key` e lendo `at.session_state["pdf_bytes"]`
com `pypdf` pra confirmar que os dados chegaram no PDF final).

## Histórico de marcos

- **09/10/2026** — v1: wizard MMII+MMSS, PDF reportlab, login opcional,
  captura de foto por câmera, publicado no GitHub + Streamlit Cloud.
- **10/10/2026** — busca de paciente no Feegow no campo Nome completo.
- **13/10/2026** — lote de 17 melhorias da equipe de fisioterapeutas:
  idade calculada, busca por ID com autopreenchimento de nascimento, fix
  de scroll, altura com 2 casas decimais, seta de colapsar sidebar,
  scroll-avançar em campos de clique único, prancha em min/seg, legenda
  Step Down + valores de referência em todos os testes relevantes,
  upload de vídeo, foto própria em Análise de Movimento, Cross Over Hop
  em segundos (troca cm), remoção de Dinamometria/Termografia,
  observação na foto geral, destaque dourado + barra de assimetria na
  Revisão. Commit `a377fbc`.
- **27/10/2026** — pendente: validação prática no tablet real antes de
  um teste de avaliação ao vivo, incluindo câmera/vídeo em dispositivo
  físico (só simulados até agora via Playwright com câmera falsa).

## Pendências conhecidas

- Validar no tablet físico de verdade: câmera, upload de vídeo, toque
  (scroll-avançar, botões de navegação) — só testado via Playwright/AppTest.
- Layout fino do MMSS (reconstruído sem PDF limpo de referência) —
  validar contra o uso real.
- Interpretação assumida sem perguntar de novo (avisar se errada): "puxar
  cadastro por ID" virou mostrar o ID dentro do seletor de nome já
  existente, não um campo de ID separado.
- URL pública do app no Streamlit Cloud não está anotada nesta skill —
  atualizar aqui assim que recuperada.
- Fase 2 (camada narrativa/diagnóstica no PDF) **não iniciar sem
  confirmação explícita do Sergio**.
