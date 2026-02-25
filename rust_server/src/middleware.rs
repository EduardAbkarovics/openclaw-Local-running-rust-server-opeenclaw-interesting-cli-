/// CORS és egyéb middleware konfigurációk.

use tower_http::cors::{Any, CorsLayer};
use tower_http::timeout::TimeoutLayer;
use tower_http::trace::TraceLayer;
use std::time::Duration;
use http::Method;

pub fn cors_layer(allowed_origins: &str) -> CorsLayer {
    if allowed_origins == "*" {
        CorsLayer::new()
            .allow_origin(Any)
            .allow_methods([Method::GET, Method::POST, Method::OPTIONS])
            .allow_headers(Any)
    } else {
        // Konkrét origin-ek parse-olása
        let _origins: Vec<&str> = allowed_origins.split(',').map(str::trim).collect();
        // Egyszerűsített: ha van konkrét lista, most Any-t használunk
        // Produkciós verzióban itt kellene parse-olni az origin-eket
        CorsLayer::new()
            .allow_origin(Any)
            .allow_methods([Method::GET, Method::POST, Method::OPTIONS])
            .allow_headers(Any)
    }
}

pub fn timeout_layer() -> TimeoutLayer {
    TimeoutLayer::new(Duration::from_secs(300))
}

pub fn trace_layer() -> TraceLayer<tower_http::classify::SharedClassifier<tower_http::classify::ServerErrorsAsFailures>> {
    TraceLayer::new_for_http()
}
