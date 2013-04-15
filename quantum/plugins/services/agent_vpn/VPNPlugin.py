# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 OpenStack LLC.
# All Rights Reserved.
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

from oslo.config import cfg

from quantum.common import exceptions as q_exc
from quantum.common import rpc as q_rpc
from quantum.common import topics
from quantum.db import api as qdbapi
from quantum.db import model_base
from quantum.db.vpn import vpn_db
from quantum.extensions import vpn
from quantum.openstack.common import log as logging
from quantum.openstack.common import rpc
from quantum.openstack.common.rpc import proxy
from quantum.plugins.common import constants

LOG = logging.getLogger(__name__)

ACTIVE_PENDING = (
    constants.ACTIVE,
    constants.PENDING_CREATE,
    constants.PENDING_UPDATE
)

class VPNCallbacks(object):
    RPC_API_VERSION = '1.0'

    def __init__(self, plugin):
        self.plugin = plugin

    def create_rpc_dispatcher(self):
        return q_rpc.PluginRpcDispatcher([self])

    def get_ready_devices(self, context, host=None):
        with context.session.begin(subtransactions=True):
            qry = (context.session.query(vpn_db.Site.id).
                   join(vpn_db.Site))

            qry = qry.filter(vpn_db.Site.status.in_(ACTIVE_PENDING))
            up = True  # makes pep8 and sqlalchemy happy
            qry = qry.filter(vpn_db.Site.admin_state_up == up)
            return [id for id, in qry.all()]


class VPNAgentApi(proxy.RpcProxy):
    """Plugin side of plugin to agent RPC API."""

    API_VERSION = '1.0'

    def __init__(self, topic, host):
        super(VPNAgentApi, self).__init__(topic, self.API_VERSION)
        self.host = host


class VPNPlugin(vpn_db.VPNPluginDb):

    """
    Implementation of the Quantum VPN Service Plugin.

    This class manages the workflow of VPNaaS request/response.
    Most DB related works are implemented in class
    vpn_db.VPNPluginDb.
    """
    supported_extension_aliases = ["vpnaas"]

    def __init__(self):
        """
        Do the initialization for the vpn service plugin here.
        """
        #qdbapi.register_models(base=model_base.BASEV2)

        qdbapi.register_models()

        self.callbacks = VPNCallbacks(self)

        self.conn = rpc.create_connection(new=True)
        self.conn.create_consumer(
            topics.VPN_PLUGIN,
            self.callbacks.create_rpc_dispatcher(),
            fanout=False)
        self.conn.consume_in_thread()

        self.agent_rpc = VPNAgentApi(
            topics.VPN_AGENT,
            cfg.CONF.host
        )

    def get_plugin_type(self):
        return constants.VPN

    def get_plugin_description(self):
        return "Quantum VPN Service Plugin"

    def create_site(self, context, site):
        s = super(VPNPlugin, self).create_site(context, site)
        self.update_status(context, vpn_db.Site, s['id'],
                           constants.PENDING_CREATE)
        LOG.debug(_("Create site: %s") % s['id'])

        # If we adopt asynchronous mode, this method should return immediately
        # and let client to query the object status. The plugin will listen on
        # the event from device and update the object status by calling
        # self.update_state(context, Site, id, ACTIVE/ERROR)
        #
        # In synchronous mode, send the request to device here and wait for
        # response. Eventually update the object status prior to the return.
        s_query = self.get_site(context, s['id'])
        return s_query

    def update_site(self, context, id, site):
        if 'status' not in site['site']:
            site['site']['status'] = constants.PENDING_UPDATE            
        s = super(VPNPlugin, self).update_site(context, id, site)
        LOG.debug(_("Update site: %s"), id)

        # TODO notify vpnagent
        s_rt = self.get_site(context, id)
        return s_rt

    def delete_site(self, context, id):
        self.update_status(context, vpn_db.Site, id, constants.PENDING_DELETE)
        LOG.debug(_("Delete site: %s"), id)

        # TODO notify vpnagent
        super(VPNPlugin, self).delete_site(context, id)

    def get_site(self, context, id, fields=None):
        res = super(VPNPlugin, self).get_site(context, id, fields)
        LOG.debug(_("Get site: %s"), id)
        return res

    def get_sites(self, context, filters=None, fields=None):
        res = super(VPNPlugin, self).get_sites(context, filters, fields)
        LOG.debug(_("Get sites"))
        return res

    def get_isakmp_policys(self, context, filters=None, fields=None):
        res = super(VPNPlugin, self).get_isakmp_policys(context, filters, fields)
        LOG.debug(_("Get isakmp policys"))
        return res

    def get_isakmp_policy(self, context, id, fields=None):
        res = super(VPNPlugin, self).get_isakmp_policy(context, id, fields)
        LOG.debug(_("Get isakmp policy: %s"), id)
        return res

    def create_isakmp_policy(self, context, isakmp_policy):
        s = super(VPNPlugin, self).create_isakmp_policy(context, isakmp_policy)
        self.update_status(context, vpn_db.IsakmpPolicy, s['id'],
                           constants.PENDING_CREATE)
        LOG.debug(_("Create isakmp policy: %s") % s['id'])

        s_query = self.get_isakmp_policy(context, s['id'])
        return s_query

    def update_isakmp_policy(self, context, id, isakmp_policy):
        if 'status' not in isakmp_policy['isakmp_policy']:
            isakmp_policy['isakmp_policy']['status'] = constants.PENDING_UPDATE            
        s = super(VPNPlugin, self).update_isakmp_policy(context, id, isakmp_policy)
        LOG.debug(_("Update isakmp policy: %s"), id)
        # TODO notify vpnagent
        s_rt = self.get_isakmp_policy(context, id)
        return s_rt

    def delete_isakmp_policy(self, context, id):
        self.update_status(context, vpn_db.IsakmpPolicy, id, constants.PENDING_DELETE)
        LOG.debug(_("Delete isakmp policy: %s"), id)
        # TODO notify vpnagent
        super(VPNPlugin, self).delete_isakmp_policy(context, id)

    def get_ipsec_policys(self, context, filters=None, fields=None):
        res = super(VPNPlugin, self).get_ipsec_policys(context, filters, fields)
        LOG.debug(_("Get ipsec policys"))
        return res

    def get_ipsec_policy(self, context, id, fields=None):
        res = super(VPNPlugin, self).get_ipsec_policy(context, id, fields)
        LOG.debug(_("Get ipsec policy: %s"), id)
        return res

    def create_ipsec_policy(self, context, ipsec_policy):
        s = super(VPNPlugin, self).create_ipsec_policy(context, ipsec_policy)
        self.update_status(context, vpn_db.IPSecPolicy, s['id'],
                           constants.PENDING_CREATE)
        LOG.debug(_("Create ipsec policy: %s") % s['id'])

        s_query = self.get_ipsec_policy(context, s['id'])
        return s_query

    def update_ipsec_policy(self, context, id, ipsec_policy):
        if 'status' not in ipsec_policy['ipsec_policy']:
            ipsec_policy['ipsec_policy']['status'] = constants.PENDING_UPDATE            
        s = super(VPNPlugin, self).update_ipsec_policy(context, id, ipsec_policy)
        LOG.debug(_("Update ipsec policy: %s"), id)

        # TODO notify vpnagent
        s_rt = self.get_ipsec_policy(context, id)
        return s_rt

    def delete_ipsec_policy(self, context, id):
        self.update_status(context, vpn_db.IPSecPolicy, id, constants.PENDING_DELETE)
        LOG.debug(_("Delete ipsec policy: %s"), id)

        # TODO notify vpnagent
        super(VPNPlugin, self).delete_ipsec_policy(context, id)

    def get_trust_profiles(self, context, filters=None, fields=None):
        pass

    def get_trust_profile(self, context, id, fields=None):
        pass

    def create_trust_profile(self, context, trust_profile):
        pass

    def update_trust_profile(self, context, id, trust_profile):
        pass

    def delete_trust_profile(self, context, id):
        pass

    def stats(self, context, site_id):
        pass
