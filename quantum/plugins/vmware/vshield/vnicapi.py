#!/usr/bin/python

import json

class VNicAPI():

    def __init__(self, vse):
        self.vse = vse

    def convert(self, vnic):
        rtn = {
            'addressGroups': {
                'addressGroups': [{
                    'primaryAddress': vnic['ip'],
                    'subnetMask': vnic['netmask']
                }]
            },
            'name': vnic['name'],
            'index': vnic['index']
        }
        return rtn

    def config(self, vnics):
        request = {
            'vnics': [
            ]
        }
        for vnic in vnics:
            request['vnics'].append(self.convert(vnic))

        uri = '/api/3.0/edges/{}/vnics/?action=patch'.format(self.vse.get_edgeId())
        content = self.vse.api('POST', uri, request)
        print "VNicAPI.preconfig: '{}'".format(content)
