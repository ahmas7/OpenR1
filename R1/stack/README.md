# R1 AI Stack (Real Components)

This stack connects Spark data processing, PyTorch/JAX training, Rust inference, and the R1 FastAPI layer.

## Local Setup

Install Python dependencies (in your venv):

```powershell
.\.venv\Scripts\python.exe -m pip install torch jax[cpu] pyspark
```

Run Spark data processing:

```powershell
.\.venv\Scripts\python.exe R1\stack\data\spark_job.py
```

Train a model with PyTorch:

```powershell
.\.venv\Scripts\python.exe R1\stack\training\train_pytorch.py
```

Or train with JAX:

```powershell
.\.venv\Scripts\python.exe R1\stack\training\train_jax.py
```

Start the Rust inference service:

```powershell
cd R1\stack\serving\rust
cargo run --release
```

Start the R1 API (enable stack endpoints):

```powershell
$env:R1_STACK_ALLOW_RUN="true"
$env:R1_RUST_INFER_URL="http://localhost:7071"
.\.venv\Scripts\python.exe run_r1.py
```

Call stack endpoints:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/ai/stack/train -ContentType "application/json" -Body '{"engine":"pytorch","run_data_job":true}'
Invoke-RestMethod -Method Post -Uri http://localhost:8000/ai/stack/infer -ContentType "application/json" -Body '{"features":[1.2,0.7]}'
```

## Kubernetes

Build container images:

```powershell
docker build -f R1\stack\serving\api\Dockerfile -t r1-api:local .
docker build -f R1\stack\serving\rust\Dockerfile -t r1-rust-infer:local .
```

Deploy:

```powershell
kubectl apply -f R1\stack\k8s\r1-rust-infer.yaml
kubectl apply -f R1\stack\k8s\r1-api.yaml
kubectl apply -f R1\stack\k8s\spark-job.yaml
```
