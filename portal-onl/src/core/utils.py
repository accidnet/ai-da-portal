def read_string(value: object) -> str | None:
    """공백이 제거된 문자열 값을 읽고, 빈값 또는 잘못된 값일 경우에는 모두 None로 return합니다."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
