"법령 원문(hwpx)을 문서 종류별로 파싱·청킹한다."
from dataclasses import dataclass
from pathlib import Path

from app.chunkers.act_chunker import ActChunker
from app.chunkers.base_law_chunker import BaseLawChunker
from app.chunkers.decree_chunker import DecreeChunker
from app.constants.law import LAW, NAME
from app.constants.paths import ACT_SOURCE_PATH, DECREE_SOURCE_PATH
from app.parsers.hwpx_parser import HwpxParser
from app.parsers.law_structure_parser import LawStructureParser


@dataclass(frozen=True)
class LawSource:
    path: Path
    chunker_class: type[BaseLawChunker]
    expected_name: str


LAW_SOURCES = {
    'act': LawSource(ACT_SOURCE_PATH, ActChunker, '개인정보 보호법'),
    'decree': LawSource(DECREE_SOURCE_PATH, DecreeChunker, '개인정보 보호법 시행령'),
}


def check_law_name(document_type: str, document: dict) -> None:
    expected = LAW_SOURCES[document_type].expected_name
    if document[LAW][NAME] != expected:
        raise ValueError(f'{document_type} 원문의 제목이 "{expected}"가 아닙니다: {document[LAW][NAME]}')


def chunk_law_document(document_type: str, max_chunk_chars: float | None = None) -> tuple[dict, list[dict]]:
    source = LAW_SOURCES[document_type]
    document = LawStructureParser().parse(HwpxParser(str(source.path)).parse())
    check_law_name(document_type, document)
    return document, source.chunker_class(max_chunk_chars).chunk(document)
