//! OpenAI-compatible /v1 API for OpenClaw gateway.
//! Allows the OpenClaw app (openclaw gateway) to use our local Rust+LLM stack without API keys.

use axum::{extract::State, Json};
use serde::{Deserialize, Serialize};
use tracing::debug;

use crate::error::AppError;
use crate::routes::AppState;

// ---------------------------------------------------------------------------
// OpenAI request/response types (minimal subset)
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
pub struct OpenAIChatMessage {
    pub role: String,
    pub content: String,
}

#[derive(Debug, Deserialize)]
pub struct OpenAIChatRequest {
    pub model: Option<String>,
    pub messages: Vec<OpenAIChatMessage>,
    #[serde(default)]
    pub max_tokens: Option<u32>,
    #[serde(default)]
    pub stream: bool,
    #[serde(default)]
    pub temperature: Option<f32>,
}

#[derive(Debug, Serialize)]
pub struct OpenAIChatResponse {
    pub id: String,
    pub object: String,
    pub created: i64,
    pub model: String,
    pub choices: Vec<OpenAIChoice>,
    pub usage: OpenAIUsage,
}

#[derive(Debug, Serialize)]
pub struct OpenAIChoice {
    pub index: u32,
    pub message: OpenAIMessage,
    pub finish_reason: String,
}

#[derive(Debug, Serialize)]
pub struct OpenAIMessage {
    pub role: String,
    pub content: String,
}

#[derive(Debug, Serialize)]
pub struct OpenAIUsage {
    pub prompt_tokens: u32,
    pub completion_tokens: u32,
    pub total_tokens: u32,
}

#[derive(Debug, Serialize)]
pub struct OAIModel {
    pub id: String,
    pub object: String,
    pub created: i64,
    pub owned_by: String,
}

#[derive(Debug, Serialize)]
pub struct OAIModelsList {
    pub object: String,
    pub data: Vec<OAIModel>,
}

// ---------------------------------------------------------------------------
// Router (unused – routes registered in routes.rs)
// ---------------------------------------------------------------------------

// GET /v1/models – OpenClaw discovers the local model
pub async fn handle_models(State(state): State<AppState>) -> Json<OAIModelsList> {
    let model_id = "openclaw-local";
    Json(OAIModelsList {
        object: "list".to_string(),
        data: vec![OAIModel {
            id: model_id.to_string(),
            object: "model".to_string(),
            created: 1700000000,
            owned_by: state.cfg.bot_name.clone(),
        }],
    })
}

// ---------------------------------------------------------------------------
// POST /v1/chat/completions – OpenAI format → our LLM → OpenAI format
// ---------------------------------------------------------------------------

pub async fn handle_chat_completions(
    State(state): State<AppState>,
    Json(req): Json<OpenAIChatRequest>,
) -> Result<Json<OpenAIChatResponse>, AppError> {
    if req.messages.is_empty() {
        return Err(AppError::BadRequest(
            "messages cannot be empty".to_string(),
        ));
    }

    let max_tokens = req
        .max_tokens
        .unwrap_or(state.cfg.default_max_tokens)
        .min(4096);

    // Build prompt from OpenAI messages: system + conversation
    let (system_prompt, prompt) = messages_to_prompt(&req.messages);

    let llm_req = crate::llm_client::LlmRequest {
        prompt,
        system_prompt: if system_prompt.is_empty() {
            None
        } else {
            Some(system_prompt)
        },
        max_new_tokens: max_tokens,
        temperature: req.temperature.unwrap_or(0.7),
        top_p: 0.95,
        top_k: 50,
        repetition_penalty: 1.1,
        stream: false,
    };

    debug!("OpenAI compat: calling local LLM");
    let resp = state.llm.generate(llm_req).await?;
    let content = state.bot.postprocess_response(&resp.text);

    let completion_tokens = resp.tokens_generated;
    let prompt_tokens = 0u32;
    let total_tokens = prompt_tokens + completion_tokens;

    Ok(Json(OpenAIChatResponse {
        id: format!("chatcmpl-{}", uuid::Uuid::new_v4()),
        object: "chat.completion".to_string(),
        created: chrono::Utc::now().timestamp(),
        model: req.model.unwrap_or_else(|| "openclaw-local".to_string()),
        choices: vec![OpenAIChoice {
            index: 0,
            message: OpenAIMessage {
                role: "assistant".to_string(),
                content,
            },
            finish_reason: "stop".to_string(),
        }],
        usage: OpenAIUsage {
            prompt_tokens,
            completion_tokens,
            total_tokens,
        },
    }))
}

/// Convert OpenAI messages to (system_prompt, user_prompt) for our LLM.
fn messages_to_prompt(messages: &[OpenAIChatMessage]) -> (String, String) {
    let mut system = String::new();
    let mut parts: Vec<String> = Vec::new();

    for m in messages {
        let content = m.content.trim();
        if content.is_empty() {
            continue;
        }
        match m.role.to_lowercase().as_str() {
            "system" => {
                if system.is_empty() {
                    system = content.to_string();
                } else {
                    system.push_str("\n\n");
                    system.push_str(content);
                }
            }
            "user" => {
                parts.push(format!("User: {}", content));
            }
            "assistant" => {
                parts.push(format!("Assistant: {}", content));
            }
            _ => {
                parts.push(format!("User: {}", content));
            }
        }
    }

    if system.is_empty() {
        system = "You are a helpful programming assistant. Respond in the same language as the user."
            .to_string();
    }

    let prompt = parts.join("\n\n");
    (system, prompt)
}
