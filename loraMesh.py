#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import network as nw
import numpy as np

#
# "main" program
#

# simulation settings
simtime = 5*1000*60*60

# override default tx param
nw.PTX = 5
nw.SF = 7
nw.CR = 4
nw.BW = 125
nw.FREQ = 900000000
nw.TTL = 10

# network settings
nw.avgSendTime = 1000*60 # avg time between packets in ms
nw.slot = 1000
n0 = 10 # assumed no. of neighbour nodes
nw.p0 = (1-(1/n0))**(n0-1)

# base station initialization
locsB = np.array([397.188492418693,226.186250701973])
bs = nw.myNode(-1,locsB[0],locsB[1],10)
bs.genPacket(-1,25,1)
bs.genPacket(-1,25,1)
bs.genPacket(-1,25,1)
nw.nodes.append(bs)

# end nodes initialization
locsN = np.loadtxt('600x800.csv',delimiter=',')
for i in range(0,locsN.shape[0]):
    node = nw.myNode(i+1,locsN[i,0],locsN[i,1],1)
    nw.nodes.append(node)

# run nodes
for i in range(0,len(nw.nodes)):
    nw.env.process(nw.transceiver(nw.env,nw.nodes[i]))
    nw.env.process(nw.sensor(nw.env,nw.nodes[i]))
nw.env.run(until=simtime) # start simulation

nw.print_data(nw.nodes)
nw.display_graph(nw.nodes)

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