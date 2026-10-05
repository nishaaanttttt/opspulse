"""Measure end-to-end pipeline runtime at sample and 10x scale."""
from pathlib import Path
import time
import tempfile
import pandas as pd
from src.cleaning import clean_tasks
from src.kpis import calculate_kpis
from src.summary import generate_summary
from src.report import create_pdf
from data.generate_sample import generate
ROOT=Path(__file__).parent

def pipeline(frame):
    cleaned,quality=clean_tasks(frame); kpis=calculate_kpis(cleaned); summary=generate_summary(kpis); pdf=create_pdf(kpis,summary,quality)
    return len(cleaned),len(pdf)
def run(label,path):
    start=time.perf_counter(); frame=pd.read_csv(path); rows,pdf_bytes=pipeline(frame); elapsed=time.perf_counter()-start
    print(f'{label}: {rows:,} rows, {pdf_bytes:,} PDF bytes, {elapsed:.3f} seconds')
if __name__=='__main__':
    run('Sample',ROOT/'data/sample_tasks.csv')
    with tempfile.TemporaryDirectory(prefix='opspulse-benchmark-') as directory:
        large_path=Path(directory)/'tasks_10x.csv'; generate(n=12000,seed=43).to_csv(large_path,index=False); run('10x synthetic',large_path)
