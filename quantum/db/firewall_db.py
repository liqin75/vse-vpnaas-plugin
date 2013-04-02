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

import json
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
from quantum.extensions.firewall import FirewallPluginBase
from quantum import manager
from quantum.openstack.common import log as logging
from quantum.openstack.common import uuidutils
from quantum.plugins.common import constants
from quantum import policy


LOG = logging.getLogger(__name__)


class RuleSourceAddress(model_base.BASEV2):
    rule_id = sa.Column(sa.String(36),
                        sa.ForeignKey('rules.id', ondelete="CASCADE"),
                        primary_key=True)
    address = sa.Column(sa.String(128),
                        nullable=False,
                        primary_key=True)


class RuleDestinationAddress(model_base.BASEV2):
    rule_id = sa.Column(sa.String(36),
                        sa.ForeignKey('rules.id', ondelete="CASCADE"),
                        primary_key=True)
    address = sa.Column(sa.String(128),
                        nullable=False,
                        primary_key=True)


class IPObjAddress(model_base.BASEV2):
    ipobj_id = sa.Column(sa.String(36),
                         sa.ForeignKey('ipobjs.id', ondelete="CASCADE"),
                         primary_key=True)
    address = sa.Column(sa.String(128),
                        nullable=False,
                        primary_key=True)


class IPObj(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    name = sa.Column(sa.String(255))
    description = sa.Column(sa.String(255))
    value = orm.relationship(IPObjAddress,
                             uselist=True,
                             cascade="all, delete-orphan")


class RuleServiceConfig(model_base.BASEV2):
    id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
    rule_id = sa.Column(sa.String(36),
                        sa.ForeignKey('rules.id',
                        ondelete="CASCADE"))
    protocol = sa.Column(sa.String(16), nullable=False)
    values = sa.Column(sa.Text())
    sourcePorts = sa.Column(sa.Text())


class ServiceObj(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    name = sa.Column(sa.String(255))
    description = sa.Column(sa.String(255))
    protocol = sa.Column(sa.String(16), nullable=False)
    values = sa.Column(sa.Text())
    sourcePorts = sa.Column(sa.Text())


class ZoneNetwork(model_base.BASEV2):
    zone_id = sa.Column(sa.String(36),
                        sa.ForeignKey('zones.id', ondelete="CASCADE"),
                        primary_key=True)
    network_id = sa.Column(sa.String(36),
#                           sa.ForeignKey('networks.id'),
                           primary_key=True)


class Zone(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    name = sa.Column(sa.String(255))
    description = sa.Column(sa.String(255))
    value = orm.relationship(ZoneNetwork,
                             uselist=True,
                             cascade="all, delete-orphan")


class RuleSourceIPObjBinding(model_base.BASEV2):
    rule_id = sa.Column(sa.String(36),
                        sa.ForeignKey('rules.id', ondelete="CASCADE"),
                        primary_key=True)
    ipobj_id = sa.Column(sa.String(46),
                         sa.ForeignKey('ipobjs.id', ondelete="CASCADE"),
                         primary_key=True)


class RuleDestinationIPObjBinding(model_base.BASEV2):
    rule_id = sa.Column(sa.String(36),
                        sa.ForeignKey('rules.id', ondelete="CASCADE"),
                        primary_key=True)
    ipobj_id = sa.Column(sa.String(46),
                         sa.ForeignKey('ipobjs.id', ondelete="CASCADE"),
                         primary_key=True)


class RuleServiceObjBinding(model_base.BASEV2):
    rule_id = sa.Column(sa.String(36),
                        sa.ForeignKey('rules.id', ondelete="CASCADE"),
                        primary_key=True)
    serviceobj_id = sa.Column(sa.String(46),
                             sa.ForeignKey('serviceobjs.id', ondelete="CASCADE"),
                             primary_key=True)


class Rule(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    """Represents a v2 quantum loadbalancer vip."""
    name = sa.Column(sa.String(255))
    description = sa.Column(sa.String(255))
    action = sa.Column(sa.Integer, nullable=False)
    log = sa.Column(sa.Boolean, nullable=False)
    enabled = sa.Column(sa.Boolean, nullable=False)
    sourceAddress = orm.relationship(RuleSourceAddress,
                                     uselist=True,
                                     cascade="all, delete-orphan")
    sourceIPObj = orm.relationship(IPObj,
                                   secondary=RuleSourceIPObjBinding.__tablename__,
                                   uselist=True,
                                   cascade="all")
    sourceZone = sa.Column(sa.String(36), sa.ForeignKey('zones.id'))
    destinationAddress = orm.relationship(RuleDestinationAddress,
                                          uselist=True,
                                          cascade="all, delete-orphan")
    destinationIPObj = orm.relationship(IPObj,
                                        secondary=RuleDestinationIPObjBinding.__tablename__,
                                        uselist=True,
                                        cascade="all")
    destinationZone = sa.Column(sa.String(36), sa.ForeignKey('zones.id'))
    serviceConfig = orm.relationship(RuleServiceConfig,
                                     uselist=True,
                                     cascade="all, delete-orphan")
    serviceObj = orm.relationship(ServiceObj,
                                  secondary=RuleServiceObjBinding.__tablename__,
                                  uselist=True,
                                  cascade="all")

class RuleLinkNode(model_base.BASEV2, models_v2.HasTenant):
    rule_id = sa.Column(sa.String(36),
                        sa.ForeignKey('rules.id'),
                        primary_key=True)
    prev_id = sa.Column(sa.String(36),
                        sa.ForeignKey('rules.id'))
    next_id = sa.Column(sa.String(36),
                        sa.ForeignKey('rules.id'))

class FirewallPluginDb(FirewallPluginBase):
    """
    A class that wraps the implementation of the Quantum
    loadbalancer plugin database access interface using SQLAlchemy models.
    """

    @property
    def _core_plugin(self):
        return manager.QuantumManager.get_plugin()

    # TODO(lcui):
    # A set of internal facility methods are borrowed from QuantumDbPluginV2
    # class and hence this is duplicate. We need to pull out those methods
    # into a seperate class which can be used by both QuantumDbPluginV2 and
    # this class (and others).
    def _get_tenant_id_for_create(self, context, resource={}):
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

    def _get_optional_attrs(self, dst, src, attrs):
        for attr in attrs:
            if src.get(attr):
                dst[attr] = src[attr]

    def _make_rule_dict(self, rule, fields=None):
        res = {
            'id': rule['id'],
            'name': rule['name'],
            'description': rule.get('description'),
            'enabled': rule['enabled']
        }
        if rule.get('log', False):
            res['log'] = 'enabled'
        else:
            res['log'] = 'disabled'
        if rule['action']:
            res['action'] = 'accept'
        else:
            res['action'] = 'drop'

        src = {}
        if rule.get('sourceAddress'):
            src['addresses'] = []
            for address in rule['sourceAddress']:
                src['addresses'].append(address['address'])
        if rule.get('sourceIPObj'):
            src['ipobjs'] = []
            for ipobj in rule['sourceIPObj']:
                src['ipobjs'].append(ipobj['id'])
        if rule.get('sourceZone'):
            src['zone'] = rule['sourceZone']
        res['source'] = src

        dst = {}
        if rule.get('destinationAddress'):
            dst['addresses'] = []
            for address in rule['destinationAddress']:
                dst['addresses'].append(address['address'])
        if rule.get('destinationIPObj'):
            dst['ipobjs'] = []
            for ipobj in rule['destinationIPObj']:
                dst['ipobjs'].append(ipobj['id'])
        if rule.get('destinationZone'):
            dst['zone'] = rule['destinationZone']
        res['destination'] = dst

        svc = {}
        if rule.get('serviceConfig'):
            svc['services'] = []
            for svcCfg in rule['serviceConfig']:
                svc['services'].append(self._serviceobj2dict(svcCfg))
        if rule.get('serviceObj'):
            svc['serviceobjs'] = []
            for svcCfg in rule['serviceObj']:
                svc['serviceobjs'].append(svcCfg['id'])
        res['service'] = svc

        return self._fields(res, fields)

    def _get_last_rule(self, context, tenant_id):
        query = context.session.query(RuleLinkNode)
        return query.filter(RuleLinkNode.tenant_id == tenant_id,
                             RuleLinkNode.next_id == None).first()

    def _get_rule_link_node(self, context, rule_id):
        return context.session.query(RuleLinkNode).filter(
            RuleLinkNode.rule_id == rule_id).one()

    def create_rule(self, context, rule):
        body = rule['rule']
        with context.session.begin(subtransactions=True):
            src = body.get('source')
            dst = body.get('destination')
            svc = body.get('service')
            if not src:
                src = {}
            if not dst:
                dst = {}
            if not svc:
                svc = {}

            print "src: {}".format(src)
            print "dst: {}".format(dst)
            print "svc: {}".format(svc)
            rule_id = uuidutils.generate_uuid()
            tenant_id = self._get_tenant_id_for_create(context, body)
            rule_db = Rule(
                id=rule_id,
                tenant_id=tenant_id,
                name=body['name'],
                description=body['description'],
                sourceZone=src.get('zone'),
                destinationZone=dst.get('zone'),
                action=(body['action'] == "accept"),
                log=(body.get('log') == "enabled"),
                enabled=body['enabled']
            )
            if src.get('addresses'):
                rule_db.sourceAddress = []
                for address in src['addresses']:
                    addr = RuleSourceAddress(address=address)
                    rule_db.sourceAddress.append(addr)
            if src.get('ipobjs'):
                rule_db.sourceIPObj = []
                for ipobj_id in src['ipobjs']:
                    ipobj = self._get_by_id(context, IPObj, ipobj_id)
                    rule_db.sourceIPObj.append(ipobj)
            if dst.get('addresses'):
                rule_db.destinationAddress = []
                for address in dst['addresses']:
                    addr = RuleDestinationAddress(address=address)
                    rule_db.destinationAddress.append(addr)
            if dst.get('ipobjs'):
                rule_db.destinationIPObj = []
                for ipobj_id in dst['ipobjs']:
                    ipobj = self._get_by_id(context, IPObj, ipobj_id)
                    rule_db.destinationIPObj.append(ipobj)
            if svc.get('services'):
                rule_db.serviceConfig = []
                for service in svc['services']:
                    svcobj = self._dict2serviceobj(service)
                    svcCfg = RuleServiceConfig(
                        protocol=svcobj['protocol'],
                        values=svcobj.get('values'),
                        sourcePorts=svcobj.get('sourcePorts')
                    )
                    rule_db.serviceConfig.append(svcCfg)
            if svc.get('serviceobjs'):
                rule_db.serviceObj = []
                for svcobj_id in svc['serviceobjs']:
                    svcobj = self._get_by_id(context, ServiceObj, svcobj_id)
                    rule_db.serviceObj.append(svcobj)

            print rule_db
            print rule_db.sourceAddress
            context.session.add(rule_db)

            prev_id = None
            next_id = None
            if body.get('location'):
                target_node = self._get_rule_link_node(context, body['location'])
                prev_id = target_node['prev_id']
                next_id = target_node['rule_id']
                if prev_id:
                    prev_node = self._get_rule_link_node(context, prev_id)
                    prev_node.update({'next_id': rule_id})
                target_node.update({'prev_id': rule_id})
            else:
                last_rule = self._get_last_rule(context, tenant_id)
                if last_rule:
                    last_rule.update({'next_id': rule_id})
                    prev_id = last_rule['rule_id']

            rule_link_node = RuleLinkNode(tenant_id=tenant_id,
                                          rule_id=rule_id,
                                          prev_id=prev_id,
                                          next_id=next_id)
            context.session.add(rule_link_node)

        return self._make_rule_dict(rule_db)

    def get_rules(self, context, filters=None, fields=None):
        tenant_id = self._get_tenant_id_for_create(context)
        with context.session.begin(subtransactions=True):
            query = context.session.query(Rule, RuleLinkNode).options(
                orm.subqueryload(Rule.sourceAddress),
                orm.subqueryload(Rule.sourceIPObj),
                orm.subqueryload(Rule.destinationAddress),
                orm.subqueryload(Rule.destinationIPObj),
                orm.subqueryload(Rule.serviceConfig),
                orm.subqueryload(Rule.serviceObj)).filter(
                Rule.tenant_id == tenant_id,
                Rule.id == RuleLinkNode.rule_id)
            rule_tuples = query.all()
        ruleHash = {}
        first_tuple = None
        for rule_tuple in rule_tuples:
            rule = rule_tuple[0]
            node = rule_tuple[1]
            ruleHash[rule['id']] = rule_tuple
            if node['prev_id'] is None:
                if first_tuple is not None:
                    raise Exception("unable to determine the first rule")
                first_tuple = rule_tuple
        if first_tuple is None:
            if len(rule_tuples) == 0:
                return []
            raise Exception("unable to locate the first rule")

        rules = [self._make_rule_dict(first_tuple[0])]
        curr_tuple = first_tuple
        while True:
            curr_rule = curr_tuple[0]
            curr_node = curr_tuple[1]
            next_rule_id = curr_node['next_id']
            if next_rule_id is None:
                break
            next_tuple = ruleHash[next_rule_id]
            next_rule = next_tuple[0]
            next_node = next_tuple[1]
            if next_node['prev_id'] != curr_rule['id']:
                raise Exception("rule order corrupted")
            rules.append(self._make_rule_dict(next_rule))
            curr_tuple = next_tuple

        return rules

    def get_rule(self, context, id, fields=None):
        tenant_id = self._get_tenant_id_for_create(context)
        with context.session.begin(subtransactions=True):
            query = context.session.query(Rule).options(
                orm.subqueryload(Rule.sourceAddress),
                orm.subqueryload(Rule.sourceIPObj),
                orm.subqueryload(Rule.destinationAddress),
                orm.subqueryload(Rule.destinationIPObj),
                orm.subqueryload(Rule.serviceConfig),
                orm.subqueryload(Rule.serviceObj)).filter(
                Rule.tenant_id == tenant_id,
                Rule.id == id)
            rule_db = query.one()
            rule = self._make_rule_dict(rule_db)
        return rule

    def delete_rule(self, context, id):
        tenant_id = self._get_tenant_id_for_create(context)
        with context.session.begin(subtransactions=True):
            rule_db = context.session.query(Rule).filter(
                Rule.tenant_id == tenant_id, Rule.id == id).one()
            rule_node = self._get_rule_link_node(context, id)
            prev_id = rule_node['prev_id']
            next_id = rule_node['next_id']
            if prev_id:
                prev_node = self._get_rule_link_node(context, prev_id)
                prev_node.update({"next_id": next_id})
            if next_id:
                next_node = self._get_rule_link_node(context, next_id)
                next_node.update({"prev_id": prev_id})
            context.session.delete(rule_node)
            context.session.delete(rule_db)

    def _make_ipobj_dict(self, ipobj, fields=None):
        res = {
            'id': ipobj['id'],
            'name': ipobj.get('name'),
            'description': ipobj.get('description')
        }
        value = []
        for addr in ipobj.get('value'):
            value.append(addr['address'])

        res['value'] = value
        return self._fields(res, fields)

    def create_ipobj(self, context, ipobj):
        body = ipobj['ipobj']
        with context.session.begin(subtransactions=True):
            ipobj_db = IPObj(id=uuidutils.generate_uuid(),
                             tenant_id=self._get_tenant_id_for_create(
                                 context, body),
                             name=body['name'],
                             description=body['description'])
            ipobj_db.value = []
            for addr in body['value']:
                ipobj_db.value.append(IPObjAddress(address=addr))
            context.session.add(ipobj_db)

        return self._make_ipobj_dict(ipobj_db)

    def get_ipobjs(self, context, filters=None, fields=None):
        tenant_id = self._get_tenant_id_for_create(context)
        ipobjs = []
        with context.session.begin(subtransactions=True):
            query = context.session.query(IPObj).options(
                orm.subqueryload(IPObj.value)).filter(
                IPObj.tenant_id == tenant_id)
            ipobjs_db = query.all()
            for ipobj_db in ipobjs_db:
                ipobjs.append(self._make_ipobj_dict(ipobj_db))
        return ipobjs

    def get_ipobj(self, context, id, fields=None):
        tenant_id = self._get_tenant_id_for_create(context)
        with context.session.begin(subtransactions=True):
            ipobj_db = context.session.query(IPObj).options(
                orm.subqueryload(IPObj.value)).filter(
                IPObj.tenant_id == tenant_id, IPObj.id == id).one()
            ipobj = self._make_ipobj_dict(ipobj_db)
        return ipobj

    def delete_ipobj(self, context, id):
        tenant_id = self._get_tenant_id_for_create(context)
        with context.session.begin(subtransactions=True):
            ipobj_db = context.session.query(IPObj).filter(
                IPObj.tenant_id == tenant_id, IPObj.id == id).one()
            context.session.delete(ipobj_db)

    def _serviceobj2dict_convert(self, svcobj, svcdict):
        if svcobj['protocol'].lower() == "icmp":
           svcdict['types'] = json.loads(svcobj['values'])
        else:
           svcdict['ports'] = json.loads(svcobj['values'])

        attrs = ['sourcePorts']
        for attr in attrs:
            if attr in svcobj:
                svcdict[attr] = json.loads(svcobj[attr])

    def _make_serviceobj_dict(self, svcobj, fields=None):
        res = {
            'id': svcobj['id'],
            'name': svcobj.get('name'),
            'description': svcobj.get('description'),
            'protocol': svcobj['protocol']
        }
        self._serviceobj2dict_convert(svcobj, res)

        return self._fields(res, fields)

    def _dict2serviceobj(self, svcdict):
        svcobj = {
            'description': svcdict.get('description'),
            'protocol': svcdict['protocol']
        }
        if 'name' in svcdict:
            svcobj['name'] = svcdict['name']
        if svcdict['protocol'].lower() == "icmp":
            if 'types' in svcdict:
                svcobj['values'] = json.dumps(svcdict['types'])
        else:
            if 'ports' in svcdict:
                svcobj['values'] = json.dumps(svcdict['ports'])
        attrs = ['sourcePorts']
        for attr in attrs:
            if attr in svcdict:
                svcobj[attr] = json.dumps(svcdict[attr])
        return svcobj

    def _serviceobj2dict(self, svcobj):
        svcdict = {}
        svcdict['protocol'] = svcobj['protocol']
        self._serviceobj2dict_convert(svcobj, svcdict)
        return svcdict

    def create_serviceobj(self, context, serviceobj):
        body = serviceobj['serviceobj']
        with context.session.begin(subtransactions=True):
            svcobj = self._dict2serviceobj(body)
            svcobj_db = ServiceObj(id=uuidutils.generate_uuid(),
                                   tenant_id=self._get_tenant_id_for_create(
                                       context, body),
                                   name=svcobj['name'],
                                   description=svcobj['description'],
                                   protocol=svcobj['protocol'],
                                   values=svcobj.get('values'),
                                   sourcePorts=svcobj.get('sourcePorts'))
            context.session.add(svcobj_db)

        return self._make_serviceobj_dict(svcobj_db)

    def get_serviceobjs(self, context, filters=None, fields=None):
        tenant_id = self._get_tenant_id_for_create(context)
        svcobjs = []
        with context.session.begin(subtransactions=True):
            query = context.session.query(ServiceObj).filter(
                ServiceObj.tenant_id == tenant_id)
            svcobjs_db = query.all()
            for svcobj_db in svcobjs_db:
                svcobjs.append(self._make_serviceobj_dict(svcobj_db))
        return svcobjs

    def get_serviceobj(self, context, id, fields=None):
        tenant_id = self._get_tenant_id_for_create(context)
        with context.session.begin(subtransactions=True):
            svcobj_db = context.session.query(ServiceObj).filter(
                ServiceObj.tenant_id == tenant_id, ServiceObj.id == id).one()
            svcobj = self._make_serviceobj_dict(svcobj_db)
        return svcobj

    def delete_serviceobj(self, context, id):
        tenant_id = self._get_tenant_id_for_create(context)
        with context.session.begin(subtransactions=True):
            svcobj_db = context.session.query(ServiceObj).filter(
                ServiceObj.tenant_id == tenant_id, ServiceObj.id == id).one()
            context.session.delete(svcobj_db)

    def _make_zone_dict(self, zone, fields=None):
        res = {
            'id': zone['id'],
            'name': zone.get('name'),
            'description': zone.get('description')
        }
        value = []
        for network in zone.get('value'):
            value.append(network['network_id'])

        res['value'] = value
        return self._fields(res, fields)

    def create_zone(self, context, zone):
        body = zone['zone']
        with context.session.begin(subtransactions=True):
            zone_db = Zone(id=uuidutils.generate_uuid(),
                           tenant_id=self._get_tenant_id_for_create(
                               context, body),
                           name=body['name'],
                           description=body['description'])
            zone_db.value = []
            for network_id in body['value']:
                zone_db.value.append(ZoneNetwork(network_id=network_id))
            context.session.add(zone_db)

        return self._make_zone_dict(zone_db)

    def get_zones(self, context, filters=None, fields=None):
        tenant_id = self._get_tenant_id_for_create(context)
        zones = []
        with context.session.begin(subtransactions=True):
            query = context.session.query(Zone).options(
                orm.subqueryload(Zone.value)).filter(
                Zone.tenant_id == tenant_id)
            zones_db = query.all()
            for zone_db in zones_db:
                zones.append(self._make_zone_dict(zone_db))
        return zones

    def get_zone(self, context, id, fields=None):
        tenant_id = self._get_tenant_id_for_create(context)
        with context.session.begin(subtransactions=True):
            zone_db = context.session.query(Zone).options(
                orm.subqueryload(Zone.value)).filter(
                Zone.tenant_id == tenant_id, Zone.id == id).one()
            zone = self._make_zone_dict(zone_db)
        return zone

    def delete_zone(self, context, id):
        tenant_id = self._get_tenant_id_for_create(context)
        with context.session.begin(subtransactions=True):
            zone_db = context.session.query(Zone).filter(
                Zone.tenant_id == tenant_id, Zone.id == id).one()
            context.session.delete(zone_db)
