import argparse
import json
from pathlib import Path


def _torch_available():
    try:
        import torch  # noqa: F401
        return True
    except Exception:
        return False


def _load_from_parquet(parquet_path):
    try:
        from pyspark.sql import SparkSession
    except Exception:
        return None

    spark = SparkSession.builder.appName("r1-train-loader").getOrCreate()
    df = spark.read.parquet(parquet_path).select("x1", "x2", "y")
    rows = df.collect()
    spark.stop()
    if not rows:
        return None
    x = [[float(r["x1"]), float(r["x2"])] for r in rows]
    y = [float(r["y"]) for r in rows]
    return x, y


def main():
    parser = argparse.ArgumentParser(description="R1 PyTorch training job.")
    parser.add_argument("--data", type=str, default="R1/stack/data/processed/dataset.parquet")
    parser.add_argument("--output", type=str, default="R1/stack/training/model.json")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--lr", type=float, default=0.05)
    parser.add_argument("--rows", type=int, default=2000)
    args = parser.parse_args()

    if not _torch_available():
        raise SystemExit("torch is not installed. Install torch to run this training job.")

    import torch

    x = None
    y = None
    data_path = Path(args.data)
    if data_path.exists():
        loaded = _load_from_parquet(str(data_path))
        if loaded:
            x, y = loaded

    if x is None:
        torch.manual_seed(0)
        x = torch.rand(args.rows, 2)
        y = (x[:, 0] * 2.5) + (x[:, 1] * -1.2) + 0.4
    else:
        x = torch.tensor(x, dtype=torch.float32)
        y = torch.tensor(y, dtype=torch.float32)

    model = torch.nn.Linear(2, 1)
    optim = torch.optim.SGD(model.parameters(), lr=args.lr)
    loss_fn = torch.nn.MSELoss()

    for _ in range(args.epochs):
        optim.zero_grad()
        pred = model(x).squeeze(-1)
        loss = loss_fn(pred, y)
        loss.backward()
        optim.step()

    weights = model.weight.detach().cpu().numpy().reshape(-1).tolist()
    bias = float(model.bias.detach().cpu().numpy().reshape(-1)[0])

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"weights": weights, "bias": bias}, indent=2))
    print(json.dumps({"output": str(out_path), "weights": weights, "bias": bias}))


if __name__ == "__main__":
    main()
