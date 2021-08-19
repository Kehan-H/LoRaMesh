import random

#
# CONSTANTS
#

n0 = 5 # assumed no. of neighbour nodes
p0 = (1-(1/n0))**(n0-1)

# rssi margin to ensure reliable routing result
RM1 = 0
RM2 = 0

# time threshold for not receiving from gw
K = 5*60*1000

# hop limit
HL = 3

# avg time between generated data packets in ms
avgGenTime = 1000*30

# default packet length
plenA = 10 # query/confirm/join
plenB = 15 # data
plenC = 20 # beacon

#
# proactive process in rx
# 
# outputs:
#   nxMode - next mode of transceiver
#   dt1 - time for staying in rx mode before the next mode 
#   dt2 - time before the next protocol loop after the next mode
#

# p-csma + dsdv
def proactive1(txNode,t0):
    nxMode = 1
    dt1 = 0
    dt2 = 0
    # initialize randomness to first time frame
    if t0 == 0:
        dt1 = random.randint(0,5000)
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

# p-csma + dsdv (with memory)
def proactive2(txNode,t0):
    nxMode = 1
    dt1 = 0
    dt2 = 0
    # initialize randomness to first time frame
    if t0 == 0:
        dt1 = random.randint(0,5000)
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

# query-based
def proactive3(txNode,t0):
    nxMode = 1
    dt1 = 0
    dt2 = 0
    # GW
    if txNode.id == 0:
        # check response
        for id in txNode.rt.childlist:
            # timeout
            if txNode.rt.resp[id] == False:
                txNode.rt.tout[id] += 1
                if txNode.rt.tout[id] > 5:
                    txNode.rt.tout[id] = 0
                    txNode.rt.childlist.remove(id)
            else:
                txNode.rt.resp[id] = False
        # send beacon
        if len(txNode.rt.childlist) == 0:
            nxMode = 2
            txNode.genPacket(0,25,1)
            dt2 = 60*1000
        # send query
        else:
            # txBuffer is empty. can start a new round of query
            if len(txNode.txBuffer) == 0:
                for id in txNode.rt.childlist:
                    txNode.genPacket(0,plenA,2)
            # send query in sequence
            nxMode = 2
            dt1 = 0
            dt2 = 1000 # wait 1s for response

    # end devices
    elif txNode.id > 0:
        # remove parent if not receive from GW for k ms
        if txNode.rt.joined and (t0 - txNode.lrt >= K):
            txNode.rt.joined = False
            txNode.rt.parent = None
            txNode.rt.hops = None
        
        # has packet to transmit
        if txNode.txBuffer:
            nxMode = 2
        # nothing to transmit
        else:
            nxMode = 1
            dt1 = 200 # refresh
    # undefined device id == 0 
    else:
        raise ValueError('undefined node id')
    return nxMode,dt1,dt2

#
# reactive process after packet is successfully decoded
#
# outputs:
#   nxMode - next mode of transceiver
#   dt1 - time for staying in rx mode before the next mode 
#   dt2 - time before the next process after the next mode is done
#

# p-csma + dsdv
def reactive1(packet,txNode,rxNode,rssi):
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
        update = False # flag needed because there can be multiple entries to update
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
                rxNode.rt.destSet.add(dest)
            rxNode.rt.nextDict[dest] = next
            rxNode.rt.metricDict[dest] = metric
            rxNode.rt.seqDict[dest] = seq
            update = True
        # broadcast table(beacon)
        if update and packet.ttl > 0:
            rxNode.rt.seqDict[rxNode.id] += 2
            rxNode.relayPacket(packet)
    else:
        raise ValueError('undefined packet type')

# p-csma + dsdv (with memory)
def reactive2(packet,txNode,rxNode,rssi):
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
        rxNode.rt.newRssi(txNode.id,rssi)
        update = False # flag needed because there can be multiple entries to update
        next = txNode.id
        for dest in txNode.rt.destSet:
            metric = txNode.rt.metricDict[dest] + 1
            seq = txNode.rt.seqDict[dest]
            # existing dest
            if dest in rxNode.rt.destSet:
                # dsdv with hysteresis
                if seq >= rxNode.rt.seqDict[dest] and metric <= rxNode.rt.metricDict[dest] + 1:
                    num = len(rxNode.rt.rssiRec[next])
                    avg =  sum(rxNode.rt.rssiRec[next])/num
                    old = rxNode.rt.nextDict[dest]
                    oldnum = len(rxNode.rt.rssiRec[old])
                    oldavg = sum(rxNode.rt.rssiRec[old])/oldnum
                    if (num >= oldnum > 5):
                        # if metric is better and rssi is not too worse, allow update
                        if metric < rxNode.rt.metricDict[dest] and (avg > oldavg - RM1):
                            pass
                        # if metric is not too worse and rssi is significantly better, update to ensure link quality
                        elif metric <= rxNode.rt.metricDict[dest] + 1 and (avg > oldavg + RM2):
                            pass
                        # reject update
                        else:
                            continue
                    # reject update
                    else:
                        continue
                    rxNode.rt.nextDict[dest] = next
                    rxNode.rt.metricDict[dest] = metric
                    rxNode.rt.seqDict[dest] = seq
                    update = True
            # new dest
            else:
                rxNode.rt.destSet.add(dest)
                rxNode.rt.nextDict[dest] = next
                rxNode.rt.metricDict[dest] = metric
                rxNode.rt.seqDict[dest] = seq
                update = True
        # broadcast table(beacon)
        if update and packet.ttl > 0:
            rxNode.rt.seqDict[rxNode.id] += 2
            rxNode.relayPacket(packet)
    else:
        raise ValueError('undefined packet type')

# query-based
def reactive3(packet,txNode,rxNode,dR,t0):
    # GW
    if rxNode.id == 0:
        # data
        if packet.type == 0:
            # arrive at dest
            if txNode.parent == 0:
                packet.src.arr += 1
                rxNode.rt.resp[rxNode] = 1
                if packet.src.arr > packet.src.pkts:
                    raise ValueError('Node ' + str(packet.src.id) + ' has more arrived than generated.')
        # join request
        elif packet.type == 3:
            rxNode.genPacket(packet.src.id,plenA,4)
            rxNode.rt.childlist.add(packet.src.id)
        # beacon/query/confirm
        else:
            pass
    # end devices
    elif rxNode.id > 0:
        # not joined
        if not rxNode.rt.joined:
            # waiting for confirmation
            if rxNode.rt.parent != None:
                # implies this is a confirmation packet
                if packet.dest == rxNode.id:
                    rxNode.rt.joined = True
                    rxNode.rt.lrt = t0
                elif t0 - txNode.lrt > 5000:
                    rxNode.rt.parent = None
                else:
                    pass
            # send join request
            elif packet.type in [0,1,2] and dR > RM1 and txNode.rt.hops <= HL:
                rxNode.genPacket(0,plenA,3)
                rxNode.rt.parent = txNode.id
                rxNode.rt.lrt = t0
            else:
                pass
        # already joined
        else:
            # data
            if packet.type == 0:
                # relay
                if txNode.rt.parent == rxNode.id:
                    rxNode.relayPacket(packet)
            # query
            elif packet.type == 2:
                if packet.dest == rxNode.id:
                    rxNode.genPacket(0,plenB,0)
                elif packet.dest in rxNode.rt.childlist:
                    rxNode.relayPacket(packet)
                else:
                    pass
            # join request
            elif packet.type == 3:
                if txNode.rt.parent != rxNode.id:
                    pass
                elif packet.src.id != txNode.id:
                    rxNode.relayPacket(packet)
                    rxNode.rt.childlist.add(packet.src.id)
                # direct link
                elif dR > RM1:
                    rxNode.genPacket(packet.src.id,plenA,4) # confirm
                    rxNode.relayPacket(packet)
                    rxNode.rt.childlist.add(packet.src.id)
                else:
                    pass
            # beacon/confirm
            else:
                pass
    # undefined device id == 0 
    else:
        raise ValueError('undefined node id')

#
# packets generation scheme
#
# output:
#   dt - time for timeout before the next generation
#

# periodic generator
def periGen(node):
    # GW
    if node.id == 0:
        node.genPacket(0,plenC,1)
        dt = 10*60*1000
    # end devices
    elif node.id > 0:
        node.genPacket(0,plenB,0)
        dt = avgGenTime
    else:
        raise ValueError('undefined node id')
    return dt

# exponential generator for end devices
def expoGen(node):
    # GW
    if node.id == 0:
        node.genPacket(0,plenC,1)
        dt = 10*60*1000
    # end devices
    elif node.id > 0:
        node.genPacket(0,plenB,0)
        dt = random.expovariate(1.0/avgGenTime)
    else:
        raise ValueError('undefined node id')
    return dt