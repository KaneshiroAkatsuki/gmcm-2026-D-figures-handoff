"""Physical reconstruction from raw tables/DEM and fixed control decisions."""
import sys
sys.dont_write_bytecode=True
for _stream in (sys.stdout,sys.stderr):
    if hasattr(_stream,'reconfigure'):_stream.reconfigure(encoding='utf-8')
import copy,json,math
from pathlib import Path
from decimal import localcontext
from dcore import Model,MODEL,absolute,metrics
from communication import relay_task
from bounded_certificates import Links,point_on
from nominal_states_v003_1 import build
from q3_engine import check_resources

ROOT=Path(__file__).resolve().parents[1]

def local_output(path):
    p=Path(path).resolve()
    if not any(p.is_relative_to(ROOT/'output'/name) for name in ('replay','reproduced')):raise ValueError('Output must be inside output/replay or output/reproduced')
    p.parent.mkdir(parents=True,exist_ok=True)
    return p

def save(path,value):
    local_output(path).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def extract_decisions(plan,nominal_working_precision=100):
    """Discard all previously computed physics and all proof objects."""
    problem='Q3' if plan.get('relays') else 'Q2'
    transport_fields=('id','type','boxes','order','start','drone','battery')
    relay_fields=('id','position','start','service_start','service_end','drone','component')
    d=dict(format='fixed_decisions_v1',problem=problem,
           meaning='A feasible schedule specified as fixed decisions; replay recomputes physical values from raw inputs and does not repeat or claim an optimization search.',
           transport=[{k:copy.deepcopy(t[k]) for k in transport_fields} for t in plan['tasks']])
    if problem=='Q2':return d
    if nominal_working_precision<80:raise ValueError('Nominal working precision must be at least 80 digits')
    d['nominal_working_precision_digits']=nominal_working_precision
    # Event clocks are finite-precision schedule decisions. They are not flight
    # geometry, energy, SOC or proof outputs. Raw duration differences are audited.
    for source,target in zip(plan['tasks'],d['transport']):
        target['event_clock']=[dict(start=e['start'],end=e['end']) for e in source['events']]
    d['relays']=[{k:copy.deepcopy(r[k]) for k in relay_fields} for r in plan['relays']]
    d['communication_rule']='Direct priority in nominal layer; robust provider selection and switching times are control decisions, never stored proof values.'
    byevent={};bypoints={}
    for row in plan['communication']['intervals']:byevent.setdefault((row['task'],row['event']),[]).append(row)
    for row in plan['communication']['boundary_points']:bypoints.setdefault((row['task'],row['event']),[]).append(row)
    decisions=[]
    for task in plan['tasks']:
        for ei,event in enumerate(task['events']):
            if 'p0' not in event:continue
            key=(task['id'],ei);rows=sorted(byevent[key],key=lambda r:(r['start'],r['end']));points=bypoints[key]
            times=sorted({r['time'] for r in points}|{x for r in rows for x in [r['start'],r['end']]})
            if times[0]!=event['start'] or times[-1]!=event['end']:raise ValueError('Source partition endpoints are not exact')
            index={x:i for i,x in enumerate(times)}
            def clock(x):
                if x==event['start']:return {'anchor':'event_start'}
                if x==event['end']:return {'anchor':'event_end'}
                return {'anchor':'schedule_time','seconds':x}
            decisions.append(dict(task=task['id'],event=ei,
                switches=[clock(x) for x in times],
                intervals=[dict(first=index[r['start']],last=index[r['end']],mode=r['mode'],relay=r['relay']) for r in rows],
                boundary_points=[dict(at=index[r['time']],mode=r['mode'],relay=r['relay']) for r in points]))
    d['communication_decisions']=decisions
    d['acceptance']=dict(delta_g_db=.01,clearance_m=1.,negative_budget_tolerance_db=0.,service_time_tolerance_s=0.)
    return d

def reconstruct_transport(model,decisions):
    tasks=[];clock_differences=[]
    for d in decisions:
        route=model.route(d['type'],d['boxes'],d['order'])
        if route is None or route['soc']<.2:raise RuntimeError('Infeasible fixed cargo or battery energy: '+d['id'])
        task=absolute(route,d['start'],d['drone'],d['battery'],d['id'])
        if 'event_clock' in d:
            clocks=d['event_clock']
            if len(clocks)!=len(task['events']):raise RuntimeError('Event clock count differs from raw route')
            for i,(event,clock) in enumerate(zip(task['events'],clocks)):
                for field in ('start','end'):
                    raw,chosen=event[field],clock[field]
                    if not math.isfinite(chosen) or abs(raw-chosen)>1e-8:raise RuntimeError('Fixed event time is inconsistent with raw flight duration')
                    if raw!=chosen:clock_differences.append(dict(task=d['id'],event=i,field=field,raw_recomputed=raw,fixed_schedule_decision=chosen,absolute_difference=abs(raw-chosen)))
                    event[field]=chosen
                if event['start']>event['end']:raise RuntimeError('Negative physical event duration')
            if task['events'][0]['start']!=d['start']:raise RuntimeError('Preparation start decision differs from first event')
            if any(a['end']!=b['start'] for a,b in zip(task['events'],task['events'][1:])):raise RuntimeError('Fixed event clock gap or overlap')
            chosen_return=task['events'][-1]['end']
            if task['return_time']!=chosen_return:clock_differences.append(dict(task=d['id'],field='return_time',raw_recomputed=task['return_time'],fixed_schedule_decision=chosen_return,absolute_difference=abs(task['return_time']-chosen_return)))
            task['return_time']=chosen_return
            for event in task['events']:
                if event['phase']=='交接':
                    for box in task['boxes']:
                        if model.boxes[box]['site']==event['node']:
                            chosen=event['end'];raw=task['deliveries'][box]
                            if raw!=chosen:clock_differences.append(dict(task=d['id'],field='deliveries.'+box,raw_recomputed=raw,fixed_schedule_decision=chosen,absolute_difference=abs(raw-chosen)))
                            task['deliveries'][box]=chosen
        tasks.append(task)
    return tasks,clock_differences

def reconstruct_communication(model,q,decisions):
    links=Links(model,.01,1.);tasks={t['id']:t for t in q['tasks']};relays={r['id']:r for r in q['relays']}
    back={rid:links.certify(links.gateway,r['position'],r['position'],'R','G') for rid,r in relays.items()}
    if not all(p['certified'] for p in back.values()):raise RuntimeError('Raw-recomputed relay backhaul rejected')
    intervals=[];boundaries=[]
    expected={(t['id'],i) for t in q['tasks'] for i,e in enumerate(t['events']) if 'p0' in e}
    seen=set()
    for decision in decisions:
        key=(decision['task'],decision['event'])
        if key in seen:raise RuntimeError('Duplicate communication event')
        seen.add(key);event=tasks[key[0]]['events'][key[1]]
        times=[]
        for v in decision['switches']:
            if v['anchor']=='event_start':tm=event['start']
            elif v['anchor']=='event_end':tm=event['end']
            elif v['anchor']=='schedule_time':tm=v['seconds']
            else:raise ValueError('Unknown clock anchor')
            times.append(tm)
        if not times or times[0]!=event['start'] or times[-1]!=event['end'] or times!=sorted(set(times)):
            raise RuntimeError('Fixed switching decisions incompatible with raw-recomputed event boundaries')
        def proof(lo,hi,relay):
            p0,p1=point_on(event,lo),point_on(event,hi)
            if relay:
                r=relays[relay]
                if not max(r['ready'],r['service_start'])<=lo<=hi<=r['service_end']:
                    raise RuntimeError(f'Strict closed relay service timing rejected: {key}, {relay}, event range=({lo!r},{hi!r}), service=({max(r["ready"],r["service_start"])!r},{r["service_end"]!r})')
                result=links.certify(r['position'],p0,p1,'T','A')
            else:result=links.certify(links.gateway,p0,p1,'T','G')
            if not result['certified']:raise RuntimeError('Raw-recomputed closed communication certificate rejected')
            return result
        cursor=times[0]
        for row in decision['intervals']:
            lo,hi=times[row['first']],times[row['last']]
            if lo!=cursor or not lo<hi:raise RuntimeError('Strict communication gap or overlap')
            cursor=hi
            intervals.append(dict(task=key[0],event=key[1],phase=event['phase'],start=lo,end=hi,
                mode=row['mode'],relay=row['relay'],interval='closed certificate; boundary policy explicit',
                certificate=proof(lo,hi,row['relay'])))
        if cursor!=event['end']:raise RuntimeError('Incomplete closed event coverage')
        points=set()
        for row in decision['boundary_points']:
            tm=times[row['at']];points.add(tm)
            boundaries.append(dict(task=key[0],event=key[1],time=tm,mode=row['mode'],relay=row['relay'],certificate=proof(tm,tm,row['relay'])))
        if points!=set(times):raise RuntimeError('Missing exact boundary decisions')
    if seen!=expected:raise RuntimeError('Missing or unexpected physical event decisions')
    margins=[r['certificate']['margin_lower_db'] for r in intervals+boundaries]+[p['margin_lower_db'] for p in back.values()]
    return dict(policy='direct_first_else_bound_relay',method='Raw geometry and fixed switching/provider decisions; every proof recomputed',delta_g_db=.01,clearance_m=1.,budget_roundoff_tolerance_db=0.,intervals=intervals,boundary_points=boundaries,backhaul_certificates=back,failures=[],min_certified_margin_db=min(margins))

def replay(decisions):
    if decisions['format']!='fixed_decisions_v1':raise ValueError('Unsupported decision format')
    model=Model();tasks,clock_differences=reconstruct_transport(model,decisions['transport'])
    q=dict(model=MODEL,version='fixed_decision_replay_v004',tasks=tasks,
           scope='Recomputation from original tables and DEM with fixed cargo/routes/start/resource/link decisions; no previous physical results or proof objects read.',
           status='replayed_pending_independent_check')
    q['raw_clock_reconstruction']=dict(meaning='Raw durations were independently recomputed before applying specified finite-precision event-clock decisions. These differences are disclosed, not hidden by resource or communication tolerance.',comparison_tolerance_seconds=1e-8,difference_count=len(clock_differences),max_absolute_difference_seconds=max((r['absolute_difference'] for r in clock_differences),default=0),differences=clock_differences)
    q['metrics']=metrics(model,tasks)
    if decisions['problem']=='Q3':
        q['relays']=[relay_task(model,d['position'],d['service_start'],d['service_end'],d['start'],d['drone'],d['component'],d['id']) for d in decisions['relays']]
        for r in q['relays']:
            if r['ready']>r['service_start']:raise RuntimeError('Exact setup-before-service condition failed')
        q['transport_metrics']=copy.deepcopy(q['metrics'])
        jm=dict(makespan=max([t['return_time'] for t in tasks]+[r['return_time'] for r in q['relays']]),
            transport_energy=q['metrics']['energy'],relay_energy=sum(r['energy'] for r in q['relays']),
            transport_sorties=len(tasks),relay_sorties=len(q['relays']),total_sorties=len(tasks)+len(q['relays']))
        jm['total_energy']=jm['transport_energy']+jm['relay_energy'];q['joint_metrics']=jm
    resources=check_resources(model,tasks,q.get('relays',[]))
    if resources['errors']:raise RuntimeError(resources['errors'])
    q['resource_check']=resources
    if decisions['problem']=='Q3':
        q['communication']=reconstruct_communication(model,q,decisions['communication_decisions'])
        with localcontext() as context:
            context.prec=decisions['nominal_working_precision_digits'];q['nominal_communication']=build(model,q)
        if q['nominal_communication']['failures']:raise RuntimeError('Raw-recomputed nominal states failed')
    return q

if __name__=='__main__':
    print('Reusable module; use prepare_fixed_decisions.py, replay_fixed_results.py and compare_fixed_results.py.')
