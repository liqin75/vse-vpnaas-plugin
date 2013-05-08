# Copyright (c) 2012 OpenStack Foundation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import contextlib
import logging
import mock
import os
import testtools

from oslo.config import cfg
import webob.exc

from quantum import context
from quantum.api.extensions import ExtensionMiddleware
from quantum.api.extensions import PluginAwareExtensionManager
from quantum.api.v2 import attributes
from quantum.api.v2.router import APIRouter
from quantum.common import config
from quantum.common import exceptions as q_exc
from quantum.common.test_lib import test_config
from quantum.db import api as db
from quantum.db.vpn import vpn_db as ldb
import quantum.extensions
from quantum.extensions import vpn
from quantum.manager import QuantumManager
from quantum.plugins.common import constants
from quantum.plugins.services.agent_vpn import VPNPlugin
from quantum.tests.unit import test_db_plugin
from quantum.tests.unit import test_extensions
from quantum.tests.unit import testlib_api
from quantum.tests.unit.testlib_api import create_request
from quantum import wsgi


LOG = logging.getLogger(__name__)

DB_CORE_PLUGIN_KLASS = 'quantum.db.db_base_plugin_v2.QuantumDbPluginV2'
DB_VPN_PLUGIN_KLASS = (
    "quantum.plugins.services.agent_vpn.VPNPlugin.VPNPlugin"
)
ROOTDIR = os.path.dirname(__file__) + '../../../..'
ETCDIR = os.path.join(ROOTDIR, 'etc')

extensions_path = ':'.join(quantum.extensions.__path__)


def etcdir(*p):
    return os.path.join(ETCDIR, *p)


class VPNPluginDbTestCase(test_db_plugin.QuantumDbPluginV2TestCase):
    resource_prefix_map = dict(
        (k, constants.COMMON_PREFIXES[constants.VPN])
        for k in vpn.RESOURCE_ATTRIBUTE_MAP.keys()
    )

    def setUp(self, core_plugin=None, vpn_plugin=None):
        service_plugins = {'vpn_plugin_name': DB_VPN_PLUGIN_KLASS}

        super(VPNPluginDbTestCase, self).setUp(
            service_plugins=service_plugins
        )

        self._subnet_id = "0c798ed8-33ba-11e2-8b28-000c291c4d14"

        self.plugin = VPNPlugin.VPNPlugin()
        ext_mgr = PluginAwareExtensionManager(
            extensions_path, {constants.VPN: self.plugin}
        )
        app = config.load_paste_app('extensions_test_app')
        self.ext_api = ExtensionMiddleware(app, ext_mgr=ext_mgr)

    def _create_site(self, fmt, name, local_endpoint, peer_endpoint,
                     local_id, peer_id, pri_networks, psk, mtu,
                     expected_res_status=None, **kwargs):
        data = {'site': {'name': name,
                         'tenant_id': self._tenant_id,
                         'local_endpoint': local_endpoint,
                         'peer_endpoint': peer_endpoint,
                         'local_id': local_id,
                         'peer_id': peer_id,
                         'pri_networks': pri_networks,
                         'psk': psk,
                         'mtu': mtu}}
        for arg in ('description', 'subnet_id'):
            if arg in kwargs and kwargs[arg] is not None:
                data['site'][arg] = kwargs[arg]

        site_req = self.new_create_request('sites', data, fmt)
        site_res = site_req.get_response(self.ext_api)
        if expected_res_status:
            self.assertEqual(site_res.status_int, expected_res_status)

        return site_res

    @contextlib.contextmanager
    def site(self, fmt=None, name='site1', subnet=None,
             local_endpoint='10.117.35.202', peer_endpoint='10.117.35.203',
             local_id='10.117.35.202', peer_id='10.117.35.203',
             pri_networks=[{'local_subnets': '192.168.1.0/24',
                            'peer_subnets': '192.168.10.0/24'}],
             psk='123', mtu=1500, no_delete=False, **kwargs):
        if not fmt:
            fmt = self.fmt

        with test_db_plugin.optional_ctx(subnet, self.subnet) as tmp_subnet:
            res = self._create_site(fmt, name,
                                    local_endpoint, peer_endpoint,
                                    local_id, peer_id,
                                    pri_networks, psk,
                                    mtu, subnet_id=tmp_subnet['subnet']['id'],
                                    **kwargs)
            site = self.deserialize(fmt or self.fmt, res)
            if res.status_int >= 400:
                raise webob.exc.HTTPClientError(code=res.status_int)
            try:
                yield site
            finally:
                if not no_delete:
                    self._delete('sites', site['site']['id'])

    # Ipsec Policy
    def _create_ipsec_policy(self, fmt,
                             name, enc_alg,
                             auth_alg, dh_group,
                             life_time, expected_res_status=None,
                             **kwargs):
        data = {
            'ipsec_policy': {
                'name': name,
                'tenant_id': self._tenant_id,
                'enc_alg': enc_alg,
                'auth_alg': auth_alg,
                'dh_group': dh_group,
                'life_time': life_time
            }
        }
        for arg in ('description'):
            if arg in kwargs and kwargs[arg] is not None:
                data['ipsec_policy'][arg] = kwargs[arg]

        ipsec_policy_req = self.new_create_request('ipsec_policys', data, fmt)
        ipsec_policy_res = ipsec_policy_req.get_response(self.ext_api)
        if expected_res_status:
            self.assertEqual(ipsec_policy_res.status_int, expected_res_status)

        return ipsec_policy_res

    @contextlib.contextmanager
    def ipsec_policy(self, fmt=None, name='ipsec_policy1',
                     enc_alg='aes256', auth_alg='sha1',
                     dh_group='2', life_time=3600,
                     no_delete=False, **kwargs):
        if not fmt:
            fmt = self.fmt

        res = self._create_ipsec_policy(fmt, name,
                                        enc_alg, auth_alg,
                                        dh_group, life_time,
                                        **kwargs)
        ipsec_policy = self.deserialize(fmt or self.fmt, res)
        if res.status_int >= 400:
            raise webob.exc.HTTPClientError(code=res.status_int)
        try:
            yield ipsec_policy
        finally:
            if not no_delete:
                self._delete('ipsec_policys',
                             ipsec_policy['ipsec_policy']['id'])

##############################################################################
# Isakmp Policy
    def _create_isakmp_policy(self, fmt, name,
                              auth_mode, enable_pfs,
                              enc_alg, auth_alg,
                              dh_group, life_time,
                              expected_res_status=None,
                              **kwargs):
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
        for arg in ('description'):
            if arg in kwargs and kwargs[arg] is not None:
                data['isakmp_policy'][arg] = kwargs[arg]
        isakmp_policy_req = self.new_create_request('isakmp_policys',
                                                    data, fmt)
        isakmp_policy_res = isakmp_policy_req.get_response(self.ext_api)
        if expected_res_status:
            self.assertEqual(isakmp_policy_res.status_int, expected_res_status)

        return isakmp_policy_res

    @contextlib.contextmanager
    def isakmp_policy(self, fmt=None, name='isakmp_policy1',
                      auth_mode='psk', enable_pfs=True,
                      enc_alg='aes256', auth_alg='sha1',
                      dh_group='2', life_time=28800,
                      no_delete=False, **kwargs):
        if not fmt:
            fmt = self.fmt

        res = self._create_isakmp_policy(fmt, name,
                                         auth_mode, enable_pfs,
                                         enc_alg, auth_alg,
                                         dh_group, life_time,
                                         **kwargs)
        isakmp_policy = self.deserialize(fmt or self.fmt, res)
        if res.status_int >= 400:
            raise webob.exc.HTTPClientError(code=res.status_int)
        try:
            yield isakmp_policy
        finally:
            if not no_delete:
                self._delete('isakmp_policys',
                             isakmp_policy['isakmp_policy']['id'])

##############################################################################
# Trust Profile
    def _create_trust_profile(self, fmt, name,
                              trust_ca, crl,
                              server_cert,
                              expected_res_status=None,
                              **kwargs):
        data = {
            'trust_profile': {
                'name': name,
                'tenant_id': self._tenant_id,
                'trust_ca': trust_ca,
                'crl': crl,
                'server_cert': server_cert
            }
        }
        for arg in ('description'):
            if arg in kwargs and kwargs[arg] is not None:
                data['trust_profile'][arg] = kwargs[arg]
        trust_profile_req = self.new_create_request('trust_profiles',
                                                    data, fmt)
        trust_profile_res = trust_profile_req.get_response(self.ext_api)
        
        if expected_res_status:
            self.assertEqual(trust_profile_res.status_int, expected_res_status)

        return trust_profile_res

    @contextlib.contextmanager
    def trust_profile(self, fmt=None, name='',
                      trust_ca='trust_ca', crl='crl',
                      server_cert='server_cert',
                      no_delete=False, **kwargs):
        if not fmt:
            fmt = self.fmt

        res = self._create_trust_profile(fmt, name,
                                         trust_ca, crl,
                                         server_cert,
                                         **kwargs)
        trust_profile = self.deserialize(fmt or self.fmt, res)
        if res.status_int >= 400:
            raise webob.exc.HTTPClientError(code=res.status_int)
        try:
            yield trust_profile
        finally:
            if not no_delete:
                self._delete('trust_profiles',
                             trust_profile['trust_profile']['id'])


############################################################################
# Test Cases
class TestVPN(VPNPluginDbTestCase):
    def test_create_site(self, **extras):
        expected = {
            'name': 'site1',
            'description': "",
            'local_endpoint': "10.117.35.202",
            'peer_endpoint': "10.117.35.203",
            'local_id': "10.117.35.202",
            'peer_id': "10.117.35.203",
            'psk': 'hello123',
            'mtu': 1500,
            'pri_networks': [{'local_subnets': "192.168.1.0/24,192.168.2.0/24",
                    'peer_subnets': "192.168.10.0/24,192.168.20.0/24"},
                             {'local_subnets': "192.168.3.0/24,192.168.4.0/24",
                    'peer_subnets': "192.168.30.0/24,192.168.40.0/24"}],
            'tenant_id': self._tenant_id
        }

        expected.update(extras)
        with self.subnet() as subnet:
            expected['subnet_id'] = subnet['subnet']['id']
            name = expected['name']
            with self.site(name=name, subnet=subnet, psk=expected['psk'],
                           pri_networks=expected['pri_networks'],
                           **extras) as site:
                for k in ('id', 'local_endpoint', 'peer_endpoint', 'local_id',
                          'peer_id'):
                    self.assertTrue(site['site'].get(k, None))
                self.assertEqual(
                    dict((k, v)
                         for k, v in site['site'].items() if k in expected),
                    expected
                )
        return site

    def test_update_site(self):
        name = 'new_site'
        keys = [('name', name),
                ('mtu', 1800),
                ('psk', "123"),
                ('local_endpoint', "10.117.35.204"),
                ('peer_endpoint', "10.117.35.205")]

        with self.site(name=name) as site:
            keys.append(('subnet_id', site['site']['subnet_id']))
            data = {'site': {'name': name,
                             'mtu': 1800,
                             'local_endpoint': "10.117.35.204",
                             'peer_endpoint': "10.117.35.205",
                             'psk': "123"}}
            req = self.new_update_request('sites', data, site['site']['id'])
            res = self.deserialize(self.fmt, req.get_response(self.ext_api))
            for k, v in keys:
                self.assertEqual(res['site'][k], v)

    def test_delete_site(self):
        with self.site(no_delete=True) as site:
            req = self.new_delete_request('sites', site['site']['id'])
            res = req.get_response(self.ext_api)
            self.assertEqual(res.status_int, 204)

    def test_show_site(self):
        name = "site_show"
        keys = [('name', name),
                ('local_endpoint', "10.117.35.202"),
                ('peer_endpoint', "10.117.35.203"),
                ('local_id', "10.117.35.202"),
                ('peer_id', "10.117.35.203")]
        with self.site(name=name, local_endpoint='10.117.35.202') as site:
            req = self.new_show_request('sites',
                                        site['site']['id'])
            res = self.deserialize(self.fmt, req.get_response(self.ext_api))
            for k, v in keys:
                self.assertEqual(res['site'][k], v)

    def test_list_sites(self):
        name = "sites_list"
        keys = [('name', name),
                ('local_endpoint', "10.117.35.202"),
                ('peer_endpoint', "10.117.35.203"),
                ('local_id', "10.117.35.202"),
                ('peer_id', "10.117.35.203")]
        with self.site(name=name) as site:
            keys.append(('id', site['site']['id']))
            req = self.new_list_request('sites')
            res = self.deserialize(self.fmt, req.get_response(self.ext_api))
            self.assertEqual(len(res), 1)
            for k, v in keys:
                self.assertEqual(res['sites'][0][k], v)

    def test_create_ipsec_policy(self, **extras):
        expected = {
            'name': '',
            'description': '',
            'enc_alg': 'aes256',
            'auth_alg': 'sha1',
            'dh_group': '2',
            'life_time': 3600}

        expected.update(extras)
        name = expected['name']
        with self.ipsec_policy(name=name, description=expected['description'],
                               enc_alg=expected['enc_alg'],
                               auth_alg=expected['auth_alg'],
                               dh_group=expected['dh_group'],
                               life_time=expected['life_time'],
                               **extras) as ipsec_policy:
            self.assertEqual(
                dict((k, v)
                     for k, v in ipsec_policy['ipsec_policy'].items()
                     if k in expected),
                expected
            )
        return ipsec_policy

    def test_update_ipsec_policy(self):
        name = 'new_ipsec_policy'
        keys = [('name', name),
                ('enc_alg', "aesgcm"),
                ('dh_group', "5"),
                ('life_time', 1800)]

        with self.ipsec_policy(name=name) as ipsec_policy:
            data = {
                'ipsec_policy': {
                    'name': name,
                    'enc_alg': "aesgcm",
                    'dh_group': "5",
                    'life_time': 1800
                }
            }
            req = self.new_update_request('ipsec_policys', data,
                                          ipsec_policy['ipsec_policy']['id'])
            res = self.deserialize(self.fmt, req.get_response(self.ext_api))
            for k, v in keys:
                self.assertEqual(res['ipsec_policy'][k], v)

    def test_delete_ipsec_policy(self):
        with self.ipsec_policy(no_delete=True) as ipsec_policy:
            req = self.new_delete_request('ipsec_policys',
                                          ipsec_policy['ipsec_policy']['id'])
            res = req.get_response(self.ext_api)
            self.assertEqual(res.status_int, 204)

    def test_show_ipsec_policy(self):
        name = "ipsec_policy_show"
        keys = [('name', name),
                ('enc_alg', "aes256")]
        with self.ipsec_policy(name=name) as ipsec_policy:
            req = self.new_show_request('ipsec_policys',
                                        ipsec_policy['ipsec_policy']['id'])
            res = self.deserialize(self.fmt, req.get_response(self.ext_api))
            for k, v in keys:
                self.assertEqual(res['ipsec_policy'][k], v)

    def test_list_ipsec_policys(self):
        name = "ipsec_policys_list"
        keys = [('name', name),
                ('enc_alg', "aes256")]
        with self.ipsec_policy(name=name) as ipsec_policy:
            keys.append(('id', ipsec_policy['ipsec_policy']['id']))
            req = self.new_list_request('ipsec_policys')
            res = self.deserialize(self.fmt, req.get_response(self.ext_api))
            self.assertEqual(len(res), 1)
            for k, v in keys:
                self.assertEqual(res['ipsec_policys'][0][k], v)

###############################################################################
# Isakmp Policy Test cases

    def test_create_isakmp_policy(self, **extras):
        expected = {
            'name': '',
            'description': '',
            'auth_mode': 'psk',
            'enable_pfs': True,
            'enc_alg': 'aes256',
            'auth_alg': 'sha1',
            'dh_group': '2',
            'life_time': 26000
        }

        expected.update(extras)
        name = expected['name']
        with self.isakmp_policy(name=name, description=expected['description'],
                                auth_mode=expected['auth_mode'],
                                enable_pfs=expected['enable_pfs'],
                                enc_alg=expected['enc_alg'],
                                auth_alg=expected['auth_alg'],
                                dh_group=expected['dh_group'],
                                life_time=expected['life_time'],
                                **extras) as isakmp_policy:
            self.assertEqual(
                dict((k, v)
                     for k, v in isakmp_policy['isakmp_policy'].items()
                     if k in expected),
                expected
            )
        return isakmp_policy

    def test_update_isakmp_policy(self):
        name = 'new_isakmp_policy'
        keys = [('name', name),
                ('auth_mode', "x.509"),
                ('enable_pfs', False),
                ('enc_alg', "aesgcm"),
                ('dh_group', "5"),
                ('life_time', 18000)]

        with self.isakmp_policy(name=name) as isakmp_policy:
            data = {
                'isakmp_policy': {
                    'name': name,
                    'auth_mode': "x.509",
                    'enable_pfs': False,
                    'enc_alg': "aesgcm",
                    'dh_group': "5",
                    'life_time': 18000
                }
            }
            req = self.new_update_request('isakmp_policys', data,
                                          isakmp_policy['isakmp_policy']['id'])
            res = self.deserialize(self.fmt, req.get_response(self.ext_api))
            for k, v in keys:
                self.assertEqual(res['isakmp_policy'][k], v)

    def test_delete_isakmp_policy(self):
        with self.isakmp_policy(no_delete=True) as isakmp_policy:
            req = self.new_delete_request('isakmp_policys',
                                          isakmp_policy['isakmp_policy']['id'])
            res = req.get_response(self.ext_api)
            self.assertEqual(res.status_int, 204)

    def test_show_isakmp_policy(self):
        name = "isakmp_policy_show"
        keys = [('name', name),
                ('enc_alg', "aes256")]
        with self.isakmp_policy(name=name) as isakmp_policy:
            req = self.new_show_request('isakmp_policys',
                                        isakmp_policy['isakmp_policy']['id'])
            res = self.deserialize(self.fmt, req.get_response(self.ext_api))
            for k, v in keys:
                self.assertEqual(res['isakmp_policy'][k], v)

    def test_list_isakmp_policys(self):
        name = "isakmp_policys_list"
        keys = [('name', name),
                ('enc_alg', "aes256")]
        with self.isakmp_policy(name=name) as isakmp_policy:
            keys.append(('id', isakmp_policy['isakmp_policy']['id']))
            req = self.new_list_request('isakmp_policys')
            res = self.deserialize(self.fmt, req.get_response(self.ext_api))
            self.assertEqual(len(res), 1)
            for k, v in keys:
                self.assertEqual(res['isakmp_policys'][0][k], v)

###############################################################################
# Trust Profile Test cases

    def test_create_trust_profile(self, **extras):
        expected = {
            'name': 'haha',
            'description': '',
            'trust_ca': 'trust_ca',
            'crl': 'crl',
            'server_cert': 'server_cert'
        }
        name = expected['name']
        expected.update(extras)
        with self.trust_profile(name=name, description=expected['description'],
                                trust_ca=expected['trust_ca'],
                                crl=expected['crl'],
                                server_cert=expected['server_cert'],
                                **extras) as trust_profile:
            self.assertEqual(
                dict((k, v)
                     for k, v in trust_profile['trust_profile'].items()
                     if k in expected),
                expected
            )
        return trust_profile

    def test_update_trust_profile(self):
        name = 'new_trust_profile'
        keys = [('name', name),
                ('trust_ca', 'new_trust_ca')]

        with self.trust_profile(name=name) as trust_profile:
            data = {
                'trust_profile': {
                    'name': name,
                    'trust_ca': 'new_trust_ca'
                }
            }
            req = self.new_update_request('trust_profiles', data,
                                          trust_profile['trust_profile']['id'])
            res = self.deserialize(self.fmt, req.get_response(self.ext_api))
            for k, v in keys:
                self.assertEqual(res['trust_profile'][k], v)

    def test_delete_trust_profile(self):
        with self.trust_profile(no_delete=True) as trust_profile:
            req = self.new_delete_request('trust_profiles',
                                          trust_profile['trust_profile']['id'])
            res = req.get_response(self.ext_api)
            self.assertEqual(res.status_int, 204)

    def test_show_trust_profile(self):
        name = "trust_profile_show"
        keys = [('name', name),
                ('trust_ca', "trust_ca")]
        with self.trust_profile(name=name) as trust_profile:
            req = self.new_show_request('trust_profiles',
                                        trust_profile['trust_profile']['id'])
            res = self.deserialize(self.fmt, req.get_response(self.ext_api))
            for k, v in keys:
                self.assertEqual(res['trust_profile'][k], v)

    def test_list_trust_profiles(self):
        name = "trust_profiles_list"
        keys = [('name', name),
                ('trust_ca', "trust_ca")]
        with self.trust_profile(name=name) as trust_profile:
            keys.append(('id', trust_profile['trust_profile']['id']))
            req = self.new_list_request('trust_profiles')
            res = self.deserialize(self.fmt, req.get_response(self.ext_api))
            self.assertEqual(len(res), 1)
            for k, v in keys:
                self.assertEqual(res['trust_profiles'][0][k], v)
