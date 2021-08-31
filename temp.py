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
            metric = txNode.rt.metricDict[dest] + 1
            seq = txNode.rt.seqDict[dest]
            # existing dest
            if dest in rxNode.rt.destSet:
                if seq >= rxNode.rt.seqDict[dest]:
                    # always update lost route
                    if metric == float('inf'):
                        pass
                    # conditionally update established routes
                    elif (sample_num >= 5):
                        old = rxNode.rt.nextDict[dest]
                        old_avg = sum(rxNode.rt.rssiRec[old])/len(rxNode.rt.rssiRec[old])
                        # if metric is better and rssi is not too worse, allow update
                        if metric < rxNode.rt.metricDict[dest] and (avg_rssi > old_avg - RM1):
                            pass
                        # if metric is not too worse and rssi is significantly better, update to ensure link quality
                        elif metric <= rxNode.rt.metricDict[dest] + 1 and (avg_rssi > old_avg + RM2):
                            pass
                        # reject update
                        else:
                            continue
                    # reject update at low sample number
                    else:
                        continue
                    rxNode.rt.nextDict[dest] = next
                    rxNode.rt.metricDict[dest] = metric
                    rxNode.rt.seqDict[dest] = seq
                    update = True
                else:
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