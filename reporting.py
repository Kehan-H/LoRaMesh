import matplotlib.pyplot as plt
import glob
import csv

# show statistics
def print_data(nodes):
    for node in nodes:
        if node.id >= 0:
            route = node.pathTo(0)
            routeStr = ''
            if node.id == 0:
                routeStr = ' destination'
            elif route:
                for nn in route:
                    routeStr = routeStr + ' -> ' + str(nn.id)
            else:
                routeStr = ' no route'
            print(str(node.id) + ':' + routeStr)
            try:
                print('PDR = ' + str(node.arr/node.pkts))
                print('Attenuated Rate = ' + str(node.atte/node.pkts))
                print('Collision Rate = ' + str(node.coll/(node.pkts-node.atte)))
                print('Miss Rate = ' + str(node.miss/(node.pkts-node.atte)))
                print('Energy Consumption = ' + str(node.energy) + 'J')
            except:
                pass
            print('\n')

# show topology
def display_graph(nodes):
    for node in nodes:
        nbr = node.getNbr()
        for n in nbr:
            plt.plot([node.x,n.x],[node.y,n.y],'c-',zorder=0)
        plt.scatter(node.x,node.y,color='red',zorder=5)
        plt.annotate(node.id,(node.x, node.y),color='black',zorder=10)
    plt.grid(True)

# show tree topology
def plot_tree(nodes,dest=0):
    for node in nodes:
        route = node.pathTo(dest)
        if route:
            plt.plot([node.x,route[0].x],[node.y,route[0].y],'c-',zorder=0)
        plt.scatter(node.x,node.y,color='red',zorder=5)
        plt.annotate(node.id,(node.x, node.y),color='black',zorder=10)
    plt.grid(True)

# show hop vs PDR
def hop_vs_pdr(nodes,color='tab:blue'):
    # dictionary of lists; hops as keys
    pdrDict = {}
    for node in nodes:
        if node.id == 0:
            continue
        if node.pkts != 0:
            pdr = node.arr/node.pkts
        else:
            pdr = 0
        hops = len(node.pathTo(0)) # do not use metric directly (metric can be outdated when RT update fails)
        plt.scatter(hops,pdr,color=color,marker='x',zorder=5)
        plt.annotate(node.id,(hops,pdr),color='black',zorder=10)
        if hops not in pdrDict.keys():
            pdrDict[hops] = []
        pdrDict[hops].append(pdr)
    for key in pdrDict.keys():
        pdrDict[key] = sum(pdrDict[key])/len(pdrDict[key]) # mean
    keys = list(pdrDict.keys())
    values = list(pdrDict.values())
    plt.plot(keys,values,marker='o',color=color)
    plt.xlabel('Number of Hops')
    plt.ylabel('PDR')
    plt.grid(True)

def id_vs_pdr(nodes,color='tab:blue',shift=0,width=0.5):
    ids = []
    pdrs = []
    for node in nodes:
        if node.id > 0:
            pdrs.append(node.arr/node.pkts)
            ids.append(node.id)
    ids_shifted = [id+shift for id in ids]
    plt.bar(ids_shifted,pdrs,color=color,width=width,tick_label=ids)
    plt.xlabel('Node ID')
    plt.ylabel('PDR')
    plt.grid(axis = 'y')

def save():
    max = 0
    for name in glob.iglob('topos/*.png', recursive=True):
        idx = int(name[6:-4])
        if idx >= max:
            max = idx + 1
    plt.savefig('topos/%d.png'%max)

def save_data(nodes, filename):
    with open(filename+'.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["id", "pdr", "ar", "cr", "mr", "energy", "hops", "x", "y"])
        for node in nodes:
            if node.id > 0:
                pdr = node.arr/node.pkts
                ar = node.atte/node.pkts
                cr = node.coll/(node.pkts-node.atte)
                mr = node.miss/(node.pkts-node.atte)
                hops = len(node.pathTo(0))
                writer.writerow([node.id, pdr, ar, cr, mr, node.energy, hops, node.x, node.y])
            else:
                writer.writerow([0, 0, 0, 0, 0, node.energy, 0, node.x, node.y])


def legend():
    plt.legend()

def show():
    plt.show(block=True)

def close():
    plt.close()

def figure():
    plt.figure()
