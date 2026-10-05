"""Normalize task exports and report every detected quality issue."""
from __future__ import annotations
import pandas as pd

REQUIRED_COLUMNS = ['Task ID','Created Date','Due Date','Completed Date','Owner','Team','Priority','Status','Client/Project','Estimated Hours','Actual Hours','Rework']
DATE_COLUMNS = ['Created Date','Due Date','Completed Date']


def parse_date(value):
    """Parse common export date forms; return NaT for blanks or invalid dates."""
    if pd.isna(value) or str(value).strip() == '': return pd.NaT
    try:
        # Explicit formats avoid locale-dependent guessing, then pandas handles ISO variants.
        for fmt in ('%Y-%m-%d','%d/%m/%Y','%m/%d/%Y','%d %b %Y','%d %B %Y'):
            try: return pd.to_datetime(str(value).strip(), format=fmt, errors='raise')
            except (ValueError, TypeError): pass
        return pd.to_datetime(value, errors='coerce', format='mixed')
    except (ValueError, TypeError): return pd.NaT


def standardize_status(value):
    """Map common tracker status spellings to four canonical states."""
    s = str(value).strip().lower().replace('_',' ').replace('-',' ')
    if s in {'done','complete','completed','closed','resolved'}: return 'Done'
    if s in {'in progress','wip','working','started'}: return 'In Progress'
    if s in {'blocked','on hold','stuck'}: return 'Blocked'
    if s in {'not started','new','todo','to do','backlog','nan',''}: return 'Not Started'
    return 'Not Started'


def clean_tasks(frame: pd.DataFrame):
    """Return normalized rows and counts. Flags are row-level booleans; no issue row is discarded."""
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing: raise ValueError('Missing required columns: ' + ', '.join(missing))
    original = frame.copy(); rows_in = len(original)
    # Exact duplicate removal is the sole row-removal rule and is reported explicitly.
    dup = original.duplicated(keep='first'); data = original.loc[~dup].copy().reset_index(drop=True)
    for col in DATE_COLUMNS: data[col] = data[col].map(parse_date)
    for col in ('Estimated Hours','Actual Hours'): data[col] = pd.to_numeric(data[col], errors='coerce')
    data['Owner'] = data['Owner'].fillna('').astype(str).str.strip().str.title().replace('', 'Unassigned')
    data['Status'] = data['Status'].map(standardize_status)
    data['Priority'] = data['Priority'].fillna('Medium').astype(str).str.strip().str.title()
    data['Rework'] = data['Rework'].fillna('No').astype(str).str.strip().str.lower().isin({'yes','y','true','1'})
    flags = pd.DataFrame(index=data.index)
    for col in DATE_COLUMNS: flags['unparseable_'+col.lower().replace(' ','_')] = data[col].isna()
    # Blank dates are expected for open tasks and are not called unparseable.
    for col in DATE_COLUMNS:
        flags['unparseable_'+col.lower().replace(' ','_')] &= original.loc[~dup,col].reset_index(drop=True).notna() & original.loc[~dup,col].reset_index(drop=True).astype(str).str.strip().ne('')
    flags['negative_hours'] = data[['Estimated Hours','Actual Hours']].lt(0).any(axis=1)
    # A median/MAD rule stays robust when rare extreme values occur in the upper tail.
    valid_hours = data[['Estimated Hours','Actual Hours']].stack().dropna().clip(lower=0)
    median = float(valid_hours.median()) if len(valid_hours) else 0.0
    mad = float((valid_hours - median).abs().median()) if len(valid_hours) else 0.0
    cutoff = max(100.0, median + 3 * 1.4826 * mad)
    flags['outlier_hours'] = data[['Estimated Hours','Actual Hours']].gt(cutoff).any(axis=1)
    flags['missing_hours'] = data[['Estimated Hours','Actual Hours']].isna().any(axis=1)
    flags['due_before_created'] = data['Due Date'].notna() & data['Created Date'].notna() & (data['Due Date'] < data['Created Date'])
    flags['completed_date_status_mismatch'] = ((data['Status'].eq('Done') & data['Completed Date'].isna()) | (data['Status'].ne('Done') & data['Completed Date'].notna()))
    flags['done_missing_completed_date'] = data['Status'].eq('Done') & data['Completed Date'].isna()
    for col in flags: data['Issue: '+col.replace('_',' ')] = flags[col]
    row_issues = flags.any(axis=1)
    quality = {'rows_in':rows_in,'rows_out':len(data),'duplicates_removed':int(dup.sum()),'issue_counts':{c:int(flags[c].sum()) for c in flags.columns},'rows_with_issues':int(row_issues.sum()),'data_quality_score':round(100*(1-row_issues.mean()),1) if len(data) else 100.0,'outlier_threshold_hours':round(cutoff,1)}
    quality['change_log'] = [f"Removed {int(dup.sum())} exact duplicate row(s).",'Parsed dates and standardized owner, status, priority, hours, and rework values.',f"Flagged {int(row_issues.sum())} row(s) with one or more data quality issues; all retained."]
    return data, quality
