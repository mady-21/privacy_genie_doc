"문서 파싱·청킹·임베딩 확인 파일을 한 번에 생성한다."
import argparse
from pathlib import Path

from app.constants.law import SUPPLEMENTS
from app.constants.paths import (
    DEFAULT_SOURCE_PATH, EXTRACTED_DIR, CLASSIFICATION_FILENAME,
    STRUCTURE_FILENAME, CHUNKS_FILENAME, PREVIEW_FILENAME,
)
from app.parsers.hwpx_parser import HwpxParser
from app.parsers.law_structure_parser import LawStructureParser
from app.chunkers.act_chunker import ActChunker
from app.chunkers.decree_chunker import DecreeChunker
from app.constants.paths import ACT_SOURCE_PATH, DECREE_SOURCE_PATH
from app.embeddings.embedding_text_builder import EmbeddingTextBuilder


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--type', choices=('act', 'decree'), default='act')
    cli.add_argument('--input', type=Path)
    cli.add_argument('--output-dir', type=Path, default=None)
    args = cli.parse_args()
    source = args.input or (ACT_SOURCE_PATH if args.type == 'act' else DECREE_SOURCE_PATH)
    args.output_dir = args.output_dir or EXTRACTED_DIR / args.type
    paragraphs = HwpxParser(str(source)).parse()
    parser = LawStructureParser()
    parser.save_classification(paragraphs, args.output_dir / CLASSIFICATION_FILENAME)
    document = parser.parse(paragraphs)
    parser.save_json(document, args.output_dir / STRUCTURE_FILENAME)
    expected_name = '개인정보 보호법' if args.type == 'act' else '개인정보 보호법 시행령'
    if document['law']['name'] != expected_name:
        raise ValueError(f'--type과 문서 제목 불일치: {document["law"]["name"]}')
    chunker = ActChunker() if args.type == 'act' else DecreeChunker()
    chunks = chunker.chunk(document)
    chunker.save_json(chunks, args.output_dir / CHUNKS_FILENAME)
    preview = EmbeddingTextBuilder().save_preview(
        chunks, args.output_dir / PREVIEW_FILENAME
    )
    print(f'{len(chunks)}개 청크 / 부칙 {len(document[SUPPLEMENTS])}개')
    print(f'확인 파일: {preview}')


if __name__ == '__main__':
    main()
