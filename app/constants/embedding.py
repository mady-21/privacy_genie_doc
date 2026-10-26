"임베딩 모델 설정. 모델을 바꾸면 web의 벡터 컬럼 차원도 같이 바꿔야 한다."
from typing import Final

EMBEDDING_MODEL: Final = 'nlpai-lab/KURE-v1'
EMBEDDING_DIMENSION: Final = 1024
MAX_TEXTS_PER_REQUEST: Final = 64
MAX_TEXT_CHARS: Final = 10_000
DEFAULT_SEARCH_TOP_K: Final = 5
MAX_SEARCH_TOP_K: Final = 20
