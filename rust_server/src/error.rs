use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde_json::json;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum AppError {
    #[error("Python LLM szerver nem elérhető: {0}")]
    LlmUnavailable(String),

    #[error("LLM generálási hiba: {0}")]
    LlmGeneration(String),

    #[error("Érvénytelen kérés: {0}")]
    BadRequest(String),

    #[allow(dead_code)]  // jövőbeli rate limiting middleware-hez
    #[error("Rate limit túllépve")]
    RateLimited,

    #[error("Belső szerver hiba: {0}")]
    Internal(#[from] anyhow::Error),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, code, message) = match &self {
            AppError::LlmUnavailable(msg) => (
                StatusCode::SERVICE_UNAVAILABLE,
                "llm_unavailable",
                msg.clone(),
            ),
            AppError::LlmGeneration(msg) => (
                StatusCode::INTERNAL_SERVER_ERROR,
                "llm_error",
                msg.clone(),
            ),
            AppError::BadRequest(msg) => (
                StatusCode::BAD_REQUEST,
                "bad_request",
                msg.clone(),
            ),
            AppError::RateLimited => (
                StatusCode::TOO_MANY_REQUESTS,
                "rate_limited",
                "Túl sok kérés, próbálj újra később.".to_string(),
            ),
            AppError::Internal(e) => (
                StatusCode::INTERNAL_SERVER_ERROR,
                "internal_error",
                e.to_string(),
            ),
        };

        let body = Json(json!({
            "error": {
                "code": code,
                "message": message,
            }
        }));

        (status, body).into_response()
    }
}
