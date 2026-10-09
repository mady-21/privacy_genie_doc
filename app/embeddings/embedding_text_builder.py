from app.constants.paths import CHUNKS_PATH, PREVIEW_DIVIDER, PREVIEW_PATH, PREVIEW_SEPARATOR, TEXT_ENCODING
from app.constants.law import CHUNK_ID, DOCUMENT_PART, ARTICLE_NUMBER, LAW_EFFECTIVE_DATE, LAW_NAME, LAW_NUMBER, TEXT
import json
from pathlib import Path

class EmbeddingTextBuilder:

    def build(self, document_name: str, chunk: dict) -> str:
        """청크에 포함된 텍스트를 중복 없이 반환한다."""
        text = chunk.get(TEXT)
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f'청크 본문이 없습니다: {chunk.get(ARTICLE_NUMBER)}')
        return text.strip()

    def save_preview(self, chunks: list[dict], output_path: str | Path=PREVIEW_PATH, article_numbers: list[str] | None=None) -> Path:
        """실제 임베딩 입력문을 확인용 파일로 저장한다."""
        article_filter = set(article_numbers) if article_numbers is not None else None
        selected = [chunk for chunk in chunks if article_filter is None or chunk.get(ARTICLE_NUMBER) in article_filter]
        if not selected:
            raise ValueError('확인할 조문이 없습니다.')
        previews = [(chunk, self.build(document_name=chunk.get(LAW_NAME, ''), chunk=chunk)) for chunk in selected]
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding=TEXT_ENCODING) as file:
            file.write(f'확인 대상: {len(previews)}개 청크\n\n')
            for index, (chunk, text) in enumerate(previews, start=1):
                file.write(PREVIEW_SEPARATOR + '\n')
                file.write(f"[청크 {index}] {chunk.get(ARTICLE_NUMBER, '')}\n")
                for key in (CHUNK_ID, DOCUMENT_PART):
                    file.write(f"{key}: {chunk.get(key, '')}\n")
                file.write(f"법률번호: {chunk.get(LAW_NUMBER, '')}\n")
                file.write(f"법률 시행일: {chunk.get(LAW_EFFECTIVE_DATE, '')}\n")
                file.write(PREVIEW_DIVIDER + '\n')
                file.write(text)
                file.write('\n\n')
        return path
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='임베딩 입력문을 확인용 파일로 저장')
    parser.add_argument('--input', default=CHUNKS_PATH)
    parser.add_argument('--output', default=PREVIEW_PATH)
    parser.add_argument('--articles', nargs='+', help='확인할 조문 번호. 생략하면 전체 저장')
    args = parser.parse_args()
    with Path(args.input).open('r', encoding=TEXT_ENCODING) as file:
        chunks = json.load(file)
    if not isinstance(chunks, list):
        raise ValueError('입력 JSON은 청크 목록(list)이어야 합니다.')
    builder = EmbeddingTextBuilder()
    path = builder.save_preview(chunks=chunks, output_path=args.output, article_numbers=args.articles)
    print(f'확인용 파일 저장 완료: {path}')
