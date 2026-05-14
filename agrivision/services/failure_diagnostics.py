from __future__ import annotations

import re


def summarize_failure(message: str) -> str:
    text = " ".join(message.strip().split())
    lower = text.lower()

    odm_match = re.search(r"ODM-(?P<label>[A-Za-z0-9_-]+) failed with exit code (?P<code>\d+)", text)
    if odm_match:
        label = odm_match.group("label").upper()
        code = int(odm_match.group("code"))
        if code == 125:
            return (
                f"ODM {label} could not start its Docker container. Check Docker Desktop, image availability, "
                "container name conflicts, and bind-mount paths."
            )
        if code == 137:
            return f"ODM {label} was killed by the system, usually because Docker ran out of memory. Increase Docker resources or reduce images."
        if code == 139:
            return (
                f"ODM {label} crashed during reconstruction. This often points to an ODM/OpenSfM crash, difficult imagery, "
                "or insufficient resources. Try reducing images or running ODM with more Docker memory."
            )
        return f"ODM {label} failed with exit code {code}. Open the run log for the full Docker/ODM output."

    if "docker compose was not found" in lower:
        return "Docker Compose was not found. Install Docker Desktop or make sure Docker is available on PATH."

    if "failed to run docker compose" in lower:
        if "sudo" in lower and "no such file" in lower:
            return "Docker Compose failed because this environment tried to use sudo, which is not available. Disable sudo usage or run from a Docker-capable host."
        return "Docker Compose failed while starting an external OpenAgri service. Check Docker Desktop and the service compose logs."

    service_match = re.search(r"Service in (?P<path>.+?) did not become reachable\. Checked: (?P<urls>.+)", text)
    if service_match:
        service_path = service_match.group("path")
        return f"External service did not become reachable from {service_path}. Check that its containers are running and the configured port matches the dashboard settings."

    if "cannot convert fill_value nan to dtype uint8" in lower:
        return "Preview generation failed because a byte raster was normalized with NaN fill values. The source artifact may still exist; check the run log."

    if text:
        return text
    return "Pipeline failed. Open the run log for details."
