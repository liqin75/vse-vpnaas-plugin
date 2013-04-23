#!/usr/bin/python

import json
import sys
import os

import lib

vpnService = lib.qService + '/vpn'
tenantId="202e69af6fc14e449744140034f977e5"
edgeUri = "10.117.35.38"
edgeId = 'edge-1'
edgeUser = 'admin'
edgePasswd = 'default'


def createSite(tenant_id, subnet_id, name, description, local_endpoint,
			   local_id, peer_endpoint, peer_id, pri_networks, psk, mtu, location=None):
	request = {
            "site": {
                "tenant_id": tenant_id,
                "subnet_id": subnet_id,
                "name": name,
                "description": description,
                "local_endpoint": local_endpoint,
                "peer_endpoint": peer_endpoint,
                "local_id": local_id,
                "peer_id": peer_id,
                "pri_networks": pri_networks,
                "psk": psk,
                "mtu": mtu
            }
	}

	if location:
		request['site']['location'] = location
	return lib.doRequest(vpnService + '/sites', 'POST', request)['site']


def statsSite(id):
    return lib.doRequest(vpnService + '/sites/{0}/stats'.format(id), 'GET')


def updateSite(id, site):
    return lib.doRequest(vpnService + '/sites/{}'.format(id), 'PUT', site)['site']


def getSite(id):
    return lib.doRequest(vpnService + '/sites/{}'.format(id), 'GET')['site']


def getSites():
    return lib.doRequest(vpnService + '/sites', 'GET')['sites']


def deleteSite(id):
    return lib.doRequest(vpnService + '/sites/{}'.format(id), 'DELETE')

#######################################################################################################
## IPSec Policy


def createIPSecPolicy(tenant_id, name='ipsec_policy1',
         enc_alg='aes256', auth_alg='sha1',
         dh_group='2', life_time=3600,description=None):
    request = {
                'ipsec_policy': {
                              'tenant_id': tenant_id,
                              'name': name,
                              'enc_alg': enc_alg,
                              'auth_alg': auth_alg,
                              'dh_group': dh_group,
                              'description': description,
                              'life_time': life_time}
                }
    return lib.doRequest(vpnService + '/ipsec_policys', 'POST', request)['ipsec_policy']


def updateIPSecPolicy(id, ipsec_policy):
    return lib.doRequest(vpnService + '/ipsec_policys/{}'.format(id), 'PUT', ipsec_policy)['ipsec_policy']


def getIPSecPolicy(id):
    return lib.doRequest(vpnService + '/ipsec_policys/{}'.format(id), 'GET')['ipsec_policy']


def getIPSecPolicys():
    return lib.doRequest(vpnService + '/ipsec_policys', 'GET')['ipsec_policys']


def deleteIPSecPolicy(id):
    return lib.doRequest(vpnService + '/ipsec_policys/{}'.format(id), 'DELETE')


#######################################################################################################
## Isakmp Policy


def createIsakmpPolicy(tenant_id, name='isakmp_policy1',
         auth_mode='psk', enable_pfs=True,
         enc_alg='aes256', auth_alg='sha1',
         dh_group='2', life_time=28000,description=None):
    request = {
                'isakmp_policy': {
                              'tenant_id': tenant_id,
                              'name': name,
                              'auth_mode': auth_mode,
                              'enable_pfs': enable_pfs,
                              'enc_alg': enc_alg,
                              'auth_alg': auth_alg,
                              'dh_group': dh_group,
                              'description': description,
                              'life_time': life_time}
                }
    return lib.doRequest(vpnService + '/isakmp_policys', 'POST', request)['isakmp_policy']


def updateIsakmpPolicy(id, isakmp_policy):
    return lib.doRequest(vpnService + 
                        '/isakmp_policys/{}'.format(id), 'PUT', isakmp_policy)['isakmp_policy']


def getIsakmpPolicy(id):
    return lib.doRequest(vpnService + '/isakmp_policys/{}'.format(id), 'GET')['isakmp_policy']


def getIsakmpPolicys():
    return lib.doRequest(vpnService + '/isakmp_policys', 'GET')['isakmp_policys']


def deleteIsakmpPolicy(id):
    return lib.doRequest(vpnService + '/isakmp_policys/{}'.format(id), 'DELETE')

############################################################################################
# Start of the scripts

#test networks creation operation
lib.NetworkInit()

#clean the sites first (also test get_site and delete_site)
sites = getSites()
if len(sites) >= 1:
    for site in sites:
        deleteSite(site['id'])

#test create_site
print '\n\nEDGE STATS:'
os.system("./restjson4.sh " + "GET " + edgeUri + " " + "/" + 
            edgeId + "/ipsec/statistics")
print '\n\nEDGE CONFIG:'
os.system("./restjson4.sh " + "GET " + edgeUri + " " + "/" + 
            edgeId + "/ipsec/config")
site = createSite(
				  tenant_id = tenantId,
                  subnet_id = "0c798ed8-33ba-11e2-8b28-000c291c4d14",
                  name = 'site1',
                  description = '',
                  local_endpoint = "10.117.35.202",
                  peer_endpoint = "10.117.35.203",
                  local_id = "192.168.2.11",
                  peer_id = "10.117.35.203",
                  psk = '123',
                  mtu = 1500,
                  pri_networks = [
                        {
                           'local_subnets': "192.168.1.0/24",
                           'peer_subnets': "192.168.11.0/24"
                        }])

#test get_sites
sites = getSites()
if len(sites) < 1:
	print 'failed to create the site'
else:
    print '\n\nSITES:'
    print json.dumps(sites, indent=4)


#test get_site
site = getSite(sites[0]['id'])
print '\n\nSITE STATS:'
print json.dumps(statsSite(sites[0]['id']), indent=4)
print '\n\nCREATE EDGE STATS:'
os.system("./restjson4.sh " + "GET " + edgeUri + " " + "/" + 
            edgeId + "/ipsec/statistics")
print '\n\nCREATE EDGE CONFIG:'
os.system("./restjson4.sh " + "GET " + edgeUri + " " + "/" + 
            edgeId + "/ipsec/config")


##test update_site
update_site = {
    "site" : {
           "name": "new_site",
           "description": "this is the updated site",
           "local_endpoint": "10.117.35.202",
           "peer_endpoint": "10.117.35.204",
           "local_id": "192.168.2.11",
           "peer_id": "10.117.35.204",
           "psk": "new hello123",
           "mtu": 1800,
           "pri_networks" : [
                 {
                    'local_subnets': "192.168.2.0/24",
                    'peer_subnets': "192.168.13.0/24"
                 }],
          }
    }
site = updateSite(sites[0]['id'], update_site)
print '\n\nUPDATED SITES:'
sites = getSites()
print json.dumps(sites, indent=4)
print '\n\nUPDATE SITE STATS:'
print json.dumps(statsSite(sites[0]['id']), indent=4)
print '\n\nUPDATE EDGE STATS:'
os.system("./restjson4.sh " + "GET " + edgeUri + " " + "/" + 
            edgeId + "/ipsec/statistics")
print '\n\nUPDATE EDGE CONFIG:'
os.system("./restjson4.sh " + "GET " + edgeUri + " " + "/" + 
            edgeId + "/ipsec/config")


#test delete_site
deleteSite(sites[0]['id'])
sites = getSites()
if len(sites) >= 1:
	print 'failed to delete the site'
	print json.dumps(sites,indent=4)
print '\n\nDELETE EDGE STATS:'
os.system("./restjson4.sh " + "GET " + edgeUri + " " + "/" + 
            edgeId + "/ipsec/statistics")
print '\n\nDELETE EDGE CONFIG:'
os.system("./restjson4.sh " + "GET " + edgeUri + " " + "/" + 
            edgeId + "/ipsec/config")


#############################################################################
## Start IPSec Policy test

#clean the ipsec_policys first (also test get_ipsec_policy and delete_ipsec_policy)
ipsec_policys = getIPSecPolicys()
if len(ipsec_policys) >= 1:
    for ipsec_policy in ipsec_policys:
        deleteIPSecPolicy(ipsec_policy['id'])

#test create_ipsec_policy
ipsec_policy = createIPSecPolicy(
				  tenant_id = tenantId,
                  name = 'ipsec_policy1',
                  description = '',
                  enc_alg = 'aes256',
                  auth_alg = 'sha1', 
                  dh_group = '2',
                  life_time = 3600,
                        )
#test get_ipsec_policy
print '\n\nCREATE IPSec Policy STATS:'
print ipsec_policy
print json.dumps(ipsec_policy, indent=4)


#test update_ipsec_policy
update_ipsec_policy = {
    "ipsec_policy" : {
           "name": "new_ipsec_policy",
           "description": "this is the updated ipsec_policy",
           "dh_group":  '5',
          }
    }
new_ipsec_policy = updateIPSecPolicy(ipsec_policy['id'], update_ipsec_policy)
print '\n\nUPDATED IPSec Policy:'
print json.dumps(new_ipsec_policy, indent=4)


#test delete_ipsec_policy
deleteIPSecPolicy(new_ipsec_policy['id'])
ipsec_policys = getIPSecPolicys()
if len(ipsec_policys) >= 1:
	print 'failed to delete the ipsec_policy'
	print json.dumps(ipsec_policys,indent=4)

######################################################################################
## Start Isakmp Policy


#clean the isakmp_policys first (also test get_isakmp_policy and delete_isakmp_policy)
isakmp_policys = getIsakmpPolicys()
if len(isakmp_policys) >= 1:
    for isakmp_policy in isakmp_policys:
        deleteIPSecPolicy(isakmp_policy['id'])

#test create_isakmp_policy
isakmp_policy = createIsakmpPolicy(
				  tenant_id = tenantId,
                  name = 'isakmp_policy1',
                  description = '',
                  enc_alg = 'aes256',
                  auth_alg = 'sha1', 
                  dh_group = '2',
                  life_time = 3600,
                        )
#test get_isakmp_policy
print '\n\nCREATE Isakmp Policy STATS:'
print isakmp_policy
print json.dumps(isakmp_policy, indent=4)


#test update_isakmp_policy
update_isakmp_policy = {
    "isakmp_policy" : {
           "name": "new_isakmp_policy",
           "description": "this is the updated isakmp_policy",
           "dh_group":  '5',
          }
    }
new_isakmp_policy = updateIsakmpPolicy(isakmp_policy['id'], update_isakmp_policy)
print '\n\nUPDATED Isakmp Policy:'
print json.dumps(new_isakmp_policy, indent=4)


#test delete_isakmp_policy
deleteIsakmpPolicy(new_isakmp_policy['id'])
isakmp_policys = getIsakmpPolicys()
if len(isakmp_policys) >= 1:
	print 'failed to delete the isakmp_policy'
	print json.dumps(isakmp_policys,indent=4)
