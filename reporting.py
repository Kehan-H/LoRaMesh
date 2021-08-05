import matplotlib.pyplot as plt

# show statistics
def print_data(nodes,exp):
    for node in nodes:
        if node.id >= 0:
            print(str(node.id) + ':' + node.pathTo(0))
            try:
                print('PDR = ' + str(node.arr/node.pkts))
                print('Faded Rate = ' + str(node.fade/node.pkts))
                print('Collision Rate = ' + str(node.coll/(node.pkts-node.fade)))
                print('Miss Rate = ' + str(node.miss/(node.pkts-node.fade)))
            except:
                pass
            print('\n')

# show topology
def display_graph(nodes,exp):
    for node in nodes:
        nbr = set()
        for other in nodes:
            if exp == 1:
                if other.id in node.nextDict.values():
                    nbr.add(other)
            if exp == 2:
                if other.id == node.rt.parent:
                    nbr.add(other)
        for n in nbr:
            plt.plot([node.x,n.x],[node.y,n.y],'c-',zorder=0)
        plt.scatter(node.x,node.y,color='red',zorder=5)
        plt.annotate(node.id,(node.x, node.y),color='black',zorder=10)
    plt.show()
