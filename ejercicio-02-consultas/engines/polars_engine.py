import polars as pl

def q1(path):
    return (
        pl.scan_parquet(path)
        .group_by("country_code")
        .len("count")
        .sort("count", descending=True)
        .collect()
        .to_pandas()
    )

def q2(path):
    return (
        pl.scan_parquet(path)
        .group_by("category")
        .agg([
            pl.col("amount").mean().alias("mean"),
            pl.col("amount").min().alias("min"),
            pl.col("amount").max().alias("max")
        ])
        .collect()
        .to_pandas()
    )

def q3(path):
    return (
        pl.scan_parquet(path)
        .group_by("user_id")
        .agg([
            pl.col("amount").sum().alias("sum"),
            pl.col("amount").count().alias("count")
        ])
        .sort("sum", descending=True)
        .head(10)
        .collect()
        .to_pandas()
    )

def q4(path):
    return (
        pl.scan_parquet(path)
        .filter(pl.col("status") == "failed")
        .with_columns(pl.col("timestamp").dt.hour().alias("hour"))
        .group_by("hour")
        .len("count")
        .sort("hour")
        .collect()
        .to_pandas()
    )

def q5(path):
    # Polars doesn't have a simple .max() on lazy without a hack or collecting part, 
    # but we can do it in the pipeline
    df = pl.scan_parquet(path)
    max_date = df.select(pl.col("timestamp").max()).collect().item()
    min_date = max_date - pl.duration(days=30)
    
    return (
        df.filter(
            (pl.col("amount") > 500) &
            (pl.col("country_code").is_in(["MX", "CO"])) &
            (pl.col("timestamp") >= min_date)
        )
        .collect()
        .to_pandas()
    )

def q6(path):
    # This is more complex in Polars but very efficient
    df = pl.scan_parquet(path)
    
    # Group by both and count/mean
    stats = (
        df.group_by(["country_code", "category"])
        .agg([
            pl.len().alias("count"),
            pl.col("amount").mean().alias("avg_amount")
        ])
    )
    
    # Get max count per country
    return (
        stats.filter(
            pl.col("count") == pl.col("count").max().over("country_code")
        )
        .collect()
        .to_pandas()
    )

def q7(path):
    return (
        pl.scan_parquet(path)
        .filter(pl.col("status") == "failed")
        .group_by("user_id")
        .len("failed_count")
        .filter(pl.col("failed_count") > 5)
        .collect()
        .to_pandas()
    )

def q8(path):
    return (
        pl.scan_parquet(path)
        .with_columns(pl.col("timestamp").dt.date().alias("date"))
        .group_by(["date", "category"])
        .agg(pl.col("amount").mean().alias("avg_amount"))
        .collect()
        .to_pandas()
    )
