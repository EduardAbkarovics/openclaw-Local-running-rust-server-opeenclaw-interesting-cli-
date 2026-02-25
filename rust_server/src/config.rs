use anyhow::Result;
use serde::Deserialize;

#[derive(Debug, Deserialize, Clone)]
pub struct AppConfig {
    /// Rust szerver host
    #[serde(default = "default_host")]
    pub host: String,

    /// Rust szerver port
    #[serde(default = "default_port")]
    pub port: u16,

    /// Python LLM szerver alap URL
    #[serde(default = "default_llm_url")]
    pub llm_url: String,

    /// Alapértelmezett max token limit
    #[serde(default = "default_max_tokens")]
    pub default_max_tokens: u32,

    /// Bot neve
    #[serde(default = "default_bot_name")]
    pub bot_name: String,

    /// CORS engedélyezett origin-ek (vesszővel elválasztva)
    #[serde(default = "default_cors_origins")]
    pub cors_origins: String,

    /// Rate limit: kérés / másodperc / IP
    #[serde(default = "default_rate_limit")]
    #[allow(dead_code)]  // jövőbeli rate limiting implementációhoz
    pub rate_limit_per_second: u32,
}

fn default_host() -> String { "0.0.0.0".to_string() }
fn default_port() -> u16 { 3000 }
fn default_llm_url() -> String { "http://127.0.0.1:8000".to_string() }
fn default_max_tokens() -> u32 { 512 }
fn default_bot_name() -> String { "ClawDBot".to_string() }
fn default_cors_origins() -> String { "*".to_string() }
fn default_rate_limit() -> u32 { 5 }

impl AppConfig {
    pub fn load() -> Result<Self> {
        // .env fájl betöltése (ha létezik)
        let _ = dotenvy::dotenv();

        let cfg = config::Config::builder()
            // 1. Alapértelmezett értékek
            .set_default("host", default_host())?
            .set_default("port", default_port() as i64)?
            .set_default("llm_url", default_llm_url())?
            .set_default("default_max_tokens", default_max_tokens() as i64)?
            .set_default("bot_name", default_bot_name())?
            .set_default("cors_origins", default_cors_origins())?
            .set_default("rate_limit_per_second", default_rate_limit() as i64)?
            // 2. config.toml (opcionális)
            .add_source(
                config::File::with_name("config")
                    .required(false)
                    .format(config::FileFormat::Toml),
            )
            // 3. Környezeti változók (CLAWDBOT_ prefix)
            .add_source(
                config::Environment::with_prefix("CLAWDBOT")
                    .separator("_"),
            )
            .build()?;

        Ok(cfg.try_deserialize()?)
    }
}
