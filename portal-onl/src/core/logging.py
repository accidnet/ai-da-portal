import logging
from logging.handlers import RotatingFileHandler

from core.config import get_settings
from core.paths import LOG_DIR


LOG_FILE_NAME = "portal.log"
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5


def configure_logging() -> None:
    """콘솔과 파일에 동일한 애플리케이션 로그를 남기도록 설정합니다."""
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=log_level,
        format=LOG_FORMAT,
        force=True,
    )
    root_logger = logging.getLogger()
    root_logger.addHandler(_build_file_handler(log_level))

    # OpenAI SDK/http client debug logs are too noisy for normal app runs.
    for logger_name in ("openai", "httpx", "httpcore", "python_multipart"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def _build_file_handler(log_level: int) -> RotatingFileHandler:
    """portal.log 파일에 로테이션 로그 핸들러를 생성합니다."""
    file_handler = RotatingFileHandler(
        LOG_DIR / LOG_FILE_NAME,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    return file_handler
