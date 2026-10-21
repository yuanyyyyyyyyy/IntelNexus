# -*- coding: utf-8 -*-
"""v3.6 正文数据独立核验：从 metrics_long.jsonl 原始记录重算表7五行+旁证核对。
独立于 paperA/stats/recompute_stats.py 的第二实现。"""
import json, math, random
import numpy as np
from scipy import stats as st

E = r'D:/Improve/Project/Python/IntelNexus/experiments'

# ---------- 1. 载入逐记录指标 ----------
recs = [json.loads(l) for l in open(E + '/reports/metrics_long.jsonl', encoding='utf-8')]
print(f'记录总数: {len(recs)}  失败: {sum(1 for r in recs if r.get("error"))}')

def per_sample(config, field, exclude_empty_ref=False):
    """每样本 3 次重复取均值；返回 {sample_id: mean}。"""
    buckets = {}
    for r in recs:
        if r['config'] != config or r.get('error'):
            continue
        v = r.get(field)
        if v is None:
            continue
        buckets.setdefault(r['sample_id'], []).append(v)
    return {k: sum(v)/len(v) for k, v in buckets.items() if len(v) == 3}

def holm(pvals):
    idx = sorted(range(len(pvals)), key=lambda i: pvals[i])
    m = len(pvals); out = [0.0]*m; prev = 0.0
    for rank, i in enumerate(idx):
        adj = min(1.0, (m - rank) * pvals[i])
        prev = max(prev, adj)          # 逐步单调
        out[i] = prev
    return out

def rank_biserial(diffs):
    """与 cost_recalc.py 同口径：含零差排平均秩，零差不计入 W+/W−，rb=(W+−W−)/(W++W−)。"""
    n = len(diffs)
    ranked = sorted(range(n), key=lambda i: abs(diffs[i]))
    ranks = [0.0]*n; i = 0
    while i < n:
        j = i
        while j+1 < n and abs(diffs[ranked[j+1]]) == abs(diffs[ranked[i]]):
            j += 1
        avg = (i+j)/2 + 1
        for k in range(i, j+1):
            ranks[ranked[k]] = avg
        i = j+1
    w_plus = sum(ranks[i] for i in range(n) if diffs[i] > 0)
    w_minus = sum(ranks[i] for i in range(n) if diffs[i] < 0)
    return (w_plus - w_minus)/(w_plus + w_minus) if (w_plus+w_minus) else 0.0

def bootstrap_ci(diffs, B=10000, seed=20260913):
    rng = random.Random(seed); meds = []
    n = len(diffs)
    for _ in range(B):
        s = [diffs[rng.randrange(n)] for _ in range(n)]
        s.sort()
        m = (s[(n-1)//2] + s[n//2]) / 2 if n % 2 == 0 else s[n//2]
        meds.append(m)
    meds.sort()
    return meds[int(0.025*B)], meds[int(0.975*B)]

def median(x):
    s = sorted(x); n = len(s)
    return (s[(n-1)//2] + s[n//2])/2 if n % 2 == 0 else s[n//2]

# ---------- 2. 表7 五行重算 ----------
tests = [
    ('本地vs旗舰 F1', 'qwen3:8b', 'cloud_flagship', 'entity_f1'),
    ('本地vs旗舰 时延', 'qwen3:8b', 'cloud_flagship', 'latency_s'),
    ('旗舰vs轻量 F1', 'cloud_flagship', 'cloud_light', 'entity_f1'),
    ('旗舰vs最强基线 F1', 'cloud_flagship', 'baseline_textrank', 'entity_f1'),
    ('本地vs最强基线 F1', 'qwen3:8b', 'baseline_textrank', 'entity_f1'),
]
print('\n== 表7 独立重算 ==')
raws = []
for name, a, b, f in tests:
    da, db = per_sample(a, f), per_sample(b, f)
    common = sorted(set(da) & set(db))
    va = [da[k] for k in common]; vb = [db[k] for k in common]
    diffs = [x-y for x, y in zip(va, vb)]
    w = st.wilcoxon(va, vb, zero_method='wilcox', correction=False,
                    method='approx' if len(common) > 20 else 'exact')
    raws.append((name, w.pvalue, diffs, common))
fam = [t[1] for t in raws]
adj = holm(fam)
expect = {  # 正文表7
    '本地vs旗舰 F1':      dict(W=542.0,  p='1.10e-09', med=-0.237, ci=(-0.280,-0.156), rb=-0.757),
    '本地vs旗舰 时延':    dict(W=0.0,    p='2.73e-17', med=123.33, ci=(117.51,125.89), rb=1.000),
    '旗舰vs轻量 F1':      dict(W=1057.0, p='1.36e-05', med=0.047,  ci=(0.033,0.076),  rb=0.546),
    '旗舰vs最强基线 F1':  dict(W=997.5,  p='5.81e-06', med=0.232,  ci=(0.159,0.283),  rb=0.572),
    '本地vs最强基线 F1':  dict(W=1288.5, p='0.594',    med=0.000,  ci=(0.000,0.006),  rb=-0.071),
}
for (name, p, diffs, common), pa in zip(raws, adj):
    e = expect[name]
    lo, hi = bootstrap_ci(diffs)
    w2 = st.wilcoxon([x for x in diffs], zero_method='wilcox') if any(diffs) else None
    W = w2.statistic if w2 else 0.0
    rb = rank_biserial(diffs)
    ok = (abs(W - e['W']) < 0.5 and abs(median(diffs) - e['med']) < 0.0006*max(1,abs(e['med']))
          and abs(lo-e['ci'][0]) < 0.002*max(1,abs(e['ci'][0])) and abs(hi-e['ci'][1]) < 0.002*max(1,abs(e['ci'][1]))
          and abs(rb - e['rb']) < 0.001)
    print(f'{name:18s} n={len(common):3d} W={W:8.1f}(期望{e["W"]}) p_adj={pa:.3e}(期望{e["p"]}) '
          f'中位差={median(diffs):+.4f}(期望{e["med"]}) CI=[{lo:.4f},{hi:.4f}](期望{e["ci"]}) rb={rb:+.3f}(期望{e["rb"]}) {"✅" if ok else "❌"}')

# ---------- 3. 表3 样本间SD ----------
print('\n== 表3 均值±样本间SD ==')
body3 = {'qwen3:8b': (0.213,0.229,0.008,0.007,0.571,0.017),
         'cloud_flagship': (0.409,0.167,0.006,0.006,0.580,0.016),
         'cloud_light': (0.356,0.149,0.006,0.005,0.579,0.016),
         'baseline_keyword': (0.202,0.262,0.132,0.190,0.659,0.068),
         'baseline_textrank': (0.238,0.278,0.122,0.145,0.650,0.071),
         'baseline_tfidf': (0.173,0.246,0.140,0.170,0.675,0.063)}
for cfg, (f1m,f1s,rm,rs,bm,bs) in body3.items():
    f1 = per_sample(cfg, 'entity_f1'); rg = per_sample(cfg, 'rouge_l'); bt = per_sample(cfg, 'bertscore')
    import statistics as S
    print(f'{cfg:18s} F1 {S.mean(f1.values()):.3f}±{S.stdev(f1.values()):.3f}(期望{f1m}±{f1s}) '
          f'ROUGE {S.mean(rg.values()):.3f}±{S.stdev(rg.values()):.3f}({rm}±{rs}) '
          f'BERT {S.mean(bt.values()):.3f}±{S.stdev(bt.values()):.3f}({bm}±{bs})')

# ---------- 4. 旁证 ----------
print('\n== 旁证 ==')
pv = json.load(open(E+'/reports/privacy.json', encoding='utf-8'))
def find_loopback(o, path=''):
    if isinstance(o, dict):
        for k,v in o.items(): yield from find_loopback(v, path+'/'+k)
    elif isinstance(o, list):
        for i,v in enumerate(o): yield from find_loopback(v, f'{path}[{i}]')
    else:
        yield path, o
hits = [(p,v) for p,v in find_loopback(pv) if isinstance(v,(int,float)) and 115000 < v < 117000]
print('回环流量 115919 候选:', hits[:3])
ps = json.load(open(E+'/reports/privacy_scan.json', encoding='utf-8'))
s = json.dumps(ps, ensure_ascii=False)
for k in ('3711','34','166','590','3768','733','4501'):
    print(f'残留 {k}:', '出现' if k in s else '未出现')
env = json.load(open(E+'/reports/env_report.json', encoding='utf-8'))
es = json.dumps(env, ensure_ascii=False)
for k in ('0.30.10','6141','566.26','12.7','25H2','7735H','3.14.4','1.1.0','1.6.0','0.42.1','1.9.0','1.18.1','2.5.2'):
    print(f'环境 {k}:', '出现' if k in es else '未出现')
agg = json.load(open(E+'/reports/aggregate.json', encoding='utf-8'))
for cfg, th in (('qwen3:8b',0.44), ('cloud_flagship',1.89), ('cloud_light',1.63)):
    v = agg['configs'][cfg].get('throughput_per_min'); pg = agg['configs'][cfg].get('peak_gpu_mb')
    print(f'吞吐 {cfg}: {v} (期望≈{th})  显存峰值: {pg}')

# ---------- 5. U*（P50 口径示意） ----------
P,pe,C,L,U0,T = 38.7,0.49,7000.0,5,0.25,152.21785
def cost(T,U): return P*T/3.6e6*pe + C*T/(3600*L*8760*U)
c25 = cost(T,0.25)
from scipy.optimize import brentq
ustar = brentq(lambda u: cost(T,u)-0.023013, 0.01, 0.99)
print(f'\n== U*（P50 口径）== 基准成本={c25:.4f}(期望0.0278)  U*={ustar:.4f}(期望≈0.30)  日均={ustar*24:.2f}h')
