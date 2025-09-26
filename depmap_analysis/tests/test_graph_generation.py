from datetime import datetime

import pandas as pd
from networkx import DiGraph, MultiDiGraph

from depmap_analysis.network_functions.net_functions import \
    sif_dump_df_to_digraph, MIN_WEIGHT
from depmap_analysis.tests import _gen_sym_df
from indra.assemblers.indranet.net import default_sign_dict

# Add input
agA_names = ['nameX1', 'nameX2']
agA_ns_list = ['nsX1', 'nsX2']
agA_ids = ['idX1', 'idX2']
agB_names = ['nameY1', 'nameY2']
agB_ns_list = ['nsY1', 'nsY2']
agB_ids = ['idY1', 'idY2']
h1, h2 = 1234657890, 9876543210
hashes = [h1, h2]
bd = [0.685, 0.95]
stmt_types = ['Activation', 'Complex']
ev_counts = [7, 13]
src = [{'srcA': 2, 'srcB': 5}, {'srcA': 5, 'srcB': 8}]
logps = [-0.5, -1.5]

sif_dict = {
    'agA_name': agA_names,
    'agA_ns': agA_ns_list,
    'agA_id': agA_ids,
    'agB_name': agB_names,
    'agB_ns': agB_ns_list,
    'agB_id': agB_ids,
    'stmt_type': stmt_types,
    'evidence_count': ev_counts,
    'stmt_hash': hashes,
    'source_counts': src,
    'belief': bd,
    'logp': logps
}


def _get_df():
    sif_df = pd.DataFrame(sif_dict)
    return sif_df


def test_df_from_dict():
    df = _get_df()
    assert len(agA_names) == len(df)


def test_digraph_dump():
    sif_df = _get_df()
    date = datetime.utcnow().strftime('%Y-%m-%d')
    idg: DiGraph = sif_dump_df_to_digraph(df=sif_df, date=date,
                                          graph_type='digraph',
                                          include_entity_hierarchies=False)
    assert idg.graph.get('edge_by_hash')
    assert idg.graph.get('date')
    assert idg.graph.get('node_by_ns_id')
    assert idg.graph['edge_by_hash'][h1] == ('nameX1', 'nameY1')
    assert idg.graph['edge_by_hash'][h2] == ('nameX2', 'nameY2')
    assert idg.edges.get(('nameX1', 'nameY1'))
    assert isinstance(idg.edges[('nameX1', 'nameY1')]['statements'], list)
    assert idg.edges[('nameX1', 'nameY1')]['statements'][0]['stmt_hash'] == \
           h1


# This test takes ~10 s
def test_ontological_edges():
    sif_df = _get_df()
    date = datetime.utcnow().strftime('%Y-%m-%d')
    idg: DiGraph = sif_dump_df_to_digraph(df=sif_df, date=date,
                                          graph_type='digraph',
                                          include_entity_hierarchies=True)
    assert len(idg.edges) > 1
    tested = False
    for u, v, data in idg.edges(data=True):
        for sd in data['statements']:
            if 'fplx' not in sd['stmt_type']:
                continue
            assert sd['evidence_count'] == 1
            assert sd['source_counts'] == {'fplx': 1}
            assert sd['belief'] == 1.0
            assert sd['curated']
            assert sd['weight'] == MIN_WEIGHT, \
                f'weight={sd["weight"]}, MIN_WEIGHT={MIN_WEIGHT}'
            assert 'stmt_hash' in sd
            assert 'curated' in sd
            tested = True
        if tested:
            break


def test_signed_graph_dump():
    sif_df = _get_df()
    signed_edge1 = (agA_names[0], agB_names[0], 0)
    sign_node_edge1 = ((agA_names[0], 0), (agB_names[0], 0))
    date = datetime.utcnow().strftime('%Y-%m-%d')
    seg, sng = \
        sif_dump_df_to_digraph(df=sif_df, date=date, graph_type='signed',
                               include_entity_hierarchies=False)
    assert isinstance(seg, MultiDiGraph), str(seg.__class__)
    assert isinstance(sng, DiGraph), str(sng.__class__)

    # Check signed edge graph
    assert seg.graph.get('edge_by_hash')
    assert seg.graph['edge_by_hash'][h1] == signed_edge1
    assert seg.graph.get('node_by_ns_id')
    assert seg.graph.get('date') == date
    assert len(seg.edges) == 1, len(seg.edges)
    # All nodes added, skip doesn't happen until nodes added
    assert len(seg.nodes) == 4, len(seg.nodes)
    assert seg.nodes[signed_edge1[0]] == {'ns': agA_ns_list[0],
                                          'id': agA_ids[0]}
    assert seg.edges.get(signed_edge1)
    assert 'weight' in seg.edges[signed_edge1]
    assert isinstance(seg.edges[signed_edge1]['statements'], list)
    sd = seg.edges[signed_edge1]['statements'][0]
    assert sd['stmt_hash'] == h1
    assert sd['stmt_type'] == stmt_types[0]
    assert sd['belief'] == bd[0]
    assert sd['evidence_count'] == ev_counts[0]
    assert sd['source_counts'] == src[0]
    assert 'curated' in sd

    # Check signed node graph
    assert sng.graph.get('edge_by_hash')
    assert sng.graph['edge_by_hash'][h1] == sign_node_edge1
    assert sng.graph.get('node_by_ns_id')
    assert sng.graph.get('date') == date
    assert len(sng.edges) == 1
    # All nodes added, skip doesn't happen until nodes added
    assert len(sng.nodes) == 4
    assert sng.nodes[sign_node_edge1[0]] == {'ns': agA_ns_list[0],
                                             'id': agA_ids[0]}
    assert sng.edges.get(sign_node_edge1)
    assert 'weight' in sng.edges[sign_node_edge1]
    assert isinstance(sng.edges[sign_node_edge1]['statements'], list)
    sd = sng.edges[sign_node_edge1]['statements'][0]
    assert sd['stmt_hash'] == h1
    assert sd['stmt_type'] == stmt_types[0]
    assert sd['belief'] == bd[0]
    assert sd['evidence_count'] == ev_counts[0]
    assert sd['source_counts'] == src[0]
    assert 'curated' in sd


def test_digraph_signed_types_dump():
    sif_df = _get_df()
    date = datetime.utcnow().strftime('%Y-%m-%d')
    edge = (agA_names[0], agB_names[0])
    dg_st = sif_dump_df_to_digraph(df=sif_df, date=date,
                                   graph_type='digraph-signed-types',
                                   include_entity_hierarchies=False)
    assert dg_st.graph.get('edge_by_hash')
    assert dg_st.graph['edge_by_hash'][h1] == edge
    assert dg_st.graph.get('node_by_ns_id')
    assert dg_st.graph.get('date') == date
    assert len(dg_st.edges) == 1, len(dg_st.edges)
    assert len(dg_st.nodes) == 2, len(dg_st.nodes)
    assert all(all([sd['stmt_type'] in default_sign_dict
                    for sd in data['statements']])
               for _, _, data in dg_st.edges(data=True))


def test_expanded_signed_graph_dump():
    sif_df = _get_df()
    signed_edge1 = (agA_names[0], agB_names[0], 0)
    signed_edge2 = (agA_names[1], agB_names[1], 0)
    signed_edge3 = (agA_names[1], agB_names[1], 1)
    sign_node_edge1 = ((agA_names[0], 0), (agB_names[0], 0))
    sign_node_edge2 = ((agA_names[1], 0), (agB_names[1], 0))
    sign_node_edge3 = ((agA_names[1], 0), (agB_names[1], 1))
    date = datetime.utcnow().strftime('%Y-%m-%d')
    seg, sng = \
        sif_dump_df_to_digraph(df=sif_df, date=date,
                               graph_type='signed-expanded',
                               stmt_types=['Complex'],
                               include_entity_hierarchies=False)
    assert isinstance(seg, MultiDiGraph), str(seg.__class__)
    assert isinstance(sng, DiGraph), str(sng.__class__)

    # Check signed edge graph
    assert seg.graph.get('edge_by_hash')
    assert signed_edge1 in seg.graph['edge_by_hash'][h1]
    assert signed_edge2 in seg.graph['edge_by_hash'][h2]
    assert signed_edge3 in seg.graph['edge_by_hash'][h2]
    assert seg.graph.get('node_by_ns_id')
    assert seg.graph.get('date') == date
    assert len(seg.edges) == 3, len(seg.edges)
    assert len(seg.nodes) == 4, len(seg.nodes)
    assert seg.nodes[signed_edge1[0]] == {'ns': agA_ns_list[0],
                                          'id': agA_ids[0]}
    assert seg.nodes[signed_edge2[0]] == {'ns': agA_ns_list[1],
                                          'id': agA_ids[1]}
    assert seg.edges.get(signed_edge1)
    assert seg.edges.get(signed_edge2)
    assert seg.edges.get(signed_edge3)
    assert 'weight' in seg.edges[signed_edge2]
    assert isinstance(seg.edges[signed_edge2]['statements'], list)
    assert isinstance(seg.edges[signed_edge3]['statements'], list)
    sd = seg.edges[signed_edge3]['statements'][0]
    assert sd['stmt_hash'] == h2
    assert sd['stmt_type'] == stmt_types[1]
    assert sd['belief'] == bd[1]
    assert sd['evidence_count'] == ev_counts[1]
    assert sd['source_counts'] == src[1]
    assert 'curated' in sd

    # Check signed node graph
    assert sng.graph.get('edge_by_hash')
    assert sign_node_edge1 in sng.graph['edge_by_hash'][h1]
    assert sign_node_edge2 in sng.graph['edge_by_hash'][h2]
    assert sign_node_edge3 in sng.graph['edge_by_hash'][h2]
    assert sng.graph.get('node_by_ns_id')
    assert sng.graph.get('date') == date
    assert len(sng.edges) == 3
    assert len(sng.nodes) == 5
    assert sng.nodes[sign_node_edge2[0]] == {'ns': agA_ns_list[1],
                                             'id': agA_ids[1]}
    assert sng.edges.get(sign_node_edge2)
    assert sng.edges.get(sign_node_edge3)
    assert 'weight' in sng.edges[sign_node_edge3]
    assert isinstance(sng.edges[sign_node_edge3]['statements'], list)
    sd = sng.edges[sign_node_edge3]['statements'][0]
    assert sd['stmt_hash'] == h2
    assert sd['stmt_type'] == stmt_types[1]
    assert sd['belief'] == bd[1]
    assert sd['evidence_count'] == ev_counts[1]
    assert sd['source_counts'] == src[1]
    assert 'curated' in sd


def test_z_score_edges():
    # Get corr matrix
    name_list = sorted(agA_names + agB_names)
    m = 10 * _gen_sym_df(len(name_list))
    m.columns = name_list
    m.index = name_list

    sif_df = _get_df()
    date = datetime.utcnow().strftime('%Y-%m-%d')
    idg: DiGraph = sif_dump_df_to_digraph(df=sif_df, date=date,
                                          graph_type='digraph',
                                          include_entity_hierarchies=False,
                                          z_sc_path=m,
                                          corr_weight_type='logp')
    edge1 = agA_names[0], agB_names[0]
    edge2 = agA_names[1], agB_names[1]
    assert 'weight' in idg.edges[edge1]
    assert 'weight' in idg.edges[edge2]
    assert 'belief' in idg.edges[edge1]
    assert 'belief' in idg.edges[edge2]
    assert 'z_score' in idg.edges[edge1]['statements'][0]
    assert 'z_score' in idg.edges[edge2]['statements'][0]
    assert 'corr_weight' in idg.edges[edge1]['statements'][0]
    assert 'corr_weight' in idg.edges[edge2]['statements'][0]
    assert 'logp' in idg.edges[edge1]['statements'][0]
    assert 'logp' in idg.edges[edge2]['statements'][0]
