#!/usr/bin/python

import json
import sys
import os

import lib

vpnService = lib.qService + '/vpn'
tenantId = "202e69af6fc14e449744140034f977e5"
EdgeUrl = "10.117.35.99"

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
os.system("./restjson4.sh GET 10.117.35.99 /edge-1/ipsec/statistics")
print '\n\nEDGE CONFIG:'
os.system("./restjson4.sh GET 10.117.35.99 /edge-1/ipsec/config")
site = createSite(
				  tenant_id = tenantId,
                  subnet_id = "0c798ed8-33ba-11e2-8b28-000c291c4d14",
                  name = 'site1',
                  description = '',
                  local_endpoint = "10.117.35.202",
                  peer_endpoint = "10.117.35.203",
                  local_id = "10.117.35.202",
                  peer_id = "10.117.35.203",
                  psk = 'hello123',
                  mtu = 1500,
                  pri_networks = [
                        {
                           'local_subnets': "192.168.1.0/24,192.168.2.0/24",
                           'peer_subnets': "192.168.11.0/24,192.168.22.0/24"
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
os.system("./restjson4.sh " + "GET " + EdgeUrl + " " + "/edge-1/ipsec/statistics")
print '\n\nCREATE EDGE CONFIG:'
os.system("./restjson4.sh " + "GET " + EdgeUrl + " " + "/edge-1/ipsec/config")


##test update_site
update_site = {
    "site" : {
           "name": "new_site",
           "description": "this is the updated site",
           "local_endpoint": "10.117.35.202",
           "peer_endpoint": "10.117.35.204",
           "local_id": "10.117.35.202",
           "peer_id": "10.117.35.204",
           "psk": "new hello123",
           "mtu": 1800,
           "pri_networks" : [
                 {
                    'local_subnets': "192.168.2.0/24,192.168.4.0/24",
                    'peer_subnets': "192.168.13.0/24,192.168.23.0/24"
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
os.system("./restjson4.sh " + "GET " + EdgeUrl + " " + "/edge-1/ipsec/statistics")
print '\n\nUPDATE EDGE CONFIG:'
os.system("./restjson4.sh " + "GET " + EdgeUrl + " " + "/edge-1/ipsec/config")


#test delete_site
deleteSite(sites[0]['id'])
sites = getSites()
if len(sites) >= 1:
	print 'failed to delete the site'
	print json.dumps(sites,indent=4)
print '\n\nDELETE EDGE STATS:'
os.system("./restjson4.sh " + "GET " + EdgeUrl + " " + "/edge-1/ipsec/statistics")
print '\n\nDELETE EDGE CONFIG:'
os.system("./restjson4.sh " + "GET " + EdgeUrl + " " + "/edge-1/ipsec/config")


