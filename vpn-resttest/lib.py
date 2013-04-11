
import httplib2
import json
import os

qService = "http://10.117.5.160:9696/v2.0"

externalNet = None
insideNet = None
externalSubnet = None
insideSubnet = None

token ="MIILogYJKoZIhvcNAQcCoIILkzCCC48CAQExCTAHBgUrDgMCGjCCCnsGCSqGSIb3DQEHAaCCCmwEggpoeyJhY2Nlc3MiOiB7InRva2VuIjogeyJpc3N1ZWRfYXQiOiAiMjAxMy0wNC0xMFQwNzoxODo1Ny42OTQ0NjYiLCAiZXhwaXJlcyI6ICIyMDEzLTA0LTExVDA3OjE4OjU3WiIsICJpZCI6ICJwbGFjZWhvbGRlciIsICJ0ZW5hbnQiOiB7ImRlc2NyaXB0aW9uIjogbnVsbCwgImVuYWJsZWQiOiB0cnVlLCAiaWQiOiAiZDJiMmIxN2NhYWVkNDdjODg4ZTU0NGQ4N2I5MjFhMjAiLCAibmFtZSI6ICJkZW1vIn19LCAic2VydmljZUNhdGFsb2ciOiBbeyJlbmRwb2ludHMiOiBbeyJhZG1pblVSTCI6ICJodHRwOi8vMTAuMTE3LjQuMTcwOjg3NzQvdjIvZDJiMmIxN2NhYWVkNDdjODg4ZTU0NGQ4N2I5MjFhMjAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTAuMTE3LjQuMTcwOjg3NzQvdjIvZDJiMmIxN2NhYWVkNDdjODg4ZTU0NGQ4N2I5MjFhMjAiLCAiaWQiOiAiMTIwYjRlNGNmM2UyNDk2YWE1OGYzNjFjODVkZTdkMWIiLCAicHVibGljVVJMIjogImh0dHA6Ly8xMC4xMTcuNC4xNzA6ODc3NC92Mi9kMmIyYjE3Y2FhZWQ0N2M4ODhlNTQ0ZDg3YjkyMWEyMCJ9XSwgImVuZHBvaW50c19saW5rcyI6IFtdLCAidHlwZSI6ICJjb21wdXRlIiwgIm5hbWUiOiAibm92YSJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xMC4xMTcuNC4xNzA6OTY5Ni8iLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTAuMTE3LjQuMTcwOjk2OTYvIiwgImlkIjogIjRhZjI4YmQ1MjVmZDQ5YTQ5MjJmMDRlMjU1YWQxMjgyIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTAuMTE3LjQuMTcwOjk2OTYvIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogIm5ldHdvcmsiLCAibmFtZSI6ICJxdWFudHVtIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzEwLjExNy40LjE3MDozMzMzIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzEwLjExNy40LjE3MDozMzMzIiwgImlkIjogIjIxOGIzZmQ1OTUxMDRjMjZiYTJlMTgzZjNlZDE1YWNkIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTAuMTE3LjQuMTcwOjMzMzMifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiczMiLCAibmFtZSI6ICJzMyJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xMC4xMTcuNC4xNzA6OTI5MiIsICJyZWdpb24iOiAiUmVnaW9uT25lIiwgImludGVybmFsVVJMIjogImh0dHA6Ly8xMC4xMTcuNC4xNzA6OTI5MiIsICJpZCI6ICIxMWYxMjhiZGUxNjE0MmUwOWU4YmIyZWY0MjYxODE1MCIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzEwLjExNy40LjE3MDo5MjkyIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImltYWdlIiwgIm5hbWUiOiAiZ2xhbmNlIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzEwLjExNy40LjE3MDo4Nzc2L3YxL2QyYjJiMTdjYWFlZDQ3Yzg4OGU1NDRkODdiOTIxYTIwIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzEwLjExNy40LjE3MDo4Nzc2L3YxL2QyYjJiMTdjYWFlZDQ3Yzg4OGU1NDRkODdiOTIxYTIwIiwgImlkIjogIjAxNDhlMTkyYmIwNDQ3YmJhOTM5YjlmN2QyNjdiNDBjIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTAuMTE3LjQuMTcwOjg3NzYvdjEvZDJiMmIxN2NhYWVkNDdjODg4ZTU0NGQ4N2I5MjFhMjAifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAidm9sdW1lIiwgIm5hbWUiOiAiY2luZGVyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzEwLjExNy40LjE3MDo4NzczL3NlcnZpY2VzL0FkbWluIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzEwLjExNy40LjE3MDo4NzczL3NlcnZpY2VzL0Nsb3VkIiwgImlkIjogIjA2OTdkNDAwMDA5YzRiZmE4MTVmOGZkMTRmMTU1OGY0IiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTAuMTE3LjQuMTcwOjg3NzMvc2VydmljZXMvQ2xvdWQifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiZWMyIiwgIm5hbWUiOiAiZWMyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzEwLjExNy40LjE3MDozNTM1Ny92Mi4wIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzEwLjExNy40LjE3MDo1MDAwL3YyLjAiLCAiaWQiOiAiMDZhMTliYzVmOWM1NDUzYzk2NGU0ZTVmMDE1YWNhN2UiLCAicHVibGljVVJMIjogImh0dHA6Ly8xMC4xMTcuNC4xNzA6NTAwMC92Mi4wIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImlkZW50aXR5IiwgIm5hbWUiOiAia2V5c3RvbmUifV0sICJ1c2VyIjogeyJ1c2VybmFtZSI6ICJkZW1vIiwgInJvbGVzX2xpbmtzIjogW10sICJpZCI6ICI1ZmMwODhjM2YxYzk0NTgxODFmYmZkOThmNDcyYjczNyIsICJyb2xlcyI6IFt7Im5hbWUiOiAiYW5vdGhlcnJvbGUifSwgeyJuYW1lIjogIk1lbWJlciJ9XSwgIm5hbWUiOiAiZGVtbyJ9LCAibWV0YWRhdGEiOiB7ImlzX2FkbWluIjogMCwgInJvbGVzIjogWyI5ODFmMTcwN2ViY2M0ZDgxYTQ1NzJiNDg3YmQyNDU3MSIsICIzNWM3M2RlNmNmYzY0YTBkYWNhNzMwMmFiY2Y1M2VlMyJdfX19MYH-MIH8AgEBMFwwVzELMAkGA1UEBhMCVVMxDjAMBgNVBAgTBVVuc2V0MQ4wDAYDVQQHEwVVbnNldDEOMAwGA1UEChMFVW5zZXQxGDAWBgNVBAMTD3d3dy5leGFtcGxlLmNvbQIBATAHBgUrDgMCGjANBgkqhkiG9w0BAQEFAASBgDW1Mcux1f9tGoqcjtzenBDY4b7wcWvdHxAjvh0XWJJz0QBJjyNfeNlaIrItwu3VAhTYy370HkFftR7x23UwuzMJ1kUGREmLhQZvnk65QRUYvdF7BXZc6FTKa71-b5WGkDXvZG+LRjlNd7RWlEH9uK54TUJxYifk7YH+ADGH3ZJo"


headers = {
	"X-Auth-Token": token,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def doRequest(url, action, request=None):
    http = httplib2.Http()
    print "{} {}".format(action, url)
    if request is None:
        header, content = http.request(url, action, headers=headers)
    else:
        header, content = http.request(url, action, body=json.dumps(request), headers=headers)
    if header.status / 100 != 2:
        print header
        print content
        raise Exception(header)
    if content.strip() != "":
        return json.loads(content)
    return None

def NetworkInit():
    global externalNet
    global insideNet
    global externalSubnet
    global insideSubnet
    networks = getNetworks()
    for n in networks:
        if n['name'] == 'external':
            externalNet = n
            continue
        if n['name'] == 'inside':
            insideNet = n
            continue
    if not externalNet:
        externalNet = createNetwork('external')
    if not insideNet:
        insideNet = createNetwork('inside')

    subnets = getSubnets()
    for s in subnets:
        if s['name'] == 'external-subnet':
            externalSubnet = s
            continue
        if s['name'] == 'inside-subnet':
            insideSubnet = s
            continue
    if not externalSubnet:
        externalSubnet = createSubnet(externalNet, 'external-subnet', '100.0.0.0/24')
    if not insideSubnet:
        insideSubnet = createSubnet(insideNet, 'inside-subnet', '101.0.0.0/24')

def getNetworks():
    return doRequest(qService + '/networks', 'GET')['networks']

def createNetwork(name):
    request = {
        'network': {
            'name': name
        }
    }
    return doRequest(qService + '/networks', 'POST', request)['network']

def getSubnets():
    return doRequest(qService + '/subnets', 'GET')['subnets']

def createSubnet(network, name, cidr):
    request = {
        'subnet': {
            'name': name,
            'network_id': network['id'],
            'ip_version': 4,
            'cidr': cidr
        }
    }
    return doRequest(qService + '/subnets', 'POST', request)['subnet']

def getPorts():
    return doRequest(qService + '/ports', 'GET')['ports']

