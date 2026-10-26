from app.constants.paths import CHUNKS_PATH, PREVIEW_DIVIDER, PREVIEW_PATH, PREVIEW_SEPARATOR, TEXT_ENCODING
from app.constants.law import CHUNK_ID, DOCUMENT_PART, ARTICLE_NUMBER, LAW_EFFECTIVE_DATE, LAW_NAME, LAW_NUMBER, TEXT
import json
import re
from pathlib import Path

class EmbeddingTextBuilder:
    ANGLE_BRACKET_PATTERN = re.compile(r'<[^<>]*>')
    ANNOTATION_KEYWORDS = ('본조신설', '전문개정', '제목개정', '시행일')
    SQUARE_BRACKET_ANNOTATION_PATTERN = re.compile(r'\[\s*(?:' + '|'.join(ANNOTATION_KEYWORDS) + r')[^\[\]]*\]')
    MULTI_SPACE_PATTERN = re.compile(r'[ \t]{2,}')

    def build(self, document_name: str, chunk: dict) -> str:
        "청크 본문에서 개정이력 annotation을 걷어낸 임베딩 입력 텍스트를 만든다. 특정 모델용 프리픽스는 붙이지 않는다."
        text = chunk.get(TEXT)
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f'청크 본문이 없습니다: {chunk.get(ARTICLE_NUMBER)}')
        return self._strip_annotations(text.strip())

    def _strip_annotations(self, text: str) -> str:
        # 개정이력 annotation(<개정 ...>, [본조신설 ...] 등)을 제거한다.
        # 스퀘어브래킷은 실질 법률 내용(예: 시행령의 [법인의 경우에는 ...])을 담고 있는
        # 경우가 있어, 개정이력 키워드로 시작하는 것만 제거한다.
        text = self.ANGLE_BRACKET_PATTERN.sub('', text)
        text = self.SQUARE_BRACKET_ANNOTATION_PATTERN.sub('', text)
        lines = [self.MULTI_SPACE_PATTERN.sub(' ', line).rstrip() for line in text.split('\n')]
        return '\n'.join(line for line in lines if line)

    def save_preview(self, chunks: list[dict], output_path: str | Path=PREVIEW_PATH, article_numbers: list[str] | None=None) -> Path:
        "실제 임베딩 입력문을 확인용 파일로 저장한다."
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
