import itertools
import numpy as np
import uuid
import requests
import time
import warnings
import qiskit
import logging
import random
import copy

logger = logging.getLogger(__name__)


def format_vector(state_vector, verbose=0):
    """ Format a state vector in LaTeX format
    
    Args:
        state_vector (array): state vector
    Returns:
        s (str): state vector in LaTeX format
    """
    s=''
    n=int(np.log2(len(state_vector)) )
    xx=list(itertools.product( * ([0,1],)*n ) )
    if verbose:
        print(xx)
    states= [ ''.join([str(p) for p in x]) for x in xx] 
    if verbose:
        print(states)
    for ii,v in enumerate(state_vector):
        st=states[ii]
        a,b=float(np.real(v)),float(np.imag(v) )
        
        def fmt(v, single=False):
            if np.abs(v-1)<1e-8:
                return ''
            if single and np.abs(v+1)<1e-8:
                return '-'
            return '%.2g' % v
        #print('%s %s' % (a,fmt(a)) )
        if np.abs(b)>1e-8:
            if ii>0:
                if len(s)>0:
                    s+=' + '
            s+= r'(%s + %s j) \left\lvert %s\right\rangle' % (fmt(a),fmt(b), st )
        else:
            if np.abs(a)>1e-8:
                if ii>0 and len(s)>0 and a>0:
                    s+=' + '
                s+= r'%s \left\lvert %s\right\rangle' % (fmt(a, True), st )
            else:
                pass
    return s

from IPython.display import display, Math, Latex
from qiskit import QuantumCircuit

def run_circuit(qc, q, n=None, verbose=0, backend='local_statevector_simulator'):
    """ Run a circuit on all input vectors and show the output
    
    Args:
        qc (quantum circuit):
        q (QuantumRegister)
        n (int or None): number of qubits
    """
    if n is None:
        n=q.size 
    if q.size!=n:
        warnings.warn('incorrect register size?')
    display(Math('\mathrm{running\ circuit\ on\ set\ of\ basis\ states:}'))
    for ii in range(2**n):
        qc0 = QuantumCircuit(q)
        qc0.barrier(q[0]) # dummy circuit

        mm=[]
        ij=ii
        for kk in range(n):
            mm+=[ij%2]
            if ij%2==1:
                qc0.x(q[kk])
            ij=ij//2
        inputstate = '|'+ (' '.join(['%d' % m for m in mm[::-1]]) ) + '>'
        if 0:
            job = qiskit.execute(qc0, backend=backend)
            state_vector = job.result().get_statevector(qc0)
            inputstate=format_vector(state_vector)

        qc0=qc0.combine(qc)

        job = qiskit.execute(qc0, backend=backend)
        state_vector = job.result().get_statevector(qc0)
        if verbose>=2:
            print(state_vector)
        display(Math(inputstate+'\mathrm{transforms\ to}: '+format_vector(state_vector)))

#%% From QisKit example scripts
    
def n_controlled_Z(circuit, controls, target):
    """Implement a Z gate with multiple controls"""
    if (len(controls) > 2):
        raise ValueError('The controlled Z with more than 2 ' +
                         'controls is not implemented')
    elif (len(controls) == 1):
        circuit.h(target)
        circuit.cx(controls[0], target)
        circuit.h(target)
    elif (len(controls) == 2):
        circuit.h(target)
        circuit.ccx(controls[0], controls[1], target)
        circuit.h(target)
        
def inversion_about_average(circuit, f_in, n):
    """Apply inversion about the average step of Grover's algorithm."""
    # Hadamards everywhere
    if n==1:
        circuit.x(f_in[0])
        return
    for j in range(n):
        circuit.h(f_in[j])
    # D matrix: flips the sign of the state |000> only
    for j in range(n):
        circuit.x(f_in[j])
    n_controlled_Z(circuit, [f_in[j] for j in range(n-1)], f_in[n-1])
    for j in range(n):
        circuit.x(f_in[j])
    # Hadamards everywhere again
    for j in range(n):
        circuit.h(f_in[j])

#%%
        

        

#%%
class QuantumInspireAPI:
    
    def __init__(self, server, auth = None):
        """ Python interface to the Quantum Inspire API
               
        For documentation see:
            
            https://dev.quantum-inspire.com/api
            https://dev.quantum-inspire.com/api/docs/#jobs-create
        
        """
        self.server = server
        try:
            _ = requests.get(server)
        except:
            raise Exception('could not connect to %s' % server)
        self.auth = auth
        
        self._last_job=None
        self._last_result = None

        req = self._subrequest('backends')
        r=req.json()
        
        if 'detail' in r:
            raise Exception('invalid credentials')
    def _subrequest(self, path):
        return requests.get(self.server+'/'+path, auth=self.auth)

    def _request(self, path):
        return requests.get(path, auth=self.auth)

    def _request_post(self, path, data=None):
        return requests.post(path, auth=self.auth, data=data)

    def _request_delete(self, path, data=None):
        return requests.delete(path, auth=self.auth, data=data)
        
    def list_backends(self):
        req = self._subrequest('backends')
        j=req.json()
        for ii, b in enumerate(j):
            print('backend: %s (qubits %s)' % (b['name'], b['nqubits']))
        return j
    def list_projects(self):
        req = self._subrequest('projects')
        j=req.json()
        for ii, b in enumerate(j):
            print('project: %s (backend %s)' % (b['name'], b['backend_type']))
        return j
    
    def get_result(self, id):
        req = self._subrequest('results/%d' % id)
        return req.json()
    
    def list_results(self):
        req = self._subrequest('results')
        j=req.json()
        for ii, b in enumerate(j):
            print('result: id %s (date %s)' % (b['id'], b['created_at']))
        return j
    def list_jobs(self, verbose=1):
        req = self._subrequest('jobs')
        j=req.json()
        if verbose:
            for ii, b in enumerate(j):
                print('result: name %s id %s (status %s)' % (b['name'], b['id'], b['status']))
        return j

    def list_assets(self):
        req = self._subrequest('assets')
        j=req.json()
        for ii, b in enumerate(j):
            print('asset: name %s id %s (project_id %s)' % (b['name'], b['id'], b['project_id']))
        return j

    def submit_qasm(self, qasm):
        pass

    def _debug_result(self, r):
        import tempfile
        
        if r.status_code==404:
            tfile = tempfile.mktemp(suffix='.html')
            with open(tfile, 'wt') as fid:
                fid.write(r.text)
                
            import webbrowser
            webbrowser.open_new(tfile)
        else:
            j=r.json()
            print(j)
    def execute_qasm(self, qasm, nshots=256, verbose=1):
        # create a project
        pname='qi-tmpproject-%s' % str(uuid.uuid1())
        jname='qi-tmpjob-%s' % str(uuid.uuid1())
        
        if verbose:
            print('submitting qasm code to quantum inspire %s' % (jname,))

        payload={'name': pname, 'number_of_shots': nshots}
        r = self._request_post(self.server+'/projects/', data=payload)
        pr = r.json()
        #self._debug_result(r)
        
        # create asset
        aname='qi-tmpasset-%s' % str(uuid.uuid1())
        payload={'name': aname, 'contentType': 'text/plain', 'project': pr['url'], 'content': qasm}
        ra = self._request_post(self.server+'/assets/', data=payload)
        asset=ra.json()
        if verbose>=2:
            print(asset)

        # create job
        payload={'name': jname, 'input': asset['url'], 'backend_type': pr['backend_type'], 'status': 'NEW', 'number_of_shots': 256}
        #payload['backend']='https://dev.quantum-inspire.com/api/backends/1/'
        #payload['backend']=''
        if verbose>=2:
            print(payload)

        jobr = self._request_post(self.server+'/jobs/', data=payload)
        job=jobr.json()
        
        for ii in range(100):
            time.sleep(.5)
            x = self._request(self.server+'/jobs/%d' % job['id'])
            jx=x.json()
            if jx['status']=='COMPLETE':
                break
            if verbose:
                print('waiting for result of job %s (iteration %d)' % (job['id'], ii))

        if jx['status']=='COMPLETE':
            if verbose:
                print('result of job %s is COMPLETE' % (job['id'],))
        else:
            if verbose:
                print('result of job %s is %s' % (job['id'], jx['status']))
            return None
        
        # get results
        results = self._request(jx['results'])
        results=results.json()
        
        self._last_job=job
        self._last_result=results
            
        # delete stuff
        try:
            x1 = self._request_delete(self.server+'/assets/%d' % asset['id'])
            x2 = self._request_delete(self.server+'/projects/%d' % pr['id'])
        except:
            pass
        return results


#%%

        