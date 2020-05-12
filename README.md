[![Downloads](https://pepy.tech/badge/arubafi)](https://pepy.tech/project/arubafi)

# Table Of Contents

-   [What is arubafi?](#what-is-arubafi)
-   [Installation](#installation)

# What is arubafi?

Arubafi is a scalable and easy to use Python module capable of interfacing with Aruba's APIs.

The module is intended for network reliability engineers that need to automate various tasks with regards to deployed, or soon to be deployed Aruba hardware or virtual appliances.

# Installation

The module can be pip installed with
```
pip install arubafi
```
or probably using `pip3` if having both Py2 and Py3 installed.

The module is then imported with
```python
import arubafi
```
but it is suggested you import the module you need for a specific task.
For example if you need to work only with AirWave import just that, like so
```python
from arubafi import AirWave
```
# Usage workflow

The usage workflow intended is:
1. Create an object instance.
2. Initiate communication with the `comms()` method.
3. Interface with the API with the provided methods.

# Mobility Master API

Below is an explanation of to get up and running with the Mobility Master API (aka. Aruba OS8 for wireless)

The minimum required for this option is to create an instance without any attributes like below.
```python
mmc = MMClient()
```
In this case, after calling the `comms()` method you are asked for the MM's FQDN, username and password.

You can provide one or both when creating a new instance and be asked about the other once the `comms()` method is run.

You can also provide one or all required attributes at instantiation.
```python
mmc = MMClient(aw_username="theuser")
```

There are various other parameters you can use with the instance object, like port, proxy, api version, etc. You can read more about them in the docstring.

## Communicating with the Mobility Master
You must call the `comms()` method on your instance, to setup the communication with your MM.
```python
aw = comms()
```

## Using methods to get data
For getting the data from your MM, you use the resource methods or the `resource` method itself. In either case you might need to pass in some arguments and for using the `resource` method itself, you will definitely need to pass in at least the method and endpoint from which you want to retrieve data.

The inbuilt resource methods begin their docsting with `RM` and are named as the endpoint as defined with Aruba API. For example, you use the `ap_group()` method to get data about AP groups at a certain `config_path` level from the `configuration/object/ap_group` URI. These methods are pretty similar to the `resource` one otherwise, but are here for easier (more human readable) interfacing with the API.

**Ex.: Comparison between resource methods and the resource method itself**
The below example shows that RMs use the resource() method with correct arguments passed in to GET or POST the data from an endpoint.
```Python
>>> mm.ap_group() == mm.resource(method='GET', endpoint='configuration/object/ap_group')
True
```

**Ex: Basic getting of data**
The below will return all defined AP groups at the `/md` config level.
```python
>>> mm.ap_group()
"({'_data': {'ap_group': [{'profile-name': 'default', '_flags': ...."
```
### Config level
The default config level (specified with the `config_path`) is `/md` unless specified otherwise.
```python
mm.ap_group(config_path='/md/mylevel_A/mylevel_B')
```

### Filtering
Filters are activated when passing in a `profile_name` argument. If specifying only that though the filter will default to `$eq` (equals), so the `profile_name` must match what you are looking for

```python
>>> mm.ap_group(profile_name='default') == mm.ap_group(profile_name='default', filter_oper='$eq')
True
```

You can pass in a `filter_oper` with the `profile_name` if you wish to have a different search option or if passing in a partial search string.
**Ex. 1: partial search string with $in**
This will return all profiles with `def` in their profile-name.
```python
mm.ap_group(profile_name='def', filter_oper='$in')
```
**Ex. 2: partial search string with $nin**
This will return all profiles that `def` is NOT in their profile-name.
```python
mm.ap_group(profile_name='def', filter_oper='$nin')
```

You can even pass in the whole filter with the `filter` argument if you so wish. If using that it will override whichever else you wanted to use as a filter, i.e. The `profile_name` and `filter_oper` will be ignored in this case, as in the end the previous examples construct the same string as the example below has passed into it, but whereas you can only look for profile names with the `profile_name` and `filter_oper`, you can filter on anything else with the `filter` parameter.
**Ex. 3: Passing in the whole filter**
This will return all profiles that `def` is NOT in their profile-name.
```python
mm.ap_group(filter='[ {"ap_group.profile-name" : { "$eq" : ["default"] } } ]')
```

For more information on how to use Aruba filters read the docstring and the associated Aruba API documentation.

## Debugging

The default debug level is `ERROR`, which can be changed per method call by preempting it with `logzero.loglevel(logging.LEVEL)` where `LEVEL` is the logging level. Each method then resets logging to `ERROR`, so you need to set logging level before each one.

**Ex. 1: DEBUG level**
```python
>>> logzero.loglevel(logging.DEBUG)
>>> mm.write_mem()
[I 200503 21:38:12 mmclient:506] Calling write_mem()
[I 200503 21:38:12 mmclient:237] Calling _params()
[D 200503 21:38:12 mmclient:281] Returned params: {'config_path': None, 'UIDARUBA': 'N2EyMDU5NGItZjRiYy00M2JhLWFjOTgtZWJk'}
[I 200503 21:38:12 mmclient:334] Calling _api_call()
[I 200503 21:38:12 mmclient:335] Method is: POST
[I 200503 21:38:12 mmclient:336] SSL verify (False or cert path): False
[D 200503 21:38:12 mmclient:340] Full URL: https://your_host:4343/v1/configuration/object/write_memory?UIDARUBA=N2EyMDU5NGItZjRiYy00M2JhLWFjOTgtZWJk
[D 200503 21:38:12 mmclient:346] Response JSON: {'write_memory': {'_result': {'status': 0, 'status_str': 'Success'}}, '_global_result': {'status': 0, 'status_str': 'Success', '_pending': False}}
```
**Ex. 2: INFO level**
```python
>>> logzero.loglevel(logging.INFO)
>>> mm.write_mem()
[I 200503 21:39:22 mmclient:506] Calling write_mem()
[I 200503 21:39:22 mmclient:237] Calling _params()
[I 200503 21:39:22 mmclient:334] Calling _api_call()
[I 200503 21:39:22 mmclient:335] Method is: POST
[I 200503 21:39:22 mmclient:336] SSL verify (False or cert path): False
```

# AirWave API

AirWaves API is quite different to what you could expect from a modern day one as it practically doesn't have any endpoints. There are about three available if not mistaken and only 2 of those are currently being used by this module, the `/client_detail.xml` and `/ap_detail.xml`.

Note here that the returned data is in XML format, but that is handled by the module and for the resource methods data is retuned in JSON (dictionary) format. There is an option to get the data in the original XML format, with the use of the `_full_raw_airwave_inventory()` method with a `return_in_dict` argument set to `False`, but it would be surprising if you'd need to use that at all.

The very important thing to remember here is that once you want to access any of the resource methods that get you the required database from AW, like `get_controller_inventory()`, which returns the database of the controller's id and it's FQDN mappings for example, ALL other databases are built as well. This is due to AW returning the whole DB of every element it holds when accessing the `/ap_detail.xml`, which can take tens of seconds to complete, depending on the number of elements in your AW and the hardware supporting it. Therefore it is much more efficient to build all DBs that the module returns at first call to any of the `get_` methods than for each one. Also due to this the AW class is made so that only one instance can be made in a script, so as to not overburden the AW with unnecessary calls.

The minimum required for this option is to create an instance without any attributes like below.
```python
aw = AirWave()
```
In this case, after calling the `comms()` method you are asked for the AW's FQDN, username and password.

You can provide one or both when creating a new instance and be asked about the other once the `comms()` method is run.

You can also provide one or all required attributes at instantiation.
```python
aw = AirWave(aw_username="theuser")
```

## Communicating with the Mobility Master
You must call the `comms()` method on your instance, to setup the communication with your MM.
```python
aw = comms()
```

## Additional

There are various other parameters you can use with the instance object, like port, proxy, api version, etc. You can read more about them in the docstring.

##Debugging

The default debug level is `ERROR`, which can be changed per method call by preempting it with `logzero.loglevel(logging.LEVEL)` where `LEVEL` is the logging level. Each method then resets logging to `ERROR`, so you need to set logging level before each one.

**Ex. 1: DEBUG level**
```python
>>> logzero.loglevel(logging.DEBUG)
>>> mm._controller_inventory()
```
**Ex. 2: INFO level**
```python
>>> logzero.loglevel(logging.INFO)
>>> mm._controller_inventory()
```

# TODO
The general TODO list is:
- add more/all Aruba systems
- add mora/all API URIs

# Contributing
Thank you for helping us develop `arubafi`. We're happy to accept contribution of any kind. Feel free to submit feature requests and bug reports under Issues.

## Submitting a pull request guidelines

- All pull requests require a code review.
- Any merge conflicts need to be resolved.
- Include unit tests when you contribute new features and bugs, as they help to a) prove that your code works correctly, and b) guard against future breaking changes to lower the maintenance cost.
- All tests need to pass before we will review your PR.
- When you respond to changes based on comments from a code review, please reply with "Done." so that we get a notification.

## Contributors
- [Ben Cardy](https://github.com/benbacardi)
- [Primoz Marinsek](https://github.com/pmarinsek)
