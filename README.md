# Arubafi

Arubafi is a highly scalable Python module enabling full interfacing with the Mist RestAPI.

## Motivation

To provide a scalable, easy to use and easy to contribute to module that will be able to interface to the fullest with the Mist Systems cloud for wired and wireless.

# Installation

The module can be pip installed

```
pip install arubafi
```
or using `pip3` if using python3.

The module is imported with
```python
import arubafi
```
but it is suggested you import the module you need for a specific task.
For example if you need to work only with AIrWave import just that without
```python
from arubafi import AirWave
```
# Usage

The usage workflow intended is:
1. Create an instance with passing in the cloud and authentication options.
2. Initiate communication with the `comms()` method.
3. Interface with the API with the use of either a specific endpoint method (like `wlans()` for example) or the `resource()` method.

## Create an instance

**Ex: Using username and password.**

The minimum required for this option is to create an instance without any attributes like below.
```python
mm = MMClient()
```
In this case you are asked for username and password.

You can provide one or both when creating a new instance and be asked about the other once the `comms()` method is run.

```python
mm = MMClient(aw_username="theuser")
```

## Communicating with the Mobility Master
You must call the `comms()` method on your instance, to setup the communication with AirWave
```python
aw = comms()
```

## Interfacing with the cloud URIs
If a specific resource method for a specific URI is not defined the main method that can be used is the `resource()` one. The resource methods defined start with `Resource method` in the docstring.

For example, GET-ing `/self` can be achieved by either the `resource()` method or the `whoami()` one.
```python
>>> whoami = mist_user.whoami()
>>> rwhoami = mist_user.resource("GET", uri="/self")
>>> print(whoami == rwhoami)
True
```

# Additional
##Debugging

The default debug level is `ERROR`, which can be changed per method call by preempting it with `logzero.loglevel(logging.LEVEL)` where `LEVEL` is the debug level.
Each method then resets logging to `ERROR`, so you need to set logging level before each one.

**Ex. 1: DEBUG level**
```python
>>> logzero.loglevel(logging.DEBUG)
>>> mist_user.whoami()
```
```
efdsd
```

**Ex. 2: INFO level**
```python
>>> logzero.loglevel(logging.INFO)
>>> mist_user.whoami()
```
```
[I 200326 14:58:23 mistifi:547] Calling whoami()
[I 200326 14:58:23 mistifi:548] kwargs in: {}
[I 200326 14:58:23 mistifi:511] Calling resource()
[I 200326 14:58:23 mistifi:471] Calling _params()
[I 200326 14:58:23 mistifi:472] kwargs in: {'uri': '/self'}
[I 200326 14:58:23 mistifi:395] Calling _resource_url()
[I 200326 14:58:23 mistifi:396] kwargs in: {'uri': '/self'}
[I 200326 14:58:23 mistifi:333] Calling _api_call()
[I 200326 14:58:23 mistifi:334] Method is: GET
[I 200326 14:58:23 mistifi:335] Calling URL: https://api.mist.com/api/v1/self
[I 200326 14:58:23 mistifi:346] Response status code: 200
```

**Ex. 3: Examples of error output**
Here no log level was set.
```python
>>> mist_user.whoami()
```
```
[E 200326 14:58:24 mistifi:351] Response Error:
    {"detail":"Method \"GET\" not allowed."}
[E 200326 14:58:24 mistifi:351] Response Error:
    {"detail":"CSRF Failed: CSRF token missing or incorrect."}
```

# TODO
The general TODO list is:
- add more/all URIs

# Contributing
Thank you for helping us develop Mistifi. We're happy to accept contribution of any kind. Feel free to submit feature requests and bug reports under Issues.

## Submitting a pull request guidelines

- All pull requests require a code review.
- Any merge conflicts needs to be resolved.
- Include unit tests when you contribute new features and bugs, as they help to a) prove that your code works correctly, and b) guard against future breaking changes to lower the maintenance cost.
- All tests needs to pass before we will review your PR.
- When you respond to changes based on comments from a code review, please reply with "Done." so that we get a notification.

## Contributors
- [Ben Cardy](https://github.com/benbacardi)
- [Primoz Marinsek](https://github.com/pmarinsek)
