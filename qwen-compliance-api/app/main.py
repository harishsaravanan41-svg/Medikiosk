import os
import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from dotenv import load_dotenv

from app.schemas import ChatCompletionRequest, ChatCompletionResponse, HealthResponse, ErrorResponse
from app.auth import verify_api_key
from app.model import QwenModelService

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("qwen_api.main")

model_service = QwenModelService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up FastAPI Qwen Model Server...")
    try:
        model_service.load_model()
    except Exception as e:
        logger.error(f"Critical error during model startup: {e}")
        raise e
    yield
    logger.info("Shutting down Qwen Model Server...")

app = FastAPI(
    title="Qwen 2.5 Conversational API",
    description="Local REST & Streaming API for serving Qwen2.5-1.5B-Instruct model.",
    version="2.0.0",
    lifespan=lifespan
)

allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "detail": exc.detail}
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Internal server error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"success": False, "detail": "An internal server error occurred."}
    )

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    return HealthResponse(status="ok", model=os.getenv("MODEL_NAME", "qwen-2.5"))

@app.post("/v1/chat", response_model=ChatCompletionResponse, tags=["Chat"])
@app.post("/v1/chat/completions", response_model=ChatCompletionResponse, tags=["Chat"])
async def chat_completions(
    request: ChatCompletionRequest,
    api_key: str = Depends(verify_api_key)
):
    msg_present = (request.message and request.message.strip()) or (request.messages and len(request.messages) > 0)
    if not msg_present:
        raise HTTPException(status_code=400, detail="Request message or messages cannot be empty.")

    logger.info(f"Processing query")

    try:
        answer = model_service.generate_answer(
            user_message=request.message.strip() if request.message else None,
            messages=request.messages,
            system_prompt=request.system_prompt,
            max_new_tokens=request.max_new_tokens or 512,
            temperature=request.temperature or 0.5
        )
        return ChatCompletionResponse(response=answer, success=True, answer=answer)
    except Exception as e:
        logger.error(f"Model generation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate answer: {str(e)}"
        )

@app.post("/v1/chat/stream", tags=["Chat"])
async def chat_stream(
    request: ChatCompletionRequest,
    api_key: str = Depends(verify_api_key)
):
    msg_present = (request.message and request.message.strip()) or (request.messages and len(request.messages) > 0)
    if not msg_present:
        raise HTTPException(status_code=400, detail="Request message or messages cannot be empty.")

    logger.info(f"Streaming query")

    def token_generator():
        try:
            for token in model_service.generate_stream(
                user_message=request.message.strip() if request.message else None,
                messages=request.messages,
                system_prompt=request.system_prompt,
                max_new_tokens=request.max_new_tokens or 512,
                temperature=request.temperature or 0.5
            ):
                if token:
                    # ensure_ascii=False guarantees proper UTF-8 output without unicode escape/replacement corruption
                    yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'error': str(e), 'done': True}, ensure_ascii=False)}\n\n"

    return StreamingResponse(token_generator(), media_type="text/event-stream")
