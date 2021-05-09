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

# turn on/off graphics
graphics = 0

# experiments:
# 0: packet with longest airtime, aloha-style experiment
# 0: one with 3 frequencies, 1 with 1 frequency
# 2: with shortest packets, still aloha-style
# 3: with shortest possible packets depending on distance

#
# check for collisions at base station
# Note: called before a packet (or rather node) is inserted into the list
def checkcollision(packet,rxNode):
    col = 0 # flag needed since there might be several collisions for packet
    if rxNode.rxBuffer: # if there is a packet on air
        for i in range(len(rxNode.rxBuffer)):
            other = rxNode.rxBuffer[i][0]
            appearTime = rxNode.rxBuffer[i][1]
            if other != packet:
                # simple collision
                if frequencyCollision(packet,other) and sfCollision(packet,other) and timingCollision(packet,other,appearTime):
                    # check who collides in the power domain
                    c = powerCollision(packet,other,rxNode) # return casualty packet(s)
                    # mark all the collided packets
                    # either this one, the other one, or both
                    for p in c:
                        if p == other:
                            rxNode.rxBuffer[i][2] = 1 # set collide flag for entry in rxBuffer
                            # raise ValueError('Collision happened for pkt from ' + str(rxNode.rxBuffer[i][0].txNode.id) + ' and ' + str(packet.txNode.id) + ' to ' + str(rxNode.id))
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

def powerCollision(p1,p2,rxNode):
    powerThreshold = 6 # dB
    # print("pwr: node {0.nodeid} {0.rssi:3.2f} dBm node {1.nodeid} {1.rssi:3.2f} dBm; diff {2:3.2f} dBm".format(p1, p2, round(p1.rssi - p2.rssi,2)))
    rssi_p1 = p1.rssiAt(rxNode)
    rssi_p2 = p2.rssiAt(rxNode)
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
    p2_end = p2Time + p2.airtime() # the time when p2 appeared + the airtime of p2
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
    def __init__(self,id,x,y,h):
        self.id = id # negative for base station
        self.x = x
        self.y = y
        self.h = h

        self.mode = 1 # 0-sleep; 1-rx; 2-tx
        self.modeStart = 0 # start time of the current mode
        self.sleepTime = 0
        self.rxTime = 0
        self.txTime = 0

        self.coll = 0 # packets lost due to collision
        self.miss = 0 # packets lost because rx node is not in rx mode; may overlap with the collision
        self.sent = 0 # sent packets include relayed ones
        self.relay = 0
        self.rec = 0 # packets successfully received without collision or miss

        self.pkts = 0 # generated packets exclude relayed ones
        self.arr = 0 # generated packets arriving at destination

        # local mesh table
        # self.meshTable = localMeshTable(id, )

        # FIFO lists
        self.rxBuffer = [] # list of tuples (packet,appear time, collision flag)
        self.txBuffer = []
        
        self.nbr = set() # neighbours
        self.rt = myRT(self) # routing table
    
    # remove packet from rxBuffer; return received or not
    def checkDelivery(self,packet,appearTime):
        for i in range(len(self.rxBuffer)):
            other = self.rxBuffer[i]
            if other[0].txNode == packet.txNode and other[1] == appearTime:
                col = self.rxBuffer[i][2]
                mis = self.rxBuffer[i][3]
                rec = not (col or mis)
                
                self.coll += col
                self.miss += mis
                self.rec += rec

                self.rxBuffer.pop(i)
                return rec # break loop, remove only one
        return False
                  
    # proccess packet; deep copy packet to rxBuffer
    def relayPacket(self,packet):
        copy = myPacket(packet.sn,packet.src,packet.dest,self,packet.plen,packet.tp)
        copy.ttl = packet.ttl - 1
        self.txBuffer.append(copy)
        self.relay += 1

    # generate packet
    def genPacket(self,dest,plen,tp):
        self.txBuffer.append(myPacket(self.pkts,self.id,dest,self,plen,tp))
        self.pkts += 1

    # add or edit entry; return update or not
    def updateRT(self,dest,nxt,metric,seq):
        rt = self.rt
        if dest in rt.destSet:
            if seq > rt.seqDict[dest]:
                pass
            elif seq == rt.seqDict[dest] and metric < rt.metricDict[dest]:
                pass
            else:
                return False
        rt.destSet.add(dest)
        rt.nextDict[dest] = nxt
        rt.metricDict[dest] = metric
        rt.seqDict[dest] = seq
        return True

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
        self.modeStart = env.now

    def pathTo(self,dest):
        global nodes
        if self.id == dest:
            return ''
        elif dest not in self.rt.destSet:
            return 'no route'
        else:
            for node in nodes:
                if node.id == self.rt.nextDict[dest]:
                    nextNode = node
            return ' -> ' + str(self.rt.nextDict[dest]) + nextNode.pathTo(dest)

#
# this function creates a routing table (associated with a node)
#
class myRT():
    def __init__(self,node):
        self.destSet ={node.id}
        self.nextDict = {node.id:node.id}
        self.metricDict = {node.id:0} # hops
        self.seqDict = {node.id:0}
    
    # add or edit entry
    def updateEntry(self,dest,nxt,metric,seq):
        self.destSet.add(dest)
        self.nextDict[dest] = nxt
        self.metricDict[dest] = metric
        self.seqDict[dest] = seq

#
# this function creates a packet
# it also sets all parameters
#
class myPacket():
    def __init__(self,sn,src,dest,txNode,plen,tp):
        self.sn = sn # serial number of packet at src node
        self.src = src # src id
        self.dest = dest # dest id
        self.txNode = txNode
        self.plen = plen
        
        # packet type flag:
        # 0 - sensor data
        # 1 - routing beacon
        # 2 - 
        self.tp = tp

        # default network settings
        self.txpow = 14
        self.sf = 7
        self.cr = 4
        self.bw = 125
        self.freq = 900000000

        self.ttl = 15 # time to live (hops)

    def airtime(self):
        sf = self.sf
        cr = self.cr
        bw = self.bw
        plen = self.plen
        # computes the airtime of a packet according to LoraDesignGuide_STD.pdf
        H = 1        # implicit header disabled (H=0) or not (H=1)
        DE = 0       # low data rate optimization enabled (=1) or not (=0)
        Npream = 8   # number of preamble symbol (12.25 from Utz paper)
        Tsym = (2.0**sf)/bw # symbol time
        Tpream = (Npream + 4.25)*Tsym
        payloadSymbNB = 8 + max(math.ceil((8.0*plen-4.0*sf+28+16-20*H)/(4.0*(sf-2*DE)))*(cr+4),0)
        Tpayload = payloadSymbNB * Tsym
        return Tpream + Tpayload

    # compute rssi at rx node
    def rssiAt(self,rxNode): # TODO: change to Okumura-Hata Model
        gamma = 2.08 # path loss exponent
        d0 = 40.0 # ref. distance in m
        var = 0 # power variance; ignored for now
        Lpld0 = 127.41 # mean path loss at d0
        GL = 0 # combined gain
        # log-shadow
        distance = math.sqrt((self.txNode.x-rxNode.x)**2+(self.txNode.y - rxNode.y)**2) # TODO: calculate dist
        Lpl = Lpld0 + 10*gamma*math.log10(distance/d0) + random.normalvariate(0,math.sqrt(var))     
        return self.txpow - GL - Lpl

#
# A finite state machine running on every node 
# DSDV + p-persistent CSMA/CA
#
def transceiver(env,txNode):
    global nodes
    env.timeout(random.randint(0,slot))
    while True:
        # to receive
        if txNode.mode == 1:
            # carrier sense
            if (not txNode.rxBuffer) and txNode.txBuffer:
                # transmit with p0 possibility
                if (random.random() <= p0):
                    txNode.modeTo(2) # mode to tx
                else:
                    # >p0, wait till next slot
                    yield env.timeout(slot)
            else:
                # refresh when channel busy or has nothing to send
                yield env.timeout(100)
        # to transmit
        elif txNode.mode == 2:
            # trasmit packet
            packet = txNode.txBuffer.pop(0)
            if packet.tp == 0 and (packet.dest not in txNode.rt.destSet):
                txNode.txBuffer.append(packet)
                yield env.timeout(10)
                txNode.modeTo(1)
                continue
            sensitivity = sensi[packet.sf - 7, [125,250,500].index(packet.bw) + 1]
            # receive packet
            appearTime = env.now
            for i in range(len(nodes)):
                if txNode.id != nodes[i].id and packet.rssiAt(nodes[i]) > sensitivity: # rssi good at receiver, add packet to rxBuffer
                    nodes[i].nbr.add(txNode)
                    mis = (nodes[i].mode != 1) # receiver not in rx mode
                    col = checkcollision(packet,nodes[i]) # side effect: also change collision flags of other packets
                    nodes[i].rxBuffer.append([packet,appearTime,col,mis]) # log packet along with appear time and flags
            yield env.timeout(packet.airtime()) # airtime
            # complete packet has been processed by rx node; can remove it
            for i in range(len(nodes)):
                if nodes[i].checkDelivery(packet,appearTime): # side effect: packet removed from rxBuffer
                    if packet.tp == 0: # sensor data
                        # arrive at dest
                        if packet.dest == nodes[i].id:
                            nodes[packet.src].arr += 1
                            if nodes[packet.src].arr > nodes[packet.src].pkts:
                                raise ValueError(str(packet.src) + ' more arrived than generated.')
                        # arrive at next but not dest
                        elif txNode.rt.nextDict[packet.dest] == nodes[i].id and packet.ttl > 0:
                            nodes[i].relayPacket(packet)
                        else:
                            pass
                    elif packet.tp == 1: # routing beacon
                        # DSDV update routing table
                        update = 0 # flag needed because there can be multiple entries to update
                        for dest in txNode.rt.destSet:
                            # return update or not; side effect: update entry
                            update = nodes[i].updateRT(dest,txNode.id,txNode.rt.metricDict[dest]+1,txNode.rt.seqDict[dest])
                        if update and packet.ttl > 0:       
                            nodes[i].relayPacket(packet)
                            nodes[i].rt.seqDict[nodes[i].id] += 2
                    else:
                        pass
            txNode.modeTo(1)
        # to sleep
        else:
            pass

def sensor(env,node):
    while True:
        yield env.timeout(avgSendTime)
        node.genPacket(-1,40,0)
    

#
# "main" program
#

experiment = 6
avgSendTime = 2000*60 # avg time between packets in ms
simtime = 1*1000*60*60
timeframe = 2000 # synced time frame (ms)
slot = 1000
n0 = 10 # assumed no. of neighbour nodes
p0 = (1-(1/n0))**(n0-1)

# global stuff
#Rnd = random.seed(12345)
nodes = []
env = simpy.Environment()

# max distance: 300m in city, 3000 m outside (5 km Utz experiment)
# also more unit-disc like according to Utz
bsId = 1
nrReceived = 0 # no. of packets successfully received
nrLost = 0 # no. of packets fail to arrive the destination (sensi or collision)

Ptx = 14 # transmitted power


# this is an array with measured values for sensitivity
# see paper, Table 3
sf7 = np.array([7,-126.5,-124.25,-120.75])
sf8 = np.array([8,-127.25,-126.75,-124.0])
sf9 = np.array([9,-131.25,-128.25,-127.5])
sf10 = np.array([10,-132.75,-130.25,-128.75])
sf11 = np.array([11,-134.5,-132.75,-128.75])
sf12 = np.array([12,-133.25,-132.25,-132.25])

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
bs = myNode(-1,0,0,10)
bs.genPacket(-1,40,1)
nodes.append(bs)

# prepare graphics and add sink

# TODO: generate spatial distribution using Poisson Hard-Core Process
locs = np.loadtxt('75.csv',delimiter=',')
for i in range(1,locs.shape[1]+1):
    nodes.append(myNode(i,locs[0,i-1],locs[1,i-1],1))

# run nodes
for i in range(0,len(nodes)):
    env.process(transceiver(env,nodes[i]))
    env.process(sensor(env,nodes[i]))
env.run(until=simtime) # start simulation

# prepare show


# output
for node in nodes:
    print(str(node.id) + ':' + node.pathTo(-1))
    print('DER = ' + str(node.arr/node.pkts))
    print('\n')

    # prepare show
    plt.scatter(node.x, node.y)
    plt.annotate(node.id,(node.x, node.y))

    for n in node.nbr:
        plt.plot([node.x,n.x],[node.y,n.y])

plt.show()

# # print stats and save into file
# # print("nrCollisions {}".format(nrCollisions))

# # compute energy
# # Transmit consumption in mA from -2 to +17 dBm
# TX = [22, 22, 22, 23,                                      # RFO/PA0: -2..1
#       24, 24, 24, 25, 25, 25, 25, 26, 31, 32, 34, 35, 44,  # PA_BOOST/PA1: 2..14
#       82, 85, 90,                                          # PA_BOOST/PA1: 15..17
#       105, 115, 125]                                       # PA_BOOST/PA1+PA2: 18..20
# # mA = 90    # current draw for TX = 17 dBm
# V = 3.0     # voltage XXX
# sent = sum(n.sent for n in nodes)
# energy = sum(node.packet.airtime * TX[int(node.packet.txpow)+2] * V * node.sent for node in nodes) / 1e6

# # print("energy (in J): {}".format(energy))
# # print("sent packets: {}".format(sent))
# # print("collisions: {}".format(nrCollisions))
# # print("received packets: {}".format(nrReceived))
# # print("processed packets: {}".format(nrProcessed))
# # print("lost packets: {}".format(nrLost))

# # data extraction rate
# der = (sent-nrCollisions)/float(sent)
# print("DER: {}".format(der))
# der = (nrReceived)/float(sent)
# print("DER method 2: {}".format(der))

# # this can be done to keep graphics visible
# if (graphics == 1):
#     raw_input('Press Enter to continue ...')