FROM archlinux/archlinux:latest

# same prep as .github/workflows/*.yaml
RUN pacman-key --init \
	&& pacman --noconfirm -Sy archlinux-keyring \
	&& pacman --noconfirm -Syu

# runtime deps from the release PKGBUILD, dev tooling comes from pip (see devcontainer.json)
COPY PKGBUILD /tmp/PKGBUILD
RUN . /tmp/PKGBUILD \
	&& pacman --noconfirm -S --needed "${depends[@]}" python-pip \
	&& pacman --noconfirm -Scc \
	&& rm /tmp/PKGBUILD
