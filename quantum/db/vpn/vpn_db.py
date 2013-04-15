# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013 OpenStack Foundation.  All rights reserved
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
#

import re
from oslo.config import cfg
import sqlalchemy as sa
from sqlalchemy import exc as sa_exc
from sqlalchemy import orm
from sqlalchemy.orm import exc
from sqlalchemy.sql import expression as expr
import webob.exc as w_exc

from quantum.api.v2 import attributes
from quantum.common import exceptions as q_exc
from quantum.db import db_base_plugin_v2
from quantum.db import model_base
from quantum.db import models_v2
from quantum.extensions import vpn
from quantum.extensions.vpn import VPNPluginBase
from quantum import manager
from quantum.openstack.common import log as logging
from quantum.openstack.common import uuidutils
from quantum.plugins.common import constants
from quantum import policy


LOG = logging.getLogger(__name__)

class Site(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    """Represents a v2 quantum VPN site."""
    name = sa.Column(sa.String(255))
    description = sa.Column(sa.String(255))
    local_endpoint = sa.Column(sa.String(64), nullable=False);
    peer_endpoint = sa.Column(sa.String(64), nullable=False);
    local_id = sa.Column(sa.String(128), nullable=False);
    peer_id = sa.Column(sa.String(128), nullable=False);
    psk = sa.Column(sa.String(64), nullable=True);
    mtu = sa.Column(sa.Integer, nullable=True);
    pri_networks = sa.Column(sa.String(2048), nullable=False);
    subnet_id = sa.Column(sa.String(64), nullable=True);

class IPSecPolicy(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    """Represents a v2 quantum VPN Ipsec Policy."""
    name = sa.Column(sa.String(32))
    description = sa.Column(sa.String(255))
    encryption_algorithm = sa.Column(sa.String(16), nullable=True);
    authentication_algorithm = sa.Column(sa.String(8), nullable=True);
    dh_group = sa.Column(sa.String(1), nullable=True);
    life_time = sa.Column(sa.Integer, nullable=True);

class VPNPluginDb(VPNPluginBase):
    """
    A class that wraps the implementation of the Quantum
    VPN plugin database access interface using SQLAlchemy models.
    """

    @property
    def _core_plugin(self):
        return manager.QuantumManager.get_plugin()

    # TODO:
    # A set of internal facility methods are borrowed from QuantumDbPluginV2
    # class and hence this is duplicate. We need to pull out those methods
    # into a seperate class which can be used by both QuantumDbPluginV2 and
    # this class (and others).
    def _get_tenant_id_for_create(self, context, resource):
        if context.is_admin and 'tenant_id' in resource:
            tenant_id = resource['tenant_id']
        elif ('tenant_id' in resource and
              resource['tenant_id'] != context.tenant_id):
            reason = _('Cannot create resource for another tenant')
            raise q_exc.AdminRequired(reason=reason)
        else:
            tenant_id = context.tenant_id
        return tenant_id

    def _fields(self, resource, fields):
        if fields:
            return dict((key, item) for key, item in resource.iteritems()
                        if key in fields)
        return resource

    def _apply_filters_to_query(self, query, model, filters):
        if filters:
            for key, value in filters.iteritems():
                column = getattr(model, key, None)
                if column:
                    query = query.filter(column.in_(value))
        return query

    def _get_collection_query(self, context, model, filters=None):
        collection = self._model_query(context, model)
        collection = self._apply_filters_to_query(collection, model, filters)
        return collection

    def _get_collection(self, context, model, dict_func, filters=None,
                        fields=None, sorts=None, limit=None, marker_obj=None,
                        page_reverse=False):
        query = self._get_collection_query(context, model, filters)
        return [dict_func(c, fields) for c in query.all()]

    def _get_collection_count(self, context, model, filters=None):
        return self._get_collection_query(context, model, filters).count()

    def _model_query(self, context, model):
        query = context.session.query(model)
        query_filter = None
        if not context.is_admin and hasattr(model, 'tenant_id'):
            if hasattr(model, 'shared'):
                query_filter = ((model.tenant_id == context.tenant_id) |
                                (model.shared))
            else:
                query_filter = (model.tenant_id == context.tenant_id)

        if query_filter is not None:
            query = query.filter(query_filter)
        return query

    def _get_by_id(self, context, model, id):
        query = self._model_query(context, model)
        return query.filter(model.id == id).one()

    def update_status(self, context, model, id, status):
        with context.session.begin(subtransactions=True):
            v_db = self._get_resource(context, model, id)
            v_db.update({'status': status})

    def _get_resource(self, context, model, id):
        try:
            r = self._get_by_id(context, model, id)
        except exc.NoResultFound:
            if issubclass(model, Site):
                raise VPN.SiteNotFound(site_id=id)
            elif issubclass(model, IPSecPolicy):
                raise VPN.IPSecPolicyNotFound(ipsec_policy_id=id)
            else:
                raise
        return r

    def assert_modification_allowed(self, obj):
        status = getattr(obj, 'status', None)

        if status == constants.PENDING_DELETE:
            raise VPN.StateInvalid(id=id, state=status)

    ########################################################
    # Site DB access
    def _make_site_dict(self, site, fields=None):
        """
        pri_networks in db looks like
        "192.168.1.0/24,192.168.2.0/24-192.168.11.0/24;
        192.168.3.0/24-192.168.33.0/24,192.168.44.0/24"
        and be convert to JSON as
        'pri_networks' : [
            {
               'local_subnets': "192.168.1.0/24,192.168.2.0/24",
               'peer_subnets': "192.168.11.0/24"
            },{
               'local_subnets': "192.168.3.0/24",
               'peer_subnets': "192.168.33.0/24,192.168.44.0/24"
            }
        ]
        """
        pri_networks = []
        pairs = site['pri_networks'].split(";")
        for pair in pairs:
            match = re.search("(.*?)-(.*)", pair)
            if match:
               pri_networks.append({'local_subnets': match.group(1),
                                    'peer_subnets': match.group(2)})        
        res = {'id': site['id'],
               'tenant_id': site['tenant_id'],
               'subnet_id': site['subnet_id'],
               'name': site['name'],
               'description': site['description'],
               'local_endpoint': site['local_endpoint'],
               'local_id': site['local_id'],
               'peer_endpoint': site['peer_endpoint'],
               'peer_id': site['peer_id'],
               'pri_networks': pri_networks,
               'psk': site['psk'],
               'mtu': site['mtu']}

        return self._fields(res, fields)


    def _subnets_to_str(self, pri_networks):
        res = ""
        count = 0
        for pair in pri_networks:
            if (count > 0):
                res += ';'
            res += '{0}-{1}'.format(pair['local_subnets'], pair['peer_subnets'])
            count += 1
        return res

    def create_site(self, context, site):
        s = site['site']
        tenant_id = self._get_tenant_id_for_create(context, s)

        with context.session.begin(subtransactions=True):
            pri_networks = self._subnets_to_str(s['pri_networks'])
            site_db = Site(id=uuidutils.generate_uuid(),
                         tenant_id=tenant_id,
                         subnet_id=s['subnet_id'],
                         name=s['name'],
                         description=s['description'],
                         local_endpoint=s['local_endpoint'],
                         peer_endpoint=s['peer_endpoint'],
                         local_id=s['local_id'],
                         peer_id=s['peer_id'],
                         pri_networks=pri_networks,
                         psk=s['psk'],
                         mtu=s['mtu'])

            try:
                context.session.add(site_db)
                context.session.flush()
            except sa_exc.IntegrityError:
                raise vpn.SiteExists(local_endpoint=s['local_endpoint'],
                                     peer_endpoint=s['peer_endpoint'])

        return self._make_site_dict(site_db)

    def update_site(self, context, id, site):
        s = site['site']
        if s.has_key('pri_networks'):
            pri_networks = self._subnets_to_str(s['pri_networks'])
            s['pri_networks'] = pri_networks

        with context.session.begin(subtransactions=True):
            site_db = self._get_resource(context, Site, id)

            self.assert_modification_allowed(site_db)

            if s:
                try:
                    site_db.update(s)
                    # To be add validation here
                    LOG.debug(_("update_site: %s") % id)
                except sa_exc.IntegrityError:
                    raise vpn.SiteExists(local_endpoint=s['local_endpoint'],
                                         peer_endpoint=s['peer_endpoint'])

        return self._make_site_dict(site_db)

    def delete_site(self, context, id):
        with context.session.begin(subtransactions=True):
            site = self._get_resource(context, Site, id)
            context.session.delete(site)
            context.session.flush()

    def get_site(self, context, id, fields=None):
        site = self._get_resource(context, Site, id)
        return self._make_site_dict(site, fields)

    def get_sites(self, context, filters=None, fields=None):
        return self._get_collection(context, Site,
                                    self._make_site_dict,
                                    filters=filters, fields=fields)


    ########################################################
    # Ipsec Policy DB access
    def _make_ipsec_policy_dict(self, ipsecp, fields=None):
        res = {'id': ipsecp['id'],
               'tenant_id': ipsecp['tenant_id'],
               'name': ipsecp['name'],
               'description': ipsecp['description'],
               'encryption_algorithm': ipsecp['encryption_algorithm'],
               'authentication_algorithm': ipsecp['authentication_algorithm'],
               'dh_group': ipsecp['dh_group'],
               'life_time': ipsecp['life_time']}

        return self._fields(res, fields)

    def create_ipsec_policy(self, context, ipsecp):
        s = ipsecp['ipsec_policy']
        tenant_id = self._get_tenant_id_for_create(context, s)

        with context.session.begin(subtransactions=True):
            ipsecp_db = IPSecPolicy(id=uuidutils.generate_uuid(),
                                tenant_id=tenant_id,
                                name=s['name'],
                                description=s['description'],
                                encryption_algorithm=s['encryption_algorithm'],
                                authentication_algorithm=s['authentication_algorithm'],
                                dh_group=s['dh_group'],
                                life_time=s['life_time'])

            try:
                context.session.add(ipsecp_db)
                context.session.flush()
            except sa_exc.IntegrityError:
                raise vpn.IPSecPolicyExists()

        return self._make_ipsec_policy_dict(ipsecp_db)


    def update_ipsec_policy(self, context, id, ipsecp):
        s = ipsecp['ipsec_policy']

        with context.session.begin(subtransactions=True):
            ipsecp_db = self._get_resource(context, IPSecPolicy, id)

            self.assert_modification_allowed(ipsecp_db)

            if s:
                try:
                    ipsecp_db.update(s)
                    # To be add validation here
                    LOG.debug(_("update_ipsec_policy: %s") % id)
                except sa_exc.IntegrityError:
                    raise vpn.IPSecPolicyExists()

        return self._make_ipsec_policy_dict(ipsecp_db)

    def delete_ipsec_policy(self, context, id):
        with context.session.begin(subtransactions=True):
            ipsecp = self._get_resource(context, IPSecPolicy, id)
            context.session.delete(ipsecp)
            context.session.flush()

    def get_ipsec_policy(self, context, id, fields=None):
        ipsecp = self._get_resource(context, IPSecPolicy, id)
        return self._make_ipsec_policy_dict(ipsecp, fields)

    def get_ipsec_policys(self, context, filters=None, fields=None):
        return self._get_collection(context, IPSecPolicy,
                                    self._make_ipsec_policy_dict,
                                    filters=filters, fields=fields)
