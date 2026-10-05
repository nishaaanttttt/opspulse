import io
import pandas as pd
import pytest
from src.cleaning import clean_tasks, REQUIRED_COLUMNS, parse_date, standardize_status
from src.kpis import calculate_kpis
from src.summary import generate_summary
from src.report import create_pdf

def frame(rows): return pd.DataFrame(rows,columns=REQUIRED_COLUMNS)
def row(id,created='2026-01-01',due='2026-01-03',completed='2026-01-02',owner='A',status='Done',est=2,act=2,rework='No',priority='High'):
    return [id,created,due,completed,owner,'Ops',priority,status,'Fictional',est,act,rework]

def test_date_parse_variants_and_invalid():
    assert parse_date('4 Mar 2026')==pd.Timestamp('2026-03-04')
    assert parse_date('04/03/2026')==pd.Timestamp('2026-03-04')
    assert pd.isna(parse_date('31/02/2026'))

def test_status_mapping():
    assert [standardize_status(x) for x in ['DONE','in-progress','WIP','blocked','??']]==['Done','In Progress','In Progress','Blocked','Not Started']

def test_duplicates_and_flags():
    d,q=clean_tasks(frame([row('1'),row('1'),row('2',created='oops',completed='')]))
    assert len(d)==2 and q['duplicates_removed']==1 and q['issue_counts']['unparseable_created_date']==1
    assert d.loc[0,'Status']=='Done'

def test_kpi_formulas_and_zero_denominators():
    d,_=clean_tasks(frame([row('1'),row('2',completed='2026-01-05',rework='Yes'),row('3',created='2026-01-01',due='2026-01-02',completed='',status='WIP',est=4,act=3)]))
    k=calculate_kpis(d); o=k['overall']
    assert o['on_time_rate']==.5 and o['average_cycle_days']==2.5 and o['throughput']==2
    assert o['rework_rate']==.5 and o['estimate_accuracy']==pytest.approx(7/8)
    assert o['overdue_backlog']==1 and o['overdue_average_age_days']>0
    assert k['workload']['open_tasks'].sum()==1 and k['priority'].iloc[0]['on_time_rate']==.5
    empty,_=clean_tasks(frame([row('4',completed='',status='WIP',est=0,act=0)])); no=calculate_kpis(empty)['overall']
    assert no['on_time_rate'] is None and no['rework_rate'] is None and no['estimate_accuracy'] is None

def test_weekly_backlog_hand_calculated():
    d,_=clean_tasks(frame([
        row('A',created='2026-01-05',due='2026-01-08',completed='2026-01-15'),
        row('B',created='2026-01-05',due='2026-01-09',completed='2026-01-10'),
        row('C',created='2026-01-12',due='2026-01-14',completed='2026-01-25'),
        row('D',created='2026-01-08',due='2026-01-09',completed='',status='Blocked')]))
    w=calculate_kpis(d,as_of_date='2026-02-01')['weekly'].set_index('Week')
    assert w.loc[pd.Timestamp('2026-01-05'),'overdue_backlog']==2
    assert w.loc[pd.Timestamp('2026-01-12'),'overdue_backlog']==2
    assert w.loc[pd.Timestamp('2026-01-05'),'overdue_average_age_days']==pytest.approx(2.5)
    assert w.loc[pd.Timestamp('2026-01-12'),'overdue_average_age_days']==pytest.approx(6.5)

def test_wow_uses_last_two_complete_weeks_and_marks_partial():
    rows=[]
    for week,count,on_time_share in [(0,25,.8),(1,30,.7),(2,7,.0)]:
        for i in range(count):
            start=pd.Timestamp('2026-01-05')+pd.Timedelta(days=week*7)
            completed=start+pd.Timedelta(days=2); due=completed+pd.Timedelta(days=1 if i<round(count*on_time_share) else -1)
            rows.append(row(f'{week}-{i}',created=start.strftime('%Y-%m-%d'),due=due.strftime('%Y-%m-%d'),completed=completed.strftime('%Y-%m-%d')))
    d,_=clean_tasks(frame(rows)); k=calculate_kpis(d,as_of_date='2026-01-22'); w=k['weekly']
    assert w.iloc[-1]['complete_week'] == False and w.iloc[-1]['low_sample']
    assert k['wow']['on_time_rate']==pytest.approx(-.1)

def test_throughput_consistency_and_done_missing_date_flag():
    d,q=clean_tasks(frame([row('ok'),row('missing',completed='')]))
    k=calculate_kpis(d)
    assert q['issue_counts']['done_missing_completed_date']==1
    assert k['overall']['done_missing_completed_date']==1
    assert k['overall']['throughput']==k['weekly']['throughput'].sum()==1

def test_summary_nan_handling_and_low_sample():
    k={'overall':{'overdue_backlog':0,'overdue_average_age_days':float('nan'),'estimate_accuracy':float('nan')},
       'weekly':pd.DataFrame([{'complete_week':True,'low_sample':False,'on_time_rate':float('nan'),'throughput':24},{'complete_week':True,'low_sample':True,'on_time_rate':.5,'throughput':3}]),
       'workload':pd.DataFrame(columns=['overloaded','load_ratio','open_tasks','Owner'])}
    result=generate_summary(k)
    assert result[0]=='On-time completion: not enough data from complete weeks for a reliable comparison.'
    assert result[2]=='There are no overdue open tasks.'
    assert result[-1]=='Estimate accuracy: not enough data with valid positive estimates.'
    assert 'fell' not in ' '.join(result) and 'rose' not in ' '.join(result)

def test_summary_exact_small_fixture():
    k={'overall':{'overdue_backlog':0,'overdue_average_age_days':None,'estimate_accuracy':1.25},
       'weekly':pd.DataFrame([{'complete_week':True,'low_sample':False,'on_time_rate':.8,'throughput':21},{'complete_week':True,'low_sample':False,'on_time_rate':.7,'throughput':22}]),
       'workload':pd.DataFrame([{'Owner':'Alex','open_tasks':4,'load_ratio':2.0,'overloaded':True}])}
    assert generate_summary(k)==[
        'On-time completion fell from 80% to 70% (-10 pts).',
        'Alex holds 4 open tasks, 2.0× the team average.',
        'There are no overdue open tasks.',
        'Weekly throughput changed by +1 task(s), from 21 to 22.',
        'Actual hours were 1.25× estimated hours across tasks with valid positive estimates.'
    ]

def test_empty_filter_pdf_generation():
    empty,_=clean_tasks(frame([])); k=calculate_kpis(empty); result=create_pdf(k,generate_summary(k),{'rows_out':0,'issue_counts':{}})
    assert result.startswith(b'%PDF') and len(result)>1000
