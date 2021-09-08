import random
import reporting as rp

#
# CONSTANTS
#

# real-time show
rts = False

# p-csma param
n0 = 5 # assumed no. of neighbour nodes
p0 = (1-(1/n0))**(n0-1)

# rssi margin to ensure reliable routing result
RM1 = 5
RM2 = 10

# time threshold for not receiving from gw
K = 5*60*1000

# hop limit
HL = 5

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
        if txNode.rt.qlst:
            id = txNode.rt.qlst.pop(0)
            # timeout
            if txNode.rt.resp[id] == False:
                txNode.rt.tout[id] += 1
                if txNode.rt.tout[id] > 5:
                    txNode.rt.tout.pop(id)
                    txNode.rt.childs.remove(id)
            # received
            else:
                txNode.rt.tout[id] = 0
                txNode.rt.resp[id] = False
        # send beacon
        if len(txNode.rt.childs) == 0:
            nxMode = 2
            txNode.genPacket(0,25,1)
            dt2 = 60*1000
        # send query
        else:
            # queue is empty. can start a new round of query
            if not txNode.rt.qlst:
                txNode.rt.qlst = list(txNode.rt.childs)
            txNode.genPacket(0,plenA,txNode.rt.qlst[0])
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
            # real-time topology
            if rts == True and dest == 0:
                rp.plot_tree()
                rp.save()
                rp.close()
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
        sample_num = len(rxNode.rt.rssiRec[next])
        avg_rssi =  sum(rxNode.rt.rssiRec[next])/sample_num
        # dsdv with hysteresis
        dests = (dest for dest in txNode.rt.destSet if dest != rxNode.id)
        for dest in dests:
            # prevent loop
            if txNode.rt.nextDict[dest] == rxNode.id:
                continue
            metric = txNode.rt.metricDict[dest] + 1
            seq = txNode.rt.seqDict[dest]
            # existing dest
            if dest in rxNode.rt.destSet:
                if seq < rxNode.rt.seqDict[dest] or metric > HL:
                    continue
                else:
                    old = rxNode.rt.nextDict[dest]
                    old_avg = sum(rxNode.rt.rssiRec[old])/len(rxNode.rt.rssiRec[old])
                    # if metric is better and rssi is not too worse, allow update
                    if metric < rxNode.rt.metricDict[dest] and (avg_rssi > old_avg - RM1):
                        pass
                    # if metric is not too worse and rssi is significantly better, reroute to ensure link quality
                    elif metric <= rxNode.rt.metricDict[dest] + 1 and (avg_rssi > old_avg + RM2):
                        pass
                    # reject update if rssi or metric is bad
                    else:
                        continue
            # new dest
            else:
                rxNode.rt.destSet.add(dest)
            rxNode.rt.nextDict[dest] = next
            rxNode.rt.metricDict[dest] = metric
            rxNode.rt.seqDict[dest] = seq
            update = True
            # real-time topology
            if rts == True and dest == 0:
                rp.plot_tree()
                rp.save()
                rp.close()
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
                rxNode.rt.resp[rxNode] = True
                if packet.src.arr > packet.src.pkts:
                    raise ValueError('Node ' + str(packet.src.id) + ' has more arrived than generated.')
        # join request
        elif packet.type == 3:
            rxNode.genPacket(packet.src.id,plenA,4)
            rxNode.rt.childs.add(packet.src.id)
            rxNode.rt.tout[id] = 0
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
                elif packet.dest in rxNode.rt.childs:
                    rxNode.relayPacket(packet)
                else:
                    pass
            # join request
            elif packet.type == 3:
                if txNode.rt.parent != rxNode.id:
                    pass
                elif packet.src.id != txNode.id:
                    rxNode.relayPacket(packet)
                    rxNode.rt.childs.add(packet.src.id)
                # direct link
                elif dR > RM1:
                    rxNode.genPacket(packet.src.id,plenA,4) # confirm
                    rxNode.relayPacket(packet)
                    rxNode.rt.childs.add(packet.src.id)
                else:
                    pass
            # beacon/confirm
            else:
                pass
    # undefined device id == 0 
    else:
        raise ValueError('undefined node id')

# p-csma + dsdv (with memory)
def reactive4(packet,txNode,rxNode,rssi):
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
        sample_num = len(rxNode.rt.rssiRec[next])
        avg_rssi =  sum(rxNode.rt.rssiRec[next])/sample_num
        # dsdv with hysteresis
        dests = (dest for dest in txNode.rt.destSet if dest != rxNode.id)
        for dest in dests:
            # prevent loop
            if rxNode in txNode.pathTo(dest):
                continue
            metric = txNode.rt.metricDict[dest] + 1
            seq = txNode.rt.seqDict[dest]
            # existing dest
            if dest in rxNode.rt.destSet:
                if seq < rxNode.rt.seqDict[dest] or metric > HL:
                    continue
                else:
                    old = rxNode.rt.nextDict[dest]
                    old_avg = sum(rxNode.rt.rssiRec[old])/len(rxNode.rt.rssiRec[old])
                    # conditionally update established routes (converge + diverge)
                    if sample_num >= len(rxNode.rt.rssiRec[old]) >= 10:
                        # if metric is better and rssi is not too worse, allow update
                        if metric < rxNode.rt.metricDict[dest] and (avg_rssi > old_avg - RM1):
                            pass
                        # if metric is not too worse and rssi is significantly better, reroute to ensure link quality
                        elif metric <= rxNode.rt.metricDict[dest] + 1 and (avg_rssi > old_avg + RM2):
                            pass
                        # reject update if rssi or metric is bad
                        else:
                            continue
                    # rssi oriented rerouting when sample not enough (diverge)
                    elif sample_num >= len(rxNode.rt.rssiRec[old]) and avg_rssi > old_avg:
                            pass
                    else:
                        continue
            # new dest
            else:
                rxNode.rt.destSet.add(dest)
            rxNode.rt.nextDict[dest] = next
            rxNode.rt.metricDict[dest] = metric
            rxNode.rt.seqDict[dest] = seq
            update = True
            # real-time topology
            if rts == True and dest == 0:
                rp.plot_tree()
                rp.save()
                rp.close()
        # broadcast table(beacon)
        if update and packet.ttl > 0:
            rxNode.rt.seqDict[rxNode.id] += 2
            rxNode.relayPacket(packet)
    else:
        raise ValueError('undefined packet type')

# p-csma + dsdv (with memory)
def reactive5(packet,txNode,rxNode,rssi):
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
        sample_num = len(rxNode.rt.rssiRec[next])
        avg_rssi =  sum(rxNode.rt.rssiRec[next])/sample_num
        # dsdv with hysteresis
        dests = (dest for dest in txNode.rt.destSet if dest != rxNode.id)
        for dest in dests:
            # prevent loop
            if rxNode in txNode.pathTo(dest):
                continue
            metric = txNode.rt.metricDict[dest] + 1
            seq = txNode.rt.seqDict[dest]
            # existing dest
            if dest in rxNode.rt.destSet:
                if seq < rxNode.rt.seqDict[dest] or metric > HL:
                    continue
                else:
                    # conditionally update established routes (converge + diverge)
                    old = rxNode.rt.nextDict[dest]
                    diff = avg_rssi - sum(rxNode.rt.rssiRec[old])/len(rxNode.rt.rssiRec[old])
                    # if metric is better and rssi is not too worse, allow update
                    if diff > -RM1 and metric < rxNode.rt.metricDict[dest]:
                        pass
                    # if metric is not too worse and rssi is significantly better, reroute to ensure link quality
                    elif diff > RM2:
                        N = round(diff/RM2)
                        if metric <= rxNode.rt.metricDict[dest] + N:
                            pass
                        else:
                            continue
                    # reject update if rssi or metric is bad
                    else:
                        continue    
            # new dest
            else:
                rxNode.rt.destSet.add(dest)
            rxNode.rt.nextDict[dest] = next
            rxNode.rt.metricDict[dest] = metric
            rxNode.rt.seqDict[dest] = seq
            update = True
            # real-time topology
            if rts == True and dest == 0:
                rp.plot_tree()
                rp.save()
                rp.close()
        # broadcast table(beacon)
        if update and packet.ttl > 0:
            rxNode.rt.seqDict[rxNode.id] += 2
            rxNode.relayPacket(packet)
    else:
        raise ValueError('undefined packet type')

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