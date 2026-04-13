use axum::{
    extract::State,
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::{env, net::SocketAddr, sync::Arc};

#[derive(Clone, Debug, Serialize, Deserialize)]
struct ModelWeights {
    weights: Vec<f64>,
    bias: f64,
}

#[derive(Clone)]
struct AppState {
    weights: Arc<ModelWeights>,
}

#[derive(Debug, Deserialize)]
struct InferRequest {
    features: Vec<f64>,
}

#[derive(Debug, Serialize)]
struct InferResponse {
    prediction: f64,
}

async fn health() -> impl IntoResponse {
    Json(serde_json::json!({ "status": "ok" }))
}

async fn infer(State(state): State<AppState>, Json(payload): Json<InferRequest>) -> impl IntoResponse {
    if payload.features.len() != state.weights.weights.len() {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({ "error": "feature length mismatch" })),
        )
            .into_response();
    }
    let mut sum = state.weights.bias;
    for (x, w) in payload.features.iter().zip(state.weights.weights.iter()) {
        sum += x * w;
    }
    Json(InferResponse { prediction: sum }).into_response()
}

fn load_weights(path: &str) -> Result<ModelWeights, String> {
    let data = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&data).map_err(|e| e.to_string())
}

#[tokio::main]
async fn main() {
    let model_path = env::var("MODEL_PATH").unwrap_or_else(|_| "R1/stack/training/model.json".to_string());
    let weights = load_weights(&model_path).unwrap_or_else(|err| {
        eprintln!("Failed to load model weights: {}", err);
        std::process::exit(1);
    });
    let state = AppState {
        weights: Arc::new(weights),
    };

    let app = Router::new()
        .route("/health", get(health))
        .route("/infer", post(infer))
        .with_state(state);

    let addr = SocketAddr::from(([0, 0, 0, 0], 7071));
    println!("r1-rust-infer listening on {}", addr);
    axum::serve(tokio::net::TcpListener::bind(addr).await.unwrap(), app)
        .await
        .unwrap();
}
