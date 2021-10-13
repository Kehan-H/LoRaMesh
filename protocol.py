import random
import reporting as rp
import network as nw

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
                rp.plot_tree(nw.nodes)
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
                rp.plot_tree(nw.nodes)
                rp.save()
                rp.close()
        # broadcast table(beacon)
        if update and packet.ttl > 0:
            rxNode.rt.seqDict[rxNode.id] += 2
            rxNode.relayPacket(packet)
    else:
        raise ValueError('undefined packet type')

# p-csma + dsdv (with memory)
# timer-based rerouting
def reactive3(packet,txNode,rxNode,rssi):
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
                    # if metric is not too worse and rssi is significantly better, reroute to ensure link quality
                    if diff > RM2 and metric <= rxNode.rt.metricDict[dest] + round(diff/RM2):
                        pass
                    # if metric is better and rssi is not too worse, allow update
                    elif diff > -RM1 and metric < rxNode.rt.metricDict[dest]:
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
                rp.plot_tree(nw.nodes)
                rp.save()
                rp.close()
        # broadcast table(beacon)
        if update and packet.ttl > 0:
            rxNode.rt.seqDict[rxNode.id] += 2
            rxNode.relayPacket(packet)
    else:
        raise ValueError('undefined packet type')

# p-csma + dsdv (with memory)
# unlimited divergence at the beginning
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
                    if sample_num >= len(rxNode.rt.rssiRec[old]) >= 5:
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
                rp.plot_tree(nw.nodes)
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