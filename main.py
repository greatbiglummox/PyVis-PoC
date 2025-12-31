import pandas as pd
from pyvis.network import Network
import networkx as nx
import os
import streamlit as st
import streamlit.components.v1 as components
from config.node_styles import NODE_STYLES, DEFAULT_STYLE

def main():
    st.set_page_config(
        page_title="School Network Path Finder",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    st.title('School Network Path Finder')
    st.write("This application finds all paths between two nodes in a school network graph.")
    st.write("Nodes represent entities such as the 500 Students, 25 Teachers, 60 Classes, and 125 Addresses, while edges represent relationships like ENROLLED_IN or TEACHES.")
    st.write("Select the source and target nodes, specify the maximum number of hops, and click 'Find Paths' to generate the report.")

    node_df, edge_df = get_data()
    id_to_label = node_df.set_index('node_id')['label'].to_dict()

    node_types = list(NODE_STYLES.keys())

    default_source_id = 'S0356'
    default_source_type = 'Student'
    default_target_id = 'T012'
    default_target_type = 'Teacher'

    # ensure the flag exists
    if 'show_report' not in st.session_state:
        st.session_state['show_report'] = False
        st.session_state['report_params'] = {}

    col1, col2, col3 = st.columns(3)
    with col1:
        source_type = st.selectbox(
            "Select source node type",
            options=node_types,
            index=node_types.index(default_source_type)
        )
        source_node_ids = node_df[node_df['node_type'] == source_type]['node_id'].tolist()

        source_id = st.selectbox(
            "Select source node",
            options=source_node_ids,
            index=source_node_ids.index(default_source_id) if default_source_id in source_node_ids else 0,
            format_func=lambda nid: f"{id_to_label.get(nid, '')} - {nid}"
        )
    with col2:
        target_type = st.selectbox(
            "Select targe node type",
            options=node_types,
            index=node_types.index(default_target_type)
        )
        target_node_ids = node_df[node_df['node_type'] == target_type]['node_id'].tolist()

        target_id = st.selectbox(
            "Select target node",
            options=target_node_ids,
            index=target_node_ids.index(default_target_id) if default_target_id in target_node_ids else 0,
            format_func=lambda nid: f"{id_to_label.get(nid, '')} - {nid}"
        )
    with col3:
        cutoff = st.number_input("Max hops", min_value=1, max_value=10, value=3, step=1)
        if st.button("Find Paths"):
            # set session state so rendering happens after the columns (at bottom)
            st.session_state['show_report'] = True
            st.session_state['report_params'] = {
                'source_id': source_id,
                'target_id': target_id,
                'cutoff': cutoff
            }

    # Reserve / render the report below the columns
    report_container = st.container()
    if st.session_state.get('show_report'):
        params = st.session_state.get('report_params', {})
        generate_report(node_df, edge_df, params.get('cutoff', 3),
                        params.get('source_id', source_id), params.get('target_id', target_id))

def generate_report(node_df, edge_df, cutoff: int, source_id: str, target_id: str):
    build_graph_from_dfs(node_df, edge_df)
    paths = find_all_paths_between(node_df, edge_df, source_id, target_id, cutoff, directed=False)
    if len(paths) == 0:
        display_html_file('output/no_path.html', height=100)
    else:
        write_report_html(node_df, edge_df, paths)
        display_html_file('output/my_graph.html', height=750)

def get_data():
    node_df = pd.read_csv('data/nodes.csv')
    edge_df = pd.read_csv('data/edges.csv')

    return node_df, edge_df

def write_report_html(node_df, edge_df, path_list):
    if len(path_list) != 0:
        node_list = []
        for idx, (path_ids, path_labels) in enumerate(path_list, 1):
            for node_id in path_ids:
                node_list.append(node_id)
        node_df = node_df[node_df['node_id'].isin(node_list)].copy()
        edge_df = edge_df[(edge_df['source'].isin(node_list)) & (edge_df['target'].isin(node_list))].copy()

    # determine shortest path edges (if any)
    shortest_edge_set = set()
    if path_list:
        # find minimum-length path(s)
        min_len = min(len(path_ids) for path_ids, _ in path_list)
        # pick the first shortest path
        for path_ids, _ in path_list:
            if len(path_ids) == min_len:
                sp = path_ids
                for i in range(len(sp) - 1):
                    shortest_edge_set.add((sp[i], sp[i + 1]))
        #         break
        # # build edge tuples from consecutive nodes
        # for i in range(len(sp) - 1):
        #     shortest_edge_set.add((sp[i], sp[i + 1]))

    net = Network(height="750px", width="100%", bgcolor="#222222", font_color="white")

    # Add nodes according to NODE_STYLES
    for node_type, style in NODE_STYLES.items():
        subset = node_df[node_df['node_type'] == node_type]
        for _, r in subset.iterrows():
            kwargs = {}
            shape = style.get('shape', 'icon')
            if shape == 'icon':
                kwargs['shape'] = 'icon'
                kwargs['icon'] = style.get('icon')
            else:
                kwargs['shape'] = shape
                if 'color' in style:
                    kwargs['color'] = style['color']
                if 'size' in style:
                    kwargs['size'] = style['size']
            net.add_node(r['node_id'], label=r['label'], title=r['label'], **kwargs)

    # Add any remaining node types with a default style
    remaining = node_df[~node_df['node_type'].isin(NODE_STYLES.keys())]
    for _, r in remaining.iterrows():
        net.add_node(
            r['node_id'],
            label=r['label'],
            title=r['label'],
            shape=DEFAULT_STYLE.get('shape'),
            color=DEFAULT_STYLE.get('color'),
            size=DEFAULT_STYLE.get('size')
        )

    # Add Edges: color red if part of the shortest path, otherwise blue
    for _, r in edge_df.iterrows():
        src = r['source']
        tgt = r['target']
        # consider undirected membership too
        if (src, tgt) in shortest_edge_set or (tgt, src) in shortest_edge_set:
            edge_color = 'red'
            edge_width = 3
        else:
            edge_color = 'blue'
            edge_width = 1
        net.add_edge(src, tgt, title=r.get('relationship'), color=edge_color, width=edge_width)

    html_path = "output/my_graph.html"
    net.save_graph(html_path)

    # Inject FontAwesome link so icons render in iframe
    fa_link = '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">'
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("</head>", f"{fa_link}\n</head>")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

def build_graph_from_dfs(node_df, edge_df, directed=True):
    """Build a NetworkX graph from node and edge DataFrames.
    Expects node id column `node_id` and edge columns `source` and `target`."""
    G = nx.DiGraph() if directed else nx.Graph()
    # add nodes with attributes (guard for missing columns)
    id_col = 'node_id'
    if id_col in node_df.columns:
        for _, r in node_df.iterrows():
            G.add_node(r[id_col], label=r.get('label'), node_type=r.get('node_type'))
    else:
        raise KeyError(f"Expected `{id_col}` column in node_df")
    # add edges
    if {'source', 'target'}.issubset(edge_df.columns):
        for _, r in edge_df.iterrows():
            G.add_edge(r['source'], r['target'], relationship=r.get('relationship'))
    else:
        raise KeyError("Expected `source` and `target` columns in edge_df")
    return G

def find_all_paths_between(node_df, edge_df, source_id, target_id, cutoff, directed):
    """Return list of (path_node_ids, path_labels) for all simple paths between two node ids.
    If cutoff is None, use len(nodes)-1 to limit path length."""
    G = build_graph_from_dfs(node_df, edge_df, directed=directed)
    if cutoff is None:
        cutoff = max(len(G.nodes) - 1, 1)
    try:
        all_paths = list(nx.all_simple_paths(G, source=source_id, target=target_id, cutoff=cutoff))
    except nx.NodeNotFound:
        return []  # no such node(s)
    # map ids to labels
    id_to_label = {row['node_id']: row.get('label') for _, row in node_df.iterrows()}
    results = []
    for path in all_paths:
        labels = [id_to_label.get(n) for n in path]
        results.append((path, labels))
    return results

def display_html_file(path: str, height: int = 750):
    """Read a local HTML file and embed it into the Streamlit page."""
    if not os.path.exists(path):
        st.info(f"No HTML to show at `{path}`")
        return
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    components.html(html, height=height, scrolling=True)

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
