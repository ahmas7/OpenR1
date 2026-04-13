import argparse
import json
import os
from pathlib import Path


def _spark_available():
    try:
        import pyspark  # noqa: F401
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="R1 Spark data processing job.")
    parser.add_argument("--input", type=str, default="", help="CSV input path (optional).")
    parser.add_argument("--output", type=str, default="R1/stack/data/processed", help="Output directory.")
    parser.add_argument("--rows", type=int, default=5000, help="Rows to synthesize if no input.")
    args = parser.parse_args()

    if not _spark_available():
        raise SystemExit("pyspark is not installed. Install pyspark to run this job.")

    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F

    spark = SparkSession.builder.appName("r1-data-processing").getOrCreate()

    if args.input:
        df = spark.read.option("header", True).csv(args.input, inferSchema=True)
    else:
        df = spark.range(0, args.rows).withColumn("x1", F.rand()).withColumn("x2", F.rand())
        df = df.withColumn("y", (F.col("x1") * 2.5) + (F.col("x2") * -1.2) + F.lit(0.4))

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = str(out_dir / "dataset.parquet")
    df.write.mode("overwrite").parquet(parquet_path)

    meta = {"rows": df.count(), "columns": df.columns, "parquet": parquet_path}
    (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
    spark.stop()
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
