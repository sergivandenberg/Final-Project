# -*- coding: utf-8 -*-
""" Test cases for projectq backend

@author: eendebakpt
"""

#%%

import numpy as np
import unittest
from unittest import mock
from unittest.mock import MagicMock
import io

import quantuminspire.projectq
import quantuminspire.projectq.backend_qx
from projectq.cengines import (TagRemover, )
from projectq import MainEngine
import projectq.libs.math
from projectq.ops import T, Tdag, S, Sdag, H, X, Y, Z, Rx, Ry, Rz, Ph, Measure, CNOT, Swap, All, CX, CZ, Barrier, QFT, Toffoli
from projectq.ops import BasicPhaseGate
from projectq.ops import C


class MockApiBasicAuth:
    def __init__(self, username, password, domain=None, scheme=None):
        """ Basic mock for coreapi.auth.BasicAuthentication."""
        self.username = username
        self.password = password
        self.domain = domain
        self.scheme = scheme


def _valid_cqasm(s):
    """ Quick test to whether an object is valid cqasm """
    if not isinstance(s, str):
        return False
    if not s.startswith('version 1.0'):
        return False
    return True


_cqasm = '''version 1.0
# generated by Quantum Inspire <class 'quantuminspire.projectq.backend_qx.QIBackend'> class
qubits 3


h q[0]
CNOT q[0], q[1]
measure q[0]
measure q[1]
measure q[2]
display
'''


class MockApiClient:
    handlers = dict()
    mock_document = "MockDocument"

    def __init__(self, auth=None):
        """ Basic mock for coreapi.Client."""
        global __cqasm
        self.authentication = auth

        # for for 2-qubit result
        self.execute_qasm = MagicMock(return_value={'histogram': {'00': 0.49, '11': 0.51}, 'results': 'dummy'})
        self.cqasm = MagicMock(return_value=_cqasm)

    def get(self, url):
        return ' '.join([self.__class__.mock_document, url])

    def action(self, document, keys, params=None, validate=True, overrides=None,
               action=None, encoding=None, transform=None):
        if keys[0] not in self.__class__.handlers:
            raise Exception("action %s not mocked" % keys[0])
        return self.__class__.handlers[keys[0]](self, document, keys, params, validate,
                                                overrides, action, encoding, transform)


class TestProjectQBackend(unittest.TestCase):
    def setUp(self):
        self.authentication = MockApiBasicAuth('user', 'unknown')
        self.coreapi_client = MockApiClient()

    def test_invalid_histogram(self):
        coreapi_client = self.coreapi_client
        coreapi_client.execute_qasm = MagicMock(return_value={'histogram': {}, 'results': 'dummy'})
        engine_list = [projectq.cengines.ManualMapper(lambda ii: ii)]  # , AutoReplacer(rule_set)]
        qi_backend = quantuminspire.projectq.backend_qx.QIBackend(
            quantum_inspire_api=coreapi_client, backend=None, perform_execution=True)

        eng = MainEngine(backend=qi_backend, engine_list=engine_list)

        with self.assertRaises(Exception):
            qubits = eng.allocate_qureg(1)
            H | qubits[0]
            All(Measure) | qubits
            eng.flush()

    def test_cqasm_submission(self):
        coreapi_client = self.coreapi_client
        engine_list = [TagRemover(), projectq.cengines.ManualMapper(lambda ii: ii)]  # , AutoReplacer(rule_set)]
        qi_backend = quantuminspire.projectq.backend_qx.QIBackend(
            quantum_inspire_api=coreapi_client, backend=None, perform_execution=True)

        # create a default compiler (the back-end is a simulator)
        eng = MainEngine(backend=qi_backend, engine_list=engine_list)

        qubits = eng.allocate_qureg(2)
        H | qubits[0]
        CNOT | (qubits[0], qubits[1])
        All(Measure) | qubits
        eng.flush()

        print("Measured {}".format(','.join([str(int(q)) for q in qubits])))  # co

        p = qi_backend.get_probabilities(qubits)

        apicall = self.coreapi_client.execute_qasm.mock_calls[0]

        cqasm_data = tuple(apicall)[1][0]
        self.assertTrue(cqasm_data.startswith('version 1.0'))
        self.assertIn('h q[0]', cqasm_data)
        self.assertIn('CNOT q[0], q[1]', cqasm_data)

        self.assertIn('00', p)
        self.assertIn('11', p)
        self.assertNotIn('01', p)
        self.assertNotIn('10', p)

        cqasm = qi_backend.cqasm()
        self.assertTrue(_valid_cqasm(cqasm))

    def test_elementary_gates(self, verbose=0, perform_execution=False, quantum_inspire_api=None):
        """ Test the backend generates cqasm for all elementary gates """
        engine_list = [TagRemover(), projectq.cengines.ManualMapper(lambda ii: ii)]  # , AutoReplacer(rule_set)]
        qi_backend = quantuminspire.projectq.backend_qx.QIBackend(
            quantum_inspire_api=quantum_inspire_api, backend=None, perform_execution=perform_execution)
        for gate in [H, Ry(0.5), Rx(np.pi / 2), Rz(.1), X, Y, Z, S, Sdag, T, Tdag,
                     CNOT, Swap, CX, CZ, Barrier]:

            if hasattr(gate, 'matrix'):
                nq = int(gate.matrix.shape[0] / 2)
            else:
                nq = 2

            if verbose:
                print('\n### run gate %s on %d qubits' % (gate, nq))

            # create a default compiler (the back-end is a simulator)
            eng = MainEngine(backend=qi_backend, engine_list=engine_list)

            qubits = eng.allocate_qureg(nq + 1)
            if nq == 1:
                gate | qubits[0]
            else:
                gate | tuple(qubits[0:nq])
            All(Measure) | qubits

            eng.flush()

            if verbose >= 2:
                print('generated cqasm:\n---')
                print(qi_backend.cqasm())
                print('---')

    def test_toffoli_gate(self):
        qi_backend = quantuminspire.projectq.backend_qx.QIBackend(perform_execution=False)
        eng = MainEngine(backend=qi_backend, engine_list=[])

        qubits = eng.allocate_qureg(3)
        Toffoli | (qubits[0], qubits[1], qubits[2])
        eng.flush()

        cqasm = qi_backend.cqasm()
        self.assertTrue(_valid_cqasm(cqasm))
        self.assertIn('Toffoli q[0], q[1], q[2]', cqasm)

    def test_controlled_gates(self):
        qi_backend = quantuminspire.projectq.backend_qx.QIBackend(perform_execution=False)
        eng = MainEngine(backend=qi_backend, engine_list=[])

        qubits = eng.allocate_qureg(2)
        C(X) | (qubits[0], qubits[1])
        C(Rz(.1)) | (qubits[0], qubits[1])
        with self.assertRaises(NotImplementedError):
            C(Rx(.1)) | (qubits[0], qubits[1])
        eng.flush()

    def test_notimplemented_gate(self):
        qi_backend = quantuminspire.projectq.backend_qx.QIBackend(perform_execution=False)
        eng = MainEngine(backend=qi_backend, engine_list=[])

        qubits = eng.allocate_qureg(2)
        with self.assertRaises(NotImplementedError):
            QFT | qubits

    def test_initial_cqasm(self):
        qi_backend = quantuminspire.projectq.backend_qx.QIBackend()
        self.assertEqual(qi_backend.cqasm(), '')

    def test_is_available(self, perform_execution=False, quantum_inspire_api=None):
        engine_list = [projectq.cengines.ManualMapper(lambda ii: ii)]
        qi_backend = quantuminspire.projectq.backend_qx.QIBackend(
            quantum_inspire_api=quantum_inspire_api, backend=None, perform_execution=perform_execution)
        eng = MainEngine(backend=qi_backend, engine_list=engine_list)
        qubits = eng.allocate_qureg(1)
        for gate in [H, Ry(0.5), Rx(np.pi / 2), Rz(.1), X, Y, Z, S, Sdag, T, Tdag]:
            cmd = gate.generate_command(qubits[0:1])
            self.assertTrue(qi_backend.is_available(cmd))

        cmd = Measure.generate_command(qubits[0])
        self.assertTrue(qi_backend.is_available(cmd))

        cmd = Barrier.generate_command(qubits[0])
        self.assertTrue(qi_backend.is_available(cmd))

        phcmd = Ph(0.1).generate_command(qubits[0:1])
        self.assertFalse(qi_backend.is_available(phcmd))

        class NotImplementedGate(BasicPhaseGate):
            pass
        not_available_cmd = NotImplementedGate(.1).generate_command(qubits[0:1])
        self.assertFalse(qi_backend.is_available(not_available_cmd))

    def test_execute_verbose(self):
        qi_backend = quantuminspire.projectq.backend_qx.QIBackend(perform_execution=False)
        eng = MainEngine(backend=qi_backend)
        qi_backend._verbose = 2

        with unittest.mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            qubits = eng.allocate_qureg(1)
            H | qubits[0]

            eng.flush()
            print_string = mock_stdout.getvalue()
            self.assertIn('_run', print_string)
            self.assertIn('sending cqasm', print_string)
            self.assertIn('------', print_string)

    def test_is_available_verbose(self):
        qi_backend = quantuminspire.projectq.backend_qx.QIBackend(perform_execution=False)
        eng = MainEngine(backend=qi_backend, engine_list=[])
        qi_backend._verbose = 1

        with unittest.mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            qubits = eng.allocate_qureg(1)
            cmd = H.generate_command(qubits[0])
            qi_backend.is_available(cmd)

            print_string = mock_stdout.getvalue()
            self.assertTrue(print_string.startswith('call to is_available with cmd H'))