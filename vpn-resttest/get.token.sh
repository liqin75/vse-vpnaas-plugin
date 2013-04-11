#!/bin/bash
. openrc
OS_AUTH_URL=http://10.117.5.160:5000/v2.0
curl -X POST -H "Content-Type: application/json" -d "{\"auth\":{\"passwordCredentials\":{\"username\":\"$OS_USERNAME\",\"password\":\"$OS_PASSWORD\"},\"tenantName\":\"$OS_TENANT_NAME\"}}" "$OS_AUTH_URL"/tokens | python -m json.tool
