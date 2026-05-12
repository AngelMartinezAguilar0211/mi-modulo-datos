import pandas as pd

def q1(path):
    df = pd.read_parquet(path)
    return df.groupby('country_code').size().reset_index(name='count').sort_values('count', ascending=False)

def q2(path):
    df = pd.read_parquet(path)
    return df.groupby('category')['amount'].agg(['mean', 'min', 'max']).reset_index()

def q3(path):
    df = pd.read_parquet(path)
    return df.groupby('user_id')['amount'].agg(['sum', 'count']).sort_values('sum', ascending=False).head(10).reset_index()

def q4(path):
    df = pd.read_parquet(path)
    df['hour'] = df['timestamp'].dt.hour
    return df[df['status'] == 'failed'].groupby('hour').size().reset_index(name='count')

def q5(path):
    df = pd.read_parquet(path)
    max_date = df['timestamp'].max()
    min_date = max_date - pd.Timedelta(days=30)
    return df[
        (df['amount'] > 500) & 
        (df['country_code'].isin(['MX', 'CO'])) & 
        (df['timestamp'] >= min_date)
    ]

def q6(path):
    df = pd.read_parquet(path)
    # Count transactions per country and category
    counts = df.groupby(['country_code', 'category']).size().reset_index(name='count')
    # Get category with max count per country
    idx = counts.groupby('country_code')['count'].idxmax()
    top_categories = counts.loc[idx]
    
    # Get average amount for those country-category pairs
    avgs = df.groupby(['country_code', 'category'])['amount'].mean().reset_index(name='avg_amount')
    
    result = pd.merge(top_categories, avgs, on=['country_code', 'category'])
    return result[['country_code', 'category', 'count', 'avg_amount']]

def q7(path):
    df = pd.read_parquet(path)
    failed = df[df['status'] == 'failed']
    counts = failed.groupby('user_id').size().reset_index(name='failed_count')
    return counts[counts['failed_count'] > 5]

def q8(path):
    df = pd.read_parquet(path)
    df['date'] = df['timestamp'].dt.date
    return df.groupby(['date', 'category'])['amount'].mean().reset_index(name='avg_amount')
