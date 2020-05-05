import requests
import getpass
import json

import time
from functools import wraps
from requests.adapters import HTTPAdapter

import logging
import logzero
from logzero import logger


def log(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        logger.info(f'Calling {func.__name__}()')
        logger.debug(f'kwargs in: {kwargs}')

        start = time.time()
        func_call = func(*args, **kwargs)
        diff = start - time.time()
        logger.debug(f'Call took {diff}s')

        logzero.loglevel(logging.ERROR)

        return func_call
    return wrapped


class MMClient:
    """MobilityMaster API Client object.

    All AOS8 API resources are found on the MM https://<MM-IP|FQDN>:4343/api

    Params
    ------
    mm_host: `str`, optional, default: None
        FQDN or IP of the Mobility Master. No leading https://

    username: `str`, optional, default: None
        Username for Mobility Master login

    password: `str`, optional, default: None
        Password for Mobility Master login

    api_version: `str`, optional, default: 1
        The API version used for the calls.

    port: `str`, optional, default: 4343
        The port for the connection

    verify: `str`, optional, default: False
        Same as requests verify, but defaults to False as most MM
        implementations are expected to not use certs. Either a boolean, in
        which case it controls whether we verify the server’s TLS
        certificate, or a string, in which case it must be a path to a CA
        bundle to use.

    timeout: `int`, optional, default: 10
        The timeout for the connection

    Examples
    --------
    **Ex. 1:** Passing in minimum required parameters

    mmc = MMClient(
            mm_host="arubamm.domain.com",
            username="apiuser",
            password="the_password"
            )

    Instance can be created without some or all of above attributes. User
    will be prompted for either one or more `mm_host`, `username`,
    `password`.

    **Ex. 2:** passing in just the host.

    >>> mmc = MMClient(mm_host="arubamm.domain.com")
    MM API username required. Should I use `donkey.kong` to continue [Y/n]?
    MM API password for user `donkey.kong` required:

    **Ex. 3:** Passing in just the username and password

    >>> password = getpass.getpass()
    Password:

    >>> mmc = MMClient(username="apitest", password=password)
    Mobility Master URL or IP required: arubamm.domain.com

    **Ex. 4:** Using a proxy
    To use a proxy specify it with the `proxy` parameter
    """

    def __init__(self, mm_host=None, username=None, password=None, api_version=1, port=4343, verify=False, timeout=10, proxy=str()):
        self.mm_host = mm_host
        self.username = username
        self.password = password
        self.api_version = api_version
        self.port = port
        self.timeout = abs(timeout)
        self._access_token = ""

        self.proxy = {}
        if proxy:
            self.proxy = {
                'http': proxy,
                'https': proxy
                }

        self.verify = verify
        if self.verify == False:
            # Disable warnings that come up, as we're not checking the cert
            requests.packages.urllib3.disable_warnings()
            logger.info("Not verifying SSL")

    @log
    def comms(self):
        """User prompt for getting username and/or password, if they haven't been
        passed in with the constructor.
        """
        #
        # If MM URL or IP is not provided, ask for it
        #
        if not self.mm_host:
            self.mm_host = input("Mobility Master URL or IP required: ")

        # If username not provided...
        if not self.username:
            # ... ask for it
            user_input = input("MM API username required. Should I use `{}` to continue [Y/n]?".format(getpass.getuser()))

            # Option for a user if they want to specify a username
            if user_input.lower() == "n":
                self.username = input("API username:\x20")
            # ...any other answer, just use their current username
            else:
                self.username = getpass.getuser()

        # If password not provided, ask for it
        if not self.password:
            # If password is not set, get the username to log into and ask the
            # user for the password for that user
            self.password = getpass.getpass("MM API password for user `{}` required:\x20".format(self.username))

        # Base API URL for requests
        self.mm_base_api_url = f"{self.mm_host}:{self.port}/v{self.api_version}"
        if "https://" not in self.mm_base_api_url:
            self.mm_base_api_url = f"https://{self.mm_base_api_url}"

        # The login credentials dictionary
        self.login_payload = {
            'username': self.username,
            'password': self.password,
        }

        # We require data be returned in JSON format
        # We also pass it in the same format
        self.headers = {
            'Content-Type': 'application/json',
            'Accept' : 'application/json',
        }

        # Configure the session
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.session.verify = self.verify
        self.session.timeout = self.timeout
        self.session.proxies = self.proxy
        self.session.mount(self.mm_base_api_url, HTTPAdapter(max_retries=3))

        assert_status_hook = lambda response, *args, **kwargs: response.raise_for_status()
        self.session.hooks["response"] = [assert_status_hook]

        # Finaly login
        self._login()

    def _params(self, **kwargs):
        '''Parameters configurator for passing into the requests module

        Meant for parameters that get passed with the `params` attribute of
        requests.

        Args:
        -----
        config_path: `str`, default '/md'
            The config path of the MM.

        profile_name: `str`, optional
            A full or partial profile-name to be searched on. If partial include
            the proper 'filter_oper' otherwise `$eq` will be used to match
            exactly for that name.

        filter_oper: `str`, optional, default '$eq'
            An Aruba API defined filter operator:
                $eq: matches one of the values
                $neq: does not match any of the values
                $gt: matches a value which is greater than the filter
                $gte: matches a value which is greater than or equal to the filter
                $lt: matches a value which is less than the filter
                $lte: matches a value which is less than or equal to the filter
                $in: pattern matches the filter value. E.g., if filter says “ap”,
                “default-ap” and “ap- grp1” will both match
                $nin: pattern does not match the filter. Opposite of $in

        filter: `str`, optional
            A JSON data filter expression for the GET request.
            If defined it will override the `profile_name` and `filter_oper`
            arguments completely.

            Ex.:
            [ {"ap_sys_prof.profile-name" : { "$in" : ["def"] } } ]
            returns all profiles who's names include the 'def' string

            [ {"ht_ssid_prof.profile-name" : { "$eq" : ["default"] } } ]
            returns the profile who's name matches the whole 'default' string

        limit: `str`, optional
            The maximum number of instances of an object that a single GET
            request should return.

        count: `str`, optional
            List of fully qualified parameter name for which count operation
            needs to be performed.
            Ex.: 'int_vlan.int_vlan_ip_helper'

        total: `str`, optional
            The total number of instances of that object existing in system at
            that given configuration node. It should be set to 0 when first
            query is done and the count field specified in the result should be
            put here (optionally) for subsequent queries.

        offset: `str`, optional
            Conveys the number of the entry from which we should start the next
            data set.

        sort: `str`, optional
            The data from the GET request can be sorted based on a single field
            (currently, multi-parameter or nested sorts are not supported).
            There can only be one sort filter per request.
            Works in the form or <oper><key>, where <oper> is either + or - and
            <key> is the fully qualified object to which to sort on

            **Ex.:**
            '-int_vlan.int_vlan_mtu.value' will sort in descending order on the
            value parameter of 'int_vlan.int_vlan_mtu' object

        Returns:
        --------
        params: dict
            The full dict of parameters to be passed with the requets params attribute
        '''
        logger.info("Calling _params()")

        # Set the default config path if none provided
        params = {
            "config_path": kwargs.get('config_path', '/md'),
            "UIDARUBA": self._access_token
        }

        # If config path was provided with the kwargs, then rewrite the defualt
        if 'config_path' in kwargs:
            params['config_path'] = kwargs['config_path']

        # If `profile_name` provided filter for its exact match in the request
        # and use the `filter_oper` if provided
        if 'profile_name' in kwargs:
            profile_name_filter = [
                {
                    f"{kwargs['search']}.profile-name": { kwargs.get('filter_oper', '$eq'): [ kwargs['profile_name']]},
                }
            ]
            params['filter'] = json.dumps(profile_name_filter)

        # If filter provided it will override whatever was passed in with
        # either `profile_name` or `filter_oper` attributes
        if 'filter' in kwargs:
            if type(kwargs['filter']) is str:
                params['filter'] = kwargs['filter']
            else:
                params['filter'] = json.dumps(kwargs['filter'])

        # Other optional Aruba API defined parameters
        if 'limit' in kwargs:
            params['limit'] = str(kwargs['limit'])
        if 'count' in kwargs:
            params['count'] = str(kwargs['count'])
        if 'total' in kwargs:
            params['total'] = str(kwargs['total'])
        if 'offset' in kwargs:
            params['offset'] = str(wargs['offset'])
        if 'sort' in kwargs:
            params['sort'] = str(kwargs['sort'])
        if 'offset' in kwargs:
            params['offset'] = str(kwargs['offset'])

        logger.debug(f"Returned params: {params}")

        return params

    def _resource_url(self, resource):
        '''The resource URL formatter

        Will add the preceding '/' if not provided in the resource string

        Args:
        -----
        resource: `str`
            The endpoint resource, ex. 'configuration/object/ap_sys_prof'

        Returns:
        --------
        The full URL string to the requested resource.
        '''
        logger.info("Calling _resource_url()")
        url = str()

        if resource.startswith("/"):
            url = f'{self.mm_base_api_url}{resource}'
            logger.debug(f"URL to endpoint: {url}")
            return url
        else:
            url = f'{self.mm_base_api_url}/{resource}'
            logger.debug(f"URL to endpoint: {url}")
            return url

    def _api_call(self, method, url, **kwargs):
        '''The API call handler.

        This method is used by `resource`. kwargs passed in get passed to the
        requests.session instance

        Args:
        -----
        method: `str`
            either `POST` or `GET`

        url: `str`
            URL with the endpoint included

        **kwargs:
        These are passed into the requests and include the `params` and `json`
        attributes which are the exact same ones used by requests.

        Returns:
        --------
        The full response in JSON format including `_global_result` AND
        The error if status string returned is not 0, else `None`.
        '''
        logger.info(f'Calling _api_call()')
        logger.info(f"Method is: {method.upper()}")

        response = getattr(self.session, method.lower())(url, verify=self.verify, **kwargs)
        #response.raise_for_status()
        logger.debug(f"Full URL: {response.url}")

        # If response is wrong, for example if someone passes in the wrong
        # endpoint return https://gitlab.ocado.tech/Net-wifi/wireless-passphrase-change/-/merge_requests/2, None for both values
        try:
            jresp = response.json()
            logger.debug(f"Response JSON: {jresp}")
        except json.decoder.JSONDecodeError as e:
            logger.exception(f'Got a JSONDecodeError exception. Check the defined endpoint is correct\n')
            logger.exception(f"Response text:\n{response.text}")
            return None, None

        # Return propper values depending on the type of HTTP request and
        # the response received from it
        if method.lower() == "get":
            return jresp, None
        else:
            if '_global_result' in jresp:
                if jresp["_global_result"]["status"] == 0 or jresp["_global_result"]["status"] == '0':
                    return jresp, None
                else:
                    #logger.debug(f'Error is: {jresp["_global_result"]}')
                    return jresp, jresp["_global_result"]
            else:
                return None, logger.error(f"Config not written: {jresp}")

    @log
    def _login(self):
        '''Login handler to loginto the Mobility Master server.

        Returns:
        --------
        Either the response from the sucesfull login attempt or the error from
        it.
        '''
        logger.info(f"SSL verify (False or cert path): {self.verify}")

        login_url = f'{self.mm_base_api_url}/api/login'

        error_msg = f'Calling _login() with host: {self.mm_host} & username: {self.username}'

        try:
            login_resp, login_resp_err = self._api_call("post", login_url, data=self.login_payload)

        except requests.exceptions.ConnectionError as exc:
            logger.exception(f'Got a {exc.__class__.__name__} exception\n')
            logger.error(error_msg)
            exit(0)
        except requests.RequestException as exc:
            logger.exception(f'Got a {exc.__class__.__name__} exception\n')
            logger.error(error_msg)
            exit(0)
        except requests.HTTPError as exc:
            logger.exception(f'Got a {exc.__class__.__name__} exception\n')
            logger.error(error_msg)
            exit(0)
        except requests.URLRequired as exc:
            logger.exception(f'Got a {exc.__class__.__name__} exception\n')
            logger.error(error_msg)
            exit(0)
        except requests.TooManyRedirects as exc:
            logger.exception(f'Got a {exc.__class__.__name__} exception\n')
            logger.error(error_msg)
            exit(0)
        except requests.ConnectTimeout as exc:
            logger.exception(f'Got a {exc.__class__.__name__} exception\n')
            logger.error(error_msg)
            exit(0)
        except requests.ReadTimeout as exc:
            logger.exception(f'Got a {exc.__class__.__name__} exception\n')
            logger.error(error_msg)
            exit(0)

        # Set the UIDARUBA as the API token
        if not login_resp_err:
            self._access_token = login_resp['_global_result']['UIDARUBA']
            logger.debug(login_resp)

            # Reset logging to ERROR as this method is called through _api_call and
            # is not reset as if it were with by calling resource
            #logzero.loglevel(logging.ERROR)

            return login_resp
        else:
            logger.error("Login failed")
            logger.debug(login_resp_err)

            # Reset logging to ERROR as this method is called through _api_call and
            # is not reset as if it were with by calling resource
            #logzero.loglevel(logging.ERROR)

            return login_resp_err

    @log
    def _kwargs_modify(self, api_endpoint, data=None, **kwargs):
        '''Modifies the `kwargs` depending if either POST-ing data or GET-ing
        it.

        This is used with resource methods where it adds keys to the `kwargs`
        allready passed in.

        Args:
        -----
        api_endpoint: `str`
            The hardcoded endpoint for the specific resource method.
        data: dict, optional
            If data passed in the HTTP method defaults to POST and the
        **kwargs:
            These are passed into `self._params` and used in requests with the
            params attribute.

        Returns:
        --------
        Modified `kwargs` passed in with the method.
        '''
        logger.debug(f'Endpoint: {api_endpoint}')
        logger.debug(f'Data Payload: {data}')

        kwargs['endpoint'] = api_endpoint

        # If data is passed in, the HTTP method is POST with that data
        if data:
            kwargs['method'] = 'POST'
            kwargs['jpayload'] = data
        else:
            kwargs['method'] = 'GET'
            kwargs['search'] = kwargs['endpoint'].split('/')[-1]

        logger.debug(f'kwargs out: {kwargs}')

        return kwargs

    @log
    def logout(self):
        '''Logs out of the current instance of MM

        Returns:
        --------
        The full response in JSON format including `_global_result`

        The error if status string returned is not 0, else it returns None
        '''
        logout_url = f'{self.mm_base_api_url}/api/logout'

        jresp, jresp_err = self._api_call("get", logout_url)

        # Reset logging to ERROR as this method is called through _api_call and
        # is not reset as if it were with by calling resource
        #logzero.loglevel(logging.ERROR)

        return jresp, jresp_err

    @log
    def write_mem(self, config_path=None):
        '''Saves the config at the given `config_path` level.

        Defaults to `/md` if none provided.

        Args:
        -----
        config_path: `str`
            The level at which the config will be saved at.

        Returns:
        --------
        The full response in JSON format including `_global_result`

        The error if status string returned is not 0, else it returns None
        '''
        url = f'{self.mm_base_api_url}/configuration/object/write_memory'
        params = self._params(config_path=config_path)

        jresp, jresp_err = self._api_call("POST", url, params=params)

        return jresp, jresp_err

    @log
    def resource(self, method, endpoint, jpayload=None, **kwargs):
        '''Actiones the HTTP request type defined with the `method` attribute to
        the defined `endpoint`.

        This is the main function of the class, which does all the interfacing
        with the API. It can be called by its own to GET or POST to a resource,
        but the preffered way is to define a resource method below that utilises
        this one for interfacing. The difference between the 2 apporoaches is
        shown in the Examples.

        Args:
        -----
        method: `str`
            Either `GET` or `POST`. Case insensitive.
        endpoint: `str`
            An rendpoint esource path (ex.: "configuration/object/ap_sys_prof").
            Can be with or without the leading `/`.
            The endpoint string is split at `/` and the final list entry used
            as the `search` string used with the `self._params` method.
        jpayload: dict, optional
            JSON formated payload. Same as requests json sent with the body of
            the request. With this passed in, the HTTP method is always POST.
        **kwargs:
            These get passed to the `_params` method, so read what is accepted
            from there.

        Returns:
        --------
        The JSON response and None for error if everything went OK.
        The JSON response and JSON error response in case of the response
        getting an error.

        Examples:
        ---------
        In the examples below the JSON data `apsys_prof` is passed and `aos_obj`
        in an MMClient instance.

        >>> apsys_prof = {
            'bkup_lms_ip': {'bkup-lms-ip': '10.11.11.11'},
            'lms_hold_down_period': {'lms-hold-down-period': 10},
            'lms_ip': {'lms-ip':'10.10.10.11'},
            'lms_preemption': {},
            'profile-name': 'test-01.ap_sys_prof'}

        >>> aos_obj = MMClient()

        **Ex. 1:** Calling a dedicated `/configuration/object/ap_sys_prof` endpoint
        method. (THE PREFFERED WAY)

        a) POST `apsys_prof` data to the '/md/Test_empty' level
        >>> aos_obj.ap_sys_profile(
                data=apsys_prof,
                config_path='/md/Test_empty')

        b) GET the exact ap_sys_profile derfined with
        `profile_name=test-01.ap_sys_prof` at the `/md/Test_empty` level

        >>> aos_obj.ap_sys_profile(
                profile_name='test-01.ap_sys_prof',
                config_path='/md/Test_empty')

        **Ex. 2:** The same as Ex. 1, but with calling the resource method directly.

        a) POST `apsys_prof` data at the '/md/Test_empty' level
        >>> aos_obj.resource(
                'POST',
                endpoint='/configuration/object/ap_sys_prof',
                config_path='/md',
                jpayload=apsys_prof)

        b) GET the exact ap_sys_profile derfined with
        `profile_name=test-01.ap_sys_prof` at the `/md/Test_empty` level

        >>> aos_obj.resource(
                'GET',
                endpoint='configuration/object/ap_sys_prof',
                config_path='/md/Test_empty',
                profile_name='test-01.ap_sys_prof')

        '''
        # Add the 'search' string used with the filter option used by the
        # self._params method.
        # For example this is the last element in the splited endpoint string.
        # For 'configuration/object/ap_sys_prof' this would be 'ap_sys_prof'
        kwargs['search'] = endpoint.split('/')[-1]

        # Get the params from the passed in kwargs
        params = self._params(**kwargs)

        # Build the full URL to the resource
        resource_url = self._resource_url(endpoint)

        # Get the JSON response and error
        jresp, jresp_err = self._api_call(method, resource_url, params=params, json=jpayload)

        # Reset logging to ERROR
        #logzero.loglevel(logging.ERROR)

        return jresp, jresp_err


    '''Below are defined resource methods, which are the ones with a
    hardcoded endpoint object.
    '''
    @log
    def ap_sys_profile(self, data=None, **kwargs):
        '''RM to GET or POST to an `ap_sys_prof` endpoint object.

        If `data` passed method is POST and takes presedence over other
        attributes.

        Args:
        -----
        data: `str`, optional
            JSON formated payload. Same as requests json sent with the body of
            the request. With this passed in, the HTTP method is always POST.
        **kwargs:
            These are passed to `self._kwargs_modify` and `self._params` to
            create a propper request with params.

        Returns:
        --------
        The same as what `self.resource` returns, which is response and
        error or None if no error.
        '''
        logger.debug(f'Data in: {data}')

        kwargs = self._kwargs_modify(
            'configuration/object/ap_sys_prof',
            data,
            **kwargs)

        return self.resource(**kwargs)

    @log
    def wlan_ssid_profile(self, data=None, **kwargs):
        '''RM to GET or POST to an `ssid_prof` endpoint object.

        If `data` passed method is POST and takes presedence over other
        attributes.

        Args:
        -----
        data: `str`, optional
            JSON formated payload. Same as requests json sent with the body of
            the request. With this passed in, the HTTP method is always POST.
        **kwargs:
            These are passed to `self._kwargs_modify` and `self._params` to
            create a propper request with params.

        Returns:
        --------
        The same as what `self.resource` returns, which is response and
        error or None if no error.
        '''
        logger.debug(f'Data in: {data}')

        kwargs = self._kwargs_modify(
            'configuration/object/ssid_prof',
            data,
            **kwargs)

    @log
    def ap_group(self, data=None, **kwargs):
        '''RM to GET or POST to an `ap_group` endpoint object.

        If `data` passed method is POST and takes presedence over other
        attributes.

        Args:
        -----
        profile_name: ``str``, optional
            If passed in, it will search for that profile
        data: `str`, optional
            JSON formated payload. Same as requests json sent with the body of
            the request. With this passed in, the HTTP method is always POST.
        **kwargs:
            These are passed to `self._kwargs_modify` and `self._params` to
            create a propper request with params.

        Returns:
        --------
        The same as what `self.resource` returns, which is response and
        error or None if no error.
        '''
        logger.debug(f'Data in: {data}')

        kwargs = self._kwargs_modify(
            'configuration/object/ap_group',
            data,
            **kwargs)

        return self.resource(**kwargs)

    @log
    def virtual_ap(self, data=None, **kwargs):
        '''RM to GET or POST to an `virtual_ap` endpoint object.

        If `data` passed method is POST and takes presedence over other
        attributes.

        Args:
        -----
        profile_name: ``str``, optional
            If passed in, it will search for that profile
        data: `str`, optional
            JSON formated payload. Same as requests json sent with the body of
            the request. With this passed in, the HTTP method is always POST.
        **kwargs:
            These are passed to `self._kwargs_modify` and `self._params` to
            create a propper request with params.

        Returns:
        --------
        The same as what `self.resource` returns, which is response and
        error or None if no error.
        '''
        logger.debug(f'Data in: {data}')

        kwargs = self._kwargs_modify(
            'configuration/object/virtual_ap',
            data,
            **kwargs)

        return self.resource(**kwargs)

    @log
    def ap_sys_prof(self, data=None, **kwargs):
        '''RM to GET or POST to an `ap_sys_prof` endpoint object.

        If `data` passed method is POST and takes presedence over other
        attributes.

        Args:
        -----
        profile_name: ``str``, optional
            If passed in, it will search for that profile
        data: `str`, optional
            JSON formated payload. Same as requests json sent with the body of
            the request. With this passed in, the HTTP method is always POST.
        **kwargs:
            These are passed to `self._kwargs_modify` and `self._params` to
            create a propper request with params.

        Returns:
        --------
        The same as what `self.resource` returns, which is response and
        error or None if no error.
        '''
        logger.debug(f'Data in: {data}')

        kwargs = self._kwargs_modify(
            'configuration/object/ap_sys_prof',
            data,
            **kwargs)

        return self.resource(**kwargs)

    @log
    def reg_domain_prof(self, data=None, **kwargs):
        '''RM to GET or POST to an `reg_domain_prof` endpoint object.

        If `data` passed method is POST and takes presedence over other
        attributes.

        Args:
        -----
        profile_name: ``str``, optional
            If passed in, it will search for that profile
        data: `str`, optional
            JSON formated payload. Same as requests json sent with the body of
            the request. With this passed in, the HTTP method is always POST.
        **kwargs:
            These are passed to `self._kwargs_modify` and `self._params` to
            create a propper request with params.

        Returns:
        --------
        The same as what `self.resource` returns, which is response and
        error or None if no error.
        '''
        logger.debug(f'Data in: {data}')

        kwargs = self._kwargs_modify(
            'configuration/object/reg_domain_prof',
            data,
            **kwargs)

        return self.resource(**kwargs)

    @log
    def dot11k_prof(self, data=None, **kwargs):
        '''RM to GET or POST to an `dot11k_prof` endpoint object.

        If `data` passed method is POST and takes presedence over other
        attributes.

        Args:
        -----
        profile_name: ``str``, optional
            If passed in, it will search for that profile
        data: `str`, optional
            JSON formated payload. Same as requests json sent with the body of
            the request. With this passed in, the HTTP method is always POST.
        **kwargs:
            These are passed to `self._kwargs_modify` and `self._params` to
            create a propper request with params.

        Returns:
        --------
        The same as what `self.resource` returns, which is response and
        error or None if no error.
        '''
        logger.debug(f'Data in: {data}')

        kwargs = self._kwargs_modify(
            'configuration/object/dot11k_prof',
            data,
            **kwargs)

        return self.resource(**kwargs)

    @log
    def dot11r_prof(self, data=None, **kwargs):
        '''RM to GET or POST to an `dot11r_prof` endpoint object.

        If `data` passed method is POST and takes presedence over other
        attributes.

        Args:
        -----
        profile_name: ``str``, optional
            If passed in, it will search for that profile
        data: `str`, optional
            JSON formated payload. Same as requests json sent with the body of
            the request. With this passed in, the HTTP method is always POST.
        **kwargs:
            These are passed to `self._kwargs_modify` and `self._params` to
            create a propper request with params.

        Returns:
        --------
        The same as what `self.resource` returns, which is response and
        error or None if no error.
        '''
        logger.debug(f'Data in: {data}')

        kwargs = self._kwargs_modify(
            'configuration/object/dot11r_prof',
            data,
            **kwargs)

        return self.resource(**kwargs)

    @log
    def ap_a_radio_prof(self, data=None, **kwargs):
        '''RM to GET or POST to an `ap_a_radio_prof` endpoint object.

        If `data` passed method is POST and takes presedence over other
        attributes.

        Args:
        -----
        profile_name: ``str``, optional
            If passed in, it will search for that profile
        data: `str`, optional
            JSON formated payload. Same as requests json sent with the body of
            the request. With this passed in, the HTTP method is always POST.
        **kwargs:
            These are passed to `self._kwargs_modify` and `self._params` to
            create a propper request with params.

        Returns:
        --------
        The same as what `self.resource` returns, which is response and
        error or None if no error.
        '''
        logger.debug(f'Data in: {data}')

        kwargs = self._kwargs_modify(
            'configuration/object/ap_a_radio_prof',
            data,
            **kwargs)

        return self.resource(**kwargs)

    @log
    def ht_radio_prof(self, data=None, **kwargs):
        '''RM to GET or POST to an `ht_radio_prof` endpoint object.

        If `data` passed method is POST and takes presedence over other
        attributes.

        Args:
        -----
        data: `str`, optional
            JSON formated payload. Same as requests json sent with the body of
            the request. With this passed in, the HTTP method is always POST.
        **kwargs:
            These are passed to `self._kwargs_modify` and `self._params` to
            create a propper request with params.

        Returns:
        --------
        The same as what `self.resource` returns, which is response and
        error or None if no error.
        '''
        logger.debug(f'Data in: {data}')

        kwargs = self._kwargs_modify(
            'configuration/object/ht_radio_prof',
            data,
            **kwargs)

        return self.resource(**kwargs)

    @log
    def node_hierarchy(self, data=None, **kwargs):
        '''RM to GET or POST to an `node_hierarchy` endpoint object.

        If `data` passed method is POST and takes presedence over other
        attributes.

        Args:
        -----
        data: `str`, optional
            JSON formated payload. Same as requests json sent with the body of
            the request. With this passed in, the HTTP method is always POST.
        **kwargs:
            These are passed to `self._kwargs_modify` and `self._params` to
            create a propper request with params.

        Returns:
        --------
        The same as what `self.resource` returns, which is response and
        error or None if no error.
        '''
        logger.debug(f'Data in: {data}')

        kwargs = self._kwargs_modify(
            'configuration/object/node_hierarchy',
            data,
            **kwargs)

        return self.resource(**kwargs)

    @log
    def add_configuration_device(self, data, **kwargs):
        '''RM to GET or POST to an `add_configuration_device` endpoint object.

        If `data` passed method is POST and takes presedence over other
        attributes.

        Args:
        -----
        data: `str`
            JSON formated payload. Same as requests json sent with the body of
            the request. With this passed in, the HTTP method is always POST.
        **kwargs:
            These are passed to `self._kwargs_modify` and `self._params` to
            create a propper request with params.

        Returns:
        --------
        The same as what `self.resource` returns, which is response and
        error or None if no error.
        '''
        logger.debug(f'Data in: {data}')

        kwargs = self._kwargs_modify(
            'configuration/object/add_configuration_device',
            data,
            **kwargs)

        return self.resource(**kwargs)

    @log
    def netdst(self, data=None, **kwargs):
        '''RM to GET or POST to an `netdst` endpoint object.

        If `data` passed method is POST and takes presedence over other
        attributes.

        Args:
        -----
        data: `str`, optional
            JSON formated payload. Same as requests json sent with the body of
            the request. With this passed in, the HTTP method is always POST.
        **kwargs:
            These are passed to `self._kwargs_modify` and `self._params` to
            create a propper request with params.

        Returns:
        --------
        The same as what `self.resource` returns, which is response and
        error or None if no error.
        '''
        logger.debug(f'Data in: {data}')

        kwargs = self._kwargs_modify(
            'configuration/object/netdst',
            data,
            **kwargs)

        return self.resource(**kwargs)

    @log
    def netsvc(self, data=None, **kwargs):
        '''RM to GET or POST to an `netsvc` endpoint object.

        If `data` passed method is POST and takes presedence over other
        attributes.

        Args:
        -----
        data: `str`, optional
            JSON formated payload. Same as requests json sent with the body of
            the request. With this passed in, the HTTP method is always POST.
        **kwargs:
            These are passed to `self._kwargs_modify` and `self._params` to
            create a propper request with params.

        Returns:
        --------
        The same as what `self.resource` returns, which is response and
        error or None if no error.
        '''
        logger.debug(f'Data in: {data}')

        kwargs = self._kwargs_modify(
            'configuration/object/netsvc',
            data,
            **kwargs)

        return self.resource(**kwargs)

    @log
    def acl_sess(self, data=None, **kwargs):
        '''RM to GET or POST to an `acl_sess` endpoint object.

        If `data` passed method is POST and takes presedence over other
        attributes.

        Args:
        -----
        data: `str`, optional
            JSON formated payload. Same as requests json sent with the body of
            the request. With this passed in, the HTTP method is always POST.
        **kwargs:
            These are passed to `self._kwargs_modify` and `self._params` to
            create a propper request with params.

        Returns:
        --------
        The same as what `self.resource` returns, which is response and
        error or None if no error.
        '''
        logger.debug(f'Data in: {data}')

        kwargs = self._kwargs_modify(
            'configuration/object/acl_sess',
            data,
            **kwargs)

        return self.resource(**kwargs)
