#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import random
import numpy as np

import network as nw
import protocol as pr
import reporting as rp

import csv


#
# "main" program
#

# simulation settings
simtime = 5*1000*60*60
random.seed(15)

# network settings
nw.EXP = 3

nw.PTX = 12
nw.SF = 7
nw.CR = 4
nw.BW = 125
nw.FREQ = 900000000
nw.TTL = 10

# protocol settings
pr.n0 = 5
pr.RM1 = 5
pr.RM2 = 10
pr.QTH = 5*60*1000
pr.HL = 5

pr.rts = False

def run_exp(sigma):
    nw.nodes = []
    nw.env = nw.simpy.Environment()

    nw.SIGMA = sigma

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
    return nw.nodes

# main
with open('exp3_sigma.csv', 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(["sigma", "avg_pdr"])
    for sigma in range(0, 10):
        nodes = run_exp(sigma)
        ss = 0
        nn = 0
        for i in range(1,len(nodes)):
            node = nodes[i]
            ss = ss +  node.arr/node.pkts
            nn = nn + 1
        writer.writerow([sigma, ss/nn])