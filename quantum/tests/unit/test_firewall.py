# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 VMware, Inc. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json
from oslo.config import cfg
import testtools
import webob.exc as webexc

import quantum
from quantum.api import extensions
from quantum.api.v2 import attributes
from quantum.api.v2 import router
from quantum.common import config
from quantum import context as q_context
from quantum.db import api as db
from quantum.db import db_base_plugin_v2
from quantum.db import firewall_db as fw_db
from quantum.plugins.common import constants
from quantum.tests import base
from quantum.tests.unit import test_api_v2
from quantum.tests.unit import testlib_api
from quantum import wsgi

_uuid = test_api_v2._uuid
_get_path = test_api_v2._get_path
extensions_path = ':'.join(quantum.extensions.__path__)


class FirewallTestPlugin(
    fw_db.FirewallPluginDb,
    db_base_plugin_v2.QuantumDbPluginV2):

    supported_extension_aliases = ["fwaas"]

    """
    def create_rule(self, context, rule, **kwargs):
        r = super(FirewallTestPlugin, self).create_rule(
            context, rule)
        return r

    def get_rules(self, context, filters=None, fields=None):
        r = super(FirewallTestPlugin, self).get_rules(
            context, filters, fields)
        return r

    def get_rule(self, context, id, fields=None):
        r = super(FirewallTestPlugin, self).get_rule(
            context, id, fields)
        return r

    def create_ipobj(self, context, ipobj):
        with context.session.begin(subtransactions=True):
            r = super(FirewallTestPlugin, self).create_ipobj(
                context, ipobj) 
        return r

    def get_ipobjs(self, context, filters=None, fields=None):
        r = super(FirewallTestPlugin, self).get_ipobjs(
            context, filters, fields)
        return r

    def get_ipobj(self, context, id, fields=None):
        r = super(FirewallTestPlugin, self).get_ipobj(
            context, id, fields)
        return r

    def create_serviceobj(self, context, serviceobj):
        with context.session.begin(subtransactions=True):
            r = super(FirewallTestPlugin, self).create_serviceobj(
                context, serviceobj) 
        return r

    def create_zone(self, context, zone):
        with context.session.begin(subtransactions=True):
            r = super(FirewallTestPlugin, self).create_zone(
                context, zone) 
        return r
    """


class FirewallTestCase(base.BaseTestCase):
    def setUp(self):
        super(FirewallTestCase, self).setUp()
        plugin = ("quantum.tests.unit.test_firewall.FirewallTestPlugin")

        # point config file to: quantum/tests/etc/quantum.conf.test
        args = ['--config-file', test_api_v2.etcdir('quantum.conf.test')]
        config.parse(args=args)

        #just stubbing core plugin with LoadBalancer plugin
        cfg.CONF.set_override('core_plugin', plugin)
        cfg.CONF.set_override('service_plugins', [plugin])
        self.addCleanup(cfg.CONF.reset)

        # Ensure 'stale' patched copies of the plugin are never returned
        quantum.manager.QuantumManager._instance = None

        # Ensure the database is reset between tests
        db._ENGINE = None
        db._MAKER = None
        # Ensure existing ExtensionManager is not used

        ext_mgr = extensions.PluginAwareExtensionManager(
            extensions_path,
            {constants.FIREWALL: FirewallTestPlugin()}
        )
        extensions.PluginAwareExtensionManager._instance = ext_mgr
        router.APIRouter()

        app = config.load_paste_app('extensions_test_app')
        self._api = extensions.ExtensionMiddleware(app, ext_mgr=ext_mgr)

        self._tenant_id = "8c70909f-b081-452d-872b-df48e6c355d1"

    def _do_request(self, method, path, data=None, params=None, action=None):
        content_type = 'application/json'
        body = None
        if data is not None:  # empty dict is valid
            body = wsgi.Serializer().serialize(data, content_type)

        req = testlib_api.create_request(
            path, body, content_type,
            method, query_string=params)
        req.environ['quantum.context'] = q_context.Context('', self._tenant_id)
        res = req.get_response(self._api)
        if res.status_code >= 400:
            raise webexc.HTTPClientError(detail=res.body, code=res.status_code)
        if res.status_code != webexc.HTTPNoContent.code:
            return res.json

    def _get_resources(self, resource):
        collection = resource + 's'
        res = self._do_request('GET', _get_path('firewall/') + collection)
        return res[collection]

    def _get_resource(self, resource, ipobj_id):
        collection = resource + 's'
        res = self._do_request('GET', _get_path('firewall/' + collection + '/' + ipobj_id))
        return res[resource]

    def _rule_create(self, name="", description="", location=None):
        zone1 = self._zone_create()
        zone2 = self._zone_create()
        sipobj1 = self._ipobj_create()
        sipobj2 = self._ipobj_create()
        dipobj1 = self._ipobj_create()
        dipobj2 = self._ipobj_create()
        svcobj1 = self._serviceobj_create()
        svcobj2 = self._serviceobj_create()
        data = {
            "rule": {
                "tenant_id": self._tenant_id,
                "name": name,
                "description": description,
                "source": {
                    "addresses": ["10.0.0.1", "10.0.1.0/24", "10.0.2.1-10.0.2.100"],
                    "ipobjs": [sipobj1['id'], sipobj2['id']],
                    "zone": zone1['id']
                },
                "destination": {
                    "addresses": ["20.0.0.1", "20.0.1.0/24", "20.0.2.1-20.0.2.100"],
                    "ipobjs": [dipobj1['id'], dipobj2['id']],
                    "zone": zone2['id']
                },
                "service": {
                    "serviceobjs": [svcobj1['id'], svcobj2['id']],
                    "services": [
                        {
                            "protocol": "tcp",
                            "ports": [80, 8080]
                        },
                        {
                            "protocol": "tcp",
                            "sourcePorts": [80, 8080]
                        },
                        {
                            "protocol": "icmp",
                            "types": ["echo", "reply", 6]
                        }
                    ]
                },
                "action": "accept",
                "log": "enabled",
                "enabled": True
            }
        }

        uri = 'firewall/rules'
        if location:
            data['rule']['location'] = location
        res = self._do_request('POST', _get_path('firewall/rules'), data)
        return res['rule']

    def _ipobj_create(self):
        data = {
            "ipobj": {
                "tenant_id": self._tenant_id,
                "name": "test ipobj",
                "description": "test ipobj",
                "value": [
                   "10.0.0.1", "10.0.1.0/24", "10.0.2.0-10.0.2.100"
                ]
            }
        }

        res = self._do_request('POST', _get_path('firewall/ipobjs'), data)
        return res['ipobj']

    def _serviceobj_create(self):
        data = {
            "serviceobj": {
                "tenant_id": self._tenant_id,
                "name": "test serviceobj",
                "description": "test serviceobj",
                "value": [
                    {
                        "protocol": "tcp",
                        "ports": ["80", "443"]
                    },
                    {
                        "protocol": "tcp",
                        "sourcePorts": ["1-1024"],
                        "ports": ["80", "443"]
                    },
                    {
                        "protocol": "icmp",
                        "types": ["echo", "reply"]
                    }
                ]
            }
        }
        res = self._do_request('POST', _get_path('firewall/serviceobjs'), data)
        return res['serviceobj']

    def _zone_create(self):
        data = {
            'zone': {
                "tenant_id": self._tenant_id,
                "name": "test zone",
                "description": "test zone",
                "value": [
                    "c2fea071-ffb4-4917-87a2-c684be9ecf25",
                    "b3a8992b-5c07-4199-a1ac-173652d70ede",
                    "fed7e5c8-bf42-4766-ad34-0ffe7e0ab893"
                ]
            }
        }
        res = self._do_request('POST', _get_path('firewall/zones'), data)
        return res['zone']

    """
    def test_rule_create2(self):
        rule = self._rule_create("rule", "description")

    def test_rule_create(self):
        rule1 = self._rule_create()
        rule2 = self._rule_create("rule 2", "description 2", rule1['id'])
    """

    def test_rules_get(self):
        rule1 = self._rule_create("rule 1", "description 1")
        rule2 = self._rule_create("rule 3", "description 2")
        rule3 = self._rule_create("rule 4", "description 3")
        rule5 = self._rule_create("rule 5", "description 4")
        rule4 = self._rule_create("rule 2", "description 5", rule5['id'])
        rules = self._get_resources('rule')
        self.assertEqual(len(rules), 5)
        self.assertEqual(rules[0]['name'], rule1['name'])
        self.assertEqual(rules[1]['name'], rule2['name'])
        self.assertEqual(rules[2]['name'], rule3['name'])
        self.assertEqual(rules[3]['name'], rule4['name'])
        self.assertEqual(rules[4]['name'], rule5['name'])
        self.assertEqual(rules[0]['description'], rule1['description'])
        self.assertEqual(rules[1]['description'], rule2['description'])
        self.assertEqual(rules[2]['description'], rule3['description'])
        self.assertEqual(rules[3]['description'], rule4['description'])
        self.assertEqual(rules[4]['description'], rule5['description'])
        r1 = self._get_resource('rule', rule1['id'])
        r2 = self._get_resource('rule', rule2['id'])
        r3 = self._get_resource('rule', rule3['id'])
        r4 = self._get_resource('rule', rule4['id'])
        r5 = self._get_resource('rule', rule5['id'])
        self.assertEqual(r1['id'], rule1['id'])
        self.assertEqual(r2['id'], rule2['id'])
        self.assertEqual(r3['id'], rule3['id'])
        self.assertEqual(r4['id'], rule4['id'])
        self.assertEqual(r5['id'], rule5['id'])

    def test_ipobj_create(self):
        ipobj = self._ipobj_create()
        ipobjs = self._get_resources('ipobj')
        self.assertEqual(len(ipobjs), 1)
        self.assertEqual(ipobjs[0]['id'], ipobj['id'])
        ipobj2 = self._get_resource('ipobj', ipobj['id'])
        self.assertEqual(ipobj['id'], ipobj2['id'])
        #print json.dumps(ipobjs[0], indent=4)

    def test_serviceobj_create(self):
        svcobj = self._serviceobj_create()
        svcobjs = self._get_resources('serviceobj')
        self.assertEqual(len(svcobjs), 1)
        self.assertEqual(svcobjs[0]['id'], svcobj['id'])
        svcobj2 = self._get_resource('serviceobj', svcobj['id'])
        self.assertEqual(svcobj['id'], svcobj2['id'])
        #print json.dumps(svcobj2, indent=4)

    def test_zone_create(self):
        zone = self._zone_create()
        zones = self._get_resources('zone')
        self.assertEqual(len(zones), 1)
        self.assertEqual(zones[0]['id'], zone['id'])
        zone2 = self._get_resource('zone', zone['id'])
        self.assertEqual(zone['id'], zone2['id'])
        #print json.dumps(zone2, indent=4)
