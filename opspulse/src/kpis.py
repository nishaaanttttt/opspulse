"""Operations KPI calculations with explicit report-date and weekly semantics."""
import pandas as pd


def _week_start(values):
    return pd.to_datetime(values).dt.to_period('W-SUN').dt.start_time


def calculate_kpis(df, as_of_date=None):
    """Return period KPIs, calendar-week series, workload, and priority performance.

    On-time = dated Done tasks completed on/before due / dated Done tasks with a due date.
    Cycle time = mean nonnegative created-to-completed days for dated Done tasks.
    Throughput counts dated Done tasks by completion week; period throughput is its weekly sum.
    Weekly backlog at week end counts tasks created by then, due before then, and not completed by then.
    Overall backlog/age use report_as_of; default is latest Completed Date among Done tasks.
    Rework = reworked dated Done / dated Done. Estimate accuracy = valid actual sum / valid estimate sum.
    Weeks ending after report_as_of are partial. Weeks below 20 completions are low sample.
    WoW compares the last two adjacent complete, non-low-sample weeks only.
    """
    d=df.copy()
    for col in ('Created Date','Due Date','Completed Date'):
        d[col]=pd.to_datetime(d[col],errors='coerce',format='mixed',dayfirst=True)
    done=d['Status'].eq('Done'); valid_done=done & d['Completed Date'].notna(); done_missing=done & d['Completed Date'].isna(); due_done=valid_done & d['Due Date'].notna()
    ontime=float((d.loc[due_done,'Completed Date']<=d.loc[due_done,'Due Date']).mean()) if due_done.any() else None
    cycle_mask=valid_done & d['Created Date'].notna()
    cyc=(d.loc[cycle_mask,'Completed Date']-d.loc[cycle_mask,'Created Date']).dt.total_seconds()/86400; cyc=cyc[cyc>=0]
    completed=int(valid_done.sum()); rework=float(d.loc[valid_done,'Rework'].astype(bool).mean()) if completed else None
    est=d['Estimated Hours']; act=d['Actual Hours']; good=est.notna() & act.notna() & est.gt(0) & act.ge(0)
    accuracy=float(act[good].sum()/est[good].sum()) if good.any() and est[good].sum() else None
    done_dates=d.loc[valid_done,'Completed Date']; latest_done=done_dates.max() if len(done_dates) else pd.NaT
    report_as_of=pd.Timestamp(as_of_date).normalize() if as_of_date is not None else latest_done
    if pd.notna(report_as_of): report_as_of=report_as_of.normalize()
    openmask=~valid_done
    if pd.notna(report_as_of):
        existed_by_asof=d['Created Date'].notna() & d['Created Date'].le(report_as_of)
        active_at_asof=d['Completed Date'].isna() | d['Completed Date'].gt(report_as_of)
        overdue=existed_by_asof & active_at_asof & d['Due Date'].notna() & d['Due Date'].lt(report_as_of)
    else:
        overdue=pd.Series(False,index=d.index)
    age=(report_as_of-d.loc[overdue,'Due Date']).dt.total_seconds()/86400 if overdue.any() else pd.Series(dtype=float)

    observed=pd.concat([d['Created Date'],done_dates]).dropna(); weekly_rows=[]
    if len(observed):
        first=_week_start(pd.Series([observed.min()])).iloc[0]; last=_week_start(pd.Series([observed.max()])).iloc[0]
        for week in pd.date_range(first,last,freq='7D'):
            week_end=week+pd.Timedelta(days=6)
            part=d.loc[valid_done & _week_start(d['Completed Date']).eq(week)]
            duepart=part[part['Due Date'].notna()]
            cycle=(part['Completed Date']-part['Created Date']).dt.total_seconds()/86400; cycle=cycle[cycle>=0]
            hourpart=part[part['Estimated Hours'].gt(0)&part['Actual Hours'].ge(0)]
            created_by_end=d['Created Date'].notna() & d['Created Date'].le(week_end)
            not_done_yet=d['Completed Date'].isna() | d['Completed Date'].gt(week_end)
            weekly_overdue=created_by_end & not_done_yet & d['Due Date'].notna() & d['Due Date'].lt(week_end)
            weekly_age=(week_end-d.loc[weekly_overdue,'Due Date']).dt.total_seconds()/86400 if weekly_overdue.any() else pd.Series(dtype=float)
            weekly_rows.append({'Week':week,'Week End':week_end,'on_time_rate':float((duepart['Completed Date']<=duepart['Due Date']).mean()) if len(duepart) else None,'average_cycle_days':float(cycle.mean()) if len(cycle) else None,'throughput':int(len(part)),'overdue_backlog':int(weekly_overdue.sum()),'overdue_average_age_days':float(weekly_age.mean()) if len(weekly_age) else None,'rework_rate':float(part['Rework'].astype(bool).mean()) if len(part) else None,'estimate_accuracy':float(hourpart['Actual Hours'].sum()/hourpart['Estimated Hours'].sum()) if len(hourpart) and hourpart['Estimated Hours'].sum() else None})
    weekly=pd.DataFrame(weekly_rows)
    metrics=['on_time_rate','average_cycle_days','throughput','overdue_backlog','overdue_average_age_days','rework_rate','estimate_accuracy']
    if len(weekly):
        weekly['complete_week']=weekly['Week End'].le(report_as_of) if pd.notna(report_as_of) else False
        weekly['low_sample']=weekly['throughput'].lt(20)
        for metric in metrics: weekly[metric+'_wow']=None
        eligible=weekly.index[weekly['complete_week'] & ~weekly['low_sample']].tolist()
        for prev,cur in zip(eligible,eligible[1:]):
            if weekly.loc[cur,'Week']-weekly.loc[prev,'Week']==pd.Timedelta(days=7):
                for metric in metrics:
                    a,b=weekly.loc[prev,metric],weekly.loc[cur,metric]
                    weekly.loc[cur,metric+'_wow']=float(b-a) if pd.notna(a) and pd.notna(b) else None
    open_df=d.loc[openmask].copy()
    workload=open_df.groupby('Owner',dropna=False).agg(open_tasks=('Task ID','count'),open_hours=('Estimated Hours',lambda x:float(x.clip(lower=0).sum()))).reset_index()
    avg=float(workload['open_tasks'].mean()) if len(workload) else 0.0
    workload['team_average_tasks']=avg; workload['load_ratio']=workload['open_tasks']/avg if avg else 0.0; workload['overloaded']=workload['load_ratio']>1.5
    priority_rows=[]
    for priority,group in d[due_done].groupby('Priority'):
        priority_rows.append({'Priority':priority,'on_time_rate':float((group['Completed Date']<=group['Due Date']).mean()),'completed':len(group)})
    priority=pd.DataFrame(priority_rows)
    if len(priority):
        order={'High':0,'Medium':1,'Low':2}; priority['_order']=priority['Priority'].map(order).fillna(3); priority=priority.sort_values('_order').drop(columns='_order').reset_index(drop=True)
    wow={metric:None for metric in metrics}; complete_indices=weekly.index[weekly['complete_week']].tolist() if len(weekly) else []
    if len(complete_indices)>=2:
        prev,cur=complete_indices[-2:]
        comparable=(not bool(weekly.loc[prev,'low_sample']) and not bool(weekly.loc[cur,'low_sample']) and weekly.loc[cur,'Week']-weekly.loc[prev,'Week']==pd.Timedelta(days=7))
        if comparable:
            for metric in metrics:
                a,b=weekly.loc[prev,metric],weekly.loc[cur,metric]; wow[metric]=float(b-a) if pd.notna(a) and pd.notna(b) else None
    overall={'on_time_rate':ontime,'average_cycle_days':float(cyc.mean()) if len(cyc) else None,'throughput':int(weekly['throughput'].sum()) if len(weekly) else 0,'overdue_backlog':int(overdue.sum()),'overdue_average_age_days':float(age.mean()) if len(age) else None,'rework_rate':rework,'estimate_accuracy':accuracy,'open_tasks':int(openmask.sum()),'as_of':report_as_of,'done_missing_completed_date':int(done_missing.sum())}
    overdue_by_owner=open_df.loc[overdue].groupby('Owner').size().sort_values(ascending=False) if overdue.any() else pd.Series(dtype='int64',name='count')
    return {'overall':overall,'weekly':weekly,'workload':workload,'priority':priority,'wow':wow,'overdue_by_owner':overdue_by_owner}
