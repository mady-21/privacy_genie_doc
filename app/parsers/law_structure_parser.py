from app.utils.files import save_json as write_json
from app.constants.paths import CLASSIFICATION_PATH, STRUCTURE_PATH, TEXT_ENCODING
from app.constants.law import ARTICLE, ARTICLES, ARTICLE_CREATED, BODY, CHAPTER, CREATED, DOCUMENT_PART, EFFECTIVE_DATE, HEADING, ID, ITEM, ITEMS, LAW, LAW_METADATA_SCAN_LIMIT, LAW_NUMBER, LOCATION, MAIN, METADATA, NAME, NUMBER, OCCURRENCE, OTHER, PARAGRAPH, PARAGRAPHS, PREAMBLE, PROMULGATION_DATE, SECTION, SOURCE_LINES, SUBITEM, SUBITEMS, SUPPLEMENT, SUPPLEMENTARY, SUPPLEMENTS, TEXT, TITLE, TITLE_AMENDED
import re
from pathlib import Path

class LawStructureParser:
    SUPPLEMENT_PATTERN = re.compile('^부\\s*칙(?:\\s|[<〈\\[]|$)')
    DATE_PATTERN = re.compile('(\\d{4})\\.\\s*(\\d{1,2})\\.\\s*(\\d{1,2})\\.?')
    CHAPTER_PATTERN = re.compile('^제\\d+장(?:의\\d+)?\\s+.+')
    SECTION_PATTERN = re.compile('^제\\d+절(?:의\\d+)?\\s+.+')
    ARTICLE_PATTERN = re.compile('^(제\\d+조(?:의\\d+)?)(?:\\(([^)]+)\\))?\\s*(.*)$')
    PARAGRAPH_PATTERN = re.compile('^([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳])\\s*(.*)$')
    ITEM_PATTERN = re.compile('^(\\d+(?:의\\d+)?)\\.\\s*(.*)$')
    SUBITEM_PATTERN = re.compile('^([가-하])\\.\\s*(.*)$')
    ARTICLE_CREATED_PATTERN = re.compile('^\\[본조신설')
    TITLE_AMENDED_PATTERN = re.compile('^\\[제목개정')
    LAW_EFFECTIVE_PATTERN = re.compile('\\[시행\\s+(\\d{4}\\.\\s*\\d{1,2}\\.\\s*\\d{1,2}\\.)\\]')
    SUPPLEMENT_NUMBER_PATTERN = re.compile(r"(?:법률|대통령령)\s+제\s*\d+\s*호")
    LAW_NUMBER_PATTERN = re.compile(r'\[((?:법률|대통령령)\s+제\d+호)')

    def classify(self, text: str) -> str:
        text = text.strip()
        if self.SUPPLEMENT_PATTERN.match(text):
            return SUPPLEMENTARY
        if self.CHAPTER_PATTERN.match(text):
            return CHAPTER
        if self.SECTION_PATTERN.match(text):
            return SECTION
        if self.ARTICLE_PATTERN.match(text):
            return ARTICLE
        if self.PARAGRAPH_PATTERN.match(text):
            return PARAGRAPH
        if self.ITEM_PATTERN.match(text):
            return ITEM
        if self.SUBITEM_PATTERN.match(text):
            return SUBITEM
        if self.ARTICLE_CREATED_PATTERN.match(text):
            return ARTICLE_CREATED
        if self.TITLE_AMENDED_PATTERN.match(text):
            return TITLE_AMENDED
        return OTHER

    def parse(self, paragraphs: list[str]) -> dict:
        document = {LAW: {NAME: None, EFFECTIVE_DATE: None, LAW_NUMBER: None}, ARTICLES: []}
        self._parse_law_metadata(paragraphs=paragraphs, document=document)
        current_chapter = None
        current_section = None
        current_article = None
        current_paragraph = None
        current_item = None
        document[SUPPLEMENTS] = []
        current_supplement = None
        occurrence_counts = {}
        for text in paragraphs:
            text = text.strip()
            if not text:
                continue
            paragraph_type = self.classify(text)
            if paragraph_type == SUPPLEMENTARY:
                number_match = self._supplement_number_match(text, document[LAW][LAW_NUMBER])
                date_match = self.DATE_PATTERN.search(text)
                current_supplement = {ID: f'supplement-{len(document[SUPPLEMENTS]) + 1}', HEADING: text, LAW_NUMBER: number_match.group(0) if number_match else None, PROMULGATION_DATE: self._normalize_date(date_match) if date_match else None, PREAMBLE: []}
                document[SUPPLEMENTS].append(current_supplement)
                current_chapter = current_section = None
                current_article = current_paragraph = current_item = None
                continue
            if current_article and paragraph_type not in (ARTICLE, CHAPTER, SECTION):
                current_article[SOURCE_LINES].append(text)
            if paragraph_type == CHAPTER:
                current_chapter = text
                current_section = None
                continue
            if paragraph_type == SECTION:
                current_section = text
                continue
            if paragraph_type == ARTICLE:
                current_article = self._parse_article(text=text, chapter=current_chapter, section=current_section)
                current_article[DOCUMENT_PART] = SUPPLEMENTARY if current_supplement else MAIN
                current_article[SUPPLEMENT] = dict(current_supplement) if current_supplement else None
                current_article[SOURCE_LINES] = [text]
                scope = current_supplement[ID] if current_supplement else MAIN
                key = (scope, current_article[NUMBER])
                occurrence_counts[key] = occurrence_counts.get(key, 0) + 1
                current_article[OCCURRENCE] = occurrence_counts[key]
                document[ARTICLES].append(current_article)
                current_paragraph = None
                current_item = None
                if self.PARAGRAPH_PATTERN.match(current_article[BODY]):
                    current_paragraph = self._parse_paragraph(current_article[BODY])
                    current_article[PARAGRAPHS].append(current_paragraph)
                    current_article[BODY] = ''
                continue
            if paragraph_type == PARAGRAPH and current_article:
                current_paragraph = self._parse_paragraph(text)
                current_article[PARAGRAPHS].append(current_paragraph)
                current_item = None
                continue
            if paragraph_type == ITEM and current_article:
                item = self._parse_item(text)
                if current_paragraph:
                    current_paragraph[ITEMS].append(item)
                else:
                    current_article[ITEMS].append(item)
                current_item = item
                continue
            if paragraph_type == SUBITEM and current_item:
                current_item[SUBITEMS].append(self._parse_subitem(text))
                continue
            if paragraph_type == ARTICLE_CREATED and current_article:
                current_article[METADATA][CREATED] = text
                continue
            if paragraph_type == TITLE_AMENDED and current_article:
                current_article[METADATA][TITLE_AMENDED] = text
                continue
            if paragraph_type == OTHER and current_supplement and (not current_article):
                if re.match('^[<〈\\[]', text):
                    number_match = self._supplement_number_match(text, document[LAW][LAW_NUMBER])
                    date_match = self.DATE_PATTERN.search(text)
                    if number_match:
                        current_supplement[LAW_NUMBER] = number_match.group(0)
                    if date_match:
                        current_supplement[PROMULGATION_DATE] = self._normalize_date(date_match)
                    current_supplement[HEADING] += ' ' + text
                else:
                    current_supplement[PREAMBLE].append(text)
        return document

    def _supplement_number_match(self, text, document_number):
        match = self.SUPPLEMENT_NUMBER_PATTERN.search(text)
        if match:
            return match
        # 원문이 <제123호, ...>처럼 종류를 생략한 경우 문서 종류를 따른다.
        bare = re.search(r"제\s*\d+\s*호", text)
        if bare:
            prefix = "대통령령" if (document_number or "").startswith("대통령령") else "법률"
            return self.SUPPLEMENT_NUMBER_PATTERN.search(f"{prefix} {bare[0]}")
        return None

    @staticmethod
    def _normalize_date(match) -> str:
        return f'{int(match[1]):04d}-{int(match[2]):02d}-{int(match[3]):02d}'

    def _parse_law_metadata(self, paragraphs: list[str], document: dict) -> None:
        """
        문서 상단에서 법률 기본정보를 추출한다.

        예:
        개인정보 보호법

        [시행 2026. 9. 11.]
        [법률 제21445호, 2026. 3. 10., 일부개정]
        """
        if paragraphs:
            document[LAW][NAME] = paragraphs[0].strip()
        for text in paragraphs[:LAW_METADATA_SCAN_LIMIT]:
            text = text.strip()
            effective_match = self.LAW_EFFECTIVE_PATTERN.search(text)
            if effective_match:
                document[LAW][EFFECTIVE_DATE] = effective_match.group(1)
            law_number_match = self.LAW_NUMBER_PATTERN.search(text)
            if law_number_match:
                document[LAW][LAW_NUMBER] = law_number_match.group(1)

    def _parse_article(self, text: str, chapter: str | None, section: str | None) -> dict:
        match = self.ARTICLE_PATTERN.match(text)
        if not match:
            raise ValueError(f'Invalid article: {text}')
        number = match.group(1)
        title = match.group(2)
        body = match.group(3).strip()
        return {NUMBER: number, TITLE: title, LOCATION: {CHAPTER: chapter, SECTION: section}, BODY: body, PARAGRAPHS: [], ITEMS: [], METADATA: {}}

    def _parse_paragraph(self, text: str) -> dict:
        match = self.PARAGRAPH_PATTERN.match(text)
        if not match:
            raise ValueError(f'Invalid paragraph: {text}')
        return {NUMBER: match.group(1), TEXT: match.group(2).strip(), ITEMS: []}

    def _parse_item(self, text: str) -> dict:
        match = self.ITEM_PATTERN.match(text)
        if not match:
            raise ValueError(f'Invalid item: {text}')
        return {NUMBER: match.group(1), TEXT: match.group(2).strip(), SUBITEMS: []}

    def _parse_subitem(self, text: str) -> dict:
        match = self.SUBITEM_PATTERN.match(text)
        if not match:
            raise ValueError(f'Invalid subitem: {text}')
        return {NUMBER: match.group(1), TEXT: match.group(2).strip()}

    def save_classification(self, paragraphs: list[str], output_path: str=CLASSIFICATION_PATH) -> Path:
        """
        파싱 전 각 문단이 어떻게 분류되는지
        확인하기 위한 디버깅 파일.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding=TEXT_ENCODING) as file:
            for index, paragraph in enumerate(paragraphs, start=1):
                paragraph_type = self.classify(paragraph)
                file.write(f'[{index}] [{paragraph_type}]\n')
                file.write(paragraph)
                file.write('\n\n')
        return path

    def save_json(self, document: dict, output_path: str=STRUCTURE_PATH) -> Path:
        return write_json(document, output_path)
