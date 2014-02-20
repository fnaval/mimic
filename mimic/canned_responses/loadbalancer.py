"""
Canned response for add/list/delete load balancers and add/delete/list nodes
"""
from random import randrange
from copy import deepcopy
from mimic.util.helper import (not_found_response, current_time_in_utc,
                               invalid_resource, set_resource_status)
from twisted.python import log
lb_cache = {}
meta_cache = {}


def load_balancer_example(lb_info, lb_id, status):
    """
    Create load balancer response example
    """
    lb_example = {"name": lb_info["name"],
                  "id": lb_id,
                  "protocol": lb_info["protocol"],
                  "port": lb_info.get("port", 80),
                  "algorithm": lb_info.get("algorithm") or "RANDOM",
                  "status": status,
                  "cluster": {"name": "test-cluster"},
                  "timeout": lb_info.get("tiemout", 30),
                  "created": {"time": current_time_in_utc()},
                  "virtualIps": [{"address": "127.0.0.1",
                                 "id": 1111,
                                 "type": "PUBLIC",
                                 "ipVersion": "IPV4"},
                                 {"address": "0000:0000:0000:0000:1111:111b:0000:0000",
                                  "id": 1111,
                                  "type": "PUBLIC",
                                  "ipVersion": "IPV6"}],
                  "sourceAddresses": {"ipv6Public": "0000:0001:0002::00/00",
                                      "ipv4Servicenet": "127.0.0.1",
                                      "ipv4Public": "127.0.0.1"},
                  "httpsRedirect": lb_info.get("httpsRedirect", False),
                  "updated": {"time": current_time_in_utc()},
                  "halfClosed": lb_info.get("halfClosed", False),
                  "connectionLogging": lb_info.get("connectionLogging", {"enabled": False}),
                  "contentCaching": {"enabled": False}}
    if lb_info.get("nodes"):
        lb_example.update({"nodes": _add_nodes_to_lb(lb_info["nodes"])})
    if lb_info.get("metadata"):
        lb_example.update({"metadata": _add_meta(lb_info["metadata"])})
    return lb_example


def add_load_balancer(tenant_id, lb_info, lb_id):
    """
    Returns response of a newly created load balancer with
    response code 202, and adds the new lb to the lb_cache.
    Note: lb_cache has tenant_id added as an extra key in comparison
    to the lb_example.
    """
    status = "ACTIVE"

    # create a metadata cache so we dont have to deal with the list
    meta = {}
    for each in lb_info["metadata"]:
        meta.update({each["key"]: each["value"]})
    meta_cache[lb_id] = meta
    log.msg(meta_cache)

    if "lb_building" in meta_cache[lb_id]:
        status = "BUILD"

    # Add tenant_id to lb_cache to be able to associate lbs with tenant
    # and remove before returning response for add lb
    lb_cache[lb_id] = load_balancer_example(lb_info, lb_id, status)
    lb_cache[lb_id].update({"tenant_id": tenant_id})
    new_lb = _lb_cache_without_tenant(lb_id)

    return {'loadBalancer': new_lb}, 202


def get_load_balancers(lb_id):
    """
    Returns the load balancers with the given lb id, with response
    code 200. If no load balancers are found returns 404.
    """
    if lb_id in lb_cache:
        _verify_and_update_lb_state(lb_id, False)
        log.msg(lb_cache[lb_id]["status"])
        new_lb = _lb_cache_without_tenant(lb_id)
        return {'loadBalancer': new_lb}, 200
    else:
        return not_found_response("loadbalancer"), 404


def del_load_balancer(lb_id):
    """
    Returns response for a load balancer that is in building status for 20 seconds
    and response code 202, and adds the new lb to the lb_cache
    """
    if lb_id in lb_cache:

        if any([lb_cache[lb_id]["status"] == "ACTIVE", lb_cache[lb_id]["status"] == "ERROR"]):
            del lb_cache[lb_id]

            return None, 202

        if lb_cache[lb_id]["status"] == "DELETED":
            _verify_and_update_lb_state(lb_id)
            msg = "Must provide valid load balancers: {0} could not be found.".format(lb_id)
        msg = ("Must provide valid load balancers: {0} are immutable and "
               "could not be processed.".format(lb_id))
        return invalid_resource(msg, 400), 400

    else:
        return not_found_response("loadbalancer"), 404


def list_load_balancers(tenant_id):
    """
    Returns the list of load balancers with the given tenant id with response
    code 200. If no load balancers are found returns empty list.
    """
    response = {k: v for (k, v) in lb_cache.items() if tenant_id == v['tenant_id']}
    for each in response:
        _verify_and_update_lb_state(each, False)
        log.msg(lb_cache[each]["status"])
    updated_resp = {k: v for (k, v) in lb_cache.items() if tenant_id == v['tenant_id']}
    return {'loadBalancers': updated_resp.values() or []}, 200


def add_node(node_list, lb_id):
    """
    Returns the canned response for add nodes
    """
    if lb_id in lb_cache:

        if lb_cache[lb_id]["status"] != "ACTIVE":
            return invalid_resource("Load Balancer '{0}' has a status of {1} and is considered "
                                    "immutable.".format(lb_id, lb_cache[lb_id]["status"]), 422), 422

        nodes = _add_nodes_to_lb(node_list)
        if lb_cache[lb_id].get("nodes"):
            for existing_node in lb_cache[lb_id]["nodes"]:
                for new_node in node_list:
                    if (existing_node["address"] == new_node["address"] and
                       existing_node["port"] == new_node["port"]):
                        return invalid_resource("Duplicate nodes detected. One or more nodes "
                                                "already configured on load balancer.", 413), 413
            lb_cache[lb_id]["nodes"] = lb_cache[lb_id]["nodes"] + nodes
        else:
            lb_cache[lb_id]["nodes"] = nodes
            _verify_and_update_lb_state(lb_id)
        return {"nodes": nodes}, 200
    else:
        return not_found_response("loadbalancer"), 404


def get_nodes(lb_id, node_id):
    """
    Returns the node on the load balancer
    """

    if lb_id in lb_cache:
        _verify_and_update_lb_state(lb_id, False)

        if lb_cache[lb_id] == "DELETED":
            return invalid_resource("The loadbalancer is marked as deleted.", 410), 410
        node_list = []
        if lb_cache[lb_id].get("nodes"):
            node_list = lb_cache[lb_id]["nodes"]
        return {"nodes": node_list}, 200
    else:
        return not_found_response("loadbalancer"), 404


def delete_node(lb_id, node_id):
    """
    Determines whether the node to be deleted exists in mimic cache and
    returns the response code.
    Note : Currently even if node does not exist, return 202 on delete.
    """
    if lb_id in lb_cache:

        if lb_cache[lb_id]["status"] != "ACTIVE":
            return invalid_resource("Load Balancer '{0}' has a status of {1} and is considered "
                                    "immutable.".format(lb_id, lb_cache[lb_id]["status"]), 422), 422

        lb_cache[lb_id]["nodes"] = [x for x in lb_cache[lb_id]["nodes"]
                                    if not (node_id == x.get("id"))]
        if not lb_cache[lb_id]["nodes"]:
            del lb_cache[lb_id]["nodes"]

        _verify_and_update_lb_state(lb_id)
        return None, 202
    else:
        return not_found_response("loadbalancer"), 404


def list_nodes(lb_id):
    """
    Returns the list of nodes remaining on the load balancer
    """

    if lb_id in lb_cache:
        _verify_and_update_lb_state(lb_id, False)

        if lb_cache[lb_id] == "DELETED":
            return invalid_resource("The loadbalancer is marked as deleted.", 410), 410
        node_list = []
        if lb_cache[lb_id].get("nodes"):
            node_list = lb_cache[lb_id]["nodes"]
        return {"nodes": node_list}, 200
    else:
        return not_found_response("loadbalancer"), 404


def _add_nodes_to_lb(node_list):
    """
    create a dict of nodes given the list of nodes
    """
    nodes = []
    for each in node_list:
        node = {}
        node["address"] = each["address"]
        node["condition"] = each["condition"]
        node["port"] = each["port"]
        if each.get("weight"):
            node["weight"] = each["weight"]
        if each.get("type"):
            node["type"] = each["type"]
        node["id"] = randrange(999999)
        node["status"] = "ONLINE"
        nodes.append(node)
    return nodes


def _add_meta(node_list):
    """
    creates metadata with 'id' as a key
    """
    meta = []
    for each in node_list:
        each.update({"id": randrange(999)})
        meta.append(each)
    return meta


def _lb_cache_without_tenant(lb_id):
    """
    returns a copy of the cache for the given lb_id, without
    tenant_id
    """
    new_lb = deepcopy(lb_cache[lb_id])
    del new_lb["tenant_id"]
    return new_lb


def _verify_and_update_lb_state(lb_id, set_state=True):
    """
    Based on the current state, the metadata on the lb and the time since the LB has
    been in that state, set the appropriate state in lb_cache
    Note: Reconsider if update metadata is implemented
    """
    if lb_cache[lb_id]["status"] == "BUILD":
        meta_cache[lb_id]["lb_building"] = meta_cache[lb_id]["lb_building"] or 10
        lb_cache[lb_id]["status"] = set_resource_status(
            lb_cache[lb_id]["updated"],
            meta_cache[lb_id]["lb_building"]) or "BUILD"

    elif lb_cache[lb_id]["status"] == "ACTIVE" and set_state:
        if "lb_pending_update" in meta_cache[lb_id]:
            lb_cache[lb_id]["status"] = "PENDING-UPDATE"
            log.msg("here")
            log.msg(lb_cache[lb_id]["status"])
        if "lb_pending_delete" in meta_cache[lb_id]:
            lb_cache[lb_id]["status"] = "PENDING-DELETE"
        if "lb_error_state" in meta_cache[lb_id]:
            lb_cache[lb_id]["status"] = "ERROR"
        lb_cache[lb_id]["updated"] = current_time_in_utc()

    elif lb_cache[lb_id]["status"] == "PENDING-UPDATE":
        if "lb_pending_update" in meta_cache[lb_id]:
            lb_cache[lb_id]["status"] = set_resource_status(
                lb_cache[lb_id]["updated"],
                meta_cache[lb_id]["lb_pending_update"]) or "PENDING-UPDATE"

    elif lb_cache[lb_id]["status"] == "PENDING-DELETE":
        meta_cache[lb_id]["lb_pending_delete"] = meta_cache[lb_id]["lb_pending_delete"] or 10
        lb_cache[lb_id]["status"] = set_resource_status(
            lb_cache[lb_id]["updated"],
            meta_cache[lb_id]["lb_pending_delete"], "DELETED") or "PENDING-DELETE"
        lb_cache[lb_id]["updated"] = current_time_in_utc()

    elif lb_cache[lb_id]["status"] == "DELETED":
        lb_cache[lb_id]["status"] = set_resource_status(
            lb_cache[lb_id]["updated"], 3600, "DELETING-NOW") or "DELETED"
        if lb_cache[lb_id]["status"] == "DELETING-NOW":
            del lb_cache[lb_id]
