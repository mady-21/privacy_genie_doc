import re
from app.utils.files import save_json as write_json
from app.constants.paths import CHUNKS_PATH, TEXT_ENCODING
from app.constants.law import ARTICLES, ARTICLE_NUMBER, ARTICLE_TITLE, BODY, CHAPTER, CHUNK_ID, DOCUMENT_PART, EFFECTIVE_DATE, HEADING, ID, ITEMS, LAW, LAW_EFFECTIVE_DATE, LAW_NAME, LAW_NUMBER, LOCATION, MAIN, METADATA, NAME, NUMBER, OCCURRENCE, PARAGRAPHS, PART_COUNT, PART_INDEX, PREAMBLE, SECTION, SOURCE_LINES, SUBITEMS, SUPPLEMENT, TEXT, TITLE
from app.parsers.law_structure_parser import LawStructureParser
from pathlib import Path

class BaseLawChunker:
    MAX_CHUNK_CHARS: int = 1000

    def should_exclude(self, article: dict) -> bool:
        return False

    def chunk(self, document: dict) -> list[dict]:
        chunks = []
        law = document[LAW]
        for article in document[ARTICLES]:
            if self.should_exclude(article):
                continue
            chunks.extend(self._build_article_chunks(law=law, article=article))
        return chunks

    def _build_article_chunks(self, law: dict, article: dict) -> list[dict]:
        full_text = self._build_article_text(law=law, article=article)
        if len(full_text) <= self.MAX_CHUNK_CHARS or SOURCE_LINES not in article:
            return [self._finalize_chunk(law=law, article=article, text=full_text, part_index=1, part_count=1)]

        heading_line, *body_lines = article[SOURCE_LINES]
        if not body_lines:
            return [self._finalize_chunk(law=law, article=article, text=full_text, part_index=1, part_count=1)]

        boundary_pattern = LawStructureParser.PARAGRAPH_PATTERN if article[PARAGRAPHS] else LawStructureParser.ITEM_PATTERN
        groups = self._split_source_lines(body_lines=body_lines, boundary_pattern=boundary_pattern)
        if len(groups) <= 1:
            return [self._finalize_chunk(law=law, article=article, text=full_text, part_index=1, part_count=1)]

        prefix = self._prefix_lines(law=law, article=article)
        texts = ['\n'.join(prefix + [heading_line] + group) for group in groups]
        return [
            self._finalize_chunk(law=law, article=article, text=text, part_index=index, part_count=len(texts))
            for index, text in enumerate(texts, start=1)
        ]

    def _split_source_lines(self, body_lines: list[str], boundary_pattern: re.Pattern) -> list[list[str]]:
        "경계 패턴(항 또는 호)을 만날 때마다 새 그룹을 시작하고, 길이 제한에 맞춰 다시 묶는다."
        groups: list[list[str]] = []
        current: list[str] = []
        for line in body_lines:
            if boundary_pattern.match(line.strip()) and current:
                groups.append(current)
                current = []
            current.append(line)
        if current:
            groups.append(current)
        return self._pack_groups(groups)

    def _pack_groups(self, groups: list[list[str]]) -> list[list[str]]:
        "항/호 그룹을 길이 제한 안에서 그리디하게 다시 묶는다. 그룹 하나가 제한을 넘어도 쪼개지 않는다."
        packed: list[list[str]] = []
        bucket: list[str] = []
        bucket_len = 0
        for group in groups:
            group_len = sum(len(line) + 1 for line in group)
            if bucket and bucket_len + group_len > self.MAX_CHUNK_CHARS:
                packed.append(bucket)
                bucket = []
                bucket_len = 0
            bucket.extend(group)
            bucket_len += group_len
        if bucket:
            packed.append(bucket)
        return packed

    def _finalize_chunk(self, law: dict, article: dict, text: str, part_index: int, part_count: int) -> dict:
        supplement = article.get(SUPPLEMENT)
        scope = supplement[ID] if supplement else MAIN
        chunk_id = f'{law[LAW_NUMBER]}:{scope}:{article[NUMBER]}:{article.get(OCCURRENCE, 1)}'
        if part_count > 1:
            chunk_id += f':part{part_index}'
        return {'document_type': self.DOCUMENT_TYPE, CHUNK_ID: chunk_id, DOCUMENT_PART: article.get(DOCUMENT_PART, MAIN), SUPPLEMENT: supplement, LAW_NAME: law[NAME], LAW_NUMBER: law[LAW_NUMBER], LAW_EFFECTIVE_DATE: law[EFFECTIVE_DATE], ARTICLE_NUMBER: article[NUMBER], ARTICLE_TITLE: article[TITLE], CHAPTER: article[LOCATION][CHAPTER], SECTION: article[LOCATION][SECTION], TEXT: text, METADATA: article[METADATA], PART_INDEX: part_index, PART_COUNT: part_count}

    def _prefix_lines(self, law: dict, article: dict) -> list[str]:
        lines = []
        if law[NAME]:
            lines.append(law[NAME])
        supplement = article.get(SUPPLEMENT)
        if supplement:
            lines.append(supplement[HEADING])
            lines.extend(supplement.get(PREAMBLE, []))
        for value in (article[LOCATION][CHAPTER], article[LOCATION][SECTION]):
            if value:
                lines.append(value)
        return lines

    def _build_article_text(self, law: dict, article: dict) -> str:
        if SOURCE_LINES in article:
            lines = self._prefix_lines(law=law, article=article) + article[SOURCE_LINES]
            return '\n'.join(lines)
        lines = self._prefix_lines(law=law, article=article)
        article_heading = article[NUMBER]
        if article[TITLE]:
            article_heading += f'({article[TITLE]})'
        lines.append(article_heading)
        if article[BODY]:
            lines.append(article[BODY])
        for paragraph in article[PARAGRAPHS]:
            paragraph_text = f'{paragraph[NUMBER]} {paragraph[TEXT]}'
            lines.append(paragraph_text)
            for item in paragraph[ITEMS]:
                self._append_item(lines=lines, item=item)
        for item in article[ITEMS]:
            self._append_item(lines=lines, item=item)
        return '\n'.join(lines)

    def _append_item(self, lines: list[str], item: dict) -> None:
        lines.append(f'{item[NUMBER]}. {item[TEXT]}')
        for subitem in item[SUBITEMS]:
            lines.append(f'{subitem[NUMBER]}. {subitem[TEXT]}')

    def save_json(self, chunks: list[dict], output_path: str=CHUNKS_PATH) -> Path:
        return write_json(chunks, output_path)
