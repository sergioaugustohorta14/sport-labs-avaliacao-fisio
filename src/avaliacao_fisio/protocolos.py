"""Definição dos campos de cada protocolo de avaliação (Membros Inferiores,
Membros Superiores) e das seções compartilhadas entre eles (Dados do
paciente, Dor, Testes adicionais, Classificação de risco, Responsável).

Isto é só o MODELO de dados — `wizard.py` usa essas definições pra desenhar
os widgets e `pdf_avaliacao.py` usa as mesmas pra montar as tabelas do PDF,
então a ordem das seções/campos aqui é a ordem real que aparece nos dois
lugares.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Campo:
    """Um teste/medida dentro de uma seção.

    `tipo` define o widget no wizard e o formato da tabela no PDF:
    - "unico_texto" / "unico_numero" / "data" / "booleano": um valor só.
    - "idade_calculada": sem widget — deriva de `data_nascimento` (mesma
      seção, campo anterior) e fica só exibida.
    - "lado_unico": escolha D OU E (ex.: membro dominante).
    - "busca_paciente": autocomplete sobre o cadastro do Feegow.
    - "bilateral_numero": valor numérico pro lado D e pro lado E.
    - "bilateral_sinal": resultado +/- pro lado D e pro lado E (ex.: Thomas).
    - "bilateral_score": score 1 a 3 pro lado D e pro lado E.
    - "bilateral_tempo" / "unico_tempo": minutos+segundos (ex.: prancha).
    - "foto_unica": uma foto (câmera) + legenda, não repetível.
    - "video_upload": upload de vídeo já gravado (não entra no PDF).
    - "opcoes": escolha única entre `opcoes`.

    `ajuda`, se definido, vira o tooltip "?" nativo do Streamlit (`help=`).
    `casas_decimais` só se aplica a "unico_numero"/"bilateral_numero"
    (default 1; usar 2 pra medidas que precisam de mais precisão, ex.
    altura em metros).
    """

    id: str
    rotulo: str
    tipo: str
    unidade: str | None = None
    observacao: bool = False
    opcoes: tuple[str, ...] | None = None
    ajuda: str | None = None
    casas_decimais: int = 1
    # Só pros campos bilaterais numéricos, no PDF: "maior" = mais é melhor
    # (força, alcance, saltos); "menor" = menos é melhor (tempo de salto);
    # None = sem direção clara (flexibilidade, amplitude) — nenhum lado é
    # destacado como o mais fraco nos gráficos de evolução.
    sentido: str | None = "maior"
    # False: a assimetria aparece só como número, sem a cor de "chance de lesão"
    # (as faixas de 10%/20% foram definidas pra testes de força, não pra métricas de corrida).
    risco: bool = True


@dataclass(frozen=True)
class Secao:
    id: str
    titulo: str
    campos: tuple[Campo, ...] = ()


@dataclass(frozen=True)
class SecaoCorrida(Secao):
    """Seção cujos valores (métricas por pé) podem ser importados de uma corrida do
    RunScribe. Depois de importados continuam editáveis à mão. O `id` de cada campo
    bilateral é o nome da métrica na API do RunScribe."""


@dataclass(frozen=True)
class SecaoRepetivel:
    """Seção com um número variável de linhas (ex.: Dinamometria — um grupo
    muscular por linha; Testes adicionais — um teste por linha)."""

    id: str
    titulo: str
    colunas: tuple[tuple[str, str], ...]  # (id_coluna, rótulo_coluna)
    minimo_linhas: int = 1
    tem_toggle_realizado: bool = False


@dataclass(frozen=True)
class SecaoDor:
    """Seção fixa de Dor: escala VAS (repouso/atividade) + lista repetível
    de locais de dor (região + lado + intensidade) — substitui o diagrama
    corporal desenhado à mão do formulário em papel."""

    id: str
    titulo: str
    opcoes_regiao: tuple[str, ...]
    opcoes_lado: tuple[str, ...] = ("Direito", "Esquerdo", "Bilateral", "Central")


@dataclass(frozen=True)
class SecaoFotos:
    """Seção repetível de registros fotográficos (câmera do tablet/celular),
    pra ilustrar o PDF final — ex.: "Teste de Thomas", "Step Down" etc.,
    mesmo padrão visto nos relatórios de referência."""

    id: str
    titulo: str


@dataclass(frozen=True)
class Protocolo:
    id: str
    nome: str
    secoes: tuple[object, ...]  # Secao | SecaoRepetivel | SecaoDor | SecaoFotos


# ---------------------------------------------------------------------------
# Seções compartilhadas entre MMII e MMSS
# ---------------------------------------------------------------------------

DADOS_PACIENTE = Secao(
    id="dados_paciente",
    titulo="Dados do Paciente",
    campos=(
        Campo("nome_completo", "Nome completo", "busca_paciente"),
        Campo("data_nascimento", "Data de nascimento", "data"),
        Campo("idade", "Idade", "idade_calculada", unidade="anos"),
        Campo("peso_kg", "Peso", "unico_numero", unidade="kg"),
        Campo("altura_m", "Altura", "unico_numero", unidade="m", casas_decimais=2),
        Campo("membro_dominante", "Membro dominante", "lado_unico"),
        Campo("esporte_modalidade", "Esporte / modalidade", "unico_texto"),
        Campo("data_lesao", "Data da lesão", "data"),
        Campo("lesao_diagnostico", "Lesão / diagnóstico", "unico_texto"),
        Campo("local_lesao", "Local da lesão", "unico_texto"),
        Campo("medico_responsavel", "Médico responsável", "unico_texto"),
    ),
)

TESTES_ADICIONAIS = SecaoRepetivel(
    id="testes_adicionais",
    titulo="Testes Adicionais",
    colunas=(
        ("nome_teste", "Teste"),
        ("direito", "Direito"),
        ("esquerdo", "Esquerdo"),
        ("unidade", "Unidade"),
    ),
    minimo_linhas=0,
)

FOTOS = SecaoFotos(id="fotos", titulo="Registros Fotográficos")

DOR = SecaoDor(
    id="dor",
    titulo="Dor",
    opcoes_regiao=(
        "Cabeça / Pescoço", "Coluna cervical", "Ombro", "Cotovelo", "Antebraço",
        "Punho / Mão", "Coluna torácica", "Coluna lombar", "Quadril",
        "Coxa anterior", "Coxa posterior", "Joelho", "Perna", "Tornozelo", "Pé",
    ),
)

CLASSIFICACAO_RISCO = Secao(
    id="classificacao_risco",
    titulo="Classificação de Risco do Paciente",
    campos=(
        Campo("risco", "Classificação de risco", "opcoes", opcoes=("Baixo", "Moderado", "Alto")),
    ),
)

RESPONSAVEL = Secao(
    id="responsavel",
    titulo="Responsável",
    campos=(
        Campo("fisioterapeuta_responsavel", "Fisioterapeuta responsável", "unico_texto"),
        Campo("crefito", "CREFITO", "unico_texto"),
    ),
)

# ---------------------------------------------------------------------------
# Membros Inferiores (MMII) — ordem do formulário oficial
# ---------------------------------------------------------------------------

_MMII_MOBILIDADE = Secao(
    id="mmii_mobilidade",
    titulo="Mobilidade e Flexibilidade",
    campos=(
        Campo(
            "flexibilidade_isquiotibiais", "Flexibilidade de isquiotibiais", "bilateral_numero", unidade="°",
            ajuda="Referência: quanto mais próximo de 0°, mais flexível.", sentido=None,
        ),
        Campo(
            "rigidez_quadril", "Rigidez de quadril", "bilateral_numero", unidade="°",
            ajuda="Referência: 30°–40°.", sentido=None,
        ),
        Campo(
            "lunge_test", "Lunge test (dorsiflexão de tornozelo)", "bilateral_numero", unidade="°",
            ajuda="Referência: 35°–45° (média de 3 valores).", sentido=None,
        ),
        Campo("thomas_iliopsoas", "Teste de Thomas — Iliopsoas", "bilateral_sinal"),
        Campo("thomas_reto_femoral", "Teste de Thomas — Reto femoral", "bilateral_sinal"),
    ),
)

_MMII_FORCA = Secao(
    id="mmii_forca",
    titulo="Força",
    campos=(
        Campo(
            "gluteo_medio", "Glúteo médio", "bilateral_numero", unidade="repetições",
            ajuda="Referência: máximo de 15 repetições.",
        ),
        Campo(
            "extensores_quadril", "Extensores de quadril", "bilateral_numero", unidade="repetições", observacao=True,
            ajuda="Referência: máximo de 20 repetições.",
        ),
        Campo(
            "rotadores_quadril", "Rotadores de quadril", "bilateral_numero", unidade="repetições",
            ajuda="Referência: máximo de 15 repetições.",
        ),
    ),
)

_MMII_CONTROLE_MOTOR = Secao(
    id="mmii_controle_motor",
    titulo="Controle Motor e Estabilidade",
    campos=(
        Campo(
            "estabilidade_lombo_pelvica", "Estabilidade lombo-pélvica", "bilateral_numero", unidade="°",
            ajuda="Referência: 0°.", sentido=None,
        ),
        Campo(
            "prancha_lateral", "Prancha lateral", "bilateral_tempo",
            ajuda="Referência: 1 minuto.",
        ),
        Campo(
            "prancha_frontal", "Prancha frontal (bilateral)", "unico_tempo",
            ajuda="Referência: 1 minuto.",
        ),
    ),
)

_MMII_ANALISE_MOVIMENTO = Secao(
    id="mmii_analise_movimento",
    titulo="Análise de Movimento",
    campos=(
        Campo(
            "step_down", "Step Down", "bilateral_score",
            ajuda=(
                "1 = ruim (alterações importantes no controle do movimento) · "
                "2 = moderado (alterações leves a moderadas) · "
                "3 = bom (boa execução, alinhamento e controle motor). "
                "Observa valgo dinâmico, queda da pelve, rotação e inclinação de tronco."
            ),
        ),
        Campo("agachamento_bilateral", "Agachamento bilateral (qualidade do movimento)", "unico_texto"),
        Campo("agachamento_unilateral", "Agachamento unilateral", "bilateral_numero", unidade="repetições"),
        Campo("salto_unilateral", "Salto unilateral", "bilateral_score"),
        Campo("observacoes_gerais", "Observações da análise de movimento", "unico_texto"),
        Campo("foto_analise_movimento", "Foto do teste", "foto_unica"),
        Campo(
            "video_analise_movimento", "Vídeo do teste (upload)", "video_upload",
            ajuda="Vídeo já gravado no tablet/celular — fica anexado, não entra no PDF impresso.",
        ),
    ),
)

_MMII_Y_BALANCE = Secao(
    id="mmii_y_balance",
    titulo="Y-Balance Test",
    campos=(
        Campo("anterior", "Anterior", "bilateral_numero", unidade="cm"),
        Campo("postero_medial", "Póstero-medial", "bilateral_numero", unidade="cm"),
        Campo("postero_lateral", "Póstero-lateral", "bilateral_numero", unidade="cm"),
        Campo("comprimento_membro", "Comprimento do membro (EIAS–maléolo)", "bilateral_numero", unidade="cm", sentido=None),
        Campo("discrepancia_membros", "Discrepância entre membros", "unico_numero", unidade="cm"),
    ),
)

_MMII_HOP_TEST = Secao(
    id="mmii_hop_test",
    titulo="Hop Test",
    campos=(
        Campo("single_hop", "Single Hop", "bilateral_numero", unidade="cm"),
        Campo("triple_hop", "Triple Hop", "bilateral_numero", unidade="cm"),
        Campo("cross_over_hop", "Cross Over Hop", "bilateral_numero", unidade="segundos", sentido="menor"),
        Campo("seis_m_hop", "6 m Hop", "bilateral_numero", unidade="segundos", sentido="menor"),
    ),
)

PROTOCOLO_MMII = Protocolo(
    id="mmii",
    nome="Membros Inferiores",
    secoes=(
        DADOS_PACIENTE,
        _MMII_MOBILIDADE,
        _MMII_FORCA,
        _MMII_CONTROLE_MOTOR,
        _MMII_ANALISE_MOVIMENTO,
        _MMII_Y_BALANCE,
        _MMII_HOP_TEST,
        DOR,
        TESTES_ADICIONAIS,
        FOTOS,
        CLASSIFICACAO_RISCO,
        RESPONSAVEL,
    ),
)

# ---------------------------------------------------------------------------
# Membros Superiores (MMSS) — reconstruído a partir do formulário preenchido
# à mão (sem PDF limpo de referência); validar layout fino com o Sergio.
# ---------------------------------------------------------------------------

_MMSS_AVALIACAO = Secao(
    id="mmss_avaliacao",
    titulo="Avaliação de Membros Superiores",
    campos=(
        Campo("adm_rotadores_internos", "ADM Rotadores Internos", "bilateral_numero", unidade="°", sentido=None),
        Campo("adm_rotadores_externos", "ADM Rotadores Externos", "bilateral_numero", unidade="°", sentido=None),
        Campo("gird", "GIRD", "bilateral_numero", unidade="°", sentido=None),
        Campo("encurtamento_peitoral", "Encurtamento de Peitoral", "bilateral_sinal"),
        Campo("encurtamento_grande_dorsal", "Encurtamento de Grande Dorsal", "bilateral_sinal"),
        Campo("prancha_frontal", "Prancha Frontal", "bilateral_tempo"),
        Campo("prancha_lateral", "Prancha Lateral", "bilateral_tempo"),
    ),
)

_MMSS_ANALISE_MOVIMENTO = Secao(
    id="mmss_analise_movimento",
    titulo="Análise de Movimento",
    campos=(Campo("discinese_escapular", "Discinese Escapular", "bilateral_score"),),
)

_MMSS_Y_BALANCE = Secao(
    id="mmss_y_balance",
    titulo="Y-Balance Test (Membro Superior)",
    campos=(
        Campo("alcance_direito", "Alcance direito", "unico_numero", unidade="cm"),
        Campo("alcance_esquerdo", "Alcance esquerdo", "unico_numero", unidade="cm"),
        Campo("discrepancia_msd", "Discrepância MSD", "unico_numero", unidade="cm"),
        Campo("discrepancia_mse", "Discrepância MSE", "unico_numero", unidade="cm"),
    ),
)

PROTOCOLO_MMSS = Protocolo(
    id="mmss",
    nome="Membros Superiores",
    secoes=(
        DADOS_PACIENTE,
        _MMSS_AVALIACAO,
        _MMSS_ANALISE_MOVIMENTO,
        _MMSS_Y_BALANCE,
        DOR,
        TESTES_ADICIONAIS,
        FOTOS,
        CLASSIFICACAO_RISCO,
        RESPONSAVEL,
    ),
)

# ---------------------------------------------------------------------------
# Corrida — métricas por pé importadas do RunScribe (direito = D, esquerdo = E)
# ---------------------------------------------------------------------------


def _metrica_corrida(id: str, rotulo: str, unidade: str, casas: int) -> Campo:
    return Campo(id, rotulo, "bilateral_numero", unidade=unidade, casas_decimais=casas, sentido=None, risco=False)


_CORRIDA_RUNSCRIBE = SecaoCorrida(
    id="corrida_runscribe",
    titulo="Corrida (RunScribe)",
    campos=(
        Campo("corrida_analisada", "Corrida analisada", "unico_texto"),
        Campo("distancia_m", "Distância", "unico_numero", unidade="m", casas_decimais=0),
        Campo("duracao_min", "Duração", "unico_numero", unidade="min", casas_decimais=1),
        Campo("passos", "Passos", "unico_numero", casas_decimais=0),
        _metrica_corrida("step_rate", "Cadência", "passos/min", 1),
        _metrica_corrida("stride_length", "Comprimento da passada", "m", 2),
        _metrica_corrida("contact_time", "Tempo de contato", "ms", 0),
        _metrica_corrida("flight_ratio", "Razão de voo", "%", 1),
        _metrica_corrida("power", "Potência", "W", 0),
        _metrica_corrida("shock", "Choque", "G", 1),
        _metrica_corrida("impact_gs", "Impacto", "G", 1),
        _metrica_corrida("braking_gs", "Frenagem", "G", 1),
        _metrica_corrida("pronation_excursion_fs_mp", "Excursão de pronação", "°", 1),
        _metrica_corrida("footstrike_type", "Tipo de pisada (índice)", "", 1),
    ),
)

METRICAS_RUNSCRIBE: tuple[str, ...] = tuple(c.id for c in _CORRIDA_RUNSCRIBE.campos if c.tipo == "bilateral_numero")

PROTOCOLO_CORRIDA = Protocolo(
    id="corrida",
    nome="Corrida",
    secoes=(
        DADOS_PACIENTE,
        _CORRIDA_RUNSCRIBE,
        DOR,
        TESTES_ADICIONAIS,
        FOTOS,
        CLASSIFICACAO_RISCO,
        RESPONSAVEL,
    ),
)

PROTOCOLOS: dict[str, Protocolo] = {
    PROTOCOLO_MMII.id: PROTOCOLO_MMII,
    PROTOCOLO_MMSS.id: PROTOCOLO_MMSS,
    PROTOCOLO_CORRIDA.id: PROTOCOLO_CORRIDA,
}
