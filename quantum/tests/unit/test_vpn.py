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
#import logging
from quantum.openstack.common import log as logging
from oslo.config import cfg
import webob.exc as webexc

import quantum
from quantum.api import extensions
from quantum.api.v2 import router
from quantum.common import config
from quantum import context as q_context
from quantum.db import api as db
from quantum.db import db_base_plugin_v2
from quantum.plugins.vmware.vshield import vpnplugin
from quantum.plugins.common import constants
from quantum.tests import base
from quantum.tests.unit import test_api_v2
from quantum.tests.unit import testlib_api
from quantum import wsgi

_uuid = test_api_v2._uuid
_get_path = test_api_v2._get_path
extensions_path = ':'.join(quantum.extensions.__path__)

LOG = logging.getLogger(__name__)

class VPNTestPlugin(
    vpnplugin.VShieldEdgeVPNPlugin,
    db_base_plugin_v2.QuantumDbPluginV2):

    supported_extension_aliases = ["vpnaas"]
    """
    def create_site(self, context, site, **kwargs):
        r = super(VPNTestPlugin, self).create_site(
            context, site)
        return r

    def get_sites(self, context, filters=None, fields=None):
        r = super(VPNTestPlugin, self).get_sites(
            context, filters, fields)
        return r

    def get_site(self, context, id, fields=None):
        r = super(VPNTestPlugin, self).get_site(
            context, id, fields)
        return r
    """

class VPNTestCase(base.BaseTestCase):
    def setUp(self):
        super(VPNTestCase, self).setUp()
        plugin = ("quantum.tests.unit.test_vpn.VPNTestPlugin")

        # point config file to: quantum/tests/etc/quantum.conf.test
        args = ['--config-file', test_api_v2.etcdir('quantum.conf.test')]
        config.parse(args=args)

        #just stubbing core plugin with VPN plugin
        cfg.CONF.set_override('core_plugin', plugin)
        cfg.CONF.set_override('service_plugins', [plugin])
        self.addCleanup(cfg.CONF.reset)

        # Ensure 'stale' patched copies of the plugin are never returned
        quantum.manager.QuantumManager._instance = None

        # Ensure the database is reset between tests
        db._ENGINE = None
        db._MAKER = None
        db.configure_db()
        # Ensure existing ExtensionManager is not used

        ext_mgr = extensions.PluginAwareExtensionManager(
            extensions_path,
            {constants.VPN: VPNTestPlugin()}
        )
        extensions.PluginAwareExtensionManager._instance = ext_mgr
        router.APIRouter()

        app = config.load_paste_app('extensions_test_app')
        self._api = extensions.ExtensionMiddleware(app, ext_mgr=ext_mgr)

        self._tenant_id = "8c70909f-b081-452d-872b-df48e6c355d1"
        self._subnet_id = "0c798ed8-33ba-11e2-8b28-000c291c4d14"

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
        res = self._do_request('GET', _get_path('vpn/') + collection)
        return res[collection]

    def _get_resource(self, resource, id):
        collection = resource + 's'
        res = self._do_request('GET', _get_path('vpn/' + collection + '/' + id))
        return res[resource]

    def _site_create(self, name="", description="",
                     local_endpoint="10.117.35.202", local_id="10.117.35.202",
                     peer_endpoint="10.117.35.203", peer_id="10.117.35.203",
                     pri_networks = [
                        {
                           'local_subnets': "192.168.1.0/24,192.168.2.0/24",
                           'peer_subnets': "192.168.11.0/24,192.168.22.0/24"
                        }],
                      psk="123",
                      mtu="1500",
                      location=None):
        data = {
            "site": {
                "tenant_id": self._tenant_id,
                "subnet_id": self._subnet_id,
                "name": name,
                "description": description,
                "local_endpoint": local_endpoint,
                "peer_endpoint": peer_endpoint,
                "local_id": local_id,
                "peer_id": peer_id,
                "pri_networks": pri_networks,
                "psk": psk,
                "mtu": mtu
            }
        }

        if location:
            data['site']['location'] = location
        res = self._do_request('POST', _get_path('vpn/sites'), data)
        return res['site']

    def _site_update(self, id, site=None):
        path = 'vpn/sites/{0}'.format(id)
        old_site = self._do_request('GET', _get_path(path), None)
        if site is None:
            return old_site['site']
        data = {
            "site": site
            }
        new_site = self._do_request('PUT', _get_path(path), data)
        return new_site['site']


    def _site_delete(self, id):
        path = 'vpn/sites/{0}'.format(id)
        res = self._do_request('DELETE', _get_path(path), None)
        return res

    def _stats(self, id):
        path = 'vpn/sites/{0}/stats'.format(id)
        res = self._do_request('GET', _get_path(path), None)
        return res


    def test_create_site(self, **extras):
        LOG.info("test to create site");
        expected = {
            'name': 'site1',
            'description': '',
            'local_endpoint': "10.117.35.202",
            'peer_endpoint': "10.117.35.203",
            'local_id': "10.117.35.202",
            'peer_id': "10.117.35.203",
            'psk': 'hello123',
            'mtu': 1500,
            'pri_networks': [
               {
                  'local_subnets': "192.168.1.0/24,192.168.2.0/24",
                  'peer_subnets': "192.168.11.0/24,192.168.22.0/24"
               }]
            }
        expected.update(extras)
        site = self._site_create(name=expected['name'],
                                 description=expected['description'],
                                 local_endpoint=expected['local_endpoint'],
                                 local_id=expected['local_id'],
                                 peer_endpoint=expected['peer_endpoint'],
                                 peer_id=expected['peer_id'],
                                 pri_networks=expected['pri_networks'],
                                 psk=expected['psk'],
                                 mtu=expected['mtu'])
        for k in ('id','local_endpoint','peer_endpoint','local_id','peer_id'):
            self.assertTrue(site.get(k, None))
        self.assertEqual(
            dict((k, v) for k, v in site.items() if k in expected),
            expected
        )
        res = self._get_resource('site', site['id'])
        return site

    def test_update_site(self):
        LOG.info("test to update site");
        expected = {
            'name': 'site1',
            'description': 'description for site1',
            'psk': '123',
            'mtu': 1800,
            'pri_networks': [
               {
                  'local_subnets': "192.168.1.0/24,192.168.2.0/24",
                  'peer_subnets': "192.168.11.0/24,192.168.22.0/24"
               }]
            }
        site = self._site_create(name=expected['name'],
                                 description=expected['description'],
                                 pri_networks=expected['pri_networks'],
                                 psk=expected['psk'],
                                 mtu=expected['mtu'])
        new_expected = {
            'name': 'site2',
            'description': 'new description for site1',
            'psk': '234',
            'mtu': 1800,
            'pri_networks': [
               {
                  'local_subnets': "192.168.1.0/24,192.168.2.0/24",
                  'peer_subnets': "192.168.11.0/24,192.168.22.0/24"
               }]
            }
        new_site = self._site_update(site['id'], new_expected)
        self.assertEqual(site['id'], new_site['id'])
        self.assertEqual(
            dict((k, v) for k, v in new_site.items() if k in new_expected),
            new_expected
        )
        return new_site

    def test_list_sites(self):
        LOG.info("test to list sites");
        expected = {
            'name': 'site3',
            'description': 'description for site3',
            'psk': '123',
            'mtu': 1800,
            'pri_networks': [
               {
                'local_subnets': "192.168.1.0/24",
                'peer_subnets': "192.168.11.0/24"
               }]
            }
        site = self._site_create(name=expected['name'],
                                 description=expected['description'],
                                 pri_networks=expected['pri_networks'],
                                 psk=expected['psk'],
                                 mtu=expected['mtu'])
        for k in ('id','local_endpoint','peer_endpoint','local_id','peer_id'):
            self.assertTrue(site.get(k, None))
        self.assertEqual(
            dict((k, v) for k, v in site.items() if k in expected),
            expected
        )
        res = self._get_resources('site')
        print(json.dumps(res, indent=4))
        return res


    def test_delete_site(self):
        LOG.info("test to delete site");
        expected = {
            'name': 'site1',
            'description': 'description for site1',
            'local_endpoint': "10.117.35.202",
            'peer_endpoint': "10.117.35.203",
            'local_id': "10.117.35.202",
            'peer_id': "10.117.35.203",
            'pri_networks': [
               {
                  'local_subnets': "192.168.1.0/24",
                  'peer_subnets': "192.168.11.0/24"
               }]
            }
        site = self._site_create(name=expected['name'],
                                 description=expected['description'],
                                 local_endpoint=expected['local_endpoint'],
                                 local_id=expected['local_id'],
                                 peer_endpoint=expected['peer_endpoint'],
                                 peer_id=expected['peer_id'],
                                 pri_networks=expected['pri_networks']
                                 )
        site = self._site_delete(id=site['id'])
        return


    def test_get_sites(self):
        LOG.info("test to get sites");
        site1 = self._site_create(name="site 1",
                                  description="description 1",
                                  local_endpoint="10.117.35.202",
                                  local_id="10.117.35.202",
                                  peer_endpoint="10.117.35.203",
                                  peer_id="10.117.35.203",
                                  pri_networks=[{
                                       'local_subnets': "192.168.1.0/24",
                                       'peer_subnets': "192.168.11.0/24"
                                    }]
                                  )
        site2 = self._site_create(name="site 2",
                            description="description 2",
                            local_endpoint="10.117.35.202",
                            local_id="10.117.35.202",
                            peer_endpoint="10.117.35.204",
                            peer_id="10.117.35.204",
                            pri_networks=[{
                              'local_subnets': "192.168.1.0/24,192.168.2.0/24",
                              'peer_subnets': "192.168.11.0/24,192.168.22.0/24"
                              }]
                            )
        sites = self._get_resources('site')
        self.assertEqual(len(sites), 2)
        self.assertEqual(sites[0]['name'], site1['name'])
        self.assertEqual(sites[1]['name'], site2['name'])
        self.assertEqual(sites[0]['description'], site1['description'])
        self.assertEqual(sites[1]['description'], site2['description'])
        r1 = self._get_resource('site', site1['id'])
        r2 = self._get_resource('site', site2['id'])
        self.assertEqual(r1['id'], site1['id'])
        self.assertEqual(r2['id'], site2['id'])


    def test_stats(self):
        LOG.info("test to get stats of site");
        expected = {
            'name': 'site1',
            'description': 'description for site1',
            'local_endpoint': "10.117.35.202",
            'peer_endpoint': "10.117.35.203",
            'local_id': "10.117.35.202",
            'peer_id': "10.117.35.203",
            'pri_networks': [
               {
                  'local_subnets': "192.168.1.0/24",
                  'peer_subnets': "192.168.11.0/24"
               }]
            }
        site = self._site_create(name=expected['name'],
                                 description=expected['description'],
                                 local_endpoint=expected['local_endpoint'],
                                 local_id=expected['local_id'],
                                 peer_endpoint=expected['peer_endpoint'],
                                 peer_id=expected['peer_id'],
                                 pri_networks=expected['pri_networks']
                                 )
        res = self._stats(id=site['id'])
        return
