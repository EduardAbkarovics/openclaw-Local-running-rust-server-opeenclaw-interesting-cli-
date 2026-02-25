/// HTTP kliens a Python LLM szerver felé.
/// Támogatja a normál és a streaming (SSE) módot.

use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::time::Duration;
use tracing::{debug, warn};

use crate::error::AppError;

// ---------------------------------------------------------------------------
// Request / Response struktúrák (tükrözik a Python API-t)
// ---------------------------------------------------------------------------

#[derive(Debug, Serialize, Clone)]
pub struct LlmRequest {
    pub prompt: String,
    pub max_new_tokens: u32,
    pub temperature: f32,
    pub top_p: f32,
    pub top_k: u32,
    pub repetition_penalty: f32,
    pub stream: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub system_prompt: Option<String>,
}

impl Default for LlmRequest {
    fn default() -> Self {
        Self {
            prompt: String::new(),
            max_new_tokens: 512,
            temperature: 0.7,
            top_p: 0.95,
            top_k: 50,
            repetition_penalty: 1.1,
            stream: false,
            system_prompt: None,
        }
    }
}

#[derive(Debug, Deserialize)]
pub struct LlmResponse {
    pub text: String,
    pub tokens_generated: u32,
    pub elapsed_seconds: f64,
    pub model: String,
}

#[derive(Debug, Deserialize)]
pub struct HealthResponse {
    pub status: String,
    pub model: String,
    pub model_loaded: bool,
}

// ---------------------------------------------------------------------------
// LLM kliens
// ---------------------------------------------------------------------------

#[derive(Clone)]
pub struct LlmClient {
    client: Client,
    base_url: String,
}

impl LlmClient {
    pub fn new(base_url: &str) -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(300)) // LLM generálás lassú lehet
            .connect_timeout(Duration::from_secs(10))
            .build()
            .expect("Reqwest kliens létrehozása sikertelen");

        Self {
            client,
            base_url: base_url.trim_end_matches('/').to_string(),
        }
    }

    /// Egyszeri (nem streaming) generálás.
    pub async fn generate(&self, req: LlmRequest) -> Result<LlmResponse, AppError> {
        let url = format!("{}/generate", self.base_url);
        debug!("LLM kérés küldése: {url}");

        let response = self
            .client
            .post(&url)
            .json(&req)
            .send()
            .await
            .map_err(|e| {
                warn!("Python LLM elérhetetlen: {e}");
                AppError::LlmUnavailable(e.to_string())
            })?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(AppError::LlmGeneration(format!(
                "HTTP {status}: {body}"
            )));
        }

        let llm_resp: LlmResponse = response
            .json()
            .await
            .map_err(|e| AppError::LlmGeneration(e.to_string()))?;

        debug!(
            "LLM válasz: {} token, {:.2}s",
            llm_resp.tokens_generated, llm_resp.elapsed_seconds
        );

        Ok(llm_resp)
    }

    /// Streaming generálás – tokenenként hívja a callback-et.
    pub async fn generate_streaming<F>(
        &self,
        req: LlmRequest,
        mut on_token: F,
    ) -> Result<(), AppError>
    where
        F: FnMut(String) + Send,
    {
        let mut stream_req = req;
        stream_req.stream = true;

        let url = format!("{}/generate", self.base_url);

        let response = self
            .client
            .post(&url)
            .json(&stream_req)
            .send()
            .await
            .map_err(|e| AppError::LlmUnavailable(e.to_string()))?;

        // SSE parsing – minden sor "data: <token>" formátumú
        use reqwest::header::CONTENT_TYPE;
        let ct = response
            .headers()
            .get(CONTENT_TYPE)
            .and_then(|v| v.to_str().ok())
            .unwrap_or("");

        if !ct.contains("text/event-stream") {
            return Err(AppError::LlmGeneration(
                "A szerver nem adott SSE választ.".to_string(),
            ));
        }

        let mut stream = response.bytes_stream();
        use futures_util::StreamExt;
        let mut buffer = String::new();

        while let Some(chunk) = stream.next().await {
            let chunk = chunk.map_err(|e| AppError::LlmGeneration(e.to_string()))?;
            buffer.push_str(&String::from_utf8_lossy(&chunk));

            // Soronként feldolgozás
            while let Some(pos) = buffer.find('\n') {
                let line = buffer[..pos]
                    .trim_end_matches('\r')
                    .to_string();
                buffer = buffer[pos + 1..].to_string();

                if let Some(data) = line.strip_prefix("data: ") {
                    if data == "[DONE]" {
                        return Ok(());
                    }
                    on_token(data.to_string());
                }
            }
        }

        Ok(())
    }

    /// Python LLM szerver egészségügyi ellenőrzése.
    pub async fn health(&self) -> Result<HealthResponse, AppError> {
        let url = format!("{}/health", self.base_url);
        let resp = self
            .client
            .get(&url)
            .timeout(Duration::from_secs(5))
            .send()
            .await
            .map_err(|e| AppError::LlmUnavailable(e.to_string()))?;

        resp.json::<HealthResponse>()
            .await
            .map_err(|e| AppError::LlmGeneration(e.to_string()))
    }
}
