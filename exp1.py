import numpy as np

# simulation settings
simtime = 5*1000*60*60

# default tx param
PTX = 8
SF = 7
CR = 4
BW = 125
FREQ = 900000000
TTL = 15

# network settings
avgSendTime = 1000*60 # avg time between packets in ms
slot = 1000
n0 = 10 # assumed no. of neighbour nodes
p0 = (1-(1/n0))**(n0-1)

# end nodes placement
# TODO: generate spatial distribution using Poisson Hard-Core Process
locsN = np.loadtxt('600x800.csv',delimiter=',')

# basestation
locsB = np.array([397.188492418693,226.186250701973])