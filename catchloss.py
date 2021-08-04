#
# catch losing condition of packet
#

# dsdv
def catch1(packet,txNode,rxNode,result):
    if not result:
        packet.src.fade += 1
    elif txNode.rt.nextDict[packet.dest] == rxNode.id and packet.type == 0:
        packet.src.coll += result[0]
        packet.src.miss += result[1]
    else:
        pass

#
# query-based
#