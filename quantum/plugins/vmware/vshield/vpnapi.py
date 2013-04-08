#!/usr/bin/python

import re
import sqlalchemy as sa
from quantum.db import api as qdbapi
from quantum.db import model_base


class SiteUuid2Vseid(model_base.BASEV2):
    __tablename__ = 'siteuuid2vseid'
    uuid = sa.Column(sa.String(36),
                     sa.ForeignKey("sites.id", ondelete='CASCADE'),
                     primary_key=True)
    vseid = sa.Column(sa.String(36), nullable=False)


def getuuid2vseid(context, uuid, model):
    query = context.session.query(model)
    query = query.filter(model.uuid == uuid)
    if query.count() == 0:
        return None
    return query.one()


def uuid2vseid(context, uuid, model):
    uuid2vseid = getuuid2vseid(context, uuid, model)
    if uuid2vseid is None:
        return None
    return uuid2vseid.vseid


def deluuid2vseid(context, uuid, model):
    uuid2vseid = getuuid2vseid(context, uuid, model)
    if uuid2vseid is None:
        raise Exception("{0} id for {1} not found".format(
            model.__name__, uuid))
    context.session.delete(uuid2vseid)


def getobj(context, model, id):
    query = context.session.query(model)
    return query.filter(model.id == id).one()


class VPNAPI():
    def __init__(self, vse):
        qdbapi.register_models(base=model_base.BASEV2)
        self.vse = vse
        #self.uriprefix = '/api/3.0/edges/{0}/ipsec'.format(
        self.uriprefix = '/api/4.0/edges/{0}/ipsec'.format(
            vse.get_edgeId())
        self.enabled = False

    def vpnaas2vsmSitev3(self, context, site):
        print site
        s = {
            'name': site['name'],
            'localIP': site['local_endpoint'],
            'peerIP': site['peer_endpoint'],
            'localId': site['local_id'],
            'peerId': site['peer_id'],
            'psk': site['psk'],
            'mtu': site['mtu']
        }
        return s

    def vpnaas2vsmSite(self, context, site):
        s = {
            'name': site['name'],
            'description': site['description'],
            'localId': site['local_id'],
            'localIp': site['local_endpoint'],
            'peerId': site['peer_id'],
            'peerIp': site['peer_endpoint'],
            'encryptionAlgorithm': 'aes256',
            'mtu': site['mtu'],
            'enablePfs': 'true',
            'dhGroup': 'dh2',
            'localSubnets': {},
            'peerSubnets': {},
            'psk': site['psk'],
            'certificate': None,
            'authenticationMode': 'psk',
        }
        match = re.search("(.*?)-(.*)", site['pri_networks'])
        if match:
           s['localSubnets']['subnets'] = match.group(1).split(",")
           s['peerSubnets']['subnets'] = match.group(2).split(",")
        return s


    def vpnaas2vsmIPSec(self, context, site):
        conf = {
             'enabled': 'true',
             'logging':{
                'enable': 'true',
                'logLevel': 'info'
             },
             'global':{
                'psk': None,
                'serviceCertificate': None
             },   
             'sites': {
                'sites': [site]
             }
        }
        return conf


    def get_site_vseid(self, context, uuid):
        return uuid2vseid(context, uuid, SiteUuid2Vseid)


    def create_site(self, context, site):
        uri = self.uriprefix + '/config'
        s = self.vpnaas2vsmSite(context, site)
        request = self.vpnaas2vsmIPSec(context, s)
        header, response = self.vse.vsmconfig('PUT', uri, request)
        return response

    def update_site(self, context, site):
        s = self.vpnaas2vsmSite(context, site)
        request = self.vpnaas2vsmIPSec(context, s)
        uri = self.uriprefix + '/config'
        response = self.vse.api('PUT', uri, request)
        return response

    def delete_site(self, context, site):
        uri = self.uriprefix + '/config'
        response = self.vse.api('DELETE', uri)
        return response

    def get_vsm_vpn_config(self):
        uri = self.uriprefix + '/config'
        return self.vse.api('GET', uri)

    def __reconfigure(self, config):
        uri = self.uriprefix + '/config'
        self.vse.vsmconfig('PUT', uri, config)
