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
             pri_networks=[{'local_subnets':'192.168.1.0/24',
                            'peer_subnets': '192.168.10.0/24'}],
             psk='123', mtu=1500, no_delete=False, **kwargs):
        if not fmt:
            fmt = self.fmt

        with test_db_plugin.optional_ctx(subnet, self.subnet) as tmp_subnet:
            res = self._create_site(fmt, name,
                                    local_endpoint, peer_endpoint,
                                    local_id, peer_id, pri_networks, psk,mtu, 
                                    subnet_id=tmp_subnet['subnet']['id'],
                                    **kwargs)
            site = self.deserialize(fmt or self.fmt, res)
            if res.status_int >= 400:
                raise webob.exc.HTTPClientError(code=res.status_int)
            try:
                yield site
            finally:
                if not no_delete:
                    self._delete('sites', site['site']['id'])

class TestVPN(VPNPluginDbTestCase):
    def test_create_site(self, **extras):
        expected = {
            'name': 'site1',
            'description': '',
            'local_endpoint': "10.117.35.202",
            'peer_endpoint': "10.117.35.203",
            'local_id': "10.117.35.202",
            'peer_id': "10.117.35.203",
            'psk': 'hello123',
            'mtu': 1500,
            'pri_networks': [{'local_subnets': "192.168.1.0/24,192.168.2.0/24",
                              'peer_subnets': "192.168.10.0/24,192.168.20.0/24"},
                             {'local_subnets': "192.168.3.0/24,192.168.4.0/24",
                              'peer_subnets': "192.168.30.0/24,192.168.40.0/24"}
                            ],
            'tenant_id': self._tenant_id}

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
                ('peer_id', "10.117.35.203"),
               ]
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


    def test_create_ipsecvpn(self):
        site_name = "site3"


class TestVPNXML(TestVPN):
    fmt = 'json'