"""Run inside /app: python rebuild_chunks.py --input /app/docs/privacy.hwpx"""
import argparse
from pathlib import Path
from app.parsers.hwpx_parser import HwpxParser
from app.parsers.law_structure_parser import LawStructureParser
from app.chunkers.law_chunker import LawChunker


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--input', required=True)
    cli.add_argument('--output-dir', default='/app/docs/extracted')
    args = cli.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paragraphs = HwpxParser(args.input).parse()
    parser = LawStructureParser()
    parser.save_classification(paragraphs, str(output / 'classified_paragraphs.txt'))
    document = parser.parse(paragraphs)
    parser.save_json(document, str(output / 'law_structure.json'))
    chunker = LawChunker()
    chunks = chunker.chunk(document)
    chunker.save_json(chunks, str(output / 'chunks.json'))
    with (output / 'embedding_preview.txt').open('w', encoding='utf-8') as file:
        for chunk in chunks:
            file.write('=' * 60 + '\n')
            for key in ("chunk_id", "document_part"):
                file.write(f'{key}: {chunk[key]}\n')
            file.write('-' * 60 + '\n' + chunk['text'] + '\n\n')
    with (output / 'review_warnings.txt').open('w', encoding='utf-8') as file:
        file.write('\n'.join(document['warnings']) or '같은 범위 내 중복 조문이 없습니다.')
    print(f'{len(chunks)}개 청크 / 부칙 {len(document["supplements"])}개')
    print(f'버전 검토 경고 {len(document["warnings"])}건: {output / "review_warnings.txt"}')
    print(f'확인 파일: {output / "embedding_preview.txt"}')


if __name__ == '__main__':
    main()
