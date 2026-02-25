mod config;
mod error;
mod llm_client;
mod routes;
mod bot_logic;
mod middleware;

use std::net::SocketAddr;
use std::sync::Arc;
use tokio::net::TcpListener;
use tracing::info;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use crate::config::AppConfig;
use crate::routes::build_router;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Logging inicializálás
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "clawdbot_server=debug,tower_http=debug".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    // Konfiguráció betöltése (.env + config.toml)
    let cfg = AppConfig::load()?;
    let cfg = Arc::new(cfg);

    info!("ClawDBot Rust szerver indul...");
    info!("  Python LLM URL: {}", cfg.llm_url);
    info!("  Szerver cím:    {}:{}", cfg.host, cfg.port);

    let app = build_router(cfg.clone()).await?;

    let addr: SocketAddr = format!("{}:{}", cfg.host, cfg.port).parse()?;
    let listener = TcpListener::bind(addr).await?;

    info!("Rust szerver hallgat: http://{}", addr);
    axum::serve(listener, app).await?;

    Ok(())
}
