#
# catch losing condition of packet
#

# dsdv
def catch1(packet,txNode,rxNode,result):
    if txNode.rt.nextDict[packet.dest] == rxNode.id and packet.type == 0:
        if result:
            packet.src.coll += result[0]
            packet.src.miss += result[1]
        else:
            packet.src.fade += 1

#
# query-based
#