#!/bin/bash
#HOW TO USE:

#

# ~# ./resttest.sh PUT 10.117.4.140 /edge-4/loadbalancer/config lbConfigAll.json
#### ./restjson4.sh GET 10.117.35.99 /edge-1/ipsec/config
###  ./restjson4.sh GET 10.117.35.99 /edge-1/ipsec/statistics
if [ $# == 3 ]; then

    echo "curl -i -k -H \"content-type: application/json\" -H \"Accept: application/json\" -H \"Authorization: Basic YWRtaW46ZGVmYXVsdA==\" -X $1 https://$2/api/4.0/edges$3"

    curl -i -k -H "content-type: application/json" -H "Accept: application/json" -H "Authorization: Basic YWRtaW46ZGVmYXVsdA==" -X $1 https://$2/api/4.0/edges$3 

    echo ""

    exit 0

fi

 

if [ $# == 4 ]; then

    echo "curl -i -k -H \"content-type: application/json\" -H \"Accept: application/json\" -H \"Authorization: Basic YWRtaW46ZGVmYXVsdA==\" -X $1 https://$2/api/4.0/edges$3 -d \"\`cat $4\`\""

    curl -i -k -H "content-type: application/json" -H "Accept: application/json" -H "Authorization: Basic YWRtaW46ZGVmYXVsdA==" -X $1 https://$2/api/4.0/edges$3 -d "`cat $4`" 

fi

echo ""

