"""Deterministic plain-English observations derived from KPI values."""
import pandas as pd

def generate_summary(kpis):
    """Create 4-6 bullets; incomplete or low-sample weeks never headline a change."""
    o=kpis['overall']; weekly=kpis['weekly']; items=[]
    complete=weekly[weekly['complete_week']] if len(weekly) and 'complete_week' in weekly else weekly.iloc[0:0]
    if len(complete)>=2:
        prev,cur=complete.iloc[-2],complete.iloc[-1]
        if bool(prev['low_sample']) or bool(cur['low_sample']) or pd.isna(prev['on_time_rate']) or pd.isna(cur['on_time_rate']):
            items.append('On-time completion: not enough data from complete weeks for a reliable comparison.')
        else:
            delta=float(cur['on_time_rate']-prev['on_time_rate'])
            if abs(delta)>=.05: items.append(f"On-time completion {'rose' if delta>0 else 'fell'} from {cur['on_time_rate']-delta:.0%} to {cur['on_time_rate']:.0%} ({delta*100:+.0f} pts).")
            else: items.append('On-time completion showed no significant change between complete weeks.')
    else: items.append('On-time completion: not enough data from two complete weeks.')
    wl=kpis['workload']
    if len(wl) and wl['overloaded'].fillna(False).any():
        top=wl.loc[wl['overloaded'].fillna(False)].sort_values('load_ratio',ascending=False).iloc[0]
        items.append(f"{top['Owner']} holds {int(top['open_tasks'])} open tasks, {top['load_ratio']:.1f}× the team average.")
    else: items.append('No owner is above 1.5× the team average open task load.')
    n=o['overdue_backlog']; avg_age=o.get('overdue_average_age_days')
    if n and pd.notna(avg_age): items.append(f"{n} open task(s) are overdue; the average is {avg_age:.0f} days late.")
    else: items.append('There are no overdue open tasks.')
    if len(complete)>=2 and not bool(complete.iloc[-2]['low_sample']) and not bool(complete.iloc[-1]['low_sample']):
        items.append(f"Weekly throughput changed by {int(complete.iloc[-1]['throughput']-complete.iloc[-2]['throughput']):+d} task(s), from {int(complete.iloc[-2]['throughput'])} to {int(complete.iloc[-1]['throughput'])}.")
    else: items.append('Throughput: not enough data from two complete, non-low-sample weeks for a comparison.')
    accuracy=o.get('estimate_accuracy')
    if pd.notna(accuracy): items.append(f"Actual hours were {accuracy:.2f}× estimated hours across tasks with valid positive estimates.")
    else: items.append('Estimate accuracy: not enough data with valid positive estimates.')
    return items
