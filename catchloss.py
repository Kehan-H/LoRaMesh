#
# catch losing condition of packet
#

# p-csma + dsdv / with memory
def catch1(packet, txNode, rxNode, result):
    if txNode.rt.nextDict[packet.dest] == rxNode.id and packet.type == 0:
        if result:
            packet.src.coll += result[0]
            packet.src.miss += result[1]
        else:
            packet.src.atte += 1