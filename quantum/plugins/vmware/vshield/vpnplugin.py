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


import re
from quantum.db import api as qdbapi
from quantum.db import model_base
from quantum.db.vpn import vpn_db
from quantum.extensions import vpn
from quantum.openstack.common import log as logging
from quantum.plugins.common import constants
from vseapi import VseAPI
from vpnapi import VPNAPI

LOG = logging.getLogger(__name__)

edgeUri = 'https://10.117.35.38'
edgeId = 'edge-1'
edgeUser = 'admin'
edgePasswd = 'default'


class VShieldEdgeVPNPlugin(vpn_db.VPNPluginDb):

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
        # Hard coded for now
        vseapi = VseAPI(edgeUri, edgeUser, edgePasswd, edgeId)
        self.vsevpn = VPNAPI(vseapi)
        qdbapi.register_models(base=model_base.BASEV2)

    def get_plugin_type(self):
        return constants.VPN

    def get_plugin_description(self):
        return "Quantum VPN Service Plugin"

    def create_site(self, context, site):
        with context.session.begin(subtransactions=True):
            s = super(VShieldEdgeVPNPlugin,
                      self).create_site(context, site)
            self.update_status(context, vpn_db.Site, s['id'],
                               constants.PENDING_CREATE)
            LOG.debug(_("Create site: %s") % s['id'])
            self.vsevpn.create_site(context, s)
            self.update_status(context, vpn_db.Site, s['id'],
                               constants.ACTIVE)

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
        with context.session.begin(subtransactions=True):
#            s_query = self.get_site(context, id, fields=["status"])
#            if s_query['status'] in [constants.PENDING_DELETE,
#                                     constants.ERROR]:
#                raise vpn.StateInvalid(id=id, state=s_query['status'])

            s = super(VShieldEdgeVPNPlugin,
                      self).update_site(context, id, site)
            self.update_status(context, vpn_db.Site, id,
                               constants.PENDING_UPDATE)
            LOG.debug(_("Update site: %s"), id)
            self.vsevpn.update_site(context, s)
            self.update_status(context, vpn_db.Site, id, constants.ACTIVE)

        s_rt = self.get_site(context, id)
        return s_rt

    def delete_site(self, context, id):
        with context.session.begin(subtransactions=True):
            site = self.get_site(context, id)
            #uuid2vseid = self.vsevpn.get_site_vseid(context, site['id'])
            self.update_status(context, vpn_db.Site, id,
                               constants.PENDING_DELETE)
            LOG.debug(_("Delete site: %s"), id)

            super(VShieldEdgeVPNPlugin, self).delete_site(context, id)
            #site['vseid'] = uuid2vseid
            self.vsevpn.delete_site(context, site)

    def get_site(self, context, id, fields=None):
        res = super(VShieldEdgeVPNPlugin, self).get_site(context, id, fields)
        LOG.debug(_("Get site: %s"), id)
        return res

    def get_sites(self, context, filters=None, fields=None):
        res = super(VShieldEdgeVPNPlugin, self).get_sites(
            context, filters, fields)
        LOG.debug(_("Get sites"))
        return res

    def stats(self, context, site_id):
        site = self.get_site(context, site_id)
        res = self.vsevpn.get_stats(context, site)
        return res

    def get_isakmp_policys(self, context, filters=None, fields=None):
        res = super(VShieldEdgeVPNPlugin, self).get_isakmp_policys(
            context, filters, fields)
        LOG.debug(_("Get isakmp policys"))
        return res

    def get_isakmp_policy(self, context, id, fields=None):
        res = super(VShieldEdgeVPNPlugin,
                    self).get_isakmp_policy(context, id, fields)
        LOG.debug(_("Get isakmp policy: %s"), id)
        return res

    def create_isakmp_policy(self, context, isakmp_policy):
        with context.session.begin(subtransactions=True):
            s = super(VShieldEdgeVPNPlugin,
                      self).create_isakmp_policy(context, isakmp_policy)
            self.update_status(context, vpn_db.IsakmpPolicy, s['id'],
                               constants.PENDING_CREATE)
            LOG.debug(_("Create isakmp policy: %s") % s['id'])
        s_query = self.get_isakmp_policy(context, s['id'])
        return s_query

    def update_isakmp_policy(self, context, id, isakmp_policy):
        with context.session.begin(subtransactions=True):
            s = super(VShieldEdgeVPNPlugin,
                      self).update_isakmp_policy(context, id, isakmp_policy)
            self.update_status(context, vpn_db.IsakmpPolicy, id,
                               constants.PENDING_UPDATE)
            LOG.debug(_("Update isakmp policy: %s"), id)

        s_rt = self.get_isakmp_policy(context, id)
        return s_rt

    def delete_isakmp_policy(self, context, id):
        with context.session.begin(subtransactions=True):
            isakmp_policy = self.get_isakmp_policy(context, id)
            self.update_status(context, vpn_db.IsakmpPolicy, id,
                               constants.PENDING_DELETE)
            LOG.debug(_("Delete isakmp policy: %s"), id)
            super(VShieldEdgeVPNPlugin,
                  self).delete_isakmp_policy(context, id)

    def create_ipsec_policy(self, context, ipsec_policy):
        with context.session.begin(subtransactions=True):
            p = super(VShieldEdgeVPNPlugin,
                      self).create_ipsec_policy(context, ipsec_policy)
            self.update_status(context, vpn_db.IPSecPolicy, p['id'],
                               constants.PENDING_CREATE)
            LOG.debug(_("Create ipsec policy: %s") % p['id'])
        s_query = self.get_ipsec_policy(context, p['id'])
        return s_query

    def update_ipsec_policy(self, context, id, ipsec_policy):
        with context.session.begin(subtransactions=True):
            p = super(VShieldEdgeVPNPlugin,
                      self).update_ipsec_policy(context, id, ipsec_policy)
            self.update_status(context, vpn_db.IPSecPolicy, id,
                               constants.PENDING_UPDATE)
            LOG.debug(_("Update ipsec policy: %s"), id)

        s_rt = self.get_ipsec_policy(context, id)
        return s_rt

    def delete_ipsec_policy(self, context, id):
        with context.session.begin(subtransactions=True):
            ipsec_policy = self.get_ipsec_policy(context, id)
            self.update_status(context, vpn_db.IPSecPolicy, id,
                               constants.PENDING_DELETE)
            LOG.debug(_("Delete ipsec policy: %s"), id)
            super(VShieldEdgeVPNPlugin,
                  self).delete_ipsec_policy(context, id)

    def get_ipsec_policy(self, context, id, fields=None):
        res = super(VShieldEdgeVPNPlugin,
                    self).get_ipsec_policy(context, id, fields)
        LOG.debug(_("Get ipsec policy: %s"), id)
        return res

    def get_ipsec_policys(self, context, filters=None, fields=None):
        res = super(VShieldEdgeVPNPlugin, self).get_ipsec_policys(
            context, filters, fields)
        LOG.debug(_("Get ipsec policys"))
        return res

    def get_trust_profiles(self, context, filters=None, fields=None):
        res = super(VShieldEdgeVPNPlugin, self).get_trust_profiles(
                context, filters, fields)
        LOG.debug(_("Get trust profiles"))
        return res

    def get_trust_profile(self, context, id, fields=None):
        res = super(VShieldEdgeVPNPlugin,
                    self).get_trust_profile(context, id, fields)
        LOG.debug(_("Get trust profile: %s"), id)
        return res

    def create_trust_profile(self, context, trust_profile):
        with context.session.begin(subtransactions=True):
            p = super(VShieldEdgeVPNPlugin,
                      self).create_trust_profile(context, trust_profile)
            self.update_status(context, vpn_db.TrustProfile, p['id'],
                               constants.PENDING_CREATE)
            LOG.debug(_("Create trust profile: %s") % p['id'])
        s_query = self.get_trust_profile(context, p['id'])
        return s_query
        pass

    def update_trust_profile(self, context, id, trust_profile):
        with context.session.begin(subtransactions=True):
            p = super(VShieldEdgeVPNPlugin,
                      self).update_trust_profile(context, id, trust_profile)
            self.update_status(context, vpn_db.TrustProfile, id,
                               constants.PENDING_UPDATE)
            LOG.debug(_("Update trust profile: %s"), id)

        s_rt = self.get_trust_profile(context, id)
        return s_rt

    def delete_trust_profile(self, context, id):
        with context.session.begin(subtransactions=True):
            trust_profile = self.get_trust_profile(context, id)
            self.update_status(context, vpn_db.TrustProfile, id,
                               constants.PENDING_DELETE)
            LOG.debug(_("Delete trust profile: %s"), id)
            super(VShieldEdgeVPNPlugin,
                  self).delete_trust_profile(context, id)
