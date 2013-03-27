#!/usr/bin/python

import httplib2
import json


class Config():
    def __init__(self, server, project, user, password):
        self.server = server
        self.idServiceUri = 'http://{0}:5000/v2.0'.format(server)
        self.computeServiceUri = 'http://{0}:8774/v2'.format(server)
        self.qService = 'http://{0}:9696/v2.0'.format(server)
        self.project = project
        self.user = user
        self.password = password


class OpenstackException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class AuthenticationException(OpenstackException):
    pass


class OpenstackAPI(object):
    def __init__(self, address, project, admin, password):
        self.config = Config(address, project, admin, password)
        self.authToken = None
        self.tenantId = None

    def _getAuthHeader(self):
        if self.authToken is None:
            self.authToken = self._getToken()
        return {'X-Auth-Token': self.authToken}

    def _getHeaders(self):
        if self.authToken is None:
            self.authToken = self._getToken()
        return {
            'X-Auth-Token': self.authToken,
            'Content-Type': 'application/json'
        }

    def _getTenantId(self):
        if self.tenantId is None:
            tenantsUri = '{0}/tenants'.format(self.config.idServiceUri)
            http = httplib2.Http()
            resp, content = http.request(tenantsUri, 'GET',
                                         headers=self._getHeaders())
            if int(resp['status']) != 200:
                raise OpenstackException("Openstack Failed: {0}".format(
                    resp['status']))

            content = json.loads(content)
            for tenant in content['tenants']:
                if tenant['name'] == self.config.project:
                    self.tenantId = tenant['id']
                    break
        return self.tenantId

    def _getToken(self):
        tokenUri = '{0}/tokens?name={1}'.format(
            self.config.idServiceUri, self.config.project)
        request = {
            'auth': {
                'passwordCredentials': {
                    'username': self.config.user,
                    'password': self.config.password
                },
                'tenantName': self.config.project
            }
        }
        http = httplib2.Http()
        resp, content = http.request(
            tokenUri, 'POST', json.dumps(request),
            headers={'Content-Type': 'application/json'})
        if int(resp['status']) != 200:
            raise AuthenticationException("Authentication Failed: {0}".format(
                resp['status']))

        print content
        content = json.loads(content)
        return content['access']['token']['id']

    def _getInstanceId(self, instanceName):
        instanceUri = '{0}/{1}/servers?name={2}'.format(
            self.config.computeServiceUri, self._getTenantId(), instanceName)
        resp, content = self._doRequest(instanceUri, 'GET')
        if int(resp['status']) != 200:
            raise OpenstackException(json.dumps(resp) + '\n' + content)

        result = json.loads(content)
        if len(result['servers']) == 0:
            return None

        if len(result['servers']) > 1:
            print content
            raise OpenstackException("Multiple instances named {0}".format(
                instanceName))

        return result['servers'][0]['id']

    def inject_file(self, instanceName, filename, injectId, content):
        injectUri = '{0}/{1}/servers/{2}/action'.format(
            self.config.computeServiceUri,
            self._getTenantId(),
            self._getInstanceId(instanceName))
        request = {
            'os-inject': {
                'id': injectId,
                'path': filename,
                'contents': content
            }
        }
        print injectUri
        print json.dumps(request)
        resp, content = self._doRequest(injectUri, 'POST', request)
        status = int(resp['status'])
        if status / 100 != 2:
            raise OpenstackException(json.dumps(resp) + '\n' + content)

    def createLoadBalancer(self):
        lbService = os.config.qService + '/extensions/lbs'
        lbService = os.config.qService + '/lbs'
        print lbService
        request = {
            'lb': {
                'name': 'vse-kvm-instance',
                'user': 'admin',
                'password': 'default',
                'address': 'fank-dev4.eng.vmware.com'
            }
        }
        resp, content = self._doRequest(lbService, 'POST', request)
        print resp
        print ''
        print content

    def _doRequest(self, uri, method, request=None, headers=None):
        http = httplib2.Http()
        if request is not None:
            body = json.dumps(request)
        else:
            body = None

        if headers is None:
            headers = self._getHeaders()
        else:
            headers = dict(self._getHeaders().items() + headers.items())

        return http.request(uri, method, body=body, headers=headers)

    def getUri(self, uri):
        http = httplib2.Http()
        resp, content = http.request(uri, 'GET', headers=self._getHeaders())
        print resp
        print ''
        print content
