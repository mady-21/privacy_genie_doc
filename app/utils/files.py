"""출력 파일 생성과 JSON 저장의 공통 처리."""
import json
from pathlib import Path
from app.constants.paths import TEXT_ENCODING


def prepare_output_path(output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def save_json(data, output_path: str | Path) -> Path:
    path = prepare_output_path(output_path)
    with path.open("w", encoding=TEXT_ENCODING) as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    return path
