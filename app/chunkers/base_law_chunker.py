from app.utils.files import save_json as write_json
from app.constants.paths import CHUNKS_PATH, TEXT_ENCODING
from app.constants.law import ARTICLES, ARTICLE_NUMBER, ARTICLE_TITLE, BODY, CHAPTER, CHUNK_ID, DOCUMENT_PART, EFFECTIVE_DATE, HEADING, ID, ITEMS, LAW, LAW_EFFECTIVE_DATE, LAW_NAME, LAW_NUMBER, LOCATION, MAIN, METADATA, NAME, NUMBER, OCCURRENCE, PARAGRAPHS, PREAMBLE, SECTION, SOURCE_LINES, SUBITEMS, SUPPLEMENT, TEXT, TITLE
from pathlib import Path

class BaseLawChunker:
    def should_exclude(self, article: dict) -> bool:
        return False

    def chunk(self, document: dict) -> list[dict]:
        chunks = []
        law = document[LAW]
        for article in document[ARTICLES]:
            chapter = article[LOCATION].get(CHAPTER) or ''
            if self.should_exclude(article):
                continue
            chunk = self._build_article_chunk(law=law, article=article)
            chunks.append(chunk)
        return chunks

    def _build_article_chunk(self, law: dict, article: dict) -> dict:
        text = self._build_article_text(law=law, article=article)
        supplement = article.get(SUPPLEMENT)
        scope = supplement[ID] if supplement else MAIN
        return {'document_type': self.DOCUMENT_TYPE, CHUNK_ID: f'{law[LAW_NUMBER]}:{scope}:{article[NUMBER]}:{article.get(OCCURRENCE, 1)}', DOCUMENT_PART: article.get(DOCUMENT_PART, MAIN), SUPPLEMENT: supplement, LAW_NAME: law[NAME], LAW_NUMBER: law[LAW_NUMBER], LAW_EFFECTIVE_DATE: law[EFFECTIVE_DATE], ARTICLE_NUMBER: article[NUMBER], ARTICLE_TITLE: article[TITLE], CHAPTER: article[LOCATION][CHAPTER], SECTION: article[LOCATION][SECTION], TEXT: text, METADATA: article[METADATA]}

    def _build_article_text(self, law: dict, article: dict) -> str:
        lines = []
        if law[NAME]:
            lines.append(law[NAME])
        supplement = article.get(SUPPLEMENT)
        if supplement:
            lines.append(supplement[HEADING])
            lines.extend(supplement.get(PREAMBLE, []))
        if SOURCE_LINES in article:
            for value in (article[LOCATION][CHAPTER], article[LOCATION][SECTION]):
                if value:
                    lines.append(value)
            lines.extend(article[SOURCE_LINES])
            return '\n'.join(lines)
        chapter = article[LOCATION][CHAPTER]
        if chapter:
            lines.append(chapter)
        section = article[LOCATION][SECTION]
        if section:
            lines.append(section)
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
