/// CORS és egyéb middleware konfigurációk.

use governor::{DefaultKeyedRateLimiter, Quota, RateLimiter};
use http::{HeaderValue, Method};
use std::net::IpAddr;
use std::num::NonZeroU32;
use std::sync::Arc;
use std::time::Duration;
use tower_http::cors::{AllowOrigin, Any, CorsLayer};
use tower_http::timeout::TimeoutLayer;
use tower_http::trace::TraceLayer;

pub fn cors_layer(allowed_origins: &str) -> CorsLayer {
    if allowed_origins == "*" {
        CorsLayer::new()
            .allow_origin(Any)
            .allow_methods([Method::GET, Method::POST, Method::OPTIONS])
            .allow_headers(Any)
    } else {
        let origins: Vec<HeaderValue> = allowed_origins
            .split(',')
            .map(str::trim)
            .filter_map(|o| o.parse::<HeaderValue>().ok())
            .collect();

        let allow = if origins.is_empty() {
            AllowOrigin::any()
        } else {
            AllowOrigin::list(origins)
        };

        CorsLayer::new()
            .allow_origin(allow)
            .allow_methods([Method::GET, Method::POST, Method::OPTIONS])
            .allow_headers(Any)
    }
}

pub fn build_rate_limiter(per_second: u32) -> Arc<DefaultKeyedRateLimiter<IpAddr>> {
    let quota = Quota::per_second(NonZeroU32::new(per_second.max(1)).unwrap());
    Arc::new(RateLimiter::dashmap(quota))
}

pub fn timeout_layer() -> TimeoutLayer {
    TimeoutLayer::new(Duration::from_secs(300))
}

pub fn trace_layer() -> TraceLayer<tower_http::classify::SharedClassifier<tower_http::classify::ServerErrorsAsFailures>> {
    TraceLayer::new_for_http()
}
