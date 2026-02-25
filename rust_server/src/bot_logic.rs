/// ClawDBot logika – prompt összeállítás, kontextus kezelés, válasz feldolgozás.

use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc};

use crate::llm_client::LlmRequest;

// ---------------------------------------------------------------------------
// Üzenet típusok
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum Role {
    System,
    User,
    Assistant,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub role: Role,
    pub content: String,
    pub timestamp: DateTime<Utc>,
}

impl Message {
    pub fn user(content: impl Into<String>) -> Self {
        Self {
            role: Role::User,
            content: content.into(),
            timestamp: Utc::now(),
        }
    }

    pub fn assistant(content: impl Into<String>) -> Self {
        Self {
            role: Role::Assistant,
            content: content.into(),
            timestamp: Utc::now(),
        }
    }
}

// ---------------------------------------------------------------------------
// Chat session (kontextus tárolás)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatSession {
    pub id: Uuid,
    pub created_at: DateTime<Utc>,
    pub last_active: DateTime<Utc>,
    pub messages: Vec<Message>,
    /// Maximálisan megőrzött üzenetek száma (régebbiek törlése)
    pub max_history: usize,
}

impl ChatSession {
    pub fn new(max_history: usize) -> Self {
        let now = Utc::now();
        Self {
            id: Uuid::new_v4(),
            created_at: now,
            last_active: now,
            messages: Vec::new(),
            max_history,
        }
    }

    pub fn add_message(&mut self, msg: Message) {
        self.last_active = Utc::now();
        self.messages.push(msg);
        // Kontextus ablak limit
        if self.messages.len() > self.max_history * 2 {
            let drain_count = self.messages.len() - self.max_history * 2;
            self.messages.drain(0..drain_count);
        }
    }
}

// ---------------------------------------------------------------------------
// ClawDBot prompt builder
// ---------------------------------------------------------------------------

pub struct BotLogic {
    system_prompt: String,
    bot_name: String,
}

impl BotLogic {
    pub fn new(bot_name: &str) -> Self {
        let system_prompt = format!(
            "Te vagy {bot_name}, egy intelligens kód-asszisztens bot. \
            Feladatod, hogy segíts a felhasználóknak programozási kérdésekben, \
            kódhibák javításában és szoftvertervezésben. \
            Legyél tömör, pontos, és mindig adj működő kód példákat. \
            Magyar és angol nyelven egyaránt kommunikálsz."
        );

        Self {
            system_prompt,
            bot_name: bot_name.to_string(),
        }
    }

    /// Felhasználói üzenetből LLM kérést épít, beleértve a chat history-t.
    pub fn build_llm_request(
        &self,
        user_message: &str,
        session: &ChatSession,
        max_new_tokens: u32,
    ) -> LlmRequest {
        // Kontextus: az előző néhány üzenet belekerül a promptba
        let history_text = self.format_history(&session.messages);

        let prompt = if history_text.is_empty() {
            user_message.to_string()
        } else {
            format!("{history_text}\n\nUser: {user_message}")
        };

        LlmRequest {
            prompt,
            system_prompt: Some(self.system_prompt.clone()),
            max_new_tokens,
            temperature: 0.7,
            top_p: 0.95,
            top_k: 50,
            repetition_penalty: 1.1,
            stream: false,
        }
    }

    pub fn build_streaming_request(
        &self,
        user_message: &str,
        session: &ChatSession,
        max_new_tokens: u32,
    ) -> LlmRequest {
        let mut req = self.build_llm_request(user_message, session, max_new_tokens);
        req.stream = true;
        req
    }

    /// Előző üzeneteket szövegként formázza.
    fn format_history(&self, messages: &[Message]) -> String {
        messages
            .iter()
            .filter(|m| m.role != Role::System)
            .map(|m| {
                let role_label = match m.role {
                    Role::User => "User",
                    Role::Assistant => self.bot_name.as_str(),
                    Role::System => "System",
                };
                format!("{}: {}", role_label, m.content)
            })
            .collect::<Vec<_>>()
            .join("\n")
    }

    /// Tisztítja az LLM nyers kimenetét (felesleges prefixek eltávolítása stb.)
    pub fn postprocess_response(&self, raw: &str) -> String {
        let raw = raw.trim();

        // Eltávolítjuk ha a bot saját nevével kezdi a választ
        let prefixes = [
            &format!("{}:", self.bot_name),
            "Assistant:",
            "### Response:",
        ];

        for prefix in &prefixes {
            if let Some(stripped) = raw.strip_prefix(prefix) {
                return stripped.trim().to_string();
            }
        }

        raw.to_string()
    }
}

// ---------------------------------------------------------------------------
// Kérés / Válasz struktúrák a Rust API-hoz (HTTP)
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
pub struct ChatRequest {
    pub message: String,
    #[serde(default)]
    pub session_id: Option<Uuid>,
    /// None → szerver alapértelmezett (AppConfig::default_max_tokens)
    pub max_tokens: Option<u32>,
}

#[derive(Debug, Serialize)]
pub struct ChatResponse {
    pub session_id: Uuid,
    pub reply: String,
    pub tokens_generated: u32,
    pub elapsed_seconds: f64,
    pub model: String,
}
