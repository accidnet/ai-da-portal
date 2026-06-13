from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import BadZipFile, ZipFile, ZipInfo
import mimetypes

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from core.paths import DATA_SOURCE_STORAGE_DIR
from features.data_sources.api.deps import get_data_source_usecase
from features.data_sources.api.schemas import (
    DataSourceItemResponse,
    DataSourceDeleteResponse,
    DataSourceTreeResponse,
    DataSourceUploadResponse,
)
from features.data_sources.application.dto import (
    DataSourceItemResult,
    DataSourceDeleteResult,
    DataSourceUploadCommand,
    DataSourceUploadFile,
    DataSourceUploadResult,
)
from features.data_sources.application.usecase import DataSourceUsecase

router = APIRouter()

MAX_ZIP_ENTRY_COUNT = 20000
MAX_ZIP_UNCOMPRESSED_BYTES = 10 * 1024 * 1024 * 1024


@router.post(
    "/uploads",
    response_model=DataSourceUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_data_sources(
    files: list[UploadFile] = File(...),
    relative_paths: list[str] | None = Form(default=None),
    extract_zip: bool = Form(default=False),
    usecase: DataSourceUsecase = Depends(get_data_source_usecase),
) -> DataSourceUploadResponse:
    """파일 여러 개 또는 폴더 선택 결과를 원천 데이터 저장소에 업로드합니다."""
    temp_paths: list[Path] = []
    try:
        upload_files: list[DataSourceUploadFile] = []
        for file in files:
            upload_file = await _spool_upload_file(file)
            if upload_file.temp_path is not None:
                temp_paths.append(upload_file.temp_path)
            if extract_zip and _is_zip_upload(upload_file):
                extracted_files = _extract_zip_upload_file(upload_file)
                temp_paths.extend(
                    extracted_file.temp_path
                    for extracted_file in extracted_files
                    if extracted_file.temp_path is not None
                )
                upload_files.extend(extracted_files)
            else:
                upload_files.append(upload_file)
        result = usecase.upload(
            DataSourceUploadCommand(
                files=upload_files,
                relative_paths=[] if extract_zip else relative_paths or [],
            )
        )
    except (BadZipFile, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    finally:
        for temp_path in temp_paths:
            temp_path.unlink(missing_ok=True)

    return _to_upload_response(result)


@router.get("/tree", response_model=DataSourceTreeResponse)
def list_data_source_tree(
    usecase: DataSourceUsecase = Depends(get_data_source_usecase),
) -> DataSourceTreeResponse:
    """DB에 저장된 flat 노드를 프론트 표시용 트리 구조로 반환합니다."""
    return DataSourceTreeResponse(items=_build_tree_response(usecase.list_items()))


@router.delete("/{item_id}", response_model=DataSourceDeleteResponse)
def delete_data_source_item(
    item_id: str,
    usecase: DataSourceUsecase = Depends(get_data_source_usecase),
) -> DataSourceDeleteResponse:
    """원천 데이터 파일 또는 폴더 노드를 삭제합니다."""
    try:
        return _to_delete_response(usecase.delete(item_id))
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source item '{item_id}' was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


def _to_upload_response(result: DataSourceUploadResult) -> DataSourceUploadResponse:
    """application 업로드 결과를 API 응답으로 변환합니다."""
    return DataSourceUploadResponse(items=_build_tree_response(result.items))


async def _spool_upload_file(file: UploadFile) -> DataSourceUploadFile:
    """FastAPI 업로드 파일을 메모리 대신 임시 파일로 스트리밍합니다."""
    DATA_SOURCE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    size_bytes = 0
    with NamedTemporaryFile(
        dir=DATA_SOURCE_STORAGE_DIR,
        prefix="upload__",
        delete=False,
    ) as temp_file:
        temp_path = Path(temp_file.name)
        while chunk := await file.read(1024 * 1024):
            size_bytes += len(chunk)
            temp_file.write(chunk)

    return DataSourceUploadFile(
        filename=file.filename or "uploaded-file",
        content_type=file.content_type,
        temp_path=temp_path,
        size_bytes=size_bytes,
    )


def _extract_zip_upload_file(file: DataSourceUploadFile) -> list[DataSourceUploadFile]:
    """zip 파일명 폴더 아래에 내부 파일을 배치하도록 임시 파일로 풉니다."""
    if file.temp_path is None:
        raise ValueError("Zip upload file is not available.")
    if not _is_zip_upload(file):
        raise ValueError("Only zip files can be extracted.")

    extracted_files: list[DataSourceUploadFile] = []
    try:
        total_size = 0
        zip_root_name = _build_zip_root_name(file.filename)
        with ZipFile(file.temp_path) as archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            if not infos:
                raise ValueError("Zip file does not contain files.")
            if len(infos) > MAX_ZIP_ENTRY_COUNT:
                raise ValueError(
                    f"Zip file contains too many files. Maximum {MAX_ZIP_ENTRY_COUNT} files are supported."
                )

            for info in infos:
                member_path = _validate_zip_member_path(info.filename)
                relative_path = f"{zip_root_name}/{member_path}"
                total_size += info.file_size
                if total_size > MAX_ZIP_UNCOMPRESSED_BYTES:
                    raise ValueError("Zip file is too large after extraction.")
                if info.flag_bits & 0x1:
                    raise ValueError("Encrypted zip files are not supported.")

                content_type, _ = mimetypes.guess_type(relative_path)
                extracted_files.append(
                    _extract_zip_member(
                        archive=archive,
                        info=info,
                        relative_path=relative_path,
                        content_type=content_type,
                    )
                )
    except Exception:
        for extracted_file in extracted_files:
            if extracted_file.temp_path is not None:
                extracted_file.temp_path.unlink(missing_ok=True)
        raise

    return extracted_files


def _build_zip_root_name(filename: str) -> str:
    """업로드된 zip 파일명을 최상위 폴더명으로 쓸 수 있게 정규화합니다."""
    raw_name = Path(filename.replace("\\", "/")).name
    stem = Path(raw_name).stem.strip()
    return _validate_zip_member_path(stem or "uploaded-zip")


def _is_zip_upload(file: DataSourceUploadFile) -> bool:
    """확장자와 content type을 함께 확인해 zip 해제 대상만 허용합니다."""
    content_type = (file.content_type or "").lower()
    return file.filename.lower().endswith(".zip") or content_type in {
        "application/zip",
        "application/x-zip-compressed",
        "multipart/x-zip",
    }


def _validate_zip_member_path(filename: str) -> str:
    """zip slip을 막기 위해 내부 경로를 안전한 상대 경로로 제한합니다."""
    normalized_path = filename.replace("\\", "/").strip()
    if (
        not normalized_path
        or normalized_path.startswith("/")
        or any(part in {"", ".", ".."} for part in normalized_path.split("/"))
        or Path(normalized_path).is_absolute()
    ):
        raise ValueError("Zip file contains an unsafe path.")
    return normalized_path


def _extract_zip_member(
    *,
    archive: ZipFile,
    info: ZipInfo,
    relative_path: str,
    content_type: str | None,
) -> DataSourceUploadFile:
    """zip 엔트리를 임시 파일로 스트리밍해 대용량 파일 메모리 적재를 피합니다."""
    DATA_SOURCE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        dir=DATA_SOURCE_STORAGE_DIR,
        prefix="upload_zip__",
        delete=False,
    ) as temp_file:
        temp_path = Path(temp_file.name)
        with archive.open(info) as source_file:
            while chunk := source_file.read(1024 * 1024):
                temp_file.write(chunk)

    return DataSourceUploadFile(
        filename=relative_path,
        content_type=content_type,
        temp_path=temp_path,
        size_bytes=info.file_size,
    )


def _to_delete_response(result: DataSourceDeleteResult) -> DataSourceDeleteResponse:
    """application 삭제 결과를 API 응답으로 변환합니다."""
    return DataSourceDeleteResponse(
        id=result.id,
        deleted=result.deleted,
        deleted_count=result.deleted_count,
    )


def _to_item_response(item: DataSourceItemResult) -> DataSourceItemResponse:
    """application 파일/폴더 DTO를 API 응답으로 변환합니다."""
    return DataSourceItemResponse(
        id=item.id,
        parent_id=item.parent_id,
        item_type=item.item_type,
        name=item.name,
        relative_path=item.relative_path,
        depth=item.depth,
        sort_order=item.sort_order,
        content_type=item.content_type,
        size_bytes=item.size_bytes,
        storage_path=item.storage_path,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _build_tree_response(
    items: list[DataSourceItemResult],
) -> list[DataSourceItemResponse]:
    """parent_id 관계를 사용해 flat 노드를 트리 응답으로 조립합니다."""
    node_by_id = {item.id: _to_item_response(item) for item in items}
    roots: list[DataSourceItemResponse] = []

    for item in sorted(
        items, key=lambda item: (item.depth, item.sort_order, item.name)
    ):
        node = node_by_id[item.id]
        if item.parent_id and item.parent_id in node_by_id:
            node_by_id[item.parent_id].children.append(node)
        else:
            roots.append(node)

    return roots
