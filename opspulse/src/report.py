"""Create a compact one-page A4 weekly report, including safe empty-state charts."""
from io import BytesIO
from pathlib import Path
import os
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.units import mm
os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parent.parent / '.mpl-cache'))
import matplotlib.pyplot as plt
ACCENT=colors.HexColor('#146C78')
RATE_METRICS={'on_time_rate','rework_rate'}
def _format_change(value,key):
    if value is None or pd.isna(value): return 'N/A'
    return f'{value*100:+.1f} pts' if key in RATE_METRICS else f'{value:+.1f}'
def create_pdf(kpis, summary, quality):
    """Return PDF bytes; empty weekly/priority data render explanatory chart placeholders."""
    buf=BytesIO(); doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=13*mm,leftMargin=13*mm,topMargin=10*mm,bottomMargin=10*mm)
    styles=getSampleStyleSheet(); styles.add(ParagraphStyle(name='Small',parent=styles['BodyText'],fontSize=8,leading=10))
    w=kpis['weekly']; period=f"{w['Week'].min().date()} to {w['Week'].max().date()}" if len(w) else 'No completed weeks'
    report_as_of=kpis['overall'].get('as_of'); asof_text=f' · Report as of: {report_as_of.date()}' if report_as_of is not None and pd.notna(report_as_of) else ''
    story=[Paragraph('OpsPulse | Weekly Operations Report',styles['Title']),Paragraph('Reporting period: '+period+asof_text,styles['Normal']),Spacer(1,4*mm)]
    rows=[['KPI','Period value','WoW change']]
    for label,key,suffix in [('On-time completion','on_time_rate','%'),('Average cycle time','average_cycle_days',' days'),('Throughput','throughput',' tasks'),('Overdue backlog','overdue_backlog',' tasks'),('Overdue average age','overdue_average_age_days',' days'),('Rework rate','rework_rate','%'),('Estimate accuracy','estimate_accuracy','×')]:
        val=kpis['overall'].get(key); fmt=f'{val:.0%}' if suffix=='%' and val is not None and pd.notna(val) else (f'{val:.1f}{suffix}' if val is not None and pd.notna(val) else 'N/A'); rows.append([label,fmt,_format_change(kpis['wow'].get(key),key)])
    table=Table(rows,colWidths=[75*mm,48*mm,48*mm]); table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),ACCENT),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.3,colors.lightgrey),('FONTSIZE',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)])); story += [table,Spacer(1,3*mm)]
    def chart(kind):
        f,ax=plt.subplots(figsize=(4.1,1.55)); ax.spines[['top','right']].set_visible(False); ax.grid(axis='y',alpha=.18)
        if kind=='throughput':
            if len(w): ax.plot(w['Week'],w['throughput'],color='#146C78',marker='o'); ax.tick_params(axis='x',labelrotation=30,labelsize=6)
            else: ax.text(.5,.5,'No weekly completions available',ha='center',va='center',transform=ax.transAxes)
            ax.set_title('Weekly throughput',fontsize=9)
        else:
            q=kpis['priority']
            if len(q): ax.bar(q['Priority'],q['on_time_rate']*100,color='#146C78')
            else: ax.text(.5,.5,'No priority deadline data available',ha='center',va='center',transform=ax.transAxes)
            ax.set_ylim(0,100); ax.set_title('On-time completion by priority',fontsize=9); ax.set_ylabel('%',fontsize=7)
        f.tight_layout(); out=BytesIO(); f.savefig(out,format='png',dpi=110); plt.close(f); out.seek(0); return Image(out,width=83*mm,height=31*mm)
    charts=Table([[chart('throughput'),chart('priority')]],colWidths=[88*mm,88*mm]); charts.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)])); story += [charts,Paragraph('This week in plain English',styles['Heading2'])]
    for item in summary: story.append(Paragraph('• '+item,styles['Small']))
    story += [Spacer(1,2*mm),Paragraph(f"Data quality: {quality['rows_out']:,} rows cleaned; {sum(quality['issue_counts'].values()):,} issue flags recorded.",styles['Small'])]
    doc.build(story); return buf.getvalue()
