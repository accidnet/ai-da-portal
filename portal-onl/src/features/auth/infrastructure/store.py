from pathlib import Path

from features.auth.domain.models import OpenAiAuthState


class OpenAiAuthStore:
    """OpenAI 인증 상태를 로컬 JSON 파일에 저장합니다."""

    def __init__(self, storage_path: str) -> None:
        self._path = Path(storage_path)

    def load(self) -> OpenAiAuthState:
        """저장된 인증 상태를 읽고, 파일이 없으면 빈 상태를 반환합니다."""
        if not self._path.exists():
            return OpenAiAuthState()
        return OpenAiAuthState.model_validate_json(
            self._path.read_text(encoding="utf-8")
        )

    def save(self, state: OpenAiAuthState) -> None:
        """인증 토큰을 포함한 상태를 설정된 파일 경로에 기록합니다."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # OAuth 토큰은 설정된 data 하위 경로에만 쓰도록
        # dependency에서 경로를 주입합니다.
        self._path.write_text(
            state.model_dump_json(indent=2),
            encoding="utf-8",
        )
