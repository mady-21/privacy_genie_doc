import json
from pathlib import Path


class EmbeddingTextBuilder:
    def build(
        self,
        document_name: str,
        chunk: dict,
    ) -> str:
        """청크에 포함된 텍스트를 중복 없이 반환한다."""
        text = chunk.get("text")

        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                f"청크 본문이 없습니다: {chunk.get('article_number')}"
            )

        # 기존 호출과 호환되도록 document_name 인자는 유지한다.
        # 법률명과 조문 제목은 이미 text에 포함되어 있다.
        return text.strip()

    def save_preview(
        self,
        chunks: list[dict],
        output_path: str = (
            "/app/docs/extracted/embedding_preview.txt"
        ),
        article_numbers: list[str] | None = None,
    ) -> Path:
        """실제 임베딩 입력문을 확인용 파일로 저장한다."""
        selected = [
            chunk
            for chunk in chunks
            if article_numbers is None
            or chunk.get("article_number") in article_numbers
        ]

        if not selected:
            raise ValueError("확인할 조문이 없습니다.")

        # 파일을 쓰기 전에 모든 입력문을 검증한다.
        previews = [
            (
                chunk,
                self.build(
                    document_name=chunk.get("law_name", ""),
                    chunk=chunk,
                ),
            )
            for chunk in selected
        ]

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as file:
            file.write(f"확인 대상: {len(previews)}개 청크\n\n")

            for index, (chunk, text) in enumerate(
                previews, start=1
            ):
                file.write("=" * 60 + "\n")
                file.write(
                    f"[청크 {index}] "
                    f"{chunk.get('article_number', '')}\n"
                )
                file.write(
                    f"법률번호: {chunk.get('law_number', '')}\n"
                )
                file.write(
                    "법률 시행일: "
                    f"{chunk.get('law_effective_date', '')}\n"
                )
                file.write("-" * 60 + "\n")
                file.write(text)
                file.write("\n\n")

        return path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="임베딩 입력문을 확인용 파일로 저장"
    )
    parser.add_argument(
        "--input",
        default="/app/docs/extracted/chunks.json",
    )
    parser.add_argument(
        "--output",
        default="/app/docs/extracted/embedding_preview.txt",
    )
    parser.add_argument(
        "--articles",
        nargs="+",
        help="확인할 조문 번호. 생략하면 전체 저장",
    )
    args = parser.parse_args()

    with Path(args.input).open("r", encoding="utf-8") as file:
        chunks = json.load(file)

    if not isinstance(chunks, list):
        raise ValueError(
            "입력 JSON은 청크 목록(list)이어야 합니다."
        )

    builder = EmbeddingTextBuilder()
    path = builder.save_preview(
        chunks=chunks,
        output_path=args.output,
        article_numbers=args.articles,
    )
    print(f"확인용 파일 저장 완료: {path}")