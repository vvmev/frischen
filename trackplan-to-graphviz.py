#!/usr/bin/env python
# -*- coding: utf-8 -*-

import yaml

from graphviz import Graph


element_types = {
    'connection': 'diamond',
    'switch': 'triangle',
    'buffer-stop': 'octagon',
    'HV-H': 'circle',
    'HV-V': 'star',
}


def element_and_link_from_connect(connect):
    return connect.rsplit('.', 2)


def shape_for_element_type(type):
    if type in element_types:
        return element_types[type]
    return 'box'


with open('adorf-trackplan.yml') as f:
    t = yaml.load(f)

dot = Graph(comment=t['name'])
dot.graph_attr['rankdir'] = 'LR'

for k, v in t['elements'].items():
    shape = shape_for_element_type(v['type'])
    dot.node(k, v['name'], shape=shape)

for rank in ['min', 'max']:
    with dot.subgraph() as s:
        s.attr(rank=rank)
        for k, v in t['elements'].items():
            if 'graphviz' in v:
                if 'rank' in v['graphviz']:
                    if rank in v['graphviz']['rank']:
                        s.node(k)

for k, v in t['tracks'].items():
    n0 = element_and_link_from_connect(v['connects'][0])
    n1 = element_and_link_from_connect(v['connects'][1])
    length = abs(v['start'] - v['end'])
    weight = str(int(10000.0 / length)) if length > 0 else '10000'
    print('{} -> {} ({})'.format(n0[0], n1[0], weight))
    dot.edge(n0[0], n1[0], label=k, weight=weight)

print(dot.source)
dot.render('adorf-trackplan.gv', view=True)
