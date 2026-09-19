from pathlib import Path
from zipfile import ZipFile
from xml.dom import minidom


class HwpxParser:
    def __init__(self, file_path: str, output_dir: str = "/app/docs/extracted"):
        self.file_path = Path(file_path)
        self.output_dir = Path(output_dir)

    def list_files(self) -> list[str]:
        with ZipFile(self.file_path, "r") as hwpx:
            return hwpx.namelist()

    def extract_section(self, section_name: str = "Contents/section0.xml"):
        self.output_dir.mkdir(parents=True, exist_ok=True)

        with ZipFile(self.file_path, "r") as hwpx:
            xml_data = hwpx.read(section_name)

        # 원본 XML
        raw_path = self.output_dir / "section0.xml"
        raw_path.write_bytes(xml_data)

        # 확인하기 좋게
        pretty_xml = minidom.parseString(xml_data).toprettyxml(
            indent="  ",
            encoding="utf-8",
        )

        pretty_path = self.output_dir / "section0_pretty.xml"
        pretty_path.write_bytes(pretty_xml)

        return raw_path, pretty_path