# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 OpenStack Foundation.
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

import abc

from oslo.config import cfg

from quantum.api import extensions
from quantum.api.v2 import attributes as attr
from quantum.api.v2 import base
from quantum.common import exceptions as qexception
from quantum import manager
from quantum.plugins.common import constants
from quantum.plugins.services.service_base import ServicePluginBase


RESOURCE_ATTRIBUTE_MAP = {
    'rules': {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:uuid': None},
               'is_visible': True,
               'primary_key': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'validate': {'type:string': None},
                      'required_by_policy': True,
                      'is_visible': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'validate': {'type:string': None},
                 'default': '',
                 'is_visible': True},
        'description': {'allow_post': True, 'allow_put': True,
                        'validate': {'type:string': None},
                        'is_visible': True, 'default': ''},
        'source': {'allow_post': True, 'allow_put': True,
                   'default': None,
                   'is_visible': True},
        'destination': {'allow_post': True, 'allow_put': True,
                        'default': None,
                        'is_visible': True},
        'service': {'allow_post': True, 'allow_put': True,
                    'default': None,
                    'is_visible': True},
        'action': {'allow_post': True, 'allow_put': True,
                   'is_visible': True},
        'log': {'allow_post': True, 'allow_put': True,
                'default': 'disabled', 'is_visible': True},
        'enabled': {'allow_post': True, 'allow_put': True,
                    'default': False, 'is_visible': True},
        'location': {'allow_post': True, 'allow_put': False,
                    'default': None, 'is_visible': False},
    },
    'ipobjs': {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:uuid': None},
               'is_visible': True,
               'primary_key': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'validate': {'type:string': None},
                      'required_by_policy': True,
                      'is_visible': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'validate': {'type:string': None},
                 'default': '',
                 'is_visible': True},
        'description': {'allow_post': True, 'allow_put': True,
                        'validate': {'type:string': None},
                        'is_visible': True, 'default': ''},
        'value': {'allow_post': True, 'allow_put': True,
                  'is_visible': True}
    },
    'serviceobjs': {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:uuid': None},
               'is_visible': True,
               'primary_key': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'validate': {'type:string': None},
                      'required_by_policy': True,
                      'is_visible': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'validate': {'type:string': None},
                 'default': '',
                 'is_visible': True},
        'description': {'allow_post': True, 'allow_put': True,
                        'validate': {'type:string': None},
                        'is_visible': True, 'default': ''},
        'value': {'allow_post': True, 'allow_put': True,
                  'is_visible': True}
    },
    'zones': {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:uuid': None},
               'is_visible': True,
               'primary_key': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'validate': {'type:string': None},
                      'required_by_policy': True,
                      'is_visible': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'validate': {'type:string': None},
                 'default': '',
                 'is_visible': True},
        'description': {'allow_post': True, 'allow_put': True,
                        'validate': {'type:string': None},
                        'is_visible': True, 'default': ''},
        'value': {'allow_post': True, 'allow_put': True,
                  'is_visible': True}
    }
}


class Firewall(extensions.ExtensionDescriptor):

    @classmethod
    def get_name(cls):
        return "Firewall service"

    @classmethod
    def get_alias(cls):
        return "fwaas"

    @classmethod
    def get_description(cls):
        return "Extension for Firewall service"

    @classmethod
    def get_namespace(cls):
        return "http://wiki.openstack.org/Quantum/FWaaS/API_1.0"

    @classmethod
    def get_updated(cls):
        return "2013-03-27T10:00:00-00:00"

    @classmethod
    def get_resources(cls):
        my_plurals = [(key, key[:-1]) for key in RESOURCE_ATTRIBUTE_MAP.keys()]
        attr.PLURALS.update(dict(my_plurals))
        resources = []
        plugin = manager.QuantumManager.get_service_plugins()[
            constants.FIREWALL]
        for collection_name in RESOURCE_ATTRIBUTE_MAP:
            # Special handling needed for resources with 'y' ending
            # (e.g. proxies -> proxy)
            resource_name = collection_name[:-1]
            params = RESOURCE_ATTRIBUTE_MAP[collection_name]

            member_actions = {}

            controller = base.create_resource(
                collection_name, resource_name, plugin, params,
                member_actions=member_actions,
                allow_pagination=cfg.CONF.allow_pagination,
                allow_sorting=cfg.CONF.allow_sorting)

            resource = extensions.ResourceExtension(
                collection_name,
                controller,
                path_prefix=constants.COMMON_PREFIXES[constants.FIREWALL],
                member_actions=member_actions,
                attr_map=params)
            resources.append(resource)

        return resources

    @classmethod
    def get_plugin_interface(cls):
        return FirewallPluginBase

    def update_attributes_map(self, attributes):
        super(Firewall, self).update_attributes_map(
            attributes, extension_attrs_map=RESOURCE_ATTRIBUTE_MAP)

    def get_extended_resources(self, version):
        if version == "2.0":
            return RESOURCE_ATTRIBUTE_MAP
        else:
            return {}


class FirewallPluginBase(ServicePluginBase):
    __metaclass__ = abc.ABCMeta

    def get_plugin_name(self):
        return constants.FIREWALL

    def get_plugin_type(self):
        return constants.FIREWALL

    def get_plugin_description(self):
        return 'Firewall service plugin'

"""
    @abc.abstractmethod
    def get_rules(self, context, filters=None, fields=None):
        pass

    @abc.abstractmethod
    def get_rule(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def create_rule(self, context, vip):
        pass

    @abc.abstractmethod
    def update_rule(self, context, id, vip):
        pass

    @abc.abstractmethod
    def delete_rule(self, context, id):
        pass

    @abc.abstractmethod
    def get_ipobjs(self, context, filters=None, fields=None):
        pass

    @abc.abstractmethod
    def get_ipobj(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def create_ipobj(self, context, pool):
        pass

    @abc.abstractmethod
    def update_ipobj(self, context, id, pool):
        pass

    @abc.abstractmethod
    def delete_ipobj(self, context, id):
        pass

    @abc.abstractmethod
    def get_serviceobjs(self, context, filters=None, fields=None):
        pass

    @abc.abstractmethod
    def get_serviceobj(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def create_serviceobj(self, context, pool):
        pass

    @abc.abstractmethod
    def update_serviceobj(self, context, id, pool):
        pass

    @abc.abstractmethod
    def delete_serviceobj(self, context, id):
        pass

    @abc.abstractmethod
    def get_zones(self, context, filters=None, fields=None):
        pass

    @abc.abstractmethod
    def get_zone(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def create_zone(self, context, pool):
        pass

    @abc.abstractmethod
    def update_zone(self, context, id, pool):
        pass

    @abc.abstractmethod
    def delete_zone(self, context, id):
        pass

"""
