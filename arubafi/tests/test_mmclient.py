import sys
import os
import json
import responses
import requests
import unittest
from xmltodict import parse
from mock import patch

sys.path.append(os.path.dirname(__file__) + "/../")
#print(sys.path)

from mmclient import MMClient
from .test_data.mmclient_data import *

BASE_URL = "https://test.arubamm.com"
BASE_API_URL = BASE_URL + ":4343/v1"
LOGIN_URL = BASE_API_URL + "/api/login"

import logging
import logzero
from logzero import logger



class TestMMClient(unittest.TestCase):
    '''Test class for testing MMClient.
    '''
    @responses.activate
    def setUp(self):
        '''MMClient instance creator for the whole class.
        '''
        responses.add(responses.POST, LOGIN_URL, status=200, json=login_resp)
        resp = requests.post(LOGIN_URL)

        # For figuring out how to use responses
        assert resp.json() == login_resp

        self.mmc = MMClient(BASE_URL, "care", "pare")
        self.mmc.comms()

    def test_kwargs_modify_get(self):
        '''Test for kwargs_modify for GET method with endpoint
        'configuration/object/ap_sys_prof'

        Keys must have `endpoint`, `search` and `method = GET` in them
        '''
        expected_kwargs = {
            'endpoint': 'configuration/object/ap_sys_prof',
            'search': 'ap_sys_prof',
            'method': 'GET'}

        actual_kwargs = self.mmc._kwargs_modify('configuration/object/ap_sys_prof')

        self.assertEqual(
            expected_kwargs,
            actual_kwargs,
            f'\nExp kwargs = {expected_kwargs}\nAct kwargs = {actual_kwargs}')

    def test_kwargs_modify_post(self):
        '''Test for kwargs_modify for POST method with endpoint 'configuration/object/ap_sys_prof'

        Keys must have `endpoint`, `jpayload` and `method = POST` in them
        '''
        expected_kwargs = {
            'endpoint': 'configuration/object/ap_sys_prof',
            'jpayload': 'some JSON data payload',
            'method': 'POST'}

        actual_kwargs = self.mmc._kwargs_modify(
            'configuration/object/ap_sys_prof',
            data="some JSON data payload")

        self.assertEqual(
            expected_kwargs,
            actual_kwargs,
            f'\nExp kwargs = {expected_kwargs}\nAct kwargs = {actual_kwargs}')

    def test_params_1(self):
        '''Test for _params() by passing in just
        `profile_name='test-01.ap_sys_prof'` with endpoint
        `configuration/object/ap_sys_prof`
        '''
        expected_params = {
            'config_path': '/md',
            'UIDARUBA': 'fntoken',
            'filter': '[{"ap_sys_prof.profile-name": {"$eq": ["test-01.ap_sys_prof"]}}]'
            }

        modified_kwargs = self.mmc._kwargs_modify('configuration/object/ap_sys_prof')

        actual_params = self.mmc._params(
            profile_name='test-01.ap_sys_prof',
            **modified_kwargs)

        self.assertEqual(
            expected_params,
            actual_params,
            f'\nExp params = {expected_params}\nAct params = {actual_params}')

    def test_params_2(self):
        '''Testing _params() by passing in `profile_name='test-01.ap_sys_prof'` AND `config_path='/md/Test'`
        '''
        expected_params = {
            'config_path': '/md/Test',
            'UIDARUBA': 'fntoken',
            'filter': '[{"ap_sys_prof.profile-name": {"$eq": ["test-01.ap_sys_prof"]}}]'
            }

        modified_kwargs = self.mmc._kwargs_modify('configuration/object/ap_sys_prof')
        actual_params = self.mmc._params(
                profile_name='test-01.ap_sys_prof',
                config_path='/md/Test',
                **modified_kwargs)
        self.assertEqual(
            expected_params,
            actual_params,
            f'\nExp params = {expected_params}\nAct params = {actual_params}')

    def test_params_3(self):
        '''Testing _params() by passing in only `config_path='/md/Test'`
        '''
        expected_params = {
            'config_path': '/md/Test',
            'UIDARUBA': 'fntoken',
            }

        modified_kwargs = self.mmc._kwargs_modify('configuration/object/ap_sys_prof')
        actual_params = self.mmc._params(
                config_path='/md/Test',
                **modified_kwargs)
        self.assertEqual(
            expected_params,
            actual_params,
            f'\nExp params = {expected_params}\nAct params = {actual_params}')

    def test_params_4(self):
        '''Testing _params() by passing in the full filter `[ {"ap_sys_prof.profile-name" : { "$in" : ["a_profile"] } } ]` as JSON or list
        '''
        expected_params = {
            'config_path': '/md/Test',
            'UIDARUBA': 'fntoken',
            'filter': '[{"ap_sys_prof.profile-name": {"$in": ["a_profile"]}}]'
            }

        modified_kwargs = self.mmc._kwargs_modify('configuration/object/ap_sys_prof')
        actual_params = self.mmc._params(
                filter=[{"ap_sys_prof.profile-name":{"$in": ["a_profile"]}}],
                config_path='/md/Test',
                **modified_kwargs)
        self.assertEqual(
            expected_params,
            actual_params,
            f'\nExp params = {expected_params}\nAct params = {actual_params}')


    def test_params_5(self):
        '''Testing _params() by passing in the full filter `[ {"ap_sys_prof.profile-name" : { "$in" : ["a_profile"] } } ]` as string
        '''
        expected_params = {
            'config_path': '/md/Test',
            'UIDARUBA': 'fntoken',
            'filter': '[{"ap_sys_prof.profile-name":{"$in": ["a_profile"]}}]'
            }

        modified_kwargs = self.mmc._kwargs_modify('configuration/object/ap_sys_prof')
        actual_params = self.mmc._params(
                filter='[{"ap_sys_prof.profile-name":{"$in": ["a_profile"]}}]',
                config_path='/md/Test',
                **modified_kwargs)
        self.assertEqual(
            expected_params,
            actual_params,
            f'\nExp params = {expected_params}\nAct params = {actual_params}')


if __name__ == "__main__":
    unittest.main()
