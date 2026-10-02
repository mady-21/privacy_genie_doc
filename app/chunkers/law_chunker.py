import json
import re
from pathlib import Path

from app.constants.law import ARTICLES, CHAPTER, SECTION


class LawChunker:
    def chunk(self, document: dict) -> list[dict]:
        chunks = []

        law = document["law"]

        for article in document[ARTICLES]:
            chapter = article["location"].get(CHAPTER) or ""
            if (
                article.get("document_part", "main") == "main"
                and re.match(r"^제\s*10\s*장\s+벌칙(?:\s|$)", chapter.strip())
            ):
                continue

            chunk = self._build_article_chunk(
                law=law,
                article=article,
            )

            chunks.append(chunk)

        return chunks

    def _build_article_chunk(
        self,
        law: dict,
        article: dict,
    ) -> dict:
        text = self._build_article_text(
            law=law,
            article=article,
        )

        supplement = article.get("supplement")
        scope = supplement["id"] if supplement else "main"
        return {
            "chunk_id": f"{law['law_number']}:{scope}:{article['number']}:{article.get('occurrence', 1)}",
            "document_part": article.get("document_part", "main"),
            "supplement": supplement,
            "law_name": law["name"],
            "law_number": law["law_number"],
            "law_effective_date": law["effective_date"],

            "article_number": article["number"],
            "article_title": article["title"],

            CHAPTER: article["location"][CHAPTER],
            SECTION: article["location"][SECTION],

            "text": text,

            "metadata": article["metadata"],
        }

    def _build_article_text(
        self,
        law: dict,
        article: dict,
    ) -> str:
        lines = []

        # 법률명
        if law["name"]:
            lines.append(law["name"])

        supplement = article.get("supplement")
        if supplement:
            lines.append(supplement["heading"])
            lines.extend(supplement.get("preamble", []))

        if "source_lines" in article:
            for value in (article["location"][CHAPTER], article["location"][SECTION]):
                if value:
                    lines.append(value)
            lines.extend(article["source_lines"])
            return "\n".join(lines)

        # 장
        chapter = article["location"][CHAPTER]

        if chapter:
            lines.append(chapter)

        # 절
        section = article["location"][SECTION]

        if section:
            lines.append(section)

        # 조문 제목
        article_heading = article["number"]

        if article["title"]:
            article_heading += (
                f"({article['title']})"
            )

        lines.append(article_heading)

        # 항이 없는 조문의 본문
        if article["body"]:
            lines.append(article["body"])

        # 항
        for paragraph in article["paragraphs"]:
            paragraph_text = (
                f"{paragraph['number']} "
                f"{paragraph['text']}"
            )

            lines.append(paragraph_text)

            # 항 아래의 호
            for item in paragraph["items"]:
                self._append_item(
                    lines=lines,
                    item=item,
                )

        # 항 없이 조 바로 아래에 존재하는 호
        for item in article["items"]:
            self._append_item(
                lines=lines,
                item=item,
            )

        return "\n".join(lines)

    def _append_item(
        self,
        lines: list[str],
        item: dict,
    ) -> None:
        lines.append(
            f"{item['number']}. {item['text']}"
        )

        # 목
        for subitem in item["subitems"]:
            lines.append(
                f"{subitem['number']}. "
                f"{subitem['text']}"
            )

    def save_json(
        self,
        chunks: list[dict],
        output_path: str = (
            "/app/docs/extracted/chunks.json"
        ),
    ) -> Path:
        path = Path(output_path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                chunks,
                file,
                ensure_ascii=False,
                indent=2,
            )

        return path

