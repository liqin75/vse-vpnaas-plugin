#!/usr/bin/python

import json
from vsmapi import VsmAPI


class VseAPI():

    def __init__(self, address, user, password, edgeId):
        self.vsmapi = VsmAPI(address, user, password)
        self.edgeId = edgeId
        self.configId = 0

    def vsmconfig(self, method, uri, params=None):
        print "VseAPI('{}', '{}', '{}')".format(
            method, uri, json.dumps(params))
        resp, content = self.vsmapi.api(method, uri, params)
        print "header: '{}'".format(resp)
        print "content: '{}'".format(content)
        if int(resp['status']) / 100 != 2:
            raise Exception(json.dumps(resp) + "\n" + content)
        if content == '':
            return {}
        return json.loads(content)

    def api(self, method, uri, params=None):
        content = self.vsmconfig(method, uri, params)
        if method.upper() is not "GET":
            self.vsm2os()
        return content

    def get_edgeId(self):
        return self.edgeId

    def get_vsm_config(self):
        uri = '/api/3.0/edges/{}'.format(self.edgeId)
        resp, content = self.vsmapi.api('GET', uri)
        if int(resp['status']) != 200:
            raise Exception(json.dumps(resp))

        return content

    def get_vse_config(self):
        uri = '/api/3.0/edges/{}/json'.format(self.edgeId)
        resp, content = self.vsmapi.api('GET', uri)
        if int(resp['status']) / 100 != 2:
            raise Exception(json.dumps(resp))

        return content
