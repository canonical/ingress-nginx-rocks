#
# Copyright 2024 Canonical, Ltd.
#

import json
import logging
import sys

import pytest
from k8s_test_harness.util import docker_util, env_util, platform_util

LOG: logging.Logger = logging.getLogger(__name__)

LOG.addHandler(logging.FileHandler(f"{__name__}.log"))
LOG.addHandler(logging.StreamHandler(sys.stdout))


IMAGE_NAME = "kube-webhook-certgen"
IMAGE_VERSIONS = ["v1.4.0", "v1.4.1"]


@pytest.mark.abort_on_fail
@pytest.mark.parametrize("image_version", IMAGE_VERSIONS)
def test_check_rock_image_contents(image_version):
    """Test ROCK contains same fileset as original image."""

    architecture = platform_util.get_current_rockcraft_platform_architecture()

    rock_meta = env_util.get_build_meta_info_for_rock_version(
        IMAGE_NAME, image_version, architecture
    )
    rock_image = rock_meta.image

    docker_util.ensure_image_contains_paths(
        rock_image,
        ["/kube-webhook-certgen", "/etc/nsswitch.conf"],
        override_entrypoint="busybox",
    )

    # NOTE(aznashwan): included for later reference against the upstream image:
    all_files = docker_util.list_files_under_container_image_dir(
        rock_image,
        root_dir="/",
        override_entrypoint="busybox",
    )
    LOG.debug(f"All files in {rock_image}: {json.dumps(all_files, indent=4)}")
