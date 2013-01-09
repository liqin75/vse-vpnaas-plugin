# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2012, Nachi Ueno, NTT MCL, Inc.
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

import netaddr

from quantum.common import constants as q_const
from quantum.db import models_v2
from quantum.db import securitygroups_db as sg_db
from quantum.openstack.common import log as logging

LOG = logging.getLogger(__name__)


IP_MASK = {q_const.IPv4: 32,
           q_const.IPv6: 128}


DIRECTION_IP_PREFIX = {'ingress': 'source_ip_prefix',
                       'egress': 'dest_ip_prefix'}


class SecurityGroupServerRpcMixin(sg_db.SecurityGroupDbMixin):

    def create_security_group_rule(self, context, security_group_rule):
        bulk_rule = {'security_group_rules': [security_group_rule]}
        rule = self.create_security_group_rule_bulk_native(context,
                                                           bulk_rule)[0]
        sgids = [rule['security_group_id']]
        self.notifier.security_groups_rule_updated(context, sgids)
        return rule

    def create_security_group_rule_bulk(self, context,
                                        security_group_rule):
        rules = super(SecurityGroupServerRpcMixin,
                      self).create_security_group_rule_bulk_native(
                          context, security_group_rule)
        sgids = set([r['security_group_id'] for r in rules])
        self.notifier.security_groups_rule_updated(context, list(sgids))
        return rules

    def delete_security_group_rule(self, context, sgrid):
        rule = self.get_security_group_rule(context, sgrid)
        super(SecurityGroupServerRpcMixin,
              self).delete_security_group_rule(context, sgrid)
        self.notifier.security_groups_rule_updated(context,
                                                   [rule['security_group_id']])


class SecurityGroupServerRpcCallbackMixin(object):
    """A mix-in that enable SecurityGroup agent

    support in plugin implementations.
    """

    def security_group_rules_for_devices(self, context, **kwargs):
        """ return security group rules for each port

        also convert source_group_id rule
        to source_ip_prefix rule

        :params devices: list of devices
        :returns: port correspond to the devices with security group rules
        """
        devices = kwargs.get('devices')

        ports = {}
        for device in devices:
            port = self.get_port_from_device(device)
            if not port:
                continue
            if port['device_owner'].startswith('network:'):
                continue
            ports[port['id']] = port
        return self._security_group_rules_for_ports(context, ports)

    def _select_rules_for_ports(self, context, ports):
        if not ports:
            return []
        sg_binding_port = sg_db.SecurityGroupPortBinding.port_id
        sg_binding_sgid = sg_db.SecurityGroupPortBinding.security_group_id

        sgr_sgid = sg_db.SecurityGroupRule.security_group_id

        query = context.session.query(sg_db.SecurityGroupPortBinding,
                                      sg_db.SecurityGroupRule)
        query = query.join(sg_db.SecurityGroupRule,
                           sgr_sgid == sg_binding_sgid)
        query = query.filter(sg_binding_port.in_(ports.keys()))
        return query.all()

    def _select_ips_for_source_group(self, context, source_group_ids):
        ips_by_group = {}
        if not source_group_ids:
            return ips_by_group
        for source_group_id in source_group_ids:
            ips_by_group[source_group_id] = []

        ip_port = models_v2.IPAllocation.port_id
        sg_binding_port = sg_db.SecurityGroupPortBinding.port_id
        sg_binding_sgid = sg_db.SecurityGroupPortBinding.security_group_id

        query = context.session.query(sg_binding_sgid,
                                      models_v2.IPAllocation.ip_address)
        query = query.join(models_v2.IPAllocation,
                           ip_port == sg_binding_port)
        query = query.filter(sg_binding_sgid.in_(source_group_ids))
        ip_in_db = query.all()
        for security_group_id, ip_address in ip_in_db:
            ips_by_group[security_group_id].append(ip_address)
        return ips_by_group

    def _select_source_group_ids(self, ports):
        source_group_ids = []
        for port in ports.values():
            for rule in port.get('security_group_rules'):
                source_group_id = rule.get('source_group_id')
                if source_group_id:
                    source_group_ids.append(source_group_id)
        return source_group_ids

    def _select_network_ids(self, ports):
        return set((port['network_id'] for port in ports.values()))

    def _select_dhcp_ips_for_network_ids(self, context, network_ids):
        if not network_ids:
            return {}
        query = context.session.query(models_v2.Port,
                                      models_v2.IPAllocation.ip_address)
        query = query.join(models_v2.IPAllocation)
        query = query.filter(models_v2.Port.network_id.in_(network_ids))
        owner = q_const.DEVICE_OWNER_DHCP
        query = query.filter(models_v2.Port.device_owner == owner)
        ips = {}

        for network_id in network_ids:
            ips[network_id] = []

        for port, ip in query.all():
            ips[port['network_id']].append(ip)
        return ips

    def _convert_source_group_id_to_ip_prefix(self, context, ports):
        source_group_ids = self._select_source_group_ids(ports)
        ips = self._select_ips_for_source_group(context, source_group_ids)
        for port in ports.values():
            updated_rule = []
            for rule in port.get('security_group_rules'):
                source_group_id = rule.get('source_group_id')
                direction = rule.get('direction')
                direction_ip_prefix = DIRECTION_IP_PREFIX[direction]
                if not source_group_id:
                    updated_rule.append(rule)
                    continue

                port['security_group_source_groups'].append(source_group_id)
                base_rule = rule
                for ip in ips[source_group_id]:
                    if ip in port.get('fixed_ips', []):
                        continue
                    ip_rule = base_rule.copy()
                    version = netaddr.IPAddress(ip).version
                    ethertype = 'IPv%s' % version
                    if base_rule['ethertype'] != ethertype:
                        continue
                    ip_rule[direction_ip_prefix] = "%s/%s" % (
                        ip, IP_MASK[ethertype])
                    updated_rule.append(ip_rule)
            port['security_group_rules'] = updated_rule
        return ports

    def _add_default_egress_rule(self, port, ethertype, ips):
        """ Adding default egress rule which allows all egress traffic. """
        egress_rule = [r for r in port['security_group_rules']
                       if (r['direction'] == 'egress' and
                           r['ethertype'] == ethertype)]
        if len(egress_rule) > 0:
            return
        for ip in port['fixed_ips']:
            version = netaddr.IPAddress(ip).version
            if "IPv%s" % version == ethertype:
                default_egress_rule = {'direction': 'egress',
                                       'ethertype': ethertype}
                port['security_group_rules'].append(default_egress_rule)
                return

    def _add_ingress_dhcp_rule(self, port, ips):
        dhcp_ips = ips.get(port['network_id'])
        for dhcp_ip in dhcp_ips:
            if not netaddr.IPAddress(dhcp_ip).version == 4:
                return

            dhcp_rule = {'direction': 'ingress',
                         'ethertype': q_const.IPv4,
                         'protocol': 'udp',
                         'port_range_min': 68,
                         'port_range_max': 68,
                         'source_port_range_min': 67,
                         'source_port_range_max': 67}
            dhcp_rule['source_ip_prefix'] = "%s/%s" % (dhcp_ip,
                                                       IP_MASK[q_const.IPv4])
            port['security_group_rules'].append(dhcp_rule)

    def _add_ingress_ra_rule(self, port, ips):
        ra_ips = ips.get(port['network_id'])
        for ra_ip in ra_ips:
            if not netaddr.IPAddress(ra_ip).version == 6:
                return

            ra_rule = {'direction': 'ingress',
                       'ethertype': q_const.IPv6,
                       'protocol': 'icmp'}
            ra_rule['source_ip_prefix'] = "%s/%s" % (ra_ip,
                                                     IP_MASK[q_const.IPv6])
            port['security_group_rules'].append(ra_rule)

    def _apply_provider_rule(self, context, ports):
        network_ids = self._select_network_ids(ports)
        ips = self._select_dhcp_ips_for_network_ids(context, network_ids)
        for port in ports.values():
            self._add_default_egress_rule(port, q_const.IPv4, ips)
            self._add_default_egress_rule(port, q_const.IPv6, ips)
            self._add_ingress_ra_rule(port, ips)
            self._add_ingress_dhcp_rule(port, ips)

    def _security_group_rules_for_ports(self, context, ports):
        rules_in_db = self._select_rules_for_ports(context, ports)
        for (binding, rule_in_db) in rules_in_db:
            port_id = binding['port_id']
            port = ports[port_id]
            direction = rule_in_db['direction']
            rule_dict = {
                'security_group_id': rule_in_db['security_group_id'],
                'direction': direction,
                'ethertype': rule_in_db['ethertype'],
            }
            for key in ('protocol', 'port_range_min', 'port_range_max',
                        'source_ip_prefix', 'source_group_id'):
                if rule_in_db.get(key):
                    if key == 'source_ip_prefix' and direction == 'egress':
                        rule_dict['dest_ip_prefix'] = rule_in_db[key]
                        continue
                    rule_dict[key] = rule_in_db[key]
            port['security_group_rules'].append(rule_dict)
        self._apply_provider_rule(context, ports)
        return self._convert_source_group_id_to_ip_prefix(context, ports)