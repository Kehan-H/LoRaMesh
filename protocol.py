import random

#
# CONSTANTS
#
n0 = 10 # assumed no. of neighbour nodes
p0 = (1-(1/n0))**(n0-1)

#
# MAC protocols (rx -> tx)
#
# dt - time for env.timeout()
#    - to tx mode when returning 0

# carrier sense
def csma(txNode):
    if (not txNode.rxBuffer) and txNode.txBuffer:
        # transmit with p0 possibility
        if (random.random() <= p0):
            dt = 0 # mode to tx
        else:
            # >p0, wait till next slot
            dt = 1000
    else:
        # refresh when channel busy or has nothing to send
        dt = 100
    return dt


#
# routing algorithms
#

# DSDV
def dsdv(packet,txNode,rxNode):
    # sensor data
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
            else:
                pass
    # routing beacon
    elif packet.type == 1:
        # DSDV update routing table
        update = 0 # flag needed because there can be multiple entries to update
        rxNode.nbr.add(txNode)
        for dest in txNode.rt.destSet:
            # return update or not; side effect: update entry
            update = rxNode.updateRT(dest,txNode.id,txNode.rt.metricDict[dest]+1,txNode.rt.seqDict[dest])
        if update and packet.ttl > 0:       
            rxNode.relayPacket(packet)
            rxNode.rt.seqDict[rxNode.id] += 2
    # reserved for other packet type
    else:
        pass
