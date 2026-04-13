import argparse
import json
from pathlib import Path


def _jax_available():
    try:
        import jax  # noqa: F401
        import jax.numpy  # noqa: F401
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="R1 JAX training job.")
    parser.add_argument("--output", type=str, default="R1/stack/training/model_jax.json")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--lr", type=float, default=0.05)
    parser.add_argument("--rows", type=int, default=2000)
    args = parser.parse_args()

    if not _jax_available():
        raise SystemExit("jax is not installed. Install jax to run this training job.")

    import jax
    import jax.numpy as jnp

    key = jax.random.PRNGKey(0)
    x = jax.random.uniform(key, shape=(args.rows, 2))
    y = (x[:, 0] * 2.5) + (x[:, 1] * -1.2) + 0.4

    w = jnp.zeros((2,))
    b = jnp.array(0.0)

    def loss_fn(params, inputs, targets):
        w, b = params
        pred = jnp.dot(inputs, w) + b
        return jnp.mean((pred - targets) ** 2)

    grad_fn = jax.grad(loss_fn)

    for _ in range(args.epochs):
        grads = grad_fn((w, b), x, y)
        w = w - args.lr * grads[0]
        b = b - args.lr * grads[1]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"weights": [float(w[0]), float(w[1])], "bias": float(b)}, indent=2))
    print(json.dumps({"output": str(out_path), "weights": [float(w[0]), float(w[1])], "bias": float(b)}))


if __name__ == "__main__":
    main()
