#!/usr/bin/python

import copy
import json

from vseapi import VseAPI
import sqlalchemy as sa
from sqlalchemy import orm
from quantum.db import api as qdbapi
from quantum.db import model_base
from quantum.db.loadbalancer.loadbalancer_db import Pool


class IPObjUuid2Vseid(model_base.BASEV2):
    __tablename__ = 'ipobjuuid2vseid'
    uuid = sa.Column(sa.String(36),
                     sa.ForeignKey("ipobjs.id", ondelete='CASCADE'),
                     primary_key=True)
    vseid = sa.Column(sa.String(36), nullable=False)


class ServiceObjUuid2Vseid(model_base.BASEV2):
    __tablename__ = 'serviceobjuuid2vseid'
    uuid = sa.Column(sa.String(36),
                     sa.ForeignKey("serviceobjs.id", ondelete='CASCADE'),
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

def list2str(value):
    if value == None:
        return None
    if len(value) == 0:
        return ""
    rstr = ""
    for v in value:
        rstr = rstr + "," + v
    return rstr[1:]


class FirewallAPI():
    def __init__(self, vse):
        qdbapi.register_models(base=model_base.BASEV2)
        self.vse = vse
#        self.uriprefix = '/api/3.0/edges/{0}/loadbalancer'.format(
        self.uriprefix = '/api/4.0/edges/{0}/firewall'.format(
            vse.get_edgeId())
        self.ipseturi = '/api/2.0/services/ipset'
        self.appuri = '/api/2.0/services/application'

    def fwaas2vsmRule(self, rule):
        if rule['action']:
            action = "accept"
        else:
            action = "drop"
        vsmRule = {
            "ruleType": "user",
            "name": rule['name'],
#            "description": rule.get('descrption'),
            "description": rule['name'],
            "enabled": rule['enabled'],
            "action": action
        }
        src = rule['source']
        dst = rule['destination']
        svc = rule['service']

        srcGroupObjIds = []
        if src.get("ipobjs"):
            # convert ipobj uuid to groupingObjectId
            pass

        dstGroupObjIds = []
        if dst.get("ipobjs"):
            # convert ipobj uuid to groupingObjectId
            pass

        appIds = []
        if svc.get("serviceobjs"):
            # convert serviceobj uuid to applicationId
            pass

        vsmSrc = {
            "ipAddress": src.get("addresses"),
            "groupingObjectId": srcGroupObjIds,
            "vnicGroupId": []
        }
        vsmDst = {
            "ipAddress": dst.get("addresses"),
            "groupingObjectId": dstGroupObjIds,
            "vnicGroupId": []
        }
        vsmApp = {
            "applicationId": appIds,
#            "service": svc.get('services')
            "service": None
        }
        vsmRule['source'] = vsmSrc
        vsmRule['destination'] = vsmDst
        vsmRule['application'] = vsmApp

        return vsmRule

    def create_rule(self, context, rule, location=None):
        request = self.fwaas2vsmRule(rule)
        uri = self.uriprefix + '/config/rules'
        header, response = self.vse.vsmconfig('POST', uri, request)
        objuri = header['location']
        ruleId = objuri[objuri.rfind("/")+1:]
        """
        uuid2vseid = PoolUuid2Vseid(uuid=pool['id'], vseid=poolId)
        context.session.add(uuid2vseid)
        print "create_pool: response '{0}'".format(response)
        """
        return response

    def fwaas2vsmIpset(self, ipset):
        ipset = {
            "name": ipset['name'],
            "description": ipset.get('description'),
            "value": list2str(ipset['value'])
        }
        return ipset

    def create_ipset(self, context, ipobj):
        request = self.fwaas2vsmIpset(ipobj)
        uri = self.ipseturi + "/{}".format(self.vse.get_edgeId())
        header, response = self.vse.vsmconfig('POST', uri, request, decode=False)
        objuri = header['location']
        ipsetId = objuri[objuri.rfind("/")+1:]
        uuid2vseid = IPObjUuid2Vseid(uuid=ipobj['id'], vseid=ipsetId)
        context.session.add(uuid2vseid)
        return response

    def delete_ipset(self, context, ipobj):
        ipsetId = uuid2vseid(context, ipobj['id'], IPObjUuid2Vseid)
        uri = self.ipseturi + "/{}".format(ipsetId)
        header, response = self.vse.vsmconfig('DELETE', uri)

    def fwaas2vsmApp(self, service):
        element = {
            'applicationProtocol': service['protocol']
        }
        if 'sourcePort' in service:
            element['sourcePort'] = list2str(service['sourcePort'])
        if 'ports' in service:
            element['value'] = list2str(service['ports'])
        elif 'types' in service:
            element['value'] = list2str(service['types'])

        app = {
            "name": service['name'],
            "description": service.get('description'),
            "element": element
        }
        return app

    def create_application(self, context, svcobj):
        request = self.fwaas2vsmApp(svcobj)
        uri = self.appuri + "/{}".format(self.vse.get_edgeId())
        header, response = self.vse.vsmconfig('POST', uri, request, decode=False)
        objuri = header['location']
        appId = objuri[objuri.rfind("/")+1:]
        uuid2vseid = ServiceObjUuid2Vseid(uuid=ipobj['id'], vseid=appId)
        context.session.add(uuid2vseid)
        return response

    def delete_application(self, context, svcobj):
        appId = uuid2vseid(context, svcobj['id'], ServiceObjUuid2Vseid)
        uri = self.appuri + "/{}".format(appId)
        header, response = self.vse.vsmconfig('DELETE', uri)


