#
# Copyright 2024 Canonical, Ltd.
#

import functools
import json
import logging
import sys

import pytest
from k8s_test_harness import harness
from k8s_test_harness.util import constants, env_util, k8s_util, platform_util

LOG: logging.Logger = logging.getLogger(__name__)

LOG.addHandler(logging.FileHandler(f"{__name__}.log"))
LOG.addHandler(logging.StreamHandler(sys.stdout))


NGINX_CONTROLLER_VERSIONS = ["v1.10.1", "v1.11.0"]
# NOTE(aznashwan): the `kube-webhook-certgen` image is versioned
# separately from the main `nginx-controller` image.
NGINX_KUBE_WEBHOOK_CERTGEN_VERSION_MAP = {
    # https://github.com/kubernetes/ingress-nginx/pull/11212
    # https://github.com/kubernetes/ingress-nginx/releases/tag/controller-v1.11.0
    "v1.11.0": "v1.4.1",
    # https://github.com/kubernetes/ingress-nginx/pull/11033
    # https://github.com/kubernetes/ingress-nginx/releases/tag/controller-v1.10.0
    "v1.10.1": "v1.4.0",
}

# HACK(aznashwan): revert to upstream chart once this PR is included in a release:
# https://github.com/kubernetes/ingress-nginx/pull/11710
# CHART_RELEASE_URL = "https://github.com/kubernetes/ingress-nginx/releases/download/helm-chart-4.11.1/ingress-nginx-4.11.1.tgz"
CHART_RELEASE_URL = "https://github.com/aznashwan/ingress-nginx/releases/download/helm-chart-4.11.1/ingress-nginx-4.11.1.tgz"
INSTALL_NAME = "ingress-nginx"

# This mapping indicates which fields of the upstream Nginx-ingress Helm chart
# contain the 'image' fields which should be overriden with the ROCK
# image URLs and version during testing.
# https://github.com/kubernetes/ingress-nginx/blob/main/charts/ingress-nginx/values.yaml
IMAGE_NAMES_TO_CHART_VALUES_OVERRIDES_MAP = {
    "controller": "controller",
    # https://github.com/kubernetes/ingress-nginx/blob/main/charts/ingress-nginx/values.yaml#L807
    "kube-webhook-certgen": "controller.admissionWebhooks.patch",
}


def describe_resources_on_error(resource_type: str):
    def _decorator(fun):
        @functools.wraps(fun)
        def _inner(function_instance: harness.Instance, *args, **kwargs):
            try:
                return fun(function_instance, *args, **kwargs)
            except Exception:
                proc = function_instance.exec(
                    ["k8s", "kubectl", "describe", resource_type], capture_output=True
                )
                LOG.info(
                    f"### All current '{resource_type}' definitions: "
                    f"{proc.stdout.decode()}"
                )
                raise

        return _inner

    return _decorator


@describe_resources_on_error("pods")
@pytest.mark.parametrize("controller_version", NGINX_CONTROLLER_VERSIONS)
def test_nginx_ingress_chart_deployment(
    function_instance: harness.Instance, controller_version: str
):

    architecture = platform_util.get_current_rockcraft_platform_architecture()

    # Compose the Helm command line args for overriding the
    # image fields for each component:
    all_chart_value_overrides_args = []

    controller_rock_info = env_util.get_build_meta_info_for_rock_version(
        "controller",
        controller_version,
        architecture,
    )
    controller_chart_section = IMAGE_NAMES_TO_CHART_VALUES_OVERRIDES_MAP["controller"]
    controller_image, controller_tag = controller_rock_info.image.split(":")
    controller_registry, controller_image_name = controller_image.split("/", maxsplit=1)
    all_chart_value_overrides_args.extend(
        [
            "--set",
            f"{controller_chart_section}.image.registry={controller_registry}",
            "--set",
            f"{controller_chart_section}.image.image={controller_image_name}",
            "--set",
            f"{controller_chart_section}.image.tag={controller_tag}",
            "--set",
            f"{controller_chart_section}.image.digest=",
        ]
    )

    # NOTE(aznashwan): we pass the whole securityContext definition
    # as JSON as the Chart's values doesn't expose the `capabilites`
    # field of the controller containers directly:
    # https://github.com/kubernetes/ingress-nginx/blob/controller-v1.11.0/charts/ingress-nginx/templates/_helpers.tpl#L44-L54
    controller_security_context = {
        # HACK(aznashwan): rockcraft does not currently preserve extended file
        # attributes and Nginx cannot be run on low ports (< 1024) without
        # cap_net_bind_service available, so we run the test as root:
        # https://github.com/canonical/rockcraft/issues/683
        # NOTE(aznashwan): Ubuntu has defaults for the IDs of the www-data
        # user/group different from the ones set in the upstream repo:
        # https://github.com/kubernetes/ingress-nginx/blob/helm-chart-4.11.1/charts/ingress-nginx/values.yaml#L34-L35
        # "runAsUser": 33,
        # "runAsGroup": 33,
        "runAsUser": 0,
        "runAsGroup": 0,
        "runAsNonRoot": False,
        "allowPrivilegeEscalation": False,
        "capabilities": None,
        # NOTE(aznashwan): Pebble requires access to /var:
        "readOnlyRootFilesystem": False,
    }

    sec_ctxt_json = json.dumps(controller_security_context)
    all_chart_value_overrides_args.extend(
        [
            "--set-json",
            f"{controller_chart_section}.containerSecurityContext={sec_ctxt_json}"
        ]
    )

    certgen_rock_info = env_util.get_build_meta_info_for_rock_version(
        "kube-webhook-certgen",
        NGINX_KUBE_WEBHOOK_CERTGEN_VERSION_MAP[controller_version],
        architecture,
    )
    certgen_chart_section = IMAGE_NAMES_TO_CHART_VALUES_OVERRIDES_MAP[
        "kube-webhook-certgen"
    ]
    certgen_image, certgen_tag = certgen_rock_info.image.split(":")
    certgen_registry, certgen_image_name = certgen_image.split("/", maxsplit=1)
    all_chart_value_overrides_args.extend(
        [
            "--set",
            f"{certgen_chart_section}.image.registry={certgen_registry}",
            "--set",
            f"{certgen_chart_section}.image.image={certgen_image_name}",
            "--set",
            f"{certgen_chart_section}.image.tag={certgen_tag}",
            "--set",
            f"{certgen_chart_section}.image.digest=",
        ]
    )
    # NOTE(aznashwan): admission web hook containers are set to RO:
    all_chart_value_overrides_args.extend(
        [
            "--set",
            "controller.admissionWebhooks.createSecretJob.securityContext.readOnlyRootFilesystem=false",
            "--set",
            "controller.admissionWebhooks.patchWebhookJob.securityContext.readOnlyRootFilesystem=false",
        ]
    )

    # NOTE(aznashwan): GitHub actions UI sometimes truncates env values:
    all_rocks_meta_info = env_util.get_rocks_meta_info_from_env()
    LOG.info(
        f"All built rocks metadata from env was: "
        f"{json.dumps([rmi.__dict__ for rmi in all_rocks_meta_info])}"
    )

    helm_command = [
        "sudo",
        "k8s",
        "helm",
        "install",
        INSTALL_NAME,
        CHART_RELEASE_URL,
    ]
    helm_command.extend(all_chart_value_overrides_args)

    function_instance.exec(helm_command)

    deployment_name = "ingress-nginx-controller"
    retry_kwargs = {"retry_times": 30, "retry_delay_s": 10}
    k8s_util.wait_for_deployment(
        function_instance,
        deployment_name,
        condition=constants.K8S_CONDITION_AVAILABLE,
        **retry_kwargs,
    )
