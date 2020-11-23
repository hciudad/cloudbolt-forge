import json
import logging
import re

from api.api_samples.python_client.api_client import CloudBoltAPIClient
from api.api_samples.python_client.samples.api_helpers import wait_for_order_completion
from common.methods import set_progress
from servicecatalog.models import ServiceBlueprint
from utilities.exceptions import CloudBoltException
from utilities.models import ConnectionInfo


# suppress logging from requests module
logger = logging.getLogger('requests')
logger.setLevel(40)
logger = logging.getLogger('py.warnings')
logger.setLevel(40)

API_CLIENT_CI = "CIT API Client"

# BP specific variables - You should change these
BLUEPRINT = 96

BP_PAYLOAD = """
{
    "group": "/api/v2/groups/2/",
    "items": {
        "deploy-items": [
            {
                "blueprint": "/api/v2/blueprints/96/",
                "blueprint-items-arguments": {
                    "build-item-Google Cloud Firewall Build": {
                        "parameters": {
                            "allowed-ports-a432": "80, 443",
                            "allowed-protocol-a432": "icmp",
                            "direction-a432": "EGRESS",
                            "env-id-a432": "57",
                            "firewall-name-a432": "citfirewallrulegcp",
                            "priority-a432": "5177"
                        }
                    }
                },
                "resource-name": "Google Cloud Firewall",
                "resource-parameters": {}
            }
        ]
    },
    "submit-now": "true"
}
"""

NEW_RESOURCE_NAME = "citfirewallrulegcp"
# END of BP specific variables

def get_order_id_from_href(order_href):
    mo = re.search("/orders/([0-9]+)", order_href)
    return int(mo.groups()[0])

def test_order_blueprint(client):
    order = json.loads(client.post('/api/v2/orders/', body=BP_PAYLOAD))
    order_href = order['_links']['self']['href']
    order_id = get_order_id_from_href(order_href)
    result = wait_for_order_completion(client, order_id, 600, 10)
    if result != 0:
        raise CloudBoltException("Blueprint Deployment order {} did not succeed.".format(order_id))
    set_progress("Blueprint deployment order {} completed successfully.".format(order_id))

def test_delete_resource(client, resource):
    body = "{}"
    json.loads(client.post(
        '/api/v2/resources/{}/{}/actions/1/'.format(resource.resource_type.name, resource.id), body=body))

def get_api_client():
    ci = ConnectionInfo.objects.get(name=API_CLIENT_CI)
    return CloudBoltAPIClient(
        ci.username, ci.password, ci.ip, ci.port, protocol=ci.protocol)

def run(job, *args, **kwargs):
    bp = ServiceBlueprint.objects.get(id=BLUEPRINT)
    set_progress(
        "Running Continuous Infrastructure Test for blueprint {}".format(bp)
    )
    
    client = get_api_client()
    
    # Order the BP
    set_progress("### ORDERING BLUEPRINT ###", tasks_done=0, total_tasks=3)
    test_order_blueprint(client)
    
    resource = bp.resource_set.filter(name__iexact=NEW_RESOURCE_NAME, lifecycle='ACTIVE').first()

    set_progress(f"RESOURCE {resource}")
    rce = bp.resource_set.last()
    set_progress(f"LAST RESOURCE {rce}")
    # Delete the resource from the database only
    resource.delete()

    set_progress("### DISCOVERING RESOURCES FOR BLUEPRINT ###", tasks_done=1)
    bp.sync_resources()
    
    # should be able to get the resource since the sync should have created it
    resource = bp.resource_set.get(name__iexact=NEW_RESOURCE_NAME, lifecycle='ACTIVE')
    
    set_progress("### DELETING RESOURCE FOR BLUEPRINT ###", tasks_done=2)
    test_delete_resource(client, resource)
    
    set_progress("ALL Tests completed!", tasks_done=3)