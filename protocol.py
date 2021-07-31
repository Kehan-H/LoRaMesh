import random

#
# CONSTANTS
#

n0 = 10 # assumed no. of neighbour nodes
p0 = (1-(1/n0))**(n0-1)

# rssi margin to ensure reliable routing result
RM = 15

# avg time between generated data packets in ms
avgGenTime = 1000*60

# default packet length of beacon and data
plenB = 20
plenD = 15

#
# MAC protocols (rx -> tx)
# 
# outputs:
#   nxMode - next mode of transceiver
#   dt1 - time for timeout before the next mode 
#   dt2 - time for timeout after the next mode
#

# p-csma
def csma(txNode):
    nxMode = 1
    dt1 = 0
    dt2 = 0
    if (not txNode.rxBuffer) and txNode.txBuffer:
        # transmit with p0 possibility
        if (random.random() <= p0):
            nxMode = 2 # mode to tx
        else:
            # >p0, wait till next slot
            dt1 = 1000
    else:
        # refresh when channel busy or has nothing to send
        dt1 = 500
    return nxMode,dt1,dt2

# query-based
def query(txNode):
    nxMode = 1
    dt1 = 0
    dt2 = 0
    # BS
    if txNode.id < 0:
        if len(txNode.rt.destSet) <= 1:
            nxMode = 1
            txNode.genPacket(-1,25,1)
            dt2 = 60*1000
    # end devices
    elif txNode.id > 0:
        pass
    # undefined device id == 0 
    else:
        raise ValueError('invalid node id')
    return nxMode,dt1,dt2

#
# routing algorithms (packet processing after scccessfully decoded)
#

# DSDV
def dsdv(packet,txNode,rxNode,dR):
    # add or edit entry in rt; return update or not
    def updateRT(dest,txNode,rxNode,dR):        
        next = txNode.id
        metric = txNode.rt.metricDict[dest] + 1
        seq = txNode.rt.seqDict[dest]
        # existing dest
        if dest in rxNode.rt.destSet:
            if seq >= rxNode.rt.seqDict[dest] and metric < rxNode.rt.metricDict[dest]:
                pass
            else:
                return False
        # new dest
        else:
            # for direct link, if dR does not exceed rssi margin, reject link to ensure link quality
            if dR < RM and metric == 1:
                return False
            else:
                rxNode.rt.destSet.add(dest)
        rxNode.rt.nextDict[dest] = next
        rxNode.rt.metricDict[dest] = metric
        rxNode.rt.seqDict[dest] = seq
        return True

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
        for dest in txNode.rt.destSet:
            # return update or not; side effect: update entry
            update += updateRT(dest,txNode,rxNode,dR)
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
    dt = 100
    # BS
    if node.id < 0:
        node.genPacket(-1,plenB,1)
        dt = 10*60*1000
    # end devices
    elif node.id > 0:
        node.genPacket(-1,plenD,0)
        dt = avgGenTime
    # undefined device id == 0 
    else:
        raise ValueError('invalid node id')
    return dt
