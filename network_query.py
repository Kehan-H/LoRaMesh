import simpy
import random
import numpy as np
import math

import catchloss as cl
import reporting as rp

#
# CONTANTS
#

# experiment no.
EXP = 0

# default tx param
PTX = 5
SF = 7
CR = 4
BW = 125
FREQ = 900000000
TTL = 4

# shadowing
SIGMA = 11.25

# real-time show
rts = False

# p-csma param
n0 = 5 # assumed no. of neighbour nodes
p0 = (1-(1/n0))**(n0-1)

# rssi margin to ensure reliable routing result
RM1 = 5
RM2 = 10

# time thresholds for query-based protocols
QTH = 5*60*1000 # no query
RTH = 1000 # no response
CTH = 5000 # no confirmation

# hop limit
HL = 5

# avg time between generated data packets in ms
avgGenTime = 1000*30

# default packet length
plenA = 10 # query/confirm/join
plenB = 15 # data
plenC = 20 # beacon

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
    rssi_p1 = p1.rssiAt[rxNode]
    rssi_p2 = p2.rssiAt[rxNode]
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
    def __init__(self,id,x,y):
        self.id = id # negative for base station
        self.x = x
        self.y = y

        self.mode = 1 # 0-sleep; 1-rx; 2-tx
        self.modeStart = 0 # start time of the current mode
        self.sleepTime = 0
        self.rxTime = 0
        self.txTime = 0

        # statistics
        self.coll = 0 # packets lost due to collision
        self.miss = 0 # packets lost because rx node is not in rx mode; may overlap with the collision
        self.atte = 0 # packets lost due to path loss, independent

        self.relay = 0
        self.pkts = 0 # data packets generated, exclude relayed ones
        self.arr = 0 # packets arrive at destination

        # FIFO lists
        self.rxBuffer = [] # list of tuples in the form (packet,collision flag,miss flag)
        self.txBuffer = []
        
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
        copy.passed.append(self.id)
        self.txBuffer.append(copy)
        self.relay += 1

    # generate packet
    def genPacket(self,dest,plen,type):
        packet = myPacket(self.pkts,self,dest,self,plen,type)
        packet.passed.append(self.id)
        self.txBuffer.append(packet)
        if type == 0:
            self.pkts += 1

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
                entry[2] = 1 # packets not fully received are missed
        else:
            raise ValueError('Mode not defined for Node ' + str(self.id))
        self.mode = mode
        self.modeStart = env.now

    # [next node, ... , destination node]
    def pathTo(self,dest):
        route = []
        if self.rt.parent == None:
            return route
        atNode = self
        counter = 0
        while atNode.id != 0:
            counter = counter + 1
            if counter > TTL:
                break
            for node in nodes:
                if node.id == atNode.rt.parent:
                    route.append(node)
                    atNode = node

        return route
    
    def getNbr(self):
        nbr = set()
        for other in nodes:
            if other.id == self.rt.parent:
                nbr.add(other)
        return nbr

    # this function creates a routing table (associated with a node)
    class myRT():
        def __init__(self,node):
            # history rssi grouped by node id
            # dictionary of FIFO lists; list structure [rssi0, rssi1, ... , rssin]
            self.rssiRec = {}

            # dsdv table
            self.destSet ={node.id}
            self.nextDict = {node.id:node.id}
            self.metricDict = {node.id:0} # hops
            self.seqDict = {node.id:0}
            
            # query-based table
            self.childs = set()
            self.resp = {} # child nodes responded or not
            self.tout = {} # child nodes timeout count
            # GW only
            self.qlst = [] # ids of nodes to query
            self.waiting = None # id of node being waiting for response
            # end devices only
            self.parent = None
            self.lrt = None # time of last received (query/beacon) from parent 
            self.joined = False
            self.hops = None
        
        # record new rssi value
        def newRssi(self,txid,rssi):
            if txid in self.rssiRec.keys():
                self.rssiRec[txid].append(rssi)
                # maximum size
                if len(self.rssiRec[txid]) > 25:
                    self.rssiRec[txid].pop(0)
            else:
                self.rssiRec[txid] = [rssi]

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
        # 0 - data
        # 1 - routing beacon
        # 2 - query
        # 3 - join request
        # 4 - confirm
        self.type = type

        # default RF settings
        self.txpow = PTX
        self.sf = SF
        self.cr = CR
        self.bw = BW
        self.freq = FREQ

        self.ttl = TTL # time to live (hops)

        self.appearTime = None
        self.rssiAt = {} # rssi at rx nodes
        self.passed = [] # passed nodes
    
    # channel estimation - compute rssi at rx nodes
    # call this function when packet is transmitted
    def chanEst(self,nodes):
        for rxNode in (node for node in nodes if node != self.txNode):
            gamma = 2.75 # path loss exponent
            d0 = 1 # ref. distance in m
            PLd0 = 74.85 # mean path loss at d0
            GL = 0 # combined gain
            # log-shadow
            dist = math.sqrt((self.txNode.x-rxNode.x)**2+(self.txNode.y - rxNode.y)**2)
            PL = PLd0 + 10*gamma*math.log10(dist/d0) + random.gauss(0,SIGMA)
            self.rssiAt[rxNode] = self.txpow + GL - PL

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

#
# A finite state machine running on every node 
#
def transceiver(env,txNode):
    global nodes
    while True:
        # to receive
        if txNode.mode == 1:
            nxMode = 1
            dt1 = 0
            dt2 = 0
            # GW
            if txNode.id == 0:
                # has child, generate query
                if txNode.rt.childs:
                    # queue is empty. can start a new round of query
                    if not txNode.rt.qlst:
                        txNode.rt.qlst = list(txNode.rt.childs)
                    # not waiting for response. can send the next query
                    elif txNode.rt.waiting == None:
                        id = txNode.rt.qlst.pop(0)
                        txNode.genPacket(id,plenA,2)
                        txNode.rt.waiting = id
                    else:
                        pass
                # no child, generate beacon
                else:
                    txNode.genPacket(0,plenC,1)
            # end devices
            elif txNode.id > 0:
                pass
            else:
                raise ValueError('undefined node id')

            # has packet to transmit
            if txNode.txBuffer:
                nxMode = 2
                # beacon
                if txNode.txBuffer[0].type == 1:
                    dt2 = 60*1000 # period
                # query
                elif txNode.txBuffer[0].type == 2:
                    yield env.process(wait_response(env,txNode)) # wait for response
                # data/confirm/request
                elif txNode.txBuffer[0].type in [0,3,4]:
                    pass
                else:
                    raise ValueError('undefined packet type')
            # nothing to transmit
            else:
                nxMode = 1
                dt1 = 200 # refresh
            
            txNode.modeTo(nxMode)
            yield env.timeout(dt1)
        # to transmit
        elif txNode.mode == 2:
            # transmit packet
            packet = txNode.txBuffer.pop(0)
            packet.appearTime = env.now
            packet.chanEst(nodes)
            sensitivity = sensi[packet.sf - 7, [125,250,500].index(packet.bw) + 1]
            ids = [i for i in range(len(nodes)) if i != txNode.id] 
            # receive packet
            for i in ids:
                if packet.rssiAt[nodes[i]] - sensitivity > 0: # rssi good at receiver, add packet to rxBuffer
                    col = checkcollision(packet,nodes[i]) # side effect: also change collision flags of other packets                    
                    mis = (nodes[i].mode != 1) # receiver not in rx mode
                    nodes[i].rxBuffer.append([packet,col,mis]) # log packet along with appear time and flags
            yield env.timeout(packet.airtime()) # airtime
            # complete packet has been processed by rx node; can remove it
            for i in ids:
                result = nodes[i].checkDelivery(packet) # side effect: packet removed from rxBuffer
                # rssi good and no col or mis
                if result and not any(result):
                    
                    
                    # GW
                    if nodes[i].id == 0:
                        # data
                        if packet.type == 0:
                            # arrive at dest
                            if txNode.rt.parent == 0 and nodes[i].rt.waiting == packet.src.id:
                                # update RT
                                nodes[i].rt.waiting = None
                                nodes[i].rt.resp[packet.src.id] = True
                                nodes[i].rt.tout[packet.src.id] = 0
                                # update statistics
                                packet.src.arr += 1
                                if packet.src.arr > packet.src.pkts:
                                    raise ValueError('Node ' + str(packet.src.id) + ' has more arrived than generated.')
                        # beacon/query/confirm/join request
                        else:
                            pass
                    # end devices
                    elif nodes[i].id > 0:
                        # not joined
                        if not nodes[i].rt.joined:
                            # waiting for confirmation
                            if nodes[i].rt.parent != None:
                                # implies this is a confirmation packet or a query
                                if packet.dest == nodes[i].id:
                                    nodes[i].rt.joined = True
                                    nodes[i].rt.lrt = env.now
                                    yield env.process(wait_query(env,nodes[i]))
                                    # query packet, directly reply data (implies confirmation is lost)
                                    if packet.type == 2:
                                        nodes[i].genPacket(0,plenB,0)
                                    # real-time topology
                                    if rts == True:
                                        rp.plot_tree(nodes)
                                        rp.save()
                                        rp.close()
                                else:
                                    pass
                            # not waiting, can send join request
                            elif packet.type in [0,1,2] and txNode.rt.hops < HL:
                                nodes[i].genPacket(0,plenA,3)
                                nodes[i].rt.parent = txNode.id
                                nodes[i].rt.hops = txNode.rt.hops + 1
                                yield env.process(wait_confirm(env,nodes[i]))
                            else:
                                pass
                        # already joined
                        else:
                            # data
                            if packet.type == 0:
                                if txNode.rt.parent == nodes[i].id:
                                    nodes[i].rt.resp[packet.src.id] = True
                                    nodes[i].rt.tout[packet.src.id] = 0
                                    nodes[i].relayPacket(packet)
                            # query
                            elif packet.type == 2:
                                if nodes[i].rt.parent == txNode.id:
                                    if packet.dest == nodes[i].id:
                                        nodes[i].rt.lrt = env.now
                                        nodes[i].genPacket(0,plenB,0)
                                    elif packet.dest in nodes[i].rt.childs:
                                        nodes[i].relayPacket(packet)
                                    else:
                                        pass
                            # beacon/confirm/join request
                            else:
                                pass
                    # undefined device id == 0 
                    else:
                        raise ValueError('undefined node id')
                    
                    # join request
                    if packet.type == 3:
                        if txNode.rt.parent == nodes[i].id:
                            # initialize child
                            nodes[i].rt.tout[packet.src.id] = 0
                            nodes[i].rt.resp[packet.src.id] = False
                            nodes[i].rt.childs.add(packet.src.id)
                            # not at GW, relay
                            if nodes[i].id != 0:
                                nodes[i].relayPacket(packet)
                            # direct link
                            if packet.src.id == txNode.id:
                                nodes[i].genPacket(packet.src.id,plenA,4) # confirm
                            # indirect link
                            else:
                                pass
                        else:
                            pass


                # catch losing condition when node is critical
                else:
                    pass
                    #cl.catch3(packet,txNode,nodes[i],result)
            txNode.modeTo(1)
            yield env.timeout(dt2)
        # to sleep
        else:
            pass

def wait_response(env,node):
    id = node.txBuffer[0].dest
    node.rt.resp[id] = False
    yield env.timeout(RTH)
    if id == 0:
        node.rt.waiting = None
    # timeout
    if not node.rt.resp[id]:
        node.rt.tout[id] += 1
        if node.rt.tout[id] > 5:
            node.rt.tout.pop(id)
            node.rt.resp.pop(id)
            node.rt.childs.remove(id)
            # real-time topology
            if rts == True:
                rp.plot_tree(nodes)
                rp.save()
                rp.close()

def wait_query(env,node):
    yield env.timeout(QTH)
    # no query
    if env.now - node.rt.lrt >= QTH:
        node.rt.childs = set()
        node.rt.resp = {}
        node.rt.tout = {}

        node.rt.parent = None
        node.rt.lrt = None
        node.rt.joined = False
        node.rt.hops = None
    # received query
    else:
        pass

def wait_confirm(env,node):
    yield env.timeout(CTH)
    # no confirm
    if not node.rt.joined:
        node.rt.parent = None
        node.rt.joined = False
        node.rt.hops = None
    # already joined
    else:
        pass