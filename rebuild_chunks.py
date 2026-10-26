"문서 파싱·청킹·임베딩 결과(검색용 벡터 포함)를 한 번에 생성한다."
import argparse
import time
from pathlib import Path

from app.constants.law import ARTICLES
from app.constants.paths import (
    EXTRACTED_DIR, CLASSIFICATION_FILENAME,
    STRUCTURE_FILENAME, CHUNKS_FILENAME, PREVIEW_FILENAME, EMBEDDINGS_FILENAME,
)
from app.documents.law_documents import LAW_SOURCES, check_law_name
from app.parsers.hwpx_parser import HwpxParser
from app.parsers.law_structure_parser import LawStructureParser
from app.embeddings.embedding_text_builder import EmbeddingTextBuilder
from app.embeddings.store import embedding_inputs, save_embeddings


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--type', choices=tuple(LAW_SOURCES), default='act')
    cli.add_argument('--input', type=Path)
    cli.add_argument('--output-dir', type=Path, default=None)
    cli.add_argument('--skip-embeddings', action='store_true', help='벡터 계산(CPU로 수 분) 없이 청크만 다시 만든다')
    args = cli.parse_args()
    law_source = LAW_SOURCES[args.type]
    source = args.input or law_source.path
    args.output_dir = args.output_dir or EXTRACTED_DIR / args.type
    paragraphs = HwpxParser(str(source)).parse()
    parser = LawStructureParser()
    parser.save_classification(paragraphs, args.output_dir / CLASSIFICATION_FILENAME)
    document = parser.parse(paragraphs)
    parser.save_json(document, args.output_dir / STRUCTURE_FILENAME)
    check_law_name(args.type, document)
    chunker = law_source.chunker_class()
    chunks = chunker.chunk(document)
    chunker.save_json(chunks, args.output_dir / CHUNKS_FILENAME)
    preview = EmbeddingTextBuilder().save_preview(
        chunks, args.output_dir / PREVIEW_FILENAME
    )
    excluded = sum(1 for article in document[ARTICLES] if chunker.should_exclude(article))
    print(f'{len(chunks)}개 청크 (조문 {excluded}개 제외: 부칙·형사처벌 조문 등)')
    print(f'확인 파일: {preview}')

    if args.skip_embeddings:
        print(f'벡터 계산 생략: 기존 {EMBEDDINGS_FILENAME}가 이 청크와 다르면 서버가 시작하지 않습니다.')
        return
    from app.embeddings.embedder import Embedder

    started = time.time()
    embedder = Embedder()
    vectors = embedder.embed_array(embedding_inputs(chunks))
    path = save_embeddings(args.output_dir / EMBEDDINGS_FILENAME, chunks, vectors, embedder.model_name)
    print(f'벡터 {vectors.shape} 저장 ({time.time() - started:.0f}초): {path}')


if __name__ == '__main__':
    main()
