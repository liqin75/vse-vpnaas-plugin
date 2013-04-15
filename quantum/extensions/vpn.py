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

# VPN Exceptions
class SiteNotFound(qexception.NotFound):
    message = _("Site %(site_id)s could not be found")


class SiteExists(qexception.QuantumException):
    message = _("Another Site already exists for local_endpoint") 
    message+= _(" %(local_endpoint)s and peer_endpoint %(peer_endpoint)s")


class IsakmpPolicyNotFound(qexception.NotFound):
    message = _("ISAKMP policy %(isakmp_policy_id)s could not be found")


class IPSecPolicyNotFound(qexception.NotFound):
    message = _("IPSec policy %(ipsec_policy_id)s could not be found")


class IPSecPolicyExists(qexception.QuantumException):
    message = _("Another Ipsec Policy already exists") 


class TrustProfileNotFound(qexception.NotFound):
    message = _("Trust profile %(trust_profile)s could not be found")


class StateInvalid(qexception.QuantumException):
    message = _("Invalid state %(state)s of VPN resource %(id)s")

RESOURCE_ATTRIBUTE_MAP = {
    'sites': {
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
        'subnet_id': {'allow_post': True, 'allow_put': False,
                      'validate': {'type:uuid': None},
                      'is_visible': True},
        'local_endpoint': {'allow_post': True, 'allow_put': True,
                    'validate': {'type:ip_address': None},
                    'is_visible': True},
        'peer_endpoint':  {'allow_post': True, 'allow_put': True,
                    'validate': {'type:ip_address': None},
                    'is_visible': True},
        'local_id': {'allow_post': True, 'allow_put': True,
                    'validate': {'type:string': None},
                    'default': '',
                    'is_visible': True},
        'peer_id':  {'allow_post': True, 'allow_put': True,
                    'validate': {'type:string': None},
                    'default': '',
                    'is_visible': True},
        'pri_networks': {'allow_post': True, 'allow_put': True,
                         'is_visible': True},
        'isakmp_policy_id': {'allow_post': True, 'allow_put': True,
                             'validate': {'type:uuid': None},
                             'default': attr.ATTR_NOT_SPECIFIED,
                             'is_visible': True},
        'ipsec_policy_id':  {'allow_post': True, 'allow_put': True,
                             'validate': {'type:uuid': None},
                             'default': attr.ATTR_NOT_SPECIFIED,
                             'is_visible': True},
        'trust_profile_id': {'allow_post': True, 'allow_put': True,
                             'validate': {'type:uuid': None},
                             'default': attr.ATTR_NOT_SPECIFIED,
                             'is_visible': True},
        'psk': {'allow_post': True, 'allow_put': True,
                'validate': {'type:string': None},
                'default': '',
                'is_visible': True},
        'nat_traversal': {'allow_post': True, 'allow_put': True,
                          'default': True,
                          'convert_to': attr.convert_to_boolean,
                          'is_visible': True},
        'mtu': {'allow_post': True, 'allow_put': True,
                'validate': {'type:non_negative': None},
                'convert_to': attr.convert_to_int,
                'default': 1500,
                'is_visible': True},
        'dpd_delay': {'allow_post': True, 'allow_put': True,
                      'validate': {'type:non_negative': None},
                      'convert_to': attr.convert_to_int,
                      'default': 30,
                      'is_visible': True},
        'dpd_timeout': {'allow_post': True, 'allow_put': True,
                        'validate': {'type:non_negative': None},
                        'convert_to': attr.convert_to_int,
                        'default': 120,
                        'is_visible': True},
    },
    'isakmp_policys': {
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
        'authentication_mode': {'allow_post': True, 'allow_put': True,
                                'validate': {'type:values': ['psk','x.509']},
                                'default': 'psk',
                                'is_visible': True},
        'encryption_algorithm': {'allow_post': True, 'allow_put': True,
                                 'validate': {
                                    'type:values':
                                       ['3des', 'aes128', 'aes256', 'aesgcm']},
                                 'default': 'aes256',
                                 'is_visible': True},
        'authentication_algorithm': {'allow_post': True, 'allow_put': True,
                                     'validate': {'type:values': ['sha1']},
                                     'default': 'sha1',
                                     'is_visible': True},
        'enabe_pfs': {'allow_post': True, 'allow_put': True,
                      'default': True,
                      'convert_to': attr.convert_to_boolean,
                      'is_visible': True},
        'dh_group': {'allow_post': True, 'allow_put': True,
                     'validate': {'type:values': ['1', '2', '5']},
                     'default': '2',
                     'is_visible': True},
        'life_time': {'allow_post': True, 'allow_put': True,
                      'default': 28800,
                      'validate': {'type:non_negative': None},
                      'convert_to': attr.convert_to_int,
                      'is_visible': True}
    },
    'ipsec_policys': {
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
        'encryption_algorithm': {'allow_post': True, 'allow_put': True,
                                 'validate': {
                                    'type:values':
                                       ['3des', 'aes128', 'aes256', 'aesgcm']},
                                 'default': 'aes256',
                                 'is_visible': True},
        'authentication_algorithm': {'allow_post': True, 'allow_put': True,
                                     'validate': {'type:values': ['sha1']},
                                     'default': 'sha1',
                                     'is_visible': True},
        'dh_group': {'allow_post': True, 'allow_put': True,
                     'validate': {'type:values': ['1', '2', '5']},
                     'default': '2',
                     'is_visible': True},
        'life_time': {'allow_post': True, 'allow_put': True,
                      'default': 3600,
                      'validate': {'type:non_negative': None},
                      'convert_to': attr.convert_to_int,
                      'is_visible': True},
        'life_size': {'allow_post': True, 'allow_put': True,
                      'default': 28800,
                      'validate': {'type:non_negative': None},
                      'convert_to': attr.convert_to_int,
                      'is_visible': True}
    },
    'trust_profiles': {
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
        'trust_ca': {'allow_post': True, 'allow_put': True,
                     'is_visible': True},
        'crl': {'allow_post': True, 'allow_put': True,
                'is_visible': True, 'default': ''},
        'server_certificate': {'allow_post': True, 'allow_put': True,
                               'is_visible': True}

   }

}

class Vpn(extensions.ExtensionDescriptor):

    @classmethod
    def get_name(cls):
        return "VPN service"

    @classmethod
    def get_alias(cls):
        return "vpnaas"

    @classmethod
    def get_description(cls):
        return "Extension for VPN service"

    @classmethod
    def get_namespace(cls):
        return "http://wiki.openstack.org/Quantum/VPNaaS/API_1.0"

    @classmethod
    def get_updated(cls):
        return "2013-03-25T10:00:00-00:00"

    @classmethod
    def get_resources(cls):
        my_plurals = [(key, key[:-1]) for key in RESOURCE_ATTRIBUTE_MAP.keys()]
        attr.PLURALS.update(dict(my_plurals))
        resources = []
        plugin = manager.QuantumManager.get_service_plugins()[
            constants.VPN]
        for collection_name in RESOURCE_ATTRIBUTE_MAP:
            # Special handling needed for resources with 'y' ending
            # (e.g. proxies -> proxy)
            resource_name = collection_name[:-1]
            params = RESOURCE_ATTRIBUTE_MAP[collection_name]

            member_actions = {}
            if resource_name == 'site':
                member_actions = {'stats': 'GET'}

            controller = base.create_resource(
                collection_name, resource_name, plugin, params,
                member_actions=member_actions,
                allow_pagination=cfg.CONF.allow_pagination,
                allow_sorting=cfg.CONF.allow_sorting)

            resource = extensions.ResourceExtension(
                collection_name,
                controller,
                path_prefix=constants.COMMON_PREFIXES[constants.VPN],
                member_actions=member_actions,
                attr_map=params)
            resources.append(resource)

        return resources

    @classmethod
    def get_plugin_interface(cls):
        return VPNPluginBase

    def update_attributes_map(self, attributes):
        super(Vpn, self).update_attributes_map(
            attributes, extension_attrs_map=RESOURCE_ATTRIBUTE_MAP)

    def get_extended_resources(self, version):
        if version == "2.0":
            return RESOURCE_ATTRIBUTE_MAP
        else:
            return {}


class VPNPluginBase(ServicePluginBase):
    __metaclass__ = abc.ABCMeta

    def get_plugin_name(self):
        return constants.VPN

    def get_plugin_type(self):
        return constants.VPN

    def get_plugin_description(self):
        return ' VPN service plugin'

    @abc.abstractmethod
    def get_sites(self, context, filters=None, fields=None):
        pass

    @abc.abstractmethod
    def get_site(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def create_site(self, context, vip):
        pass

    @abc.abstractmethod
    def update_site(self, context, id, vip):
        pass

    @abc.abstractmethod
    def delete_site(self, context, id):
        pass

    @abc.abstractmethod
    def get_isakmp_policys(self, context, filters=None, fields=None):
        pass

    @abc.abstractmethod
    def get_isakmp_policy(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def create_isakmp_policy(self, context, isakmp_policy):
        pass

    @abc.abstractmethod
    def update_isakmp_policy(self, context, id, isakmp_policy):
        pass

    @abc.abstractmethod
    def delete_isakmp_policy(self, context, id):
        pass

    @abc.abstractmethod
    def get_ipsec_policys(self, context, filters=None, fields=None):
        pass

    @abc.abstractmethod
    def get_ipsec_policy(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def create_ipsec_policy(self, context, ipsec_policy):
        pass

    @abc.abstractmethod
    def update_ipsec_policy(self, context, id, ipsec_policy):
        pass

    @abc.abstractmethod
    def delete_ipsec_policy(self, context, id):
        pass

    @abc.abstractmethod
    def get_trust_profiles(self, context, filters=None, fields=None):
        pass

    @abc.abstractmethod
    def get_trust_profile(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def create_trust_profile(self, context, trust_profile):
        pass

    @abc.abstractmethod
    def update_trust_profile(self, context, id, trust_profile):
        pass

    @abc.abstractmethod
    def delete_trust_profile(self, context, id):
        pass

    @abc.abstractmethod
    def stats(self, context, site_id):
        pass
