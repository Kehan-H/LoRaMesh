import matplotlib.pyplot as plt

# print routes and DER
def print_data(nodes):
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

# prepare show
def display_graph(nodes):
    for node in nodes:
        nbr = node.rt.getNbr()
        for n in nbr:
            plt.plot([node.x,n.x],[node.y,n.y],'c-',zorder=0)
        plt.scatter(node.x,node.y,color='red',zorder=5)
        plt.annotate(node.id,(node.x, node.y),color='black',zorder=10)
    plt.show()