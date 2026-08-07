import json, collections
ROOT = '/Users/ck/dev/things/tekton'
g = json.load(open(ROOT + '/experiments/subtractive/_explore/graph.json'))
edges = [(int(s), p, int(t)) for s, p, t in g['edges']]
own = {int(k): int(v) for k, v in g['own'].items()}
cls = {int(k): v for k, v in g['classes'].items()}
names = {int(k): v for k, v in g['names'].items()}
SF = g['frame_roles']['self_family']
roles = g['frame_roles']

print('== named elements ==')
for i in sorted(names):
    if names[i]:
        print(f'  {i} {cls[i]:24s} {names[i]!r}')
