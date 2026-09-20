from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET


class HwpxParser:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)

    def parse(self) -> list[str]:
        paragraphs = []

        with ZipFile(self.file_path, "r") as hwpx:
            section_files = self._find_section_files(hwpx)

            for section_file in section_files:
                root = ET.fromstring(hwpx.read(section_file))
                paragraphs.extend(self._parse_section(root))

        return paragraphs

    def _find_section_files(self, hwpx: ZipFile) -> list[str]:
        return sorted(
            name
            for name in hwpx.namelist()
            if name.startswith("Contents/section")
            and name.endswith(".xml")
        )

    def _parse_section(self, root: ET.Element) -> list[str]:
        paragraphs = []

        for element in root:
            if self._local_name(element.tag) != "p":
                continue

            text = self._extract_text(element)

            if text:
                paragraphs.append(text)

        return paragraphs

    def _extract_text(self, paragraph: ET.Element) -> str:
        texts = []

        for element in paragraph.iter():
            if self._local_name(element.tag) != "t":
                continue

            if element.text:
                texts.append(element.text)

        return "".join(texts).strip()

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.split("}")[-1]