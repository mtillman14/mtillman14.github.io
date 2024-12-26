---
layout: single
title:  "The Eternal Search for a Good Graph Visualizer"
tags:
  - software
---

Graphs ([in the mathematical sense](https://en.wikipedia.org/wiki/Graph_(discrete_mathematics))) underly many common problems, as they are an elegant way to manage "many to many" relationships. They have certainly captured my attention in the last few years as I attempt to build a workflow orchestration tool/data processing pipeline runner for use in my own research, which requires a graph (specifically, a [DAG](https://en.wikipedia.org/wiki/Directed_acyclic_graph)) to keep track of the dependencies of each step (see my current effort [here](https://github.com/ResearchOS/dagrunner)).

I find myself utilizing graphs in other projects as well, such as [my attempt to better understand the structure of the items in my Zotero library](https://github.com/mtillman14/zotero_utils). 

However, I continue to struggle to be able to visualize the graphs that I create. Nowhere online have I found a graph visualization tool that meets all of my criteria:

1. Open-source and straightforward enough to fit into my tech stack (Python and/or some basic Javascript)

2. Works with directed and undirected graphs

3. Interactivity - moving nodes, adding and deleting nodes and edges, selecting a node to highlight it and all of its edges

4. Metadata - more info about a selected node should be obtainable

5. Layouts - customize how the nodes are laid out, as graphs made for different purposes need to be laid out differently

6. Connectivity-based sizing - for some purposes, it is helpful to make more strongly connected/central nodes show larger, to reflect their integral status

7. Visualized redundant connections between the same two nodes. If two nodes are connected to each other more than once, it is often desirable for the visualization to reflect that fact

I have attempted to use several existing graph visualization tools:

## [cytoscape.js](https://js.cytoscape.org)
This is quite a powerful framework for graph visualization, however it is not straightforward to integrate with a Python stack, and as a Javascript and HTML novice, this solution feels quite out of reach.

## [dagviz](https://github.com/WimYedema/dagviz)
Another approach was to generate a static svg of a graph, in a similar fashion as Git's branching graphs. Simple enough to get an svg output from, but the lack of interactivity or customizability is really a deal breaker.

# A New Approach: [Cosma](https://cosma.arthurperret.fr/index.html)
I recently discovered Cosma, a relatively new graph visualization tool that at first glance appears to meet all of my above criteria! I need to try out this tool and will report back. To use it, I need to add a new method to my [base-dag](https://github.com/ResearchOS/base-dag) project's DAG class to save each node as a .md file with YAML headers and links to the connected nodes.

More to come here after I test out Cosma!