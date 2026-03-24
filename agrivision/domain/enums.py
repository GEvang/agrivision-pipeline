from __future__ import annotations

from enum import Enum


class DeploymentProfile(str, Enum):
    STANDALONE = "standalone"
    DOCKER_LOCAL = "docker-local"
    DOCKER_WITH_SERVICES = "docker-with-openagri-services"
    EDGE_OFFLINE = "edge-offline"
