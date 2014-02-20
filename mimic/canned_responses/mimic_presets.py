"""
Defines the preset values in the mimic api.
"""


get_presets = {"loadbalancers": {"lb_building": "Keeps the load balancer in building state"
                                                "for given seconds. Used only on create load balancer",
                                 "lb_error_state": "Puts the LB in error state, and such an LB can only"
                                                   "be deleted",
                                 "lb_pending_update": "Changes the load balancer to PENDING-UPDATE"
                                                      "state for the given number, any action"
                                                      "other than delete is performed on the server",
                                 "lb_pending_delete": "Changes the load balancer to PENDING-DELETE"
                                                      "state for the given seconds, when deleted",
                                 "failing_lb_id": "175647",
                                 "invalid_lb": "3909",
                                 "return_422_on_add_node_count": 3},
               "servers": {"create_server_failure": "{\"message\": \"given message\","
                                                    "\"code\": given code}",
                           "delete_server_failure": "{\"code\": given code,"
                                                    "\"times\": returns given code that many times}",
                           "invalid_image_ref": ["INVALID-IMAGE-ID", "1111", "image_ends_with_Z"],
                           "invalid_flavor_ref": ["INVALID-FLAVOR-ID", "8888", "-4", "1"],
                           "server_error": "sets server state to error on create",
                           "server_building": "sets the server to be in building state for given time"}
               }
