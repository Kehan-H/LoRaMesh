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

# time threshold for not receiving from gw
QTH = 5*60*1000

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

# query-based
def proactive3(txNode,t0):
    nxMode = 1
    dt1 = 0
    dt2 = 0
    # GW
    if txNode.id == 0:
        sent = 1
        for packet in txNode.txBuffer:
            if packet.type == 2:
                sent = 0
        # query has been sent, check response
        if txNode.rt.qlst and sent:
            id = txNode.rt.qlst.pop(0)
            # received
            if txNode.rt.resp[id]:
                txNode.rt.tout[id] = 0
                txNode.rt.resp[id] = False
            # timeout
            else:
                txNode.rt.tout[id] += 1
                if txNode.rt.tout[id] > 5:
                    txNode.rt.tout.pop(id)
                    txNode.rt.childs.remove(id)
        # generate query
        if txNode.rt.childs:
            # queue is empty. can start a new round of query
            if not txNode.rt.qlst:
                txNode.rt.qlst = list(txNode.rt.childs)
            txNode.genPacket(txNode.rt.qlst[0],plenA,2)
        # generate beacon
        else:
            txNode.genPacket(0,plenC,1)
    # end devices
    elif txNode.id > 0:
        # remove parent if not receive from GW for QTH ms
        if txNode.rt.joined and (t0 - txNode.rt.lrt >= QTH):
            txNode.rt.joined = False
            txNode.rt.parent = None
            txNode.rt.hops = None
            if rts == True:
                rp.plot_tree(nw.nodes)
                rp.plt.title(t0)
                rp.save()
                rp.close()
    else:
        raise ValueError('undefined node id')

    # has packet to transmit
    if txNode.txBuffer:
        nxMode = 2
        # beacon
        if txNode.txBuffer[0].type == 1:
            dt2 = 60*1000
        # query
        elif txNode.txBuffer[0].type == 2:
            dt2 = 2000 # wait 2s for response
        # data/confirm/request
        elif txNode.txBuffer[0].type in [0,3,4]:
            dt2 = 0
        else:
            raise ValueError('undefined packet type')
    # nothing to transmit
    else:
        nxMode = 1
        dt1 = 100 # refresh
    return nxMode,dt1,dt2

#
# reactive process after packet is successfully decoded
#
# outputs:
#   nxMode - next mode of transceiver
#   dt1 - time for staying in rx mode before the next mode 
#   dt2 - time before the next process after the next mode is done
#

# query-based
def reactive3(packet,txNode,rxNode,t0):
    # GW
    if rxNode.id == 0:
        # data
        if packet.type == 0:
            # arrive at dest
            if txNode.rt.parent == 0:
                packet.src.arr += 1
                rxNode.rt.resp[packet.src.id] = True
                if packet.src.arr > packet.src.pkts:
                    raise ValueError('Node ' + str(packet.src.id) + ' has more arrived than generated.')
        # beacon/query/confirm/join request
        else:
            pass
    # end devices
    elif rxNode.id > 0:
        # not joined
        if not rxNode.rt.joined:
            # waiting for confirmation
            if rxNode.rt.parent != None:
                # confirm
                if packet.dest == rxNode.id and packet.type == 4:
                    rxNode.rt.joined = True
                    rxNode.rt.lrt = t0
                    # real-time topology
                    if rts == True:
                        rp.plot_tree(nw.nodes)
                        rp.plt.title(t0)
                        rp.save()
                        rp.close()
                elif t0 - rxNode.rt.lrt > 60*1000:
                    rxNode.rt.parent = None
                else:
                    pass
            # send join request when data/beacon/query
            elif packet.type in [0,1,2] and txNode.rt.hops < HL:
                rxNode.genPacket(0,plenA,3)
                rxNode.rt.parent = txNode.id
                rxNode.rt.hops = txNode.rt.hops + 1
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
            # beacon/confirm/join request
            else:
                pass
    # undefined device id
    else:
        raise ValueError('undefined node id')
    
    # receive join request
    if packet.type == 3:
        if txNode.rt.parent == rxNode.id:
            # arrive at GW
            if rxNode.id == 0:
                rxNode.rt.tout[packet.src.id] = 0
                rxNode.rt.resp[packet.src.id] = False
            # relay
            else:
                rxNode.relayPacket(packet)
            # direct link
            if packet.src.id == txNode.id:
                rxNode.genPacket(txNode.id,plenA,4) # confirm
            # indirect link
            else:
                pass
            rxNode.rt.childs.add(packet.src.id)
        else:
            pass