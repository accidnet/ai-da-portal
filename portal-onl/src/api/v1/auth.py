from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse

from api.deps import get_openai_auth_service
from domain.auth.schemas import OpenAiAuthStatusResponse, OpenAiAuthorizeResponse
from domain.auth.service import OpenAiAuthError, OpenAiAuthService

router = APIRouter()


@router.get("/openai/status", response_model=OpenAiAuthStatusResponse)
def get_openai_auth_status(
    service: OpenAiAuthService = Depends(get_openai_auth_service),
) -> OpenAiAuthStatusResponse:
    return service.get_status()


@router.post("/openai/authorize", response_model=OpenAiAuthorizeResponse)
def authorize_openai(
    request: Request,
    service: OpenAiAuthService = Depends(get_openai_auth_service),
) -> OpenAiAuthorizeResponse:
    callback_url = str(request.url_for("openai_auth_callback"))
    return service.build_authorize_url(callback_url)


@router.get("/openai/callback", response_class=HTMLResponse, name="openai_auth_callback")
def openai_auth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    service: OpenAiAuthService = Depends(get_openai_auth_service),
) -> HTMLResponse:
    if error:
        description = error_description or error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OpenAI authentication failed: {description}",
        )
    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenAI callback requires both code and state.",
        )

    try:
        token_bundle = service.complete_callback(code=code, state_value=state)
    except OpenAiAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    account_label = token_bundle.account_email or "your ChatGPT account"
    html = f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>ChatGPT Connected</title>
    <style>
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        font-family: "Segoe UI", system-ui, sans-serif;
        background: linear-gradient(180deg, #f4f7fb 0%, #dfe9f6 100%);
        color: #17314d;
      }}
      main {{
        width: min(92vw, 520px);
        padding: 32px;
        border-radius: 28px;
        background: rgba(255, 255, 255, 0.92);
        box-shadow: 0 24px 60px rgba(23, 49, 77, 0.14);
      }}
      h1 {{
        margin: 0 0 12px;
      }}
      p {{
        line-height: 1.7;
      }}
      button {{
        margin-top: 18px;
        padding: 14px 18px;
        border: 0;
        border-radius: 16px;
        color: white;
        background: #1f5ca8;
        cursor: pointer;
      }}
    </style>
  </head>
  <body>
    <main>
      <h1>ChatGPT is connected</h1>
      <p>Authentication completed for <strong>{account_label}</strong>. You can return to the portal and start using GPT-backed responses.</p>
      <button type="button" onclick="window.close()">Close this window</button>
    </main>
  </body>
</html>
""".strip()
    return HTMLResponse(content=html, status_code=status.HTTP_200_OK)
