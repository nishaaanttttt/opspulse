"""Generate a reproducible fictional task export with controlled defects and KPI patterns."""
from pathlib import Path
import numpy as np
import pandas as pd

def generate(n=1200, seed=42):
    """Build 12 weeks of synthetic tasks with measured patterns and export defects."""
    rng=np.random.default_rng(seed); start=pd.Timestamp('2026-01-05'); period_end=start+pd.Timedelta(days=12*7-1)
    owners=['Priya S.','Marco L.','Amina K.','Theo R.','Jules M.','Sam N.']; teams=['Operations','Customer Success','Implementation']; clients=['Northstar Labs','Cedar & Finch','Blue Orbit','Juniper Works']; records=[]
    for i in range(n):
        week=int(rng.integers(0,12)); created=start+pd.Timedelta(days=week*7+int(rng.integers(0,7))); priority=str(rng.choice(['High','Medium','Low'],p=[.35,.45,.20]))
        done=bool(rng.random()<(.28 if week==7 else .68)); status=str(rng.choice(['Done','done','DONE','Completed'])) if done else str(rng.choice(['In progress','in-progress','WIP','Blocked','blocked','Not started']))
        due=created+pd.Timedelta(days=int(rng.integers(1,9)))
        if done:
            late=bool(rng.random()<(.35 if priority=='High' else .18)); offset=int(rng.integers(1,4)) if late else int(rng.integers(-2 if priority=='High' else -3,1)); completed=due+pd.Timedelta(days=offset)
            completed=min(completed,period_end)
        else:
            completed=pd.NaT; due=created+pd.Timedelta(days=int(rng.integers(1,7) if rng.random()<.06 else rng.integers(80,161)))
        owner=str(rng.choice(owners,p=[.42,.17,.14,.11,.09,.07])); owner=f'  {owner.lower()}  ' if rng.random()<.03 else owner; owner='' if rng.random()<.03 else owner
        hours=[]
        for _ in range(2):
            mark=rng.random()
            if mark<.03: hours.append(0.0)
            elif mark<.05: hours.append(-float(rng.integers(1,5)))
            elif mark<.07: hours.append(400.0)
            else: hours.append(float(rng.integers(2,25)))
        date_format=str(rng.choice(['%Y-%m-%d','%d/%m/%Y','%d %b %Y']))
        records.append({'Task ID':f'T-{i+1:04d}','Created Date':created.strftime(date_format),'Due Date':due.strftime('%Y-%m-%d'),'Completed Date':completed.strftime('%d/%m/%Y') if pd.notna(completed) else '', 'Owner':owner,'Team':str(rng.choice(teams)),'Priority':priority,'Status':status,'Client/Project':str(rng.choice(clients)),'Estimated Hours':hours[0],'Actual Hours':hours[1],'Rework':str(rng.choice(['Yes','No'],p=[.14,.86]))})
    for j in rng.choice(len(records),size=max(1,round(n*.02)),replace=False): records.append(records[int(j)].copy())
    frame=pd.DataFrame(records)
    for j in rng.choice(len(frame),size=max(1,round(n*.008)),replace=False): frame.at[j,'Created Date']='31/02/2026'
    open_ids=frame.index[~frame['Status'].str.lower().isin({'done','completed'})].to_numpy(); done_ids=frame.index[frame['Status'].str.lower().isin({'done','completed'})].to_numpy()
    for j in rng.choice(open_ids,size=max(1,round(n*.01)),replace=False): frame.at[j,'Completed Date']='2026-03-20'
    for j in rng.choice(done_ids,size=max(1,round(n*.01)),replace=False): frame.at[j,'Completed Date']=''
    for j in rng.choice(len(frame),size=max(1,round(n*.01)),replace=False):
        created_value=pd.to_datetime(frame.at[j,'Created Date'],errors='coerce',format='mixed',dayfirst=True)
        if pd.notna(created_value): frame.at[j,'Due Date']=(created_value-pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    return frame
if __name__=='__main__':
    out=Path(__file__).with_name('sample_tasks.csv'); generate().to_csv(out,index=False); print(f'Wrote {out}')
