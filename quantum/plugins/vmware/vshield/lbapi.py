#!/usr/bin/python

import json
import copy
from vseapi import VseAPI
from vnicapi import VNicAPI
import sqlalchemy as sa
from sqlalchemy import orm
from quantum.db import api as qdbapi
from quantum.db import model_base
import json
from quantum.db.loadbalancer.loadbalancer_db import Pool

class PoolUuid2Vseid(model_base.BASEV2):
    __tablename__ = 'pooluuid2vseid'
    uuid = sa.Column(sa.String(36),
                     sa.ForeignKey("pools.id", ondelete='CASCADE'),
                     primary_key=True)
    vseid = sa.Column(sa.Integer, nullable=False)

class VipUuid2Vseid(model_base.BASEV2):
    __tablename__ = 'vipuuid2vseid'
    uuid = sa.Column(sa.String(36),
                     sa.ForeignKey("vips.id", ondelete='CASCADE'),
                     primary_key=True)
    vseid = sa.Column(sa.Integer, nullable=False)

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
    context.session.delete(uuid2vseid)

def getobj(context, model, id):
    query = context.session.query(model)
    return query.filter(model.id == id).one()

class LoadBalancerAPI():

    def __init__(self, vse):
        qdbapi.register_models(base=model_base.BASEV2)
        self.vse = vse
        self.initialized = True

    def init(self):
        if self.initialized:
            return

        vnicapi = VNicAPI(self.vse)
        vnicapi.config([{
            'ip': '100.0.0.1',
            'name': 'external',
            'netmask': '255.255.255.0',
            'index': 0
        },{ 
            'ip': '101.0.0.1',
            'name': 'inside',
            'netmask': '255.255.255.0',
            'index': 1
        },{ 
            'ip': '102.0.0.1',
            'name': 'outside',
            'netmask': '255.255.255.0',
            'index': 2
        }])
        self.initialized = True

    def lbaas2vsmPool(self, pool):
        vsepool = {
            'name': pool['name'],
            'servicePorts': [{
                'protocol': pool['protocol'],
                'algorithm': pool['lb_method'],
            }],
            'members': []
        }
        for member in pool['members']:
            vsepool['members'].append({
                'ipAddress': member['address'],
                'servicePortList': [{
                    'protocol': pool['protocol'],
                    'port': member['port']
                }]
            })
        return vsepool

    def lbaas2vsmVS(self, context, vip):
        print vip
        vseid = uuid2vseid(context, vip['pool_id'], PoolUuid2Vseid)
        if vseid is None:
            raise Exception("pool id for {} not found".format(vip['pool_id']))
        vs = {
            'name': vip['name'],
            'ipAddress': vip['address'],
            'serviceProfileList': [{
                'protocol': vip['protocol'],
                'port': vip['port']
            }],
            'pool': {
                'id': vseid
            }
        }
        return vs

    def get_vip_vseid(self, context, uuid):
        return uuid2vseid(context, uuid, VipUuid2Vseid)

    def get_pool_vseid(self, context, uuid):
        return uuid2vseid(context, uuid, PoolUuid2Vseid)

    def __pool_ready(self, pool):
        return len(pool['members']) > 0

    def create_pool(self, context, pool):
        if not self.__pool_ready(pool):
            print "no member. skip pool created"
            return None
        request = self.lbaas2vsmPool(pool)
        uri = '/api/3.0/edges/{}/loadbalancer/config/pools'.format(self.vse.get_edgeId())
        self.init()
        response = self.vse.api('POST', uri, request)
        uuid2vseid = PoolUuid2Vseid(uuid=pool['id'], vseid=response['id'])
        context.session.add(uuid2vseid)
        print "create_pool: response '{}'".format(response)
        return response

    def update_pool(self, context, pool):
        vseid = uuid2vseid(context, pool['id'], PoolUuid2Vseid)
        if vseid is None:
            raise Exception("pool id for {} not found".format(pool['id']))
        uri = '/api/3.0/edges/{}/loadbalancer/config/pools/{}'.format(self.vse.get_edgeId(), vseid)
        request = self.lbaas2vsmPool(pool)
        self.init()
        response = self.vse.api('PUT', uri, request)
        return response

    def delete_pool(self, context, pool):
        #vseid = uuid2vseid(context, pool['id'], PoolUuid2Vseid)
        vseid = pool['vseid']
        if vseid is None:
            raise Exception("pool id for {} not found".format(pool['id']))
        deluuid2vseid(context, pool['id'], PoolUuid2Vseid)
        uri = '/api/3.0/edges/{}/loadbalancer/config/pools/{}'.format(self.vse.get_edgeId(), vseid)
        self.init()
        response = self.vse.api('DELETE', uri)
        return response

    def __update_pool(self, context, pool):
        vseid = uuid2vseid(context,pool['id'], PoolUuid2Vseid)
        if vseid is None:
            return self.create_pool(context, pool)
        return self.update_pool(context, pool)

    def __delete_pool(self, context, pool):
        return self.delete_pool(context, pool)

    def __update_member_pool(self, context, member):
        pool = getobj(context, Pool, member['pool_id'])
        if self.__pool_ready(pool):
            return self.__update_pool(context, pool)
        else:
            return self.__delete_pool(context, pool)

    def create_member(self, context, member):
        return self.__update_member_pool(context, member)

    def update_member(self, context, member):
        return self.__update_member_pool(context, member)

    def delete_member(self, context, member):
        return self.__update_member_pool(context, member)

    def create_vip(self, context, vip):
        uri = '/api/3.0/edges/{}/loadbalancer/config/virtualservers'.format(self.vse.get_edgeId())
        request = self.lbaas2vsmVS(context, vip)
        response = self.vse.api('POST', uri, request)
        uuid2vseid = VipUuid2Vseid(uuid=vip['id'], vseid=response['id'])
        context.session.add(uuid2vseid)
        return response

    def update_vip(self, context, vip):
        vseid = uuid2vseid(context, vip['id'], VipUuid2Vseid)
        if vseid is None:
            raise Exception("virtualserver id for {} not found".format(vip['id']))
        request = self.lbaas2vsmVS(context, vip)
        uri = '/api/3.0/edges/{}/loadbalancer/config/virtualservers/{}'.format(self.vse.get_edgeId(), vseid)
        request = self.quantum2VSM(vs, self.VirtualServerAttrs)
        response = self.vse.api('PUT', uri, request)
        return response

    def delete_vip(self, context, vip):
        #vseid = uuid2vseid(context, vip['id'], VipUuid2Vseid)
        vseid = vip['vseid']
        if vseid is None:
            raise Exception("virtualserver id for {} not found".format(vip['id']))
        uri = '/api/3.0/edges/{}/loadbalancer/config/virtualservers/{}'.format(self.vse.get_edgeId(), vseid)
        response = self.vse.api('DELETE', uri)
        return response

    def get_vsm_lb_config(self):
        uri = '/api/3.0/edges/{}/loadbalancer/config'.format(self.vse.get_edgeId())
        return self.vse.api('GET', uri)

