import requests
import xmltodict
import pprint
import socket
import logging
import getpass

import logging
import logzero
from logzero import logger


class OnlyOneInstance(type):
    """Metaclass that allows only one class instance to be created
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(OnlyOneInstance, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


# Class to connect to the Aruba Airwave management system
class AirWave(metaclass=OnlyOneInstance):
    """All Aruba Mobility Master API URIs are found on https://mm-host/api/
    and are accessible if logged in.

    Only the ``aw_url`` is mandatory and username and password will be asked for
    when calling the ``comms()`` method if not provided.

    Parameters
    ----------
    aw_url: `str`
        The URL of the AirWave instance

    aw_username: `str`, optional
        A username for loggin in to AirWave. Although optional it is required
        and will be prompetd for if not passed in.

    aw_password: `str`, optional
        Password for the provided username. Although optional it is required
        and will be prompetd for if not passed in.

    verify: bool or string, optional, deafult false
        Specify how SSL verification will be handled. Handling is done same way
        as with requests, so either:
        - leave blank or use False (bool) to disable OR
        - specify path to a cert file to enable

    Examples:
    ---------
    **Ex. 1:** Importing the AirWave module

    >>> from arubafi import AirWave
    >>> aw = AirWave(
            aw_url="my.airwave.com",
            aw_username="a-username",
            aw_password="a-pass")
    >>> aw.comms()

    **Ex. 2:** Not passing in username or password
    In this case you are asked for username and password or you can provide one
    or both when creating a new instance.

    from arubafi import AirWave
    aw = AirWave(aw_url="my.airwave.com")

    Airwave username required. Should I use `your.username` to continue [Y/n]?
    AirWave Password required:
    <arubatools.airwave.AirWave at 0x112a92dd0>
    """
    def __init__(self, aw_url, aw_username=str(), aw_password=str(), verify=False):
        self.aw_url = str(aw_url)
        self.aw_username = str(aw_username)
        self.aw_password = str(aw_password)
        self.verify = verify

        # URLs used with AirWave to get client data and to login
        if "https://" not in self.aw_url:
            self.aw_url = f"https://{self.aw_url}"
        login_url = self.aw_url + '/LOGIN'

    def comms(self):
        """User prompt for getting username and/or password, if they haven't been
        passed in
        """
        if not self.aw_username:
            #
            # If user is not set, ask for it, but get the password regardless of the answer
            #
            system_user = getpass.getuser()
            user_input = input(f"Airwave username required. Should `{system_user}` be used [Y/n]?")

            # Option for a user if they want to specify a username
            if user_input.lower() == "n":
                #kwargs.update({ 'username': input("Username:\x20") })
                self.aw_username = input("AirWave username:\x20")
            # ...any other answer, just use their current username
            else:
                self.aw_username = system_user

            # Specify the password for the user regardless of it being set
            self.aw_password = getpass.getpass("AirWave Password required:\x20")

        if not self.aw_password:
            #
            # If password is not set, get the username to log into and ask the user
            # for the password for that user
            self.aw_password = getpass.getpass(f"AirWave Password for user `{self.aw_username}` required:\x20")

        # The login credentials dictionary
        self.login_payload = {
            'destination': '/',
            'credential_0': self.aw_username,
            'credential_1': self.aw_password
        }

        # Create a session object
        self.session = requests.Session()

        try:
            login_resp = self.session.post(login_url, data=self.login_payload, verify=self.verify, timeout=30)
            # Raise an exception if the status code != 2xx
            login_resp.raise_for_status()
            # If there is no raise response you're authenticated!

        except requests.RequestException as exc:
            print('There was an ambiguous exception that occurred while handling your request.\n' + str(exc))
        except requests.ConnectionError as exc:
            print('Failed to connect to API:\t' + str(exc))
        except requests.HTTPError(*args, **kwargs) as exc:
            print('An HTTP error occurred.\n' + str(exc))
        except requests.URLRequired as exc:
            print('A valid URL is required to make a request.')
        except requests.TooManyRedirects as exc:
            print('Too many redirects.\n' + str(exc))



    #
    ##
    ### Health Methods
    ### Take care of helthy checks and such
    ##
    #
    def close(self):
        """Function that just closes the AirWave session
        """
        self.session.close()

    def _dns_ptr_check(self, addr):
        """Returns either `FQDN` of an IP or `None` which signifies missing PTR
        """
        try:
            get_response = socket.gethostbyaddr(addr)
            logging.debug(get_response)

            # Fix for the Apline Python docker image
            if get_response[0] == addr:
                return None, None, None

            return get_response

        except socket.herror:
            return None, None, None




    #
    ##
    ### Inventory Methods
    ### These just get the DB dicts from AirWave output
    ### Do NOT call these methods directly, but use associated ``get_`` methods instead
    ##
    #
    def _full_raw_airwave_inventory(self):
        """Returns the WHOLE inventory in a dict (APs, IAPs, controllers and VCs) as returned
        by passing in ~/ap_list.xml without any parameters
        """
        if not hasattr(self, '_inventory') or not self._inventory:

            ap_list_url = self.aw_url + '/ap_list.xml'

            response = self.session.get(ap_list_url, timeout=30)
            # Raise an exception if the status code != 2xx
            response.raise_for_status()

            # Convert the XML client_detail_resp into a dictionary
            self._inventory = xmltodict.parse(response.content)

        #print(self._inventory)
        return self._inventory

    def _create_inventory_dbs(self):
        """Creates inventory dictionaries (DBs), split into dicts for APs/IAPs, controllers
        and virtual cotrollers

        GET the DB by calling associated ``get_*`` methods

        Creates:
        - controller_id to controller_fqdn mapping
        - VC_id to VC_fqdn mapping
        - controller_id to ap_name mapping
        - ap_name to controller_id mapping
        - controller_id to controller_fqdn mapping
        - controller_id to controller_name mapping
        - DB for controllers with no FQDN (missing PTR record)
        """

        # controller_id to controller_fqdn mapping
        self._controllers_db = dict()
        # VC_id to VC_fqdn mapping
        self._iapvc_db = dict()
        # controller_id to ap_name mapping
        self._contrlollerid_to_ap_db = dict()
        # ap_name to controller_id mapping
        self._apname_to_controllerid_db = dict()
        # All standalone APs with no controllermanagement
        self._controllerless_ap_db = dict()
        # DB for controllers with no FQDN (missing PTR record)
        # controller_id to controller_name mapping
        self._no_ptr_controllers_db = dict()
        # A DB for every item with an ID and another dict for various values
        self._all_items_db = dict()


        # get the full AMP inventory dict
        amp_inventory = self._full_raw_airwave_inventory()
        #pprint.pprint(amp_inventory)

        # Iterate through all items and asign them to their respective DB dict
        for item in amp_inventory["amp:amp_ap_list"]["ap"]:

            #pprint.pprint(item)
            item_data = self._all_items_db.setdefault(item["@id"], {})

            item_data["lan_ip"] = item.get("lan_ip")
            item_data["lan_mac"] = item.get("lan_mac")
            item_data["name"] = item.get("name")
            item_data["serial_number"] = item.get("serial_number")
            item_data["device_category"] = item.get("device_category")
            item_data["controller_id"] = item.get("controller_id")
            item_data["fqdn"] = item.get("fqdn")
            item_data["manufacturer"] = item.get("mfgr")
            item_data["model"] = item.get("model", {}).get("#text")
            item_data["is_rap"] = item.get("is_remote_ap")



            # Add @id and controller_fqdn as key/value to the _controllers_db
            # if controller is a "normal" controller
            if "controller" in item["device_category"] and "Instant Virtual Controller" not in item['model']['#text']:

                #try getting controllers FQDN, but if key does not exists...
                try:
                    self._controllers_db[item['@id']] = item['fqdn']
                    #print('FQDN', item['@id'], item['fqdn'])
                # ... Try finding it's FQDN via its IP address
                except KeyError:
                    controller_ip = item["lan_ip"]
                    controller_fqdn = self._dns_ptr_check(controller_ip)
                    #print(controller_fqdn)
                    if controller_fqdn[0]:
                        self._controllers_db[item['@id']] = controller_fqdn[0]
                        #print(controller_fqdn[0])1
                    else:
                        self._no_ptr_controllers_db[controller_ip] = item["name"]
                        #print(item["name"])

                    #print("WARNING: no FQDN for {}".format(item["name"]))

            # Add @id and iapvc_fqdn as key/value to the _iapvc_db
            # if the controller is a virtual IAP controller
            elif "controller" in item['device_category'] and "Instant Virtual Controller" in item['model']['#text']:
                self._iapvc_db[item['@id']] = item['fqdn']

            # if item is AP & managed by a controller...
            elif "thin_ap" in item['device_category'] and "controller_id" in item:

                # if the controller_id is not in the dict
                # put it there with a default empty list
                k = item['controller_id']
                self._contrlollerid_to_ap_db.setdefault(item_data["controller_id"], [])
                # Put the AP in the list next to the controller_id
                self._contrlollerid_to_ap_db[k].append(item_data["name"])

                # Put the ap_name with its controller_id into the dict
                self._apname_to_controllerid_db[item_data["name"]] = item_data["controller_id"]


            # if item is AP and is not managed by a controller
            # i.e. it doesn't have a `controller_id`
            elif not "controller_id" in item and not "controller" in item_data["device_category"]:
                # Put it into the controllerless AP database with
                # its own id and its name (AP name)
                self._controllerless_ap_db[item['@id']] = item['name']

    def _controller_inventory(self):
        """Returns the `self._controllers_db` dict with
        controller ID to controller FQDN key value mappings

        Call `get_controller_inventory()` to get the output of this.
        """

        if not hasattr(self, '_controllers_db') or not self._controllers_db:
            self._create_inventory_dbs()

        return self._controllers_db

    def _no_ptr_controller_inventory(self):
        """Returns the `self._no_ptr_controllers_db` dict with
        controller IP to controller NAME key value mappings

        Call `get_no_ptr_controller_inventory()` to get the output of this.
        """
        if not hasattr(self, '_no_ptr_controllers_db') or not self._no_ptr_controllers_db:
            self._create_inventory_dbs()

        return self._no_ptr_controllers_db

    def _iapvc_inventory(self):
        """Returns the `self._iapvc_db` dict with
        controller_id to controller_FQDN key value mappings

        Call `get_iapvc_inventory()` to get the output of this.
        """
        if not hasattr(self, '_iapvc_db') or not self._iapvc_db:
            self._create_inventory_dbs()

        return self._iapvc_db

    def _controllerid_to_ap_inventory(self):
        """Returns the `self._contrlollerid_to_ap_db` dict with
        AP_NAME to controller_ID key value mappings

        Call `get_controllerid_to_ap_inventory()` to get the output of this.
        """
        if not hasattr(self, '_contrlollerid_to_ap_db') or not self._contrlollerid_to_ap_db:
            self._create_inventory_dbs()

        return self._contrlollerid_to_ap_db

    def _apname_to_controllerid_inventory(self):
        """Returns the `self._apname_to_controllerid_db` dict with
        AP_NAME to controller_ID key value mappings

        Call `get_apname_to_controllerid_inventory()` to get the output of this.
        """
        if not hasattr(self, '_apname_to_controllerid_db') or not self._apname_to_controllerid_db:
            self._create_inventory_dbs()

        return self._apname_to_controllerid_db

    def _controllerless_ap_inventory(self):
        """Returns the filled in `self._controllerless_ap_db`

        Call `get_ap_inventory()` to get the output of this.
        """
        if not hasattr(self, '_controllerless_ap_db') or not self._controllerless_ap_db:
            self._create_inventory_dbs()

        return self._controllerless_ap_db

    def _all_items_inventory(self):
        """Returns the filled in `self._all_items_db`

        Call `get_all_items_inventory()` to get the output of this.
        """
        if not hasattr(self, '_all_items_db') or not self._all_items_db:
            self._create_inventory_dbs()

        return self._all_items_db


    #
    ##
    ### GET inventory methods
    ### These return a full DB of elements specified within them
    ##
    #
    def get_controller_inventory(self):
        """Returns a dict with controller's @id as key and FQDN as value
        as returned by accessing the AirWave/ap_list.xml without any parameters.

        Example output:

        controllers_db = {
            '1064': 'loop0-cont01.blah.com',
            '1069': 'loop0-cont02.blah.com',
            '1072': 'loop0-cont03.blah.com',
            '1090': 'loop0-cont04.blah.com',
            '1116': 'loop0-cont05.blah.com'
        }
        """
        return self._controller_inventory()

    def get_no_ptr_controller_inventory(self):
        """Returns a dict with controller's @id as key and NAME
        as value as returned by accessing the AirWave/ap_list.xml without any parameters.

        Example output:

        {'10.238.3.4': 'aa-wi0',
         '10.254.44.19': 'bb-wi0',
         '10.254.44.21': 'cc-wi1'}
        """
        #print(self._controller_inventory())
        return self._no_ptr_controller_inventory()

    def get_iapvc_inventory(self):
        """Returns a dict with controller's @id as key and NAME
        as value as returned by accessing the AirWave/ap_list.xml without any parameters.

        Example output:

        {
            '1627': 'th-iapvc0.blah.com'
        }
        """
        return self._iapvc_inventory()

    def get_controllerid_to_ap_inventory(self):
        """Returns a dict with controller @id as key and its list of associated APS
        as returned by accessing the AirWave/ap_list.xml without any parameters.

        Example output:

        {
            '1865': ['ap501', 'ap502', 'ap503'],
            '367': ['ap164','ap165','ap167','ap161','ap162','ap163']
        }
        """
        return self._controllerid_to_ap_inventory()

    def get_apname_to_controllerid_inventory(self):
        """Returns a dict with AP `name` as key and its `controller @id` as value
        as returned by accessing the AirWave/ap_list.xml without any parameters.

        DB contains ALL APs controlled by any type of controller (VC or mobility switch)

        Example output:

        {
            'ap160.zv': '1901',
            'ap120': '1703',
            'ap130': '1901',
            'ap153': '1901',
        }
        """
        return self._apname_to_controllerid_inventory()

    def get_controllerless_ap_inventory(self):
        """
        Returns the AP NAME inventory in a list as returned by by accesing the
        AirWave/ap_list.xml without any parameters.

        Example output:

        {
            '1106': 'ap12',
            '1109': 'ap13',
            '1394': 'ap31',
            '1399': 'ap183',
            '527': 'ap33',
            '808': 'ap17',
            '948': 'ap20'
        }
        """
        return self._controllerless_ap_inventory()

    def get_all_items_inventory(self):
        """
        Returns the inventory with dist of ALL items from AW within it

        Example output:

        {
        '101': {
            'lan_ip': '10.22.50.106',
            'lan_mac': '00:01:86:C2:dd:aa',
            'name': 'ap54',
            'serial_number': '345309345',
            'device_category': 'thin_ap',
            'controller_id': '17',
            'fqdn': 'ap54',
            'manufacturer': 'Aruba',
            'model': 'AP 70',
            'is_rap': 'false'
            },

        '1687': {
            'lan_ip': '10.254.104.21',
            'lan_mac': '00:4C:f3:35:C2:aC',
            'name': 'wi0',
            'serial_number': '345345345',
            'device_category': 'controller',
            'controller_id': None,
            'fqdn': 'wi0-loop.blah.com',
            'manufacturer': 'Aruba',
            'model': '7010',
            'is_rap': None
            },
        }


        """
        return self._all_items_inventory()




    #
    ##
    ### GET specific elements methods
    ### These return a a subset of elements from the DB dicts produced by
    ### the _*() methods of elements specified within them
    ##
    #
    def get_users_ap_info(self, users_mac, printout=True):
        """
        Gets the AP to which the user is connected to, by passing
        in the `user_mac`

        Example output:

        {
            'ap_id': '1868',
            'name': 'ap502',
            'radio': 'a',
            'essid': 'blah',
            'vlan': '610',
            'client_aw_url': 'https://test.airwave.com/client_detail.xml?mac=33%3Add%34ff%3Aaa%3Abb%3A11',
            'controller_id': '1865',
            'client_count': '17',
            'firmware': '6.5.4.9',
            'ap_fqdn': 'ap502.blah.com',
            'lan_ip': '10.22.72.12',
            'lan_mac': '20:A6:be:C5:3f:d2',
            'model': 'AP 305',
            'operating_mode': 'ap',
            'serial_number': 'FGBTG345345',
            'ap_aw_url': 'https://test.airwave.com/ap_list.xml?id=1868',
        }
        """
        # URLs used with Airvawe to get client and client's AP data
        client_detail_url = self.aw_url + '/client_detail.xml'
        ap_list_url = self.aw_url + '/ap_list.xml'

        self.users_ap_info = dict()
        self.user_mac = {'mac': users_mac.upper()}


        # Make a call to AW with users MAC address
        #
        client_detail_resp = self.session.get(client_detail_url, params=self.user_mac, timeout=30)
        client_detail_resp.raise_for_status()
        #pprint.pprint(client_detail_resp.request.url)
        #pprint.pprint(client_detail_resp.content)

        # Convert the XML client_detail_resp into a dictionary
        amp_client_detail = xmltodict.parse(client_detail_resp.content)
        #pprint.pprint(amp_client_detail['amp:amp_client_detail'])

        # Populate the users_ap_info database with information but check for errors
        # and if the client exists in the first place
        if "client" in amp_client_detail['amp:amp_client_detail'] and amp_client_detail['amp:amp_client_detail']['client']['assoc_stat'] == 'true':

            # Make a shoter version of amp_client_detail['amp:amp_client_detail']['client']
            # for easier asignment to users_ap_info dict
            client_ap_bulk = amp_client_detail['amp:amp_client_detail']['client']

            self.users_ap_info['ap_id']  = client_ap_bulk['ap'].get('@id')
            self.users_ap_info['name']   = client_ap_bulk['ap'].get('#text')
            self.users_ap_info['radio']  = client_ap_bulk.get('radio_mode')
            self.users_ap_info['essid']  = client_ap_bulk.get('ssid')
            self.users_ap_info['vlan']   = client_ap_bulk.get('vlan')
            self.users_ap_info['client_aw_url'] = client_detail_resp.request.url


            # Make another call to AW, this time with the ID of the AP to get more info
            # on it including the controllers FQDN and ID
            #
            ap_detail_response = self.session.get(ap_list_url, params={'id': self.users_ap_info['ap_id']}, timeout=30)
            #print(ap_detail_response.content)
            ap_detail_response.raise_for_status()
            #print(ap_detail_response.request.url)

            # Convert the XML ap_detail_response into a dictionary
            ap_detail = xmltodict.parse(ap_detail_response.content)['amp:amp_ap_list']['ap']
            #pprint.pprint(ap_detail)

            self.users_ap_info['controller_id']  = ap_detail.get('controller_id')
            self.users_ap_info['client_count']   = ap_detail.get('client_count')
            self.users_ap_info['firmware']       = ap_detail.get('firmware')
            self.users_ap_info['ap_fqdn']        = ap_detail.get('fqdn')
            self.users_ap_info['lan_ip']         = ap_detail.get('lan_ip')
            self.users_ap_info['lan_mac']        = ap_detail.get('lan_mac')
            self.users_ap_info['model']          = ap_detail['model'].get('#text')
            self.users_ap_info['operating_mode'] = ap_detail.get('operating_mode')
            self.users_ap_info['serial_number']  = ap_detail.get('serial_number')
            self.users_ap_info['ap_aw_url']      = ap_detail_response.request.url


            if printout:
                print("AirWave Client URL:\t{}".format(self.users_ap_info['client_aw_url']))
                print("AirWave client assoc AP:{}".format(self.users_ap_info['name']))
                print("AirWave client's ESSID:\t{}".format(self.users_ap_info['essid']))
                print("AirWave client's radio:\t{}".format(self.users_ap_info['radio']))
                print("AirWave client's VLAN:\t{}".format(self.users_ap_info['vlan']))

        elif 'error' in amp_client_detail['amp:amp_client_detail']:
            print("This MAC {} is not valid!".format(users_mac))
            print(amp_client_detail['amp:amp_client_detail']['error'])

        else:
            print("Couldn't get data from AirWave for client: {}".format(users_mac))

        #print(users_ap_info)
        return self.users_ap_info

    def get_users_controller_info(self, users_mac=str(), users_ap_controller_id=str()):
        """Gets the controller's FQDN to which the `users_ap_controller_id` is connected to.

        `users_ap_controller_id` is output from self.get_users_ap_info()

        Example output:

        {
            'lan_ip': '10.23.9.12',
            'lan_mac': '20:3f:da:42:23:76',
            'name': 'wi11',
            'serial_number': '3543543567',
            'device_category': 'controller',
            'controller_id': None,
            'fqdn': 'wi11-loop.blah.com',
            'manufacturer': 'Aruba',
            'model': '7030',
            'is_rap': None
        }

        """
        # If you don't pass in the controller Id on which to check on,
        # we need to get it from the passed in users MAC or
        # from a previous event that caused the creation of `self.users_ap_info` variable
        if not users_ap_controller_id:
            if hasattr(self, 'users_ap_info'):
                ap_info = self.users_ap_info
            elif users_mac:
                ap_info = self.get_users_ap_info(users_mac, printout=False)
            else:
                print("Can't get controller ID if you don't give me users MAC address or it's controller Id!")
                return

            return self.get_all_items_inventory()[ap_info['controller_id']]

        else:
            return self.get_all_items_inventory()[users_ap_controller_id]

    def get_controller_fqdn_list(self):
        """Returns a set of all mobility switch controllers FQDNs

        Example output:
        {
            'aa-wi0-loop.blah.com',
            'ab-wi0-loop.blah.com',
            'ac-wi0-loop.blah.com',
            ...
        }
        """
        cinv = self.get_controller_inventory()
        cfqdn = set()

        for controller in cinv.values():
            cfqdn.add(controller)

        return cfqdn

    def get_single_aps_controllerid(self, ap_name=str()):
        """Returns a controllers `@id` to which the AP `ap_name` is associated with.

        `ap_name` is string
        """

        ap_db = self.get_apname_to_controllerid_inventory()

        if ap_name not in ap_db:
            return None

        # Return AP's controller `@id`
        return ap_db[ap_name]

    def get_multiple_aps_controllerid(self, ap_names=None):
        """Returns a list of controllers `@id` or `None` to which the list of APs passed in belong to

        `ap_names` is list
        """
        ap_db = self.get_apname_to_controllerid_inventory()
        ctrl_ids = set()

        if ap_names and isinstance(ap_names, list):
            { ctrl_ids.add(ap_db[ap]) for ap in ap_names if ap in ap_db }

        # Return AP's controller's `@id`
        return ctrl_ids

    # METHODS THAT NEED WORK ARE FROM HERE DOWN TO THE END
    def get_iapvcs_aps(self):
        """Returns a dict with VCs' FQDN as keys and list of their APs as values.

        INCLUDES VCs ONLY!

        Example output:

        iapvc_aps = {

            {'th-iapvc0.blah.com': ['th-iap01']}
        }
        """
        """
        iapvc_aps = {}

        # Write key from `iapvc_db` as key and value from `ap_db` as value into `iapvc_aps`
        for k in iapvc_db.keys(), ap_db.values():
            # ...If key found in both
            if k in v:
                # Write the AP name at key position
                iapvc_aps[iapvc_db[k]] = ap_db[k]

        return iapvc_aps
        """
        pass

    def get_controllers_aps(self):
        """Returns a list of APs belonging to the 'controller' (passed in as FQDN

        DOES NOT return APs that belong to VCs

        Example output:

        controller_aps = {

            'loop0-cont01.blah.com': ['ap01'],

            'loop0-cont02.blah.com': [
                'ap01',
                'ap09',
                'ap06',
                'ap13',
                'ap05',
                'ap02',
                'ap07',
            ],
            ...
        }
        """

        # Get relevant databases
        controller_inventory_db = self.get_controller_inventory()
        #print(controller_inventory_db)
        contid_to_aplist_db = self.get_controllerid_to_ap_inventory()
        #print(contid_to_aplist_db)

        # dict with relevant controllers and their AP list
        cnames_to_aps_db = dict()

        # Write value@key from `controller_inventory_db` as key and value@key from `ap_db`
        # as value into `controller_aps`
        for cid, controller in controller_inventory_db.items():
            if contid_to_aplist_db.get(cid):
                cnames_to_aps_db[controller] = contid_to_aplist_db[cid]

        return cnames_to_aps_db

    def get_aps_controller(self, ap_name):
        """
        Returns a controllers `@id` to which the AP `ap_name` is associated with.

        You can use this response for getting the controllers FQDN or IP from the other DBs
        """

        aps_controller = ""
        ap_db = self.get_apname_to_controllerid_inventory()

        if ap_name in ap_db:
            #print(ap_db[ap_name])
            controller_id = ap_db[ap_name]

        # Return AP's controller's `@id`
        return aps_controller
