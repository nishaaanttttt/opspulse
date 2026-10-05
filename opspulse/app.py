"""Streamlit interface for OpsPulse; calculations live in src modules."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import pandas as pd
import streamlit as st
import plotly.express as px
from src.cleaning import clean_tasks
from src.kpis import calculate_kpis
from src.summary import generate_summary
from src.report import create_pdf

st.set_page_config(page_title='OpsPulse',page_icon='📈',layout='wide')
st.markdown('<style>:root{--primary-color:#146C78} div[data-testid="stMetric"]{border-left:3px solid #146C78;padding-left:12px}</style>',unsafe_allow_html=True)
st.title('OpsPulse'); st.caption('A clear weekly view of delivery, workload and data quality.')

def uploaded_file_changed():
    st.session_state['data_source']='upload'

with st.sidebar:
    st.header('Task data')
    upload=st.file_uploader('Upload CSV or Excel',type=['csv','xlsx','xls'],key='task_upload',on_change=uploaded_file_changed)
    if st.button('Use sample data',type='primary'):
        st.session_state['data_source']='sample'
    st.caption('Expected task tracker columns are listed in the README.')

source_choice=st.session_state.get('data_source','sample')
try:
    if source_choice=='upload' and upload is not None:
        raw=pd.read_csv(upload) if upload.name.lower().endswith('.csv') else pd.read_excel(upload)
        source=upload.name
    else:
        raw=pd.read_csv(Path(__file__).parent/'data/sample_tasks.csv'); source='Synthetic sample data'
    cleaned,quality=clean_tasks(raw)
except (ValueError,pd.errors.EmptyDataError,pd.errors.ParserError,ImportError) as error:
    st.error(f"Could not load this file: {error}. Upload a non-empty CSV or Excel export with the required task columns."); st.stop()
except Exception as error:
    st.error(f"Could not read this file ({error}). Check that it is a valid CSV or Excel workbook."); st.stop()
st.caption(f'Source: {source} · {quality["rows_out"]:,} cleaned rows')
latest_done=cleaned.loc[cleaned['Status'].eq('Done'),'Completed Date'].dropna()
default_as_of=latest_done.max().date() if len(latest_done) else pd.Timestamp.today().date()
with st.sidebar:
    dates=cleaned['Created Date'].dropna()
    if len(dates): date_range=st.date_input('Created date range',value=(dates.min().date(),dates.max().date()))
    else: date_range=None
    report_as_of=st.date_input('Report as of',value=default_as_of)
    teams=sorted(cleaned['Team'].dropna().astype(str).unique()); selected_teams=st.multiselect('Team',teams,default=teams)
    owners=sorted(cleaned['Owner'].unique()); selected_owners=st.multiselect('Owner',owners,default=owners)
    priorities=sorted(cleaned['Priority'].unique(),key=lambda p:{'High':0,'Medium':1,'Low':2}.get(p,3)); selected_priorities=st.multiselect('Priority',priorities,default=priorities)
filtered=cleaned.copy()
if date_range and len(date_range)==2:
    filtered=filtered[filtered['Created Date'].between(pd.Timestamp(date_range[0]),pd.Timestamp(date_range[1]),inclusive='both')]
filtered=filtered[filtered['Team'].isin(selected_teams)&filtered['Owner'].isin(selected_owners)&filtered['Priority'].isin(selected_priorities)]
k=calculate_kpis(filtered,as_of_date=report_as_of); o=k['overall']; summary=generate_summary(k)
tabs=st.tabs(['Overview','Data Quality','Workload','Weekly Report'])
with tabs[0]:
    metrics=[('On-time',o['on_time_rate'],'on_time_rate','{:.0%}'),('Cycle time',o['average_cycle_days'],'average_cycle_days','{:.1f} d'),('Throughput',o['throughput'],'throughput','{:.0f}'),('Overdue backlog',o['overdue_backlog'],'overdue_backlog','{:.0f}')]
    cols=st.columns(4)
    for col,(label,value,key,fmt) in zip(cols,metrics):
        delta=k['wow'].get(key)
        if key in {'on_time_rate','rework_rate'}: delta_text=f'{delta*100:+.1f} pts' if pd.notna(delta) else None
        else: delta_text=f'{delta:+.1f}' if pd.notna(delta) else None
        col.metric(label,fmt.format(value) if pd.notna(value) else 'N/A',delta_text,delta_color='inverse' if key in {'average_cycle_days','overdue_backlog'} else 'normal')
    left,right=st.columns(2)
    if len(k['weekly']): left.plotly_chart(px.line(k['weekly'],x='Week',y='throughput',markers=True,title='Throughput by week',color_discrete_sequence=['#146C78']),width='stretch')
    else: left.info('No weekly throughput data in this selection.')
    if len(k['priority']): right.plotly_chart(px.bar(k['priority'],x='Priority',y='on_time_rate',title='On-time rate by priority',color_discrete_sequence=['#146C78']).update_yaxes(tickformat='.0%'),width='stretch')
    else: right.info('No tasks with usable priority deadline data.')
    st.subheader('Overdue backlog by owner'); overdue=k['overdue_by_owner'].rename('Overdue tasks').reset_index()
    if len(overdue): st.plotly_chart(px.bar(overdue,x='Owner',y='Overdue tasks',color_discrete_sequence=['#146C78']),width='stretch')
    else: st.info('No overdue tasks in this selection.')
with tabs[1]:
    st.subheader('Data quality report'); st.write(f"{quality['rows_in']:,} rows in · {quality['rows_out']:,} rows out · {quality['duplicates_removed']:,} exact duplicates removed · score {quality['data_quality_score']:.1f}%")
    st.write('**Change log**')
    for change in quality['change_log']: st.write('• '+change)
    st.dataframe(pd.DataFrame({'Issue':quality['issue_counts'].keys(),'Flagged rows':quality['issue_counts'].values()}),hide_index=True,width='stretch')
    st.download_button('Download cleaned CSV',cleaned.to_csv(index=False).encode(),file_name='opspulse_cleaned.csv',mime='text/csv')
with tabs[2]:
    st.subheader('Open workload by owner'); st.caption('Overloaded means more than 1.5× the average number of open tasks per owner.')
    def workload_row_style(row):
        styles=[]
        for _ in row: styles.append('background-color: #ffe8cc' if row['overloaded'] else '')
        return styles
    st.dataframe(k['workload'].style.apply(workload_row_style,axis=1),hide_index=True,width='stretch')
    if len(k['workload']): st.plotly_chart(px.bar(k['workload'],x='Owner',y='open_tasks',color='overloaded',color_discrete_map={True:'#D97706',False:'#146C78'},title='Open tasks by owner'),width='stretch')
with tabs[3]:
    st.subheader('Weekly report')
    for item in summary: st.markdown('• '+item)
    weekly_display=k['weekly'].copy()
    for rate_metric in ('on_time_rate','rework_rate'):
        wow_col=rate_metric+'_wow'
        if wow_col in weekly_display.columns:
            weekly_display[wow_col]=weekly_display[wow_col].map(lambda value:f'{value*100:+.1f} pts' if pd.notna(value) else 'N/A')
    st.dataframe(weekly_display,hide_index=True,width='stretch')
    # Streamlit invokes this callable only when the download control is clicked.
    st.download_button('Download one-page PDF',data=lambda:create_pdf(k,summary,quality),file_name='opspulse_weekly_report.pdf',mime='application/pdf',on_click='ignore',type='primary')
