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


class VPNTestPlugin(vpnplugin.VShieldEdgeVPNPlugin,
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
        res = self._do_request('GET',
                               _get_path('vpn/' + collection + '/' + id))
        return res[resource]

    def _site_create(self, name="", description="",
                     local_endpoint="10.117.35.202",
                     local_id="10.117.35.202",
                     peer_endpoint="10.117.35.203",
                     peer_id="10.117.35.203",
                     pri_networks=[
                         {'local_subnets': "192.168.1.0/24, 192.168.2.0/24",
                          'peer_subnets': "192.168.11.0/24, 192.168.22.0/24"}
                     ],
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
        LOG.info("test to create site")
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
                {'local_subnets': "192.168.1.0/24,192.168.2.0/24",
                 'peer_subnets': "192.168.11.0/24,192.168.22.0/24"}
            ]
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
        for k in ('id', 'local_endpoint', 'peer_endpoint',
                  'local_id', 'peer_id'):
            self.assertTrue(site.get(k, None))
        self.assertEqual(
            dict((k, v) for k, v in site.items() if k in expected),
            expected
        )
        res = self._get_resource('site', site['id'])
        return site

    def test_update_site(self):
        LOG.info("test to update site")
        expected = {
            'name': 'site1',
            'description': 'description for site1',
            'psk': '123',
            'mtu': 1800,
            'pri_networks': [
                {'local_subnets': "192.168.1.0/24,192.168.2.0/24",
                 'peer_subnets': "192.168.11.0/24,192.168.22.0/24"}
            ]
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
                {'local_subnets': "192.168.1.0/24,192.168.2.0/24",
                 'peer_subnets': "192.168.11.0/24,192.168.22.0/24"}
            ]
        }
        new_site = self._site_update(site['id'], new_expected)
        self.assertEqual(site['id'], new_site['id'])
        self.assertEqual(
            dict((k, v) for k, v in new_site.items() if k in new_expected),
            new_expected
        )
        return new_site

    def test_list_sites(self):
        LOG.info("test to list sites")
        expected = {
            'name': 'site3',
            'description': 'description for site3',
            'psk': '123',
            'mtu': 1800,
            'pri_networks': [
                {'local_subnets': "192.168.1.0/24",
                 'peer_subnets': "192.168.11.0/24"}
            ]
        }
        site = self._site_create(name=expected['name'],
                                 description=expected['description'],
                                 pri_networks=expected['pri_networks'],
                                 psk=expected['psk'],
                                 mtu=expected['mtu'])
        for k in ('id', 'local_endpoint', 'peer_endpoint',
                  'local_id', 'peer_id'):
            self.assertTrue(site.get(k, None))
        self.assertEqual(
            dict((k, v) for k, v in site.items() if k in expected),
            expected
        )
        res = self._get_resources('site')
        print(json.dumps(res, indent=4))
        return res

    def test_delete_site(self):
        LOG.info("test to delete site")
        expected = {
            'name': 'site1',
            'description': 'description for site1',
            'local_endpoint': "10.117.35.202",
            'peer_endpoint': "10.117.35.203",
            'local_id': "10.117.35.202",
            'peer_id': "10.117.35.203",
            'pri_networks': [
                {'local_subnets': "192.168.1.0/24",
                 'peer_subnets': "192.168.11.0/24"}
            ]
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
        LOG.info("test to get sites")
        site1 = self._site_create(name="site 1",
                                  description="description 1",
                                  local_endpoint="10.117.35.202",
                                  local_id="10.117.35.202",
                                  peer_endpoint="10.117.35.203",
                                  peer_id="10.117.35.203",
                                  pri_networks=[
                                      {'local_subnets': "192.168.1.0/24",
                                       'peer_subnets': "192.168.11.0/24"}
                                  ])
        site2 = self._site_create(
            name="site 2",
            description="description 2",
            local_endpoint="10.117.35.202",
            local_id="10.117.35.202",
            peer_endpoint="10.117.35.204",
            peer_id="10.117.35.204",
            pri_networks=[{
                'local_subnets': "192.168.1.0/24,192.168.2.0/24",
                'peer_subnets': "192.168.11.0/24,192.168.22.0/24"}])
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
        LOG.info("test to get stats of site")
        expected = {
            'name': 'site1',
            'description': 'description for site1',
            'local_endpoint': "10.117.35.202",
            'peer_endpoint': "10.117.35.203",
            'local_id': "10.117.35.202",
            'peer_id': "10.117.35.203",
            'pri_networks': [
                {'local_subnets': "192.168.1.0/24",
                 'peer_subnets': "192.168.11.0/24"}
            ]
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

    def _ipsec_policy_create(self, name='ipsec_policy1',
                             enc_alg='aes256', auth_alg='sha1',
                             dh_group='2', life_time=3600,
                             description=None):
        data = {'ipsec_policy': {'name': name,
                                 'tenant_id': self._tenant_id,
                                 'enc_alg': enc_alg,
                                 'auth_alg': auth_alg,
                                 'dh_group': dh_group,
                                 'life_time': life_time}}
        if description:
            data['ipsec_policy']['description'] = description
        res = self._do_request('POST', _get_path('vpn/ipsec_policys'), data)
        return res['ipsec_policy']

    def _ipsec_policy_update(self, id, ipsec_policy=None):
        path = 'vpn/ipsec_policys/{0}'.format(id)
        old_ipsec_policy = self._do_request('GET', _get_path(path), None)
        if ipsec_policy is None:
            return old_ipsec_policy['ipsec_policy']
        data = {
            "ipsec_policy": ipsec_policy
        }
        new_ipsec_policy = self._do_request('PUT', _get_path(path), data)
        return new_ipsec_policy['ipsec_policy']

    def _ipsec_policy_delete(self, id):
        path = 'vpn/ipsec_policys/{0}'.format(id)
        res = self._do_request('DELETE', _get_path(path), None)
        return res

    def test_create_ipsec_policy(self, **extras):
        LOG.info("test to create ipsec policy")
        expected = {
            'name': '',
            'description': '',
            'enc_alg': 'aes256',
            'auth_alg': 'sha1',
            'dh_group': '2',
            'life_time': 3600}
        expected.update(extras)
        ipsec_policy = self._ipsec_policy_create(
            name=expected['name'],
            description=expected['description'],
            enc_alg=expected['enc_alg'],
            auth_alg=expected['auth_alg'],
            dh_group=expected['dh_group'],
            life_time=expected['life_time']
        )
        for k in ('id', 'enc_alg', 'auth_alg',
                  'dh_group', 'life_time'):
            self.assertTrue(ipsec_policy.get(k, None))
        self.assertEqual(
            dict((k, v) for k, v in ipsec_policy.items() if k in expected),
            expected
        )
        res = self._get_resource('ipsec_policy', ipsec_policy['id'])
        return ipsec_policy

    def test_update_ipsec_policy(self):
        LOG.info("test to update ipsec_policy")
        expected = {
            'name': '',
            'description': '',
            'enc_alg': 'aes256',
            'auth_alg': 'sha1',
            'dh_group': '2',
            'life_time': 3600
        }
        ipsec_policy = self._ipsec_policy_create(
            name=expected['name'],
            description=expected['description'],
            enc_alg=expected['enc_alg'],
            auth_alg=expected['auth_alg'],
            dh_group=expected['dh_group'],
            life_time=expected['life_time'])
        new_expected = {
            'name': 'new policy',
            'enc_alg': "aesgcm",
            'dh_group': "5",
            'life_time': 1800
        }
        new_ipsec_policy = self._ipsec_policy_update(ipsec_policy['id'],
                                                     new_expected)
        self.assertEqual(ipsec_policy['id'], new_ipsec_policy['id'])
        self.assertEqual(
            dict((k, v) for k, v in new_ipsec_policy.items()
                 if k in new_expected),
            new_expected
        )
        return new_ipsec_policy

    def test_list_ipsec_policys(self):
        LOG.info("test to list ipsec_policys")
        expected = {
            'name': '',
            'description': '',
            'enc_alg': 'aes256',
            'auth_alg': 'sha1',
            'dh_group': '2',
            'life_time': 3600}
        ipsec_policy = self._ipsec_policy_create(
            name=expected['name'],
            description=expected['description'],
            enc_alg=expected['enc_alg'],
            auth_alg=expected['auth_alg'],
            dh_group=expected['dh_group'],
            life_time=expected['life_time'])
        for k in ('id', 'enc_alg', 'auth_alg',
                  'dh_group', 'life_time'):
            self.assertTrue(ipsec_policy.get(k, None))
        self.assertEqual(
            dict((k, v) for k, v in ipsec_policy.items() if k in expected),
            expected
        )
        res = self._get_resources('ipsec_policy')
        print(json.dumps(res, indent=4))
        return res

    def test_delete_ipsec_policy(self):
        LOG.info("test to delete ipsec_policy")
        expected = {
            'name': '',
            'description': '',
            'enc_alg': 'aes256',
            'auth_alg': 'sha1',
            'dh_group': '2',
            'life_time': 3600}
        ipsec_policy = self._ipsec_policy_create(
            name=expected['name'],
            description=expected['description'],
            enc_alg=expected['enc_alg'],
            auth_alg=expected['auth_alg'],
            dh_group=expected['dh_group'],
            life_time=expected['life_time'])
        ipsec_policy = self._ipsec_policy_delete(id=ipsec_policy['id'])
        return

    def test_get_ipsec_policys(self):
        LOG.info("test to get ipsec_policys")
        ipsec_policy1 = {
            'name': '',
            'description': '',
            'enc_alg': 'aes256',
            'auth_alg': 'sha1',
            'dh_group': '2',
            'life_time': 3600}
        ipsec_policy1_get = self._ipsec_policy_create(
            name=ipsec_policy1['name'],
            description=ipsec_policy1['description'],
            enc_alg=ipsec_policy1['enc_alg'],
            auth_alg=ipsec_policy1['auth_alg'],
            dh_group=ipsec_policy1['dh_group'],
            life_time=ipsec_policy1['life_time'])
        ipsec_policy2 = {
            'name': '',
            'description': '',
            'enc_alg': 'aes256',
            'auth_alg': 'sha1',
            'dh_group': '2',
            'life_time': 1800}
        ipsec_policy2_get = self._ipsec_policy_create(
            name=ipsec_policy2['name'],
            description=ipsec_policy2['description'],
            enc_alg=ipsec_policy2['enc_alg'],
            auth_alg=ipsec_policy2['auth_alg'],
            dh_group=ipsec_policy2['dh_group'],
            life_time=ipsec_policy2['life_time'])
        ipsec_policys = self._get_resources('ipsec_policy')
        self.assertEqual(len(ipsec_policys), 2)
        self.assertEqual(ipsec_policys[0]['name'], ipsec_policy1_get['name'])
        self.assertEqual(ipsec_policys[1]['name'], ipsec_policy2_get['name'])
        self.assertEqual(ipsec_policys[0]['description'],
                         ipsec_policy1_get['description'])
        self.assertEqual(ipsec_policys[1]['description'],
                         ipsec_policy2_get['description'])
        r1 = self._get_resource('ipsec_policy', ipsec_policy1_get['id'])
        r2 = self._get_resource('ipsec_policy', ipsec_policy2_get['id'])
        self.assertEqual(r1['id'], ipsec_policy1_get['id'])
        self.assertEqual(r2['id'], ipsec_policy2_get['id'])

###############################################################################
## Isakmp Policy test
    def _isakmp_policy_create(self, name='isakmp_policy1',
                              auth_mode='psk',
                              enable_pfs=True,
                              enc_alg='aes256', auth_alg='sha1',
                              dh_group='2', life_time=28000,
                              description=None):
        data = {
            'isakmp_policy': {
                'name': name,
                'tenant_id': self._tenant_id,
                'auth_mode': auth_mode,
                'enable_pfs': enable_pfs,
                'enc_alg': enc_alg,
                'auth_alg': auth_alg,
                'dh_group': dh_group,
                'life_time': life_time
            }
        }
        if description:
            data['isakmp_policy']['description'] = description
        res = self._do_request('POST', _get_path('vpn/isakmp_policys'), data)
        return res['isakmp_policy']

    def _isakmp_policy_update(self, id, isakmp_policy=None):
        path = 'vpn/isakmp_policys/{0}'.format(id)
        old_isakmp_policy = self._do_request('GET', _get_path(path), None)
        if isakmp_policy is None:
            return old_isakmp_policy['isakmp_policy']
        data = {
            "isakmp_policy": isakmp_policy
        }
        new_isakmp_policy = self._do_request('PUT', _get_path(path), data)
        return new_isakmp_policy['isakmp_policy']

    def _isakmp_policy_delete(self, id):
        path = 'vpn/isakmp_policys/{0}'.format(id)
        res = self._do_request('DELETE', _get_path(path), None)
        return res

    def test_create_isakmp_policy(self, **extras):
        LOG.info("test to create isakmp policy")
        expected = {
            'name': '',
            'description': '',
            'enc_alg': 'aes256',
            'auth_alg': 'sha1',
            'dh_group': '2',
            'life_time': 3600}
        expected.update(extras)
        isakmp_policy = self._isakmp_policy_create(
            name=expected['name'],
            description=expected['description'],
            enc_alg=expected['enc_alg'],
            auth_alg=expected['auth_alg'],
            dh_group=expected['dh_group'],
            life_time=expected['life_time'])
        for k in ('id', 'enc_alg', 'auth_alg',
                  'dh_group', 'life_time'):
            self.assertTrue(isakmp_policy.get(k, None))
        self.assertEqual(
            dict((k, v) for k, v in isakmp_policy.items() if k in expected),
            expected
        )
        res = self._get_resource('isakmp_policy', isakmp_policy['id'])
        return isakmp_policy

    def test_update_isakmp_policy(self):
        LOG.info("test to update isakmp_policy")
        expected = {
            'name': '',
            'description': '',
            'enc_alg': 'aes256',
            'auth_alg': 'sha1',
            'dh_group': '2',
            'life_time': 3600}
        isakmp_policy = self._isakmp_policy_create(
            name=expected['name'],
            description=expected['description'],
            enc_alg=expected['enc_alg'],
            auth_alg=expected['auth_alg'],
            dh_group=expected['dh_group'],
            life_time=expected['life_time'])
        new_expected = {
            'name': 'new policy',
            'enc_alg': "aesgcm",
            'dh_group': "5",
            'life_time': 1800
        }
        new_isakmp_policy = self._isakmp_policy_update(isakmp_policy['id'],
                                                       new_expected)
        self.assertEqual(isakmp_policy['id'], new_isakmp_policy['id'])
        self.assertEqual(
            dict((k, v) for k, v in new_isakmp_policy.items()
                 if k in new_expected),
            new_expected
        )
        return new_isakmp_policy

    def test_list_isakmp_policys(self):
        LOG.info("test to list isakmp_policys")
        expected = {
            'name': '',
            'description': '',
            'enc_alg': 'aes256',
            'auth_alg': 'sha1',
            'dh_group': '2',
            'life_time': 3600}
        isakmp_policy = self._isakmp_policy_create(
            name=expected['name'],
            description=expected['description'],
            enc_alg=expected['enc_alg'],
            auth_alg=expected['auth_alg'],
            dh_group=expected['dh_group'],
            life_time=expected['life_time'])
        for k in ('id', 'enc_alg', 'auth_alg',
                  'dh_group', 'life_time'):
            self.assertTrue(isakmp_policy.get(k, None))
        self.assertEqual(
            dict((k, v) for k, v in isakmp_policy.items()
                 if k in expected),
            expected
        )
        res = self._get_resources('isakmp_policy')
        print(json.dumps(res, indent=4))
        return res

    def test_delete_isakmp_policy(self):
        LOG.info("test to delete isakmp_policy")
        expected = {
            'name': '',
            'description': '',
            'enc_alg': 'aes256',
            'auth_alg': 'sha1',
            'dh_group': '2',
            'life_time': 3600}
        isakmp_policy = self._isakmp_policy_create(
            name=expected['name'],
            description=expected['description'],
            enc_alg=expected['enc_alg'],
            auth_alg=expected['auth_alg'],
            dh_group=expected['dh_group'],
            life_time=expected['life_time'])
        isakmp_policy = self._isakmp_policy_delete(id=isakmp_policy['id'])
        return

    def test_get_isakmp_policys(self):
        LOG.info("test to get isakmp_policys")
        isakmp_policy1 = {
            'name': '',
            'description': '',
            'enc_alg': 'aes256',
            'auth_alg': 'sha1',
            'dh_group': '2',
            'life_time': 3600}
        isakmp_policy1_get = self._isakmp_policy_create(
            name=isakmp_policy1['name'],
            description=isakmp_policy1['description'],
            enc_alg=isakmp_policy1['enc_alg'],
            auth_alg=isakmp_policy1['auth_alg'],
            dh_group=isakmp_policy1['dh_group'],
            life_time=isakmp_policy1['life_time'])
        isakmp_policy2 = {
            'name': '',
            'description': '',
            'enc_alg': 'aes256',
            'auth_alg': 'sha1',
            'dh_group': '2',
            'life_time': 1800}
        isakmp_policy2_get = self._isakmp_policy_create(
            name=isakmp_policy2['name'],
            description=isakmp_policy2['description'],
            enc_alg=isakmp_policy2['enc_alg'],
            auth_alg=isakmp_policy2['auth_alg'],
            dh_group=isakmp_policy2['dh_group'],
            life_time=isakmp_policy2['life_time'])
        isakmp_policys = self._get_resources('isakmp_policy')
        print "isakmp_policys:"
        print isakmp_policys
        self.assertEqual(len(isakmp_policys), 2)
        self.assertEqual(isakmp_policys[0]['name'], isakmp_policy1_get['name'])
        self.assertEqual(isakmp_policys[1]['name'], isakmp_policy2_get['name'])
        self.assertEqual(isakmp_policys[0]['description'],
                         isakmp_policy1_get['description'])
        self.assertEqual(isakmp_policys[1]['description'],
                         isakmp_policy2_get['description'])
        r1 = self._get_resource('isakmp_policy', isakmp_policy1_get['id'])
        r2 = self._get_resource('isakmp_policy', isakmp_policy2_get['id'])
        self.assertEqual(r1['id'], isakmp_policy1_get['id'])
        self.assertEqual(r2['id'], isakmp_policy2_get['id'])

###############################################################################
## Trust Profile test
    def _trust_profile_create(self, name='',
                              trust_ca='trust_ca',
                              crl='crl',
                              server_cert='server_cert',
                              description=None):
        data = {
            'trust_profile': {
                'name': name,
                'trust_ca': trust_ca,
                'crl': crl,
                'server_cert': server_cert
            }
        }
        if description:
            data['trust_profile']['description'] = description
        res = self._do_request('POST', _get_path('vpn/trust_profiles'), data)
        return res['trust_profile']

    def _trust_profile_update(self, id, trust_profile=None):
        path = 'vpn/trust_profiles/{0}'.format(id)
        old_trust_profile = self._do_request('GET', _get_path(path), None)
        if trust_profile is None:
            return old_trust_profile['trust_profile']
        data = {
            "trust_profile": trust_profile
        }
        new_trust_profile = self._do_request('PUT', _get_path(path), data)
        return new_trust_profile['trust_profile']

    def _trust_profile_delete(self, id):
        path = 'vpn/trust_profiles/{0}'.format(id)
        res = self._do_request('DELETE', _get_path(path), None)
        return res

    def test_create_trust_profile(self, **extras):
        LOG.info("test to create trust profile")
        expected = {
            'name': '',
            'description': '',
            'trust_ca': 'trust_ca',
            'crl': 'crl',
            'server_cert': 'server_cert'}
        expected.update(extras)
        trust_profile = self._trust_profile_create(
            name=expected['name'],
            description=expected['description'],
            trust_ca=expected['trust_ca'],
            crl=expected['crl'],
            server_cert=expected['server_cert'])
        for k in ('id', 'trust_ca', 'crl',
                  'server_cert'):
            self.assertTrue(trust_profile.get(k, None))
        self.assertEqual(
            dict((k, v) for k, v in trust_profile.items() if k in expected),
            expected
        )
        res = self._get_resource('trust_profile', trust_profile['id'])
        return trust_profile

    def test_update_trust_profile(self):
        LOG.info("test to update trust_profile")
        expected = {
            'name': '',
            'description': '',
            'trust_ca': 'trust_ca',
            'crl': 'crl',
            'server_cert': 'server_cert'}
        trust_profile = self._trust_profile_create(
            name=expected['name'],
            description=expected['description'],
            trust_ca=expected['trust_ca'],
            crl=expected['crl'],
            server_cert=expected['server_cert'])
        new_expected = {
            'name': 'new policy',
            'trust_ca': 'new trust_ca',
            'crl': 'new crl',
            'server_cert': 'new server_cert'}
        new_trust_profile = self._trust_profile_update(trust_profile['id'],
                                                       new_expected)
        self.assertEqual(trust_profile['id'], new_trust_profile['id'])
        self.assertEqual(
            dict((k, v) for k, v in new_trust_profile.items()
                 if k in new_expected),
            new_expected
        )
        return new_trust_profile
    def test_list_trust_profiles(self):
         LOG.info("test to list trust_profiles")
         expected = {
             'name': '',
             'description': '',
             'trust_ca': 'trust_ca',
             'crl': 'crl',
             'server_cert': 'server_cert'}
         trust_profile = self._trust_profile_create(
             name=expected['name'],
             description=expected['description'],
             trust_ca=expected['trust_ca'],
             crl=expected['crl'],
             server_cert=expected['server_cert'])
         for k in ('id', 'trust_ca', 'crl',
                   'server_cert'):
             self.assertTrue(trust_profile.get(k, None))
         self.assertEqual(
             dict((k, v) for k, v in trust_profile.items()
                  if k in expected),
             expected
         )
         res = self._get_resources('trust_profile')
         print(json.dumps(res, indent=4))
         return res

    def test_delete_trust_profile(self):
        LOG.info("test to delete trust_profile")
        expected = {
            'name': '',
            'description': '',
            'trust_ca': 'trust_ca',
            'crl': 'crl',
            'server_cert': 'server_cert'}
        trust_profile = self._trust_profile_create(
            name=expected['name'],
            description=expected['description'],
            trust_ca=expected['trust_ca'],
            crl=expected['crl'],
            server_cert=expected['server_cert'])
        trust_profile = self._trust_profile_delete(id=trust_profile['id'])
        return

    def test_get_trust_profiles(self):
        LOG.info("test to get trust profiles")
        trust_profile1 = {
            'name': '',
            'description': '',
            'trust_ca': 'trust_ca1',
            'crl': 'crl1',
            'server_cert': 'server_cert1'}
        trust_profile1_get = self._trust_profile_create(
            name=trust_profile1['name'],
            description=trust_profile1['description'],
            trust_ca=trust_profile1['trust_ca'],
            crl=trust_profile1['crl'],
            server_cert=trust_profile1['server_cert'])
        trust_profile2 = {
            'name': '',
            'description': '',
            'trust_ca': 'trust_ca2',
            'crl': 'crl2',
            'server_cert': 'server_cert2'}
        trust_profile2_get = self._trust_profile_create(
            name=trust_profile2['name'],
            description=trust_profile2['description'],
            trust_ca=trust_profile2['trust_ca'],
            crl=trust_profile2['crl'],
            server_cert=trust_profile2['server_cert'])
        trust_profiles = self._get_resources('trust_profile')
        print "trust_profiles:"
        print trust_profiles
        self.assertEqual(len(trust_profiles), 2)
        self.assertEqual(trust_profiles[0]['name'], trust_profile1_get['name'])
        self.assertEqual(trust_profiles[1]['name'], trust_profile2_get['name'])
        self.assertEqual(trust_profiles[0]['description'],
                         trust_profile1_get['description'])
        self.assertEqual(trust_profiles[1]['description'],
                         trust_profile2_get['description'])
        r1 = self._get_resource('trust_profile', trust_profile1_get['id'])
        r2 = self._get_resource('trust_profile', trust_profile2_get['id'])
        self.assertEqual(r1['id'], trust_profile1_get['id'])
        self.assertEqual(r2['id'], trust_profile2_get['id'])
