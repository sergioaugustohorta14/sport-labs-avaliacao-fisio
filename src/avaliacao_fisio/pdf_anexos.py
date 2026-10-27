"""Relatório do Kinology (plataforma de dinamometria): lista as páginas do PDF
enviado e anexa as escolhidas, SEM alteração, ao fim do PDF da avaliação.

O PDF do Kinology é vetorial (texto extraível). Estrutura observada em
27/10/2026 (relatório de 24 páginas): pág. 1 = índice, 2 a 8 = resumos
(assimetria, desequilíbrio, evolução, histórico de força), 9 em diante =
curvas brutas de "Dinâmica e Desempenho Muscular", uma por exercício/lado.
"""
from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass

from pypdf import PdfReader, PdfWriter

_TITULOS_CONHECIDOS = (
    "Asimetria e Indicativos de Risco | Membros Superiores",
    "Assimetria e Indicativos de Risco | Membros Superiores",
    "Assimetria e Indicativos de Risco | Membros Inferiores",
    "Evolução de Assimetria",
    "Desequilíbrio Muscular | Membros Superiores",
    "Desequilíbrio Muscular | Membros Inferiores",
    "Evolução de Desequilíbrio Muscular",
    "Evolução de Risco de Lesão",
    "Histórico de Força e Valores de Referência",
    "Dinâmica e Desempenho Muscular",
)
_TITULO_CURVAS = "Dinâmica e Desempenho Muscular"
_RE_EXERCICIO = re.compile(r"^(.+?)\s+(direito|esquerdo)$", re.IGNORECASE)


@dataclass(frozen=True)
class PaginaKinology:
    numero: int  # 1-based, como no PDF original
    titulo: str
    e_indice: bool
    e_curva: bool

    @property
    def rotulo(self) -> str:
        return f"Pág. {self.numero}: {self.titulo}"


def _abrir(pdf_bytes: bytes) -> PdfReader:
    leitor = PdfReader(io.BytesIO(pdf_bytes))
    if leitor.is_encrypted:
        leitor.decrypt("")
    return leitor


def _normalizar(texto: str) -> str:
    # NFKC desfaz ligaduras do PDF ("ﬁ" -> "fi").
    return " ".join(unicodedata.normalize("NFKC", texto).split()).lower()


def analisar(pdf_bytes: bytes) -> list[PaginaKinology]:
    """Uma entrada por página. Levanta `ValueError` se o arquivo não for um PDF legível."""
    try:
        leitor = _abrir(pdf_bytes)
        textos = [(pagina.extract_text() or "") for pagina in leitor.pages]
    except Exception as erro:  # arquivo corrompido, protegido, não-PDF
        raise ValueError(f"Não consegui ler o PDF: {erro}") from erro

    paginas = []
    for i, texto in enumerate(textos, start=1):
        normal = _normalizar(texto)
        e_indice = "resultados" in normal and "seção" in normal and "página" in normal and i == 1
        titulo = next((t for t in _TITULOS_CONHECIDOS if _normalizar(t) in normal), None)
        e_curva = titulo == _TITULO_CURVAS
        if e_indice:
            titulo = "Índice do relatório"
        elif e_curva:
            exercicio = next(
                (linha.strip() for linha in texto.splitlines() if _RE_EXERCICIO.match(linha.strip())), None,
            )
            titulo = f"{_TITULO_CURVAS} ({exercicio})" if exercicio else _TITULO_CURVAS
        elif titulo is None:
            titulo = "Página sem título reconhecido"
        paginas.append(PaginaKinology(numero=i, titulo=titulo, e_indice=e_indice, e_curva=e_curva))
    return paginas


def parece_kinology(pdf_bytes: bytes) -> bool:
    try:
        leitor = _abrir(pdf_bytes)
        return any("kinology" in (p.extract_text() or "").lower() for p in leitor.pages[:3])
    except Exception:
        return False


def paginas_padrao(paginas: list[PaginaKinology], incluir_curvas: bool) -> list[int]:
    """Números das páginas que entram por padrão: tudo, menos o índice (a
    numeração dele não vale no nosso documento) e, a menos que o usuário peça,
    as curvas brutas."""
    return [p.numero for p in paginas if not p.e_indice and (incluir_curvas or not p.e_curva)]


def anexar(pdf_proprio: bytes, kinology: bytes, paginas: list[int]) -> bytes:
    """Nosso PDF + as `paginas` (1-based) do Kinology, na ordem pedida, sem alteração."""
    escritor = PdfWriter()
    for pagina in PdfReader(io.BytesIO(pdf_proprio)).pages:
        escritor.add_page(pagina)
    leitor = _abrir(kinology)
    for numero in paginas:
        escritor.add_page(leitor.pages[numero - 1])
    saida = io.BytesIO()
    escritor.write(saida)
    return saida.getvalue()
