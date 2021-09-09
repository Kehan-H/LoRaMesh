#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import random
import numpy as np

import network as nw
import protocol as pr
import reporting as rp

#
# "main" program
#

# simulation settings
simtime = 10*1000*60*60
random.seed(15)

# network settings

nw.SIGMA = 11.25

nw.PTX = 12
nw.SF = 7
nw.CR = 4
nw.BW = 125
nw.FREQ = 900000000
nw.TTL = 10

# protocol settings
pr.n0 = 5
pr.RM1 = 10
pr.RM2 = 20
pr.QTH = 5*60*1000
pr.HL = 5

pr.rts = False


def run_exp(EXP):
    nw.EXP = EXP

    nw.nodes = []
    nw.env = nw.simpy.Environment()

    # base station initialization
    locsB = np.array([397.188492418693,226.186250701973])
    gw = nw.myNode(0,locsB[0],locsB[1])
    gw.genPacket(0,25,1)
    gw.genPacket(0,25,1)
    nw.nodes.append(gw)

    # end nodes initialization
    locsN = np.loadtxt('600x800.csv',delimiter=',')
    for i in range(0,locsN.shape[0]):
        node = nw.myNode(i+1,locsN[i,0],locsN[i,1])
        nw.nodes.append(node)

    # run nodes
    nw.env.process(nw.transceiver(nw.env,nw.nodes[0]))
    for i in range(1,len(nw.nodes)):
        nw.env.process(nw.transceiver(nw.env,nw.nodes[i]))
        nw.env.process(nw.generator(nw.env,nw.nodes[i]))
    nw.env.run(until=simtime) # start simulation

# plot
rp.figure()
run_exp(4)
rp.hop_vs_pdr(nw.nodes,color='green')
run_exp(5)
rp.hop_vs_pdr(nw.nodes,color='red')
rp.show()

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