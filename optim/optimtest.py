#!/usr/bin/env python

''' Test file for an entire optimization run of the power control problem. Mostly for testing ipopt functionality and dbugging.

File: optimtest.py
'''

__author__ = "Hauke Holtkamp"
__credits__ = "Hauke Holtkamp"
__license__ = "unknown"
__version__ = "unknown"
__maintainer__ = "Hauke Holtkamp"
__email__ = "h.holtkamp@gmail.com" 
__status__ = "Development" 

from numpy import *
import scipy as Sci
import scipy.linalg
import pyipopt

pmax = 10 # arbitrary
nvar = 3
x_L = zeros((nvar), dtype=float_) * 0.0
x_U = ones((nvar), dtype=float_) * 1.0

ncon = nvar + 1 # transmit power constraints and the unit sum 
g_L = zeros(1+nvar) # unit sum and all power constraints
g_L[0] = 1.
g_U = pmax * ones(1+nvar) # unit sum and all power constraints
g_U[0] = 1.

def eval_f(mus, noisepower, H, rate, linkBandwidth, p0, m ):
    """Objective function. Min power equal power 2x2 MIMO. 
    Variable is the resource share in TDMA. Returns scalar."""

    result = 0

    if mus.size is 1: # mus is integer
        return mus*(p0 + m*ptxOfMu(mus, rate, linkBandwidth, noisepower, H[0,:,:]))
    else:
        for i in range(mus.size):
            Ptxi = ptxOfMu(mus[i], rate, linkBandwidth, noisepower, H[i,:,:])
            Ppm = (p0 + m*Ptxi) * mus[i]
            result = result + Ppm

        #print result
        return result

def eval_grad_f(mus, noisepower, H, rate, linkBandwidth, p0, m):
    """Gradient of the objective function. Returns array of scalars, each one the partial derivative."""
    result = 0
    mus = array(mus) # allow iteration
    if mus.size is 1:
        a,b,M = dissectH(H[0,:,:])
        capacity = rate / (linkBandwidth * mus)
        return p0 + m*M*noisepower*( ( ( a**2 / b + 2*2**capacity - 1/mus * ( rate/linkBandwidth* log(2) * 2**capacity) - 2 ) /  sqrt( a**2 + 2 * b * (2**capacity - 1) ) ) - a / b ) 
    else:
        result = zeros((mus.size), dtype=float_)
        for i in range(mus.size):
            a,b,M = dissectH(H[i,:,:])
            capacity = rate / (linkBandwidth * mus[i])
            result[i] = p0 + m*M*noisepower*( ( ( a**2 / b + 2*2**capacity - 1/mus[i] * ( rate/linkBandwidth * log(2) * 2**capacity) - 2 ) /  sqrt( a**2 + 2 * b * (2**capacity - 1) ) ) - a/b ) 
        #print result
        return result

def eval_g(mus, noisepower, H, rate, linkBandwidth):
    """Constraint functions. Returns an array."""

    mus = array(mus)
    result = zeros((mus.size+1), dtype=float_)
    result[0] = sum(mus) # first constraint is the unit sum
    # Other constraints: Maximum transmission power limit
    if mus.size is 1:
        result[1] = ptxOfMu(mus, rate, linkBandwidth, noisepower, H[0,:,:])
        return result
    else:
        for i in range(mus.size):
            result[i+1] = ptxOfMu(mus[i], rate, linkBandwidth, noisepower, H[i,:,:])
    
    #print result
    return result
   
nnzj = nvar * (1+nvar) # There is a power constraint for each variable. Each of these has nvar partial derivatives. And there is the unit sum constraint which has nvar partial derivatives. Makes nvar*nvar + nvar Jacobian entries in total.
def eval_jac_g(mus, noisepower, H, rate, linkBandwidth, flag):
    """Gradient of constraint function/Jacobian. min power equal power 2x2 MIMO.
    mus is the resource share in TDMA. Output is a numpy array with the nnzj rows."""
    if mus.size is 1:
        a,b,M = dissectH(H[0,:,:])
        capacity = rate / (linkBandwidth * mus)
        result = M*noisepower* ( - (rate/linkBandwidth)* log(2) * 2**capacity) / (mus**2 * sqrt( a**2 + 2*b*(2**capacity - 1)))
        return result

    if flag: # The 'structure of the Jacobian' is the map of which return value refers to which constraint function. There are nvar*(1+nvar) constraints overall. There are 1+nvar functions in eval_g, each of which has nvar partial derivatives. 
        lineindex = array(range(1+nvar)).repeat(nvar)
        rowindex  = tile(array(range(nvar)),nvar+1)
        return (lineindex,rowindex)

    else:
        index = 0
        mus = array(mus) # allow iteration
        result = zeros((mus.size*(mus.size+1)), dtype=float_)
        # The derivatives of the unit sum are just 1
        for i in range(mus.size):
            result[index] = 1
            index = index + 1
        
        # The derivatives of each power constraint:
        for i in range(mus.size): # the number of power constraints
            for j in range(mus.size): # the number of partial derivatives per power constraint
                if i == j: # there is a partial derivative
                    a,b,M = dissectH(H[i,:,:])
                    capacity = rate / (linkBandwidth * mus[i])
                    result[index] = M*noisepower* ( - (rate/linkBandwidth)* log(2) * 2**capacity) / (mus[i]**2 * sqrt( a**2 + 2*b*(2**capacity - 1)))
                else: # there is no partial derivative
                    result[index] = 0 # partial derivative is zero

                index = index + 1
    
        #print result
        return result

def ergMIMOsnrCDITCSIR2x2(capacity, H):
    """Ergodic MIMO SNR as a function of achieved capacity and channel."""
    a,b,M = dissectH(H)
    return (M / b) * ( -a + sqrt( a**2 + 2 * b * (2**capacity - 1) ) )

def dissectH(H):
    """Take apart H into some values that we need often."""
    M = H.shape[0]
    eigvals, eigvects = linalg.eig(dot(H,H.conj().T))
    e1 = eigvals[0].real
    e2 = eigvals[1].real
    a = e1 + e2 
    b = 2*e1 * e2

    return (a,b,M) 

def ptxOfMu(mu, rate, linkBandwidth, noisepower, H):
    """Returns transmission power needed for a certain channel capacity as a function of the MIMO channel and noise power."""
    capacity = rate / (linkBandwidth * mu)
    return noisepower*ergMIMOsnrCDITCSIR2x2(capacity, H)

########################################################################################
#if __name__ == '__main__':
# timeit
import time
start = time.time()


# Input parameters
H = array([[[1.-1j,-1.],[-1.,1.]],[[1.-1j,1.],[-1.,1.]],[[0.5,1.j],[1.,-1.j]]])
e1s,ev = linalg.eig(dot(H[0,:,:],H[0,:,:].conj().T))
e2s,ev = linalg.eig(dot(H[1,:,:],H[1,:,:].conj().T))
print 'Eigenvalues: ', e1s[0].real,e1s[1].real,e2s[0].real,e2s[1].real

noisepower = 1
rate = 1
linkBandwidth = 1
p0 = 0
m = 1
mus = array([0.1,0.1,0.1])

# Anonymous functions for optim, because optim can only take one parameter
anon_eval_f = lambda mus: eval_f(mus, noisepower, H, rate, linkBandwidth, p0, m) 
anon_eval_grad_f = lambda mus: eval_grad_f(mus, noisepower, H, rate, linkBandwidth, p0, m) 
anon_eval_g = lambda mus: eval_g(mus, noisepower, H, rate, linkBandwidth)
anon_eval_jac_g = lambda mus, flag: eval_jac_g(mus, noisepower, H, rate, linkBandwidth, flag) # Needs flag!

# Prep 
def print_variable(variable_name, value):
      for i in xrange(len(value)):
              print variable_name + "["+str(i)+"] =", value[i]

nnzh = 0 #used?
x0 = array([0.1, 0.1, 0.1]) # Starting point

# Function test
print 'x0:', x0
print 'H:',H
print 'f(x):',anon_eval_f(x0) # should be 8.6789
print 'dissectH:', dissectH(H[0,:,:]) # 5,2,2
print 'ptxOfMu:', ptxOfMu(0.1, rate, linkBandwidth, noisepower, H[0,:,:]) # 59.16
print 'grad_f:', anon_eval_grad_f(x0) # not sure
print 'eval_g:', anon_eval_g(x0) # [0.2 27.625, 59.16]
print 'jac_g(1):', anon_eval_jac_g(x0,1)
print 'jac_g:', anon_eval_jac_g(x0,0) # not sure


print
print "Calling solver with set of vars"
print "nvar = ", nvar 
print "x_L  = ", x_L 
print "x_U  = ", x_U 
print "g_L  = ", g_L 
print "g_U  = ", g_U 
print "ncon = ", ncon 
print "nnzj, nnzh = ", nnzj, ", ", nnzh
print "x0   = ", x0

# Call solve() 
#pyipopt.set_loglevel(2) # verbose
nlp = pyipopt.create(nvar, x_L, x_U, ncon, g_L, g_U, nnzj, nnzh, anon_eval_f, anon_eval_grad_f, anon_eval_g, anon_eval_jac_g)
#nlp.int_option("max_iter", 3000)
#nlp.num_option("tol", 1e-8)
#nlp.num_option("acceptable_tol", 1e-2)
#nlp.int_option("acceptable_iter", 0)
nlp.str_option("derivative_test", "first-order")
nlp.str_option("derivative_test_print_all", "no")
#nlp.str_option("print_options_documentation", "yes")
nlp.str_option("print_user_options", "yes")
#nlp.int_option("print_level", 12)
x, zl, zu, obj, status = nlp.solve(x0)
nlp.close()

# Print results
print
print "Solution of the primal variables, x"
print_variable("x", x)
print
print "Solution of the bound multipliers, z_L and z_U"
print_variable("z_L", zl)
print_variable("z_U", zu)
print
print "Objective value"
print "f(x*) =", obj

# timeit
end = time.time()
print 'Code time %.6f seconds' % (end - start)

# Test result
x = array([0.5701, 0.4299])
print 'x:', x
print 'f(x):', anon_eval_f(x)
print 'dissectH: ', dissectH(H[0,:,:])
print 'ptxOfMu: ', ptxOfMu(x[1], rate, linkBandwidth, noisepower, H[1,:,:])
print 'ergMIMOsnrCDITCSIR2x2: ', ergMIMOsnrCDITCSIR2x2( 1./x[0], H[0,:,:]) 


# Test cost function and derivative graphically

import matplotlib.pyplot as plt
murange = arange(0.01,.11,0.001)
# eval_f
result_f = []
for mu in murange:
   result_f.append(anon_eval_f (mu))
# eval_grad_f
result_grad_f = []
for mu in murange:
    result_grad_f.append(anon_eval_grad_f (mu))
# eval_g
result_g = []
for mu in murange:
    result_g.append(anon_eval_g(mu))
# eval_jac_g
result_grad_g = []
for mu in murange:
    result_grad_g.append(anon_eval_jac_g(mu,0))

#plt.plot(murange,result_f, 'r', murange, result_grad_f, 'b', murange, result_grad_g, 'gs')
#plt.plot(result_grad_g, 'r')
#plt.plot(result_grad_g)
#plt.show()
