FROM rust:1.76 as builder

WORKDIR /app
COPY R1/stack/serving/rust/Cargo.toml /app/Cargo.toml
RUN mkdir -p /app/src && echo "fn main() {}" > /app/src/main.rs
RUN cargo build --release

COPY R1/stack/serving/rust/src /app/src
RUN cargo build --release

FROM debian:bookworm-slim
WORKDIR /app
COPY --from=builder /app/target/release/r1-rust-infer /app/r1-rust-infer
COPY R1/stack/training/model.json /app/model.json
ENV MODEL_PATH=/app/model.json
EXPOSE 7071
CMD ["/app/r1-rust-infer"]
