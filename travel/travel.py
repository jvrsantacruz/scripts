#!/usr/bin/env python
#-*- coding: utf-8 -*-
"""
Dijkstra travel map

Javier Santacruz 2012-07-31
"""
import sys
import yaml
import logging
from collections import defaultdict
from optparse import OptionParser

_LOGGING_FMT_ = '%(asctime)s %(levelname)-8s %(message)s'


def error(msg, is_exit=True):
    logging.error(msg)
    if is_exit:
        sys.exit()


def open_yaml(yaml_path):
    "Opens and returns the yaml file"
    yfile = None
    try:
        with open(yaml_path, 'r') as gfile:
            yfile = yaml.load(gfile, Loader=yaml.Loader)
    except yaml.error.YAMLError, e:
        logging.error('Could not open the graph file {0}: {1}'
                      .format(yaml_path, e))

    if not isinstance(yfile, dict):
        logging.error('Wrong yaml file format {0}'.format(yaml_path))
        return

    return yfile


class Graph(object):
    """
    Class to hold the graph and perform operations on it.
    """

    def __init__(self, graph_path):
        """
        Reads the graph config file in yaml
        The yaml should look like:

            'place':
                - 'other_place': cost

        Omitted origin-dest pairs will set the connection as unreachable.

        returns graph as a dictionary:
            {
            'from': {
                'to_1': cost,
                'to_2': cost ..
                }
            ..
            }
        """
        # The graph is a dict of connection dicts
        # The connection dicts returns infinite for not connected cities
        # The graph returns an empty connection dict for non existent cities
        inf = lambda: float('inf')
        dict_inf = lambda: defaultdict(inf)

        self.graph = defaultdict(dict_inf)
        for origin, dests in open_yaml(graph_path).iteritems():
            ddict = dict()
            for d in dests:
                ddict.update(d.items())
            self.graph[origin] = defaultdict(inf, ddict)

    def min_cost(self, orig, dest):
        """
        Takes strings orig, dest (both in graph)
        Returns (min cost, path-list)
        """
        # Dist from orig to x
        costs = defaultdict(lambda: float('inf'), {orig: 0})
        prev = defaultdict()
        graph = self.graph
        nvisited = set(graph.keys())

        while nvisited:
            city = min(nvisited, key=lambda c: costs[c])

            if costs[city] == float('inf'):  # destination unreachable
                break

            neighbours = graph[city]
            nvisited.discard(city)  # mark as visited

            for neighbor in neighbours:
                alt = costs[city] + graph[city][neighbor]
                if alt < costs[neighbor]:
                    costs[neighbor] = alt
                    prev[neighbor] = city

        return costs[dest], self.path(orig, dest, prev)

    def path(self, orig, dest, previous):
        """
        Returns the path from origin to dest
        """
        path = []
        city = dest
        while city != orig:
            path.insert(0, city)
            city = previous[city]

        path.insert(0, orig)
        return path


def parse_opts():
    """Parses the command line and checks some values.
    Returns parsed options and positional arguments: (opts, args)"
    """
    parser = OptionParser()

    parser.add_option("-g", "--graph", dest="graph_path", action="store",
                      default="travel.yaml",
                      help="""Graph yaml file which should look like:
                            'place':
                                - 'other_place': cost
                            """)

    parser.add_option("-v", "--verbose", dest="verbose", action="count",
                      default=0, help="")

    parser.set_usage("Usage: [options] DEST DEST [DEST..]")

    opts, args = parser.parse_args()

    # Configure logging
    logging_levels = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
    level = logging_levels[opts.verbose if opts.verbose < 3 else 2]
    logging.basicConfig(level=level, format=_LOGGING_FMT_)

    return opts, args


def main():
    opts, args = parse_opts()

    total = 0.0
    g = Graph(args.pop(0))

    while len(args) > 1:
        print args[0], args[1]
        cost, path = g.min_cost(args[0], args[1])
        total += cost
        print cost, path
        args.pop(0)

    print "total {0}".format(total)

if __name__ == "__main__":
    main()
