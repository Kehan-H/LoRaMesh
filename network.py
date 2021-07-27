#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import simpy
import random
import numpy as np
import math
import matplotlib.pyplot as plt

import protocol as pr

#
# CONTANTS
#

# default tx param
PTX = 8
SF = 7
CR = 4
BW = 125
FREQ = 900000000
TTL = 15

# network settings
avgSendTime = 1000*60 # avg time between packets in ms
slot = 1000
n0 = 10 # assumed no. of neighbour nodes
p0 = (1-(1/n0))**(n0-1)

# this is an array with measured values for sensitivity
# see paper, Table 3
sf7 = np.array([7,-126.5,-124.25,-120.75])
sf8 = np.array([8,-127.25,-126.75,-124.0])
sf9 = np.array([9,-131.25,-128.25,-127.5])
sf10 = np.array([10,-132.75,-130.25,-128.75])
sf11 = np.array([11,-134.5,-132.75,-128.75])
sf12 = np.array([12,-133.25,-132.25,-132.25])

sensi = np.array([sf7,sf8,sf9,sf10,sf11,sf12])

#
# global stuff
#

nodes = []
env = simpy.Environment()

#
# network structures
#

# check for collisions at rx node
# Note: called before a packet (or rather node) is inserted into the list
def checkcollision(packet,rxNode):
    col = 0 # flag needed since there might be several collisions for packet
    if rxNode.rxBuffer: # if there is a packet on air
        for i in range(len(rxNode.rxBuffer)):
            other = rxNode.rxBuffer[i][0]
            if other != packet:
                # simple collision
                if frequencyCollision(packet,other) and sfCollision(packet,other) and timingCollision(packet,other):
                    # check who collides in the power domain
                    c = powerCollision(packet,other,rxNode) # return casualty packet(s)
                    # mark all the collided packets
                    # either this one, the other one, or both
                    for p in c:
                        if p == other:
                            rxNode.rxBuffer[i][1] = 1 # set collide flag for entry in rxBuffer
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

def timingCollision(p1,p2):
    # assuming p1 is the freshly arrived packet and this is the last check
    # we've already determined that p1 is a weak packet, so the only
    # way we can win is by being late enough (only the first n - 5 preamble symbols overlap)

    # assuming 8 preamble symbols
    Npream = 8

    # we can lose at most (Npream - 5) * Tsym of our preamble; symbol time Tsym = (2.0**sf)/bw
    Tpreamb = 2**p1.sf/(1.0*p1.bw) * (Npream - 5) # minimum preamble time

    # check whether p2 ends in p1's critical section
    p2_end = p2.appearTime + p2.airtime() # the time when p2 appeared + the airtime of p2
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
        self.h = h # current not used

        self.mode = 1 # 0-sleep; 1-rx; 2-tx
        self.modeStart = 0 # start time of the current mode
        self.sleepTime = 0
        self.rxTime = 0
        self.txTime = 0

        # statistics
        self.coll = 0 # packets lost due to collision
        self.miss = 0 # packets lost because rx node is not in rx mode; may overlap with the collision
        self.fade = 0 # packets lost due to fading, independent

        self.relay = 0
        self.pkts = 0 # packets generated, exclude relayed ones
        self.arr = 0 # packets arrive at destination

        # FIFO lists
        self.rxBuffer = [] # list of tuples in the form (packet,collision flag,miss flag)
        self.txBuffer = []
        
        self.nbr = set() # neighbours
        self.rt = self.myRT(self) # routing table
    
    # remove packet from rxBuffer; return [col,mis]
    def checkDelivery(self,packet):
        for i in range(len(self.rxBuffer)):
            other = self.rxBuffer[i]
            if other[0] == packet:
                entry = self.rxBuffer.pop(i)
                return entry[1:] # break loop, remove only one
        return []
                  
    # proccess packet; deep copy packet to rxBuffer
    def relayPacket(self,packet):
        copy = myPacket(packet.sn,packet.src,packet.dest,self,packet.plen,packet.type)
        copy.ttl = packet.ttl - 1
        self.txBuffer.append(copy)
        self.relay += 1

    # generate packet
    def genPacket(self,dest,plen,type):
        packet = myPacket(self.pkts,self,dest,self,plen,type)
        self.txBuffer.append(packet)
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

    # change mode flag and update time of the last status
    def modeTo(self,mode):
        pastTime = env.now - self.modeStart
        if self.mode == 0:
            self.sleepTime += pastTime
        elif self.mode == 1:
            self.rxTime += pastTime
        elif self.mode == 2:
            self.txTime += pastTime
            for entry in self.rxBuffer:
                entry[2] = 1
        else:
            raise ValueError('Mode not defined for Node ' + str(self.id))
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

    # this function creates a routing table (associated with a node)
    class myRT():
        def __init__(self,node):
            self.destSet ={node.id}
            self.nextDict = {node.id:node.id}
            self.metricDict = {node.id:0} # hops
            self.seqDict = {node.id:0}

#
# this function creates a packet
# it also sets all parameters
#
class myPacket():
    def __init__(self,sn,src,dest,txNode,plen,type):
        self.sn = sn # serial number of packet at src node
        self.src = src # src node
        self.dest = dest # dest id
        self.txNode = txNode
        self.plen = plen
        
        # packet type identifier:
        # 0 - sensor data
        # 1 - routing beacon
        # 2 - 
        self.type = type

        # default network settings
        self.txpow = PTX
        self.sf = SF
        self.cr = CR
        self.bw = BW
        self.freq = FREQ

        self.ttl = TTL # time to live (hops)

        self.appearTime = None

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
    def rssiAt(self,rxNode):
        gamma = 2.03 # path loss exponent
        sigma = 7.21
        d0 = 1.0 # ref. distance in m
        PLd0 = 94.40 # mean path loss at d0
        GL = 0 # combined gain
        # log-shadow
        dist = math.sqrt((self.txNode.x-rxNode.x)**2+(self.txNode.y - rxNode.y)**2)
        PL = PLd0 + 10*gamma*math.log10(dist/d0) + random.normalvariate(0,sigma)     
        return self.txpow + GL - PL

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
            packet.appearTime = env.now
            # hold packet when no route
            if packet.type == 0 and (packet.dest not in txNode.rt.destSet):
                txNode.txBuffer.append(packet)
                yield env.timeout(10)
                txNode.modeTo(1)
                continue
            sensitivity = sensi[packet.sf - 7, [125,250,500].index(packet.bw) + 1]
            # receive packet
            for i in range(len(nodes)):
                if txNode.id != nodes[i].id and packet.rssiAt(nodes[i]) > sensitivity: # rssi good at receiver, add packet to rxBuffer
                    col = checkcollision(packet,nodes[i]) # side effect: also change collision flags of other packets                    
                    mis = (nodes[i].mode != 1) # receiver not in rx mode
                    nodes[i].rxBuffer.append([packet,col,mis]) # log packet along with appear time and flags
            yield env.timeout(packet.airtime()) # airtime
            # complete packet has been processed by rx node; can remove it
            for i in range(len(nodes)):
                result = nodes[i].checkDelivery(packet) # side effect: packet removed from rxBuffer
                # rssi good and no col or mis
                if result and not any(result): 
                    # sensor data
                    if packet.type == 0:
                        # not supposed to receive, wasted
                        if txNode.rt.nextDict[packet.dest] != nodes[i].id:
                            pass
                        # arrive at next/dest
                        else:
                            if packet.dest == nodes[i].id:
                                packet.src.arr += 1
                                if packet.src.arr > packet.src.pkts:
                                    raise ValueError('Node ' + str(packet.src.id) + ' has more arrived than generated.')
                            elif packet.ttl > 0:
                                nodes[i].relayPacket(packet)
                            else:
                                pass
                    # routing beacon
                    elif packet.type == 1:
                        # DSDV update routing table
                        update = 0 # flag needed because there can be multiple entries to update
                        nodes[i].nbr.add(txNode)
                        for dest in txNode.rt.destSet:
                            # return update or not; side effect: update entry
                            update = nodes[i].updateRT(dest,txNode.id,txNode.rt.metricDict[dest]+1,txNode.rt.seqDict[dest])
                        if update and packet.ttl > 0:       
                            nodes[i].relayPacket(packet)
                            nodes[i].rt.seqDict[nodes[i].id] += 2
                    # reserved for other packet type
                    else:
                        pass
                # catch losing condition when node is critical
                elif txNode.rt.nextDict[packet.dest] == nodes[i].id:
                    try:
                        packet.src.coll += result[0]
                        packet.src.miss += result[1]
                    # error when result is empty
                    except:
                        packet.src.fade += 1
                # rssi bad (not found in rxBuffer) or coll or miss
                else:
                    pass
            txNode.modeTo(1)
        # to sleep
        else:
            pass

def sensor(env,node):
    while True:
        yield env.timeout(avgSendTime)
        node.genPacket(-1,25,0)

# print routes and DER
def print_data(nodes):
    for node in nodes:
        if node.id >= 0:
            print(str(node.id) + ':' + node.pathTo(-1))
            print('DER = ' + str(node.arr/node.pkts))
            print('Collision Rate = ' + str(node.coll/(node.pkts-node.fade)))
            print('Miss Rate = ' + str(node.miss/(node.pkts-node.fade)))
            print('Faded Rate = ' + str(node.fade/node.pkts))
            print('\n')

# prepare show
def display_graph(nodes):
    for node in nodes:
        for n in node.nbr:
            plt.plot([node.x,n.x],[node.y,n.y],'c-',zorder=0)
        plt.scatter(node.x,node.y,color='red',zorder=5)
        plt.annotate(node.id,(node.x, node.y),color='black',zorder=10)
    plt.show()