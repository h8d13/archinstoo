FROM registry.fedoraproject.org/fedora:44

# usage: podman build -t fedinstoo-dev .

# runtime deps from BOOT's DEPENDS, linters are pinned by pre-commit itself.
# python3 first: the base image has none to read BOOT with
COPY BOOT /tmp/BOOT
RUN dnf -y install python3 \
	&& python3 -c "import runpy; print(*runpy.run_path('/tmp/BOOT')['DEPENDS'])" \
		>/tmp/deps \
	&& xargs dnf -y --setopt=install_weak_deps=False install python3-pip </tmp/deps \
	&& dnf clean all \
	&& rm /tmp/BOOT /tmp/deps
