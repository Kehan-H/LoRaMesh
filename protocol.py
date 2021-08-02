import random

#
# CONSTANTS
#

n0 = 5 # assumed no. of neighbour nodes
p0 = (1-(1/n0))**(n0-1)

# rssi margin to ensure reliable routing result
RM = 22.5

# avg time between generated data packets in ms
avgGenTime = 1000*60

# default packet length
plenB = 20 # beacon
plenD = 15 # data
plenQ = 10 # query

#
# MAC protocols (rx -> tx)
# 
# outputs:
#   nxMode - next mode of transceiver
#   dt1 - time for staying in rx mode before the next mode 
#   dt2 - time before the next protocol loop after returning to rx mode from other mode 
#

# csma
def csma(txNode,t0):
    nxMode = 1
    dt1 = 0
    dt2 = 0
    # initialize randomness to first time frame
    if t0 == 0:
        dt1 = random.randint(0,5000)
        print(dt1)
        return nxMode,dt1,dt2
    # p-csma
    if txNode.txBuffer:
        packet = txNode.txBuffer[0]
        # hold packet when channel is busy or no route for non-beacon packet
        if txNode.rxBuffer or (packet.type != 1 and (packet.dest not in txNode.rt.destSet)):
            dt1 = 500
        else:
            # transmit with p0 possibility
            if (random.random() <= p0):
                nxMode = 2 # mode to tx
            else:
                # >p0, wait till next slot
                dt1 = 500
    else:
        # has nothing to send
        dt1 = 500
    return nxMode,dt1,dt2

# # query-based
# def query(txNode):
#     nxMode = 1
#     dt1 = 0
#     dt2 = 0
#     # BS
#     if txNode.id == 0:
#         if len(txNode.rt.destSet) <= 1:
#             nxMode = 1
#             txNode.genPacket(0,25,1)
#             dt2 = 60*1000
#         else:
#             # txBuffer is empty. can start a new round of query
#             if len(txNode.txBuffer) == 0:
#                 for id in txNode.rt.destSet:
#                     if id != txNode.id:
#                         txNode.genPacket(0,plenQ,2)
#             # query not finished
#             else:
#                 pass
#             nxMode = 2
#             dt1 = 


#     # end devices
#     elif txNode.id > 0:
#         pass
#     # undefined device id == 0 
#     else:
#         raise ValueError('undefined node id')
#     return nxMode,dt1,dt2

#
# routing algorithms (packet processing after scccessfully decoded)
#

# DSDV
def dsdv(packet,txNode,rxNode,dR):
    # data packets
    if packet.type == 0:
        # not supposed to receive, wasted
        if txNode.rt.nextDict[packet.dest] != rxNode.id:
            pass
        # arrive at next/dest
        else:
            if packet.dest == rxNode.id:
                packet.src.arr += 1
                if packet.src.arr > packet.src.pkts:
                    raise ValueError('Node ' + str(packet.src.id) + ' has more arrived than generated.')
            elif packet.ttl > 0:
                rxNode.relayPacket(packet)
            # pkt runs out of ttl before reaching dest
            else:
                pass
    # routing beacon
    elif packet.type == 1:
        # update routing table
        update = 0 # flag needed because there can be multiple entries to update
        next = txNode.id
        for dest in txNode.rt.destSet:
            metric = txNode.rt.metricDict[dest] + 1
            seq = txNode.rt.seqDict[dest]
            # existing dest
            if dest in rxNode.rt.destSet:
                if seq < rxNode.rt.seqDict[dest] or metric >= rxNode.rt.metricDict[dest]:
                    continue
            # new dest
            else:
                # for direct link, if dR does not exceed rssi margin, reject link to ensure link quality
                if dR < RM and metric == 1:
                    continue                    
            rxNode.rt.destSet.add(dest)
            rxNode.rt.nextDict[dest] = next
            rxNode.rt.metricDict[dest] = metric
            rxNode.rt.seqDict[dest] = seq
            update = 1
        # broadcast table(beacon)
        if update and packet.ttl > 0:
            rxNode.relayPacket(packet)
            rxNode.rt.seqDict[rxNode.id] += 2
    
    # reserved for other packet type
    else:
        pass

#
# packets generation scheme
#
# output:
#   dt - time for timeout before the next generation
#

# periodic generator
def periGen(node):
    # BS
    if node.id == 0:
        node.genPacket(0,plenB,1)
        dt = 10*60*1000
    # end devices
    elif node.id > 0:
        node.genPacket(0,plenD,0)
        dt = avgGenTime
    else:
        raise ValueError('undefined node id')
    return dt

# exponential generator for end devices
def expoGen(node):
    # BS
    if node.id == 0:
        node.genPacket(0,plenB,1)
        dt = 10*60*1000
    # end devices
    elif node.id > 0:
        node.genPacket(0,plenD,0)
        dt = random.expovariate(1.0/avgGenTime)
    else:
        raise ValueError('undefined node id')
    return dt