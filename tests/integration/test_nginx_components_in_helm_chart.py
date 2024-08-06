#
# Copyright 2024 Canonical, Ltd.
#

import json
import logging
import sys

import pytest
from k8s_test_harness import harness
from k8s_test_harness.util import env_util, platform_util

LOG: logging.Logger = logging.getLogger(__name__)

LOG.addHandler(logging.FileHandler(f"{__name__}.log"))
LOG.addHandler(logging.StreamHandler(sys.stdout))


NGINX_CONTROLLER_VERSIONS = ["v1.11.0"]
# NOTE(aznashwan): the `kube-webhook-certgen` image is versioned
# separately from the main `nginx-controller` image.
NGINX_KUBE_WEBHOOK_CERTGEN_VERSION_MAP = {
    # https://github.com/kubernetes/ingress-nginx/pull/11212
    # https://github.com/kubernetes/ingress-nginx/releases/tag/controller-v1.11.0
    "v1.11.0": "v1.4.1"
}

CHART_RELEASE_URL = "https://github.com/kubernetes/ingress-nginx/releases/download/helm-chart-4.11.1/ingress-nginx-4.11.1.tgz"
INSTALL_NAME = "ingress-nginx"

# This mapping indicates which fields of the upstream Nginx-ingress Helm chart
# contain the 'image' fields which should be overriden with the ROCK
# image URLs and version during testing.
# https://github.com/kubernetes/ingress-nginx/blob/main/charts/ingress-nginx/values.yaml
IMAGE_NAMES_TO_CHART_VALUES_OVERRIDES_MAP = {
    # TODO(aznashwan): enable this when controller ROCK is ready:
    # "controller": "controller",
    # https://github.com/kubernetes/ingress-nginx/blob/main/charts/ingress-nginx/values.yaml#L807
    "kube-webhook-certgen": "controller.admissionWebhooks.patch",
}


@pytest.mark.parametrize("controller_version", NGINX_CONTROLLER_VERSIONS)
def test_nginx_ingress_chart_deployment(
    function_instance: harness.Instance, controller_version: str
):

    architecture = platform_util.get_current_rockcraft_platform_architecture()

    # Compose the Helm command line args for overriding the
    # image fields for each component:
    all_chart_value_overrides_args = []

    # TODO(aznashwan): enable when nginx rock is ready:
    # nginx_rock_info = env_util.get_build_meta_info_for_rock_version(
    #     "controller",
    #     controller_version,
    #     architecture,
    # )

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
    certgen_digest = certgen_tag.split('0')[0]
    all_chart_value_overrides_args.extend(
        [
            "--set",
            f"{certgen_chart_section}.image.registry={certgen_registry}",
            "--set",
            f"{certgen_chart_section}.image.image={certgen_image_name}",
            "--set",
            f"{certgen_chart_section}.image.tag={certgen_tag}",
            "--set",
            f"{certgen_chart_section}.image.digest=sha256:{certgen_digest}",
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

    # TODO(aznashwan): add checks for controller pod and certgen admission hook:
