/// Axum route definíciók és handler-ek.

use std::collections::HashMap;
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::sync::{mpsc, RwLock};
use uuid::Uuid;

use axum::{
    extract::{ConnectInfo, State, WebSocketUpgrade},
    extract::ws::{Message as WsMessage, WebSocket},
    http::{Request, StatusCode},
    middleware::{self, Next},
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use futures_util::{SinkExt, StreamExt};
use serde_json::{json, Value};
use tracing::{debug, error, info, warn};

use crate::bot_logic::{BotLogic, ChatRequest, ChatResponse, ChatSession, Message as BotMessage};
use crate::config::AppConfig;
use crate::error::AppError;
use crate::llm_client::LlmClient;
use crate::middleware::{build_rate_limiter, cors_layer, timeout_layer, trace_layer};

// ---------------------------------------------------------------------------
// App State
// ---------------------------------------------------------------------------

#[derive(Clone)]
pub struct AppState {
    pub cfg: Arc<AppConfig>,
    pub llm: LlmClient,
    pub bot: Arc<BotLogic>,
    /// In-memory session store (produkciós verzióban Redis)
    pub sessions: Arc<RwLock<HashMap<Uuid, ChatSession>>>,
    pub rate_limiter: Arc<governor::DefaultKeyedRateLimiter<std::net::IpAddr>>,
}

// ---------------------------------------------------------------------------
// Router összeállítás
// ---------------------------------------------------------------------------

pub async fn build_router(cfg: Arc<AppConfig>) -> anyhow::Result<Router> {
    let llm = LlmClient::new(&cfg.llm_url);
    let bot = Arc::new(BotLogic::new(&cfg.bot_name));
    let rate_limiter = build_rate_limiter(cfg.rate_limit_per_second);

    let state = AppState {
        cfg: cfg.clone(),
        llm,
        bot,
        sessions: Arc::new(RwLock::new(HashMap::new())),
        rate_limiter,
    };

    // --- Session cleanup háttér task (30 perc TTL, 10 percenként fut) ---
    let sessions_for_cleanup = Arc::clone(&state.sessions);
    tokio::spawn(async move {
        let interval = std::time::Duration::from_secs(600);
        loop {
            tokio::time::sleep(interval).await;
            let cutoff = chrono::Utc::now() - chrono::Duration::seconds(1800);
            let mut sessions = sessions_for_cleanup.write().await;
            let before = sessions.len();
            sessions.retain(|_, s| s.last_active > cutoff);
            let removed = before - sessions.len();
            if removed > 0 {
                tracing::info!("Session cleanup: {removed} lejárt session törölve");
            }
        }
    });

    let app = Router::new()
        // --- Egészségellenőrzés ---
        .route("/health", get(handle_health))
        .route("/llm/health", get(handle_llm_health))
        // --- Chat REST API ---
        .route("/chat", post(handle_chat))
        // --- WebSocket chat ---
        .route("/ws/chat", get(handle_ws_upgrade))
        // --- Session kezelés ---
        .route("/session/new", post(handle_new_session))
        .route_layer(middleware::from_fn_with_state(state.clone(), rate_limit_middleware))
        .with_state(state)
        .layer(cors_layer(&cfg.cors_origins))
        .layer(timeout_layer())
        .layer(trace_layer());

    Ok(app)
}

// ---------------------------------------------------------------------------
// Rate limit middleware
// ---------------------------------------------------------------------------

async fn rate_limit_middleware(
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
    State(state): State<AppState>,
    request: Request<axum::body::Body>,
    next: Next,
) -> Response {
    if state.rate_limiter.check_key(&addr.ip()).is_err() {
        return AppError::RateLimited.into_response();
    }
    next.run(request).await
}

// ---------------------------------------------------------------------------
// Handler: /health
// ---------------------------------------------------------------------------

async fn handle_health(State(state): State<AppState>) -> impl IntoResponse {
    Json(json!({
        "status": "ok",
        "service": "clawdbot-rust-server",
        "bot_name": state.cfg.bot_name,
        "llm_url": state.cfg.llm_url,
    }))
}

// ---------------------------------------------------------------------------
// Handler: /llm/health – Python LLM szerver állapota
// ---------------------------------------------------------------------------

async fn handle_llm_health(State(state): State<AppState>) -> impl IntoResponse {
    match state.llm.health().await {
        Ok(h) => Json(json!({
            "status": h.status,
            "model": h.model,
            "model_loaded": h.model_loaded,
        }))
        .into_response(),
        Err(e) => {
            warn!("LLM health check sikertelen: {e}");
            (
                StatusCode::SERVICE_UNAVAILABLE,
                Json(json!({ "status": "error", "detail": e.to_string() })),
            )
                .into_response()
        }
    }
}

// ---------------------------------------------------------------------------
// Handler: POST /session/new
// ---------------------------------------------------------------------------

async fn handle_new_session(State(state): State<AppState>) -> impl IntoResponse {
    let session = ChatSession::new(10);
    let id = session.id;
    state.sessions.write().await.insert(id, session);
    info!("Új session létrehozva: {id}");
    Json(json!({ "session_id": id }))
}

// ---------------------------------------------------------------------------
// Handler: POST /chat
// ---------------------------------------------------------------------------

async fn handle_chat(
    State(state): State<AppState>,
    Json(req): Json<ChatRequest>,
) -> Result<Json<ChatResponse>, AppError> {
    if req.message.trim().is_empty() {
        return Err(AppError::BadRequest("Az üzenet nem lehet üres.".to_string()));
    }

    // Session keresése vagy új létrehozása
    let session_id = req.session_id.unwrap_or_else(Uuid::new_v4);
    {
        let mut sessions = state.sessions.write().await;
        sessions
            .entry(session_id)
            .or_insert_with(|| ChatSession::new(10));
    }

    // LLM kérés összeállítása
    let llm_req = {
        let sessions = state.sessions.read().await;
        let session = sessions.get(&session_id).unwrap();
        state
            .bot
            .build_llm_request(&req.message, session, req.max_tokens.unwrap_or(state.cfg.default_max_tokens))
    };

    debug!("LLM kérés küldése, session: {session_id}");
    let llm_resp = state.llm.generate(llm_req).await?;

    // Válasz feldolgozás
    let reply = state.bot.postprocess_response(&llm_resp.text);

    // Session frissítése
    {
        let mut sessions = state.sessions.write().await;
        if let Some(session) = sessions.get_mut(&session_id) {
            session.add_message(BotMessage::user(&req.message));
            session.add_message(BotMessage::assistant(&reply));
        }
    }

    info!(
        "Chat válasz: session={session_id}, {} token, {:.2}s",
        llm_resp.tokens_generated, llm_resp.elapsed_seconds
    );

    Ok(Json(ChatResponse {
        session_id,
        reply,
        tokens_generated: llm_resp.tokens_generated,
        elapsed_seconds: llm_resp.elapsed_seconds,
        model: llm_resp.model,
    }))
}

// ---------------------------------------------------------------------------
// Handler: GET /ws/chat – WebSocket upgrade
// ---------------------------------------------------------------------------

async fn handle_ws_upgrade(
    State(state): State<AppState>,
    ws: WebSocketUpgrade,
) -> Response {
    ws.on_upgrade(move |socket| handle_ws(socket, state))
}

async fn handle_ws(socket: WebSocket, state: AppState) {
    let (mut sender, mut receiver) = socket.split();
    let session_id = Uuid::new_v4();

    {
        let mut sessions = state.sessions.write().await;
        sessions.insert(session_id, ChatSession::new(10));
    }

    info!("WebSocket kapcsolat: session={session_id}");

    // Üdvözlő üzenet
    let welcome = json!({
        "type": "connected",
        "session_id": session_id,
        "bot": state.cfg.bot_name,
    });
    let _ = sender
        .send(WsMessage::Text(welcome.to_string()))
        .await;

    while let Some(msg) = receiver.next().await {
        let msg = match msg {
            Ok(m) => m,
            Err(e) => {
                warn!("WebSocket hiba: {e}");
                break;
            }
        };

        match msg {
            WsMessage::Text(text) => {
                let user_msg: Value = match serde_json::from_str(&text) {
                    Ok(v) => v,
                    Err(_) => {
                        // Sima szöveg → becsomagoljuk
                        json!({ "message": text })
                    }
                };

                let user_text = match user_msg.get("message").and_then(|v| v.as_str()) {
                    Some(t) => t.to_string(),
                    None => continue,
                };

                let max_tokens = user_msg
                    .get("max_tokens")
                    .and_then(|v| v.as_u64())
                    .unwrap_or(512) as u32;

                debug!("WS üzenet érkezett: session={session_id}");

                // LLM kérés összeállítása
                let llm_req = {
                    let sessions = state.sessions.read().await;
                    let session = sessions.get(&session_id).unwrap();
                    state
                        .bot
                        .build_streaming_request(&user_text, session, max_tokens)
                };

                // Streaming: mpsc channel a sync callback → async WS bridge-hez
                let mut full_reply = String::new();
                let (token_tx, mut token_rx) = mpsc::unbounded_channel::<String>();

                let llm_clone = state.llm.clone();
                let generate_task = tokio::spawn(async move {
                    llm_clone
                        .generate_streaming(llm_req, move |token| {
                            let _ = token_tx.send(token);
                        })
                        .await
                });

                // Tokenek forwarding-ja WebSocket-re amint megérkeznek
                while let Some(token) = token_rx.recv().await {
                    full_reply.push_str(&token);
                    let payload = json!({
                        "type": "token",
                        "data": token,
                        "session_id": session_id,
                    });
                    if sender
                        .send(WsMessage::Text(payload.to_string()))
                        .await
                        .is_err()
                    {
                        break;
                    }
                }

                let result = generate_task
                    .await
                    .unwrap_or_else(|e| Err(AppError::Internal(anyhow::anyhow!("Task join error: {e}"))));

                match result {
                    Ok(_) => {
                        let reply = state.bot.postprocess_response(&full_reply);

                        // Session frissítése
                        {
                            let mut sessions = state.sessions.write().await;
                            if let Some(s) = sessions.get_mut(&session_id) {
                                s.add_message(BotMessage::user(&user_text));
                                s.add_message(BotMessage::assistant(&reply));
                            }
                        }

                        let response = json!({
                            "type": "reply",
                            "session_id": session_id,
                            "data": reply,
                        });
                        let _ = sender
                            .send(WsMessage::Text(response.to_string()))
                            .await;
                    }
                    Err(e) => {
                        // Fallback: nem-streaming mód ha a streaming nem sikerült
                        warn!("Streaming hiba, fallback nem-streaming módra: {e}");
                        let fallback_req = {
                            let sessions = state.sessions.read().await;
                            let session = sessions.get(&session_id).unwrap();
                            state
                                .bot
                                .build_llm_request(&user_text, session, max_tokens)
                        };

                        match state.llm.generate(fallback_req).await {
                            Ok(llm_resp) => {
                                let reply = state.bot.postprocess_response(&llm_resp.text);
                                {
                                    let mut sessions = state.sessions.write().await;
                                    if let Some(s) = sessions.get_mut(&session_id) {
                                        s.add_message(BotMessage::user(&user_text));
                                        s.add_message(BotMessage::assistant(&reply));
                                    }
                                }
                                let response = json!({
                                    "type": "reply",
                                    "session_id": session_id,
                                    "data": reply,
                                });
                                let _ = sender
                                    .send(WsMessage::Text(response.to_string()))
                                    .await;
                            }
                            Err(fallback_err) => {
                                error!("WS LLM hiba (streaming + fallback): {fallback_err}");
                                let err_msg = json!({
                                    "type": "error",
                                    "message": fallback_err.to_string(),
                                });
                                let _ = sender
                                    .send(WsMessage::Text(err_msg.to_string()))
                                    .await;
                            }
                        }
                    }
                }
            }
            WsMessage::Close(_) => {
                info!("WebSocket lezárva: session={session_id}");
                break;
            }
            _ => {}
        }
    }

    // Session cleanup
    state.sessions.write().await.remove(&session_id);
    info!("Session eltávolítva: {session_id}");
}
