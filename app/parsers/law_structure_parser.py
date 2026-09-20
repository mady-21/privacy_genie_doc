import json
import re
from pathlib import Path


class LawStructureParser:
    # 법령 구조
    CHAPTER_PATTERN = re.compile(
        r"^제\d+장(?:의\d+)?\s+.+"
    )

    SECTION_PATTERN = re.compile(
        r"^제\d+절(?:의\d+)?\s+.+"
    )

    ARTICLE_PATTERN = re.compile(
        r"^(제\d+조(?:의\d+)?)(?:\(([^)]+)\))?\s*(.*)$"
    )

    PARAGRAPH_PATTERN = re.compile(
        r"^([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳])\s*(.*)$"
    )

    ITEM_PATTERN = re.compile(
        r"^(\d+(?:의\d+)?)\.\s*(.*)$"
    )

    SUBITEM_PATTERN = re.compile(
        r"^([가-하])\.\s*(.*)$"
    )

    # 조문 메타데이터
    EFFECTIVE_DATE_PATTERN = re.compile(
        r"^\[시행일:"
    )

    ARTICLE_CREATED_PATTERN = re.compile(
        r"^\[본조신설"
    )

    TITLE_AMENDED_PATTERN = re.compile(
        r"^\[제목개정"
    )

    # 법률 자체의 메타데이터
    LAW_EFFECTIVE_PATTERN = re.compile(
        r"\[시행\s+(\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.)\]"
    )

    LAW_NUMBER_PATTERN = re.compile(
        r"\[(법률\s+제\d+호)"
    )

    def classify(self, text: str) -> str:
        text = text.strip()

        if self.CHAPTER_PATTERN.match(text):
            return "chapter"

        if self.SECTION_PATTERN.match(text):
            return "section"

        if self.ARTICLE_PATTERN.match(text):
            return "article"

        if self.PARAGRAPH_PATTERN.match(text):
            return "paragraph"

        if self.ITEM_PATTERN.match(text):
            return "item"

        if self.SUBITEM_PATTERN.match(text):
            return "subitem"

        if self.EFFECTIVE_DATE_PATTERN.match(text):
            return "effective_date"

        if self.ARTICLE_CREATED_PATTERN.match(text):
            return "article_created"

        if self.TITLE_AMENDED_PATTERN.match(text):
            return "title_amended"

        return "other"

    def parse(self, paragraphs: list[str]) -> dict:
        document = {
            "law": {
                "name": None,
                "effective_date": None,
                "law_number": None,
            },
            "articles": [],
        }

        # 법률명, 시행일, 법률번호 추출
        self._parse_law_metadata(
            paragraphs=paragraphs,
            document=document,
        )

        current_chapter = None
        current_section = None
        current_article = None
        current_paragraph = None
        current_item = None

        for text in paragraphs:
            text = text.strip()

            if not text:
                continue

            paragraph_type = self.classify(text)

            # 장
            if paragraph_type == "chapter":
                current_chapter = text
                current_section = None
                continue

            # 절
            if paragraph_type == "section":
                current_section = text
                continue

            # 조
            if paragraph_type == "article":
                current_article = self._parse_article(
                    text=text,
                    chapter=current_chapter,
                    section=current_section,
                )

                document["articles"].append(
                    current_article
                )

                current_paragraph = None
                current_item = None

                # 예:
                # 제3조(개인정보 보호 원칙) ① 개인정보처리자는...
                #
                # 조문 본문 안에 ①이 포함된 경우
                # 별도의 paragraph로 분리한다.
                if self.PARAGRAPH_PATTERN.match(
                    current_article["body"]
                ):
                    current_paragraph = (
                        self._parse_paragraph(
                            current_article["body"]
                        )
                    )

                    current_article[
                        "paragraphs"
                    ].append(
                        current_paragraph
                    )

                    current_article["body"] = ""

                continue

            # 항
            if (
                paragraph_type == "paragraph"
                and current_article
            ):
                current_paragraph = (
                    self._parse_paragraph(text)
                )

                current_article[
                    "paragraphs"
                ].append(
                    current_paragraph
                )

                current_item = None
                continue

            # 호
            if (
                paragraph_type == "item"
                and current_article
            ):
                item = self._parse_item(text)

                # 항 아래에 있는 호
                if current_paragraph:
                    current_paragraph[
                        "items"
                    ].append(item)

                # 항 없이 조문 바로 아래에 있는 호
                else:
                    current_article[
                        "items"
                    ].append(item)

                current_item = item
                continue

            # 목
            if (
                paragraph_type == "subitem"
                and current_item
            ):
                current_item[
                    "subitems"
                ].append(
                    self._parse_subitem(text)
                )

                continue

            # 본조신설
            if (
                paragraph_type == "article_created"
                and current_article
            ):
                current_article[
                    "metadata"
                ]["created"] = text

                continue

            # 제목개정
            if (
                paragraph_type == "title_amended"
                and current_article
            ):
                current_article[
                    "metadata"
                ]["title_amended"] = text

                continue

            # 미래 시행일
            if (
                paragraph_type == "effective_date"
                and current_article
            ):
                current_article[
                    "metadata"
                ]["effective_date"] = text

                continue

        return document

    def _parse_law_metadata(
        self,
        paragraphs: list[str],
        document: dict,
    ) -> None:
        """
        문서 상단에서 법률 기본정보를 추출한다.

        예:
        개인정보 보호법

        [시행 2026. 9. 11.]
        [법률 제21445호, 2026. 3. 10., 일부개정]
        """

        if paragraphs:
            document["law"]["name"] = (
                paragraphs[0].strip()
            )

        # 법률 기본정보는 문서 상단에 있다고 보고
        # 앞부분만 확인한다.
        for text in paragraphs[:10]:
            text = text.strip()

            effective_match = (
                self.LAW_EFFECTIVE_PATTERN.search(
                    text
                )
            )

            if effective_match:
                document[
                    "law"
                ]["effective_date"] = (
                    effective_match.group(1)
                )

            law_number_match = (
                self.LAW_NUMBER_PATTERN.search(
                    text
                )
            )

            if law_number_match:
                document[
                    "law"
                ]["law_number"] = (
                    law_number_match.group(1)
                )

    def _parse_article(
        self,
        text: str,
        chapter: str | None,
        section: str | None,
    ) -> dict:
        match = self.ARTICLE_PATTERN.match(text)

        if not match:
            raise ValueError(
                f"Invalid article: {text}"
            )

        number = match.group(1)
        title = match.group(2)
        body = match.group(3).strip()

        return {
            "number": number,
            "title": title,
            "location": {
                "chapter": chapter,
                "section": section,
            },
            "body": body,
            "paragraphs": [],
            "items": [],
            "metadata": {},
        }

    def _parse_paragraph(
        self,
        text: str,
    ) -> dict:
        match = self.PARAGRAPH_PATTERN.match(text)

        if not match:
            raise ValueError(
                f"Invalid paragraph: {text}"
            )

        return {
            "number": match.group(1),
            "text": match.group(2).strip(),
            "items": [],
        }

    def _parse_item(
        self,
        text: str,
    ) -> dict:
        match = self.ITEM_PATTERN.match(text)

        if not match:
            raise ValueError(
                f"Invalid item: {text}"
            )

        return {
            "number": match.group(1),
            "text": match.group(2).strip(),
            "subitems": [],
        }

    def _parse_subitem(
        self,
        text: str,
    ) -> dict:
        match = self.SUBITEM_PATTERN.match(text)

        if not match:
            raise ValueError(
                f"Invalid subitem: {text}"
            )

        return {
            "number": match.group(1),
            "text": match.group(2).strip(),
        }

    def save_classification(
        self,
        paragraphs: list[str],
        output_path: str = (
            "/app/extracted/"
            "classified_paragraphs.txt"
        ),
    ) -> Path:
        """
        파싱 전 각 문단이 어떻게 분류되는지
        확인하기 위한 디버깅 파일.
        """

        path = Path(output_path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with path.open(
            "w",
            encoding="utf-8",
        ) as file:
            for index, paragraph in enumerate(
                paragraphs,
                start=1,
            ):
                paragraph_type = self.classify(
                    paragraph
                )

                file.write(
                    f"[{index}] "
                    f"[{paragraph_type}]\n"
                )

                file.write(paragraph)
                file.write("\n\n")

        return path

    def save_json(
        self,
        document: dict,
        output_path: str = (
            "/app/docs/extracted/"
            "law_structure.json"
        ),
    ) -> Path:
        """
        최종 파싱된 법령 구조를
        사람이 확인할 수 있도록 JSON으로 저장한다.
        """

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
                document,
                file,
                ensure_ascii=False,
                indent=2,
            )

        return path