## pseudo code for transceiver process

```
while True:
    if mode == receive:
        # p-persistent CSMA
        if channel empty:
            # transmit with p0 possibility
            if random.random() <= p0:
                mode = transmit
            else:
                wait a time slot
        else:
            wait a refresh period
    elif mode == transmit:
        broadcast packet
        for receiver in nodes:
            if (rssi at other) > sensitivity:
                coll = collision at receiver
                miss = (mode of receiver != receive)
                add [packet, coll, miss] to the receiving queue
        wait until transmit ends
        for receiver in nodes:
            result = delivery at receiver
            if packet type == data:
                # not supposed to receive, wasted
                if receiver is not the next node:
                    pass
                else:
                    if receiver is the destination node:
                        CONGRATS
                    elif packet TTL > 0:
                        receiver relay packet
                        TTL -= 1
                    else:
                        pass
            elif packet type == routing beacon:
                # DSDV
                update = 0
                for entry in received routing table:
                    if (new entry) or (entry has less hop) or (entry has larger sequence number):
                        update own entry
                        update = 1
                if (update == 1) and packet TTL > 0:
                    sequence number += 2
                    TTL -= 1
                    relay beacon with own routing table
            else:
                pass
        mode = receive
    else:
        pass
```