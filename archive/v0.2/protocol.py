import random
import simpy

#
# CONSTANTS
#

n0 = 10 # assumed no. of neighbour nodes
p0 = (1-(1/n0))**(n0-1)

RM = 2 # rssi margin to ensure reliable routing result

#
# MAC protocols (rx <-> tx)
# 
# outputs:
#   nxMode - next mode of transceiver
#   dt - time for env.timeout()
#

# p-csma
def csma(txNode):
    nxMode = 1
    dt = 0
    if (not txNode.rxBuffer) and txNode.txBuffer:
        # transmit with p0 possibility
        if (random.random() <= p0):
            nxMode = 2 # mode to tx
        else:
            # >p0, wait till next slot
            dt = 1000
    else:
        # refresh when channel busy or has nothing to send
        dt = 100
    return nxMode,dt

#
# routing algorithms
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
            if seq > rxNode.rt.seqDict[dest]:
                pass
            elif seq == rxNode.rt.seqDict[dest] and metric < rxNode.rt.metricDict[dest]:
                pass
            else:
                return False
        # new dest
        else:
            # for direct link, if dR does not exceed rssi margin, reject link to ensure link quality
            if metric == 1 and dR < RM:
                return False
            else:
                pass
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
# data packets generation
#

