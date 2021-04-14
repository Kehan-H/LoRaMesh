#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
 LoRaSim 0.2.1: simulate collisions in LoRa
 Copyright © 2016 Thiemo Voigt <thiemo@sics.se> and Martin Bor <m.bor@lancaster.ac.uk>

 This work is licensed under the Creative Commons Attribution 4.0
 International License. To view a copy of this license,
 visit http://creativecommons.org/licenses/by/4.0/.

 Do LoRa Low-Power Wide-Area Networks Scale? Martin Bor, Utz Roedig, Thiemo Voigt
 and Juan Alonso, MSWiM '16, http://dx.doi.org/10.1145/2988287.2989163

 $Date: 2017-05-12 19:16:16 +0100 (Fri, 12 May 2017) $
 $Revision: 334 $
"""

"""
 SYNOPSIS:
   ./loraDir.py <nodes> <avgsend> <experiment> <simtime> [collision]
 DESCRIPTION:
    nodes
        number of nodes to simulate
    avgsend
        average sending interval in milliseconds
    experiment
        experiment is an integer that determines with what radio settings the
        simulation is run. All nodes are configured with a fixed transmit power
        and a single transmit frequency, unless stated otherwise.
        0   use the settings with the the slowest datarate (SF12, BW125, CR4/8).
        1   similair to experiment 0, but use a random choice of 3 transmit
            frequencies.
        2   use the settings with the fastest data rate (SF6, BW500, CR4/5).
        3   optimise the setting per node based on the distance to the gateway.
        4   use the settings as defined in LoRaWAN (SF12, BW125, CR4/5).
        5   similair to experiment 3, but also optimises the transmit power.
    simtime
        total running time in milliseconds
    collision
        set to 1 to enable the full collision check, 0 to use a simplified check.
        With the simplified check, two messages collide when they arrive at the
        same time, on the same frequency and spreading factor. The full collision
        check considers the 'capture effect', whereby a collision of one or the
 OUTPUT
    The result of every simulation run will be appended to a file named expX.dat,
    whereby X is the experiment number. The file contains a space separated table
    of values for nodes, collisions, transmissions and total energy spent. The
    data file can be easily plotted using e.g. gnuplot.
"""

import simpy
import random
import numpy as np
import math
import sys
import matplotlib.pyplot as plt
import os
import networkx as nx

# turn on/off graphics
graphics = 0

# do the full collision check
full_collision = False

# experiments:
# 0: packet with longest airtime, aloha-style experiment
# 0: one with 3 frequencies, 1 with 1 frequency
# 2: with shortest packets, still aloha-style
# 3: with shortest possible packets depending on distance



# this is an array with measured values for sensitivity
# see paper, Table 3
sf7 = np.array([7,-126.5,-124.25,-120.75])
sf8 = np.array([8,-127.25,-126.75,-124.0])
sf9 = np.array([9,-131.25,-128.25,-127.5])
sf10 = np.array([10,-132.75,-130.25,-128.75])
sf11 = np.array([11,-134.5,-132.75,-128.75])
sf12 = np.array([12,-133.25,-132.25,-132.25])

#
# check for collisions at base station
# Note: called before a packet (or rather node) is inserted into the list
def checkcollision(packet,node):
    col = 0 # flag needed since there might be several collisions for packet
    if node.rxBuffer: # if there is a packet on air
        for i in range(len(node.rxBuffer)):
            other = node.rxBuffer[i][0]
            appearTime = node.rxBuffer[i][1]
            if not other == packet:
            #    print(">> node {} (sf:{} bw:{} freq:{:.6e})".format(
            #         other.id, other.packet.sf, other.packet.bw, other.packet.freq))
               # simple collision
                if frequencyCollision(packet,other) and sfCollision(packet,other) and timingCollision(packet,other,appearTime):
                    # check who collides in the power domain
                    c = powerCollision(packet,other,node) # return casualty packet(s)
                    # mark all the collided packets
                    # either this one, the other one, or both
                    for p in c:
                        if p == other:
                            node.rxBuffer[i][2] = 1 # set collide flag for entry in rxBuffer
                        if p == packet:
                            col = 1
                else:
                    pass # no timing collision, all fine
        return col
    return 0

#
# frequencyCollision, conditions
#
#        |f1-f2| <= 120 kHz if f1 or f2 has bw 500
#        |f1-f2| <= 60 kHz if f1 or f2 has bw 250
#        |f1-f2| <= 30 kHz if f1 or f2 has bw 125
def frequencyCollision(p1,p2):
    if (abs(p1.freq-p2.freq)<=120) and (p1.bw==500 or p2.freq==500):
        # print("frequency coll 500")
        return True
    elif (abs(p1.freq-p2.freq)<=60) and (p1.bw==250 or p2.freq==250):
        # print("frequency coll 250")
        return True
    elif (abs(p1.freq-p2.freq)<=30) and (p1.bw==125 or p2.freq==125):
        # print("frequency coll 125")
        return True
    # print("no frequency coll")
    return False

def sfCollision(p1,p2):
    if p1.sf == p2.sf:
        # print("collision sf node {} and node {}".format(p1.id, p2.id))
        # p2 may have been lost too, will be marked by other checks
        return True
    # print("no sf collision")
    return False

def powerCollision(p1,p2,node):
    powerThreshold = 6 # dB
    # print("pwr: node {0.nodeid} {0.rssi:3.2f} dBm node {1.nodeid} {1.rssi:3.2f} dBm; diff {2:3.2f} dBm".format(p1, p2, round(p1.rssi - p2.rssi,2)))
    rssi_p1 = p1.rssiAt(node)
    rssi_p2 = p2.rssiAt(node)
    if abs(rssi_p1 - rssi_p2) < powerThreshold:
        # print("collision pwr both node {} and node {}".format(p1.nodeid, p2.nodeid))
        # packets are too close to each other, both collide
        # return both packets as casualties
        return (p1,p2)
    elif rssi_p1 - rssi_p2 < powerThreshold:
        # p2 overpowered p1, return p1 as casualty
        # print("collision pwr node {} overpowered node {}".format(p2.nodeid, p1.nodeid))
        return (p1,)
    # print("p1 wins, p2 lost")
    # p2 was the weaker packet, return it as a casualty
    return (p2,)

def timingCollision(p1,p2,p2Time):
    # assuming p1 is the freshly arrived packet and this is the last check
    # we've already determined that p1 is a weak packet, so the only
    # way we can win is by being late enough (only the first n - 5 preamble symbols overlap)

    # assuming 8 preamble symbols
    Npream = 8

    # we can lose at most (Npream - 5) * Tsym of our preamble; symbol time Tsym = (2.0**sf)/bw
    Tpreamb = 2**p1.sf/(1.0*p1.bw) * (Npream - 5) # minimum preamble time

    # check whether p2 ends in p1's critical section
    p2_end = p2Time + p2.airtime # the time when p2 appeared + the airtime of p2
    p1_cs = env.now + Tpreamb
    # print("collision timing node {} ({},{},{}) node {} ({},{})".format(
    #     p1.nodeid, env.now - env.now, p1_cs - env.now, p1.airtime,
    #     p2.nodeid, p2.addTime - env.now, p2_end - env.now
    # ))
    if p1_cs < p2_end:
        # p1 collided with p2 and lost
        # print("not late enough")
        return True
    # print("saved by the preamble")
    return False

#
# this function creates a node
#
class myNode():
    def __init__(self,id,x,y,h,maxRx):
        self.id = id # negative - base station
        self.x = x
        self.y = y
        self.h = h
        self.maxRx = maxRx

        self.mode = 1 # 0-sleep; 1-rx; 2-tx
        self.modeStart = 0 # start time of the current mode
        self.sleepTime = 0
        self.rxTime = 0
        self.txTime = 0

        self.coll = 0 # no. of packets lost after collision
        self.sent = 0 # no. of sent packets include relayed ones
        self.pkts = 0 # no. of generated packets exclude relayed ones
        self.relay = 0
        self.received = 0

        # local mesh table
        # self.meshTable = localMeshTable(id, )

        self.rxBuffer = []
        self.txBuffer = [] # FIFO lists
        
        self.nbr = [] # neighbours
        self.rt = self.myRT() # routing table

    def recPacket(self,packet,col):
        self.rxBuffer.append((packet,env.now,col)) # log packet along with appear time and collision flag

    def relayPacket(self,packet):
        self.txBuffer.append(packet)
        self.removeRxPacket(packet)
        self.relay += 1
    
    def removeRxPacket(self,packet):
        for i in range(len(self.rxBuffer)):
            if self.rxBuffer[i][0] == packet:
                if not self.rxBuffer[i][2]:
                    self.coll += 1
                else:
                    self.received += 1
                self.rxBuffer[i].pop(i)
                break

    # generate packet
    def genPacket(self,pktNum,dest,sf,cr,bw,txpow,plen,freq):
        self.txBuffer.append(myPacket(self.pkts,self.id,dest,sf,cr,bw,txpow,plen,freq))
        self.pkts += 1

    # change status flag and add time of the last status
    def modeTo(self,mode):
        pastTime = env.now - self.modeStart
        if self.mode == 0:
            self.sleepTime += pastTime
        elif self.mode == 1:
            self.rxTime += pastTime
        elif self.mode == 2:
            self.txTime += pastTime
            self.sent += 1
        self.mode = mode
        self.modeStart = 0

    #
    # this function creates a routing table (associated with a node)
    #
    class myRT():
        def __init__(self):
            self.destList = []
            self.nextDict = {}
            self.metricDict = {} # hops
            self.seqDict = {}
        
        def addEntry(self,dest,nxt,metric):
            if dest not in self.destList:
                self.destList.append(dest)
                self.nextDict[dest] = nxt
                self.metricDict[dest] = metric
                self.seqDict[dest] = 0
        
        def updateSeq(self,dest,seq):
            self.seqDict[dest] = seq

#
# this function creates a packet
# it also sets all parameters
#
class myPacket():
    def __init__(self,pktNum,src,dest,sf,cr,bw,txpow,plen,freq):
        global gamma # path loss exponent
        global d0 # ref. distance in m
        global var # variance due to shadowing
        global Lpld0 # mean path loss at d0
        global GL # combined gain
        
        self.pktNum = pktNum
        self.src = src
        self.dest = dest
        self.sf = sf
        self.cr = cr
        self.bw = bw
        self.txpow = txpow
        self.plen = plen
        self.freq = freq

        # self.ttl = 10 # time to live (hops)

        # computes the airtime of a packet according to LoraDesignGuide_STD.pdf
        H = 1        # implicit header disabled (H=0) or not (H=1)
        DE = 0       # low data rate optimization enabled (=1) or not (=0)
        Npream = 8   # number of preamble symbol (12.25 from Utz paper)
        Tsym = (2.0**sf)/bw # symbol time
        Tpream = (Npream + 4.25)*Tsym
        payloadSymbNB = 8 + max(math.ceil((8.0*plen-4.0*sf+28+16-20*H)/(4.0*(sf-2*DE)))*(cr+4),0)
        Tpayload = payloadSymbNB * Tsym
        self.Tsym = Tsym
        self.airtime = Tpream + Tpayload

    # compute rssi at rx node
    def rssiAt(self,node): # TODO: change to Okumura-Hata Model
        # log-shadow
        distance = 0 # TODO: calculate dist
        Lpl = Lpld0 + 10*gamma*math.log10(distance/d0) + random.normalvariate(0,math.sqrt(var))     
        return self.txpow - GL - Lpl

#
# discrete event loop in flooding phase, runs for each tx node
# DSDV + p-persistent CSMA/CA
#
def flood(env,txNode):
    global nodes
    env.timeout(random.randint(0,slot)) # asynchronous nodes at start
    while True:
        # to receive
        if txNode.mode == 1:
            # carrier sense
            sense = bool(txNode.rxBuffer)
            if (not sense) and txNode.txBuffer:
                if (random.random() < p0): # transmit in the next time slot with p0 possibility
                    txNode.modeTo(2) # mode to tx
                else:
                    yield env.timeout(slot)
            # channel busy or has nothing to send
            else:
                yield env.timeout(10)
        # to transmit
        elif txNode.mode == 2:
            # trasmit packet
            txNode.sent += 1
            packet = txNode.txBuffer.pop(1)
            sensitivity = sensi[packet.sf - 7, [125,250,500].index(packet.bw) + 1]

            # receive packet
            for i in range(len(nodes)):
                rxNode = nodes[i]
                if rxNode.mode != 1: # receiver not in receive mode
                    continue
                elif (txNode.id != rxNode.id) and (packet.rssiAt(rxNode) > sensitivity): # rssi good at receiver
                    # adding packet if no collision
                    if (checkcollision(packet,nodes[i]) == 1):
                        nodes[i].recPacket(packet,1)
                    else:
                        nodes[i].recPacket(packet,0)
                    nodes[i].recPacket(packet,) # log a packet once partially arriving at rxNode
            yield env.timeout(packet.airtime) # airtime
            # complete packet has been received by rx node; can remove it
            for i in range(len(nodes)):
                nodes[i].relayPacket(packet)
            
            txNode.modeTo(1)

        # to sleep
        else:
            pass
            


#
# "main" program
#

# get arguments
# if len(sys.argv) >= 5:
#     nrNodes = int(sys.argv[1])
#     avgSendTime = int(sys.argv[2])  # avg time between packets in ms
#     experiment = int(sys.argv[3])
#     simtime = int(sys.argv[4])
#     if len(sys.argv) > 5:
#         full_collision = bool(int(sys.argv[5]))
#     print("Nodes: {}".format(nrNodes))
#     print("AvgSendTime (exp. distributed): {}".format(avgSendTime))
#     print("Experiment: {}".format(experiment))
#     print("Simtime: {}".format(simtime))
#     print("Full Collision: " + full_collision)
# else:
#     print("usage: ./loraDir <nodes> <avgsend> <experiment> <simtime> [collision]")
#     print("experiment 0 and 1 use 1 frequency only")
#     exit(-1)
nrNodes = 100
avgSendTime = 1000*60*2 # avg time between packets in ms
experiment = 6
simtime = 1000*60*60*24
full_collision = True
timeframe = 2000 # synced time frame (ms)
slot = 100
n0 = 5 # assumed no. of neighbour nodes
p0 = (1-(1/n0))**(n0-1)

# global stuff
#Rnd = random.seed(12345)
nodes = []
packetsAtBS = []
env = simpy.Environment()

# max distance: 300m in city, 3000 m outside (5 km Utz experiment)
# also more unit-disc like according to Utz
bsId = 1
nrReceived = 0 # no. of packets successfully received
nrLost = 0 # no. of packets fail to arrive the destination (sensi or collision)

Ptx = 14 # transmitted power
gamma = 2.08 # path loss exponent
d0 = 40.0 # ref. distance in m
var = 0 # power variance; ignored for now
Lpld0 = 127.41 # mean path loss at d0
GL = 0 # combined gain

sensi = np.array([sf7,sf8,sf9,sf10,sf11,sf12])
if experiment in [0,1,4]:
    minsensi = sensi[5,2]  # 5th row is SF12, 2nd column is BW125
elif experiment == 2:
    minsensi = -112.0   # no experiments, so value from datasheet
elif experiment in [3,5]:
    minsensi = np.amin(sensi) ## Experiment 3 can use any setting, so take minimum
elif experiment == 6:
    minsensi = sensi[0,2] # 0th row is SF7, 2nd column is BW125

# TODO: base station placement


# prepare graphics and add sink
if (graphics == 1):
    plt.ion()
    plt.figure()
    ax = plt.gcf().gca()
    # XXX should be base station position
    ax.add_artist(plt.Circle((bsx, bsy), 3, fill=True, color='green'))
    ax.add_artist(plt.Circle((bsx, bsy), maxDist, fill=False, color='green'))

# TODO: generate spatial distribution using Poisson Hard-Core Process

# initialise nodes
for i in range(0,nrNodes):
    node = myNode(0,0,0,0,1) # TODO: define nodes wrt distribution
    nodes.append(node)

# TODO: get mesh table by flooding
env.process(flood(env,bs))
env.run(until=simtime) # start simulation
## flooding done

## Main Simulation
for i in range(0,nrNodes):
    node = myNode(0,0,0,0,1) # TODO: define nodes wrt distribution
    nodes.append(node)

    env.process(transmit(env,node))

#prepare show
G = nx.Graph()
G.add_nodes_from(nodes)

# start simulation
env.run(until=simtime)

# print stats and save into file
# print("nrCollisions {}".format(nrCollisions))

# compute energy
# Transmit consumption in mA from -2 to +17 dBm
TX = [22, 22, 22, 23,                                      # RFO/PA0: -2..1
      24, 24, 24, 25, 25, 25, 25, 26, 31, 32, 34, 35, 44,  # PA_BOOST/PA1: 2..14
      82, 85, 90,                                          # PA_BOOST/PA1: 15..17
      105, 115, 125]                                       # PA_BOOST/PA1+PA2: 18..20
# mA = 90    # current draw for TX = 17 dBm
V = 3.0     # voltage XXX
sent = sum(n.sent for n in nodes)
energy = sum(node.packet.airtime * TX[int(node.packet.txpow)+2] * V * node.sent for node in nodes) / 1e6

# print("energy (in J): {}".format(energy))
# print("sent packets: {}".format(sent))
# print("collisions: {}".format(nrCollisions))
# print("received packets: {}".format(nrReceived))
# print("processed packets: {}".format(nrProcessed))
# print("lost packets: {}".format(nrLost))

# data extraction rate
der = (sent-nrCollisions)/float(sent)
print("DER: {}".format(der))
der = (nrReceived)/float(sent)
print("DER method 2: {}".format(der))

# this can be done to keep graphics visible
if (graphics == 1):
    raw_input('Press Enter to continue ...')
