import matplotlib.pyplot as plt

from network import EXP

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
                print('Faded Rate = ' + str(node.fade/node.pkts))
                print('Collision Rate = ' + str(node.coll/(node.pkts-node.fade)))
                print('Miss Rate = ' + str(node.miss/(node.pkts-node.fade)))
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
    plt.show()

# show tree topology
def display_tree(nodes):
    for node in nodes:
        route = node.pathTo(0)
        if route:
            plt.plot([node.x,route[0].x],[node.y,route[0].y],'c-',zorder=0)
        plt.scatter(node.x,node.y,color='red',zorder=5)
        plt.annotate(node.id,(node.x, node.y),color='black',zorder=10)
    plt.show()