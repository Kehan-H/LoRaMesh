#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import random
import csv

import network as nw
import protocol as pr

#
# "main" program
#

# variables
N = 20 # maximum number of hops
D = 500 # end2end distance
relay_only = 1

# simulation settings
simtime = 5*1000*60*60
random.seed(15)

# network settings

nw.SIGMA = 11.25

nw.PTX = 12
nw.SF = 7
nw.CR = 4
nw.BW = 125
nw.FREQ = 900000000
nw.TTL = 20

# protocol settings
nw.EXP = 1
pr.n0 = 2
pr.RM1 = 5
pr.RM2 = 10
pr.HL = 5
pr.avgGenTime = 1000*10

pr.rts = False

def run_exp(n):
    nw.nodes = []
    nw.env = nw.simpy.Environment()

    # base station initialization
    gw = nw.myNode(0, 0, 0)
    nw.nodes.append(gw)

    # end nodes initialization
    for i in range(1, n+1):
        node = nw.myNode(i, i*D/n, 0)
        # set routing table
        node.rt.destSet.add(0)
        node.rt.nextDict[0] = i-1
        node.rt.metricDict = i # hops
        node.rt.seqDict = 0
        nw.nodes.append(node)

    # run nodes
    for i in range(0,len(nw.nodes)):
        nw.env.process(nw.transceiver(nw.env,nw.nodes[i]))
        if (not relay_only) and i > 0:
            nw.env.process(nw.generator(nw.env,nw.nodes[i]))
    if relay_only:
        nw.env.process(nw.generator(nw.env,nw.nodes[n]))      
    nw.env.run(until=simtime) # start simulation
    return nw.nodes

# main
with open('linear.csv', 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(["dist", "hops", "pdr", "ar", "cr", "mr", "energy"])
    for hops in range(1, N+1):
        nodes = run_exp(hops)
        node = nodes[-1]
        pdr = node.arr/node.pkts
        ar = node.atte/node.pkts
        cr = node.coll/(node.pkts-node.atte)
        mr = node.miss/(node.pkts-node.atte)
        writer.writerow([node.x, hops, pdr, ar, cr, mr, node.energy])






# energy = sum(node.packet.airtime * TX[int(node.packet.txpow)+2] * V * node.sent for node in nodes) / 1e6
# sent = sum(n.sent for n in nodes)
# V = 3.0     # voltage XXX
# # mA = 90    # current draw for TX = 17 dBm
#       105, 115, 125]                                       # PA_BOOST/PA1+PA2: 18..20
#       82, 85, 90,                                          # PA_BOOST/PA1: 15..17
#       24, 24, 24, 25, 25, 25, 25, 26, 31, 32, 34, 35, 44,  # PA_BOOST/PA1: 2..14
# TX = [22, 22, 22, 23,                                      # RFO/PA0: -2..1
# # Transmit consumption in mA from -2 to +17 dBm
# # compute energy